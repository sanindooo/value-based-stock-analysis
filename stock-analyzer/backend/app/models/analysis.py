from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StockAnalysis(Base):
    __tablename__ = "stock_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_ticker: Mapped[str] = mapped_column(String(10), ForeignKey("stocks.ticker"))
    screening_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("screening_runs.id"), nullable=True
    )
    tier: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(20), server_default="value", default="value")
    analysis_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
