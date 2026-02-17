"""Tests for Genesis Common Fund (GCF) — Phase E-1.

Proves constitutional invariants:
- 1% GCF contribution computed correctly on every transaction.
- GCF inactive before First Light, activates automatically when fired.
- Updated invariant: commission + creator + worker + gcf == mission_reward.
- GCF contribution deducted from worker_payout.
- GCF_ACTIVATED and GCF_CONTRIBUTION_RECORDED events emitted.
- No per-actor balance query method exists (structurally impossible).
- GCF_CONTRIBUTION_RATE entrenched in constitutional_params.json.

Design tests (constitutional):
#45. Can the GCF contribution rate be changed without 4/5 supermajority +
     50% participation + 90-day cooling-off + confirmation vote?
     If yes, reject design.
"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

from genesis.compensation.engine import CommissionEngine
from genesis.compensation.escrow import EscrowManager
from genesis.compensation.gcf import GCFContribution, GCFState, GCFTracker
from genesis.compensation.ledger import OperationalLedger
from genesis.models.compensation import (
    CommissionBreakdown,
    CompletedMission,
    CostCategory,
    OperationalCostEntry,
    ReserveFundState,
)
from genesis.persistence.event_log import EventKind
from genesis.policy.resolver import PolicyResolver


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def engine(resolver: PolicyResolver) -> CommissionEngine:
    return CommissionEngine(resolver)


@pytest.fixture
def gcf_tracker() -> GCFTracker:
    return GCFTracker()


def _now() -> datetime:
    return datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc)


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


def _bootstrap_ledger(now: Optional[datetime] = None) -> OperationalLedger:
    """Ledger with no missions — triggers bootstrap mode."""
    return OperationalLedger()


def _populated_ledger(now: Optional[datetime] = None) -> OperationalLedger:
    """Ledger with enough missions to exit bootstrap mode."""
    if now is None:
        now = _now()
    ledger = OperationalLedger()
    for i in range(60):
        ledger.record_completed_mission(
            _make_mission(f"m_{i}", "1000.00", days_ago=i + 1, ops_cost="30.00", now=now)
        )
        ledger.record_operational_cost(
            _make_cost(f"c_{i}", CostCategory.INFRASTRUCTURE, "30.00", days_ago=i + 1, now=now)
        )
    return ledger


def _reserve_at_target() -> ReserveFundState:
    return ReserveFundState(
        balance=Decimal("50000"),
        target=Decimal("50000"),
        gap=Decimal("0"),
        is_below_target=False,
    )


# =====================================================================
# TestGCFContribution — 1% computation and invariant
# =====================================================================

class TestGCFContribution:
    """GCF contribution is correctly computed from mission_reward."""

    def test_gcf_1pct_computed_correctly(self, engine: CommissionEngine):
        """1% GCF contribution on mission_reward."""
        ledger = _populated_ledger()
        reserve = _reserve_at_target()
        breakdown = engine.compute_commission(
            mission_reward=Decimal("1000.00"),
            ledger=ledger,
            reserve=reserve,
            now=_now(),
        )
        assert breakdown.gcf_contribution == Decimal("10.00")

    def test_gcf_zero_when_rate_is_zero(self, resolver: PolicyResolver):
        """GCF contribution is zero when rate is 0."""
        # Override the commission policy to set gcf rate to 0
        resolver._commission_policy["gcf_contribution_rate"] = "0"
        engine = CommissionEngine(resolver)
        ledger = _populated_ledger()
        reserve = _reserve_at_target()
        breakdown = engine.compute_commission(
            mission_reward=Decimal("1000.00"),
            ledger=ledger,
            reserve=reserve,
            now=_now(),
        )
        assert breakdown.gcf_contribution == Decimal("0")
        # Restore
        resolver._commission_policy["gcf_contribution_rate"] = "0.01"

    def test_gcf_deducted_from_worker_payout(self, engine: CommissionEngine):
        """GCF is deducted from worker_payout, not from commission or creator."""
        ledger = _populated_ledger()
        reserve = _reserve_at_target()
        breakdown = engine.compute_commission(
            mission_reward=Decimal("1000.00"),
            ledger=ledger,
            reserve=reserve,
            now=_now(),
        )
        # Worker gets less by exactly the GCF amount
        expected_before_gcf = (
            breakdown.mission_reward
            - breakdown.commission_amount
            - breakdown.creator_allocation
        )
        assert breakdown.worker_payout == expected_before_gcf - breakdown.gcf_contribution

    def test_updated_invariant_holds(self, engine: CommissionEngine):
        """commission + creator + worker + gcf == mission_reward."""
        ledger = _populated_ledger()
        reserve = _reserve_at_target()
        for reward_str in ("100.00", "500.00", "1000.00", "9999.99"):
            breakdown = engine.compute_commission(
                mission_reward=Decimal(reward_str),
                ledger=ledger,
                reserve=reserve,
                now=_now(),
            )
            total = (
                breakdown.commission_amount
                + breakdown.creator_allocation
                + breakdown.worker_payout
                + breakdown.gcf_contribution
            )
            assert total == breakdown.mission_reward, (
                f"Invariant violation: {breakdown.commission_amount} + "
                f"{breakdown.creator_allocation} + {breakdown.worker_payout} + "
                f"{breakdown.gcf_contribution} = {total} != {breakdown.mission_reward}"
            )

    def test_gcf_appears_in_cost_breakdown(self, engine: CommissionEngine):
        """GCF contribution appears in the published cost breakdown."""
        ledger = _populated_ledger()
        reserve = _reserve_at_target()
        breakdown = engine.compute_commission(
            mission_reward=Decimal("1000.00"),
            ledger=ledger,
            reserve=reserve,
            now=_now(),
        )
        assert "gcf_contribution" in breakdown.cost_breakdown
        assert breakdown.cost_breakdown["gcf_contribution"] == Decimal("10.00")

    def test_gcf_rounds_to_2dp(self, engine: CommissionEngine):
        """GCF contribution is rounded to 2 decimal places."""
        ledger = _populated_ledger()
        reserve = _reserve_at_target()
        # 1% of 333.33 = 3.3333 → should round to 3.33
        breakdown = engine.compute_commission(
            mission_reward=Decimal("333.33"),
            ledger=ledger,
            reserve=reserve,
            now=_now(),
        )
        assert breakdown.gcf_contribution == Decimal("3.33")

    def test_gcf_on_small_amount(self, engine: CommissionEngine):
        """GCF computes correctly on a small mission_reward."""
        ledger = _populated_ledger()
        reserve = _reserve_at_target()
        breakdown = engine.compute_commission(
            mission_reward=Decimal("10.00"),
            ledger=ledger,
            reserve=reserve,
            now=_now(),
        )
        assert breakdown.gcf_contribution == Decimal("0.10")

    def test_escrow_invariant_with_gcf(self, engine: CommissionEngine):
        """Escrow validates the updated invariant including GCF."""
        ledger = _populated_ledger()
        reserve = _reserve_at_target()
        breakdown = engine.compute_commission(
            mission_reward=Decimal("500.00"),
            ledger=ledger,
            reserve=reserve,
            now=_now(),
        )
        # Create escrow with correct total
        manager = EscrowManager()
        record = manager.create_escrow(
            "m_test", "poster_1", breakdown.total_escrow
        )
        manager.lock_escrow(record.escrow_id)
        # Release should succeed with updated invariant
        released, payout = manager.release_escrow(record.escrow_id, breakdown)
        assert payout == breakdown.worker_payout


# =====================================================================
# TestGCFActivation — First Light activation lifecycle
# =====================================================================

class TestGCFActivation:
    """GCF activates automatically at First Light."""

    def test_gcf_inactive_by_default(self, gcf_tracker: GCFTracker):
        """GCF is inactive before First Light."""
        assert not gcf_tracker.is_active
        state = gcf_tracker.get_state()
        assert not state.activated
        assert state.activated_utc is None

    def test_gcf_activates(self, gcf_tracker: GCFTracker):
        """GCF activates when activate() is called."""
        now = _now()
        gcf_tracker.activate(now)
        assert gcf_tracker.is_active
        state = gcf_tracker.get_state()
        assert state.activated
        assert state.activated_utc == now

    def test_gcf_double_activation_rejected(self, gcf_tracker: GCFTracker):
        """GCF cannot be activated twice (idempotency protection)."""
        gcf_tracker.activate(_now())
        with pytest.raises(ValueError, match="already activated"):
            gcf_tracker.activate(_now())

    def test_gcf_contribution_before_activation_rejected(self, gcf_tracker: GCFTracker):
        """Contributions cannot be recorded before First Light."""
        with pytest.raises(ValueError, match="not yet activated"):
            gcf_tracker.record_contribution(
                amount=Decimal("10.00"),
                mission_id="m_1",
            )

    def test_gcf_contribution_after_activation(self, gcf_tracker: GCFTracker):
        """Contributions succeed after activation."""
        gcf_tracker.activate(_now())
        contrib = gcf_tracker.record_contribution(
            amount=Decimal("10.00"),
            mission_id="m_1",
            now=_now(),
        )
        assert contrib.amount == Decimal("10.00")
        assert contrib.mission_id == "m_1"
        state = gcf_tracker.get_state()
        assert state.balance == Decimal("10.00")
        assert state.contribution_count == 1


# =====================================================================
# TestGCFIntegration — accumulation and structural constraints
# =====================================================================

class TestGCFIntegration:
    """GCF contributions accumulate and are structurally non-extractable."""

    def test_multiple_contributions_accumulate(self, gcf_tracker: GCFTracker):
        """Multiple contributions accumulate in the GCF balance."""
        gcf_tracker.activate(_now())
        for i in range(5):
            gcf_tracker.record_contribution(
                amount=Decimal("10.00"),
                mission_id=f"m_{i}",
                now=_now(),
            )
        state = gcf_tracker.get_state()
        assert state.balance == Decimal("50.00")
        assert state.total_contributed == Decimal("50.00")
        assert state.contribution_count == 5

    def test_no_per_actor_balance_method(self):
        """GCFTracker has no method to query per-actor balance.

        This is a structural constraint — the fund is a shared commons.
        """
        tracker = GCFTracker()
        # Verify no method exists for per-actor queries
        assert not hasattr(tracker, "get_actor_balance")
        assert not hasattr(tracker, "actor_balance")
        assert not hasattr(tracker, "get_individual_share")
        assert not hasattr(tracker, "per_actor_balance")

    def test_negative_contribution_rejected(self, gcf_tracker: GCFTracker):
        """Negative contributions are rejected."""
        gcf_tracker.activate(_now())
        with pytest.raises(ValueError, match="positive"):
            gcf_tracker.record_contribution(
                amount=Decimal("-1.00"),
                mission_id="m_1",
            )

    def test_zero_contribution_rejected(self, gcf_tracker: GCFTracker):
        """Zero contributions are rejected."""
        gcf_tracker.activate(_now())
        with pytest.raises(ValueError, match="positive"):
            gcf_tracker.record_contribution(
                amount=Decimal("0"),
                mission_id="m_1",
            )

    def test_contributions_are_auditable(self, gcf_tracker: GCFTracker):
        """All contributions are retrievable for audit."""
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("10.00"), "m_1", _now())
        gcf_tracker.record_contribution(Decimal("20.00"), "m_2", _now())
        contribs = gcf_tracker.get_contributions()
        assert len(contribs) == 2
        assert contribs[0].amount == Decimal("10.00")
        assert contribs[1].amount == Decimal("20.00")


# =====================================================================
# TestGCFEventKinds — new event types exist
# =====================================================================

class TestGCFEventKinds:
    """GCF events are registered in the event system."""

    def test_gcf_activated_event_exists(self):
        assert EventKind.GCF_ACTIVATED.value == "gcf_activated"

    def test_gcf_contribution_recorded_event_exists(self):
        assert EventKind.GCF_CONTRIBUTION_RECORDED.value == "gcf_contribution_recorded"


# =====================================================================
# TestGCFCostCategory — GCF_CONTRIBUTION exists in CostCategory
# =====================================================================

class TestGCFCostCategory:
    """GCF_CONTRIBUTION is a valid cost category."""

    def test_gcf_contribution_category_exists(self):
        assert CostCategory.GCF_CONTRIBUTION.value == "gcf_contribution"


# =====================================================================
# TestEntrenched — GCF rate is entrenched
# =====================================================================

class TestEntrenched:
    """Entrenched provisions protect the GCF rate."""

    def test_entrenched_provisions_exist(self):
        """Constitutional params include entrenched provisions."""
        import json
        params = json.loads((CONFIG_DIR / "constitutional_params.json").read_text())
        entrenched = params.get("entrenched_provisions")
        assert entrenched is not None

    def test_gcf_rate_entrenched(self):
        """GCF_CONTRIBUTION_RATE is in entrenched provisions."""
        import json
        params = json.loads((CONFIG_DIR / "constitutional_params.json").read_text())
        entrenched = params["entrenched_provisions"]
        assert "GCF_CONTRIBUTION_RATE" in entrenched
        assert float(entrenched["GCF_CONTRIBUTION_RATE"]) == 0.01

    def test_amendment_threshold_high(self):
        """Entrenched amendment threshold is >= 0.80 (supermajority)."""
        import json
        params = json.loads((CONFIG_DIR / "constitutional_params.json").read_text())
        entrenched = params["entrenched_provisions"]
        assert entrenched["entrenched_amendment_threshold"] >= 0.80

    def test_participation_minimum(self):
        """Entrenched participation minimum is >= 0.50."""
        import json
        params = json.loads((CONFIG_DIR / "constitutional_params.json").read_text())
        entrenched = params["entrenched_provisions"]
        assert entrenched["entrenched_participation_minimum"] >= 0.50

    def test_cooling_off_period(self):
        """Entrenched cooling-off is >= 90 days."""
        import json
        params = json.loads((CONFIG_DIR / "constitutional_params.json").read_text())
        entrenched = params["entrenched_provisions"]
        assert entrenched["entrenched_cooling_off_days"] >= 90

    def test_confirmation_vote_required(self):
        """Entrenched provisions require confirmation vote."""
        import json
        params = json.loads((CONFIG_DIR / "constitutional_params.json").read_text())
        entrenched = params["entrenched_provisions"]
        assert entrenched["entrenched_confirmation_vote_required"] is True

    def test_gcf_rate_in_commission_policy(self):
        """Commission policy includes gcf_contribution_rate."""
        import json
        cp = json.loads((CONFIG_DIR / "commission_policy.json").read_text())
        assert "gcf_contribution_rate" in cp
        assert float(cp["gcf_contribution_rate"]) == 0.01

    def test_gcf_rate_cross_check(self):
        """Commission policy rate matches entrenched rate."""
        import json
        params = json.loads((CONFIG_DIR / "constitutional_params.json").read_text())
        cp = json.loads((CONFIG_DIR / "commission_policy.json").read_text())
        assert float(cp["gcf_contribution_rate"]) == float(
            params["entrenched_provisions"]["GCF_CONTRIBUTION_RATE"]
        )
