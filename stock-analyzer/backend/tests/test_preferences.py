from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.preference import PortfolioPreference
from app.schemas.preferences import DEFAULT_CATEGORY_WEIGHTS, DEFAULT_METRIC_THRESHOLDS


@pytest.fixture
def mock_db():
    session = AsyncMock()
    return session


@pytest.fixture
def mock_pref():
    pref = MagicMock(spec=PortfolioPreference)
    pref.preferred_sectors = ["Technology", "Healthcare"]
    pref.risk_tolerance = "conservative"
    pref.hold_duration = "5y+"
    pref.category_weights = {"value": 40, "growth": 20, "financial_health": 20, "profitability": 20}
    pref.metric_overrides = {"pe_ratio": {"min": None, "max": 15}}
    return pref


@pytest_asyncio.fixture
async def client(mock_db):
    from app.db import get_db

    async def _override():
        yield mock_db

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_preferences_returns_defaults_when_empty(client, mock_db):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result_mock

    resp = await client.get("/api/preferences")
    assert resp.status_code == 200
    data = resp.json()
    assert data["preferred_sectors"] == []
    assert data["risk_tolerance"] == "moderate"
    assert data["hold_duration"] == "3-5y"
    assert data["category_weights"] == DEFAULT_CATEGORY_WEIGHTS
    assert data["metric_overrides"] == {
        k: {ik: iv for ik, iv in v.items()} for k, v in DEFAULT_METRIC_THRESHOLDS.items()
    }


@pytest.mark.asyncio
async def test_get_preferences_returns_saved(client, mock_db, mock_pref):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_pref
    mock_db.execute.return_value = result_mock

    resp = await client.get("/api/preferences")
    assert resp.status_code == 200
    data = resp.json()
    assert data["preferred_sectors"] == ["Technology", "Healthcare"]
    assert data["risk_tolerance"] == "conservative"
    assert data["hold_duration"] == "5y+"
    assert data["category_weights"]["value"] == 40
    # metric_overrides should merge defaults with saved overrides
    assert data["metric_overrides"]["pe_ratio"]["max"] == 15
    assert data["metric_overrides"]["roe"]["min"] == 15  # default preserved


@pytest.mark.asyncio
async def test_put_preferences_creates_new(client, mock_db):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result_mock

    # Intercept add() to set attributes on the new PortfolioPreference object
    # so the response builder can read them after commit+refresh.
    def capture_add(obj):
        obj.preferred_sectors = ["Energy"]
        obj.risk_tolerance = "aggressive"
        obj.hold_duration = "1-3y"
        obj.category_weights = DEFAULT_CATEGORY_WEIGHTS
        obj.metric_overrides = {}

    mock_db.add.side_effect = capture_add
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    resp = await client.put(
        "/api/preferences",
        json={
            "preferred_sectors": ["Energy"],
            "risk_tolerance": "aggressive",
            "hold_duration": "1-3y",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["preferred_sectors"] == ["Energy"]
    assert data["risk_tolerance"] == "aggressive"
    assert data["hold_duration"] == "1-3y"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_put_preferences_updates_existing(client, mock_db, mock_pref):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_pref
    mock_db.execute.return_value = result_mock
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    resp = await client.put(
        "/api/preferences",
        json={"risk_tolerance": "moderate"},
    )
    assert resp.status_code == 200
    # Verify the model attribute was updated
    assert mock_pref.risk_tolerance == "moderate"
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_put_invalid_risk_tolerance(client, mock_db):
    resp = await client.put(
        "/api/preferences",
        json={"risk_tolerance": "yolo"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_invalid_hold_duration(client, mock_db):
    resp = await client.put(
        "/api/preferences",
        json={"hold_duration": "10y"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_invalid_category_weights_keys(client, mock_db):
    resp = await client.put(
        "/api/preferences",
        json={"category_weights": {"value": 100}},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_invalid_category_weights_range(client, mock_db):
    resp = await client.put(
        "/api/preferences",
        json={
            "category_weights": {
                "value": 150,
                "growth": 25,
                "financial_health": 25,
                "profitability": 25,
            }
        },
    )
    assert resp.status_code == 422
