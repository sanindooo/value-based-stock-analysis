"""Composite scoring engine with 4-category weighted scoring.

Each stock is scored 0-100 based on value, growth, financial health,
and profitability metrics. Category weights come from user preferences.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Category -> metric mappings
# ---------------------------------------------------------------------------
CATEGORY_METRICS: dict[str, list[str]] = {
    "value": [
        "pe_ratio",
        "peg_ratio",
        "pb_ratio",
        "ps_ratio",
        "price_to_cash",
        "price_to_fcf",
    ],
    "growth": [
        "eps_growth_this_year",
        "eps_growth_next_year",
        "eps_growth_past_5y",
        "eps_growth_next_5y",
        "sales_growth_past_5y",
    ],
    "financial_health": [
        "current_ratio",
        "quick_ratio",
        "debt_to_equity",
        "lt_debt_to_equity",
    ],
    "profitability": [
        "roe",
        "roa",
        "roi",
        "gross_margin",
        "operating_margin",
        "net_profit_margin",
        "dividend_yield",
    ],
}

# ---------------------------------------------------------------------------
# Normalization ranges: (min_bad, max_good, higher_is_better)
#
# Each metric maps to the range used to normalize it to 0-1.
# For "lower is better" metrics (like P/E), lower values score higher.
# ---------------------------------------------------------------------------
METRIC_RANGES: dict[str, tuple[float, float, bool]] = {
    # Value — lower is better
    "pe_ratio": (0, 40, False),
    "peg_ratio": (0, 3, False),
    "pb_ratio": (0, 10, False),
    "ps_ratio": (0, 10, False),
    "price_to_cash": (0, 40, False),
    "price_to_fcf": (0, 40, False),
    # Growth — higher is better (percentages as decimals or whole numbers)
    "eps_growth_this_year": (-20, 50, True),
    "eps_growth_next_year": (-20, 50, True),
    "eps_growth_past_5y": (-10, 30, True),
    "eps_growth_next_5y": (-10, 30, True),
    "sales_growth_past_5y": (-10, 30, True),
    # Financial health — mixed
    "current_ratio": (0, 4, True),
    "quick_ratio": (0, 3, True),
    "debt_to_equity": (0, 3, False),
    "lt_debt_to_equity": (0, 2, False),
    # Profitability — higher is better (percentages)
    "roe": (0, 40, True),
    "roa": (0, 20, True),
    "roi": (0, 30, True),
    "gross_margin": (0, 60, True),
    "operating_margin": (0, 40, True),
    "net_profit_margin": (0, 30, True),
    "dividend_yield": (0, 8, True),
}

DEFAULT_CATEGORY_WEIGHTS: dict[str, int] = {
    "value": 25,
    "growth": 25,
    "financial_health": 25,
    "profitability": 25,
}


def normalize_metric(metric: str, value: float) -> float:
    """Normalize a metric value to 0-1 based on its defined range.

    Returns 0.5 if the metric is unknown.
    """
    if metric not in METRIC_RANGES:
        return 0.5

    range_min, range_max, higher_is_better = METRIC_RANGES[metric]
    span = range_max - range_min
    if span == 0:
        return 0.5

    # Clamp to range
    clamped = max(range_min, min(range_max, value))
    normalized = (clamped - range_min) / span

    # For "lower is better" metrics, invert the score
    if not higher_is_better:
        normalized = 1.0 - normalized

    return normalized


def score_category(
    metrics: dict[str, Any],
    category: str,
) -> float | None:
    """Score a single category (0-1) by averaging normalized metric scores.

    Returns None if no metrics are available for the category.
    """
    metric_names = CATEGORY_METRICS.get(category, [])
    scores: list[float] = []

    for metric_name in metric_names:
        value = metrics.get(metric_name)
        if value is None:
            continue
        scores.append(normalize_metric(metric_name, value))

    if not scores:
        return None
    return sum(scores) / len(scores)


def compute_composite_score(
    metrics: dict[str, Any],
    category_weights: dict[str, int] | None = None,
    preferred_sectors: list[str] | None = None,
    stock_sector: str | None = None,
) -> float:
    """Compute the final composite score (0-100) for a stock.

    Steps:
    1. Score each category 0-1
    2. Weighted average across categories (using provided weights)
    3. Scale to 0-100
    4. Add sector preference bonus (+10, capped at 100)
    """
    weights = category_weights or DEFAULT_CATEGORY_WEIGHTS

    weighted_sum = 0.0
    total_weight = 0

    for category, weight in weights.items():
        cat_score = score_category(metrics, category)
        if cat_score is not None:
            weighted_sum += cat_score * weight
            total_weight += weight

    if total_weight == 0:
        base_score = 0.0
    else:
        base_score = (weighted_sum / total_weight) * 100

    # Sector preference bonus
    if (
        preferred_sectors
        and stock_sector
        and stock_sector in preferred_sectors
    ):
        base_score = min(100.0, base_score + 10)

    return round(base_score, 1)
