"""Screening engine — filters cached stocks by metric thresholds, scores them,
and generates rule-based valuation summaries.

This is the core of the screening pipeline. It reads Stock rows from the DB,
applies configurable filters, computes conviction data and composite scores,
then writes ScreeningResult rows.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.screening import ScreeningResult, ScreeningRun
from app.models.stock import Stock
from app.models.task import TaskStatus
from app.services.scorer import CATEGORY_METRICS, compute_composite_score

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default Buffett-style thresholds
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLDS: dict[str, dict[str, float | None]] = {
    "pe_ratio": {"min": None, "max": 20},
    "peg_ratio": {"min": None, "max": 1.5},
    "pb_ratio": {"min": None, "max": 3},
    "ps_ratio": {"min": None, "max": 5},
    "price_to_fcf": {"min": None, "max": 20},
    "roe": {"min": 15, "max": None},
    "roa": {"min": 5, "max": None},
    "current_ratio": {"min": 1.5, "max": None},
    "debt_to_equity": {"min": None, "max": 1.0},
    "gross_margin": {"min": 30, "max": None},
    "net_profit_margin": {"min": 10, "max": None},
    "dividend_yield": {"min": 1, "max": None},
}

# Metrics where we store the "all metrics" list from the Stock model
ALL_METRIC_FIELDS: list[str] = sorted(
    {m for metrics in CATEGORY_METRICS.values() for m in metrics}
)


def _merge_thresholds(
    filter_config: dict[str, Any] | None,
    metric_overrides: dict[str, Any] | None,
) -> dict[str, dict[str, float | None]]:
    """Merge default thresholds with preference overrides, then filter_config overrides."""
    merged = {k: dict(v) for k, v in DEFAULT_THRESHOLDS.items()}

    if metric_overrides:
        for metric, bounds in metric_overrides.items():
            if metric in merged:
                merged[metric].update(bounds)
            else:
                merged[metric] = dict(bounds)

    if filter_config:
        for metric, bounds in filter_config.items():
            if isinstance(bounds, dict):
                if metric in merged:
                    merged[metric].update(bounds)
                else:
                    merged[metric] = dict(bounds)

    return merged


def _extract_metrics(stock: Stock) -> dict[str, Any]:
    """Extract all metric values from a Stock model instance into a flat dict."""
    return {
        col.name: getattr(stock, col.name)
        for col in Stock.__table__.columns
        if col.name not in ("ticker", "company_name", "sector", "industry", "last_updated")
    }


def _passes_thresholds(
    metrics: dict[str, Any],
    thresholds: dict[str, dict[str, float | None]],
) -> bool:
    """Check if a stock's metrics pass ALL threshold criteria.

    If a metric value is None, that filter is skipped (not rejected).
    """
    for metric, bounds in thresholds.items():
        value = metrics.get(metric)
        if value is None:
            continue

        min_val = bounds.get("min")
        max_val = bounds.get("max")

        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False

    return True


def _compute_conviction(
    metrics: dict[str, Any],
    thresholds: dict[str, dict[str, float | None]],
) -> dict[str, float]:
    """Compute conviction strength per metric.

    For "max" metrics (lower is better):
        conviction = (threshold - value) / threshold * 100
    For "min" metrics (higher is better):
        conviction = (value - threshold) / threshold * 100

    Returns a dict of metric -> conviction percentage.
    """
    conviction: dict[str, float] = {}

    for metric, bounds in thresholds.items():
        value = metrics.get(metric)
        if value is None:
            continue

        max_val = bounds.get("max")
        min_val = bounds.get("min")

        if max_val is not None and max_val != 0:
            conviction[metric] = round((max_val - value) / max_val * 100, 1)
        elif min_val is not None and min_val != 0:
            conviction[metric] = round((value - min_val) / min_val * 100, 1)

    return conviction


def _generate_summary(
    metrics: dict[str, Any],
    conviction: dict[str, float],
    composite_score: float,
    thresholds: dict[str, dict[str, float | None]],
) -> str:
    """Generate a rule-based valuation summary highlighting top 3 conviction metrics."""
    # Sort by absolute conviction strength, pick top 3
    ranked = sorted(conviction.items(), key=lambda kv: abs(kv[1]), reverse=True)
    top_3 = ranked[:3]

    if not top_3:
        return f"Limited data available. Composite score: {composite_score}/100."

    parts: list[str] = []
    for metric, strength in top_3:
        value = metrics.get(metric)
        if value is None:
            continue

        bounds = thresholds.get(metric, {})
        max_val = bounds.get("max")
        min_val = bounds.get("min")

        label = _metric_label(metric)

        if max_val is not None:
            parts.append(f"Low {label} of {_fmt(metric, value)} vs threshold of {_fmt(metric, max_val)}")
        elif min_val is not None:
            pct = abs(round(strength))
            parts.append(f"Strong {label} at {_fmt(metric, value)} ({pct}% above threshold)")

    if not parts:
        return f"Composite score: {composite_score}/100."

    summary = ", ".join(parts) + f". Value score: {composite_score}/100."
    # Cap at 1000 chars (DB column limit)
    return summary[:1000]


def _metric_label(metric: str) -> str:
    """Human-readable label for a metric."""
    labels = {
        "pe_ratio": "P/E",
        "peg_ratio": "PEG",
        "pb_ratio": "P/B",
        "ps_ratio": "P/S",
        "price_to_cash": "P/Cash",
        "price_to_fcf": "P/FCF",
        "roe": "ROE",
        "roa": "ROA",
        "roi": "ROI",
        "current_ratio": "Current Ratio",
        "quick_ratio": "Quick Ratio",
        "debt_to_equity": "D/E",
        "lt_debt_to_equity": "LT D/E",
        "gross_margin": "Gross Margin",
        "operating_margin": "Op. Margin",
        "net_profit_margin": "Net Margin",
        "dividend_yield": "Div. Yield",
        "eps_growth_this_year": "EPS Growth (This Year)",
        "eps_growth_next_year": "EPS Growth (Next Year)",
        "eps_growth_past_5y": "EPS Growth (5Y)",
        "eps_growth_next_5y": "EPS Growth (Next 5Y)",
        "sales_growth_past_5y": "Sales Growth (5Y)",
    }
    return labels.get(metric, metric.replace("_", " ").title())


def _fmt(metric: str, value: float) -> str:
    """Format a metric value for display."""
    pct_metrics = {
        "roe", "roa", "roi", "gross_margin", "operating_margin",
        "net_profit_margin", "dividend_yield",
    }
    if metric in pct_metrics:
        return f"{value:.1f}%"
    return f"{value:.1f}"


async def run_screening(
    db: AsyncSession,
    filter_config: dict[str, Any] | None = None,
    preferences: dict[str, Any] | None = None,
    task_id: int | None = None,
) -> int:
    """Run the full screening pipeline. Returns the screening_run ID.

    Steps:
    1. Create a ScreeningRun row
    2. Query all cached stocks
    3. Apply metric thresholds
    4. For each passing stock: compute conviction, score, summary
    5. Store ScreeningResult rows
    6. Update ScreeningRun status and TaskStatus progress
    """
    prefs = preferences or {}
    category_weights = prefs.get("category_weights")
    preferred_sectors = prefs.get("preferred_sectors", [])
    metric_overrides = prefs.get("metric_overrides")

    thresholds = _merge_thresholds(filter_config, metric_overrides)

    # --- Create ScreeningRun ---
    run = ScreeningRun(
        filter_config=filter_config or {},
        status="running",
    )
    db.add(run)
    await db.flush()  # get run.id
    run_id = run.id

    # --- Update task if provided ---
    if task_id is not None:
        await _update_task(db, task_id, status="running", progress="filtering", result_id=run_id)

    # --- Query all stocks ---
    result = await db.execute(select(Stock))
    stocks = list(result.scalars().all())

    if task_id is not None:
        await _update_task(db, task_id, progress="filtering")

    # --- Filter + score ---
    results_count = 0
    for stock in stocks:
        metrics = _extract_metrics(stock)
        if not _passes_thresholds(metrics, thresholds):
            continue

        conviction = _compute_conviction(metrics, thresholds)
        composite = compute_composite_score(
            metrics,
            category_weights=category_weights,
            preferred_sectors=preferred_sectors,
            stock_sector=stock.sector,
        )
        summary = _generate_summary(metrics, conviction, composite, thresholds)

        screening_result = ScreeningResult(
            screening_run_id=run_id,
            stock_ticker=stock.ticker,
            composite_score=composite,
            metric_snapshot=metrics,
            conviction_data=conviction,
            summary=summary,
            stage="screened",
        )
        db.add(screening_result)
        results_count += 1

    if task_id is not None:
        await _update_task(db, task_id, progress="scoring")

    # --- Finalize ---
    run.status = "completed"

    if task_id is not None:
        await _update_task(db, task_id, status="completed", progress="done")

    await db.commit()

    logger.info(
        "Screening run %d completed: %d/%d stocks passed",
        run_id,
        results_count,
        len(stocks),
    )
    return run_id


async def _update_task(
    db: AsyncSession,
    task_id: int,
    status: str | None = None,
    progress: str | None = None,
    result_id: int | None = None,
) -> None:
    """Update a TaskStatus row in-place."""
    from datetime import datetime, timezone

    result = await db.execute(
        select(TaskStatus).where(TaskStatus.id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        return

    if status is not None:
        task.status = status
    if progress is not None:
        task.progress = progress
    if result_id is not None:
        task.result_id = result_id
    if status == "completed":
        task.completed_at = datetime.now(timezone.utc)
