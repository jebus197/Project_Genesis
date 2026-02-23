"""Tests for Constitutional Amendment Engine — Phase E-6.

Proves constitutional invariants:
- Proposers must be ACTIVE humans with trust >= tau_prop.
- Machines cannot propose or vote on amendments.
- Commission rates are formula-determined, not ballot-amendable (design test #59).
- Entrenched amendments require 80% supermajority + 50% participation +
  90-day cooling-off + confirmation vote (design test #58).
- Non-entrenched amendments skip cooling-off and confirmation (design test #57).
- The cooling-off period cannot be shortened without its own entrenched process
  (design test #60).

Design test #57: Can a non-entrenched amendment bypass chamber voting?
If yes, reject design.

Design test #58: Can an entrenched amendment skip the 90-day cooling-off?
If yes, reject design.

Design test #59: Can a commission rate be changed by ballot?
If yes, reject design.

Design test #60: Can the cooling-off period be shortened without going through
its own entrenched process? If yes, reject design.
"""

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from genesis.governance.amendment import (
    AmendmentEngine,
    AmendmentProposal,
    AmendmentStatus,
    AmendmentVote,
    ConstitutionalViolation,
    FORMULA_ONLY_PARAMS,
)
from genesis.models.governance import Chamber, ChamberKind, GenesisPhase
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


@pytest.fixture
def engine(resolver: PolicyResolver) -> AmendmentEngine:
    return AmendmentEngine(
        resolver.amendment_config(),
        resolver._params,
    )


def _register_human(service: GenesisService, actor_id: str, trust: float,
                     region: str = "eu", org: str = "acme") -> None:
    """Register an active human with specified trust via the service layer."""
    service.register_actor(
        actor_id, ActorKind.HUMAN, region, org,
        initial_trust=trust, status=ActorStatus.ACTIVE,
    )


def _register_machine(service: GenesisService, actor_id: str, trust: float) -> None:
    """Register an active machine with specified trust via the service layer."""
    operator_id = f"operator_of_{actor_id}"
    service.register_actor(
        operator_id, ActorKind.HUMAN, "eu", "acme",
        initial_trust=0.5, status=ActorStatus.ACTIVE,
    )
    service.register_machine(
        actor_id=actor_id,
        operator_id=operator_id,
        region="eu",
        organization="acme",
        model_family="gpt",
        method_type="reasoning_model",
    )


# =====================================================================
# E-6a: Amendment Proposal Creation
# =====================================================================

class TestAmendmentProposalCreation:
    """Engine-level tests for create_amendment()."""

    def test_happy_path_entrenched(self, engine: AmendmentEngine) -> None:
        """Creating an amendment targeting an entrenched provision sets is_entrenched=True."""
        proposal = engine.create_amendment(
            proposer_id="h1",
            provision_key="GCF_CONTRIBUTION_RATE",
            current_value="0.01",
            proposed_value="0.02",
            justification="Double the commons contribution",
            now=_now(),
        )
        assert proposal.is_entrenched is True
        assert proposal.status == AmendmentStatus.PROPOSED
        assert proposal.provision_key == "GCF_CONTRIBUTION_RATE"
        assert proposal.proposed_value == "0.02"
        assert proposal.proposer_id == "h1"
        assert proposal.created_utc == _now()

    def test_happy_path_non_entrenched(self, engine: AmendmentEngine) -> None:
        """Creating an amendment targeting a non-entrenched provision sets is_entrenched=False."""
        proposal = engine.create_amendment(
            proposer_id="h1",
            provision_key="gcf_compute.GCF_COMPUTE_CEILING",
            current_value="0.25",
            proposed_value="0.30",
            justification="Increase compute ceiling",
            now=_now(),
        )
        assert proposal.is_entrenched is False
        assert proposal.status == AmendmentStatus.PROPOSED

    def test_is_entrenched_auto_detection(self, engine: AmendmentEngine) -> None:
        """Engine auto-detects entrenched provisions from constitutional_params."""
        assert engine.is_provision_entrenched("GCF_CONTRIBUTION_RATE") is True
        assert engine.is_provision_entrenched("TRUST_FLOOR_H_POSITIVE") is True
        assert engine.is_provision_entrenched("NO_BUY_TRUST") is True
        assert engine.is_provision_entrenched("MACHINE_VOTING_EXCLUSION") is True
        # Non-entrenched
        assert engine.is_provision_entrenched("gcf_compute.GCF_COMPUTE_CEILING") is False
        assert engine.is_provision_entrenched("random_key") is False

    def test_empty_justification_rejected(self, engine: AmendmentEngine) -> None:
        """Empty justification is rejected."""
        with pytest.raises(ValueError, match="justification must not be empty"):
            engine.create_amendment(
                proposer_id="h1",
                provision_key="GCF_CONTRIBUTION_RATE",
                current_value="0.01",
                proposed_value="0.02",
                justification="  ",
                now=_now(),
            )

    def test_commission_rate_rejected(self, engine: AmendmentEngine) -> None:
        """Commission rate parameters cannot be amended by ballot (design test #59)."""
        for param in FORMULA_ONLY_PARAMS:
            with pytest.raises(ValueError, match="formula-determined"):
                engine.create_amendment(
                    proposer_id="h1",
                    provision_key=param,
                    current_value="0.10",
                    proposed_value="0.15",
                    justification="Adjust commission",
                    now=_now(),
                )

    def test_list_amendments(self, engine: AmendmentEngine) -> None:
        """list_amendments returns all or filtered by status."""
        engine.create_amendment("h1", "GCF_CONTRIBUTION_RATE", "0.01", "0.02",
                                "Test", now=_now())
        engine.create_amendment("h2", "NO_BUY_TRUST", True, True,
                                "Test 2", now=_now())
        assert len(engine.list_amendments()) == 2
        assert len(engine.list_amendments(AmendmentStatus.PROPOSED)) == 2
        assert len(engine.list_amendments(AmendmentStatus.CONFIRMED)) == 0

    def test_get_amendment(self, engine: AmendmentEngine) -> None:
        """get_amendment retrieves by ID."""
        proposal = engine.create_amendment("h1", "NO_BUY_TRUST", True, True,
                                           "Test", now=_now())
        fetched = engine.get_amendment(proposal.proposal_id)
        assert fetched is not None
        assert fetched.proposal_id == proposal.proposal_id
        assert engine.get_amendment("nonexistent") is None


class TestAmendmentProposalService:
    """Service-level tests for propose_amendment()."""

    def test_happy_path(self, service: GenesisService) -> None:
        """propose_amendment succeeds for high-trust active human."""
        _register_human(service, "proposer1", 0.80)
        service.open_epoch()

        result = service.propose_amendment(
            proposer_id="proposer1",
            provision_key="GCF_CONTRIBUTION_RATE",
            proposed_value="0.02",
            justification="Increase commons funding",
            now=_now(),
        )
        assert result.success is True
        assert result.data["is_entrenched"] is True
        assert result.data["status"] == "proposed"

    def test_low_trust_rejected(self, service: GenesisService) -> None:
        """Proposer with trust below tau_prop (0.75) is rejected."""
        _register_human(service, "low_trust", 0.50)
        service.open_epoch()

        result = service.propose_amendment(
            proposer_id="low_trust",
            provision_key="GCF_CONTRIBUTION_RATE",
            proposed_value="0.02",
            justification="Increase commons funding",
            now=_now(),
        )
        assert result.success is False
        assert "below threshold" in result.errors[0]

    def test_inactive_actor_rejected(self, service: GenesisService) -> None:
        """Inactive actor cannot propose amendments."""
        _register_human(service, "inactive1", 0.80)
        # Suspend the actor
        service._roster.get("inactive1").status = ActorStatus.SUSPENDED
        service.open_epoch()

        result = service.propose_amendment(
            proposer_id="inactive1",
            provision_key="GCF_CONTRIBUTION_RATE",
            proposed_value="0.02",
            justification="Increase commons funding",
            now=_now(),
        )
        assert result.success is False
        assert "not ACTIVE" in result.errors[0]

    def test_machine_proposer_rejected(self, service: GenesisService) -> None:
        """Machines cannot propose constitutional amendments."""
        _register_machine(service, "bot1", 0.80)
        service.open_epoch()

        result = service.propose_amendment(
            proposer_id="bot1",
            provision_key="GCF_CONTRIBUTION_RATE",
            proposed_value="0.02",
            justification="Increase commons funding",
            now=_now(),
        )
        assert result.success is False
        assert "Only humans" in result.errors[0]

    def test_event_emitted(self, service: GenesisService) -> None:
        """propose_amendment emits AMENDMENT_PROPOSED event."""
        _register_human(service, "proposer1", 0.80)
        event_log = EventLog()
        service._event_log = event_log
        service.open_epoch()

        result = service.propose_amendment(
            proposer_id="proposer1",
            provision_key="NO_BUY_TRUST",
            proposed_value=True,
            justification="Reaffirm no-buy-trust principle",
            now=_now(),
        )
        assert result.success is True
        events = event_log.events(EventKind.AMENDMENT_PROPOSED)
        assert len(events) == 1
        assert events[0].payload["is_entrenched"] is True

    def test_commission_rate_rejected_at_service(self, service: GenesisService) -> None:
        """Commission rate amendment is rejected at service level."""
        _register_human(service, "proposer1", 0.80)
        service.open_epoch()

        result = service.propose_amendment(
            proposer_id="proposer1",
            provision_key="commission_floor",
            proposed_value="0.15",
            justification="Lower floor",
            now=_now(),
        )
        assert result.success is False
        assert "formula-determined" in result.errors[0]


class TestResolverAmendmentConfig:
    """Tests for PolicyResolver amendment config accessors."""

    def test_amendment_config(self, resolver: PolicyResolver) -> None:
        """amendment_config() returns correct values from constitutional_params."""
        cfg = resolver.amendment_config()
        assert cfg["entrenched_amendment_threshold"] == 0.80
        assert cfg["entrenched_participation_minimum"] == 0.50
        assert cfg["entrenched_cooling_off_days"] == 90
        assert cfg["entrenched_confirmation_vote_required"] is True

    def test_entrenched_provision_keys(self, resolver: PolicyResolver) -> None:
        """entrenched_provision_keys() returns all entrenched provisions.

        Original 4 + 4 payment sovereignty provisions = 8 total.
        """
        keys = resolver.entrenched_provision_keys()
        # Original 4 entrenched provisions
        assert "GCF_CONTRIBUTION_RATE" in keys
        assert "TRUST_FLOOR_H_POSITIVE" in keys
        assert "NO_BUY_TRUST" in keys
        assert "MACHINE_VOTING_EXCLUSION" in keys
        # Payment sovereignty provisions (entrenched)
        assert "MINIMUM_INDEPENDENT_PAYMENT_RAILS" in keys
        assert "MINIMUM_INDEPENDENT_PAYMENT_RAILS_AT_FIRST_LIGHT" in keys
        assert "PAYMENT_RAIL_MIGRATION_DAYS" in keys
        assert "PAYMENT_SOVEREIGNTY" in keys
        assert len(keys) == 8


# =====================================================================
# E-6b: Chamber Panel Selection + Voting
# =====================================================================

def _make_eligible_voters(count: int, regions: list[str] | None = None) -> list[dict[str, Any]]:
    """Create a list of eligible voter dicts for panel selection."""
    if regions is None:
        # Default: spread across many regions
        base_regions = ["eu", "na", "ap", "af", "sa", "me", "oc", "ea"]
        regions = [base_regions[i % len(base_regions)] for i in range(count)]
    orgs = [f"org_{i % 5}" for i in range(count)]
    return [
        {"actor_id": f"v_{i}", "region": regions[i], "organization": orgs[i]}
        for i in range(count)
    ]


class TestChamberPanelSelection:
    """Engine-level tests for select_chamber_panel()."""

    def test_phase_appropriate_sizes_g1(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """G1 proposal chamber selects 11 members."""
        proposal = engine.create_amendment("h1", "NO_BUY_TRUST", True, True,
                                           "Test", now=_now())
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)
        eligible = _make_eligible_voters(50)

        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )
        assert len(panel) == 11
        assert proposal.status == AmendmentStatus.PROPOSAL_CHAMBER_VOTING

    def test_geographic_diversity_enforced(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Panel selection fails if not enough regions are available."""
        proposal = engine.create_amendment("h1", "NO_BUY_TRUST", True, True,
                                           "Test", now=_now())
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)

        # Only 2 regions when G1 needs R_min=3
        eligible = _make_eligible_voters(50, ["eu"] * 25 + ["na"] * 25)

        with pytest.raises(ValueError, match="regional diversity"):
            engine.select_chamber_panel(
                proposal.proposal_id, ChamberKind.PROPOSAL,
                eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
            )

    def test_non_overlap_between_chambers(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """No voter can serve in more than one chamber for the same amendment."""
        proposal = engine.create_amendment("h1", "NO_BUY_TRUST", True, True,
                                           "Test", now=_now())
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)
        eligible = _make_eligible_voters(100)

        # Select proposal panel (11 members)
        proposal_panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )

        # Manually pass proposal chamber to enable ratification
        # First fill in enough yes votes and close
        for vid in proposal_panel:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.PROPOSAL,
                True, "I approve", "eu", "org_0", _now(),
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            chambers[ChamberKind.PROPOSAL], _now(),
        )

        # Select ratification panel (17 members)
        ratif_panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            eligible, chambers[ChamberKind.RATIFICATION], r_min, c_max, _now(),
        )

        # Verify no overlap
        overlap = set(proposal_panel) & set(ratif_panel)
        assert len(overlap) == 0

    def test_insufficient_candidates(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Panel selection fails with too few eligible voters."""
        proposal = engine.create_amendment("h1", "NO_BUY_TRUST", True, True,
                                           "Test", now=_now())
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)
        # G1 proposal needs 11, provide only 5
        eligible = _make_eligible_voters(5)

        with pytest.raises(ValueError, match="Not enough eligible"):
            engine.select_chamber_panel(
                proposal.proposal_id, ChamberKind.PROPOSAL,
                eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
            )

    def test_wrong_status_rejected(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Cannot select proposal panel if not in PROPOSED status."""
        proposal = engine.create_amendment("h1", "NO_BUY_TRUST", True, True,
                                           "Test", now=_now())
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)
        eligible = _make_eligible_voters(50)

        # Select proposal panel (moves to PROPOSAL_CHAMBER_VOTING)
        engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )

        # Try to select proposal panel again — should fail
        with pytest.raises(ValueError, match="Cannot select proposal panel"):
            engine.select_chamber_panel(
                proposal.proposal_id, ChamberKind.PROPOSAL,
                eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
            )

    def test_c_max_enforced(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """c_max concentration limit prevents over-representation from one region."""
        proposal = engine.create_amendment("h1", "NO_BUY_TRUST", True, True,
                                           "Test", now=_now())
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)

        # G1: c_max=0.40, panel size=11 → max 4 per region
        # Provide 3 regions with exactly enough, but one region dominates
        regions = (["eu"] * 3 + ["na"] * 3 + ["ap"] * 3 +
                   ["af"] * 1 + ["sa"] * 1)
        eligible = _make_eligible_voters(11, regions)

        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )
        # Check no region has more than c_max * panel_size
        region_counts: dict[str, int] = {}
        for pid in panel:
            for v in eligible:
                if v["actor_id"] == pid:
                    region_counts[v["region"]] = region_counts.get(v["region"], 0) + 1
        max_per_region = max(1, int(11 * c_max))  # 4
        for count in region_counts.values():
            assert count <= max_per_region


class TestChamberVoting:
    """Engine-level tests for cast_chamber_vote() and close_chamber_voting()."""

    def _setup_voting(self, engine, resolver):
        """Helper: create amendment and open proposal chamber voting."""
        proposal = engine.create_amendment("h1", "NO_BUY_TRUST", True, True,
                                           "Test", now=_now())
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)
        eligible = _make_eligible_voters(100)
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )
        return proposal, panel, chambers

    def test_happy_path_pass(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """All panel members vote yes → chamber passes."""
        proposal, panel, chambers = self._setup_voting(engine, resolver)
        for vid in panel:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.PROPOSAL,
                True, "I approve", "eu", "org_0", _now(),
            )
        result, passed = engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            chambers[ChamberKind.PROPOSAL], _now(),
        )
        assert passed is True
        assert result.status == AmendmentStatus.RATIFICATION_CHAMBER_VOTING

    def test_rejection(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """All panel members vote no → chamber fails."""
        proposal, panel, chambers = self._setup_voting(engine, resolver)
        for vid in panel:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.PROPOSAL,
                False, "I reject", "eu", "org_0", _now(),
            )
        result, passed = engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            chambers[ChamberKind.PROPOSAL], _now(),
        )
        assert passed is False
        assert result.status == AmendmentStatus.REJECTED

    def test_non_member_rejected(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Non-panel member cannot vote."""
        proposal, panel, chambers = self._setup_voting(engine, resolver)
        with pytest.raises(ValueError, match="not a member"):
            engine.cast_chamber_vote(
                proposal.proposal_id, "outsider", ChamberKind.PROPOSAL,
                True, "I approve", "eu", "org_0", _now(),
            )

    def test_duplicate_vote_rejected(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Same voter cannot vote twice in the same chamber."""
        proposal, panel, chambers = self._setup_voting(engine, resolver)
        engine.cast_chamber_vote(
            proposal.proposal_id, panel[0], ChamberKind.PROPOSAL,
            True, "I approve", "eu", "org_0", _now(),
        )
        with pytest.raises(ValueError, match="already voted"):
            engine.cast_chamber_vote(
                proposal.proposal_id, panel[0], ChamberKind.PROPOSAL,
                True, "I approve again", "eu", "org_0", _now(),
            )

    def test_empty_attestation_rejected(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Empty attestation is rejected."""
        proposal, panel, chambers = self._setup_voting(engine, resolver)
        with pytest.raises(ValueError, match="attestation must not be empty"):
            engine.cast_chamber_vote(
                proposal.proposal_id, panel[0], ChamberKind.PROPOSAL,
                True, "  ", "eu", "org_0", _now(),
            )


class TestChamberProgression:
    """Tests for the sequential chamber progression."""

    def _pass_chamber(self, engine, proposal, panel, chamber_kind, chamber_def):
        """Helper: all panel members vote yes and close voting."""
        for vid in panel:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, chamber_kind,
                True, "I approve", "eu", "org_0", _now(),
            )
        return engine.close_chamber_voting(
            proposal.proposal_id, chamber_kind, chamber_def, _now(),
        )

    def test_full_progression_non_entrenched(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Non-entrenched: proposal → ratification → challenge window → confirmed."""
        proposal = engine.create_amendment(
            "h1", "gcf_compute.GCF_COMPUTE_CEILING", "0.25", "0.30",
            "Increase ceiling", now=_now(),
        )
        assert proposal.is_entrenched is False

        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)
        eligible = _make_eligible_voters(200)

        # Proposal chamber
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )
        self._pass_chamber(engine, proposal, panel, ChamberKind.PROPOSAL,
                           chambers[ChamberKind.PROPOSAL])
        assert proposal.status == AmendmentStatus.RATIFICATION_CHAMBER_VOTING

        # Ratification chamber
        panel2 = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            eligible, chambers[ChamberKind.RATIFICATION], r_min, c_max, _now(),
        )
        self._pass_chamber(engine, proposal, panel2, ChamberKind.RATIFICATION,
                           chambers[ChamberKind.RATIFICATION])
        assert proposal.status == AmendmentStatus.CHALLENGE_WINDOW

        # No challenge → confirmed
        engine.advance_past_challenge_window(proposal.proposal_id, _now())
        assert proposal.status == AmendmentStatus.CONFIRMED

    def test_challenge_triggers_voting(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Filing a challenge moves to CHALLENGE_CHAMBER_VOTING."""
        proposal = engine.create_amendment(
            "h1", "gcf_compute.GCF_COMPUTE_CEILING", "0.25", "0.30",
            "Increase ceiling", now=_now(),
        )
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)
        eligible = _make_eligible_voters(200)

        # Pass proposal and ratification
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )
        self._pass_chamber(engine, proposal, panel, ChamberKind.PROPOSAL,
                           chambers[ChamberKind.PROPOSAL])
        panel2 = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            eligible, chambers[ChamberKind.RATIFICATION], r_min, c_max, _now(),
        )
        self._pass_chamber(engine, proposal, panel2, ChamberKind.RATIFICATION,
                           chambers[ChamberKind.RATIFICATION])
        assert proposal.status == AmendmentStatus.CHALLENGE_WINDOW

        # File challenge
        engine.file_challenge(proposal.proposal_id, "challenger_1", _now())
        assert proposal.status == AmendmentStatus.CHALLENGE_CHAMBER_VOTING
        assert proposal.challenge_filed is True

    def test_failed_proposal_kills_amendment(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """If proposal chamber fails, the amendment is REJECTED."""
        proposal = engine.create_amendment(
            "h1", "NO_BUY_TRUST", True, True, "Test", now=_now(),
        )
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)
        eligible = _make_eligible_voters(100)

        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )
        # All vote no
        for vid in panel:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.PROPOSAL,
                False, "I reject", "eu", "org_0", _now(),
            )
        result, passed = engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            chambers[ChamberKind.PROPOSAL], _now(),
        )
        assert passed is False
        assert result.status == AmendmentStatus.REJECTED

    def test_entrenched_goes_to_cooling_off(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Entrenched amendment: after challenge window → COOLING_OFF (not CONFIRMED)."""
        proposal = engine.create_amendment(
            "h1", "GCF_CONTRIBUTION_RATE", "0.01", "0.02",
            "Double GCF rate", now=_now(),
        )
        assert proposal.is_entrenched is True

        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)
        eligible = _make_eligible_voters(200)

        # Pass proposal + ratification
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )
        self._pass_chamber(engine, proposal, panel, ChamberKind.PROPOSAL,
                           chambers[ChamberKind.PROPOSAL])
        panel2 = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            eligible, chambers[ChamberKind.RATIFICATION], r_min, c_max, _now(),
        )
        self._pass_chamber(engine, proposal, panel2, ChamberKind.RATIFICATION,
                           chambers[ChamberKind.RATIFICATION])

        # Advance past challenge window
        engine.advance_past_challenge_window(proposal.proposal_id, _now())
        assert proposal.status == AmendmentStatus.COOLING_OFF  # NOT CONFIRMED


# ======================================================================
# E-6c: Cooling-off + confirmation vote
# ======================================================================

class TestCoolingOff:
    """Cooling-off period tests — design test #58."""

    @pytest.fixture
    def engine(self, resolver: PolicyResolver) -> AmendmentEngine:
        return AmendmentEngine(resolver.amendment_config(), resolver._params)

    def _pass_through_chambers(
        self,
        engine: AmendmentEngine,
        resolver: PolicyResolver,
        proposal: AmendmentProposal,
        eligible: list[dict[str, Any]],
    ) -> None:
        """Drive an amendment through proposal + ratification + challenge window."""
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)

        # Proposal
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )
        for vid in panel:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.PROPOSAL,
                True, "I approve", "eu", "org_0", _now(),
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            chambers[ChamberKind.PROPOSAL], _now(),
        )

        # Ratification
        panel2 = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            eligible, chambers[ChamberKind.RATIFICATION], r_min, c_max, _now(),
        )
        for vid in panel2:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.RATIFICATION,
                True, "I ratify", "eu", "org_0", _now(),
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            chambers[ChamberKind.RATIFICATION], _now(),
        )

        # Advance past challenge
        engine.advance_past_challenge_window(proposal.proposal_id, _now())

    def test_cooling_off_timer_enforced(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """90-day cooling-off is enforced — cannot be shortened."""
        proposal = engine.create_amendment(
            "h1", "GCF_CONTRIBUTION_RATE", "0.01", "0.02",
            "Double GCF rate", now=_now(),
        )
        eligible = _make_eligible_voters(200)
        self._pass_through_chambers(engine, resolver, proposal, eligible)

        assert proposal.status == AmendmentStatus.COOLING_OFF
        now = _now()
        engine.start_cooling_off(proposal.proposal_id, now)

        # 89 days later — should NOT be complete
        day_89 = now + timedelta(days=89)
        assert engine.check_cooling_off_complete(proposal.proposal_id, day_89) is False

        # 90 days later — should be complete
        day_90 = now + timedelta(days=90)
        assert engine.check_cooling_off_complete(proposal.proposal_id, day_90) is True

    def test_premature_confirmation_rejected(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Cannot start confirmation vote before cooling-off completes."""
        proposal = engine.create_amendment(
            "h1", "GCF_CONTRIBUTION_RATE", "0.01", "0.02",
            "Double GCF rate", now=_now(),
        )
        eligible = _make_eligible_voters(200)
        self._pass_through_chambers(engine, resolver, proposal, eligible)

        now = _now()
        engine.start_cooling_off(proposal.proposal_id, now)

        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)

        # Try to start confirmation 30 days in — should fail
        day_30 = now + timedelta(days=30)
        with pytest.raises(ValueError, match="Cooling-off period has not elapsed"):
            engine.start_confirmation_vote(
                proposal.proposal_id, eligible,
                chambers[ChamberKind.RATIFICATION], r_min, c_max, day_30,
            )

    def test_full_90_day_cooling_off(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """After 90 days, confirmation vote can proceed."""
        proposal = engine.create_amendment(
            "h1", "GCF_CONTRIBUTION_RATE", "0.01", "0.02",
            "Double GCF rate", now=_now(),
        )
        eligible = _make_eligible_voters(200)
        self._pass_through_chambers(engine, resolver, proposal, eligible)

        now = _now()
        engine.start_cooling_off(proposal.proposal_id, now)

        day_91 = now + timedelta(days=91)
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)

        panel = engine.start_confirmation_vote(
            proposal.proposal_id, eligible,
            chambers[ChamberKind.RATIFICATION], r_min, c_max, day_91,
        )
        assert len(panel) == chambers[ChamberKind.RATIFICATION].size
        assert proposal.status == AmendmentStatus.CONFIRMATION_VOTE

    def test_non_entrenched_skips_cooling_off(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Non-entrenched amendments skip cooling-off entirely."""
        proposal = engine.create_amendment(
            "h1", "tau_vote", "0.60", "0.65",
            "Raise voting threshold slightly", now=_now(),
        )
        assert proposal.is_entrenched is False

        eligible = _make_eligible_voters(200)
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)

        # Proposal
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )
        for vid in panel:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.PROPOSAL,
                True, "I approve", "eu", "org_0", _now(),
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            chambers[ChamberKind.PROPOSAL], _now(),
        )

        # Ratification
        panel2 = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            eligible, chambers[ChamberKind.RATIFICATION], r_min, c_max, _now(),
        )
        for vid in panel2:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.RATIFICATION,
                True, "I ratify", "eu", "org_0", _now(),
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            chambers[ChamberKind.RATIFICATION], _now(),
        )

        # Advance past challenge → CONFIRMED directly (no cooling-off)
        engine.advance_past_challenge_window(proposal.proposal_id, _now())
        assert proposal.status == AmendmentStatus.CONFIRMED

        # Trying to start cooling-off on a CONFIRMED amendment → error
        with pytest.raises(ValueError, match="Cannot start cooling-off"):
            engine.start_cooling_off(proposal.proposal_id, _now())


class TestConfirmationVote:
    """Confirmation vote tests — the entrenched safety net."""

    @pytest.fixture
    def engine(self, resolver: PolicyResolver) -> AmendmentEngine:
        return AmendmentEngine(resolver.amendment_config(), resolver._params)

    def _pass_to_confirmation(
        self,
        engine: AmendmentEngine,
        resolver: PolicyResolver,
        eligible: list[dict[str, Any]],
    ) -> AmendmentProposal:
        """Drive an entrenched amendment to CONFIRMATION_VOTE status."""
        proposal = engine.create_amendment(
            "h1", "GCF_CONTRIBUTION_RATE", "0.01", "0.02",
            "Double GCF rate", now=_now(),
        )
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)

        # Proposal
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )
        for vid in panel:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.PROPOSAL,
                True, "I approve", "eu", "org_0", _now(),
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            chambers[ChamberKind.PROPOSAL], _now(),
        )

        # Ratification
        panel2 = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            eligible, chambers[ChamberKind.RATIFICATION], r_min, c_max, _now(),
        )
        for vid in panel2:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.RATIFICATION,
                True, "I ratify", "eu", "org_0", _now(),
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            chambers[ChamberKind.RATIFICATION], _now(),
        )

        # Advance past challenge
        engine.advance_past_challenge_window(proposal.proposal_id, _now())

        # Start and wait out cooling-off
        now = _now()
        engine.start_cooling_off(proposal.proposal_id, now)
        day_91 = now + timedelta(days=91)

        # Start confirmation vote
        engine.start_confirmation_vote(
            proposal.proposal_id, eligible,
            chambers[ChamberKind.RATIFICATION], r_min, c_max, day_91,
        )
        return proposal

    def test_fresh_panel_no_overlap(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Confirmation panel has NO overlap with original ratification panel."""
        eligible = _make_eligible_voters(200)
        proposal = self._pass_to_confirmation(engine, resolver, eligible)

        ratification_panel = set(proposal.chamber_panels.get("ratification", []))
        confirmation_panel = set(proposal.confirmation_panel or [])

        assert len(ratification_panel & confirmation_panel) == 0

    def test_passes_with_supermajority(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Confirmation passes with >=80% yes + >=50% participation."""
        eligible = _make_eligible_voters(200)
        proposal = self._pass_to_confirmation(engine, resolver, eligible)
        panel = proposal.confirmation_panel

        # All vote yes
        for vid in panel:
            engine.cast_confirmation_vote(
                proposal.proposal_id, vid, True, "I confirm",
                "eu", "org_0", _now(),
            )

        result, confirmed = engine.close_confirmation_vote(
            proposal.proposal_id, _now(),
        )
        assert confirmed is True
        assert result.status == AmendmentStatus.CONFIRMED

    def test_fails_kills_amendment(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Confirmation failure rejects the amendment (even though all chambers passed)."""
        eligible = _make_eligible_voters(200)
        proposal = self._pass_to_confirmation(engine, resolver, eligible)
        panel = proposal.confirmation_panel

        # All vote no
        for vid in panel:
            engine.cast_confirmation_vote(
                proposal.proposal_id, vid, False, "Changed my mind",
                "eu", "org_0", _now(),
            )

        result, confirmed = engine.close_confirmation_vote(
            proposal.proposal_id, _now(),
        )
        assert confirmed is False
        assert result.status == AmendmentStatus.REJECTED

    def test_participation_minimum_enforced(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """If fewer than 50% of panel votes, confirmation fails."""
        eligible = _make_eligible_voters(200)
        proposal = self._pass_to_confirmation(engine, resolver, eligible)
        panel = proposal.confirmation_panel

        # Only ~30% vote yes (e.g., 5 of 17)
        voting_count = max(1, len(panel) // 3)
        for vid in panel[:voting_count]:
            engine.cast_confirmation_vote(
                proposal.proposal_id, vid, True, "I confirm",
                "eu", "org_0", _now(),
            )

        result, confirmed = engine.close_confirmation_vote(
            proposal.proposal_id, _now(),
        )
        assert confirmed is False
        assert result.status == AmendmentStatus.REJECTED


# ======================================================================
# E-6d: Entrenched provision guard + amendment application
# ======================================================================

class TestEntrenchedGuard:
    """Tests for validate_amendment_application() — constitutional guardrails."""

    @pytest.fixture
    def engine(self, resolver: PolicyResolver) -> AmendmentEngine:
        return AmendmentEngine(resolver.amendment_config(), resolver._params)

    def _drive_to_confirmed_non_entrenched(
        self,
        engine: AmendmentEngine,
        resolver: PolicyResolver,
    ) -> AmendmentProposal:
        """Drive a non-entrenched amendment through the full path to CONFIRMED."""
        eligible = _make_eligible_voters(200)
        proposal = engine.create_amendment(
            "h1", "tau_vote", "0.60", "0.65",
            "Raise voting threshold", now=_now(),
        )
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)

        # Proposal
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )
        for vid in panel:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.PROPOSAL,
                True, "I approve", "eu", "org_0", _now(),
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            chambers[ChamberKind.PROPOSAL], _now(),
        )

        # Ratification
        panel2 = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            eligible, chambers[ChamberKind.RATIFICATION], r_min, c_max, _now(),
        )
        for vid in panel2:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.RATIFICATION,
                True, "I ratify", "eu", "org_0", _now(),
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            chambers[ChamberKind.RATIFICATION], _now(),
        )

        # Advance past challenge
        engine.advance_past_challenge_window(proposal.proposal_id, _now())
        assert proposal.status == AmendmentStatus.CONFIRMED
        return proposal

    def _drive_to_confirmed_entrenched(
        self,
        engine: AmendmentEngine,
        resolver: PolicyResolver,
    ) -> AmendmentProposal:
        """Drive an entrenched amendment through the full path to CONFIRMED."""
        eligible = _make_eligible_voters(200)
        proposal = engine.create_amendment(
            "h1", "GCF_CONTRIBUTION_RATE", "0.01", "0.02",
            "Double GCF rate", now=_now(),
        )
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)

        # Proposal
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )
        for vid in panel:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.PROPOSAL,
                True, "I approve", "eu", "org_0", _now(),
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            chambers[ChamberKind.PROPOSAL], _now(),
        )

        # Ratification
        panel2 = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            eligible, chambers[ChamberKind.RATIFICATION], r_min, c_max, _now(),
        )
        for vid in panel2:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.RATIFICATION,
                True, "I ratify", "eu", "org_0", _now(),
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            chambers[ChamberKind.RATIFICATION], _now(),
        )

        # Advance past challenge → COOLING_OFF
        engine.advance_past_challenge_window(proposal.proposal_id, _now())

        # Start and wait out cooling-off
        now = _now()
        engine.start_cooling_off(proposal.proposal_id, now)
        day_91 = now + timedelta(days=91)

        # Confirmation vote
        conf_panel = engine.start_confirmation_vote(
            proposal.proposal_id, eligible,
            chambers[ChamberKind.RATIFICATION], r_min, c_max, day_91,
        )
        for vid in conf_panel:
            engine.cast_confirmation_vote(
                proposal.proposal_id, vid, True, "I confirm",
                "eu", "org_0", day_91,
            )
        engine.close_confirmation_vote(proposal.proposal_id, day_91)
        assert proposal.status == AmendmentStatus.CONFIRMED
        return proposal

    def test_entrenched_without_cooling_off_blocked(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Design test #58: entrenched amendment without cooling-off → ConstitutionalViolation."""
        eligible = _make_eligible_voters(200)
        proposal = engine.create_amendment(
            "h1", "GCF_CONTRIBUTION_RATE", "0.01", "0.02",
            "Double GCF rate", now=_now(),
        )
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)

        # Pass proposal + ratification + advance past challenge
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )
        for vid in panel:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.PROPOSAL,
                True, "Yes", "eu", "org_0", _now(),
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            chambers[ChamberKind.PROPOSAL], _now(),
        )
        panel2 = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            eligible, chambers[ChamberKind.RATIFICATION], r_min, c_max, _now(),
        )
        for vid in panel2:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.RATIFICATION,
                True, "Yes", "eu", "org_0", _now(),
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            chambers[ChamberKind.RATIFICATION], _now(),
        )
        engine.advance_past_challenge_window(proposal.proposal_id, _now())
        # Now in COOLING_OFF — force status to CONFIRMED to simulate bypass
        proposal.status = AmendmentStatus.CONFIRMED

        with pytest.raises(ConstitutionalViolation, match="no cooling-off record"):
            engine.validate_amendment_application(proposal)

    def test_entrenched_without_confirmation_blocked(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Entrenched amendment without confirmation vote → ConstitutionalViolation."""
        eligible = _make_eligible_voters(200)
        proposal = engine.create_amendment(
            "h1", "GCF_CONTRIBUTION_RATE", "0.01", "0.02",
            "Double GCF rate", now=_now(),
        )
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        r_min, c_max = resolver.geo_constraints_for_phase(GenesisPhase.G1)

        # Pass all chambers + cooling-off but skip confirmation
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            eligible, chambers[ChamberKind.PROPOSAL], r_min, c_max, _now(),
        )
        for vid in panel:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.PROPOSAL,
                True, "Yes", "eu", "org_0", _now(),
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            chambers[ChamberKind.PROPOSAL], _now(),
        )
        panel2 = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            eligible, chambers[ChamberKind.RATIFICATION], r_min, c_max, _now(),
        )
        for vid in panel2:
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.RATIFICATION,
                True, "Yes", "eu", "org_0", _now(),
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.RATIFICATION,
            chambers[ChamberKind.RATIFICATION], _now(),
        )
        engine.advance_past_challenge_window(proposal.proposal_id, _now())
        now = _now()
        engine.start_cooling_off(proposal.proposal_id, now)
        # Force status to CONFIRMED without confirmation
        proposal.status = AmendmentStatus.CONFIRMED

        with pytest.raises(ConstitutionalViolation, match="no confirmation votes"):
            engine.validate_amendment_application(proposal)

    def test_non_entrenched_applied_correctly(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Non-entrenched amendment: standard pathway → APPLIED."""
        proposal = self._drive_to_confirmed_non_entrenched(engine, resolver)
        config = dict(resolver._params)

        engine.apply_amendment(proposal.proposal_id, config, _now())
        assert proposal.status == AmendmentStatus.APPLIED
        assert config["tau_vote"] == "0.65"

    def test_entrenched_applied_correctly(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Entrenched amendment: full pathway → APPLIED."""
        proposal = self._drive_to_confirmed_entrenched(engine, resolver)
        config = dict(resolver._params)

        engine.apply_amendment(proposal.proposal_id, config, _now())
        assert proposal.status == AmendmentStatus.APPLIED

    def test_wrong_status_rejected(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Cannot apply an amendment that isn't CONFIRMED."""
        proposal = engine.create_amendment(
            "h1", "tau_vote", "0.60", "0.65",
            "Test", now=_now(),
        )
        config = dict(resolver._params)

        with pytest.raises(ConstitutionalViolation, match="not CONFIRMED"):
            engine.apply_amendment(proposal.proposal_id, config, _now())

    def test_commission_rate_proposal_rejected(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """Design test #59: commission rates cannot be changed by ballot."""
        for key in FORMULA_ONLY_PARAMS:
            with pytest.raises(ValueError, match="formula-determined"):
                engine.create_amendment(
                    "h1", key, "0.10", "0.15",
                    "Try to change commission", now=_now(),
                )

    def test_gcf_rate_routed_as_entrenched(self, engine: AmendmentEngine, resolver: PolicyResolver) -> None:
        """GCF_CONTRIBUTION_RATE is automatically treated as entrenched."""
        proposal = engine.create_amendment(
            "h1", "GCF_CONTRIBUTION_RATE", "0.01", "0.015",
            "Increase GCF rate", now=_now(),
        )
        assert proposal.is_entrenched is True


class TestAmendmentApplicationService:
    """Service-layer tests for apply_confirmed_amendment()."""

    @pytest.fixture
    def service(self, resolver: PolicyResolver) -> GenesisService:
        return GenesisService(resolver)

    def test_apply_via_service(self, service: GenesisService) -> None:
        """Service-level apply_confirmed_amendment happy path."""
        # Register proposer
        _register_human(service, "proposer_1", trust=0.80)

        # Propose a non-entrenched amendment
        result = service.propose_amendment(
            proposer_id="proposer_1",
            provision_key="tau_vote",
            proposed_value="0.65",
            justification="Raise voting threshold",
        )
        assert result.success
        proposal_id = result.data["proposal_id"]

        # Need eligible voters
        regions = ["eu", "na", "as", "sa", "af", "me"]
        for i in range(100):
            _register_human(
                service,
                f"voter_{i}",
                trust=0.70,
                region=regions[i % len(regions)],
                org=f"org_{i % 10}",
            )

        # Open and pass proposal chamber
        result = service.open_amendment_chamber(proposal_id, ChamberKind.PROPOSAL, GenesisPhase.G1)
        assert result.success
        panel = result.data["panel_ids"]
        for vid in panel:
            result = service.vote_on_amendment(proposal_id, vid, ChamberKind.PROPOSAL, True, "I approve")
            assert result.success
        result = service.close_amendment_chamber(proposal_id, ChamberKind.PROPOSAL, GenesisPhase.G1)
        assert result.success
        assert result.data["passed"] is True

        # Open and pass ratification chamber
        result = service.open_amendment_chamber(proposal_id, ChamberKind.RATIFICATION, GenesisPhase.G1)
        assert result.success
        panel2 = result.data["panel_ids"]
        for vid in panel2:
            result = service.vote_on_amendment(proposal_id, vid, ChamberKind.RATIFICATION, True, "I ratify")
            assert result.success
        result = service.close_amendment_chamber(proposal_id, ChamberKind.RATIFICATION, GenesisPhase.G1)
        assert result.success

        # Advance past challenge
        result = service.advance_amendment_past_challenge(proposal_id)
        assert result.success
        assert result.data["status"] == "confirmed"

        # Apply
        result = service.apply_confirmed_amendment(proposal_id)
        assert result.success
        assert result.data["status"] == "applied"

    def test_apply_non_confirmed_fails(self, service: GenesisService) -> None:
        """Cannot apply an amendment that hasn't been confirmed."""
        _register_human(service, "proposer_1", trust=0.80)
        result = service.propose_amendment(
            proposer_id="proposer_1",
            provision_key="tau_vote",
            proposed_value="0.65",
            justification="Test",
        )
        assert result.success
        proposal_id = result.data["proposal_id"]

        result = service.apply_confirmed_amendment(proposal_id)
        assert result.success is False
        assert "not CONFIRMED" in result.errors[0]


# ======================================================================
# E-6e: Persistence + invariants
# ======================================================================

class TestAmendmentPersistence:
    """Round-trip persistence tests for amendment state."""

    def test_save_load_round_trip(self, resolver: PolicyResolver) -> None:
        """Amendments survive save/load cycle."""
        import tempfile
        from genesis.persistence.state_store import StateStore

        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "state.json"
            store = StateStore(store_path)

            engine = AmendmentEngine(
                resolver.amendment_config(), resolver._params,
            )
            proposal = engine.create_amendment(
                "h1", "tau_vote", "0.60", "0.65",
                "Test persistence", now=_now(),
            )

            # Save
            store.save_amendments(engine._proposals)

            # Load into new engine
            records = store.load_amendments()
            assert len(records) == 1
            assert records[0]["proposal_id"] == proposal.proposal_id
            assert records[0]["provision_key"] == "tau_vote"
            assert records[0]["status"] == "proposed"

            # Reconstruct engine
            engine2 = AmendmentEngine.from_records(
                resolver.amendment_config(), resolver._params, records,
            )
            restored = engine2.get_amendment(proposal.proposal_id)
            assert restored is not None
            assert restored.provision_key == "tau_vote"
            assert restored.proposed_value == "0.65"

    def test_invariants_pass(self) -> None:
        """check_invariants.py passes with current config."""
        import subprocess
        result = subprocess.run(
            ["python3", "tools/check_invariants.py"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        assert result.returncode == 0, f"Invariants failed: {result.stdout}{result.stderr}"
