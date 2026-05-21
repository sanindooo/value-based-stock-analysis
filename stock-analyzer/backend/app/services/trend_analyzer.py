"""Trend analyzer — computes margin history, dividend growth streak,
and revenue consistency from yfinance historical data.
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


def _fetch_trends_sync(ticker: str) -> dict[str, Any]:
    import yfinance as yf

    t = yf.Ticker(ticker)
    warnings: list[str] = []

    margin_history: list[dict[str, Any]] = []
    revenue_consistency: float | None = None
    dividend_growth_streak: int = 0
    years_of_data: int = 0

    try:
        financials = t.financials
        if financials is not None and not financials.empty:
            years_of_data = len(financials.columns)
            revenue_values: list[float] = []

            for col in financials.columns:
                year = str(col.year) if hasattr(col, "year") else str(col)
                gross_profit = None
                total_revenue = None

                if "Gross Profit" in financials.index:
                    val = financials.loc["Gross Profit", col]
                    if val is not None and not (isinstance(val, float) and math.isnan(val)):
                        gross_profit = float(val)

                if "Total Revenue" in financials.index:
                    val = financials.loc["Total Revenue", col]
                    if val is not None and not (isinstance(val, float) and math.isnan(val)):
                        total_revenue = float(val)

                margin = None
                if gross_profit is not None and total_revenue and total_revenue > 0:
                    margin = round(gross_profit / total_revenue * 100, 2)

                margin_history.append({"year": year, "gross_margin": margin, "revenue": total_revenue})

                if total_revenue is not None:
                    revenue_values.append(total_revenue)

            if len(revenue_values) >= 2:
                growth_rates = []
                for i in range(len(revenue_values) - 1):
                    if revenue_values[i + 1] and revenue_values[i + 1] > 0:
                        rate = (revenue_values[i] - revenue_values[i + 1]) / revenue_values[i + 1]
                        growth_rates.append(rate)
                if growth_rates:
                    mean_growth = sum(growth_rates) / len(growth_rates)
                    variance = sum((r - mean_growth) ** 2 for r in growth_rates) / len(growth_rates)
                    revenue_consistency = round(math.sqrt(variance) * 100, 2)
        else:
            warnings.append("no_financials")
    except Exception as exc:
        logger.warning("Failed to fetch financials for %s: %s", ticker, exc)
        warnings.append("financials_error")

    try:
        dividends = t.dividends
        if dividends is not None and not dividends.empty:
            annual_dividends: dict[int, float] = {}
            for date, amount in dividends.items():
                yr = date.year if hasattr(date, "year") else int(str(date)[:4])
                annual_dividends[yr] = annual_dividends.get(yr, 0) + float(amount)

            years = sorted(annual_dividends.keys(), reverse=True)
            streak = 0
            for i in range(len(years) - 1):
                if years[i] - years[i + 1] == 1 and annual_dividends[years[i]] > annual_dividends[years[i + 1]]:
                    streak += 1
                else:
                    break
            dividend_growth_streak = streak
    except Exception as exc:
        logger.warning("Failed to fetch dividends for %s: %s", ticker, exc)
        warnings.append("dividends_error")

    return {
        "margin_history": margin_history,
        "dividend_growth_streak": dividend_growth_streak,
        "revenue_consistency": revenue_consistency,
        "years_of_data": years_of_data,
        "data_warnings": warnings if warnings else None,
    }


async def fetch_trends(ticker: str) -> dict[str, Any]:
    return await asyncio.to_thread(_fetch_trends_sync, ticker)
