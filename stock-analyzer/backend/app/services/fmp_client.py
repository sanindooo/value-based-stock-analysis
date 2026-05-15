"""Async FMP (Financial Modeling Prep) API client.

Fetches fundamental stock data, caches it in Postgres via the Stock model,
and respects the 250 req/day free-tier limit.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.stock import Stock

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate-limit constants
# ---------------------------------------------------------------------------
DAILY_LIMIT = 250
RATE_WARN_THRESHOLD = 225  # warn when this many requests have been made
STALENESS_HOURS = 24
FMP_BASE = "https://financialmodelingprep.com/api/v3"
MAX_BATCH_TICKERS = 10  # FMP batch profile limit
MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB safety cap


# ---------------------------------------------------------------------------
# Pydantic response models for FMP API validation
# ---------------------------------------------------------------------------
class FMPScreenerItem(BaseModel):
    symbol: str
    companyName: str | None = None
    marketCap: float | None = None
    sector: str | None = None
    industry: str | None = None
    price: float | None = None


class FMPProfile(BaseModel):
    symbol: str
    companyName: str | None = None
    sector: str | None = None
    industry: str | None = None
    mktCap: float | None = None
    price: float | None = None

    # Value metrics available from profile
    pe: float | None = Field(None, alias="pe")


class FMPKeyMetricsTTM(BaseModel):
    peRatioTTM: float | None = None
    pegRatioTTM: float | None = None
    pbRatioTTM: float | None = None
    priceToSalesRatioTTM: float | None = None
    priceToCashFlowRatioTTM: float | None = None  # maps to price_to_cash (operating CF)
    pfcfRatioTTM: float | None = None  # maps to price_to_fcf
    currentRatioTTM: float | None = None
    quickRatioTTM: float | None = None
    debtToEquityTTM: float | None = None
    roeTTM: float | None = None
    roaTTM: float | None = None
    returnOnCapitalEmployedTTM: float | None = None  # maps to roi
    dividendYieldTTM: float | None = None
    netIncomePerShareTTM: float | None = None
    earningsYieldTTM: float | None = None


class FMPRatiosTTM(BaseModel):
    peRatioTTM: float | None = None
    pegRatioTTM: float | None = None
    priceBookValueRatioTTM: float | None = None
    priceToSalesRatioTTM: float | None = None
    priceToFreeCashFlowsRatioTTM: float | None = None
    priceCashFlowRatioTTM: float | None = None
    grossProfitMarginTTM: float | None = None
    operatingProfitMarginTTM: float | None = None
    netProfitMarginTTM: float | None = None
    returnOnEquityTTM: float | None = None
    returnOnAssetsTTM: float | None = None
    returnOnCapitalEmployedTTM: float | None = None
    currentRatioTTM: float | None = None
    quickRatioTTM: float | None = None
    debtEquityRatioTTM: float | None = None
    longTermDebtToCapitalizationTTM: float | None = None  # maps to lt_debt_to_equity
    dividendYieldTTM: float | None = None
    dividendYielTTM: float | None = None  # FMP typo in their API
    priceEarningsToGrowthRatioTTM: float | None = None


# ---------------------------------------------------------------------------
# FMP Client
# ---------------------------------------------------------------------------
class FMPClient:
    """Async wrapper around the FMP free-tier API."""

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
        """Make a GET request to FMP, enforce rate limit, return parsed JSON."""
        self._check_rate_limit()

        params = params or {}
        params["apikey"] = self._api_key
        url = f"{FMP_BASE}{path}"

        resp = await client.get(url, params=params)
        self._daily_requests += 1

        if resp.status_code == 429:
            raise RateLimitExceeded("FMP returned HTTP 429 — rate limited by server.")

        resp.raise_for_status()

        if len(resp.content) > MAX_RESPONSE_BYTES:
            raise FMPClientError("FMP response exceeded size limit.")

        return resp.json()

    # -- public API wrappers ------------------------------------------------

    async def screen_stocks(
        self,
        client: httpx.AsyncClient,
        market_cap_min: int = 100_000_000,
        country: str = "US",
        exchanges: str = "NYSE,NASDAQ,AMEX",
    ) -> list[FMPScreenerItem]:
        """Run the FMP stock screener and return matching tickers."""
        data = await self._get(
            client,
            "/stock-screener",
            params={
                "marketCapMoreThan": market_cap_min,
                "country": country,
                "exchange": exchanges,
            },
        )
        if not isinstance(data, list):
            return []
        return [FMPScreenerItem.model_validate(item) for item in data]

    async def batch_profile(
        self,
        client: httpx.AsyncClient,
        tickers: list[str],
    ) -> list[FMPProfile]:
        """Fetch profiles for up to MAX_BATCH_TICKERS tickers at once."""
        if not tickers:
            return []
        batch = tickers[:MAX_BATCH_TICKERS]
        ticker_str = ",".join(batch)
        data = await self._get(client, f"/profile/{ticker_str}")
        if not isinstance(data, list):
            return []
        return [FMPProfile.model_validate(item) for item in data]

    async def key_metrics_ttm(
        self,
        client: httpx.AsyncClient,
        ticker: str,
    ) -> FMPKeyMetricsTTM | None:
        """Fetch TTM key metrics for a single ticker."""
        data = await self._get(client, f"/key-metrics-ttm/{ticker}")
        if not isinstance(data, list) or len(data) == 0:
            return None
        return FMPKeyMetricsTTM.model_validate(data[0])

    async def ratios_ttm(
        self,
        client: httpx.AsyncClient,
        ticker: str,
    ) -> FMPRatiosTTM | None:
        """Fetch TTM ratios for a single ticker."""
        data = await self._get(client, f"/ratios-ttm/{ticker}")
        if not isinstance(data, list) or len(data) == 0:
            return None
        return FMPRatiosTTM.model_validate(data[0])

    # -- high-level: merge data into Stock model ----------------------------

    def map_to_stock(
        self,
        profile: FMPProfile | None,
        metrics: FMPKeyMetricsTTM | None,
        ratios: FMPRatiosTTM | None,
        ticker: str,
    ) -> dict[str, Any]:
        """Merge FMP data sources into a dict matching Stock model columns."""
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
                    "market_cap": profile.mktCap,
                    "price": profile.price,
                }
            )

        if metrics:
            result.update(
                {
                    "pe_ratio": metrics.peRatioTTM,
                    "peg_ratio": metrics.pegRatioTTM,
                    "pb_ratio": metrics.pbRatioTTM,
                    "ps_ratio": metrics.priceToSalesRatioTTM,
                    "price_to_cash": metrics.priceToCashFlowRatioTTM,
                    "price_to_fcf": metrics.pfcfRatioTTM,
                    "current_ratio": metrics.currentRatioTTM,
                    "quick_ratio": metrics.quickRatioTTM,
                    "debt_to_equity": metrics.debtToEquityTTM,
                    "roe": metrics.roeTTM,
                    "roa": metrics.roaTTM,
                    "roi": metrics.returnOnCapitalEmployedTTM,
                    "dividend_yield": metrics.dividendYieldTTM,
                }
            )

        if ratios:
            # Ratios endpoint has margin data and some metrics not in key-metrics
            result.update(
                {
                    "gross_margin": ratios.grossProfitMarginTTM,
                    "operating_margin": ratios.operatingProfitMarginTTM,
                    "net_profit_margin": ratios.netProfitMarginTTM,
                    "forward_pe": None,  # FMP free tier doesn't provide forward PE in TTM endpoints
                    "lt_debt_to_equity": ratios.longTermDebtToCapitalizationTTM,
                }
            )

            # Fill from ratios if key-metrics didn't have the value
            if result.get("pe_ratio") is None:
                result["pe_ratio"] = ratios.peRatioTTM
            if result.get("peg_ratio") is None:
                result["peg_ratio"] = ratios.priceEarningsToGrowthRatioTTM
            if result.get("pb_ratio") is None:
                result["pb_ratio"] = ratios.priceBookValueRatioTTM
            if result.get("ps_ratio") is None:
                result["ps_ratio"] = ratios.priceToSalesRatioTTM
            if result.get("price_to_fcf") is None:
                result["price_to_fcf"] = ratios.priceToFreeCashFlowsRatioTTM
            if result.get("price_to_cash") is None:
                result["price_to_cash"] = ratios.priceCashFlowRatioTTM
            if result.get("roe") is None:
                result["roe"] = ratios.returnOnEquityTTM
            if result.get("roa") is None:
                result["roa"] = ratios.returnOnAssetsTTM
            if result.get("roi") is None:
                result["roi"] = ratios.returnOnCapitalEmployedTTM
            if result.get("current_ratio") is None:
                result["current_ratio"] = ratios.currentRatioTTM
            if result.get("quick_ratio") is None:
                result["quick_ratio"] = ratios.quickRatioTTM
            if result.get("debt_to_equity") is None:
                result["debt_to_equity"] = ratios.debtEquityRatioTTM
            if result.get("dividend_yield") is None:
                result["dividend_yield"] = ratios.dividendYieldTTM or ratios.dividendYielTTM

        # Growth metrics are not available in TTM endpoints on the free tier.
        # They stay None and can be populated by other data sources later.
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
        # Check cache freshness
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

        # Fetch from FMP (3 requests per ticker)
        profile_list = await self.batch_profile(client, [ticker])
        profile = profile_list[0] if profile_list else None
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
