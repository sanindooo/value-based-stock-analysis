"""Research API — trigger research runs, fetch reports, poll task status."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session, get_db
from app.models.research import ResearchReport
from app.models.task import TaskStatus
from app.schemas.research import (
    ResearchReportOut,
    ResearchReportSummary,
    ResearchRunRequest,
    ResearchRunResponse,
    ResearchTaskInfo,
    ResearchTaskStatusOut,
)
from app.services.research_agent import run_research_for_ticker

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Background task wrapper
# ---------------------------------------------------------------------------

async def _run_research_task(task_id: int, ticker: str) -> None:
    """Background task wrapper — opens its own DB session."""
    async with async_session() as db:
        try:
            await run_research_for_ticker(db, ticker, task_id)
        except Exception:
            logger.exception("Research task %d failed for %s", task_id, ticker)
            # Task is already marked failed inside run_research_for_ticker,
            # but handle the edge case where the error happens before that.
            result = await db.execute(
                select(TaskStatus).where(TaskStatus.id == task_id)
            )
            task = result.scalar_one_or_none()
            if task and task.status != "failed":
                task.status = "failed"
                task.error_message = "Research failed — check server logs."
                await db.commit()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/run", response_model=ResearchRunResponse)
async def start_research_run(
    body: ResearchRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start research tasks for one or more stock tickers.

    Each ticker gets its own background task and task_id for polling.
    """
    tasks_info: list[ResearchTaskInfo] = []

    for ticker in body.stock_tickers:
        ticker_upper = ticker.upper().strip()
        task = TaskStatus(
            task_type="research",
            status="pending",
            progress="queued",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        background_tasks.add_task(_run_research_task, task_id=task.id, ticker=ticker_upper)
        tasks_info.append(ResearchTaskInfo(ticker=ticker_upper, task_id=task.id))

    return ResearchRunResponse(tasks=tasks_info)


@router.get("/reports", response_model=list[ResearchReportSummary])
async def list_reports(db: AsyncSession = Depends(get_db)):
    """List all research reports with summary info."""
    stmt = (
        select(ResearchReport)
        .order_by(ResearchReport.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()

    summaries: list[ResearchReportSummary] = []
    for r in rows:
        verdict = None
        confidence = None
        if isinstance(r.report_content, dict):
            opinion = r.report_content.get("investment_opinion", {})
            if isinstance(opinion, dict):
                verdict = opinion.get("verdict")
                confidence = opinion.get("confidence")
        summaries.append(
            ResearchReportSummary(
                id=r.id,
                stock_ticker=r.stock_ticker,
                created_at=r.created_at,
                verdict=verdict,
                confidence=confidence,
            )
        )
    return summaries


@router.get("/status/{task_id}", response_model=ResearchTaskStatusOut)
async def get_research_task_status(
    task_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Poll the status of a research background task."""
    result = await db.execute(
        select(TaskStatus).where(TaskStatus.id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return ResearchTaskStatusOut.model_validate(task)


@router.get("/{report_id}", response_model=ResearchReportOut)
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a full research report by ID."""
    result = await db.execute(
        select(ResearchReport).where(ResearchReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return ResearchReportOut.model_validate(report)
