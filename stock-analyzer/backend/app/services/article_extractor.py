"""Article extraction — three-tier cascade for full article content."""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import logging
import re
import socket
import threading
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10MB
MAX_ARTICLE_CONTENT = 1024 * 1024  # 1MB after cleaning
MIN_CONTENT_LENGTH = 100

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

_ua_index = 0


@dataclass
class ExtractedArticle:
    title: str
    content: str
    summary: str
    publication_date: str


def _is_private_ip(addr_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(addr_str)
        return any(addr in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False


def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    lower = hostname.lower()
    if lower in ("localhost", "localhost.localdomain"):
        return False

    try:
        addr = ipaddress.ip_address(hostname)
        return not any(addr in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        pass

    try:
        resolved = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in resolved:
            if _is_private_ip(sockaddr[0]):
                return False
    except socket.gaierror:
        pass

    return True


def _get_ua() -> str:
    global _ua_index
    ua = _USER_AGENTS[_ua_index % len(_USER_AGENTS)]
    _ua_index += 1
    return ua


def _fetch_html_sync(url: str, budget: "_ZyteBudget | None" = None) -> str | None:
    try:
        with httpx.Client(timeout=15, follow_redirects=True, max_redirects=5) as client:
            resp = client.get(url, headers={"User-Agent": _get_ua()})
            if resp.status_code in (403, 429):
                return _fetch_via_zyte_sync(url, budget)
            resp.raise_for_status()
            content = resp.text[:MAX_CONTENT_SIZE]
            replacement_ratio = content.count("�") / max(len(content), 1)
            if replacement_ratio > 0.05:
                return _fetch_via_zyte_sync(url, budget)
            return content
    except httpx.HTTPStatusError:
        return _fetch_via_zyte_sync(url, budget)
    except Exception as exc:
        logger.warning("HTTP fetch failed for %s: %s", url, type(exc).__name__)
        return None


class _ZyteBudget:
    def __init__(self, cap: int):
        self._used = 0
        self._cap = cap
        self._lock = threading.Lock()

    def try_consume(self) -> bool:
        with self._lock:
            if self._used >= self._cap:
                return False
            self._used += 1
            return True


def create_zyte_budget() -> _ZyteBudget:
    return _ZyteBudget(settings.zyte_max_articles_per_analysis)


def _fetch_via_zyte_sync(url: str, budget: "_ZyteBudget | None" = None) -> str | None:
    api_key = settings.zyte_api_key
    if not api_key:
        logger.debug("Zyte API key not configured, skipping fallback for %s", url)
        return None

    if budget and not budget.try_consume():
        logger.debug("Zyte budget cap reached, skipping %s", url)
        return None

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                "https://api.zyte.com/v1/extract",
                auth=(api_key, ""),
                json={"url": url, "httpResponseBody": True},
            )
            resp.raise_for_status()
            data = resp.json()
            body = data.get("httpResponseBody", "")
            if not body:
                logger.warning("Zyte returned empty body for %s", url)
                return None
            return base64.b64decode(body).decode("utf-8", errors="replace")[:MAX_CONTENT_SIZE]
    except Exception as exc:
        logger.warning("Zyte fetch failed for %s: %s", url, type(exc).__name__)
        return None


def _extract_trafilatura(html: str, url: str) -> tuple[str | None, str]:
    """Returns (content, title). Title is extracted alongside content to avoid double parsing."""
    try:
        from trafilatura import bare_extraction
        result = bare_extraction(html, url=url, favor_precision=True)
        if result and result.get("text"):
            text = result["text"]
            title = result.get("title", "") or ""
            if len(text) >= MIN_CONTENT_LENGTH:
                return text, title
    except Exception as exc:
        logger.debug("Trafilatura extraction failed: %s", exc)
    return None, ""


def _extract_readability(html: str) -> str | None:
    try:
        from readability import Document
        doc = Document(html)
        summary = doc.summary()
        from html.parser import HTMLParser

        class _TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts: list[str] = []
            def handle_data(self, data):
                self.parts.append(data)

        extractor = _TextExtractor()
        extractor.feed(summary)
        text = " ".join(extractor.parts).strip()
        if len(text) >= MIN_CONTENT_LENGTH:
            return text
    except Exception as exc:
        logger.debug("Readability extraction failed: %s", exc)
    return None


def _extract_bs4(html: str) -> str | None:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        article = soup.find("article") or soup.find("main") or soup.find("body")
        if article:
            text = article.get_text(separator=" ", strip=True)
            if len(text) >= MIN_CONTENT_LENGTH:
                return text
    except Exception as exc:
        logger.debug("BeautifulSoup extraction failed: %s", exc)
    return None


def clean_content(text: str) -> str:
    text = re.sub(r"\[!\[.*?\]\(.*?\)\]\(.*?\)", "", text)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\(.*?\)", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()[:MAX_ARTICLE_CONTENT]


def _fetch_and_extract_sync(url: str, budget: "_ZyteBudget | None" = None) -> ExtractedArticle | None:
    html = _fetch_html_sync(url, budget)
    if not html:
        return None

    title = ""
    content, title = _extract_trafilatura(html, url)
    if not content:
        content = _extract_readability(html)
    if not content:
        content = _extract_bs4(html)
    if not content:
        logger.debug("All extraction tiers failed for %s", url)
        return None

    content = clean_content(content)

    return ExtractedArticle(
        title=title,
        content=content,
        summary=content[:200] + "..." if len(content) > 200 else content,
        publication_date="",
    )


async def fetch_and_extract(url: str, budget: "_ZyteBudget | None" = None) -> ExtractedArticle | None:
    if not is_safe_url(url):
        logger.warning("Blocked unsafe URL: %s", url)
        return None
    return await asyncio.to_thread(_fetch_and_extract_sync, url, budget)
