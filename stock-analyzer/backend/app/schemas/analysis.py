"""Pydantic request/response schemas for analysis endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class StockAnalysisOut(BaseModel):
    id: int
    stock_ticker: str
    screening_run_id: int | None = None
    tier: str
    mode: str
    analysis_data: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisRunRequest(BaseModel):
    mode: str = "value"
