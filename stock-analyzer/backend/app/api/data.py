"""Data endpoints — trigger FMP refreshes and query cached stock data."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.stock import Stock
from app.services.fmp_client import FMPClient, RateLimitExceeded

logger = logging.getLogger(__name__)
router = APIRouter()

# Singleton FMP client (in-memory rate counter persists across requests)
_fmp_client = FMPClient()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class RefreshRequest(BaseModel):
    tickers: list[str] | None = None  # None = refresh all cached tickers
    force: bool = False  # bypass staleness check


class StockOut(BaseModel):
    ticker: str
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None
    price: float | None = None

    pe_ratio: float | None = None
    forward_pe: float | None = None
    peg_ratio: float | None = None
    pb_ratio: float | None = None
    ps_ratio: float | None = None
    price_to_cash: float | None = None
    price_to_fcf: float | None = None

    eps_growth_this_year: float | None = None
    eps_growth_next_year: float | None = None
    eps_growth_past_5y: float | None = None
    eps_growth_next_5y: float | None = None
    sales_growth_past_5y: float | None = None

    roe: float | None = None
    roa: float | None = None
    roi: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_profit_margin: float | None = None
    dividend_yield: float | None = None

    current_ratio: float | None = None
    quick_ratio: float | None = None
    debt_to_equity: float | None = None
    lt_debt_to_equity: float | None = None

    last_updated: str | None = None  # ISO 8601

    model_config = {"from_attributes": True}


class RefreshResponse(BaseModel):
    refreshed: int
    tickers: list[str]
    requests_remaining: int


class RateLimitInfo(BaseModel):
    requests_used: int
    requests_remaining: int
    daily_limit: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _stock_to_out(stock: Stock) -> StockOut:
    data = {c.name: getattr(stock, c.name) for c in Stock.__table__.columns}
    if data.get("last_updated"):
        data["last_updated"] = data["last_updated"].isoformat()
    return StockOut(**data)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/refresh", response_model=RefreshResponse)
async def refresh_data(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Trigger a refresh for specific tickers or all cached stocks."""
    tickers = body.tickers
    if tickers is None:
        # Refresh all cached tickers
        result = await db.execute(select(Stock.ticker))
        tickers = list(result.scalars().all())
        if not tickers:
            return RefreshResponse(refreshed=0, tickers=[], requests_remaining=_fmp_client.requests_remaining)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            stocks = await _fmp_client.fetch_and_cache_batch(
                client, db, tickers, force=body.force
            )
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    return RefreshResponse(
        refreshed=len(stocks),
        tickers=[s.ticker for s in stocks],
        requests_remaining=_fmp_client.requests_remaining,
    )


@router.get("/stocks", response_model=list[StockOut])
async def list_stocks(
    sector: str | None = Query(None, description="Filter by sector"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List cached stocks with optional sector filter."""
    stmt = select(Stock)
    if sector:
        stmt = stmt.where(Stock.sector == sector)
    stmt = stmt.order_by(Stock.ticker).offset(offset).limit(limit)

    result = await db.execute(stmt)
    stocks = result.scalars().all()
    return [_stock_to_out(s) for s in stocks]


@router.get("/stocks/{ticker}", response_model=StockOut)
async def get_stock(ticker: str, db: AsyncSession = Depends(get_db)):
    """Get a single cached stock by ticker."""
    result = await db.execute(select(Stock).where(Stock.ticker == ticker.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker.upper()} not found in cache")
    return _stock_to_out(stock)


@router.get("/rate-limit", response_model=RateLimitInfo)
async def rate_limit_info():
    """Check current FMP API rate-limit status."""
    return RateLimitInfo(
        requests_used=_fmp_client.requests_used,
        requests_remaining=_fmp_client.requests_remaining,
        daily_limit=250,
    )
