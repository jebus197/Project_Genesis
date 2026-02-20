"""Tests for Domain Expert Pools + Machine Domain Clearance — Phase F-3.

Proves constitutional invariants:
- Machine clearance requires domain expert verification (design test #70).
- Domain clearance does not grant governance voting power (design test #71).
- Autonomous machine operation requires annual re-authorisation (design test #72).

Also covers:
- Clearance nomination and validation
- Unanimous voting (single rejection kills clearance)
- Quorum thresholds (3 for supervised, 5 for autonomous)
- Domain trust threshold enforcement
- Clearance approval and expiry date setting
- Clearance revocation by any domain expert
- Expiration sweep
- Renewal lifecycle
- Persistence round-trip
- Service layer integration

Design test #70: Can a machine receive domain clearance without verification
by domain experts? If yes, reject design.

Design test #71: Can a machine's domain clearance transfer governance
voting power? If yes, reject design.

Design test #72: Can autonomous machine operation be authorised without
annual re-authorisation? If yes, reject design.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from genesis.governance.domain_expert import (
    AUTONOMOUS_MIN_DOMAIN_TRUST,
    AUTONOMOUS_MIN_MACHINE_TRUST,
    AUTONOMOUS_MIN_QUORUM,
    CLEARANCE_MIN_DOMAIN_TRUST,
    CLEARANCE_MIN_QUORUM,
    DEFAULT_CLEARANCE_EXPIRY_DAYS,
    ClearanceLevel,
    ClearanceVote,
    DomainClearance,
    DomainClearanceStatus,
    DomainExpertEngine,
)
from genesis.models.domain_trust import DomainTrustScore
from genesis.models.trust import ActorKind
from genesis.persistence.event_log import EventKind, EventLog
from genesis.policy.resolver import PolicyResolver
from genesis.service import GenesisService

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _now() -> datetime:
    return datetime(2026, 2, 20, 12, 0, 0, tzinfo=timezone.utc)


def _default_config() -> dict[str, Any]:
    return {
        "clearance_min_quorum": 3,
        "clearance_min_domain_trust": 0.60,
        "autonomous_min_quorum": 5,
        "autonomous_min_domain_trust": 0.70,
        "autonomous_min_machine_trust": 0.60,
        "clearance_expiry_days": 365,
    }


def _make_service(resolver: PolicyResolver) -> GenesisService:
    """Create a GenesisService with actors for domain clearance tests."""
    svc = GenesisService(resolver, event_log=EventLog())
    svc.open_epoch()
    for i in range(1, 8):
        region = ["eu", "us", "asia", "af"][i % 4]
        org = ["acme", "beta", "gamma", "delta"][i % 4]
        svc.register_actor(
            f"human-{i}", ActorKind.HUMAN, region, org, initial_trust=0.65,
        )
    svc.register_machine(
        "bot-1", operator_id="human-1", region="eu", organization="acme",
        model_family="gpt", method_type="reasoning_model",
    )
    # Give human voters domain trust in "engineering" for service integration tests
    for i in range(1, 8):
        trust = svc._trust_records.get(f"human-{i}")
        if trust is not None:
            trust.domain_scores["engineering"] = DomainTrustScore(
                domain="engineering", score=0.70,
            )
    return svc


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def engine() -> DomainExpertEngine:
    return DomainExpertEngine(_default_config())


@pytest.fixture
def service(resolver: PolicyResolver) -> GenesisService:
    return _make_service(resolver)


# ==================================================================
# Design test #70: No clearance without expert verification
# ==================================================================

class TestDesignTest70ExpertVerification:
    """Machine clearance requires domain expert verification."""

    def test_clearance_starts_pending_not_active(
        self, engine: DomainExpertEngine,
    ) -> None:
        """Clearance nomination starts in PENDING state, not ACTIVE."""
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1", now=_now(),
        )
        assert c.status == DomainClearanceStatus.PENDING

    def test_clearance_requires_quorum_votes(
        self, engine: DomainExpertEngine,
    ) -> None:
        """Cannot activate clearance without quorum of expert votes."""
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1", now=_now(),
        )
        # Only 1 vote — not enough for quorum of 3
        engine.vote_on_clearance(c.clearance_id, "h1", 0.70, True, "Good", now=_now())
        result = engine.evaluate_clearance(c.clearance_id, now=_now())
        assert result.status == DomainClearanceStatus.PENDING  # Still pending

    def test_clearance_activates_at_quorum(
        self, engine: DomainExpertEngine,
    ) -> None:
        """Clearance activates when quorum of 3 unanimous approvals reached."""
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1", now=_now(),
        )
        for voter in ["h1", "h2", "h3"]:
            engine.vote_on_clearance(
                c.clearance_id, voter, 0.70, True, "Good", now=_now(),
            )
        result = engine.evaluate_clearance(c.clearance_id, now=_now())
        assert result.status == DomainClearanceStatus.ACTIVE

    def test_low_domain_trust_voter_rejected(
        self, engine: DomainExpertEngine,
    ) -> None:
        """Voter below domain trust threshold cannot vote."""
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1", now=_now(),
        )
        with pytest.raises(ValueError, match="below"):
            engine.vote_on_clearance(
                c.clearance_id, "h1", 0.40, True, "Good", now=_now(),
            )


# ==================================================================
# Design test #71: No governance power from clearance
# ==================================================================

class TestDesignTest71NoGovernancePower:
    """Domain clearance does not grant governance voting power."""

    def test_clearance_has_no_governance_field(self) -> None:
        """DomainClearance has no governance, voting, or amendment field."""
        field_names = {f.name for f in dataclasses.fields(DomainClearance)}
        forbidden = {"governance_power", "voting_rights", "constitutional_authority",
                     "amendment_power", "ballot", "governance_vote"}
        overlap = field_names & forbidden
        assert overlap == set(), f"DomainClearance has forbidden fields: {overlap}"

    def test_vote_has_no_governance_field(self) -> None:
        """ClearanceVote has no governance or constitutional field."""
        field_names = {f.name for f in dataclasses.fields(ClearanceVote)}
        forbidden = {"governance_power", "constitutional_vote", "amendment"}
        overlap = field_names & forbidden
        assert overlap == set(), f"ClearanceVote has forbidden fields: {overlap}"

    def test_engine_has_no_governance_methods(self) -> None:
        """DomainExpertEngine has no governance methods."""
        engine = DomainExpertEngine(_default_config())
        method_names = [m for m in dir(engine) if not m.startswith("_")]
        governance_terms = {"constitutional", "amendment", "ballot",
                           "governance_vote", "disburse"}
        for method in method_names:
            for term in governance_terms:
                assert term not in method.lower(), (
                    f"Engine method '{method}' contains governance term '{term}'"
                )


# ==================================================================
# Design test #72: Annual re-authorisation required
# ==================================================================

class TestDesignTest72AnnualReauth:
    """Autonomous machine operation requires annual re-authorisation."""

    def test_clearance_always_has_expiry(
        self, engine: DomainExpertEngine,
    ) -> None:
        """Active clearance always has expires_utc set."""
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1", now=_now(),
        )
        for voter in ["h1", "h2", "h3"]:
            engine.vote_on_clearance(
                c.clearance_id, voter, 0.70, True, "Good", now=_now(),
            )
        result = engine.evaluate_clearance(c.clearance_id, now=_now())
        assert result.expires_utc is not None

    def test_default_expiry_is_one_year(
        self, engine: DomainExpertEngine,
    ) -> None:
        """Default expiry is 365 days (annual)."""
        now = _now()
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1", now=now,
        )
        for voter in ["h1", "h2", "h3"]:
            engine.vote_on_clearance(
                c.clearance_id, voter, 0.70, True, "Good", now=now,
            )
        result = engine.evaluate_clearance(c.clearance_id, now=now)
        expected_expiry = now + timedelta(days=365)
        assert result.expires_utc == expected_expiry

    def test_expired_clearance_detected(
        self, engine: DomainExpertEngine,
    ) -> None:
        """Expiration sweep catches clearances past their expiry date."""
        now = _now()
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1", now=now,
        )
        for voter in ["h1", "h2", "h3"]:
            engine.vote_on_clearance(
                c.clearance_id, voter, 0.70, True, "Good", now=now,
            )
        engine.evaluate_clearance(c.clearance_id, now=now)

        # Fast-forward past expiry
        future = now + timedelta(days=366)
        expired = engine.check_expirations(now=future)
        assert len(expired) == 1
        assert expired[0].status == DomainClearanceStatus.EXPIRED

    def test_unexpired_clearance_not_affected(
        self, engine: DomainExpertEngine,
    ) -> None:
        """Expiration sweep does not affect active clearances within expiry."""
        now = _now()
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1", now=now,
        )
        for voter in ["h1", "h2", "h3"]:
            engine.vote_on_clearance(
                c.clearance_id, voter, 0.70, True, "Good", now=now,
            )
        engine.evaluate_clearance(c.clearance_id, now=now)

        # Only 100 days later — still within expiry
        partial = now + timedelta(days=100)
        expired = engine.check_expirations(now=partial)
        assert len(expired) == 0


# ==================================================================
# Unanimous voting
# ==================================================================

class TestUnanimousVoting:
    """Unanimous voting requirement — single rejection kills clearance."""

    def test_rejection_revokes_clearance(
        self, engine: DomainExpertEngine,
    ) -> None:
        """A single reject vote revokes the clearance."""
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1", now=_now(),
        )
        engine.vote_on_clearance(
            c.clearance_id, "h1", 0.70, True, "Good", now=_now(),
        )
        result = engine.vote_on_clearance(
            c.clearance_id, "h2", 0.70, False, "Concerns", now=_now(),
        )
        assert result.status == DomainClearanceStatus.REVOKED

    def test_duplicate_vote_rejected(
        self, engine: DomainExpertEngine,
    ) -> None:
        """Same voter cannot vote twice."""
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1", now=_now(),
        )
        engine.vote_on_clearance(
            c.clearance_id, "h1", 0.70, True, "Good", now=_now(),
        )
        with pytest.raises(ValueError, match="already"):
            engine.vote_on_clearance(
                c.clearance_id, "h1", 0.70, True, "Again", now=_now(),
            )

    def test_vote_on_revoked_rejected(
        self, engine: DomainExpertEngine,
    ) -> None:
        """Cannot vote on an already-revoked clearance."""
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1", now=_now(),
        )
        engine.vote_on_clearance(
            c.clearance_id, "h1", 0.70, False, "No", now=_now(),
        )
        with pytest.raises(ValueError, match="revoked"):
            engine.vote_on_clearance(
                c.clearance_id, "h2", 0.70, True, "Yes", now=_now(),
            )


# ==================================================================
# Autonomous clearance (Tier 2)
# ==================================================================

class TestAutonomousClearance:
    """Autonomous clearance requires stricter thresholds."""

    def test_autonomous_requires_5_voters(
        self, engine: DomainExpertEngine,
    ) -> None:
        """Autonomous clearance requires 5 approvals, not 3."""
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1",
            level=ClearanceLevel.AUTONOMOUS, now=_now(),
        )
        for voter in ["h1", "h2", "h3"]:
            engine.vote_on_clearance(
                c.clearance_id, voter, 0.80, True, "Good", now=_now(),
            )
        # 3 approvals — not enough for autonomous (needs 5)
        result = engine.evaluate_clearance(c.clearance_id, 0.70, now=_now())
        assert result.status == DomainClearanceStatus.PENDING

    def test_autonomous_activates_at_5(
        self, engine: DomainExpertEngine,
    ) -> None:
        """Autonomous clearance activates at 5 approvals."""
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1",
            level=ClearanceLevel.AUTONOMOUS, now=_now(),
        )
        for voter in ["h1", "h2", "h3", "h4", "h5"]:
            engine.vote_on_clearance(
                c.clearance_id, voter, 0.80, True, "Good", now=_now(),
            )
        result = engine.evaluate_clearance(c.clearance_id, 0.70, now=_now())
        assert result.status == DomainClearanceStatus.ACTIVE

    def test_autonomous_requires_higher_voter_trust(
        self, engine: DomainExpertEngine,
    ) -> None:
        """Autonomous clearance requires voter domain trust >= 0.70."""
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1",
            level=ClearanceLevel.AUTONOMOUS, now=_now(),
        )
        # Trust of 0.65 is below autonomous threshold (0.70)
        with pytest.raises(ValueError, match="below"):
            engine.vote_on_clearance(
                c.clearance_id, "h1", 0.65, True, "Good", now=_now(),
            )

    def test_autonomous_checks_machine_domain_trust(
        self, engine: DomainExpertEngine,
    ) -> None:
        """Machine domain trust must be >= 0.60 for autonomous clearance."""
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1",
            level=ClearanceLevel.AUTONOMOUS, now=_now(),
        )
        for voter in ["h1", "h2", "h3", "h4", "h5"]:
            engine.vote_on_clearance(
                c.clearance_id, voter, 0.80, True, "Good", now=_now(),
            )
        # Machine domain trust of 0.40 is below 0.60 threshold
        with pytest.raises(ValueError, match="below"):
            engine.evaluate_clearance(c.clearance_id, 0.40, now=_now())


# ==================================================================
# Revocation
# ==================================================================

class TestClearanceRevocation:
    """Clearance revocation by domain experts."""

    def _make_active_clearance(
        self, engine: DomainExpertEngine,
    ) -> DomainClearance:
        now = _now()
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1", now=now,
        )
        for voter in ["h1", "h2", "h3"]:
            engine.vote_on_clearance(
                c.clearance_id, voter, 0.70, True, "Good", now=now,
            )
        engine.evaluate_clearance(c.clearance_id, now=now)
        return engine.get_clearance(c.clearance_id)

    def test_revoke_active_clearance(self, engine: DomainExpertEngine) -> None:
        """Any domain expert can revoke an active clearance."""
        c = self._make_active_clearance(engine)
        result = engine.revoke_clearance(c.clearance_id, "h_expert")
        assert result.status == DomainClearanceStatus.REVOKED
        assert result.revoked_by == "h_expert"

    def test_revoke_non_active_rejected(self, engine: DomainExpertEngine) -> None:
        """Cannot revoke a non-active clearance."""
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1", now=_now(),
        )
        with pytest.raises(ValueError, match="not active"):
            engine.revoke_clearance(c.clearance_id, "h1")


# ==================================================================
# Renewal
# ==================================================================

class TestClearanceRenewal:
    """Clearance renewal lifecycle."""

    def _make_active_clearance(
        self, engine: DomainExpertEngine,
    ) -> DomainClearance:
        now = _now()
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1", now=now,
        )
        for voter in ["h1", "h2", "h3"]:
            engine.vote_on_clearance(
                c.clearance_id, voter, 0.70, True, "Good", now=now,
            )
        engine.evaluate_clearance(c.clearance_id, now=now)
        return engine.get_clearance(c.clearance_id)

    def test_renew_creates_new_pending(self, engine: DomainExpertEngine) -> None:
        """Renewal creates a new PENDING clearance."""
        c = self._make_active_clearance(engine)
        new = engine.renew_clearance(c.clearance_id)
        assert new.status == DomainClearanceStatus.PENDING
        assert new.renewal_count == 1
        assert new.clearance_id != c.clearance_id

    def test_renew_increments_count(self, engine: DomainExpertEngine) -> None:
        """Renewal count increments."""
        c = self._make_active_clearance(engine)
        new = engine.renew_clearance(c.clearance_id)
        assert new.renewal_count == 1

    def test_renew_expires_old_clearance(self, engine: DomainExpertEngine) -> None:
        """Renewing an active clearance sets old one to EXPIRED."""
        c = self._make_active_clearance(engine)
        engine.renew_clearance(c.clearance_id)
        old = engine.get_clearance(c.clearance_id)
        assert old.status == DomainClearanceStatus.EXPIRED

    def test_cannot_renew_revoked(self, engine: DomainExpertEngine) -> None:
        """Cannot renew a revoked clearance."""
        c = self._make_active_clearance(engine)
        engine.revoke_clearance(c.clearance_id, "expert")
        with pytest.raises(ValueError, match="revoked"):
            engine.renew_clearance(c.clearance_id)


# ==================================================================
# Nomination validation
# ==================================================================

class TestNominationValidation:
    """Clearance nomination edge cases."""

    def test_duplicate_pending_rejected(self, engine: DomainExpertEngine) -> None:
        """Cannot nominate for same machine/org/domain/level while pending."""
        engine.nominate_for_clearance("m1", "org1", "medical", "h1", now=_now())
        with pytest.raises(ValueError, match="already"):
            engine.nominate_for_clearance("m1", "org1", "medical", "h1", now=_now())

    def test_different_domain_allowed(self, engine: DomainExpertEngine) -> None:
        """Different domain is a separate clearance."""
        engine.nominate_for_clearance("m1", "org1", "medical", "h1", now=_now())
        c2 = engine.nominate_for_clearance("m1", "org1", "legal", "h1", now=_now())
        assert c2.domain == "legal"

    def test_different_level_allowed(self, engine: DomainExpertEngine) -> None:
        """Different level (supervised vs autonomous) is separate."""
        engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1",
            level=ClearanceLevel.SUPERVISED, now=_now(),
        )
        c2 = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1",
            level=ClearanceLevel.AUTONOMOUS, now=_now(),
        )
        assert c2.level == ClearanceLevel.AUTONOMOUS


# ==================================================================
# Listing and querying
# ==================================================================

class TestClearanceListing:
    """Active clearance listing."""

    def test_list_active_clearances(self, engine: DomainExpertEngine) -> None:
        """List only active clearances."""
        now = _now()
        c = engine.nominate_for_clearance("m1", "org1", "medical", "h1", now=now)
        for voter in ["h1", "h2", "h3"]:
            engine.vote_on_clearance(c.clearance_id, voter, 0.70, True, "Good", now=now)
        engine.evaluate_clearance(c.clearance_id, now=now)

        # Also create a pending one (should not appear)
        engine.nominate_for_clearance("m2", "org1", "legal", "h1", now=now)

        active = engine.get_active_clearances()
        assert len(active) == 1
        assert active[0].machine_id == "m1"

    def test_filter_by_machine(self, engine: DomainExpertEngine) -> None:
        """Filter active clearances by machine ID."""
        active = engine.get_active_clearances(machine_id="m99")
        assert len(active) == 0

    def test_has_active_clearance(self, engine: DomainExpertEngine) -> None:
        """Check specific clearance existence."""
        now = _now()
        c = engine.nominate_for_clearance("m1", "org1", "medical", "h1", now=now)
        for voter in ["h1", "h2", "h3"]:
            engine.vote_on_clearance(c.clearance_id, voter, 0.70, True, "Good", now=now)
        engine.evaluate_clearance(c.clearance_id, now=now)

        assert engine.has_active_clearance("m1", "medical") is True
        assert engine.has_active_clearance("m1", "legal") is False
        assert engine.has_active_clearance("m99", "medical") is False


# ==================================================================
# Persistence round-trip
# ==================================================================

class TestDomainExpertPersistence:
    """from_records / to_records round-trip."""

    def test_round_trip(self, engine: DomainExpertEngine) -> None:
        """Serialise and deserialise preserves all data."""
        now = _now()
        c = engine.nominate_for_clearance("m1", "org1", "medical", "h1", now=now)
        engine.vote_on_clearance(c.clearance_id, "h1", 0.70, True, "Good", now=now)
        engine.vote_on_clearance(c.clearance_id, "h2", 0.75, True, "Fine", now=now)
        engine.vote_on_clearance(c.clearance_id, "h3", 0.80, True, "Great", now=now)
        engine.evaluate_clearance(c.clearance_id, now=now)

        records = engine.to_records()
        restored = DomainExpertEngine.from_records(_default_config(), records)

        active = restored.get_active_clearances()
        assert len(active) == 1
        assert active[0].machine_id == "m1"
        assert active[0].vote_count == 3
        assert active[0].expires_utc is not None


# ==================================================================
# Service layer integration
# ==================================================================

class TestDomainExpertServiceIntegration:
    """Domain clearance through the service layer."""

    def test_nominate_via_service(self, service: GenesisService) -> None:
        """Nominate a machine for clearance through service."""
        result = service.nominate_for_clearance(
            "bot-1", "org1", "engineering", "human-1",
        )
        assert result.success
        assert result.data["status"] == "pending"
        assert result.data["level"] == "supervised"

    def test_nominate_requires_machine(self, service: GenesisService) -> None:
        """Cannot nominate a human for clearance."""
        result = service.nominate_for_clearance(
            "human-2", "org1", "engineering", "human-1",
        )
        assert not result.success
        assert "not a machine" in result.errors[0].lower()

    def test_nominate_requires_human_nominator(
        self, service: GenesisService,
    ) -> None:
        """Machine cannot nominate for clearance."""
        result = service.nominate_for_clearance(
            "bot-1", "org1", "engineering", "bot-1",
        )
        assert not result.success
        assert "human" in result.errors[0].lower()

    def test_vote_via_service(self, service: GenesisService) -> None:
        """Vote on clearance through service."""
        nom = service.nominate_for_clearance(
            "bot-1", "org1", "engineering", "human-1",
        )
        cid = nom.data["clearance_id"]
        result = service.vote_on_clearance(
            cid, "human-1", "engineering", True, "Good work",
        )
        assert result.success

    def test_evaluate_via_service(self, service: GenesisService) -> None:
        """Evaluate clearance through service (won't activate without
        domain trust, but should not error)."""
        nom = service.nominate_for_clearance(
            "bot-1", "org1", "engineering", "human-1",
        )
        cid = nom.data["clearance_id"]
        # Vote with sufficient trust passed directly
        for i in range(1, 4):
            service._domain_expert_engine.vote_on_clearance(
                cid, f"human-{i}", 0.70, True, "Good", now=_now(),
            )
        result = service.evaluate_clearance(cid)
        assert result.success

    def test_revoke_via_service(self, service: GenesisService) -> None:
        """Revoke clearance through service."""
        nom = service.nominate_for_clearance(
            "bot-1", "org1", "engineering", "human-1",
        )
        cid = nom.data["clearance_id"]
        # Manually activate for revocation test
        for i in range(1, 4):
            service._domain_expert_engine.vote_on_clearance(
                cid, f"human-{i}", 0.70, True, "Good", now=_now(),
            )
        service._domain_expert_engine.evaluate_clearance(cid, now=_now())

        result = service.revoke_clearance(cid, "human-4")
        assert result.success
        assert result.data["status"] == "revoked"

    def test_list_active_via_service(self, service: GenesisService) -> None:
        """List active clearances through service."""
        result = service.get_active_clearances()
        assert result.success
        assert result.data["count"] == 0

    def test_expiration_via_service(self, service: GenesisService) -> None:
        """Expiration sweep through service."""
        result = service.check_clearance_expirations()
        assert result.success
        assert result.data["expired_count"] == 0

    def test_clearance_events_emitted(self, service: GenesisService) -> None:
        """Clearance operations emit audit events."""
        result = service.nominate_for_clearance(
            "bot-1", "org1", "engineering", "human-1",
        )
        events = service._event_log.events(EventKind.CLEARANCE_NOMINATED)
        assert len(events) >= 1

    def test_invalid_level_rejected(self, service: GenesisService) -> None:
        """Invalid clearance level returns error."""
        result = service.nominate_for_clearance(
            "bot-1", "org1", "engineering", "human-1", level="nonsense",
        )
        assert not result.success
        assert "invalid" in result.errors[0].lower()
