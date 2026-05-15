"""Tests for the screening engine.

Pure unit tests — DB session is mocked, no real database needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.screener import (
    DEFAULT_THRESHOLDS,
    _compute_conviction,
    _extract_metrics,
    _generate_summary,
    _merge_thresholds,
    _passes_thresholds,
    run_screening,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stock(**overrides):
    """Create a mock Stock object with reasonable defaults."""
    defaults = {
        "ticker": "TEST",
        "company_name": "Test Corp",
        "sector": "Technology",
        "industry": "Software",
        "market_cap": 1_000_000_000,
        "price": 50.0,
        "pe_ratio": 12.0,
        "forward_pe": 10.0,
        "peg_ratio": 1.0,
        "pb_ratio": 2.0,
        "ps_ratio": 3.0,
        "price_to_cash": 10.0,
        "price_to_fcf": 12.0,
        "eps_growth_this_year": 15.0,
        "eps_growth_next_year": 12.0,
        "eps_growth_past_5y": 10.0,
        "eps_growth_next_5y": 11.0,
        "sales_growth_past_5y": 8.0,
        "roe": 20.0,
        "roa": 8.0,
        "roi": 15.0,
        "gross_margin": 40.0,
        "operating_margin": 20.0,
        "net_profit_margin": 15.0,
        "dividend_yield": 2.5,
        "current_ratio": 2.0,
        "quick_ratio": 1.5,
        "debt_to_equity": 0.5,
        "lt_debt_to_equity": 0.3,
        "last_updated": None,
    }
    defaults.update(overrides)

    stock = MagicMock()
    for key, value in defaults.items():
        setattr(stock, key, value)

    # Mock __table__.columns for _extract_metrics
    columns = []
    for key in defaults:
        col = MagicMock()
        col.name = key
        columns.append(col)
    stock.__table__ = MagicMock()
    stock.__table__.columns = columns

    return stock


# ---------------------------------------------------------------------------
# _merge_thresholds
# ---------------------------------------------------------------------------

class TestMergeThresholds:
    def test_defaults_returned_when_no_overrides(self):
        result = _merge_thresholds(None, None)
        assert result == {k: dict(v) for k, v in DEFAULT_THRESHOLDS.items()}

    def test_metric_overrides_update_defaults(self):
        overrides = {"pe_ratio": {"max": 15}}
        result = _merge_thresholds(None, overrides)
        assert result["pe_ratio"]["max"] == 15
        # Other defaults preserved
        assert result["roe"]["min"] == 15

    def test_filter_config_overrides_everything(self):
        overrides = {"pe_ratio": {"max": 15}}
        filter_config = {"pe_ratio": {"max": 25}}
        result = _merge_thresholds(filter_config, overrides)
        # filter_config wins over metric_overrides
        assert result["pe_ratio"]["max"] == 25

    def test_new_metric_added_from_overrides(self):
        overrides = {"forward_pe": {"max": 18}}
        result = _merge_thresholds(None, overrides)
        assert "forward_pe" in result
        assert result["forward_pe"]["max"] == 18

    def test_new_metric_added_from_filter_config(self):
        config = {"roi": {"min": 10}}
        result = _merge_thresholds(config, None)
        assert "roi" in result
        assert result["roi"]["min"] == 10


# ---------------------------------------------------------------------------
# _passes_thresholds
# ---------------------------------------------------------------------------

class TestPassesThresholds:
    def test_stock_passes_all_thresholds(self):
        metrics = {
            "pe_ratio": 12,
            "roe": 20,
            "current_ratio": 2.0,
            "debt_to_equity": 0.5,
            "gross_margin": 40,
        }
        thresholds = {
            "pe_ratio": {"min": None, "max": 20},
            "roe": {"min": 15, "max": None},
            "current_ratio": {"min": 1.5, "max": None},
            "debt_to_equity": {"min": None, "max": 1.0},
            "gross_margin": {"min": 30, "max": None},
        }
        assert _passes_thresholds(metrics, thresholds) is True

    def test_stock_fails_max_threshold(self):
        metrics = {"pe_ratio": 25}
        thresholds = {"pe_ratio": {"min": None, "max": 20}}
        assert _passes_thresholds(metrics, thresholds) is False

    def test_stock_fails_min_threshold(self):
        metrics = {"roe": 10}
        thresholds = {"roe": {"min": 15, "max": None}}
        assert _passes_thresholds(metrics, thresholds) is False

    def test_none_metric_skips_filter(self):
        metrics = {"pe_ratio": None, "roe": 20}
        thresholds = {
            "pe_ratio": {"min": None, "max": 20},
            "roe": {"min": 15, "max": None},
        }
        assert _passes_thresholds(metrics, thresholds) is True

    def test_all_none_metrics_pass(self):
        metrics = {"pe_ratio": None, "roe": None}
        thresholds = {
            "pe_ratio": {"min": None, "max": 20},
            "roe": {"min": 15, "max": None},
        }
        assert _passes_thresholds(metrics, thresholds) is True

    def test_exact_threshold_value_passes(self):
        metrics = {"pe_ratio": 20}
        thresholds = {"pe_ratio": {"min": None, "max": 20}}
        assert _passes_thresholds(metrics, thresholds) is True

    def test_both_min_and_max_checked(self):
        thresholds = {"current_ratio": {"min": 1.0, "max": 5.0}}
        assert _passes_thresholds({"current_ratio": 3}, thresholds) is True
        assert _passes_thresholds({"current_ratio": 0.5}, thresholds) is False
        assert _passes_thresholds({"current_ratio": 6}, thresholds) is False


# ---------------------------------------------------------------------------
# _compute_conviction
# ---------------------------------------------------------------------------

class TestComputeConviction:
    def test_max_metric_conviction(self):
        metrics = {"pe_ratio": 10}
        thresholds = {"pe_ratio": {"min": None, "max": 20}}
        result = _compute_conviction(metrics, thresholds)
        # (20 - 10) / 20 * 100 = 50
        assert result["pe_ratio"] == 50.0

    def test_min_metric_conviction(self):
        metrics = {"roe": 22}
        thresholds = {"roe": {"min": 15, "max": None}}
        result = _compute_conviction(metrics, thresholds)
        # (22 - 15) / 15 * 100 ≈ 46.7
        assert result["roe"] == pytest.approx(46.7, abs=0.1)

    def test_none_metric_skipped(self):
        metrics = {"pe_ratio": None}
        thresholds = {"pe_ratio": {"min": None, "max": 20}}
        result = _compute_conviction(metrics, thresholds)
        assert "pe_ratio" not in result

    def test_negative_conviction_when_barely_passing(self):
        # P/E at threshold: (20 - 20) / 20 * 100 = 0
        metrics = {"pe_ratio": 20}
        thresholds = {"pe_ratio": {"min": None, "max": 20}}
        result = _compute_conviction(metrics, thresholds)
        assert result["pe_ratio"] == 0.0


# ---------------------------------------------------------------------------
# _generate_summary
# ---------------------------------------------------------------------------

class TestGenerateSummary:
    def test_generates_summary_with_top_3(self):
        metrics = {"pe_ratio": 8, "roe": 25, "debt_to_equity": 0.3}
        conviction = {"pe_ratio": 60.0, "roe": 66.7, "debt_to_equity": 70.0}
        thresholds = {
            "pe_ratio": {"min": None, "max": 20},
            "roe": {"min": 15, "max": None},
            "debt_to_equity": {"min": None, "max": 1.0},
        }
        summary = _generate_summary(metrics, conviction, 78.0, thresholds)
        assert "78.0/100" in summary
        assert "P/E" in summary or "D/E" in summary or "ROE" in summary

    def test_empty_conviction_returns_fallback(self):
        summary = _generate_summary({}, {}, 50.0, {})
        assert "50.0/100" in summary

    def test_summary_capped_at_1000_chars(self):
        # Even with many metrics, summary shouldn't exceed 1000 chars
        metrics = {f"metric_{i}": float(i) for i in range(20)}
        conviction = {f"metric_{i}": float(i * 10) for i in range(20)}
        thresholds = {f"metric_{i}": {"min": None, "max": float(i + 1)} for i in range(20)}
        summary = _generate_summary(metrics, conviction, 50.0, thresholds)
        assert len(summary) <= 1000


# ---------------------------------------------------------------------------
# _extract_metrics
# ---------------------------------------------------------------------------

class TestExtractMetrics:
    def test_extracts_numeric_fields(self):
        stock = _make_stock(pe_ratio=12.5, roe=20.0)
        metrics = _extract_metrics(stock)
        assert metrics["pe_ratio"] == 12.5
        assert metrics["roe"] == 20.0

    def test_excludes_non_metric_fields(self):
        stock = _make_stock()
        metrics = _extract_metrics(stock)
        assert "ticker" not in metrics
        assert "company_name" not in metrics
        assert "sector" not in metrics
        assert "industry" not in metrics
        assert "last_updated" not in metrics

    def test_includes_market_cap_and_price(self):
        stock = _make_stock(market_cap=1e9, price=100)
        metrics = _extract_metrics(stock)
        assert metrics["market_cap"] == 1e9
        assert metrics["price"] == 100


# ---------------------------------------------------------------------------
# run_screening (integration-style with mocked DB)
# ---------------------------------------------------------------------------

class TestRunScreening:
    @pytest.fixture
    def good_stock(self):
        return _make_stock(
            ticker="GOOD",
            pe_ratio=10,
            peg_ratio=0.8,
            pb_ratio=1.5,
            ps_ratio=2,
            price_to_fcf=12,
            roe=22,
            roa=10,
            current_ratio=2.5,
            debt_to_equity=0.4,
            gross_margin=45,
            net_profit_margin=18,
            dividend_yield=3,
        )

    @pytest.fixture
    def bad_stock(self):
        return _make_stock(
            ticker="BAD",
            pe_ratio=35,      # fails max 20
            peg_ratio=3.0,    # fails max 1.5
            pb_ratio=8,       # fails max 3
            roe=5,            # fails min 15
            current_ratio=0.8, # fails min 1.5
            debt_to_equity=2.5, # fails max 1.0
        )

    @pytest.fixture
    def mock_db(self, good_stock, bad_stock):
        db = AsyncMock()

        # select(Stock) returns both stocks
        stock_result = MagicMock()
        stock_result.scalars.return_value.all.return_value = [good_stock, bad_stock]

        # select(TaskStatus) returns a mock task
        task = MagicMock()
        task.status = "pending"
        task.progress = None
        task.result_id = None
        task.completed_at = None
        task_result = MagicMock()
        task_result.scalar_one_or_none.return_value = task

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            # The first execute is for Stock query
            # Subsequent ones are for TaskStatus lookups
            stmt_str = str(stmt)
            if "stocks" in stmt_str.lower():
                return stock_result
            return task_result

        db.execute = AsyncMock(side_effect=mock_execute)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        return db

    @pytest.mark.asyncio
    async def test_good_stock_passes_bad_stock_rejected(self, mock_db, good_stock, bad_stock):
        run_id = await run_screening(mock_db)

        # Check that db.add was called:
        # 1x for ScreeningRun + 1x for good stock result = 2 adds
        add_calls = mock_db.add.call_args_list
        # First call is the ScreeningRun
        screening_run = add_calls[0][0][0]
        assert screening_run.status == "completed"

        # Second call is a ScreeningResult for the good stock
        assert len(add_calls) == 2
        result = add_calls[1][0][0]
        assert result.stock_ticker == "GOOD"
        assert result.composite_score > 0
        assert result.stage == "screened"
        assert result.summary is not None

    @pytest.mark.asyncio
    async def test_custom_filter_config_applied(self, mock_db, good_stock):
        # Tighten PE threshold so good stock still passes
        config = {"pe_ratio": {"max": 15}}
        run_id = await run_screening(mock_db, filter_config=config)

        add_calls = mock_db.add.call_args_list
        # ScreeningRun + 1 result (good stock with PE=10 still passes max=15)
        assert len(add_calls) == 2

    @pytest.mark.asyncio
    async def test_very_tight_filters_reject_all(self, mock_db):
        config = {"pe_ratio": {"max": 1}}  # impossible threshold
        run_id = await run_screening(mock_db, filter_config=config)

        add_calls = mock_db.add.call_args_list
        # Only ScreeningRun, no results
        assert len(add_calls) == 1

    @pytest.mark.asyncio
    async def test_preferences_sector_bonus(self, mock_db, good_stock):
        prefs = {
            "preferred_sectors": ["Technology"],
            "category_weights": {"value": 25, "growth": 25, "financial_health": 25, "profitability": 25},
        }
        run_id = await run_screening(mock_db, preferences=prefs)

        add_calls = mock_db.add.call_args_list
        # The good stock is in "Technology" sector, should get +10 bonus
        result = add_calls[1][0][0]
        assert result.stock_ticker == "GOOD"

        # Compute without bonus for comparison
        prefs_no_bonus = {
            "preferred_sectors": [],
            "category_weights": {"value": 25, "growth": 25, "financial_health": 25, "profitability": 25},
        }
        mock_db.add.reset_mock()

        # Reset execute side effect for second run
        stock_result = MagicMock()
        stock_result.scalars.return_value.all.return_value = [good_stock]
        mock_db.execute = AsyncMock(return_value=stock_result)

        run_id2 = await run_screening(mock_db, preferences=prefs_no_bonus)
        add_calls2 = mock_db.add.call_args_list
        result_no_bonus = add_calls2[1][0][0]

        assert result.composite_score >= result_no_bonus.composite_score

    @pytest.mark.asyncio
    async def test_task_progress_updated(self, mock_db):
        run_id = await run_screening(mock_db, task_id=1)

        # Task should have been updated multiple times via execute
        assert mock_db.execute.call_count >= 1
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_screening_run_committed(self, mock_db):
        await run_screening(mock_db)
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_conviction_data_populated(self, mock_db, good_stock):
        await run_screening(mock_db)

        add_calls = mock_db.add.call_args_list
        result = add_calls[1][0][0]
        assert isinstance(result.conviction_data, dict)
        assert len(result.conviction_data) > 0

    @pytest.mark.asyncio
    async def test_metric_snapshot_populated(self, mock_db, good_stock):
        await run_screening(mock_db)

        add_calls = mock_db.add.call_args_list
        result = add_calls[1][0][0]
        assert isinstance(result.metric_snapshot, dict)
        assert "pe_ratio" in result.metric_snapshot

    @pytest.mark.asyncio
    async def test_null_metrics_dont_reject_stock(self, mock_db):
        """A stock with null metrics should not be rejected by those filters."""
        null_stock = _make_stock(
            ticker="NULL",
            pe_ratio=None,   # null → skip this filter
            peg_ratio=None,
            pb_ratio=None,
            ps_ratio=None,
            price_to_fcf=None,
            roe=20,          # passes min 15
            roa=8,           # passes min 5
            current_ratio=2, # passes min 1.5
            debt_to_equity=0.5, # passes max 1.0
            gross_margin=40, # passes min 30
            net_profit_margin=15, # passes min 10
            dividend_yield=2, # passes min 1
        )

        stock_result = MagicMock()
        stock_result.scalars.return_value.all.return_value = [null_stock]
        mock_db.execute = AsyncMock(return_value=stock_result)
        mock_db.add.reset_mock()

        await run_screening(mock_db)

        add_calls = mock_db.add.call_args_list
        # ScreeningRun + 1 result
        assert len(add_calls) == 2
        assert add_calls[1][0][0].stock_ticker == "NULL"
