"""Yahoo Finance client — fetches fundamental data via yfinance.

No API key required. Rate limits are generous (~2000 req/hr).
Used as the primary data source for stock screening metrics.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock

logger = logging.getLogger(__name__)


def _pct(value: float | None) -> float | None:
    """Convert decimal ratio to percentage (0.33 → 33.0)."""
    return round(value * 100, 4) if value is not None else None


def _safe_float(info: dict, key: str) -> float | None:
    v = info.get(key)
    if v is None or v == "Infinity" or v == "-Infinity":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fetch_ticker_sync(ticker: str) -> dict[str, Any]:
    """Synchronous yfinance fetch — runs in a thread via asyncio."""
    import yfinance as yf

    t = yf.Ticker(ticker)
    info = t.info

    if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
        raise ValueError(f"No data returned for {ticker}")

    price = _safe_float(info, "currentPrice") or _safe_float(info, "regularMarketPrice")
    market_cap = _safe_float(info, "marketCap")

    # Compute price-to-FCF and price-to-operating-cash if not directly provided
    fcf = _safe_float(info, "freeCashflow")
    ocf = _safe_float(info, "operatingCashflow")
    shares = _safe_float(info, "sharesOutstanding")

    price_to_fcf = None
    price_to_cash = None
    if price and shares:
        if fcf and fcf > 0:
            price_to_fcf = round(market_cap / fcf, 4) if market_cap else None
        if ocf and ocf > 0:
            price_to_cash = round(market_cap / ocf, 4) if market_cap else None

    # 52-week trading range as percentage
    high_52 = _safe_float(info, "fiftyTwoWeekHigh")
    low_52 = _safe_float(info, "fiftyTwoWeekLow")
    trading_range = None
    if high_52 and low_52 and low_52 > 0:
        trading_range = round((high_52 - low_52) / low_52 * 100, 2)

    return {
        "ticker": ticker,
        "company_name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": market_cap,
        "price": price,
        "website": info.get("website"),
        "beta": _safe_float(info, "beta"),
        # Value metrics
        "pe_ratio": _safe_float(info, "trailingPE"),
        "forward_pe": _safe_float(info, "forwardPE"),
        "peg_ratio": _safe_float(info, "pegRatio"),
        "pb_ratio": _safe_float(info, "priceToBook"),
        "ps_ratio": _safe_float(info, "priceToSalesTrailing12Months"),
        "price_to_fcf": price_to_fcf,
        "price_to_cash": price_to_cash,
        # Profitability (yfinance returns decimals — convert to %)
        "roe": _pct(_safe_float(info, "returnOnEquity")),
        "roa": _pct(_safe_float(info, "returnOnAssets")),
        "roi": None,
        "gross_margin": _pct(_safe_float(info, "grossMargins")),
        "operating_margin": _pct(_safe_float(info, "operatingMargins")),
        "net_profit_margin": _pct(_safe_float(info, "profitMargins")),
        "dividend_yield": _pct(_safe_float(info, "dividendYield")),
        "dividend_payout": _pct(_safe_float(info, "payoutRatio")),
        # Financial health (yfinance reports D/E as percentage, convert to ratio)
        "current_ratio": _safe_float(info, "currentRatio"),
        "quick_ratio": _safe_float(info, "quickRatio"),
        "debt_to_equity": _safe_float(info, "debtToEquity") / 100 if _safe_float(info, "debtToEquity") is not None else None,
        "lt_debt_to_equity": None,
        "debt_to_ebitda": None,
        # Book value
        "book_value_per_share": _safe_float(info, "bookValue"),
        # Growth
        "eps_growth_this_year": _pct(_safe_float(info, "earningsGrowth")),
        "eps_growth_next_year": _pct(_safe_float(info, "earningsQuarterlyGrowth")),
        "eps_growth_past_5y": None,
        "eps_growth_next_5y": None,
        "sales_growth_past_5y": None,
        "projected_earnings_growth": _pct(_safe_float(info, "revenueGrowth")),
        # Other
        "analyst_rating": _safe_float(info, "recommendationMean"),
        "trading_range_12m": trading_range,
        "data_warnings": None,
        "last_updated": datetime.now(timezone.utc),
    }


async def fetch_yahoo_ticker(ticker: str) -> dict[str, Any]:
    """Fetch data for a single ticker asynchronously."""
    return await asyncio.to_thread(_fetch_ticker_sync, ticker)


async def fetch_and_cache_yahoo(
    db: AsyncSession,
    ticker: str,
    force: bool = False,
) -> Stock:
    """Fetch from Yahoo Finance and upsert into DB."""
    from datetime import timedelta

    if not force:
        result = await db.execute(select(Stock).where(Stock.ticker == ticker))
        existing = result.scalar_one_or_none()
        if existing and existing.last_updated:
            age = datetime.now(timezone.utc) - existing.last_updated.replace(tzinfo=timezone.utc)
            if age < timedelta(hours=24):
                return existing

    data = await fetch_yahoo_ticker(ticker)

    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    existing = result.scalar_one_or_none()
    if existing:
        for key, value in data.items():
            setattr(existing, key, value)
        stock = existing
    else:
        stock = Stock(**data)
        db.add(stock)

    await db.commit()
    await db.refresh(stock)
    return stock


async def fetch_and_cache_yahoo_batch(
    db: AsyncSession,
    tickers: list[str],
    force: bool = False,
    max_concurrency: int = 5,
) -> list[Stock]:
    """Fetch and cache multiple tickers with bounded concurrency."""
    from app.db import async_session

    sem = asyncio.Semaphore(max_concurrency)
    results: list[Stock] = []

    async def _fetch_one(t: str) -> Stock | None:
        async with sem:
            try:
                async with async_session() as ticker_db:
                    return await fetch_and_cache_yahoo(ticker_db, t, force=force)
            except Exception as exc:
                logger.warning("Failed to fetch %s from Yahoo: %s", t, exc)
                return None

    batch_results = await asyncio.gather(*[_fetch_one(t) for t in tickers])
    for stock in batch_results:
        if stock is not None:
            results.append(stock)

    return results
