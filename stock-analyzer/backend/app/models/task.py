from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TaskStatus(Base):
    __tablename__ = "task_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    result_id: Mapped[int | None] = mapped_column(Integer)
    progress: Mapped[str | None] = mapped_column(String(50))
    progress_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(String(200))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
