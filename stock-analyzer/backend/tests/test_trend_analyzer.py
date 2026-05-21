"""Tests for the trend analyzer service.

Unit tests with mocked yfinance — no network calls.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pandas as pd
import pytest

mock_yf = ModuleType("yfinance")
mock_yf.Ticker = MagicMock()
sys.modules.setdefault("yfinance", mock_yf)

from app.services.trend_analyzer import _fetch_trends_sync


def _make_dividends(entries: dict[str, float]) -> pd.Series:
    index = pd.to_datetime(list(entries.keys()))
    return pd.Series(list(entries.values()), index=index)


def _setup_ticker(financials=None, dividends=None):
    ticker = MagicMock()
    if financials is not None:
        ticker.financials = financials
    else:
        ticker.financials = pd.DataFrame()
    if dividends is not None:
        ticker.dividends = dividends
    else:
        ticker.dividends = pd.Series(dtype=float)
    mock_yf.Ticker.return_value = ticker
    return ticker


class TestMarginHistory:
    def test_computes_gross_margin(self):
        cols = [pd.Timestamp(f"{y}-12-31") for y in [2024, 2023, 2022]]
        _setup_ticker(
            financials=pd.DataFrame(
                {cols[0]: [60e9, 100e9], cols[1]: [50e9, 90e9], cols[2]: [40e9, 80e9]},
                index=["Gross Profit", "Total Revenue"],
            )
        )

        result = _fetch_trends_sync("AAPL")

        assert len(result["margin_history"]) == 3
        assert result["margin_history"][0]["gross_margin"] == pytest.approx(60.0)
        assert result["margin_history"][1]["gross_margin"] == pytest.approx(55.56, abs=0.01)
        assert result["years_of_data"] == 3

    def test_handles_missing_gross_profit(self):
        cols = [pd.Timestamp("2024-12-31")]
        _setup_ticker(
            financials=pd.DataFrame({cols[0]: [100e9]}, index=["Total Revenue"])
        )

        result = _fetch_trends_sync("MSFT")

        assert result["margin_history"][0]["gross_margin"] is None

    def test_empty_financials(self):
        _setup_ticker()

        result = _fetch_trends_sync("UNKNOWN")

        assert result["margin_history"] == []
        assert result["data_warnings"] == ["no_financials"]


class TestRevenueConsistency:
    def test_computes_std_dev_of_growth_rates(self):
        cols = [pd.Timestamp(f"{y}-12-31") for y in [2024, 2023, 2022]]
        _setup_ticker(
            financials=pd.DataFrame(
                {cols[0]: [float("nan"), 120e9], cols[1]: [float("nan"), 100e9], cols[2]: [float("nan"), 80e9]},
                index=["Gross Profit", "Total Revenue"],
            )
        )

        result = _fetch_trends_sync("TEST")

        assert result["revenue_consistency"] is not None
        assert result["revenue_consistency"] > 0

    def test_zero_std_dev_for_constant_growth(self):
        cols = [pd.Timestamp(f"{y}-12-31") for y in [2024, 2023, 2022]]
        _setup_ticker(
            financials=pd.DataFrame(
                {cols[0]: [float("nan"), 200e9], cols[1]: [float("nan"), 100e9], cols[2]: [float("nan"), 50e9]},
                index=["Gross Profit", "Total Revenue"],
            )
        )

        result = _fetch_trends_sync("CONST")

        assert result["revenue_consistency"] == pytest.approx(0.0)

    def test_none_with_single_year(self):
        cols = [pd.Timestamp("2024-12-31")]
        _setup_ticker(
            financials=pd.DataFrame({cols[0]: [50e9, 100e9]}, index=["Gross Profit", "Total Revenue"])
        )

        result = _fetch_trends_sync("ONE")

        assert result["revenue_consistency"] is None


class TestDividendGrowthStreak:
    def test_counts_consecutive_growth_years(self):
        _setup_ticker(
            dividends=_make_dividends({
                "2024-03-15": 1.0, "2024-06-15": 1.0,
                "2023-03-15": 0.9, "2023-06-15": 0.9,
                "2022-03-15": 0.8, "2022-06-15": 0.8,
                "2021-03-15": 0.7, "2021-06-15": 0.7,
            })
        )

        result = _fetch_trends_sync("JNJ")

        assert result["dividend_growth_streak"] == 3

    def test_streak_breaks_on_flat_year(self):
        _setup_ticker(
            dividends=_make_dividends({
                "2024-06-15": 2.0,
                "2023-06-15": 2.0,
                "2022-06-15": 1.5,
            })
        )

        result = _fetch_trends_sync("FLAT")

        assert result["dividend_growth_streak"] == 0

    def test_no_dividends(self):
        _setup_ticker()

        result = _fetch_trends_sync("GROWTH")

        assert result["dividend_growth_streak"] == 0


class TestErrorHandling:
    def test_financials_exception_returns_warning(self):
        ticker = MagicMock()
        type(ticker).financials = property(lambda self: (_ for _ in ()).throw(RuntimeError("API down")))
        ticker.dividends = pd.Series(dtype=float)
        mock_yf.Ticker.return_value = ticker

        result = _fetch_trends_sync("ERR")

        assert "financials_error" in result["data_warnings"]
