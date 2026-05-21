"""SerpApi news discovery — finds article URLs for deep analysis."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_RESULTS = 10


@dataclass
class DiscoveredArticle:
    title: str
    url: str
    source: str
    published_date: str
    snippet: str


def _build_queries(ticker: str, company_name: str | None = None) -> list[str]:
    queries = [f"{ticker} stock"]
    if company_name:
        queries.append(company_name)
        queries.append(f"{company_name} earnings")
    return queries


def _search_sync(
    query: str,
    api_key: str,
    num_results: int = 10,
) -> list[DiscoveredArticle]:
    with httpx.Client(timeout=15) as client:
        resp = client.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_news",
                "q": query,
                "api_key": api_key,
                "num": num_results,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    articles: list[DiscoveredArticle] = []
    for item in data.get("news_results", []):
        url = item.get("link", "")
        if not url:
            continue
        articles.append(
            DiscoveredArticle(
                title=item.get("title", ""),
                url=url,
                source=item.get("source", {}).get("name", "") if isinstance(item.get("source"), dict) else str(item.get("source", "")),
                published_date=item.get("date", ""),
                snippet=item.get("snippet", ""),
            )
        )
    return articles


async def discover_articles(
    ticker: str,
    company_name: str | None = None,
) -> list[DiscoveredArticle]:
    api_key = settings.serpapi_api_key
    if not api_key:
        logger.warning("No SerpApi API key configured, skipping article discovery")
        return []

    queries = _build_queries(ticker, company_name)
    seen_urls: set[str] = set()
    all_articles: list[DiscoveredArticle] = []

    for query in queries:
        try:
            results = await asyncio.to_thread(_search_sync, query, api_key)
            for article in results:
                if article.url not in seen_urls:
                    seen_urls.add(article.url)
                    all_articles.append(article)
        except Exception as exc:
            logger.warning("SerpApi search failed for query '%s': %s", query, exc)

    return all_articles[:MAX_RESULTS]
