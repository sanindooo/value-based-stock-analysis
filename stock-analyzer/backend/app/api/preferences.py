from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.preference import PortfolioPreference
from app.schemas.preferences import (
    DEFAULT_CATEGORY_WEIGHTS,
    DEFAULT_METRIC_THRESHOLDS,
    PreferencesResponse,
    PreferencesUpdate,
)

router = APIRouter()


def _to_response(pref: PortfolioPreference) -> PreferencesResponse:
    """Convert a DB model to the API response, filling metric defaults."""
    overrides = dict(DEFAULT_METRIC_THRESHOLDS)
    if pref.metric_overrides:
        overrides.update(pref.metric_overrides)
    return PreferencesResponse(
        preferred_sectors=pref.preferred_sectors or [],
        risk_tolerance=pref.risk_tolerance or "moderate",
        hold_duration=pref.hold_duration or "3-5y",
        category_weights=pref.category_weights or DEFAULT_CATEGORY_WEIGHTS,
        metric_overrides=overrides,
    )


def _default_response() -> PreferencesResponse:
    """Return defaults when no preferences row exists yet."""
    return PreferencesResponse(
        preferred_sectors=[],
        risk_tolerance="moderate",
        hold_duration="3-5y",
        category_weights=DEFAULT_CATEGORY_WEIGHTS,
        metric_overrides=DEFAULT_METRIC_THRESHOLDS,
    )


@router.get("", response_model=PreferencesResponse)
async def get_preferences(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PortfolioPreference).limit(1))
    pref = result.scalar_one_or_none()
    if pref is None:
        return _default_response()
    return _to_response(pref)


@router.put("", response_model=PreferencesResponse)
async def update_preferences(
    body: PreferencesUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PortfolioPreference).limit(1))
    pref = result.scalar_one_or_none()

    if pref is None:
        pref = PortfolioPreference()
        db.add(pref)

    update_data = body.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(pref, field, value)

    await db.commit()
    await db.refresh(pref)
    return _to_response(pref)
