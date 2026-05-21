"""Finnhub news client.

Fetches recent company news articles, sorted by date,
limited to the most relevant items.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import finnhub

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_ARTICLES = 15


@dataclass
class NewsArticle:
    headline: str
    summary: str
    source: str
    url: str
    published_at: str


class NewsClientError(Exception):
    """Generic news client error."""


def _fetch_news_sync(
    ticker: str,
    months_back: int = 6,
    api_key: str | None = None,
) -> list[NewsArticle]:
    """Synchronous function to fetch news from Finnhub.

    Called via asyncio.to_thread() from async context since
    the finnhub Python client is synchronous.
    """
    key = api_key or settings.finnhub_api_key
    if not key:
        logger.warning("No Finnhub API key configured, skipping news fetch")
        return []

    client = finnhub.Client(api_key=key)

    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=months_back * 30)).strftime("%Y-%m-%d")
    date_to = now.strftime("%Y-%m-%d")

    try:
        raw_news = client.company_news(ticker, _from=date_from, to=date_to)
    except Exception as exc:
        logger.error("Finnhub news fetch failed for %s: %s", ticker, exc)
        return []

    if not raw_news or not isinstance(raw_news, list):
        return []

    # Sort by datetime descending, take top N
    raw_news.sort(key=lambda x: x.get("datetime", 0), reverse=True)
    raw_news = raw_news[:MAX_ARTICLES]

    articles: list[NewsArticle] = []
    for item in raw_news:
        published_ts = item.get("datetime", 0)
        published_str = (
            datetime.fromtimestamp(published_ts, tz=timezone.utc).isoformat()
            if published_ts
            else ""
        )
        articles.append(
            NewsArticle(
                headline=item.get("headline", ""),
                summary=item.get("summary", ""),
                source=item.get("source", ""),
                url=item.get("url", ""),
                published_at=published_str,
            )
        )

    return articles


async def fetch_news(
    ticker: str,
    months_back: int = 6,
    api_key: str | None = None,
) -> list[NewsArticle]:
    """Fetch recent news articles for a ticker.

    Wraps the synchronous Finnhub client in asyncio.to_thread().
    """
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_fetch_news_sync, ticker, months_back, api_key),
            timeout=30,
        )
    except asyncio.TimeoutError:
        logger.warning("Finnhub news fetch timed out for %s after 30s", ticker)
        return []
    except Exception as exc:
        logger.error("News fetch failed for %s: %s", ticker, exc)
        return []
