"""Tests for First Light sustainability estimator.

Proves the 3-layer financial model correctly determines when Genesis
becomes self-sustaining: revenue >= 1.5x costs AND reserve >= 3-month target.
"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from genesis.countdown.first_light import FirstLightEstimate, FirstLightEstimator


@pytest.fixture
def estimator() -> FirstLightEstimator:
    return FirstLightEstimator(
        sustainability_ratio=1.5,
        reserve_months_required=3,
        ema_alpha=0.3,
        network_beta=0.15,
        confidence_sigma=1.0,
        min_data_points=3,
        min_rate_floor=0.01,
    )


NOW = datetime(2026, 2, 16, 12, 0, 0, tzinfo=timezone.utc)


def _make_timestamps(count: int, interval_days: float = 1.0) -> list:
    """Create evenly-spaced registration timestamps."""
    base = NOW - timedelta(days=count * interval_days)
    return [base + timedelta(days=i * interval_days) for i in range(count)]


class TestInsufficientData:
    """Edge cases: no data, too few humans, no mission activity."""

    def test_no_data(self, estimator: FirstLightEstimator) -> None:
        result = estimator.estimate([], now=NOW)
        assert not result.achieved
        assert not result.sufficient_data
        assert result.current_humans == 0
        assert result.estimated_first_light is None
        assert "Not enough activity" in result.message

    def test_one_human(self, estimator: FirstLightEstimator) -> None:
        result = estimator.estimate([NOW], now=NOW)
        assert not result.achieved
        assert not result.sufficient_data
        assert result.current_humans == 1
        assert "1 verified humans" in result.message

    def test_below_min_data_points(self, estimator: FirstLightEstimator) -> None:
        ts = _make_timestamps(2)
        result = estimator.estimate(ts, now=NOW)
        assert not result.achieved
        assert not result.sufficient_data
        assert result.current_humans == 2

    def test_enough_humans_but_no_missions(self, estimator: FirstLightEstimator) -> None:
        ts = _make_timestamps(10)
        result = estimator.estimate(
            ts,
            monthly_costs=Decimal("500"),
            now=NOW,
        )
        assert not result.achieved
        assert not result.sufficient_data
        assert "Mission activity building" in result.message
        assert "Not enough data to project revenue" in result.message


class TestAchievement:
    """First Light achievement conditions."""

    def test_both_thresholds_met(self, estimator: FirstLightEstimator) -> None:
        """Revenue >= 1.5x costs AND reserve >= 3-month target → achieved."""
        ts = _make_timestamps(50)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("750"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("1500"),
            now=NOW,
        )
        assert result.achieved
        assert result.progress_pct == 100.0
        assert "achieved" in result.message.lower()

    def test_revenue_met_reserve_not(self, estimator: FirstLightEstimator) -> None:
        """Revenue >= 1.5x but reserve < 3-month → NOT achieved."""
        ts = _make_timestamps(50)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("800"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("100"),
            missions_per_human_per_month=2.0,
            avg_mission_value=Decimal("100"),
            now=NOW,
        )
        assert not result.achieved
        assert "Revenue target met" in result.message
        assert "reserve" in result.message.lower()

    def test_reserve_met_revenue_not(self, estimator: FirstLightEstimator) -> None:
        """Reserve >= 3-month but revenue < 1.5x → NOT achieved."""
        ts = _make_timestamps(10)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("200"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("1500"),
            missions_per_human_per_month=2.0,
            avg_mission_value=Decimal("100"),
            now=NOW,
        )
        assert not result.achieved
        assert result.current_sustainability_ratio < 1.5

    def test_exact_thresholds(self, estimator: FirstLightEstimator) -> None:
        """Exactly 1.5x revenue and exactly 3-month reserve → achieved."""
        ts = _make_timestamps(20)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("750"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("1500"),
            now=NOW,
        )
        assert result.achieved

    def test_zero_costs_not_achieved(self, estimator: FirstLightEstimator) -> None:
        """Zero operating costs → can't determine sustainability."""
        ts = _make_timestamps(20)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("1000"),
            monthly_costs=Decimal("0"),
            reserve_balance=Decimal("5000"),
            now=NOW,
        )
        assert not result.achieved


class TestProjections:
    """Financial projection accuracy."""

    def test_linear_signups_produce_sane_estimate(self, estimator: FirstLightEstimator) -> None:
        """Evenly-spaced signups → date estimate exists and is in the future."""
        ts = _make_timestamps(10, interval_days=7.0)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("50"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("0"),
            missions_per_human_per_month=2.0,
            avg_mission_value=Decimal("100"),
            commission_rate=Decimal("0.05"),
            now=NOW,
        )
        assert result.sufficient_data
        assert not result.achieved
        assert result.estimated_first_light is not None
        assert result.estimated_first_light > NOW

    def test_accelerating_signups_give_earlier_estimate(
        self, estimator: FirstLightEstimator,
    ) -> None:
        """Accelerating signup intervals → earlier estimated date."""
        # Slow signups: 10 days apart
        slow_ts = _make_timestamps(10, interval_days=10.0)
        slow = estimator.estimate(
            slow_ts,
            monthly_revenue=Decimal("50"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("0"),
            missions_per_human_per_month=2.0,
            avg_mission_value=Decimal("100"),
            commission_rate=Decimal("0.05"),
            now=NOW,
        )

        # Fast signups: 1 day apart
        fast_ts = _make_timestamps(10, interval_days=1.0)
        fast = estimator.estimate(
            fast_ts,
            monthly_revenue=Decimal("50"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("0"),
            missions_per_human_per_month=2.0,
            avg_mission_value=Decimal("100"),
            commission_rate=Decimal("0.05"),
            now=NOW,
        )

        assert slow.estimated_first_light is not None
        assert fast.estimated_first_light is not None
        assert fast.estimated_first_light < slow.estimated_first_light

    def test_network_effect_increases_rate(self, estimator: FirstLightEstimator) -> None:
        """More existing signups → higher adjusted rate → earlier date."""
        # Few signups
        few_ts = _make_timestamps(5, interval_days=3.0)
        few = estimator.estimate(
            few_ts,
            monthly_revenue=Decimal("10"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("0"),
            missions_per_human_per_month=2.0,
            avg_mission_value=Decimal("100"),
            commission_rate=Decimal("0.05"),
            now=NOW,
        )

        # Many signups (same interval → same raw rate, but more network effect)
        many_ts = _make_timestamps(50, interval_days=3.0)
        many = estimator.estimate(
            many_ts,
            monthly_revenue=Decimal("10"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("0"),
            missions_per_human_per_month=2.0,
            avg_mission_value=Decimal("100"),
            commission_rate=Decimal("0.05"),
            now=NOW,
        )

        # More signups needed for 'few' but also slower rate. The key test
        # is that both produce estimates and 'many' is earlier because
        # it has more humans already AND a higher adjusted rate.
        assert few.estimated_first_light is not None
        assert many.estimated_first_light is not None
        assert many.estimated_first_light <= few.estimated_first_light

    def test_uncertainty_band_contains_estimate(
        self, estimator: FirstLightEstimator,
    ) -> None:
        """optimistic <= estimated <= pessimistic."""
        ts = _make_timestamps(15, interval_days=2.0)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("100"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("0"),
            missions_per_human_per_month=2.0,
            avg_mission_value=Decimal("100"),
            commission_rate=Decimal("0.05"),
            now=NOW,
        )
        if result.optimistic_date and result.pessimistic_date and result.estimated_first_light:
            assert result.optimistic_date <= result.estimated_first_light
            assert result.estimated_first_light <= result.pessimistic_date

    def test_already_enough_humans_for_revenue(
        self, estimator: FirstLightEstimator,
    ) -> None:
        """When current humans already generate enough revenue, sustainability_date = now."""
        ts = _make_timestamps(100, interval_days=1.0)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("200"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("0"),
            # 100 humans * 2 missions * $100 * 5% = $1000/month >> $750 target
            missions_per_human_per_month=2.0,
            avg_mission_value=Decimal("100"),
            commission_rate=Decimal("0.05"),
            now=NOW,
        )
        assert result.projected_sustainability_date is not None
        assert result.projected_sustainability_date == NOW


class TestFalseNowRegression:
    """Regression: First Light must never be 'now' when reserve is unmet."""

    def test_first_light_not_now_when_reserve_unmet(
        self, estimator: FirstLightEstimator,
    ) -> None:
        """Even with enough humans for revenue, unmet reserve blocks first_light = now."""
        ts = _make_timestamps(100, interval_days=1.0)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("200"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("0"),  # Reserve unmet
            missions_per_human_per_month=2.0,
            avg_mission_value=Decimal("100"),
            commission_rate=Decimal("0.05"),
            now=NOW,
        )
        # First Light must be in the future or None — never now with unmet reserve
        if result.estimated_first_light is not None:
            assert result.estimated_first_light > NOW

    def test_first_light_achievable_when_reserve_met(
        self, estimator: FirstLightEstimator,
    ) -> None:
        """With reserve fully met and sufficient revenue, First Light can be now."""
        ts = _make_timestamps(100, interval_days=1.0)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("2000"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("5000"),  # Well above 3-month target
            missions_per_human_per_month=2.0,
            avg_mission_value=Decimal("100"),
            commission_rate=Decimal("0.05"),
            now=NOW,
        )
        assert result.achieved is True

    def test_optimistic_date_not_before_reserve_date(
        self, estimator: FirstLightEstimator,
    ) -> None:
        """When reserve is binding, optimistic_date >= projected_reserve_date."""
        ts = _make_timestamps(100, interval_days=1.0)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("200"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("0"),  # Reserve unmet
            missions_per_human_per_month=2.0,
            avg_mission_value=Decimal("100"),
            commission_rate=Decimal("0.05"),
            now=NOW,
        )
        # If both dates exist, optimistic cannot be earlier than reserve
        if result.optimistic_date is not None and result.projected_reserve_date is not None:
            assert result.optimistic_date >= result.projected_reserve_date


class TestEdgeCases:
    """Numeric edge cases and robustness."""

    def test_same_second_burst_no_crash(self, estimator: FirstLightEstimator) -> None:
        """All registrations at the same instant → no division by zero."""
        ts = [NOW] * 5
        result = estimator.estimate(
            ts,
            monthly_costs=Decimal("500"),
            missions_per_human_per_month=1.0,
            avg_mission_value=Decimal("50"),
            now=NOW,
        )
        assert not result.achieved
        # Should not crash — uses fallback rate (1/0.001)

    def test_deterministic_with_fixed_now(self, estimator: FirstLightEstimator) -> None:
        """Same inputs + same now → identical output."""
        ts = _make_timestamps(10, interval_days=3.0)
        kwargs = dict(
            monthly_revenue=Decimal("50"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("100"),
            missions_per_human_per_month=2.0,
            avg_mission_value=Decimal("100"),
            commission_rate=Decimal("0.05"),
            now=NOW,
        )
        r1 = estimator.estimate(ts, **kwargs)
        r2 = estimator.estimate(ts, **kwargs)
        assert r1 == r2

    def test_very_high_costs_long_projection(self, estimator: FirstLightEstimator) -> None:
        """Very high costs relative to revenue → distant but finite date."""
        ts = _make_timestamps(10, interval_days=2.0)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("1"),
            monthly_costs=Decimal("10000"),
            reserve_balance=Decimal("0"),
            missions_per_human_per_month=0.5,
            avg_mission_value=Decimal("10"),
            commission_rate=Decimal("0.05"),
            now=NOW,
        )
        assert result.estimated_first_light is not None
        assert result.estimated_first_light > NOW

    def test_tiny_commission_rate(self, estimator: FirstLightEstimator) -> None:
        """Very small commission rate → needs more humans, still produces estimate."""
        ts = _make_timestamps(10, interval_days=2.0)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("5"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("0"),
            missions_per_human_per_month=2.0,
            avg_mission_value=Decimal("100"),
            commission_rate=Decimal("0.001"),
            now=NOW,
        )
        assert result.estimated_first_light is not None


class TestProgress:
    """Progress percentage computation."""

    def test_zero_progress(self, estimator: FirstLightEstimator) -> None:
        """No revenue, no reserve → 0% progress."""
        result = estimator.estimate(
            [],
            monthly_costs=Decimal("500"),
            now=NOW,
        )
        assert result.progress_pct == 0.0

    def test_partial_revenue_progress(self, estimator: FirstLightEstimator) -> None:
        """Revenue at 50% of target → ~23.3% total (70% weight × 33.3%)."""
        ts = _make_timestamps(5)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("375"),  # 0.75x costs, which is 50% of 1.5x
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("0"),
            now=NOW,
        )
        # Revenue: 0.75 / 1.5 = 50% → 0.7 * 50 = 35
        # Reserve: 0 / 1500 = 0% → 0.3 * 0 = 0
        # Total: 35.0
        assert abs(result.progress_pct - 35.0) < 1.0

    def test_full_revenue_half_reserve(self, estimator: FirstLightEstimator) -> None:
        """Revenue at 100%, reserve at 50% → 85% progress."""
        ts = _make_timestamps(5)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("750"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("750"),  # 50% of 1500 target
            now=NOW,
        )
        # Revenue: 1.5/1.5 = 100% → 0.7 * 100 = 70
        # Reserve: 750/1500 = 50% → 0.3 * 50 = 15
        # Total: 85.0
        assert abs(result.progress_pct - 85.0) < 1.0

    def test_achieved_is_100_percent(self, estimator: FirstLightEstimator) -> None:
        ts = _make_timestamps(20)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("800"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("1500"),
            now=NOW,
        )
        assert result.achieved
        assert result.progress_pct == 100.0


class TestMessages:
    """Display message content."""

    def test_achieved_message(self, estimator: FirstLightEstimator) -> None:
        ts = _make_timestamps(20)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("800"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("1500"),
            now=NOW,
        )
        assert "First Light has been achieved" in result.message

    def test_revenue_met_building_reserve_message(
        self, estimator: FirstLightEstimator,
    ) -> None:
        ts = _make_timestamps(50)
        result = estimator.estimate(
            ts,
            monthly_revenue=Decimal("800"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("500"),
            missions_per_human_per_month=2.0,
            avg_mission_value=Decimal("100"),
            now=NOW,
        )
        assert "Revenue target met" in result.message
        assert "reserve" in result.message.lower()

    def test_insufficient_data_message(self, estimator: FirstLightEstimator) -> None:
        result = estimator.estimate(
            _make_timestamps(1),
            monthly_costs=Decimal("500"),
            now=NOW,
        )
        assert "Not enough activity" in result.message

    def test_no_missions_message(self, estimator: FirstLightEstimator) -> None:
        result = estimator.estimate(
            _make_timestamps(10),
            monthly_costs=Decimal("500"),
            now=NOW,
        )
        assert "Mission activity building" in result.message
