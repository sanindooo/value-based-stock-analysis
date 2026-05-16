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
    # Value metrics (lower is better) — Graham Ch.14 adjusted for modern markets
    "pe_ratio": {"min": None, "max": 20},
    "peg_ratio": {"min": None, "max": 1.0},
    "pb_ratio": {"min": None, "max": 1.5},
    "ps_ratio": {"min": None, "max": 3},
    "price_to_fcf": {"min": None, "max": 15},
    # Profitability (higher is better)
    "roe": {"min": 12, "max": None},
    "roa": {"min": 4, "max": None},
    "gross_margin": {"min": 25, "max": None},
    "net_profit_margin": {"min": 8, "max": None},
    # Financial health — Graham Ch.14
    "current_ratio": {"min": 1.5, "max": None},
    "debt_to_equity": {"min": None, "max": 0.5},
    "debt_to_ebitda": {"min": None, "max": 3.0},
    # Growth — Graham/Buffett minimum
    "projected_earnings_growth": {"min": 5, "max": None},
    # Stability — Graham margin of safety
    "beta": {"min": None, "max": 1.0},
    "book_value_per_share": {"min": 0, "max": None},
    # Income
    "dividend_yield": {"min": None, "max": None},
    "dividend_payout": {"min": None, "max": 75},
    # Informational (no threshold)
    "analyst_rating": {"min": None, "max": None},
    "trading_range_12m": {"min": None, "max": None},
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
        if col.name not in ("ticker", "company_name", "sector", "industry", "last_updated", "data_warnings", "website")
    }


_CORE_METRICS = {"pe_ratio", "roe", "debt_to_equity", "gross_margin", "current_ratio"}
_MIN_CORE_REQUIRED = 3


def _has_core_metrics(metrics: dict[str, Any]) -> bool:
    """Check if a stock has enough core metrics to be scored meaningfully."""
    core_present = sum(1 for m in _CORE_METRICS if metrics.get(m) is not None)
    return core_present >= _MIN_CORE_REQUIRED


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
        "beta": "Beta",
        "book_value_per_share": "Book Value/Share",
        "analyst_rating": "Analyst Rating",
        "trading_range_12m": "12M Trading Range",
        "roe": "ROE",
        "roa": "ROA",
        "roi": "ROI",
        "current_ratio": "Current Ratio",
        "quick_ratio": "Quick Ratio",
        "debt_to_equity": "D/E",
        "lt_debt_to_equity": "LT D/E",
        "debt_to_ebitda": "Debt/EBITDA",
        "gross_margin": "Gross Margin",
        "operating_margin": "Op. Margin",
        "net_profit_margin": "Net Margin",
        "dividend_yield": "Div. Yield",
        "dividend_payout": "Payout Ratio",
        "projected_earnings_growth": "Proj. Earnings Growth",
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


async def _check_cancelled(db: AsyncSession, task_id: int) -> bool:
    """Check if the task has been requested to cancel (bypasses identity map)."""
    result = await db.execute(
        select(TaskStatus.status).where(TaskStatus.id == task_id)
    )
    row = result.scalar_one_or_none()
    return row == "cancelling"


async def run_screening(
    db: AsyncSession,
    filter_config: dict[str, Any] | None = None,
    preferences: dict[str, Any] | None = None,
    task_id: int | None = None,
    max_examined: int | None = None,
    max_matches: int | None = None,
) -> int:
    """Run the full screening pipeline. Returns the screening_run ID.

    Scores ALL stocks with sufficient data, ranks by composite score,
    and returns the top max_matches results. Thresholds feed into conviction
    data but do not hard-filter stocks out of results.
    """
    prefs = preferences or {}
    category_weights = prefs.get("category_weights")
    preferred_sectors = prefs.get("preferred_sectors", [])
    metric_overrides = prefs.get("metric_overrides")

    thresholds = _merge_thresholds(filter_config, metric_overrides)

    # --- Create ScreeningRun ---
    config_to_store = dict(filter_config or {})
    if max_examined is not None:
        config_to_store["max_examined"] = max_examined
    if max_matches is not None:
        config_to_store["max_matches"] = max_matches

    run = ScreeningRun(
        filter_config=config_to_store,
        status="running",
        task_id=task_id,
    )
    db.add(run)
    await db.commit()
    run_id = run.id

    # --- Update task if provided ---
    if task_id is not None:
        await _update_task(db, task_id, status="running", progress="filtering", result_id=run_id)

    # --- Query all stocks ---
    result = await db.execute(select(Stock))
    stocks = list(result.scalars().all())
    total_stocks = len(stocks)

    if task_id is not None:
        await _update_task(
            db, task_id, progress="screening",
            progress_data={
                "stage": "screening",
                "stocks_examined": 0,
                "matches_found": 0,
                "total_stocks": total_stocks,
                "log_entries": [],
            },
        )

    # --- Score all stocks, rank, and collect top N ---
    examined_count = 0
    cancelled = False
    log_entries: list[dict[str, str]] = []
    batch_size = 10

    # Phase 1: Score all eligible stocks
    scored: list[tuple[Stock, dict[str, Any], float, dict[str, float]]] = []

    for stock in stocks:
        if task_id and examined_count > 0 and examined_count % batch_size == 0:
            if await _check_cancelled(db, task_id):
                cancelled = True
                break

        if max_examined and examined_count >= max_examined:
            break

        examined_count += 1
        metrics = _extract_metrics(stock)

        # Skip stocks without enough core data
        if not _has_core_metrics(metrics):
            continue

        conviction = _compute_conviction(metrics, thresholds)
        composite = compute_composite_score(
            metrics,
            category_weights=category_weights,
            preferred_sectors=preferred_sectors,
            stock_sector=stock.sector,
        )
        scored.append((stock, metrics, composite, conviction))

        if task_id and examined_count % batch_size == 0:
            await _update_task(
                db, task_id, progress="screening",
                progress_data={
                    "stage": "screening",
                    "stocks_examined": examined_count,
                    "matches_found": len(scored),
                    "total_stocks": total_stocks,
                    "log_entries": [],
                },
            )

    # Phase 2: Rank by composite score and take top N
    scored.sort(key=lambda x: x[2], reverse=True)
    limit = max_matches if max_matches else len(scored)
    top_results = scored[:limit]

    # Load prior stages from previous runs so we preserve research/rejection status
    prior_stages: dict[str, str] = {}
    prior_result = await db.execute(
        select(ScreeningResult.stock_ticker, ScreeningResult.stage)
        .where(ScreeningResult.stage.in_(["researched", "researching", "rejected"]))
        .order_by(ScreeningResult.id.desc())
    )
    for ticker, stage in prior_result.all():
        if ticker not in prior_stages:
            prior_stages[ticker] = stage

    # Phase 3: Write results
    results_count = 0
    for stock, metrics, composite, conviction in top_results:
        summary = _generate_summary(metrics, conviction, composite, thresholds)

        snapshot = dict(metrics)
        snapshot["company_name"] = stock.company_name
        snapshot["sector"] = stock.sector
        snapshot["website"] = stock.website
        if stock.data_warnings:
            snapshot["data_warnings"] = stock.data_warnings

        stage = prior_stages.get(stock.ticker, "screened")

        screening_result = ScreeningResult(
            screening_run_id=run_id,
            stock_ticker=stock.ticker,
            composite_score=composite,
            metric_snapshot=snapshot,
            conviction_data=conviction,
            summary=summary,
            stage=stage,
        )
        db.add(screening_result)
        results_count += 1
        log_entries.append({"message": f"Match: {stock.ticker} (score: {composite})"})

        if results_count % batch_size == 0:
            await db.commit()

    # --- Finalize ---
    if cancelled:
        run.status = "partial"
        if task_id:
            await _update_task(
                db, task_id, status="cancelled", progress="cancelled",
                progress_data={
                    "stage": "cancelled",
                    "stocks_examined": examined_count,
                    "matches_found": results_count,
                    "total_stocks": total_stocks,
                    "log_entries": log_entries[-10:],
                },
            )
    else:
        run.status = "completed"
        if task_id:
            await _update_task(
                db, task_id, status="completed", progress="done",
                progress_data={
                    "stage": "done",
                    "stocks_examined": examined_count,
                    "matches_found": results_count,
                    "total_stocks": total_stocks,
                    "log_entries": log_entries[-10:],
                },
            )

    await db.commit()

    logger.info(
        "Screening run %d %s: %d/%d stocks collected (%d examined, %d scored)",
        run_id,
        run.status,
        results_count,
        total_stocks,
        examined_count,
        len(scored),
    )
    return run_id


async def _update_task(
    db: AsyncSession,
    task_id: int,
    status: str | None = None,
    progress: str | None = None,
    progress_data: dict[str, Any] | None = None,
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
    if progress_data is not None:
        task.progress_data = progress_data
    if result_id is not None:
        task.result_id = result_id
    if status in ("completed", "cancelled"):
        task.completed_at = datetime.now(timezone.utc)
