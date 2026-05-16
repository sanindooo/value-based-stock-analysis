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


def _bs_value(bs: Any, col: Any, row_name: str) -> float | None:
    """Extract a value from a yfinance balance sheet DataFrame by row name."""
    import math
    if row_name in bs.index:
        val = bs.loc[row_name, col]
        if val is not None and not (isinstance(val, float) and math.isnan(val)):
            return float(val)
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

    # Primary values from info dict
    pe_ratio = _safe_float(info, "trailingPE")
    peg_ratio = _safe_float(info, "pegRatio")
    current_ratio = _safe_float(info, "currentRatio")
    debt_to_equity_raw = _safe_float(info, "debtToEquity")
    debt_to_equity = debt_to_equity_raw / 100 if debt_to_equity_raw is not None else None
    book_value = _safe_float(info, "bookValue")
    earnings_growth = _safe_float(info, "earningsGrowth")

    # PEG fallback: P/E ÷ (earningsGrowth × 100)
    if peg_ratio is None and pe_ratio and earnings_growth and earnings_growth > 0:
        peg_ratio = round(pe_ratio / (earnings_growth * 100), 4)

    # Balance sheet fallbacks for D/E, Current Ratio, Book Value
    needs_balance_sheet = (
        debt_to_equity is None or current_ratio is None or book_value is None
    )
    if needs_balance_sheet:
        try:
            bs = t.balance_sheet
            if not bs.empty:
                col = bs.columns[0]

                if debt_to_equity is None:
                    total_liab = _bs_value(bs, col, "Total Liabilities Net Minority Interest")
                    equity = _bs_value(bs, col, "Stockholders Equity") or _bs_value(bs, col, "Common Stock Equity")
                    if total_liab is not None and equity and equity > 0:
                        debt_to_equity = round(total_liab / equity, 4)

                if current_ratio is None:
                    cur_assets = _bs_value(bs, col, "Current Assets")
                    cur_liab = _bs_value(bs, col, "Current Liabilities")
                    if cur_assets and cur_liab and cur_liab > 0:
                        current_ratio = round(cur_assets / cur_liab, 4)

                if book_value is None and shares:
                    equity = _bs_value(bs, col, "Stockholders Equity") or _bs_value(bs, col, "Common Stock Equity")
                    if equity and shares > 0:
                        book_value = round(equity / shares, 4)
        except Exception:
            pass

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
        "pe_ratio": pe_ratio,
        "forward_pe": _safe_float(info, "forwardPE"),
        "peg_ratio": peg_ratio,
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
        # Financial health
        "current_ratio": current_ratio,
        "quick_ratio": _safe_float(info, "quickRatio"),
        "debt_to_equity": debt_to_equity,
        "lt_debt_to_equity": None,
        "debt_to_ebitda": None,
        # Book value
        "book_value_per_share": book_value,
        # Growth
        "eps_growth_this_year": _pct(earnings_growth),
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


class BatchProgress:
    """Tracks batch fetch progress for UI reporting."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.done = 0
        self.cached = 0
        self.fetched = 0
        self.failed = 0

    def snapshot(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "done": self.done,
            "cached": self.cached,
            "fetched": self.fetched,
            "failed": self.failed,
        }


async def fetch_and_cache_yahoo_batch(
    db: AsyncSession,
    tickers: list[str],
    force: bool = False,
    max_concurrency: int | None = None,
    on_progress: Any | None = None,
) -> list[Stock]:
    """Fetch and cache multiple tickers with bounded concurrency.

    on_progress: async callable(BatchProgress) called every 50 tickers.
    """
    from app.core.config import settings
    from app.db import async_session

    concurrency = max_concurrency or settings.yahoo_concurrency
    sem = asyncio.Semaphore(concurrency)
    results: list[Stock] = []
    total = len(tickers)
    progress = BatchProgress(total)

    async def _fetch_one(t: str) -> Stock | None:
        async with sem:
            try:
                async with async_session() as ticker_db:
                    was_cached = False
                    if not force:
                        from datetime import timedelta
                        result = await ticker_db.execute(select(Stock).where(Stock.ticker == t))
                        existing = result.scalar_one_or_none()
                        if existing and existing.last_updated:
                            age = datetime.now(timezone.utc) - existing.last_updated.replace(tzinfo=timezone.utc)
                            if age < timedelta(hours=24):
                                was_cached = True

                    stock = await fetch_and_cache_yahoo(ticker_db, t, force=force)
                    progress.done += 1
                    if was_cached:
                        progress.cached += 1
                    else:
                        progress.fetched += 1

                    if progress.done % 50 == 0:
                        logger.info(
                            "Yahoo batch: %d/%d done (%d cached, %d fetched, %d failed)",
                            progress.done, total, progress.cached, progress.fetched, progress.failed,
                        )
                        if on_progress:
                            await on_progress(progress)
                    return stock
            except Exception as exc:
                progress.done += 1
                progress.failed += 1
                logger.warning("Failed to fetch %s from Yahoo: %s", t, exc)
                return None

    logger.info("Fetching %d tickers from Yahoo Finance (concurrency=%d)", total, concurrency)
    batch_results = await asyncio.gather(*[_fetch_one(t) for t in tickers])
    for stock in batch_results:
        if stock is not None:
            results.append(stock)

    # Final progress update
    if on_progress:
        await on_progress(progress)

    logger.info(
        "Yahoo batch complete: %d/%d succeeded (%d cached, %d fetched, %d failed)",
        len(results), total, progress.cached, progress.fetched, progress.failed,
    )
    return results
