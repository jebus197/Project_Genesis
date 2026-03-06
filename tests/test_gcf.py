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
from genesis.compensation.gcf import GCFContribution, GCFRefund, GCFState, GCFTracker
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

    def test_gcf_refund_credited_event_exists(self):
        """GCF_REFUND_CREDITED event kind exists (P1 fix)."""
        assert EventKind.GCF_REFUND_CREDITED.value == "gcf_refund_credited"


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


# =====================================================================
# TestGCFRefund — P1 fix: refunds are first-class auditable records
# =====================================================================

class TestGCFRefund:
    """Refunds are recorded, auditable, and maintain the accounting identity.

    Falsification targets:
    - Can a refund be credited without appearing in the refund list? → No.
    - Can the balance diverge from contributed - disbursed + refunded? → No.
    - Can refund records be modified after creation? → No (frozen dataclass).
    """

    def test_refund_creates_record(self, gcf_tracker: GCFTracker):
        """credit_refund() returns an immutable GCFRefund record."""
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("100.00"), "m_1", _now())
        # Simulate disbursement
        gcf_tracker.record_disbursement(
            "d_1", "p_1", Decimal("50.00"), "COMPUTE", "test", _now()
        )
        refund = gcf_tracker.credit_refund(
            Decimal("50.00"), "listing cancelled", _now()
        )
        assert isinstance(refund, GCFRefund)
        assert refund.amount == Decimal("50.00")
        assert refund.reason == "listing cancelled"

    def test_refund_appears_in_audit_list(self, gcf_tracker: GCFTracker):
        """Refunds are retrievable for audit (no ghost refunds)."""
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("100.00"), "m_1", _now())
        gcf_tracker.record_disbursement(
            "d_1", "p_1", Decimal("50.00"), "COMPUTE", "test", _now()
        )
        gcf_tracker.credit_refund(Decimal("50.00"), "cancelled", _now())
        refunds = gcf_tracker.get_refunds()
        assert len(refunds) == 1
        assert refunds[0].amount == Decimal("50.00")

    def test_refund_updates_total_refunded(self, gcf_tracker: GCFTracker):
        """total_refunded and refund_count are updated."""
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("200.00"), "m_1", _now())
        gcf_tracker.record_disbursement(
            "d_1", "p_1", Decimal("100.00"), "COMPUTE", "test", _now()
        )
        gcf_tracker.credit_refund(Decimal("40.00"), "partial", _now())
        gcf_tracker.credit_refund(Decimal("60.00"), "remainder", _now())
        state = gcf_tracker.get_state()
        assert state.total_refunded == Decimal("100.00")
        assert state.refund_count == 2

    def test_refund_before_activation_rejected(self, gcf_tracker: GCFTracker):
        """Refunds require First Light."""
        with pytest.raises(ValueError, match="not yet activated"):
            gcf_tracker.credit_refund(Decimal("10.00"), "test")

    def test_negative_refund_rejected(self, gcf_tracker: GCFTracker):
        """Negative refund amounts are rejected."""
        gcf_tracker.activate(_now())
        with pytest.raises(ValueError, match="positive"):
            gcf_tracker.credit_refund(Decimal("-1.00"), "test")

    def test_zero_refund_rejected(self, gcf_tracker: GCFTracker):
        """Zero refund amounts are rejected."""
        gcf_tracker.activate(_now())
        with pytest.raises(ValueError, match="positive"):
            gcf_tracker.credit_refund(Decimal("0"), "test")

    def test_refund_exceeding_net_disbursed_rejected(self, gcf_tracker: GCFTracker):
        """Cannot refund more than was actually disbursed (net of prior refunds).

        Falsification from P-pass iteration 2: without this guard, you
        could create positive balance from nothing by refunding phantom funds.
        """
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("1000.00"), "m_1", _now())
        gcf_tracker.record_disbursement(
            "d_1", "p_1", Decimal("400.00"), "COMPUTE", "test", _now()
        )
        # Refund exactly what was disbursed — should succeed
        gcf_tracker.credit_refund(Decimal("400.00"), "full cancel", _now())
        # Attempt another refund — net disbursed is now 0
        with pytest.raises(ValueError, match="exceeds net disbursed"):
            gcf_tracker.credit_refund(Decimal("1.00"), "phantom refund", _now())

    def test_refund_with_no_disbursements_rejected(self, gcf_tracker: GCFTracker):
        """Cannot refund when nothing has been disbursed."""
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("1000.00"), "m_1", _now())
        with pytest.raises(ValueError, match="exceeds net disbursed"):
            gcf_tracker.credit_refund(Decimal("1.00"), "no disbursements exist", _now())

    def test_refund_record_is_frozen(self, gcf_tracker: GCFTracker):
        """GCFRefund is immutable (frozen dataclass)."""
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("100.00"), "m_1", _now())
        gcf_tracker.record_disbursement(
            "d_1", "p_1", Decimal("50.00"), "COMPUTE", "test", _now()
        )
        refund = gcf_tracker.credit_refund(Decimal("50.00"), "test", _now())
        with pytest.raises(AttributeError):
            refund.amount = Decimal("999.99")


# =====================================================================
# TestGCFAccountingIdentity — P3 fix: three-term invariant
# =====================================================================

class TestGCFAccountingIdentity:
    """balance = total_contributed - total_disbursed + total_refunded.

    Falsification target: can the balance diverge from the three-term
    identity after ANY sequence of operations? If yes, reject design.
    """

    def test_identity_after_contributions_only(self, gcf_tracker: GCFTracker):
        """Identity holds with contributions only."""
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("100.00"), "m_1", _now())
        gcf_tracker.record_contribution(Decimal("200.00"), "m_2", _now())
        assert gcf_tracker.verify_accounting_identity()
        state = gcf_tracker.get_state()
        assert state.balance == Decimal("300.00")

    def test_identity_after_disbursement(self, gcf_tracker: GCFTracker):
        """Identity holds after disbursements."""
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("1000.00"), "m_1", _now())
        gcf_tracker.record_disbursement(
            "d_1", "p_1", Decimal("400.00"), "COMPUTE", "test", _now()
        )
        assert gcf_tracker.verify_accounting_identity()
        state = gcf_tracker.get_state()
        assert state.balance == Decimal("600.00")

    def test_identity_after_refund(self, gcf_tracker: GCFTracker):
        """Identity holds after contribute → disburse → refund cycle.

        This is the exact scenario that broke the old two-term identity.
        Old: balance=1000, contributed-disbursed=600 → MISMATCH.
        New: contributed(1000) - disbursed(400) + refunded(400) = 1000 → CORRECT.
        """
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("1000.00"), "m_1", _now())
        gcf_tracker.record_disbursement(
            "d_1", "p_1", Decimal("400.00"), "COMPUTE", "test", _now()
        )
        gcf_tracker.credit_refund(Decimal("400.00"), "listing cancelled", _now())
        assert gcf_tracker.verify_accounting_identity()
        state = gcf_tracker.get_state()
        assert state.balance == Decimal("1000.00")
        assert state.total_contributed == Decimal("1000.00")
        assert state.total_disbursed == Decimal("400.00")
        assert state.total_refunded == Decimal("400.00")

    def test_identity_after_mixed_operations(self, gcf_tracker: GCFTracker):
        """Identity holds through a complex mixed sequence."""
        gcf_tracker.activate(_now())
        # Contribute 500
        gcf_tracker.record_contribution(Decimal("500.00"), "m_1", _now())
        # Contribute 300
        gcf_tracker.record_contribution(Decimal("300.00"), "m_2", _now())
        # Disburse 200
        gcf_tracker.record_disbursement(
            "d_1", "p_1", Decimal("200.00"), "COMPUTE", "test", _now()
        )
        # Refund 150
        gcf_tracker.credit_refund(Decimal("150.00"), "partial cancel", _now())
        # Disburse another 100
        gcf_tracker.record_disbursement(
            "d_2", "p_2", Decimal("100.00"), "RESEARCH", "test2", _now()
        )
        # Refund 100
        gcf_tracker.credit_refund(Decimal("100.00"), "full cancel", _now())
        assert gcf_tracker.verify_accounting_identity()
        # 800 - 300 + 250 = 750
        state = gcf_tracker.get_state()
        assert state.balance == Decimal("750.00")


# =====================================================================
# TestGCFPersistence — P4 fix: from_dict verifies balance on recovery
# =====================================================================

class TestGCFPersistence:
    """from_dict re-derives balance and rejects tampered data.

    Falsification target: can from_dict load a tampered balance
    without raising? If yes, reject design.
    """

    def test_roundtrip_with_refunds(self, gcf_tracker: GCFTracker):
        """to_dict → from_dict preserves all state including refunds."""
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("1000.00"), "m_1", _now())
        gcf_tracker.record_disbursement(
            "d_1", "p_1", Decimal("400.00"), "COMPUTE", "test", _now()
        )
        gcf_tracker.credit_refund(Decimal("200.00"), "partial cancel", _now())

        data = gcf_tracker.to_dict()
        restored = GCFTracker.from_dict(data)
        state = restored.get_state()
        assert state.balance == Decimal("800.00")
        assert state.total_contributed == Decimal("1000.00")
        assert state.total_disbursed == Decimal("400.00")
        assert state.total_refunded == Decimal("200.00")
        assert state.contribution_count == 1
        assert state.disbursement_count == 1
        assert state.refund_count == 1
        assert len(restored.get_refunds()) == 1
        assert restored.verify_accounting_identity()

    def test_tampered_balance_rejected(self, gcf_tracker: GCFTracker):
        """from_dict raises ValueError if stored balance was tampered."""
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("1000.00"), "m_1", _now())
        data = gcf_tracker.to_dict()
        # Tamper: inflate balance
        data["balance"] = "9999.00"
        with pytest.raises(ValueError, match="integrity violation"):
            GCFTracker.from_dict(data)

    def test_tampered_contribution_rejected(self, gcf_tracker: GCFTracker):
        """from_dict catches contribution list tampering."""
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("100.00"), "m_1", _now())
        data = gcf_tracker.to_dict()
        # Tamper: inflate a contribution amount
        data["contributions"][0]["amount"] = "500.00"
        with pytest.raises(ValueError, match="integrity violation"):
            GCFTracker.from_dict(data)

    def test_tampered_totals_rejected(self, gcf_tracker: GCFTracker):
        """from_dict catches total-field tampering (even if balance is consistent).

        Falsification from P-pass iteration 2: an attacker inflates
        total_contributed and total_disbursed by the same amount. The
        derived balance still matches, but the totals are fabricated.
        """
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("1000.00"), "m_1", _now())
        gcf_tracker.record_disbursement(
            "d_1", "p_1", Decimal("400.00"), "COMPUTE", "test", _now()
        )
        data = gcf_tracker.to_dict()
        # Tamper: inflate both totals by same amount (balance still correct)
        data["total_contributed"] = "5000.00"
        data["total_disbursed"] = "4400.00"
        with pytest.raises(ValueError, match="integrity violation"):
            GCFTracker.from_dict(data)

    def test_tampered_counts_rejected(self, gcf_tracker: GCFTracker):
        """from_dict catches count-field tampering."""
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("100.00"), "m_1", _now())
        data = gcf_tracker.to_dict()
        # Tamper: inflate contribution count
        data["contribution_count"] = 999
        with pytest.raises(ValueError, match="integrity violation"):
            GCFTracker.from_dict(data)

    def test_backward_compat_no_refunds(self, gcf_tracker: GCFTracker):
        """from_dict handles legacy data with no refund fields."""
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("100.00"), "m_1", _now())
        data = gcf_tracker.to_dict()
        # Remove refund fields (simulating legacy data)
        del data["total_refunded"]
        del data["refund_count"]
        del data["refunds"]
        restored = GCFTracker.from_dict(data)
        state = restored.get_state()
        assert state.balance == Decimal("100.00")
        assert state.total_refunded == Decimal("0")
        assert state.refund_count == 0
        assert restored.verify_accounting_identity()


# =====================================================================
# TestGCFStateImmutability — P5 fix: get_state() returns a copy
# =====================================================================

class TestGCFStateImmutability:
    """get_state() returns a snapshot — mutations cannot corrupt internals.

    Falsification target: can get_state().balance = 0 corrupt the
    tracker's internal state? If yes, reject design.
    """

    def test_state_mutation_does_not_affect_tracker(self, gcf_tracker: GCFTracker):
        """Mutating the returned state object has no effect on the tracker."""
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("100.00"), "m_1", _now())
        state = gcf_tracker.get_state()
        # Attempt to corrupt
        state.balance = Decimal("0")
        state.total_contributed = Decimal("0")
        state.contribution_count = 0
        # Internal state is unchanged
        real_state = gcf_tracker.get_state()
        assert real_state.balance == Decimal("100.00")
        assert real_state.total_contributed == Decimal("100.00")
        assert real_state.contribution_count == 1

    def test_successive_snapshots_are_independent(self, gcf_tracker: GCFTracker):
        """Two successive get_state() calls return independent objects."""
        gcf_tracker.activate(_now())
        gcf_tracker.record_contribution(Decimal("50.00"), "m_1", _now())
        s1 = gcf_tracker.get_state()
        gcf_tracker.record_contribution(Decimal("50.00"), "m_2", _now())
        s2 = gcf_tracker.get_state()
        assert s1.balance == Decimal("50.00")
        assert s2.balance == Decimal("100.00")
        assert s1 is not s2
