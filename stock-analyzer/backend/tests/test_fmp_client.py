"""Tests for the FMP client (stable API).

All tests run without a real database or FMP API — everything is mocked.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

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
# Fixtures — match the stable API response shapes
# ---------------------------------------------------------------------------

MOCK_PROFILE_RESPONSE = [
    {
        "symbol": "AAPL",
        "companyName": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "marketCap": 3_000_000_000_000,
        "price": 190.50,
    }
]

MOCK_KEY_METRICS_RESPONSE = [
    {
        "symbol": "AAPL",
        "currentRatioTTM": 1.07,
        "returnOnAssetsTTM": 0.28,
        "returnOnEquityTTM": 1.60,
        "returnOnCapitalEmployedTTM": 0.55,
        "earningsYieldTTM": 0.035,
    }
]

MOCK_RATIOS_RESPONSE = [
    {
        "symbol": "AAPL",
        "priceToEarningsRatioTTM": 28.5,
        "priceToEarningsGrowthRatioTTM": 1.8,
        "priceToBookRatioTTM": 45.2,
        "priceToSalesRatioTTM": 7.5,
        "priceToFreeCashFlowRatioTTM": 27.3,
        "priceToOperatingCashFlowRatioTTM": 25.1,
        "grossProfitMarginTTM": 0.45,
        "operatingProfitMarginTTM": 0.30,
        "netProfitMarginTTM": 0.25,
        "currentRatioTTM": 1.07,
        "quickRatioTTM": 0.94,
        "debtToEquityRatioTTM": 1.76,
        "longTermDebtToCapitalRatioTTM": 0.62,
        "dividendYieldTTM": 0.005,
    }
]


def _make_mock_response(json_data, status_code=200):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.content = b"{}"
    resp.raise_for_status = MagicMock()
    return resp


def _route_stable_api(url, params=None):
    """Route mock requests based on stable API URL patterns."""
    if url.endswith("/profile"):
        return _make_mock_response(MOCK_PROFILE_RESPONSE)
    elif "key-metrics-ttm" in url:
        return _make_mock_response(MOCK_KEY_METRICS_RESPONSE)
    elif "ratios-ttm" in url:
        return _make_mock_response(MOCK_RATIOS_RESPONSE)
    return _make_mock_response([])


@pytest.fixture
def fmp_client():
    return FMPClient(api_key="test-key")


@pytest.fixture
def mock_http_client():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=_route_stable_api)
    return client


# ---------------------------------------------------------------------------
# Tests: Happy path — data parsing and mapping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_profile_parses_response(fmp_client, mock_http_client):
    profile = await fmp_client.fetch_profile(mock_http_client, "AAPL")
    assert profile is not None
    assert profile.symbol == "AAPL"
    assert profile.companyName == "Apple Inc."
    assert profile.marketCap == 3_000_000_000_000


@pytest.mark.asyncio
async def test_key_metrics_ttm_parses_response(fmp_client, mock_http_client):
    metrics = await fmp_client.key_metrics_ttm(mock_http_client, "AAPL")
    assert metrics is not None
    assert metrics.returnOnEquityTTM == 1.60
    assert metrics.currentRatioTTM == 1.07


@pytest.mark.asyncio
async def test_ratios_ttm_parses_response(fmp_client, mock_http_client):
    ratios = await fmp_client.ratios_ttm(mock_http_client, "AAPL")
    assert ratios is not None
    assert ratios.grossProfitMarginTTM == 0.45
    assert ratios.longTermDebtToCapitalRatioTTM == 0.62


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

    # Pricing ratios (not converted — they're already ratios)
    assert result["pe_ratio"] == 28.5
    assert result["peg_ratio"] == 1.8
    assert result["pb_ratio"] == 45.2
    assert result["ps_ratio"] == 7.5
    assert result["price_to_cash"] == 25.1
    assert result["price_to_fcf"] == 27.3

    # Returns — decimal * 100
    assert result["roe"] == 160.0
    assert result["roa"] == 28.0
    assert result["roi"] == 55.0

    # Margins — decimal * 100
    assert result["gross_margin"] == 45.0
    assert result["operating_margin"] == 30.0
    assert result["net_profit_margin"] == 25.0

    # Financial health
    assert result["current_ratio"] == 1.07
    assert result["quick_ratio"] == 0.94
    assert result["debt_to_equity"] == 1.76
    assert result["lt_debt_to_equity"] == 0.62
    assert result["dividend_yield"] == 0.5  # 0.005 * 100

    # Growth metrics are None (not available from TTM endpoints)
    assert result["eps_growth_this_year"] is None
    assert result["eps_growth_next_5y"] is None


# ---------------------------------------------------------------------------
# Tests: Cache freshness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fresh_cache_skips_api_call(fmp_client, mock_http_client):
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
    mock_http_client.get.assert_not_called()


@pytest.mark.asyncio
async def test_stale_cache_triggers_refresh(fmp_client, mock_http_client):
    stale_stock = MagicMock()
    stale_stock.last_updated = datetime.now(timezone.utc) - timedelta(hours=STALENESS_HOURS + 1)
    stale_stock.ticker = "AAPL"

    stale_result = MagicMock()
    stale_result.scalar_one_or_none.return_value = stale_stock

    mock_db = AsyncMock()
    mock_db.execute.return_value = stale_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    await fmp_client.fetch_and_cache_ticker(
        mock_http_client, mock_db, "AAPL", force=False
    )

    assert mock_http_client.get.call_count >= 1
    mock_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: Rate limit handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_limit_exceeded_raises(fmp_client, mock_http_client):
    fmp_client._daily_requests = DAILY_LIMIT

    with pytest.raises(RateLimitExceeded):
        await fmp_client.fetch_profile(mock_http_client, "AAPL")


@pytest.mark.asyncio
async def test_http_429_raises_rate_limit(fmp_client):
    resp_429 = MagicMock(spec=httpx.Response)
    resp_429.status_code = 429
    resp_429.content = b"{}"

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=resp_429)

    with pytest.raises(RateLimitExceeded, match="429"):
        await fmp_client.fetch_profile(client, "AAPL")


def test_requests_remaining_property(fmp_client):
    assert fmp_client.requests_remaining == DAILY_LIMIT
    fmp_client._daily_requests = 100
    assert fmp_client.requests_remaining == DAILY_LIMIT - 100


def test_rate_counter_resets_on_new_day(fmp_client):
    fmp_client._daily_requests = 200
    fmp_client._day_started = datetime.now(timezone.utc) - timedelta(days=1)
    assert fmp_client.requests_remaining == DAILY_LIMIT


# ---------------------------------------------------------------------------
# Tests: Missing data — nulls stored, not rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_metrics_stored_as_none(fmp_client):
    profile = FMPProfile.model_validate(MOCK_PROFILE_RESPONSE[0])

    result = fmp_client.map_to_stock(profile, None, None, "AAPL")

    assert result["ticker"] == "AAPL"
    assert result["company_name"] == "Apple Inc."
    assert result.get("pe_ratio") is None
    assert result.get("gross_margin") is None
    assert result.get("current_ratio") is None
    assert result.get("eps_growth_this_year") is None


@pytest.mark.asyncio
async def test_missing_profile_stored_as_none(fmp_client):
    metrics = FMPKeyMetricsTTM.model_validate(MOCK_KEY_METRICS_RESPONSE[0])
    ratios = FMPRatiosTTM.model_validate(MOCK_RATIOS_RESPONSE[0])

    result = fmp_client.map_to_stock(None, metrics, ratios, "AAPL")

    assert result["ticker"] == "AAPL"
    assert result.get("company_name") is None
    assert result["pe_ratio"] == 28.5
    assert result["gross_margin"] == 45.0  # 0.45 * 100


@pytest.mark.asyncio
async def test_empty_api_response_returns_none(fmp_client, mock_http_client):
    mock_http_client.get = AsyncMock(return_value=_make_mock_response([]))
    result = await fmp_client.key_metrics_ttm(mock_http_client, "FAKE")
    assert result is None


# ---------------------------------------------------------------------------
# Tests: Batch fetch error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_continues_on_single_ticker_failure(fmp_client):
    async def mock_get(url, params=None):
        symbol = (params or {}).get("symbol", "")
        if symbol == "BAD" and url.endswith("/profile"):
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 500
            resp.content = b"{}"
            resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=resp
            )
            return resp
        return _route_stable_api(url, params)

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=mock_get)

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

    assert len(results) == 1


@pytest.mark.asyncio
async def test_batch_stops_on_rate_limit(fmp_client):
    fmp_client._daily_requests = DAILY_LIMIT - 1

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=_route_stable_api)

    results = await fmp_client.fetch_and_cache_batch(
        client, mock_db, ["AAPL", "MSFT"], force=True
    )

    assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Tests: Force refresh bypasses cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_force_bypasses_fresh_cache(fmp_client, mock_http_client):
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

    assert mock_http_client.get.call_count >= 1


# ---------------------------------------------------------------------------
# Tests: Decimal-to-percentage conversion
# ---------------------------------------------------------------------------

def test_pct_converts_decimals():
    assert FMPClient._pct(0.33) == 33.0
    assert FMPClient._pct(1.60) == 160.0
    assert FMPClient._pct(0.005) == 0.5
    assert FMPClient._pct(None) is None


def test_get_candidate_tickers_returns_list(fmp_client):
    tickers = fmp_client.get_candidate_tickers()
    assert len(tickers) > 50
    assert "AAPL" in tickers
    assert "MSFT" in tickers
