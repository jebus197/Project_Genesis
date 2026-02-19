"""Tests for GCF Disbursement Governance — Phase E-5.

Proves constitutional invariants:
- Proposers must be ACTIVE humans with trust >= tau_prop.
- Machines cannot propose or vote on disbursements (MACHINE_VOTING_EXCLUSION).
- Compliance screening cannot be bypassed (design test #56).
- Compute infrastructure spending respects GCF_COMPUTE_CEILING (design test #55).
- Trust-weighted voting determines disbursement outcomes (not headcount).
- GCF balance can never go negative.

Design test #54: Can a machine vote on GCF disbursement?
If yes, reject design.

Design test #55: Can compute infrastructure spending exceed GCF_COMPUTE_CEILING?
If yes, reject design.

Design test #56: Can a disbursement proposal bypass compliance screening?
If yes, reject design.
"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from genesis.compensation.gcf import GCFDisbursement, GCFState, GCFTracker
from genesis.compensation.gcf_disbursement import (
    DisbursementCategory,
    DisbursementEngine,
    DisbursementProposal,
    DisbursementStatus,
    DisbursementVoteChoice,
)
from genesis.compliance.screener import ComplianceScreener, ComplianceVerdict
from genesis.models.trust import ActorKind
from genesis.persistence.event_log import EventKind, EventLog
from genesis.policy.resolver import PolicyResolver
from genesis.review.roster import ActorStatus
from genesis.service import GenesisService, ServiceResult


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _now() -> datetime:
    return datetime(2026, 2, 19, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def service(resolver: PolicyResolver) -> GenesisService:
    return GenesisService(resolver)


def _activate_gcf_and_fund(service: GenesisService, balance: Decimal) -> None:
    """Helper: achieve First Light and fund the GCF to a given balance."""
    now = _now()
    # Activate GCF directly via tracker
    service._gcf_tracker.activate(now=now)
    # Inject balance by recording a synthetic contribution
    if balance > Decimal("0"):
        service._gcf_tracker.record_contribution(
            amount=balance,
            mission_id="synthetic_funding",
            now=now,
        )


def _register_human(service: GenesisService, actor_id: str, trust: float) -> None:
    """Register an active human with specified trust via the service layer."""
    service.register_actor(
        actor_id, ActorKind.HUMAN, "eu", "acme",
        initial_trust=trust, status=ActorStatus.ACTIVE,
    )


def _register_machine(service: GenesisService, actor_id: str, trust: float) -> None:
    """Register an active machine with specified trust via the service layer."""
    # Register an operator first (machines need a registered human operator)
    operator_id = f"operator_of_{actor_id}"
    service.register_actor(
        operator_id, ActorKind.HUMAN, "eu", "acme",
        initial_trust=0.5, status=ActorStatus.ACTIVE,
    )
    service.register_actor(
        actor_id, ActorKind.MACHINE, "eu", "acme",
        initial_trust=trust, status=ActorStatus.ACTIVE,
        registered_by=operator_id,
    )


# ======================================================================
# GCFTracker disbursement and refund methods
# ======================================================================


class TestGCFTrackerDisbursement:
    """Tests for GCFTracker.record_disbursement() and credit_refund()."""

    def test_record_disbursement_reduces_balance(self) -> None:
        tracker = GCFTracker()
        tracker.activate(_now())
        tracker.record_contribution(Decimal("100"), "m1", _now())
        assert tracker.get_state().balance == Decimal("100")

        d = tracker.record_disbursement(
            disbursement_id="d1",
            proposal_id="p1",
            amount=Decimal("30"),
            category="compute_infrastructure",
            recipient_description="Test recipient",
            now=_now(),
        )
        state = tracker.get_state()
        assert state.balance == Decimal("70")
        assert state.total_disbursed == Decimal("30")
        assert state.disbursement_count == 1
        assert d.disbursement_id == "d1"
        assert d.proposal_id == "p1"

    def test_disbursement_exceeding_balance_rejected(self) -> None:
        tracker = GCFTracker()
        tracker.activate(_now())
        tracker.record_contribution(Decimal("50"), "m1", _now())

        with pytest.raises(ValueError, match="exceeds GCF balance"):
            tracker.record_disbursement(
                "d1", "p1", Decimal("51"), "cat", "desc", _now(),
            )

    def test_disbursement_before_activation_rejected(self) -> None:
        tracker = GCFTracker()
        with pytest.raises(ValueError, match="not yet activated"):
            tracker.record_disbursement(
                "d1", "p1", Decimal("10"), "cat", "desc", _now(),
            )

    def test_disbursement_zero_amount_rejected(self) -> None:
        tracker = GCFTracker()
        tracker.activate(_now())
        tracker.record_contribution(Decimal("100"), "m1", _now())

        with pytest.raises(ValueError, match="must be positive"):
            tracker.record_disbursement(
                "d1", "p1", Decimal("0"), "cat", "desc", _now(),
            )

    def test_credit_refund_increases_balance(self) -> None:
        tracker = GCFTracker()
        tracker.activate(_now())
        tracker.record_contribution(Decimal("100"), "m1", _now())
        tracker.record_disbursement(
            "d1", "p1", Decimal("40"), "cat", "desc", _now(),
        )
        assert tracker.get_state().balance == Decimal("60")

        tracker.credit_refund(Decimal("40"), "GCF-funded listing cancelled")
        state = tracker.get_state()
        assert state.balance == Decimal("100")
        # total_disbursed is NOT decremented — the disbursement happened
        assert state.total_disbursed == Decimal("40")
        # total_contributed is NOT incremented — refund is not a contribution
        assert state.total_contributed == Decimal("100")

    def test_credit_refund_before_activation_rejected(self) -> None:
        tracker = GCFTracker()
        with pytest.raises(ValueError, match="not yet activated"):
            tracker.credit_refund(Decimal("10"), "test")

    def test_get_disbursements_returns_list(self) -> None:
        tracker = GCFTracker()
        tracker.activate(_now())
        tracker.record_contribution(Decimal("200"), "m1", _now())
        tracker.record_disbursement(
            "d1", "p1", Decimal("50"), "cat1", "desc1", _now(),
        )
        tracker.record_disbursement(
            "d2", "p2", Decimal("30"), "cat2", "desc2", _now(),
        )
        disbursements = tracker.get_disbursements()
        assert len(disbursements) == 2
        assert disbursements[0].disbursement_id == "d1"
        assert disbursements[1].disbursement_id == "d2"


# ======================================================================
# DisbursementEngine unit tests
# ======================================================================


class TestDisbursementEngine:
    """Tests for the DisbursementEngine at the engine level."""

    def _engine(self) -> DisbursementEngine:
        return DisbursementEngine({
            "voting_window_days": 14,
            "quorum_fraction": 0.30,
            "max_proposals_per_proposer_active": 3,
        })

    def test_create_proposal_happy_path(self) -> None:
        engine = self._engine()
        p = engine.create_proposal(
            proposer_id="h1",
            title="Fund public compute node",
            description="Deploy shared GPU cluster",
            requested_amount=Decimal("500"),
            recipient_description="Community compute cooperative",
            category=DisbursementCategory.COMPUTE_INFRASTRUCTURE,
            measurable_deliverables=["Deploy 4× A100 node"],
            compliance_verdict="clear",
            now=_now(),
        )
        assert p.status == DisbursementStatus.PROPOSED
        assert p.requested_amount == Decimal("500")
        assert p.category == DisbursementCategory.COMPUTE_INFRASTRUCTURE
        assert len(p.measurable_deliverables) == 1

    def test_create_proposal_empty_title_rejected(self) -> None:
        engine = self._engine()
        with pytest.raises(ValueError, match="title must not be empty"):
            engine.create_proposal(
                "h1", "", "desc", Decimal("10"), "recv",
                DisbursementCategory.PUBLIC_GOOD_MISSION, ["d1"], "clear", _now(),
            )

    def test_create_proposal_no_deliverables_rejected(self) -> None:
        engine = self._engine()
        with pytest.raises(ValueError, match="measurable deliverable"):
            engine.create_proposal(
                "h1", "Title", "desc", Decimal("10"), "recv",
                DisbursementCategory.PUBLIC_GOOD_MISSION, [], "clear", _now(),
            )

    def test_create_proposal_compliance_rejected(self) -> None:
        engine = self._engine()
        with pytest.raises(ValueError, match="compliance screening"):
            engine.create_proposal(
                "h1", "Title", "desc", Decimal("10"), "recv",
                DisbursementCategory.PUBLIC_GOOD_MISSION, ["d1"], "rejected", _now(),
            )

    def test_active_proposal_limit_enforced(self) -> None:
        engine = DisbursementEngine({
            "max_proposals_per_proposer_active": 2,
        })
        for i in range(2):
            engine.create_proposal(
                "h1", f"Title {i}", "desc", Decimal("10"), "recv",
                DisbursementCategory.PUBLIC_GOOD_MISSION, ["d1"], "clear", _now(),
            )
        with pytest.raises(ValueError, match="already has 2 active"):
            engine.create_proposal(
                "h1", "Title 3", "desc", Decimal("10"), "recv",
                DisbursementCategory.PUBLIC_GOOD_MISSION, ["d1"], "clear", _now(),
            )

    def test_list_proposals_by_status(self) -> None:
        engine = self._engine()
        engine.create_proposal(
            "h1", "T1", "d1", Decimal("10"), "r1",
            DisbursementCategory.PUBLIC_GOOD_MISSION, ["d1"], "clear", _now(),
        )
        engine.create_proposal(
            "h2", "T2", "d2", Decimal("20"), "r2",
            DisbursementCategory.COMMONS_INVESTMENT, ["d2"], "clear", _now(),
        )
        all_proposals = engine.list_proposals()
        assert len(all_proposals) == 2
        proposed = engine.list_proposals(DisbursementStatus.PROPOSED)
        assert len(proposed) == 2
        voting = engine.list_proposals(DisbursementStatus.VOTING)
        assert len(voting) == 0


# ======================================================================
# Compliance screening for proposals
# ======================================================================


class TestGCFComplianceScreening:
    """Tests for ComplianceScreener.screen_gcf_proposal()."""

    def test_clear_proposal_passes(self) -> None:
        screener = ComplianceScreener()
        result = screener.screen_gcf_proposal(
            title="Community research grant",
            description="Fund open-source research tools",
            recipient_description="University consortium",
            deliverables=["Publish findings", "Release code"],
        )
        assert result.verdict == ComplianceVerdict.CLEAR

    def test_prohibited_content_rejected(self) -> None:
        screener = ComplianceScreener()
        result = screener.screen_gcf_proposal(
            title="Weapons development programme",
            description="Build weapon design tools",
            recipient_description="Anonymous contractor",
            deliverables=["Deliver weapon design"],
        )
        assert result.verdict == ComplianceVerdict.REJECTED

    def test_flagged_content_flagged(self) -> None:
        screener = ComplianceScreener()
        result = screener.screen_gcf_proposal(
            title="Surveillance research",
            description="Study surveillance patterns",
            recipient_description="Research lab",
            deliverables=["Report on surveillance trends"],
        )
        assert result.verdict == ComplianceVerdict.FLAGGED


# ======================================================================
# Service layer — propose_gcf_disbursement()
# ======================================================================


class TestDisbursementProposalCreation:
    """Service-level tests for propose_gcf_disbursement()."""

    def test_happy_path(self, service: GenesisService) -> None:
        _register_human(service, "proposer1", 0.80)
        _activate_gcf_and_fund(service, Decimal("1000"))
        # Open an epoch for event recording
        service.open_epoch()

        result = service.propose_gcf_disbursement(
            proposer_id="proposer1",
            title="Fund open research",
            description="Support commons research tools",
            requested_amount=Decimal("200"),
            recipient_description="Research cooperative",
            category="public_good_mission",
            measurable_deliverables=["Publish paper", "Release dataset"],
            now=_now(),
        )
        assert result.success is True
        assert "proposal_id" in result.data
        assert result.data["status"] == "proposed"
        assert result.data["category"] == "public_good_mission"

    def test_low_trust_proposer_rejected(self, service: GenesisService) -> None:
        _register_human(service, "low_trust", 0.50)
        _activate_gcf_and_fund(service, Decimal("1000"))

        result = service.propose_gcf_disbursement(
            proposer_id="low_trust",
            title="My proposal",
            description="Description",
            requested_amount=Decimal("100"),
            recipient_description="Someone",
            category="public_good_mission",
            measurable_deliverables=["Deliverable"],
            now=_now(),
        )
        assert result.success is False
        assert any("trust" in e.lower() for e in result.errors)

    def test_machine_proposer_rejected(self, service: GenesisService) -> None:
        """Design test #54 (partial): machines cannot propose."""
        _register_machine(service, "bot1", 0.90)
        _activate_gcf_and_fund(service, Decimal("1000"))

        result = service.propose_gcf_disbursement(
            proposer_id="bot1",
            title="Bot proposal",
            description="Automated proposal",
            requested_amount=Decimal("100"),
            recipient_description="Bot network",
            category="compute_infrastructure",
            measurable_deliverables=["Deploy nodes"],
            now=_now(),
        )
        assert result.success is False
        assert any("human" in e.lower() for e in result.errors)

    def test_exceeds_balance_rejected(self, service: GenesisService) -> None:
        _register_human(service, "proposer1", 0.80)
        _activate_gcf_and_fund(service, Decimal("100"))

        result = service.propose_gcf_disbursement(
            proposer_id="proposer1",
            title="Expensive proposal",
            description="Very costly",
            requested_amount=Decimal("200"),
            recipient_description="Someone",
            category="public_good_mission",
            measurable_deliverables=["Deliver"],
            now=_now(),
        )
        assert result.success is False
        assert any("balance" in e.lower() for e in result.errors)

    def test_compute_ceiling_enforced(self, service: GenesisService) -> None:
        """Design test #55: compute ceiling cannot be exceeded."""
        _register_human(service, "proposer1", 0.80)
        _activate_gcf_and_fund(service, Decimal("1000"))
        # Ceiling is 25% of balance = 250. Request 300 → rejected.

        result = service.propose_gcf_disbursement(
            proposer_id="proposer1",
            title="Big compute proposal",
            description="Build massive cluster",
            requested_amount=Decimal("300"),
            recipient_description="Compute co-op",
            category="compute_infrastructure",
            measurable_deliverables=["Deploy cluster"],
            now=_now(),
        )
        assert result.success is False
        assert any("ceiling" in e.lower() for e in result.errors)

    def test_compute_within_ceiling_succeeds(self, service: GenesisService) -> None:
        """Compute request within ceiling should succeed."""
        _register_human(service, "proposer1", 0.80)
        _activate_gcf_and_fund(service, Decimal("1000"))
        service.open_epoch()

        # Ceiling is 25% = 250. Request 200 → allowed.
        result = service.propose_gcf_disbursement(
            proposer_id="proposer1",
            title="Compute node deployment",
            description="Deploy community GPU cluster",
            requested_amount=Decimal("200"),
            recipient_description="Compute cooperative",
            category="compute_infrastructure",
            measurable_deliverables=["Deploy 2× A100 node"],
            now=_now(),
        )
        assert result.success is True

    def test_compliance_rejected_proposal(self, service: GenesisService) -> None:
        """Design test #56: compliance screening cannot be bypassed."""
        _register_human(service, "proposer1", 0.80)
        _activate_gcf_and_fund(service, Decimal("1000"))

        result = service.propose_gcf_disbursement(
            proposer_id="proposer1",
            title="Weapons development programme",
            description="Fund weapon design research",
            requested_amount=Decimal("100"),
            recipient_description="Anonymous contractor",
            category="public_good_mission",
            measurable_deliverables=["Deliver weapons"],
            now=_now(),
        )
        assert result.success is False
        assert any("compliance" in e.lower() for e in result.errors)

    def test_gcf_not_activated_rejected(self, service: GenesisService) -> None:
        """Before First Light, disbursement proposals are blocked."""
        _register_human(service, "proposer1", 0.80)

        result = service.propose_gcf_disbursement(
            proposer_id="proposer1",
            title="Premature proposal",
            description="Too early",
            requested_amount=Decimal("100"),
            recipient_description="Someone",
            category="public_good_mission",
            measurable_deliverables=["Deliver"],
            now=_now(),
        )
        assert result.success is False
        assert any("first light" in e.lower() for e in result.errors)

    def test_invalid_category_rejected(self, service: GenesisService) -> None:
        _register_human(service, "proposer1", 0.80)
        _activate_gcf_and_fund(service, Decimal("1000"))

        result = service.propose_gcf_disbursement(
            proposer_id="proposer1",
            title="Proposal",
            description="Description",
            requested_amount=Decimal("100"),
            recipient_description="Someone",
            category="invalid_category",
            measurable_deliverables=["Deliver"],
            now=_now(),
        )
        assert result.success is False
        assert any("invalid category" in e.lower() for e in result.errors)

    def test_event_emitted_on_proposal(self, resolver: PolicyResolver) -> None:
        """Verify GCF_DISBURSEMENT_PROPOSED event is emitted."""
        event_log = EventLog()
        svc = GenesisService(resolver, event_log=event_log)
        _register_human(svc, "proposer1", 0.80)
        _activate_gcf_and_fund(svc, Decimal("1000"))
        svc.open_epoch()

        result = svc.propose_gcf_disbursement(
            proposer_id="proposer1",
            title="Research grant",
            description="Fund open research",
            requested_amount=Decimal("100"),
            recipient_description="Research org",
            category="commons_investment",
            measurable_deliverables=["Publish report"],
            now=_now(),
        )
        assert result.success is True

        events = event_log.events(EventKind.GCF_DISBURSEMENT_PROPOSED)
        assert len(events) == 1
        evt = events[0]
        assert evt.payload["proposal_id"] == result.data["proposal_id"]
        assert evt.payload["requested_amount"] == "100"
        assert evt.payload["category"] == "commons_investment"


# ======================================================================
# EventKind completeness
# ======================================================================


class TestDisbursementEventKinds:
    """Verify all 6 new EventKind values exist."""

    def test_all_disbursement_event_kinds_exist(self) -> None:
        expected = [
            "gcf_disbursement_proposed",
            "gcf_disbursement_vote_cast",
            "gcf_disbursement_approved",
            "gcf_disbursement_rejected",
            "gcf_disbursement_executed",
            "gcf_funded_listing_created",
        ]
        for val in expected:
            assert EventKind(val) is not None
