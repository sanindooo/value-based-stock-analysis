from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Stock(Base):
    __tablename__ = "stocks"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    company_name: Mapped[str | None] = mapped_column(String(255))
    sector: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(255))
    market_cap: Mapped[float | None] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float)

    # Value metrics
    pe_ratio: Mapped[float | None] = mapped_column(Float)
    forward_pe: Mapped[float | None] = mapped_column(Float)
    peg_ratio: Mapped[float | None] = mapped_column(Float)
    pb_ratio: Mapped[float | None] = mapped_column(Float)
    ps_ratio: Mapped[float | None] = mapped_column(Float)
    price_to_cash: Mapped[float | None] = mapped_column(Float)
    price_to_fcf: Mapped[float | None] = mapped_column(Float)

    # Growth metrics
    eps_growth_this_year: Mapped[float | None] = mapped_column(Float)
    eps_growth_next_year: Mapped[float | None] = mapped_column(Float)
    eps_growth_past_5y: Mapped[float | None] = mapped_column(Float)
    eps_growth_next_5y: Mapped[float | None] = mapped_column(Float)
    sales_growth_past_5y: Mapped[float | None] = mapped_column(Float)

    # Profitability metrics
    roe: Mapped[float | None] = mapped_column(Float)
    roa: Mapped[float | None] = mapped_column(Float)
    roi: Mapped[float | None] = mapped_column(Float)
    gross_margin: Mapped[float | None] = mapped_column(Float)
    operating_margin: Mapped[float | None] = mapped_column(Float)
    net_profit_margin: Mapped[float | None] = mapped_column(Float)
    dividend_yield: Mapped[float | None] = mapped_column(Float)

    # Financial health metrics
    current_ratio: Mapped[float | None] = mapped_column(Float)
    quick_ratio: Mapped[float | None] = mapped_column(Float)
    debt_to_equity: Mapped[float | None] = mapped_column(Float)
    lt_debt_to_equity: Mapped[float | None] = mapped_column(Float)

    data_warnings: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
