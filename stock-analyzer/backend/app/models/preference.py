from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PortfolioPreference(Base):
    __tablename__ = "portfolio_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    preferred_sectors: Mapped[list] = mapped_column(JSON, default=list)
    risk_tolerance: Mapped[str] = mapped_column(String(20), default="moderate")
    hold_duration: Mapped[str] = mapped_column(String(20), default="3-5y")
    category_weights: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: {
            "value": 25,
            "growth": 25,
            "financial_health": 25,
            "profitability": 25,
        },
    )
    metric_overrides: Mapped[dict] = mapped_column(JSON, default=dict)
