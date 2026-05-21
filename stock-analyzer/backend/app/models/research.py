from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_ticker: Mapped[str] = mapped_column(String(10))
    report_content: Mapped[dict] = mapped_column(JSON, default=dict)
    sources: Mapped[dict] = mapped_column(JSON, default=dict)
    mode: Mapped[str] = mapped_column(String(20), server_default="value", default="value")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
