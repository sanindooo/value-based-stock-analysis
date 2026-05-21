"""Tests for the composite scoring engine.

Pure unit tests — no database or external services needed.
"""

from __future__ import annotations

import pytest

from app.services.scorer import (
    CATEGORY_METRICS,
    DEFAULT_CATEGORY_WEIGHTS,
    PRESERVATION_METRICS,
    compute_composite_score,
    compute_preservation_score,
    normalize_metric,
    score_category,
)


# ---------------------------------------------------------------------------
# normalize_metric
# ---------------------------------------------------------------------------

class TestNormalizeMetric:
    def test_lower_is_better_low_value_scores_high(self):
        # P/E of 5 in range (0, 40) → normalized = 5/40 = 0.125, inverted = 0.875
        result = normalize_metric("pe_ratio", 5)
        assert result == pytest.approx(0.875)

    def test_lower_is_better_high_value_scores_low(self):
        # P/E of 35 → normalized = 35/40 = 0.875, inverted = 0.125
        result = normalize_metric("pe_ratio", 35)
        assert result == pytest.approx(0.125)

    def test_higher_is_better_high_value_scores_high(self):
        # ROE of 30 in range (0, 40) → 30/40 = 0.75
        result = normalize_metric("roe", 30)
        assert result == pytest.approx(0.75)

    def test_higher_is_better_low_value_scores_low(self):
        # ROE of 5 → 5/40 = 0.125
        result = normalize_metric("roe", 5)
        assert result == pytest.approx(0.125)

    def test_value_below_range_clamps_to_min(self):
        # P/E of -5 → clamped to 0, inverted = 1.0
        result = normalize_metric("pe_ratio", -5)
        assert result == pytest.approx(1.0)

    def test_value_above_range_clamps_to_max(self):
        # P/E of 100 → clamped to 40, inverted = 0.0
        result = normalize_metric("pe_ratio", 100)
        assert result == pytest.approx(0.0)

    def test_unknown_metric_returns_half(self):
        result = normalize_metric("unknown_metric", 42)
        assert result == 0.5

    def test_debt_to_equity_lower_is_better(self):
        # D/E of 0.5 in range (0, 3) → 0.5/3 ≈ 0.167, inverted ≈ 0.833
        result = normalize_metric("debt_to_equity", 0.5)
        assert result == pytest.approx(1 - 0.5 / 3)

    def test_current_ratio_higher_is_better(self):
        # current_ratio of 2 in range (0, 4) → 2/4 = 0.5
        result = normalize_metric("current_ratio", 2)
        assert result == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# score_category
# ---------------------------------------------------------------------------

class TestScoreCategory:
    def test_value_category_with_all_metrics(self):
        metrics = {
            "pe_ratio": 10,      # good
            "peg_ratio": 0.8,    # good
            "pb_ratio": 1.5,     # good
            "ps_ratio": 2,       # good
            "price_to_cash": 10, # good
            "price_to_fcf": 8,   # good
        }
        score = score_category(metrics, "value")
        assert score is not None
        assert 0.5 < score <= 1.0  # all good values should score well

    def test_returns_none_when_no_metrics_available(self):
        metrics = {"pe_ratio": None, "peg_ratio": None}
        score = score_category(metrics, "value")
        assert score is None

    def test_skips_none_metrics(self):
        metrics = {"pe_ratio": 10, "peg_ratio": None}
        score = score_category(metrics, "value")
        assert score is not None
        # Should be based only on pe_ratio
        expected = normalize_metric("pe_ratio", 10)
        assert score == pytest.approx(expected)

    def test_unknown_category_returns_none(self):
        score = score_category({"pe_ratio": 10}, "nonexistent")
        assert score is None

    def test_growth_category(self):
        metrics = {
            "eps_growth_this_year": 20,
            "eps_growth_next_year": 15,
        }
        score = score_category(metrics, "growth")
        assert score is not None
        assert 0 < score <= 1.0

    def test_profitability_with_mixed_values(self):
        metrics = {
            "roe": 25,
            "roa": 10,
            "roi": 15,
            "gross_margin": 40,
            "operating_margin": 20,
            "net_profit_margin": 15,
            "dividend_yield": 3,
        }
        score = score_category(metrics, "profitability")
        assert score is not None
        assert 0 < score <= 1.0


# ---------------------------------------------------------------------------
# compute_composite_score
# ---------------------------------------------------------------------------

class TestCompositeScore:
    @pytest.fixture
    def good_stock_metrics(self):
        return {
            # Value (lower is better for ratio metrics)
            "pe_ratio": 8,
            "peg_ratio": 0.7,
            "pb_ratio": 1.2,
            "ps_ratio": 1.5,
            "price_to_cash": 8,
            "price_to_fcf": 10,
            # Growth
            "eps_growth_this_year": 25,
            "eps_growth_next_year": 20,
            "eps_growth_past_5y": 15,
            "eps_growth_next_5y": 18,
            "sales_growth_past_5y": 12,
            # Financial health
            "current_ratio": 2.5,
            "quick_ratio": 1.8,
            "debt_to_equity": 0.3,
            "lt_debt_to_equity": 0.2,
            # Profitability
            "roe": 22,
            "roa": 12,
            "roi": 18,
            "gross_margin": 45,
            "operating_margin": 25,
            "net_profit_margin": 18,
            "dividend_yield": 3,
        }

    def test_returns_score_between_0_and_100(self, good_stock_metrics):
        score = compute_composite_score(good_stock_metrics)
        assert 0 <= score <= 100

    def test_good_stock_scores_high(self, good_stock_metrics):
        score = compute_composite_score(good_stock_metrics)
        assert score > 50  # a "good" stock should beat midpoint

    def test_bad_stock_scores_low(self):
        bad = {
            "pe_ratio": 38,
            "peg_ratio": 2.8,
            "pb_ratio": 9,
            "roe": 2,
            "roa": 1,
            "debt_to_equity": 2.8,
            "current_ratio": 0.5,
        }
        score = compute_composite_score(bad)
        assert score < 40

    def test_empty_metrics_returns_zero(self):
        score = compute_composite_score({})
        assert score == 0.0

    def test_custom_weights_shift_score(self, good_stock_metrics):
        # Heavy value weighting
        value_heavy = {"value": 80, "growth": 5, "financial_health": 5, "profitability": 10}
        score_value = compute_composite_score(good_stock_metrics, category_weights=value_heavy)

        # Heavy growth weighting
        growth_heavy = {"value": 5, "growth": 80, "financial_health": 5, "profitability": 10}
        score_growth = compute_composite_score(good_stock_metrics, category_weights=growth_heavy)

        # Scores should differ because the stock has different strengths per category
        assert score_value != score_growth

    def test_sector_bonus_applied(self, good_stock_metrics):
        base = compute_composite_score(good_stock_metrics)
        with_bonus = compute_composite_score(
            good_stock_metrics,
            preferred_sectors=["Technology"],
            stock_sector="Technology",
        )
        assert with_bonus == min(100.0, base + 10)

    def test_sector_bonus_not_applied_for_wrong_sector(self, good_stock_metrics):
        base = compute_composite_score(good_stock_metrics)
        no_bonus = compute_composite_score(
            good_stock_metrics,
            preferred_sectors=["Healthcare"],
            stock_sector="Technology",
        )
        assert no_bonus == base

    def test_sector_bonus_capped_at_100(self, good_stock_metrics):
        # Even with bonus, score should never exceed 100
        score = compute_composite_score(
            good_stock_metrics,
            preferred_sectors=["Technology"],
            stock_sector="Technology",
        )
        assert score <= 100.0

    def test_none_weights_uses_defaults(self, good_stock_metrics):
        score_none = compute_composite_score(good_stock_metrics, category_weights=None)
        score_default = compute_composite_score(
            good_stock_metrics, category_weights=DEFAULT_CATEGORY_WEIGHTS
        )
        assert score_none == score_default

    def test_partial_metrics_still_scores(self):
        # Only value metrics
        partial = {"pe_ratio": 12, "pb_ratio": 2}
        score = compute_composite_score(partial)
        assert score > 0

    def test_all_category_metrics_are_known(self):
        """Every metric referenced in CATEGORY_METRICS should have a range defined."""
        from app.services.scorer import METRIC_RANGES
        for category, metrics in CATEGORY_METRICS.items():
            for metric in metrics:
                assert metric in METRIC_RANGES, (
                    f"Metric '{metric}' in category '{category}' "
                    f"has no normalization range defined"
                )


# ---------------------------------------------------------------------------
# compute_preservation_score
# ---------------------------------------------------------------------------

class TestPreservationScore:
    def test_all_preservation_metrics_are_known(self):
        from app.services.scorer import METRIC_RANGES
        for category, metrics in PRESERVATION_METRICS.items():
            for metric in metrics:
                assert metric in METRIC_RANGES, (
                    f"Metric '{metric}' in preservation category '{category}' "
                    f"has no normalization range defined"
                )

    def test_returns_score_between_0_and_100(self):
        metrics = {
            "gross_margin": 40,
            "dividend_yield": 3,
            "dividend_payout": 30,
            "beta": 0.8,
            "roe": 20,
            "roa": 10,
        }
        score = compute_preservation_score(metrics)
        assert 0 <= score <= 100

    def test_high_preservation_metrics_score_high(self):
        metrics = {
            "gross_margin": 55,
            "dividend_yield": 5,
            "dividend_payout": 20,
            "beta": 0.3,
            "roe": 30,
            "roa": 15,
        }
        score = compute_preservation_score(metrics)
        assert score > 60

    def test_low_preservation_metrics_score_low(self):
        metrics = {
            "gross_margin": 5,
            "dividend_yield": 0.5,
            "dividend_payout": 75,
            "beta": 1.9,
            "roe": 2,
            "roa": 1,
        }
        score = compute_preservation_score(metrics)
        assert score < 40

    def test_empty_metrics_returns_zero(self):
        score = compute_preservation_score({})
        assert score == 0.0

    def test_missing_one_category_still_scores(self):
        metrics = {
            "gross_margin": 40,
            "roe": 20,
            "roa": 10,
        }
        score = compute_preservation_score(metrics)
        assert score > 0

    def test_missing_all_metrics_returns_zero(self):
        metrics = {"pe_ratio": 10, "peg_ratio": 1.0}
        score = compute_preservation_score(metrics)
        assert score == 0.0

    def test_income_resilience_averages_opposite_polarity(self):
        high_yield_low_payout = {
            "dividend_yield": 6,
            "dividend_payout": 20,
        }
        low_yield_high_payout = {
            "dividend_yield": 1,
            "dividend_payout": 70,
        }
        score_good = compute_preservation_score(high_yield_low_payout)
        score_bad = compute_preservation_score(low_yield_high_payout)
        assert score_good > score_bad
