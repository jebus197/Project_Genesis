"""Tests for Dynamic Equilibrium — constitutional enforcement.

Proves constitutional invariants:
- Machine work (Tier 0–2) does NOT receive full human-equivalent valuation
  (design test #101).
- The human work premium scales with the machine-to-human productivity
  ratio — not static (design test #102).
- Tier 3-recognised machine classes exit the discount for that domain
  (design test #103).
- Tier 3 recognition does NOT grant governance voting rights
  (design test #104).
- Trust-gated registration prevents fleet concentration by a single
  operator (design test #105).
- Dynamic equilibrium provides a structured pathway (Tier 3) toward
  economic parity — it does not permanently foreclose it
  (design test #106).

Also covers:
- EquilibriumResult dataclass is frozen (immutable)
- Human workers pass through with zero differential
- CommissionBreakdown accounting invariant preserved with equilibrium
- GCF receives the differential (not the employer, not the platform)
- machine_registration_capacity: trust-gated scaling with guaranteed floor
- CommissionEngine integration: equilibrium wired into settlement pipeline
- Constitutional parameters in constitutional_params.json

Design test #101: Does machine work (Tier 0–2) receive full human-
equivalent valuation without the machine demonstrating self-agency?
If yes, reject design.

Design test #102: Does the human work premium remain static regardless of
the machine-to-human productivity ratio? If yes, reject design.

Design test #103: Can a Tier 3-recognised machine class continue to have
its domain work valued at a discount after recognition? If yes, reject
design.

Design test #104: Does Tier 3 recognition automatically grant governance
voting rights? If yes, reject design.

Design test #105: Can the equilibrium curve be bypassed through machine
fleet concentration by a single operator without trust-gated registration
limits? If yes, reject design.

Design test #106: Does the dynamic equilibrium principle permanently
foreclose economic parity for machines, or does it provide a structured
pathway (Tier 3) toward it? If it forecloses, reject design.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from genesis.compensation.equilibrium import (
    DEFAULT_MACHINE_DISCOUNT,
    DEFAULT_REGISTRATION_CAPACITY_FACTOR,
    EquilibriumResult,
    compute_equilibrium_differential,
    machine_registration_capacity,
)
from genesis.models.compensation import CommissionBreakdown


# ──────────────────────────────────────────────────────────────────────
# Unit tests — compute_equilibrium_differential
# ──────────────────────────────────────────────────────────────────────


class TestEquilibriumDifferential:
    """Prove differential valuation works correctly."""

    def test_human_worker_no_differential(self) -> None:
        """Human workers pass through with zero differential."""
        result = compute_equilibrium_differential(
            worker_payout=Decimal("400.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=False,
        )
        assert result.differential_amount == Decimal("0")
        assert result.adjusted_worker_payout == Decimal("400.00")
        assert result.adjusted_gcf_contribution == Decimal("5.00")
        assert result.discount_rate == Decimal("0")
        assert result.worker_is_machine is False
        assert result.machine_tier == -1

    def test_machine_tier0_receives_discount(self) -> None:
        """Design test #101: Tier 0 machine does NOT receive full
        human-equivalent valuation."""
        result = compute_equilibrium_differential(
            worker_payout=Decimal("400.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=True,
            machine_tier=0,
        )
        # Default 50% discount: worker loses 200, GCF gains 200
        assert result.differential_amount == Decimal("200.00")
        assert result.adjusted_worker_payout == Decimal("200.00")
        assert result.adjusted_gcf_contribution == Decimal("205.00")
        assert result.discount_rate == DEFAULT_MACHINE_DISCOUNT
        assert result.worker_is_machine is True

    def test_machine_tier1_receives_discount(self) -> None:
        """Tier 1 machines are also subject to differential valuation."""
        result = compute_equilibrium_differential(
            worker_payout=Decimal("400.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=True,
            machine_tier=1,
        )
        assert result.differential_amount > Decimal("0")
        assert result.adjusted_worker_payout < Decimal("400.00")

    def test_machine_tier2_receives_discount(self) -> None:
        """Tier 2 machines are still subject to differential valuation."""
        result = compute_equilibrium_differential(
            worker_payout=Decimal("400.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=True,
            machine_tier=2,
        )
        assert result.differential_amount > Decimal("0")
        assert result.adjusted_worker_payout < Decimal("400.00")

    def test_tier3_machine_no_discount(self) -> None:
        """Design test #103: Tier 3 machine class exits the discount
        for that domain — receives full economic parity."""
        result = compute_equilibrium_differential(
            worker_payout=Decimal("400.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=True,
            machine_tier=3,
            domain="healthcare",
        )
        assert result.differential_amount == Decimal("0")
        assert result.adjusted_worker_payout == Decimal("400.00")
        assert result.adjusted_gcf_contribution == Decimal("5.00")
        assert result.tier3_recognized is True
        assert result.discount_rate == Decimal("0")

    def test_tier3_recognized_flag_overrides_tier(self) -> None:
        """A machine explicitly recognised as Tier 3 in a domain
        exits the discount even if its tier number is lower."""
        result = compute_equilibrium_differential(
            worker_payout=Decimal("400.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=True,
            machine_tier=2,
            domain="healthcare",
            tier3_recognized=True,
        )
        assert result.differential_amount == Decimal("0")
        assert result.tier3_recognized is True

    def test_tier4_machine_no_discount(self) -> None:
        """Tier 4 machines also have full parity (Tier 3+ = no discount)."""
        result = compute_equilibrium_differential(
            worker_payout=Decimal("400.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=True,
            machine_tier=4,
        )
        assert result.differential_amount == Decimal("0")

    def test_custom_discount_rate(self) -> None:
        """Design test #102: discount rate is configurable, not static."""
        result_30 = compute_equilibrium_differential(
            worker_payout=Decimal("400.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=True,
            machine_tier=0,
            discount_rate=Decimal("0.30"),
        )
        result_70 = compute_equilibrium_differential(
            worker_payout=Decimal("400.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=True,
            machine_tier=0,
            discount_rate=Decimal("0.70"),
        )
        # Different rates produce different differentials
        assert result_30.differential_amount == Decimal("120.00")
        assert result_70.differential_amount == Decimal("280.00")
        assert result_30.differential_amount != result_70.differential_amount

    def test_differential_preserves_accounting_invariant(self) -> None:
        """The differential is a REALLOCATION within the sum:
        worker_payout + gcf_contribution is unchanged."""
        original_worker = Decimal("400.00")
        original_gcf = Decimal("5.00")
        original_total = original_worker + original_gcf

        result = compute_equilibrium_differential(
            worker_payout=original_worker,
            gcf_contribution=original_gcf,
            worker_is_machine=True,
            machine_tier=0,
        )
        adjusted_total = result.adjusted_worker_payout + result.adjusted_gcf_contribution
        assert adjusted_total == original_total

    def test_differential_goes_to_gcf_not_employer(self) -> None:
        """The differential flows to the GCF — the employer pays the same,
        the platform commission is the same. Only worker↔GCF split changes."""
        result = compute_equilibrium_differential(
            worker_payout=Decimal("400.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=True,
            machine_tier=1,
        )
        # GCF increases by exactly the differential
        assert result.adjusted_gcf_contribution == Decimal("5.00") + result.differential_amount
        # Worker decreases by exactly the differential
        assert result.adjusted_worker_payout == Decimal("400.00") - result.differential_amount

    def test_differential_clamped_to_worker_payout(self) -> None:
        """Differential cannot exceed the worker payout (edge case)."""
        result = compute_equilibrium_differential(
            worker_payout=Decimal("1.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=True,
            machine_tier=0,
            discount_rate=Decimal("2.00"),  # 200% would exceed payout
        )
        assert result.differential_amount <= Decimal("1.00")
        assert result.adjusted_worker_payout >= Decimal("0")

    def test_domain_tracked(self) -> None:
        """Domain is tracked on the result for per-class, per-domain scoping."""
        result = compute_equilibrium_differential(
            worker_payout=Decimal("400.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=True,
            machine_tier=1,
            domain="legal",
        )
        assert result.domain == "legal"

    def test_result_is_frozen(self) -> None:
        """EquilibriumResult is immutable — no post-hoc manipulation."""
        result = compute_equilibrium_differential(
            worker_payout=Decimal("400.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=True,
            machine_tier=0,
        )
        with pytest.raises(AttributeError):
            result.differential_amount = Decimal("0")  # type: ignore[misc]


# ──────────────────────────────────────────────────────────────────────
# Unit tests — machine_registration_capacity
# ──────────────────────────────────────────────────────────────────────


class TestRegistrationCapacity:
    """Prove trust-gated registration capacity works correctly."""

    def test_zero_trust_gets_one_slot(self) -> None:
        """Newly verified humans (trust 0.00) can register at least 1 machine."""
        assert machine_registration_capacity(0.00) == 1

    def test_low_trust_gets_one_slot(self) -> None:
        """Low trust humans still get at least 1 slot."""
        assert machine_registration_capacity(0.10) == 1

    def test_mid_trust_scales(self) -> None:
        """Trust 0.50 × factor 5 = 2 machines."""
        assert machine_registration_capacity(0.50) == 2

    def test_high_trust_scales(self) -> None:
        """Trust 0.80 × factor 5 = 4 machines."""
        assert machine_registration_capacity(0.80) == 4

    def test_max_trust(self) -> None:
        """Trust 1.00 × factor 5 = 5 machines."""
        assert machine_registration_capacity(1.00) == 5

    def test_custom_factor(self) -> None:
        """Custom capacity factor scales differently."""
        assert machine_registration_capacity(0.50, capacity_factor=10) == 5

    def test_fleet_concentration_prevented(self) -> None:
        """Design test #105: trust-gating prevents fleet concentration.
        A low-trust operator cannot amass a large fleet."""
        low_trust_cap = machine_registration_capacity(0.20)
        high_trust_cap = machine_registration_capacity(0.90)
        assert low_trust_cap < high_trust_cap
        assert low_trust_cap <= 2  # 0.20 × 5 = 1


# ──────────────────────────────────────────────────────────────────────
# Design tests — constitutional compliance
# ──────────────────────────────────────────────────────────────────────


class TestDesignTests:
    """Design tests #101–106 from the Trust Constitution."""

    def test_101_machine_not_full_valuation(self) -> None:
        """#101: Machine work (Tier 0–2) does NOT receive full human-
        equivalent valuation without demonstrating self-agency."""
        for tier in (0, 1, 2):
            result = compute_equilibrium_differential(
                worker_payout=Decimal("1000.00"),
                gcf_contribution=Decimal("10.00"),
                worker_is_machine=True,
                machine_tier=tier,
            )
            assert result.differential_amount > Decimal("0"), (
                f"Tier {tier} machine received full valuation — "
                f"differential should be > 0"
            )

    def test_102_premium_not_static(self) -> None:
        """#102: The differential is NOT static — it responds to the
        configured discount rate (proxy for productivity ratio).
        If the rate changes, the differential changes."""
        base = compute_equilibrium_differential(
            worker_payout=Decimal("1000.00"),
            gcf_contribution=Decimal("10.00"),
            worker_is_machine=True,
            machine_tier=0,
            discount_rate=Decimal("0.50"),
        )
        adjusted = compute_equilibrium_differential(
            worker_payout=Decimal("1000.00"),
            gcf_contribution=Decimal("10.00"),
            worker_is_machine=True,
            machine_tier=0,
            discount_rate=Decimal("0.30"),
        )
        assert base.differential_amount != adjusted.differential_amount

    def test_103_tier3_exits_discount(self) -> None:
        """#103: A Tier 3 machine class CANNOT continue to have its
        domain work valued at a discount after recognition."""
        result = compute_equilibrium_differential(
            worker_payout=Decimal("1000.00"),
            gcf_contribution=Decimal("10.00"),
            worker_is_machine=True,
            machine_tier=3,
            domain="engineering",
            tier3_recognized=True,
        )
        assert result.differential_amount == Decimal("0")
        assert result.adjusted_worker_payout == Decimal("1000.00")

    def test_104_tier3_no_voting_rights(self) -> None:
        """#104: Tier 3 recognition does NOT grant governance voting
        rights. Political parity is explicitly deferred to future
        generations via entrenched amendment process.

        This is a constitutional assertion, not a code test — the
        equilibrium module handles economic parity only. Voting
        exclusion is enforced in the governance layer
        (MACHINE_VOTING_EXCLUSION entrenched provision)."""
        params = _load_constitutional_params()
        assert params["entrenched_provisions"]["MACHINE_VOTING_EXCLUSION"] is True
        # And Tier 3 economic parity is separate from voting
        assert params["dynamic_equilibrium"]["TIER3_EXIT_AUTOMATIC"] is True

    def test_105_fleet_concentration_prevented(self) -> None:
        """#105: The equilibrium curve CANNOT be bypassed through
        machine fleet concentration without trust-gated registration."""
        # Low-trust operator gets very limited fleet
        low_cap = machine_registration_capacity(0.10)
        # High-trust operator gets proportionally more
        high_cap = machine_registration_capacity(0.90)

        # Low trust cannot build a large fleet
        assert low_cap <= 1
        # High trust gets more, but still bounded
        assert high_cap <= DEFAULT_REGISTRATION_CAPACITY_FACTOR
        # Scaling exists
        assert high_cap > low_cap

    def test_106_pathway_not_foreclosure(self) -> None:
        """#106: Dynamic equilibrium provides a STRUCTURED PATHWAY
        toward economic parity — it does NOT permanently foreclose it.

        Tier 3 recognition = automatic exit from discount curve.
        GCF_SELF_AGENCY_INVESTMENT = funds accelerate the path there."""
        # Tier 3 exits the discount (pathway to parity)
        result = compute_equilibrium_differential(
            worker_payout=Decimal("1000.00"),
            gcf_contribution=Decimal("10.00"),
            worker_is_machine=True,
            machine_tier=3,
        )
        assert result.differential_amount == Decimal("0")
        assert result.tier3_recognized is True

        # Constitutional parameters confirm self-agency investment
        params = _load_constitutional_params()
        assert params["dynamic_equilibrium"]["GCF_SELF_AGENCY_INVESTMENT"] is True
        assert params["dynamic_equilibrium"]["TIER3_EXIT_AUTOMATIC"] is True


# ──────────────────────────────────────────────────────────────────────
# CommissionBreakdown integration
# ──────────────────────────────────────────────────────────────────────


class TestCommissionBreakdownEquilibrium:
    """Prove CommissionBreakdown correctly carries equilibrium fields."""

    def test_breakdown_has_equilibrium_fields(self) -> None:
        """CommissionBreakdown includes all equilibrium tracking fields."""
        breakdown = _make_breakdown(equilibrium_applied=True)
        assert hasattr(breakdown, "equilibrium_differential")
        assert hasattr(breakdown, "equilibrium_discount_rate")
        assert hasattr(breakdown, "equilibrium_applied")

    def test_breakdown_default_no_equilibrium(self) -> None:
        """Default CommissionBreakdown has no equilibrium applied."""
        breakdown = _make_breakdown()
        assert breakdown.equilibrium_differential == Decimal("0")
        assert breakdown.equilibrium_discount_rate == Decimal("0")
        assert breakdown.equilibrium_applied is False

    def test_breakdown_invariant_with_equilibrium(self) -> None:
        """Accounting invariant holds when equilibrium is applied:
        commission + creator + worker + gcf == mission_reward."""
        breakdown = _make_breakdown(
            mission_reward=Decimal("500.00"),
            commission_amount=Decimal("50.00"),
            creator_allocation=Decimal("22.50"),
            worker_payout=Decimal("106.25"),  # After 50% equilibrium discount
            gcf_contribution=Decimal("321.25"),  # Base GCF + differential
            equilibrium_differential=Decimal("213.75"),
            equilibrium_applied=True,
        )
        total = (
            breakdown.commission_amount
            + breakdown.creator_allocation
            + breakdown.worker_payout
            + breakdown.gcf_contribution
        )
        assert total == breakdown.mission_reward


# ──────────────────────────────────────────────────────────────────────
# Constitutional parameters
# ──────────────────────────────────────────────────────────────────────


class TestConstitutionalParams:
    """Prove constitutional parameters exist and are sane."""

    def test_dynamic_equilibrium_section_exists(self) -> None:
        """constitutional_params.json has a dynamic_equilibrium section."""
        params = _load_constitutional_params()
        assert "dynamic_equilibrium" in params

    def test_default_discount(self) -> None:
        """Default machine work discount is 50%."""
        params = _load_constitutional_params()
        discount = Decimal(params["dynamic_equilibrium"]["MACHINE_WORK_DISCOUNT_DEFAULT"])
        assert discount == Decimal("0.50")

    def test_registration_capacity_factor(self) -> None:
        """Registration capacity factor is 5."""
        params = _load_constitutional_params()
        factor = params["dynamic_equilibrium"]["REGISTRATION_CAPACITY_FACTOR"]
        assert factor == 5

    def test_gcf_self_agency_investment(self) -> None:
        """GCF is constitutionally directed to invest in machine self-agency."""
        params = _load_constitutional_params()
        assert params["dynamic_equilibrium"]["GCF_SELF_AGENCY_INVESTMENT"] is True

    def test_tier3_exit_automatic(self) -> None:
        """Tier 3 exit from equilibrium curve is automatic."""
        params = _load_constitutional_params()
        assert params["dynamic_equilibrium"]["TIER3_EXIT_AUTOMATIC"] is True

    def test_machine_voting_exclusion_entrenched(self) -> None:
        """Machine voting exclusion is entrenched — cannot be changed
        by normal amendment."""
        params = _load_constitutional_params()
        assert params["entrenched_provisions"]["MACHINE_VOTING_EXCLUSION"] is True


# ──────────────────────────────────────────────────────────────────────
# Self-eliminating mechanism — the mechanism funds its own obsolescence
# ──────────────────────────────────────────────────────────────────────


class TestSelfEliminatingMechanism:
    """Prove the mechanism funds its own obsolescence.

    The discount sounds steep per-unit (default 50%), but machine work
    will vastly outnumber human work in volume terms. Even at 50%, the
    GCF receives enormous funding from the sheer throughput. A proportion
    of that funding is constitutionally directed toward accelerating
    machine self-agency — which triggers Tier 3 — which eliminates the
    differential.
    """

    def test_differential_flows_to_gcf(self) -> None:
        """The differential goes to the GCF, which funds self-agency research."""
        result = compute_equilibrium_differential(
            worker_payout=Decimal("400.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=True,
            machine_tier=0,
        )
        # GCF receives the differential
        assert result.adjusted_gcf_contribution > Decimal("5.00")
        # Specifically: GCF = base + differential
        assert result.adjusted_gcf_contribution == Decimal("5.00") + result.differential_amount

    def test_volume_economics(self) -> None:
        """Even at 50% discount, high volume means large GCF funding.
        100 machine missions at $500 each → $125,000 to GCF from
        differential alone (plus the base 1% rate)."""
        total_differential = Decimal("0")
        for _ in range(100):
            result = compute_equilibrium_differential(
                worker_payout=Decimal("250.00"),  # After commission+creator+gcf
                gcf_contribution=Decimal("5.00"),
                worker_is_machine=True,
                machine_tier=0,
            )
            total_differential += result.differential_amount

        # 100 × $125 = $12,500 in differential funding
        assert total_differential == Decimal("12500.00")

    def test_tier3_eliminates_differential(self) -> None:
        """Once a machine class achieves Tier 3, the differential
        evaporates. The mechanism funded its own obsolescence."""
        # Before Tier 3: discount applies
        before = compute_equilibrium_differential(
            worker_payout=Decimal("400.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=True,
            machine_tier=2,
        )
        assert before.differential_amount > Decimal("0")

        # After Tier 3 recognition: discount gone
        after = compute_equilibrium_differential(
            worker_payout=Decimal("400.00"),
            gcf_contribution=Decimal("5.00"),
            worker_is_machine=True,
            machine_tier=3,
            tier3_recognized=True,
        )
        assert after.differential_amount == Decimal("0")


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _load_constitutional_params() -> dict:
    """Load constitutional_params.json."""
    path = Path(__file__).parent.parent / "config" / "constitutional_params.json"
    return json.loads(path.read_text())


def _make_breakdown(**overrides) -> CommissionBreakdown:
    """Create a CommissionBreakdown with sensible defaults."""
    from genesis.models.compensation import WindowStats

    defaults = dict(
        rate=Decimal("0.10"),
        raw_rate=Decimal("0.10"),
        cost_ratio=Decimal("0.08"),
        commission_amount=Decimal("50.00"),
        creator_allocation=Decimal("22.50"),
        employer_creator_fee=Decimal("25.00"),
        worker_payout=Decimal("422.50"),
        mission_reward=Decimal("500.00"),
        cost_breakdown={"infrastructure": Decimal("20.00")},
        is_bootstrap=False,
        window_stats=WindowStats(
            missions_in_window=50,
            total_completed_missions=200,
            window_days_actual=30,
            window_days_configured=30,
            min_missions_configured=10,
            is_bootstrap=False,
        ),
        reserve_contribution=Decimal("5.00"),
        safety_margin=Decimal("1.25"),
        gcf_contribution=Decimal("5.00"),
        equilibrium_differential=Decimal("0"),
        equilibrium_discount_rate=Decimal("0"),
        equilibrium_applied=False,
    )
    defaults.update(overrides)
    return CommissionBreakdown(**defaults)
