"""Async FMP (Financial Modeling Prep) API client — stable API.

Fetches fundamental stock data, caches it in Postgres via the Stock model,
and respects the 250 req/day free-tier limit.

Uses the /stable/ API (v3 was deprecated August 2025).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.stock import Stock

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate-limit constants
# ---------------------------------------------------------------------------
DAILY_LIMIT = 250
RATE_WARN_THRESHOLD = 225
STALENESS_HOURS = 24
FMP_BASE = "https://financialmodelingprep.com/stable"
MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB safety cap

# Fields returned as decimals by the stable API that we store as percentages.
# e.g. 0.33 from API → 33.0 in our DB.
_DECIMAL_TO_PCT_FIELDS = {
    "roe", "roa", "roi",
    "gross_margin", "operating_margin", "net_profit_margin",
    "dividend_yield",
}


# ---------------------------------------------------------------------------
# Pydantic response models for FMP stable API
# ---------------------------------------------------------------------------
class FMPProfile(BaseModel):
    symbol: str
    companyName: str | None = None
    sector: str | None = None
    industry: str | None = None
    marketCap: float | None = None
    price: float | None = None


class FMPKeyMetricsTTM(BaseModel):
    currentRatioTTM: float | None = None
    returnOnAssetsTTM: float | None = None
    returnOnEquityTTM: float | None = None
    returnOnCapitalEmployedTTM: float | None = None
    earningsYieldTTM: float | None = None


class FMPRatiosTTM(BaseModel):
    priceToEarningsRatioTTM: float | None = None
    priceToEarningsGrowthRatioTTM: float | None = None
    priceToBookRatioTTM: float | None = None
    priceToSalesRatioTTM: float | None = None
    priceToFreeCashFlowRatioTTM: float | None = None
    priceToOperatingCashFlowRatioTTM: float | None = None
    grossProfitMarginTTM: float | None = None
    operatingProfitMarginTTM: float | None = None
    netProfitMarginTTM: float | None = None
    currentRatioTTM: float | None = None
    quickRatioTTM: float | None = None
    debtToEquityRatioTTM: float | None = None
    longTermDebtToCapitalRatioTTM: float | None = None
    dividendYieldTTM: float | None = None
    dividendPerShareTTM: float | None = None


# ---------------------------------------------------------------------------
# FMP Client
# ---------------------------------------------------------------------------
class FMPClient:
    """Async wrapper around the FMP stable API (free tier)."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.fmp_api_key
        self._daily_requests = 0
        self._day_started: datetime = datetime.now(timezone.utc)

    # -- internal helpers ---------------------------------------------------

    def _reset_counter_if_new_day(self) -> None:
        now = datetime.now(timezone.utc)
        if now.date() > self._day_started.date():
            self._daily_requests = 0
            self._day_started = now

    def _check_rate_limit(self) -> None:
        self._reset_counter_if_new_day()
        if self._daily_requests >= DAILY_LIMIT:
            raise RateLimitExceeded(
                f"Daily FMP request limit reached ({DAILY_LIMIT}). "
                "Try again tomorrow or upgrade your plan."
            )
        if self._daily_requests >= RATE_WARN_THRESHOLD:
            logger.warning(
                "Approaching FMP daily limit: %d / %d requests used",
                self._daily_requests,
                DAILY_LIMIT,
            )

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict[str, Any] | None = None) -> Any:
        """Make a GET request to FMP stable API, enforce rate limit, return parsed JSON."""
        self._check_rate_limit()

        params = params or {}
        params["apikey"] = self._api_key
        url = f"{FMP_BASE}/{path}"

        resp = await client.get(url, params=params)
        self._daily_requests += 1

        if resp.status_code == 429:
            raise RateLimitExceeded("FMP returned HTTP 429 — rate limited by server.")

        resp.raise_for_status()

        if len(resp.content) > MAX_RESPONSE_BYTES:
            raise FMPClientError("FMP response exceeded size limit.")

        return resp.json()

    # -- public API wrappers ------------------------------------------------

    def get_candidate_tickers(self) -> list[str]:
        """Return a curated list of US large/mid-cap tickers for screening.

        FMP free tier doesn't include discovery endpoints. We maintain a
        curated universe across all GICS sectors. No API call needed.
        """
        return [
            # Technology
            "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AVGO", "ADBE", "CRM",
            "CSCO", "ORCL", "ACN", "INTC", "AMD", "TXN", "QCOM", "IBM",
            "NOW", "INTU", "AMAT", "MU",
            # Healthcare
            "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT",
            "DHR", "BMY", "AMGN", "GILD", "MDT", "SYK", "CI",
            # Financials
            "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS",
            "BLK", "SPGI", "AXP", "C", "SCHW", "CB", "MMC",
            # Consumer Discretionary
            "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TJX",
            "BKNG", "CMG", "ORLY", "ROST", "DHI", "GM", "F",
            # Consumer Staples
            "PG", "KO", "PEP", "COST", "WMT", "PM", "MO", "CL",
            "MDLZ", "GIS", "KHC", "STZ", "KMB", "SJM",
            # Energy
            "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO",
            "OXY", "HAL",
            # Industrials
            "CAT", "HON", "UNP", "UPS", "RTX", "BA", "DE", "LMT",
            "GE", "MMM", "EMR", "ITW", "WM", "FDX", "NSC",
            # Materials
            "LIN", "APD", "SHW", "ECL", "FCX", "NEM", "NUE", "DOW",
            # Real Estate
            "PLD", "AMT", "CCI", "EQIX", "SPG", "O", "WELL", "DLR",
            # Utilities
            "NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL",
            # Communication Services
            "GOOG", "DIS", "NFLX", "CMCSA", "T", "VZ", "TMUS", "CHTR",
        ]

    async def fetch_profile(
        self,
        client: httpx.AsyncClient,
        ticker: str,
    ) -> FMPProfile | None:
        """Fetch company profile for a single ticker."""
        data = await self._get(client, "profile", params={"symbol": ticker})
        if not isinstance(data, list) or len(data) == 0:
            return None
        return FMPProfile.model_validate(data[0])

    async def key_metrics_ttm(
        self,
        client: httpx.AsyncClient,
        ticker: str,
    ) -> FMPKeyMetricsTTM | None:
        """Fetch TTM key metrics for a single ticker."""
        data = await self._get(client, "key-metrics-ttm", params={"symbol": ticker})
        if not isinstance(data, list) or len(data) == 0:
            return None
        return FMPKeyMetricsTTM.model_validate(data[0])

    async def ratios_ttm(
        self,
        client: httpx.AsyncClient,
        ticker: str,
    ) -> FMPRatiosTTM | None:
        """Fetch TTM ratios for a single ticker."""
        data = await self._get(client, "ratios-ttm", params={"symbol": ticker})
        if not isinstance(data, list) or len(data) == 0:
            return None
        return FMPRatiosTTM.model_validate(data[0])

    # -- high-level: merge data into Stock model ----------------------------

    @staticmethod
    def _pct(value: float | None) -> float | None:
        """Convert a decimal value to percentage (0.33 → 33.0)."""
        return round(value * 100, 4) if value is not None else None

    def map_to_stock(
        self,
        profile: FMPProfile | None,
        metrics: FMPKeyMetricsTTM | None,
        ratios: FMPRatiosTTM | None,
        ticker: str,
    ) -> dict[str, Any]:
        """Merge FMP stable API data into a dict matching Stock model columns."""
        now = datetime.now(timezone.utc)
        result: dict[str, Any] = {
            "ticker": ticker,
            "last_updated": now,
        }

        if profile:
            result.update(
                {
                    "company_name": profile.companyName,
                    "sector": profile.sector,
                    "industry": profile.industry,
                    "market_cap": profile.marketCap,
                    "price": profile.price,
                }
            )

        # Key metrics provides returns (as decimals) and current ratio
        if metrics:
            result.update(
                {
                    "roe": self._pct(metrics.returnOnEquityTTM),
                    "roa": self._pct(metrics.returnOnAssetsTTM),
                    "roi": self._pct(metrics.returnOnCapitalEmployedTTM),
                    "current_ratio": metrics.currentRatioTTM,
                }
            )

        # Ratios provides pricing multiples, margins, and financial health
        if ratios:
            result.update(
                {
                    "pe_ratio": ratios.priceToEarningsRatioTTM,
                    "peg_ratio": ratios.priceToEarningsGrowthRatioTTM,
                    "pb_ratio": ratios.priceToBookRatioTTM,
                    "ps_ratio": ratios.priceToSalesRatioTTM,
                    "price_to_fcf": ratios.priceToFreeCashFlowRatioTTM,
                    "price_to_cash": ratios.priceToOperatingCashFlowRatioTTM,
                    "gross_margin": self._pct(ratios.grossProfitMarginTTM),
                    "operating_margin": self._pct(ratios.operatingProfitMarginTTM),
                    "net_profit_margin": self._pct(ratios.netProfitMarginTTM),
                    "quick_ratio": ratios.quickRatioTTM,
                    "debt_to_equity": ratios.debtToEquityRatioTTM,
                    "lt_debt_to_equity": ratios.longTermDebtToCapitalRatioTTM,
                    "dividend_yield": self._pct(ratios.dividendYieldTTM),
                    "forward_pe": None,
                }
            )

            # Fill current_ratio from ratios if key-metrics didn't have it
            if result.get("current_ratio") is None:
                result["current_ratio"] = ratios.currentRatioTTM

        # Growth metrics are not available in TTM endpoints on the free tier
        for growth_field in [
            "eps_growth_this_year",
            "eps_growth_next_year",
            "eps_growth_past_5y",
            "eps_growth_next_5y",
            "sales_growth_past_5y",
        ]:
            result.setdefault(growth_field, None)

        return result

    async def fetch_and_cache_ticker(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        ticker: str,
        force: bool = False,
    ) -> Stock:
        """Fetch data for a single ticker from FMP and upsert into DB.

        Skips the API call if cached data is less than STALENESS_HOURS old
        (unless force=True).
        """
        if not force:
            result = await db.execute(select(Stock).where(Stock.ticker == ticker))
            existing = result.scalar_one_or_none()
            if existing and existing.last_updated:
                age = datetime.now(timezone.utc) - existing.last_updated.replace(
                    tzinfo=timezone.utc
                )
                if age < timedelta(hours=STALENESS_HOURS):
                    logger.debug("Cache hit for %s (age=%s)", ticker, age)
                    return existing

        # 3 requests per ticker: profile, key-metrics-ttm, ratios-ttm
        profile = await self.fetch_profile(client, ticker)
        metrics = await self.key_metrics_ttm(client, ticker)
        ratios = await self.ratios_ttm(client, ticker)

        stock_data = self.map_to_stock(profile, metrics, ratios, ticker)

        # Upsert
        result = await db.execute(select(Stock).where(Stock.ticker == ticker))
        existing = result.scalar_one_or_none()
        if existing:
            for key, value in stock_data.items():
                setattr(existing, key, value)
            stock = existing
        else:
            stock = Stock(**stock_data)
            db.add(stock)

        await db.commit()
        await db.refresh(stock)
        return stock

    async def fetch_and_cache_batch(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        tickers: list[str],
        force: bool = False,
    ) -> list[Stock]:
        """Fetch and cache a list of tickers sequentially."""
        results: list[Stock] = []
        for ticker in tickers:
            try:
                stock = await self.fetch_and_cache_ticker(client, db, ticker, force=force)
                results.append(stock)
            except RateLimitExceeded:
                logger.error("Rate limit hit during batch — stopping at %d/%d tickers", len(results), len(tickers))
                break
            except (httpx.HTTPStatusError, FMPClientError) as exc:
                logger.warning("Failed to fetch %s: %s", ticker, exc)
                continue
        return results

    @property
    def requests_remaining(self) -> int:
        self._reset_counter_if_new_day()
        return max(0, DAILY_LIMIT - self._daily_requests)

    @property
    def requests_used(self) -> int:
        self._reset_counter_if_new_day()
        return self._daily_requests


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class FMPClientError(Exception):
    """Generic FMP client error."""


class RateLimitExceeded(FMPClientError):
    """Daily request quota exhausted."""
