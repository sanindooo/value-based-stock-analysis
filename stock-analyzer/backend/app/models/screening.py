from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ScreeningRun(Base):
    __tablename__ = "screening_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    filter_config: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")


class ScreeningResult(Base):
    __tablename__ = "screening_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screening_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("screening_runs.id")
    )
    stock_ticker: Mapped[str] = mapped_column(String(10), ForeignKey("stocks.ticker"))
    composite_score: Mapped[float] = mapped_column(Float, default=0.0)
    metric_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    conviction_data: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[str | None] = mapped_column(String(1000))
    stage: Mapped[str] = mapped_column(String(20), default="screened")
