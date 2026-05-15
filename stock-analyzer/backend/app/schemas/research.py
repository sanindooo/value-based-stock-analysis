"""Pydantic request/response schemas for research endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ResearchRunRequest(BaseModel):
    stock_tickers: list[str] = Field(..., min_length=1, max_length=20)


class ResearchTaskInfo(BaseModel):
    ticker: str
    task_id: int


class ResearchRunResponse(BaseModel):
    tasks: list[ResearchTaskInfo]


class ResearchReportOut(BaseModel):
    id: int
    stock_ticker: str
    report_content: dict[str, Any]
    sources: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class ResearchReportSummary(BaseModel):
    id: int
    stock_ticker: str
    created_at: datetime
    verdict: str | None = None
    confidence: str | None = None

    model_config = {"from_attributes": True}


class ResearchTaskStatusOut(BaseModel):
    id: int
    task_type: str
    status: str
    progress: str | None = None
    result_id: int | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}
