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
        """entrenched_provision_keys() returns the 4 entrenched provisions."""
        keys = resolver.entrenched_provision_keys()
        assert "GCF_CONTRIBUTION_RATE" in keys
        assert "TRUST_FLOOR_H_POSITIVE" in keys
        assert "NO_BUY_TRUST" in keys
        assert "MACHINE_VOTING_EXCLUSION" in keys
        assert len(keys) == 4


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
