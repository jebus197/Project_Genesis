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

from genesis.governance.amendment import (
    AmendmentEngine,
    AmendmentProposal,
    AmendmentStatus,
    AmendmentVote,
    ConstitutionalViolation,
    FORMULA_ONLY_PARAMS,
)
from genesis.models.governance import Chamber, ChamberKind
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
