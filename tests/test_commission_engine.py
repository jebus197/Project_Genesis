"""Tests for commission engine — proves constitutional commission invariants hold."""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

from genesis.compensation.engine import CommissionEngine
from genesis.compensation.ledger import OperationalLedger
from genesis.models.compensation import (
    CommissionBreakdown,
    CompletedMission,
    CostCategory,
    OperationalCostEntry,
    ReserveFundState,
)
from genesis.policy.resolver import PolicyResolver


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def engine(resolver: PolicyResolver) -> CommissionEngine:
    return CommissionEngine(resolver)


def _now() -> datetime:
    return datetime(2026, 2, 16, 12, 0, 0, tzinfo=timezone.utc)


def _make_mission(
    mission_id: str,
    reward: str,
    days_ago: int,
    ops_cost: str = "0",
    now: Optional[datetime] = None,
) -> CompletedMission:
    if now is None:
        now = _now()
    return CompletedMission(
        mission_id=mission_id,
        reward_amount=Decimal(reward),
        completed_utc=now - timedelta(days=days_ago),
        operational_costs=Decimal(ops_cost),
    )


def _make_cost(
    cost_id: str,
    category: CostCategory,
    amount: str,
    days_ago: int,
    now: Optional[datetime] = None,
) -> OperationalCostEntry:
    if now is None:
        now = _now()
    return OperationalCostEntry(
        cost_id=cost_id,
        category=category,
        amount=Decimal(amount),
        timestamp_utc=now - timedelta(days=days_ago),
        description=f"Test cost {cost_id}",
    )


def _healthy_reserve() -> ReserveFundState:
    """Reserve at target — maintenance only."""
    return ReserveFundState(
        balance=Decimal("10000"),
        target=Decimal("10000"),
        gap=Decimal("0"),
        is_below_target=False,
    )


def _depleted_reserve() -> ReserveFundState:
    """Reserve below target — gap contribution needed."""
    return ReserveFundState(
        balance=Decimal("1000"),
        target=Decimal("10000"),
        gap=Decimal("9000"),
        is_below_target=True,
    )


def _populate_ledger(
    ledger: OperationalLedger,
    num_missions: int = 60,
    reward: str = "500",
    cost_per_mission: str = "10",
) -> None:
    """Populate a ledger with completed missions and costs."""
    now = _now()
    for i in range(num_missions):
        ledger.record_completed_mission(
            _make_mission(f"m_{i}", reward, days_ago=i, now=now)
        )
        ledger.record_operational_cost(
            _make_cost(
                f"c_{i}", CostCategory.INFRASTRUCTURE, cost_per_mission,
                days_ago=i, now=now,
            )
        )


class TestRateComputation:
    """Tests for the core rate computation."""

    def test_rate_within_bounds(self, engine: CommissionEngine) -> None:
        """Rate is always within [FLOOR, CEILING]."""
        ledger = OperationalLedger()
        _populate_ledger(ledger)
        result = engine.compute_commission(
            Decimal("500"), ledger, _healthy_reserve(), now=_now()
        )
        assert Decimal("0.02") <= result.rate <= Decimal("0.10")

    def test_rate_at_floor_when_costs_low(self, engine: CommissionEngine) -> None:
        """When costs are very low relative to mission value, rate hits floor."""
        ledger = OperationalLedger()
        now = _now()
        # 60 missions at 1000 each, costs only 1 per mission
        for i in range(60):
            ledger.record_completed_mission(
                _make_mission(f"m_{i}", "1000", days_ago=i, now=now)
            )
            ledger.record_operational_cost(
                _make_cost(f"c_{i}", CostCategory.INFRASTRUCTURE, "1", days_ago=i, now=now)
            )
        result = engine.compute_commission(
            Decimal("500"), ledger, _healthy_reserve(), now=now
        )
        assert result.rate == Decimal("0.02")

    def test_rate_at_ceiling_when_costs_high(self, engine: CommissionEngine) -> None:
        """When costs are very high relative to mission value, rate hits ceiling."""
        ledger = OperationalLedger()
        now = _now()
        # 60 missions at 100 each, costs 50 per mission (50% cost ratio)
        for i in range(60):
            ledger.record_completed_mission(
                _make_mission(f"m_{i}", "100", days_ago=i, now=now)
            )
            ledger.record_operational_cost(
                _make_cost(f"c_{i}", CostCategory.INFRASTRUCTURE, "50", days_ago=i, now=now)
            )
        result = engine.compute_commission(
            Decimal("500"), ledger, _healthy_reserve(), now=now
        )
        assert result.rate == Decimal("0.10")

    def test_mid_range_rate(self, engine: CommissionEngine) -> None:
        """Rate at mid-range — cost_ratio * safety_margin between floor and ceiling."""
        ledger = OperationalLedger()
        now = _now()
        # 60 missions at 1000, costs 40 each → cost_ratio = 0.04, raw_rate = 0.052
        for i in range(60):
            ledger.record_completed_mission(
                _make_mission(f"m_{i}", "1000", days_ago=i, now=now)
            )
            ledger.record_operational_cost(
                _make_cost(f"c_{i}", CostCategory.INFRASTRUCTURE, "40", days_ago=i, now=now)
            )
        result = engine.compute_commission(
            Decimal("1000"), ledger, _healthy_reserve(), now=now
        )
        assert Decimal("0.02") < result.rate < Decimal("0.10")

    def test_min_fee_enforcement(self, engine: CommissionEngine) -> None:
        """Commission is never less than MIN_FEE (5 USDC)."""
        ledger = OperationalLedger()
        _populate_ledger(ledger, reward="500", cost_per_mission="1")
        # Small mission reward — rate * reward might be < 5 USDC
        result = engine.compute_commission(
            Decimal("10"), ledger, _healthy_reserve(), now=_now()
        )
        assert result.commission_amount >= Decimal("5.00")

    def test_commission_cannot_exceed_reward(self, engine: CommissionEngine) -> None:
        """Commission is capped at the mission reward."""
        ledger = OperationalLedger()
        _populate_ledger(ledger, reward="500", cost_per_mission="1")
        # Tiny reward — min fee would exceed it
        result = engine.compute_commission(
            Decimal("3"), ledger, _healthy_reserve(), now=_now()
        )
        assert result.commission_amount <= Decimal("3")

    def test_worker_payout_plus_deductions_equals_reward(
        self, engine: CommissionEngine
    ) -> None:
        """Worker payout + commission + creator allocation = mission reward."""
        ledger = OperationalLedger()
        _populate_ledger(ledger)
        result = engine.compute_commission(
            Decimal("500"), ledger, _healthy_reserve(), now=_now()
        )
        total = result.worker_payout + result.commission_amount + result.creator_allocation
        assert total == result.mission_reward


class TestBootstrapMode:
    """Tests for bootstrap mode (< 50 completed missions)."""

    def test_bootstrap_detected(self, engine: CommissionEngine) -> None:
        """Bootstrap mode when fewer than 50 total missions."""
        ledger = OperationalLedger()
        now = _now()
        for i in range(10):
            ledger.record_completed_mission(
                _make_mission(f"m_{i}", "500", days_ago=i, now=now)
            )
            ledger.record_operational_cost(
                _make_cost(f"c_{i}", CostCategory.INFRASTRUCTURE, "1", days_ago=i, now=now)
            )
        result = engine.compute_commission(
            Decimal("500"), ledger, _healthy_reserve(), now=now
        )
        assert result.is_bootstrap is True
        assert result.window_stats.is_bootstrap is True

    def test_bootstrap_min_rate_applied(self, engine: CommissionEngine) -> None:
        """Bootstrap mode applies 5% minimum rate even when costs are low."""
        ledger = OperationalLedger()
        now = _now()
        # Very low costs — without bootstrap, rate would be at floor (2%)
        for i in range(10):
            ledger.record_completed_mission(
                _make_mission(f"m_{i}", "10000", days_ago=i, now=now)
            )
            ledger.record_operational_cost(
                _make_cost(f"c_{i}", CostCategory.INFRASTRUCTURE, "1", days_ago=i, now=now)
            )
        result = engine.compute_commission(
            Decimal("500"), ledger, _healthy_reserve(), now=now
        )
        assert result.rate >= Decimal("0.05")

    def test_bootstrap_auto_expires(self, engine: CommissionEngine) -> None:
        """Bootstrap mode auto-expires at 50 completed missions."""
        ledger = OperationalLedger()
        now = _now()
        # Exactly 50 missions — no longer bootstrap
        for i in range(50):
            ledger.record_completed_mission(
                _make_mission(f"m_{i}", "10000", days_ago=i, now=now)
            )
            ledger.record_operational_cost(
                _make_cost(f"c_{i}", CostCategory.INFRASTRUCTURE, "1", days_ago=i, now=now)
            )
        result = engine.compute_commission(
            Decimal("500"), ledger, _healthy_reserve(), now=now
        )
        assert result.is_bootstrap is False
        # Without bootstrap, low costs → rate at floor
        assert result.rate == Decimal("0.02")


class TestReserveFund:
    """Tests for reserve fund impact on commission rate."""

    def test_healthy_reserve_low_contribution(
        self, engine: CommissionEngine
    ) -> None:
        """Reserve at target — only maintenance contribution (rate lower)."""
        ledger = OperationalLedger()
        _populate_ledger(ledger, num_missions=60, reward="500", cost_per_mission="20")
        result_healthy = engine.compute_commission(
            Decimal("500"), ledger, _healthy_reserve(), now=_now()
        )
        result_depleted = engine.compute_commission(
            Decimal("500"), ledger, _depleted_reserve(), now=_now()
        )
        # Healthy reserve → lower rate than depleted
        assert result_healthy.rate <= result_depleted.rate

    def test_depleted_reserve_raises_rate(
        self, engine: CommissionEngine
    ) -> None:
        """Reserve below target — gap contribution raises rate."""
        ledger = OperationalLedger()
        _populate_ledger(ledger, num_missions=60, reward="500", cost_per_mission="20")
        result = engine.compute_commission(
            Decimal("500"), ledger, _depleted_reserve(), now=_now()
        )
        assert result.reserve_contribution > Decimal("0")


class TestDecimalArithmetic:
    """Tests that all values use Decimal, never float."""

    def test_all_decimal_values(self, engine: CommissionEngine) -> None:
        """All monetary values in breakdown are Decimal."""
        ledger = OperationalLedger()
        _populate_ledger(ledger)
        result = engine.compute_commission(
            Decimal("500"), ledger, _healthy_reserve(), now=_now()
        )
        assert isinstance(result.rate, Decimal)
        assert isinstance(result.raw_rate, Decimal)
        assert isinstance(result.cost_ratio, Decimal)
        assert isinstance(result.commission_amount, Decimal)
        assert isinstance(result.creator_allocation, Decimal)
        assert isinstance(result.employer_creator_fee, Decimal)
        assert isinstance(result.worker_payout, Decimal)
        assert isinstance(result.mission_reward, Decimal)
        assert isinstance(result.reserve_contribution, Decimal)
        assert isinstance(result.safety_margin, Decimal)
        for v in result.cost_breakdown.values():
            assert isinstance(v, Decimal)


class TestCostBreakdown:
    """Tests for the published cost breakdown."""

    def test_breakdown_has_categories(self, engine: CommissionEngine) -> None:
        """Cost breakdown contains entries for each cost category."""
        ledger = OperationalLedger()
        now = _now()
        for i in range(60):
            ledger.record_completed_mission(
                _make_mission(f"m_{i}", "500", days_ago=i, now=now)
            )
        ledger.record_operational_cost(
            _make_cost("infra_1", CostCategory.INFRASTRUCTURE, "100", 5, now)
        )
        ledger.record_operational_cost(
            _make_cost("gas_1", CostCategory.GAS, "50", 5, now)
        )
        ledger.record_operational_cost(
            _make_cost("legal_1", CostCategory.LEGAL, "30", 5, now)
        )
        result = engine.compute_commission(
            Decimal("500"), ledger, _healthy_reserve(), now=now
        )
        assert "infrastructure" in result.cost_breakdown
        assert "gas" in result.cost_breakdown
        assert "legal" in result.cost_breakdown

    def test_empty_ledger_uses_ceiling(self, engine: CommissionEngine) -> None:
        """With no historical data, rate defaults to ceiling."""
        ledger = OperationalLedger()
        result = engine.compute_commission(
            Decimal("500"), ledger, _healthy_reserve(), now=_now()
        )
        assert result.rate == Decimal("0.10")
        assert result.is_bootstrap is True

    def test_creator_allocation_in_every_breakdown(self, engine: CommissionEngine) -> None:
        """Both-sides creator allocation appears in cost_breakdown."""
        ledger = OperationalLedger()
        now = _now()
        for i in range(60):
            ledger.record_completed_mission(
                _make_mission(f"m_{i}", "500", days_ago=i, now=now)
            )
        ledger.record_operational_cost(
            _make_cost("infra_1", CostCategory.INFRASTRUCTURE, "100", 5, now)
        )
        result = engine.compute_commission(
            Decimal("500"), ledger, _healthy_reserve(), now=now
        )
        # Worker-side: 5% of (500 - commission)
        assert "creator_allocation" in result.cost_breakdown
        assert result.creator_allocation > Decimal("0")
        assert result.creator_allocation == result.cost_breakdown["creator_allocation"]
        # Employer-side: 5% of 500 = 25.00
        assert "employer_creator_fee" in result.cost_breakdown
        assert result.employer_creator_fee == Decimal("25.00")
        assert result.employer_creator_fee == result.cost_breakdown["employer_creator_fee"]
        # Total creator income = both sides
        assert result.total_creator_income == result.creator_allocation + result.employer_creator_fee

    def test_employer_fee_scales_with_mission_reward(
        self, engine: CommissionEngine
    ) -> None:
        """Employer creator fee is always 5% of mission_reward, regardless of commission rate."""
        now = _now()
        # Scenario 1: low costs → low commission rate
        ledger_low = OperationalLedger()
        for i in range(60):
            ledger_low.record_completed_mission(
                _make_mission(f"m_{i}", "1000", days_ago=i, now=now)
            )
            ledger_low.record_operational_cost(
                _make_cost(f"c_{i}", CostCategory.INFRASTRUCTURE, "1", days_ago=i, now=now)
            )
        result_low = engine.compute_commission(
            Decimal("1000"), ledger_low, _healthy_reserve(), now=now
        )

        # Scenario 2: high costs → high commission rate
        ledger_high = OperationalLedger()
        for i in range(60):
            ledger_high.record_completed_mission(
                _make_mission(f"m_{i}", "100", days_ago=i, now=now)
            )
            ledger_high.record_operational_cost(
                _make_cost(f"c_{i}", CostCategory.INFRASTRUCTURE, "50", days_ago=i, now=now)
            )
        result_high = engine.compute_commission(
            Decimal("1000"), ledger_high, _healthy_reserve(), now=now
        )

        # Different commission rates
        assert result_low.rate != result_high.rate
        # Same employer fee: both are 5% of 1000 = 50.00
        assert result_low.employer_creator_fee == Decimal("50.00")
        assert result_high.employer_creator_fee == Decimal("50.00")
        # Worker-side creator allocation DIFFERS because commission amounts differ
        assert result_low.creator_allocation != result_high.creator_allocation
        # Lower commission → more for worker → more for creator (worker-side)
        assert result_low.creator_allocation > result_high.creator_allocation

    def test_both_sides_invariants(self, engine: CommissionEngine) -> None:
        """Commission + creator_allocation + worker_payout == mission_reward.
        total_escrow == mission_reward + employer_creator_fee.
        """
        ledger = OperationalLedger()
        _populate_ledger(ledger)
        result = engine.compute_commission(
            Decimal("1000"), ledger, _healthy_reserve(), now=_now()
        )
        # Worker-side invariant
        worker_total = result.commission_amount + result.creator_allocation + result.worker_payout
        assert worker_total == result.mission_reward
        # Escrow invariant
        assert result.total_escrow == result.mission_reward + result.employer_creator_fee
