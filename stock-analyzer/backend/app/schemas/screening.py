"""Pydantic request/response schemas for screening endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ScreeningRunRequest(BaseModel):
    filter_config: dict[str, Any] | None = None
    max_examined: int | None = None
    max_matches: int | None = None


class ScreeningRunResponse(BaseModel):
    task_id: int
    run_id: int


class ScreeningResultOut(BaseModel):
    id: int
    screening_run_id: int
    stock_ticker: str
    composite_score: float
    preservation_score: float | None = None
    metric_snapshot: dict[str, Any]
    conviction_data: dict[str, Any]
    summary: str | None = None
    stage: str

    model_config = {"from_attributes": True}


class ScreeningResultsPage(BaseModel):
    results: list[ScreeningResultOut]
    total: int


class ScreeningRunOut(BaseModel):
    id: int
    created_at: datetime
    status: str
    result_count: int
    filter_config: dict[str, Any] | None = None
    task_id: int | None = None

    model_config = {"from_attributes": True}


class TaskStatusOut(BaseModel):
    id: int
    task_type: str
    status: str
    progress: str | None = None
    progress_data: dict[str, Any] | None = None
    result_id: int | None = None
    error_message: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class StageUpdate(BaseModel):
    stage: str
