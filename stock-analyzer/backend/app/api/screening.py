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
    """Background task wrapper — fetches FMP data if cache is empty, then screens."""
    async with async_session() as db:
        try:
            # Check if we have cached stock data
            count = (await db.execute(select(func.count()).select_from(Stock))).scalar() or 0
            if count == 0:
                # Populate cache from FMP screener
                task = (await db.execute(select(TaskStatus).where(TaskStatus.id == task_id))).scalar_one_or_none()
                if task:
                    task.progress = "fetching_data"
                    await db.commit()

                fmp = FMPClient()
                tickers = fmp.get_candidate_tickers()[:80]
                async with httpx.AsyncClient(timeout=30.0) as client:
                    await fmp.fetch_and_cache_batch(client, db, tickers)

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
            # Mark task as failed
            result = await db.execute(
                select(TaskStatus).where(TaskStatus.id == task_id)
            )
            task = result.scalar_one_or_none()
            if task:
                task.status = "failed"
                task.error_message = "Screening failed — check server logs."
            # Also mark the run if it exists
            if task and task.result_id:
                run_result = await db.execute(
                    select(ScreeningRun).where(ScreeningRun.id == task.result_id)
                )
                run = run_result.scalar_one_or_none()
                if run:
                    run.status = "failed"
            await db.commit()


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


@router.get("/runs", response_model=list[ScreeningRunOut])
async def list_screening_runs(db: AsyncSession = Depends(get_db)):
    """List all past screening runs with result counts."""
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
            ScreeningRun.created_at,
            ScreeningRun.status,
            ScreeningRun.filter_config,
            ScreeningRun.task_id,
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
