"""Screening API — trigger screening runs, fetch results, poll task status."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session, get_db
from app.models.preference import PortfolioPreference
from app.models.screening import ScreeningResult, ScreeningRun
from app.models.stock import Stock
from app.models.task import TaskStatus
from app.schemas.screening import (
    ScreeningResultOut,
    ScreeningResultsPage,
    ScreeningRunOut,
    ScreeningRunRequest,
    ScreeningRunResponse,
    StageUpdate,
    TaskStatusOut,
)
from app.services.fmp_client import FMPClient, RateLimitExceeded
from app.services.screener import run_screening
from app.services.ticker_universe import get_screening_universe
from app.services.yahoo_client import fetch_and_cache_yahoo_batch

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_preferences(db: AsyncSession) -> dict[str, Any]:
    """Load the first PortfolioPreference row, or return empty defaults."""
    result = await db.execute(select(PortfolioPreference).limit(1))
    pref = result.scalar_one_or_none()
    if pref is None:
        return {}
    return {
        "preferred_sectors": pref.preferred_sectors or [],
        "category_weights": pref.category_weights,
        "metric_overrides": pref.metric_overrides,
    }


async def _run_screening_task(
    task_id: int,
    filter_config: dict[str, Any] | None,
    max_examined: int | None = None,
    max_matches: int | None = None,
) -> None:
    """Background task wrapper — fetches market data, then screens."""
    failed = False
    try:
        async with async_session() as db:
            task = (await db.execute(select(TaskStatus).where(TaskStatus.id == task_id))).scalar_one_or_none()
            if task:
                task.progress = "fetching_data"
                await db.commit()

            tickers = get_screening_universe()

            async def _on_fetch_progress(progress: Any) -> None:
                async with async_session() as progress_db:
                    result = await progress_db.execute(
                        select(TaskStatus).where(TaskStatus.id == task_id)
                    )
                    t = result.scalar_one_or_none()
                    if t and t.status not in ("completed", "cancelled", "failed"):
                        snap = progress.snapshot()
                        t.progress = "fetching_data"
                        t.progress_data = {
                            "stage": "fetching_data",
                            "total_tickers": snap["total"],
                            "tickers_done": snap["done"],
                            "tickers_cached": snap["cached"],
                            "tickers_fetched": snap["fetched"],
                            "tickers_failed": snap["failed"],
                        }
                        await progress_db.commit()

            await fetch_and_cache_yahoo_batch(db, tickers, on_progress=_on_fetch_progress)

            preferences = await _load_preferences(db)
            await run_screening(
                db,
                filter_config=filter_config,
                preferences=preferences,
                task_id=task_id,
                max_examined=max_examined,
                max_matches=max_matches,
            )
    except Exception:
        logger.exception("Screening task %d failed", task_id)
        failed = True

    if failed:
        try:
            async with async_session() as err_db:
                result = await err_db.execute(
                    select(TaskStatus).where(TaskStatus.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task and task.status not in ("completed", "cancelled"):
                    task.status = "failed"
                    task.error_message = "Screening failed — check server logs."
                    if task.result_id:
                        run_result = await err_db.execute(
                            select(ScreeningRun).where(ScreeningRun.id == task.result_id)
                        )
                        run = run_result.scalar_one_or_none()
                        if run:
                            run.status = "failed"
                    await err_db.commit()
        except Exception:
            logger.exception("Failed to mark task %d as failed", task_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/run", response_model=ScreeningRunResponse)
async def start_screening_run(
    body: ScreeningRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start a new screening run as a background task.

    Returns the task_id (for polling) and the run_id (for fetching results).
    The run_id is set on the task once the background worker creates the ScreeningRun.
    """
    # Concurrent guard — only one screening task at a time
    active = await db.execute(
        select(TaskStatus).where(
            TaskStatus.task_type == "screening",
            TaskStatus.status.in_(["pending", "running"]),
        )
    )
    if active.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="A screen is already running.",
        )

    # Create task row first
    task = TaskStatus(task_type="screening", status="pending", progress="queued")
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Launch background task
    background_tasks.add_task(
        _run_screening_task,
        task_id=task.id,
        filter_config=body.filter_config,
        max_examined=body.max_examined,
        max_matches=body.max_matches,
    )

    # run_id is 0 until the background task creates it — the client should
    # poll GET /api/tasks/{task_id}/status to get the real result_id.
    return ScreeningRunResponse(task_id=task.id, run_id=0)


@router.get("/{run_id}/results", response_model=ScreeningResultsPage)
async def get_screening_results(
    run_id: int,
    sort_by: str = Query("composite_score", pattern="^(composite_score|stock_ticker)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Fetch paginated results for a screening run."""
    # Verify the run exists
    run_result = await db.execute(
        select(ScreeningRun).where(ScreeningRun.id == run_id)
    )
    if run_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Screening run {run_id} not found")

    # Count total
    count_stmt = (
        select(func.count())
        .select_from(ScreeningResult)
        .where(ScreeningResult.screening_run_id == run_id)
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    # Fetch page
    sort_col = getattr(ScreeningResult, sort_by)
    if order == "desc":
        sort_col = sort_col.desc()
    else:
        sort_col = sort_col.asc()

    stmt = (
        select(ScreeningResult)
        .where(ScreeningResult.screening_run_id == run_id)
        .order_by(sort_col)
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()

    return ScreeningResultsPage(
        results=[ScreeningResultOut.model_validate(r) for r in rows],
        total=total,
    )


@router.get("/thresholds")
async def get_thresholds():
    """Serve canonical thresholds and metric direction flags for frontend coloring."""
    from app.services.screener import DEFAULT_THRESHOLDS
    from app.services.scorer import METRIC_RANGES

    directions = {}
    for metric, (range_min, range_max, higher_is_better) in METRIC_RANGES.items():
        directions[metric] = {
            "higher_is_better": higher_is_better,
            "range_min": range_min,
            "range_max": range_max,
        }

    return {"thresholds": DEFAULT_THRESHOLDS, "directions": directions}


@router.get("/highlights", response_model=list[ScreeningResultOut])
async def get_screening_highlights(
    min_score: float = Query(80),
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Get exceptional stocks from the latest completed/partial screening run."""
    # Find latest completed or partial run
    run_result = await db.execute(
        select(ScreeningRun)
        .where(ScreeningRun.status.in_(["completed", "partial"]))
        .order_by(ScreeningRun.created_at.desc())
        .limit(1)
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        return []

    stmt = (
        select(ScreeningResult)
        .where(
            ScreeningResult.screening_run_id == run.id,
            ScreeningResult.composite_score >= min_score,
        )
        .order_by(ScreeningResult.composite_score.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [ScreeningResultOut.model_validate(r) for r in rows]


@router.get("/runs/{run_id}", response_model=ScreeningRunOut)
async def get_screening_run(run_id: int, db: AsyncSession = Depends(get_db)):
    """Get details for a single screening run including filter_config."""
    stmt = (
        select(
            ScreeningRun.id,
            ScreeningRun.created_at,
            ScreeningRun.status,
            ScreeningRun.filter_config,
            ScreeningRun.task_id,
            func.count(ScreeningResult.id).label("result_count"),
        )
        .outerjoin(ScreeningResult, ScreeningResult.screening_run_id == ScreeningRun.id)
        .where(ScreeningRun.id == run_id)
        .group_by(
            ScreeningRun.id,
        )
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Screening run {run_id} not found")
    return ScreeningRunOut(
        id=row.id,
        created_at=row.created_at,
        status=row.status,
        result_count=row.result_count,
        filter_config=row.filter_config,
        task_id=row.task_id,
    )


@router.delete("/runs/{run_id}", status_code=204)
async def delete_screening_run(run_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a screening run and its results. Cannot delete a running run."""
    run_result = await db.execute(
        select(ScreeningRun).where(ScreeningRun.id == run_id)
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Screening run {run_id} not found")

    if run.status == "running":
        raise HTTPException(status_code=409, detail="Cancel the run before deleting.")

    # Delete results first (FK constraint)
    await db.execute(
        select(ScreeningResult)
        .where(ScreeningResult.screening_run_id == run_id)
    )
    from sqlalchemy import delete
    await db.execute(
        delete(ScreeningResult).where(ScreeningResult.screening_run_id == run_id)
    )

    # Delete associated task if exists
    if run.task_id:
        task_result = await db.execute(
            select(TaskStatus).where(TaskStatus.id == run.task_id)
        )
        task = task_result.scalar_one_or_none()
        if task:
            await db.delete(task)

    await db.delete(run)
    await db.commit()


@router.get("/runs", response_model=list[ScreeningRunOut])
async def list_screening_runs(db: AsyncSession = Depends(get_db)):
    """List all past screening runs with result counts."""
    from sqlalchemy import cast, String
    stmt = (
        select(
            ScreeningRun.id,
            ScreeningRun.created_at,
            ScreeningRun.status,
            ScreeningRun.filter_config,
            ScreeningRun.task_id,
            func.count(ScreeningResult.id).label("result_count"),
        )
        .outerjoin(ScreeningResult, ScreeningResult.screening_run_id == ScreeningRun.id)
        .group_by(
            ScreeningRun.id,
        )
        .order_by(ScreeningRun.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()

    return [
        ScreeningRunOut(
            id=row.id,
            created_at=row.created_at,
            status=row.status,
            result_count=row.result_count,
            filter_config=row.filter_config,
            task_id=row.task_id,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Task polling (lives here alongside screening for simplicity)
# ---------------------------------------------------------------------------

@router.get("/tasks/{task_id}/status", response_model=TaskStatusOut)
async def get_task_status(task_id: int, db: AsyncSession = Depends(get_db)):
    """Poll the status of a background task."""
    result = await db.execute(
        select(TaskStatus).where(TaskStatus.id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return TaskStatusOut.model_validate(task)


@router.get("/tasks", response_model=list[TaskStatusOut])
async def list_screening_tasks(
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List screening tasks, optionally filtered by status (comma-separated)."""
    stmt = select(TaskStatus).where(TaskStatus.task_type == "screening")
    if status:
        statuses = [s.strip() for s in status.split(",")]
        stmt = stmt.where(TaskStatus.status.in_(statuses))
    stmt = stmt.order_by(TaskStatus.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [TaskStatusOut.model_validate(t) for t in rows]


@router.post("/tasks/{task_id}/cancel", response_model=TaskStatusOut)
async def cancel_screening_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Request cancellation of a running screening task."""
    result = await db.execute(
        select(TaskStatus).where(TaskStatus.id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # If already completed/failed/cancelled, no-op
    if task.status in ("completed", "failed", "cancelled"):
        return TaskStatusOut.model_validate(task)

    task.status = "cancelling"
    await db.commit()
    await db.refresh(task)
    return TaskStatusOut.model_validate(task)


@router.post("/runs/{run_id}/recompute", status_code=200)
async def recompute_conviction(run_id: int, db: AsyncSession = Depends(get_db)):
    """Recompute conviction_data and summary for all results in a run using current thresholds."""
    from app.services.screener import DEFAULT_THRESHOLDS, _compute_conviction, _generate_summary

    run_result = await db.execute(
        select(ScreeningRun).where(ScreeningRun.id == run_id)
    )
    if run_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Screening run {run_id} not found")

    results = (
        await db.execute(
            select(ScreeningResult).where(ScreeningResult.screening_run_id == run_id)
        )
    ).scalars().all()

    updated = 0
    for r in results:
        metrics = dict(r.metric_snapshot or {})

        # Apply fallback calculations on stored snapshot data
        pe = metrics.get("pe_ratio")
        eps_growth = metrics.get("eps_growth_this_year")
        if metrics.get("peg_ratio") is None and pe and eps_growth and eps_growth > 0:
            metrics["peg_ratio"] = round(pe / eps_growth, 4)
            r.metric_snapshot = metrics

        conviction = _compute_conviction(metrics, DEFAULT_THRESHOLDS)
        summary = _generate_summary(metrics, conviction, r.composite_score, DEFAULT_THRESHOLDS)
        r.conviction_data = conviction
        r.summary = summary
        updated += 1

    await db.commit()
    return {"updated": updated}


VALID_STAGES = {"screened", "researching", "researched", "rejected"}


@router.patch("/{run_id}/results/{result_id}/stage", response_model=ScreeningResultOut)
async def update_result_stage(
    run_id: int,
    result_id: int,
    body: StageUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update the pipeline stage of a screening result."""
    if body.stage not in VALID_STAGES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid stage '{body.stage}'. Must be one of: {', '.join(sorted(VALID_STAGES))}",
        )

    result = await db.execute(
        select(ScreeningResult).where(
            ScreeningResult.id == result_id,
            ScreeningResult.screening_run_id == run_id,
        )
    )
    screening_result = result.scalar_one_or_none()
    if screening_result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Result {result_id} not found in run {run_id}",
        )

    screening_result.stage = body.stage
    await db.commit()
    await db.refresh(screening_result)
    return ScreeningResultOut.model_validate(screening_result)
