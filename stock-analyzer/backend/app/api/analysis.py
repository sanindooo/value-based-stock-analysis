"""Analysis API — trigger standard/deep analysis, fetch results."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session, get_db
from app.models.analysis import StockAnalysis
from app.models.research import ResearchReport
from app.models.task import TaskStatus
from app.schemas.analysis import AnalysisRunRequest, StockAnalysisOut, TickerAnalysesResponse
from app.schemas.research import ResearchReportOut
from app.schemas.screening import TaskStatusOut

logger = logging.getLogger(__name__)
router = APIRouter()


async def _run_standard_analysis_task(task_id: int, ticker: str, mode: str) -> None:
    from app.services.trend_analyzer import fetch_trends
    from app.services.news_client import fetch_news

    async with async_session() as db:
        try:
            result = await db.execute(select(TaskStatus).where(TaskStatus.id == task_id))
            task = result.scalar_one_or_none()
            if task:
                task.status = "running"
                task.progress = "fetching_trends"
                await db.commit()

            trend_data = await fetch_trends(ticker)

            result = await db.execute(select(TaskStatus).where(TaskStatus.id == task_id))
            task = result.scalar_one_or_none()
            if task:
                task.progress = "fetching_news"
                await db.commit()

            news_articles = await fetch_news(ticker)

            result = await db.execute(select(TaskStatus).where(TaskStatus.id == task_id))
            task = result.scalar_one_or_none()
            if task:
                task.progress = "storing"
                await db.commit()

            headlines = [
                {
                    "headline": a.headline,
                    "source": a.source,
                    "url": a.url,
                    "published_at": a.published_at,
                    "summary": a.summary[:200] if a.summary else "",
                }
                for a in news_articles
            ]

            analysis_data: dict[str, Any] = {
                **trend_data,
                "news_headlines": headlines,
            }

            if mode == "preservation":
                margin_history = trend_data.get("margin_history", [])
                margins = [e["gross_margin"] for e in margin_history if e.get("gross_margin") is not None]
                if len(margins) >= 2:
                    analysis_data["margin_trend"] = "expanding" if margins[0] > margins[-1] else "contracting"
                    analysis_data["pricing_power_signal"] = "strong" if margins[0] >= 30 and margins[0] > margins[-1] else "weak"
                streak = trend_data.get("dividend_growth_streak", 0)
                analysis_data["dividend_reliability"] = "high" if streak >= 5 else "moderate" if streak >= 2 else "low"
                volatility = trend_data.get("revenue_consistency")
                if volatility is not None:
                    analysis_data["business_resilience"] = "high" if volatility < 10 else "moderate" if volatility < 25 else "low"

            analysis = StockAnalysis(
                stock_ticker=ticker,
                tier="standard",
                mode=mode,
                analysis_data=analysis_data,
            )
            db.add(analysis)
            await db.commit()
            await db.refresh(analysis)

            result = await db.execute(select(TaskStatus).where(TaskStatus.id == task_id))
            task = result.scalar_one_or_none()
            if task:
                task.status = "completed"
                task.progress = "complete"
                task.result_id = analysis.id
                task.completed_at = datetime.now(timezone.utc)
                await db.commit()

        except Exception as exc:
            logger.exception("Standard analysis task %d failed for %s: %s", task_id, ticker, exc)
            async with async_session() as err_db:
                result = await err_db.execute(select(TaskStatus).where(TaskStatus.id == task_id))
                task = result.scalar_one_or_none()
                if task and task.status not in ("completed", "cancelled"):
                    task.status = "failed"
                    task.error_message = "Analysis failed — check server logs."
                    await err_db.commit()


@router.post("/standard/{ticker}", response_model=TaskStatusOut)
async def start_standard_analysis(
    ticker: str,
    body: AnalysisRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    ticker = ticker.upper().strip()

    active = await db.execute(
        select(TaskStatus).where(
            TaskStatus.task_type == "standard_analysis",
            TaskStatus.status.in_(["pending", "running"]),
            TaskStatus.description == ticker,
        )
    )
    if active.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"Analysis already running for {ticker}")

    task = TaskStatus(
        task_type="standard_analysis",
        status="pending",
        progress="queued",
        description=ticker,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(
        _run_standard_analysis_task,
        task_id=task.id,
        ticker=ticker,
        mode=body.mode,
    )

    return TaskStatusOut.model_validate(task)


@router.get("/{ticker}", response_model=TickerAnalysesResponse)
async def get_analyses_for_ticker(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    ticker = ticker.upper().strip()

    standard_results = await db.execute(
        select(StockAnalysis)
        .where(StockAnalysis.stock_ticker == ticker)
        .order_by(StockAnalysis.created_at.desc())
        .limit(20)
    )
    standard_analyses = [
        StockAnalysisOut.model_validate(r) for r in standard_results.scalars().all()
    ]

    deep_results = await db.execute(
        select(ResearchReport)
        .where(ResearchReport.stock_ticker == ticker)
        .order_by(ResearchReport.created_at.desc())
        .limit(20)
    )
    deep_analyses = [
        ResearchReportOut.model_validate(r) for r in deep_results.scalars().all()
    ]

    return {
        "ticker": ticker,
        "standard": standard_analyses,
        "deep": deep_analyses,
    }
