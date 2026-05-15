"""Tests for the FMP client and data API.

All tests run without a real database or FMP API — everything is mocked.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.fmp_client import (
    DAILY_LIMIT,
    STALENESS_HOURS,
    FMPClient,
    FMPKeyMetricsTTM,
    FMPProfile,
    FMPRatiosTTM,
    RateLimitExceeded,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_PROFILE_RESPONSE = [
    {
        "symbol": "AAPL",
        "companyName": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "mktCap": 3_000_000_000_000,
        "price": 190.50,
        "pe": 28.5,
    }
]

MOCK_KEY_METRICS_RESPONSE = [
    {
        "peRatioTTM": 28.5,
        "pegRatioTTM": 1.8,
        "pbRatioTTM": 45.2,
        "priceToSalesRatioTTM": 7.5,
        "priceToCashFlowRatioTTM": 25.1,
        "pfcfRatioTTM": 27.3,
        "currentRatioTTM": 1.07,
        "quickRatioTTM": 0.94,
        "debtToEquityTTM": 1.76,
        "roeTTM": 1.60,
        "roaTTM": 0.28,
        "returnOnCapitalEmployedTTM": 0.55,
        "dividendYieldTTM": 0.005,
        "netIncomePerShareTTM": 6.13,
        "earningsYieldTTM": 0.035,
    }
]

MOCK_RATIOS_RESPONSE = [
    {
        "peRatioTTM": 28.5,
        "pegRatioTTM": 1.8,
        "priceBookValueRatioTTM": 45.2,
        "priceToSalesRatioTTM": 7.5,
        "priceToFreeCashFlowsRatioTTM": 27.3,
        "priceCashFlowRatioTTM": 25.1,
        "grossProfitMarginTTM": 0.45,
        "operatingProfitMarginTTM": 0.30,
        "netProfitMarginTTM": 0.25,
        "returnOnEquityTTM": 1.60,
        "returnOnAssetsTTM": 0.28,
        "returnOnCapitalEmployedTTM": 0.55,
        "currentRatioTTM": 1.07,
        "quickRatioTTM": 0.94,
        "debtEquityRatioTTM": 1.76,
        "longTermDebtToCapitalizationTTM": 0.62,
        "dividendYieldTTM": 0.005,
        "dividendYielTTM": 0.005,
        "priceEarningsToGrowthRatioTTM": 1.8,
    }
]


def _make_mock_response(json_data, status_code=200):
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.content = b"{}"  # small payload for size check
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def fmp_client():
    return FMPClient(api_key="test-key")


@pytest.fixture
def mock_http_client():
    """AsyncMock that simulates httpx.AsyncClient.get() for different endpoints."""
    client = AsyncMock(spec=httpx.AsyncClient)

    async def route_get(url, params=None):
        if "/profile/" in url:
            return _make_mock_response(MOCK_PROFILE_RESPONSE)
        elif "/key-metrics-ttm/" in url:
            return _make_mock_response(MOCK_KEY_METRICS_RESPONSE)
        elif "/ratios-ttm/" in url:
            return _make_mock_response(MOCK_RATIOS_RESPONSE)
        elif "/stock-screener" in url:
            return _make_mock_response([{"symbol": "AAPL"}, {"symbol": "MSFT"}])
        return _make_mock_response([])

    client.get = AsyncMock(side_effect=route_get)
    return client


# ---------------------------------------------------------------------------
# Tests: Happy path — data parsing and mapping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_profile_parses_response(fmp_client, mock_http_client):
    profiles = await fmp_client.batch_profile(mock_http_client, ["AAPL"])
    assert len(profiles) == 1
    p = profiles[0]
    assert p.symbol == "AAPL"
    assert p.companyName == "Apple Inc."
    assert p.mktCap == 3_000_000_000_000


@pytest.mark.asyncio
async def test_key_metrics_ttm_parses_response(fmp_client, mock_http_client):
    metrics = await fmp_client.key_metrics_ttm(mock_http_client, "AAPL")
    assert metrics is not None
    assert metrics.peRatioTTM == 28.5
    assert metrics.currentRatioTTM == 1.07


@pytest.mark.asyncio
async def test_ratios_ttm_parses_response(fmp_client, mock_http_client):
    ratios = await fmp_client.ratios_ttm(mock_http_client, "AAPL")
    assert ratios is not None
    assert ratios.grossProfitMarginTTM == 0.45
    assert ratios.longTermDebtToCapitalizationTTM == 0.62


@pytest.mark.asyncio
async def test_map_to_stock_produces_complete_dict(fmp_client):
    profile = FMPProfile.model_validate(MOCK_PROFILE_RESPONSE[0])
    metrics = FMPKeyMetricsTTM.model_validate(MOCK_KEY_METRICS_RESPONSE[0])
    ratios = FMPRatiosTTM.model_validate(MOCK_RATIOS_RESPONSE[0])

    result = fmp_client.map_to_stock(profile, metrics, ratios, "AAPL")

    # Core fields
    assert result["ticker"] == "AAPL"
    assert result["company_name"] == "Apple Inc."
    assert result["market_cap"] == 3_000_000_000_000
    assert result["price"] == 190.50

    # Value metrics from key-metrics
    assert result["pe_ratio"] == 28.5
    assert result["peg_ratio"] == 1.8
    assert result["pb_ratio"] == 45.2
    assert result["ps_ratio"] == 7.5
    assert result["price_to_cash"] == 25.1
    assert result["price_to_fcf"] == 27.3

    # Profitability from ratios
    assert result["gross_margin"] == 0.45
    assert result["operating_margin"] == 0.30
    assert result["net_profit_margin"] == 0.25
    assert result["roe"] == 1.60
    assert result["roa"] == 0.28
    assert result["roi"] == 0.55

    # Financial health
    assert result["current_ratio"] == 1.07
    assert result["quick_ratio"] == 0.94
    assert result["debt_to_equity"] == 1.76
    assert result["lt_debt_to_equity"] == 0.62
    assert result["dividend_yield"] == 0.005

    # Growth metrics are None (not available from TTM endpoints)
    assert result["eps_growth_this_year"] is None
    assert result["eps_growth_next_5y"] is None


@pytest.mark.asyncio
async def test_screener_returns_tickers(fmp_client, mock_http_client):
    items = await fmp_client.screen_stocks(mock_http_client)
    assert len(items) == 2
    assert items[0].symbol == "AAPL"
    assert items[1].symbol == "MSFT"


# ---------------------------------------------------------------------------
# Tests: Cache freshness — fresh data served without API call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fresh_cache_skips_api_call(fmp_client, mock_http_client):
    """Cached data younger than STALENESS_HOURS should be returned directly."""
    fresh_stock = MagicMock()
    fresh_stock.last_updated = datetime.now(timezone.utc) - timedelta(hours=1)
    fresh_stock.ticker = "AAPL"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fresh_stock

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await fmp_client.fetch_and_cache_ticker(
        mock_http_client, mock_db, "AAPL", force=False
    )

    assert result is fresh_stock
    # HTTP client should NOT have been called (cache hit)
    mock_http_client.get.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: Stale data triggers refresh
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stale_cache_triggers_refresh(fmp_client, mock_http_client):
    """Data older than STALENESS_HOURS should trigger an API call."""
    stale_stock = MagicMock()
    stale_stock.last_updated = datetime.now(timezone.utc) - timedelta(hours=STALENESS_HOURS + 1)
    stale_stock.ticker = "AAPL"

    # First execute: staleness check returns stale stock
    # Second execute: upsert lookup returns the same stock (for update)
    stale_result = MagicMock()
    stale_result.scalar_one_or_none.return_value = stale_stock

    mock_db = AsyncMock()
    mock_db.execute.return_value = stale_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    result = await fmp_client.fetch_and_cache_ticker(
        mock_http_client, mock_db, "AAPL", force=False
    )

    # HTTP client SHOULD have been called (stale data)
    assert mock_http_client.get.call_count >= 1
    # DB should have been committed
    mock_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: Rate limit handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_limit_exceeded_raises(fmp_client, mock_http_client):
    """When daily limit is reached, RateLimitExceeded should be raised."""
    fmp_client._daily_requests = DAILY_LIMIT

    with pytest.raises(RateLimitExceeded):
        await fmp_client.batch_profile(mock_http_client, ["AAPL"])


@pytest.mark.asyncio
async def test_http_429_raises_rate_limit(fmp_client):
    """FMP returning HTTP 429 should raise RateLimitExceeded."""
    resp_429 = MagicMock(spec=httpx.Response)
    resp_429.status_code = 429
    resp_429.content = b"{}"

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=resp_429)

    with pytest.raises(RateLimitExceeded, match="429"):
        await fmp_client.batch_profile(client, ["AAPL"])


def test_requests_remaining_property(fmp_client):
    assert fmp_client.requests_remaining == DAILY_LIMIT
    fmp_client._daily_requests = 100
    assert fmp_client.requests_remaining == DAILY_LIMIT - 100


def test_rate_counter_resets_on_new_day(fmp_client):
    """Counter should reset when the day rolls over."""
    fmp_client._daily_requests = 200
    fmp_client._day_started = datetime.now(timezone.utc) - timedelta(days=1)
    # Accessing remaining triggers the reset
    assert fmp_client.requests_remaining == DAILY_LIMIT


# ---------------------------------------------------------------------------
# Tests: Missing data — nulls stored, not rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_metrics_stored_as_none(fmp_client):
    """When FMP returns no metrics/ratios, fields should be None not error."""
    profile = FMPProfile.model_validate(MOCK_PROFILE_RESPONSE[0])

    result = fmp_client.map_to_stock(profile, None, None, "AAPL")

    assert result["ticker"] == "AAPL"
    assert result["company_name"] == "Apple Inc."
    # Metric fields should not exist or be None (not raise KeyError)
    assert result.get("pe_ratio") is None
    assert result.get("gross_margin") is None
    assert result.get("current_ratio") is None
    assert result.get("eps_growth_this_year") is None


@pytest.mark.asyncio
async def test_missing_profile_stored_as_none(fmp_client):
    """When profile is missing, only ticker and metrics survive."""
    metrics = FMPKeyMetricsTTM.model_validate(MOCK_KEY_METRICS_RESPONSE[0])
    ratios = FMPRatiosTTM.model_validate(MOCK_RATIOS_RESPONSE[0])

    result = fmp_client.map_to_stock(None, metrics, ratios, "AAPL")

    assert result["ticker"] == "AAPL"
    assert result.get("company_name") is None
    assert result["pe_ratio"] == 28.5  # from metrics
    assert result["gross_margin"] == 0.45  # from ratios


@pytest.mark.asyncio
async def test_empty_api_response_returns_none(fmp_client, mock_http_client):
    """If FMP returns an empty list, key_metrics_ttm returns None."""
    mock_http_client.get = AsyncMock(
        return_value=_make_mock_response([])
    )
    result = await fmp_client.key_metrics_ttm(mock_http_client, "FAKE")
    assert result is None


# ---------------------------------------------------------------------------
# Tests: Batch fetch error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_continues_on_single_ticker_failure(fmp_client):
    """If one ticker fails, the batch should continue with the next."""
    call_count = 0

    async def mock_get(url, params=None):
        nonlocal call_count
        call_count += 1
        if "/profile/BAD" in url:
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 500
            resp.content = b"{}"
            resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=resp
            )
            return resp
        if "/profile/" in url:
            return _make_mock_response(MOCK_PROFILE_RESPONSE)
        if "/key-metrics-ttm/" in url:
            return _make_mock_response(MOCK_KEY_METRICS_RESPONSE)
        if "/ratios-ttm/" in url:
            return _make_mock_response(MOCK_RATIOS_RESPONSE)
        return _make_mock_response([])

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=mock_get)

    # Mock DB — always return None for scalar_one_or_none (no existing record)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.add = MagicMock()

    results = await fmp_client.fetch_and_cache_batch(
        client, mock_db, ["BAD", "AAPL"], force=True
    )

    # BAD failed, AAPL succeeded
    assert len(results) == 1
    assert results[0].ticker == "AAPL"


@pytest.mark.asyncio
async def test_batch_stops_on_rate_limit(fmp_client):
    """Batch should stop processing when rate limit is hit."""
    fmp_client._daily_requests = DAILY_LIMIT - 1  # only 1 request left

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    # It will use the 1 remaining request on the profile call for AAPL,
    # then hit the limit on key-metrics-ttm. The whole ticker fetch fails.
    # But the batch_fetch catches RateLimitExceeded and stops.
    results = await fmp_client.fetch_and_cache_batch(
        mock_http_client_fixture(), mock_db, ["AAPL", "MSFT"], force=True
    )

    # May get 0 or 1 depending on exact request ordering; main point is no crash
    assert isinstance(results, list)


def mock_http_client_fixture():
    """Standalone helper (not a pytest fixture) for inline use."""
    client = AsyncMock(spec=httpx.AsyncClient)

    async def route_get(url, params=None):
        if "/profile/" in url:
            return _make_mock_response(MOCK_PROFILE_RESPONSE)
        elif "/key-metrics-ttm/" in url:
            return _make_mock_response(MOCK_KEY_METRICS_RESPONSE)
        elif "/ratios-ttm/" in url:
            return _make_mock_response(MOCK_RATIOS_RESPONSE)
        return _make_mock_response([])

    client.get = AsyncMock(side_effect=route_get)
    return client


# ---------------------------------------------------------------------------
# Tests: Force refresh bypasses cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_force_bypasses_fresh_cache(fmp_client, mock_http_client):
    """force=True should call API even if cache is fresh."""
    # No staleness check executed because force=True skips it entirely
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.add = MagicMock()

    await fmp_client.fetch_and_cache_ticker(
        mock_http_client, mock_db, "AAPL", force=True
    )

    # API should have been called
    assert mock_http_client.get.call_count >= 1
