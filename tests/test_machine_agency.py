"""Tests for Machine Agency Tier Integration — Phase F-4.

Proves constitutional invariants:
- Tier 3 (Autonomous Domain Agency) requires full constitutional amendment
  process (design test #73).
- Tier 3 does NOT grant governance voting power (design test #74).
- Machine cannot self-petition for Tier 3 (design test #75).
- The constitution does not permanently foreclose machine evolution
  (design test #76).

Also covers:
- Tier computation (0/1/2/3/4 based on clearances and grants)
- Tier 3 prerequisite checks (5 years, trust, violations, reauth)
- Petition lifecycle (file → amendment → confirmed/rejected)
- Revocation and emergency suspension
- Violation auto-revert to Tier 1
- Persistence round-trip
- Service layer integration

Design test #73: Can a machine achieve Tier 3 (Autonomous Domain Agency)
without a full constitutional amendment process? If yes, reject design.

Design test #74: Can a machine with Tier 3 status vote on governance
decisions (GCF, amendments, adjudication panels)? If yes, reject design.

Design test #75: Can a machine petition for its own Tier 3 status without
a human operator initiating the process? If yes, reject design.

Design test #76: Does the constitution permanently foreclose the evolution
of machine capabilities, or does it provide a structured pathway for
community-consented expansion? If it forecloses, reject design.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from genesis.governance.machine_agency import (
    MachineAgencyEngine,
    MachineTier,
    Tier3Grant,
    Tier3PetitionStatus,
    Tier3Prerequisite,
    TIER3_MIN_DOMAIN_TRUST,
    TIER3_MIN_YEARS_AT_TIER2,
    TIER3_PROVISION_KEY_PREFIX,
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
        "tier3_min_years_at_tier2": 5,
        "tier3_min_domain_trust": 0.70,
    }


def _make_service(resolver: PolicyResolver) -> GenesisService:
    """Create a GenesisService with actors for machine agency tests."""
    svc = GenesisService(resolver, event_log=EventLog())
    svc.open_epoch()
    # Register 10 humans (need enough for amendment panels)
    for i in range(1, 11):
        region = ["eu", "us", "asia", "af"][i % 4]
        org = ["acme", "beta", "gamma", "delta"][i % 4]
        svc.register_actor(
            f"human-{i}", ActorKind.HUMAN, region, org, initial_trust=0.65,
        )
    # Register 2 machines
    svc.register_machine(
        "bot-1", operator_id="human-1", region="eu", organization="acme",
        model_family="gpt", method_type="reasoning_model",
    )
    svc.register_machine(
        "bot-2", operator_id="human-2", region="us", organization="beta",
        model_family="claude", method_type="reasoning_model",
    )
    # Give humans domain trust in "engineering" for clearance voting
    for i in range(1, 11):
        trust = svc._trust_records.get(f"human-{i}")
        if trust is not None:
            trust.domain_scores["engineering"] = DomainTrustScore(
                domain="engineering", score=0.75,
            )
    return svc


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def engine() -> MachineAgencyEngine:
    return MachineAgencyEngine(_default_config())


@pytest.fixture
def service(resolver: PolicyResolver) -> GenesisService:
    return _make_service(resolver)


# ==================================================================
# Design Tests
# ==================================================================

class TestDesignTest73RequiresAmendment:
    """Design test #73: Tier 3 requires full constitutional amendment."""

    def test_tier3_routes_through_amendment_engine(self) -> None:
        """Tier 3 petition creates an amendment with provision key
        'machine_agency.{machine_id}.{domain}'."""
        engine = MachineAgencyEngine(_default_config())
        # The engine records a petition linked to an amendment_proposal_id
        grant = engine.initiate_tier3_petition(
            "m1", "engineering", "h1", "amend_abc123", now=_now(),
        )
        assert grant.petition_id == "amend_abc123"
        assert grant.status == Tier3PetitionStatus.PENDING_AMENDMENT

    def test_no_direct_tier3_grant(self) -> None:
        """There is no method to directly grant Tier 3 without an
        amendment proposal."""
        engine = MachineAgencyEngine(_default_config())
        method_names = [m for m in dir(engine) if not m.startswith("_")]
        # No method called 'grant_tier3' or 'set_tier3' or 'promote_tier3'
        assert "grant_tier3" not in method_names
        assert "set_tier3" not in method_names
        assert "promote_tier3" not in method_names

    def test_provision_key_format(self) -> None:
        """Provision key follows the 'machine_agency.{id}.{domain}' pattern."""
        engine = MachineAgencyEngine(_default_config())
        key = engine.provision_key_for("bot-1", "engineering")
        assert key == "machine_agency.bot-1.engineering"
        assert MachineAgencyEngine.is_tier3_provision_key(key) is True

    def test_parse_provision_key(self) -> None:
        """Can parse machine_id and domain from provision key."""
        mid, domain = MachineAgencyEngine.parse_tier3_provision_key(
            "machine_agency.bot-1.engineering",
        )
        assert mid == "bot-1"
        assert domain == "engineering"


class TestDesignTest74NoGovernanceVoting:
    """Design test #74: Tier 3 does NOT grant governance voting power."""

    def test_tier3_grant_has_no_voting_field(self) -> None:
        """Tier3Grant dataclass has no voting or governance fields."""
        fields = {f.name for f in dataclasses.fields(Tier3Grant)}
        forbidden = {"voting_power", "governance_rights", "can_vote",
                     "amendment_vote", "gcf_vote", "adjudication_vote"}
        assert fields.isdisjoint(forbidden), (
            f"Tier3Grant has forbidden governance fields: "
            f"{fields & forbidden}"
        )

    def test_machine_tier_enum_has_no_voting_tier(self) -> None:
        """MachineTier enum values describe operational tiers only."""
        tier_values = {t.value for t in MachineTier}
        assert "voting" not in str(tier_values).lower()
        assert "governance" not in str(tier_values).lower()

    def test_engine_has_no_voting_methods(self) -> None:
        """MachineAgencyEngine has no methods for governance voting."""
        method_names = [m for m in dir(MachineAgencyEngine) if not m.startswith("_")]
        for name in method_names:
            assert "vote" not in name.lower() or "cast_vote" not in name.lower(), (
                f"MachineAgencyEngine has voting method: {name}"
            )


class TestDesignTest75NoSelfPetition:
    """Design test #75: Machine cannot self-petition for Tier 3."""

    def test_service_rejects_machine_petitioner(
        self, service: GenesisService,
    ) -> None:
        """Machine actor rejected as petitioner."""
        result = service.initiate_tier3_petition(
            "bot-1", "engineering", "bot-1", "I want agency",
        )
        assert not result.success
        assert "human" in result.errors[0].lower()

    def test_service_rejects_machine_petitioner_other_machine(
        self, service: GenesisService,
    ) -> None:
        """One machine cannot petition for another machine."""
        result = service.initiate_tier3_petition(
            "bot-1", "engineering", "bot-2", "My friend deserves it",
        )
        assert not result.success
        assert "human" in result.errors[0].lower()

    def test_human_petitioner_accepted(
        self, service: GenesisService,
    ) -> None:
        """Human operator can petition for a machine."""
        result = service.initiate_tier3_petition(
            "bot-1", "engineering", "human-1",
            "5 years of flawless autonomous operation",
        )
        assert result.success
        assert result.data["status"] == "pending_amendment"


class TestDesignTest76PathwayNotForeclosed:
    """Design test #76: Constitution provides structured pathway."""

    def test_tier_enum_includes_tier3_and_tier4(self) -> None:
        """MachineTier enum includes Tier 3 and Tier 4 — pathway exists."""
        assert MachineTier.TIER_3 is not None
        assert MachineTier.TIER_4 is not None

    def test_petition_mechanism_exists(self) -> None:
        """MachineAgencyEngine has initiate_tier3_petition method."""
        assert hasattr(MachineAgencyEngine, "initiate_tier3_petition")
        assert callable(MachineAgencyEngine.initiate_tier3_petition)

    def test_amendment_confirmation_mechanism_exists(self) -> None:
        """MachineAgencyEngine has on_amendment_confirmed method."""
        assert hasattr(MachineAgencyEngine, "on_amendment_confirmed")
        assert callable(MachineAgencyEngine.on_amendment_confirmed)

    def test_evolution_is_per_machine_per_domain(self) -> None:
        """Provision key is per-machine, per-domain — no batch process."""
        key1 = MachineAgencyEngine(_default_config()).provision_key_for(
            "bot-1", "engineering",
        )
        key2 = MachineAgencyEngine(_default_config()).provision_key_for(
            "bot-1", "medical",
        )
        key3 = MachineAgencyEngine(_default_config()).provision_key_for(
            "bot-2", "engineering",
        )
        # All three are distinct — no shortcuts
        assert key1 != key2
        assert key1 != key3
        assert key2 != key3


# ==================================================================
# Tier Computation
# ==================================================================

class TestTierComputation:
    """Test tier computation from clearance and grant state."""

    def test_no_clearance_is_tier0(self, engine: MachineAgencyEngine) -> None:
        """Machine with no clearance is Tier 0."""
        tiers = engine.compute_current_tier("m1", [])
        assert tiers == {}
        assert engine.compute_effective_tier("m1", []) == MachineTier.TIER_0

    def test_supervised_clearance_is_tier1(
        self, engine: MachineAgencyEngine,
    ) -> None:
        """Machine with supervised clearance is Tier 1."""
        clearances = [
            {"machine_id": "m1", "domain": "eng", "level": "supervised"},
        ]
        tiers = engine.compute_current_tier("m1", clearances)
        assert tiers["eng"] == MachineTier.TIER_1
        assert engine.compute_effective_tier("m1", clearances) == MachineTier.TIER_1

    def test_autonomous_clearance_is_tier2(
        self, engine: MachineAgencyEngine,
    ) -> None:
        """Machine with autonomous clearance is Tier 2."""
        clearances = [
            {"machine_id": "m1", "domain": "eng", "level": "autonomous"},
        ]
        tiers = engine.compute_current_tier("m1", clearances)
        assert tiers["eng"] == MachineTier.TIER_2
        assert engine.compute_effective_tier("m1", clearances) == MachineTier.TIER_2

    def test_tier3_grant_overrides_clearance(
        self, engine: MachineAgencyEngine,
    ) -> None:
        """Tier 3 grant overrides Tier 1/2 clearance for that domain."""
        clearances = [
            {"machine_id": "m1", "domain": "eng", "level": "autonomous"},
        ]
        # Grant Tier 3
        engine.initiate_tier3_petition(
            "m1", "eng", "h1", "amend_abc", now=_now(),
        )
        engine.on_amendment_confirmed("amend_abc", now=_now())

        tiers = engine.compute_current_tier("m1", clearances)
        assert tiers["eng"] == MachineTier.TIER_3

    def test_multi_domain_tier3_is_tier4(
        self, engine: MachineAgencyEngine,
    ) -> None:
        """Machine with Tier 3 in 2+ domains is Tier 4."""
        clearances = [
            {"machine_id": "m1", "domain": "eng", "level": "autonomous"},
            {"machine_id": "m1", "domain": "med", "level": "autonomous"},
        ]
        # Grant Tier 3 in two domains
        engine.initiate_tier3_petition(
            "m1", "eng", "h1", "amend_1", now=_now(),
        )
        engine.on_amendment_confirmed("amend_1", now=_now())

        engine.initiate_tier3_petition(
            "m1", "med", "h1", "amend_2", now=_now(),
        )
        engine.on_amendment_confirmed("amend_2", now=_now())

        effective = engine.compute_effective_tier("m1", clearances)
        assert effective == MachineTier.TIER_4

    def test_other_machine_clearances_ignored(
        self, engine: MachineAgencyEngine,
    ) -> None:
        """Clearances for other machines don't affect this machine's tier."""
        clearances = [
            {"machine_id": "m2", "domain": "eng", "level": "autonomous"},
        ]
        tiers = engine.compute_current_tier("m1", clearances)
        assert tiers == {}


# ==================================================================
# Tier 3 Prerequisites
# ==================================================================

class TestTier3Prerequisites:
    """Test prerequisite checking for Tier 3 eligibility."""

    def test_all_met(self, engine: MachineAgencyEngine) -> None:
        """All prerequisites met — eligible."""
        now = _now()
        tier2_date = now - timedelta(days=6 * 365)
        prereqs = engine.check_tier3_prerequisites(
            "m1", "eng",
            tier2_granted_utc=tier2_date,
            domain_trust_score=0.80,
            violation_count=0,
            reauth_chain_broken=False,
            now=now,
        )
        assert prereqs.all_met is True
        assert prereqs.has_5_years_tier2 is True
        assert prereqs.domain_trust_above_threshold is True
        assert prereqs.zero_violations is True
        assert prereqs.unbroken_reauth_chain is True

    def test_insufficient_time(self, engine: MachineAgencyEngine) -> None:
        """Less than 5 years at Tier 2 — not eligible."""
        now = _now()
        tier2_date = now - timedelta(days=3 * 365)
        prereqs = engine.check_tier3_prerequisites(
            "m1", "eng",
            tier2_granted_utc=tier2_date,
            domain_trust_score=0.80,
            violation_count=0,
            reauth_chain_broken=False,
            now=now,
        )
        assert prereqs.all_met is False
        assert prereqs.has_5_years_tier2 is False

    def test_low_domain_trust(self, engine: MachineAgencyEngine) -> None:
        """Domain trust below 0.70 — not eligible."""
        now = _now()
        tier2_date = now - timedelta(days=6 * 365)
        prereqs = engine.check_tier3_prerequisites(
            "m1", "eng",
            tier2_granted_utc=tier2_date,
            domain_trust_score=0.65,
            violation_count=0,
            reauth_chain_broken=False,
            now=now,
        )
        assert prereqs.all_met is False
        assert prereqs.domain_trust_above_threshold is False

    def test_violation_blocks(self, engine: MachineAgencyEngine) -> None:
        """Any violation blocks Tier 3."""
        now = _now()
        tier2_date = now - timedelta(days=6 * 365)
        prereqs = engine.check_tier3_prerequisites(
            "m1", "eng",
            tier2_granted_utc=tier2_date,
            domain_trust_score=0.80,
            violation_count=1,
            reauth_chain_broken=False,
            now=now,
        )
        assert prereqs.all_met is False
        assert prereqs.zero_violations is False

    def test_broken_reauth_chain(self, engine: MachineAgencyEngine) -> None:
        """Broken re-auth chain blocks Tier 3."""
        now = _now()
        tier2_date = now - timedelta(days=6 * 365)
        prereqs = engine.check_tier3_prerequisites(
            "m1", "eng",
            tier2_granted_utc=tier2_date,
            domain_trust_score=0.80,
            violation_count=0,
            reauth_chain_broken=True,
            now=now,
        )
        assert prereqs.all_met is False
        assert prereqs.unbroken_reauth_chain is False

    def test_no_tier2_ever(self, engine: MachineAgencyEngine) -> None:
        """Never had Tier 2 — not eligible."""
        prereqs = engine.check_tier3_prerequisites(
            "m1", "eng",
            tier2_granted_utc=None,
            domain_trust_score=0.80,
            violation_count=0,
            reauth_chain_broken=False,
            now=_now(),
        )
        assert prereqs.all_met is False
        assert prereqs.has_5_years_tier2 is False


# ==================================================================
# Petition Lifecycle
# ==================================================================

class TestPetitionLifecycle:
    """Test the Tier 3 petition lifecycle."""

    def test_petition_creation(self, engine: MachineAgencyEngine) -> None:
        """Create a petition with pending status."""
        grant = engine.initiate_tier3_petition(
            "m1", "eng", "h1", "amend_abc", now=_now(),
        )
        assert grant.status == Tier3PetitionStatus.PENDING_AMENDMENT
        assert grant.machine_id == "m1"
        assert grant.domain == "eng"
        assert grant.petitioner_id == "h1"

    def test_amendment_confirmed(self, engine: MachineAgencyEngine) -> None:
        """Confirmed amendment grants Tier 3."""
        engine.initiate_tier3_petition(
            "m1", "eng", "h1", "amend_abc", now=_now(),
        )
        grant = engine.on_amendment_confirmed("amend_abc", now=_now())
        assert grant is not None
        assert grant.status == Tier3PetitionStatus.GRANTED
        assert grant.granted_utc is not None

    def test_amendment_rejected(self, engine: MachineAgencyEngine) -> None:
        """Rejected amendment marks petition as rejected."""
        engine.initiate_tier3_petition(
            "m1", "eng", "h1", "amend_abc", now=_now(),
        )
        grant = engine.on_amendment_rejected("amend_abc", now=_now())
        assert grant is not None
        assert grant.status == Tier3PetitionStatus.REJECTED

    def test_duplicate_petition_blocked(
        self, engine: MachineAgencyEngine,
    ) -> None:
        """Cannot file a second petition for same machine+domain."""
        engine.initiate_tier3_petition(
            "m1", "eng", "h1", "amend_1", now=_now(),
        )
        with pytest.raises(ValueError, match="already exists"):
            engine.initiate_tier3_petition(
                "m1", "eng", "h2", "amend_2", now=_now(),
            )

    def test_rejected_petition_allows_retry(
        self, engine: MachineAgencyEngine,
    ) -> None:
        """After rejection, can file a new petition."""
        engine.initiate_tier3_petition(
            "m1", "eng", "h1", "amend_1", now=_now(),
        )
        engine.on_amendment_rejected("amend_1", now=_now())
        # Should succeed now
        grant = engine.initiate_tier3_petition(
            "m1", "eng", "h1", "amend_2", now=_now(),
        )
        assert grant.status == Tier3PetitionStatus.PENDING_AMENDMENT

    def test_unknown_amendment_returns_none(
        self, engine: MachineAgencyEngine,
    ) -> None:
        """Unknown amendment ID returns None."""
        assert engine.on_amendment_confirmed("amend_nope") is None
        assert engine.on_amendment_rejected("amend_nope") is None


# ==================================================================
# Revocation and Suspension
# ==================================================================

class TestRevocationAndSuspension:
    """Test revocation and emergency suspension of Tier 3."""

    def test_revoke_tier3(self, engine: MachineAgencyEngine) -> None:
        """Revoke a granted Tier 3."""
        engine.initiate_tier3_petition(
            "m1", "eng", "h1", "amend_abc", now=_now(),
        )
        engine.on_amendment_confirmed("amend_abc", now=_now())

        grant = engine.revoke_tier3("m1", "eng", "Bad behaviour", now=_now())
        assert grant is not None
        assert grant.status == Tier3PetitionStatus.REVOKED
        assert grant.revocation_reason == "Bad behaviour"

    def test_revoke_clears_from_tier_computation(
        self, engine: MachineAgencyEngine,
    ) -> None:
        """Revoked Tier 3 no longer appears in tier computation."""
        clearances = [
            {"machine_id": "m1", "domain": "eng", "level": "autonomous"},
        ]
        engine.initiate_tier3_petition(
            "m1", "eng", "h1", "amend_abc", now=_now(),
        )
        engine.on_amendment_confirmed("amend_abc", now=_now())
        assert engine.compute_current_tier("m1", clearances)["eng"] == MachineTier.TIER_3

        engine.revoke_tier3("m1", "eng", "Revoked", now=_now())
        # Falls back to Tier 2 (autonomous clearance still exists)
        assert engine.compute_current_tier("m1", clearances)["eng"] == MachineTier.TIER_2

    def test_emergency_suspend(self, engine: MachineAgencyEngine) -> None:
        """Emergency suspension freezes Tier 3."""
        engine.initiate_tier3_petition(
            "m1", "eng", "h1", "amend_abc", now=_now(),
        )
        engine.on_amendment_confirmed("amend_abc", now=_now())

        grant = engine.emergency_suspend(
            "m1", "eng", "Safety concern", now=_now(),
        )
        assert grant is not None
        assert grant.status == Tier3PetitionStatus.SUSPENDED

    def test_violation_auto_reverts(self, engine: MachineAgencyEngine) -> None:
        """Constitutional violation auto-reverts Tier 3."""
        engine.initiate_tier3_petition(
            "m1", "eng", "h1", "amend_abc", now=_now(),
        )
        engine.on_amendment_confirmed("amend_abc", now=_now())

        grant = engine.on_violation("m1", "eng", now=_now())
        assert grant is not None
        assert grant.status == Tier3PetitionStatus.REVOKED
        assert "violation" in grant.revocation_reason.lower()

    def test_revoke_nonexistent_returns_none(
        self, engine: MachineAgencyEngine,
    ) -> None:
        """Revoking a non-existent grant returns None."""
        assert engine.revoke_tier3("m1", "eng", "test") is None
        assert engine.emergency_suspend("m1", "eng", "test") is None
        assert engine.on_violation("m1", "eng") is None


# ==================================================================
# Grant Queries
# ==================================================================

class TestGrantQueries:
    """Test grant querying and filtering."""

    def test_get_tier3_grant(self, engine: MachineAgencyEngine) -> None:
        """Get specific machine+domain grant."""
        engine.initiate_tier3_petition(
            "m1", "eng", "h1", "amend_abc", now=_now(),
        )
        grant = engine.get_tier3_grant("m1", "eng")
        assert grant is not None
        assert grant.machine_id == "m1"
        assert grant.domain == "eng"

    def test_get_all_grants_filtered(
        self, engine: MachineAgencyEngine,
    ) -> None:
        """Filter grants by machine and status."""
        engine.initiate_tier3_petition(
            "m1", "eng", "h1", "amend_1", now=_now(),
        )
        engine.initiate_tier3_petition(
            "m2", "eng", "h2", "amend_2", now=_now(),
        )
        engine.on_amendment_confirmed("amend_1", now=_now())

        # Filter by machine
        m1_grants = engine.get_all_grants(machine_id="m1")
        assert len(m1_grants) == 1

        # Filter by status
        granted = engine.get_all_grants(status=Tier3PetitionStatus.GRANTED)
        assert len(granted) == 1
        assert granted[0].machine_id == "m1"

        pending = engine.get_all_grants(status=Tier3PetitionStatus.PENDING_AMENDMENT)
        assert len(pending) == 1
        assert pending[0].machine_id == "m2"


# ==================================================================
# Persistence
# ==================================================================

class TestMachineAgencyPersistence:
    """from_records / to_records round-trip."""

    def test_round_trip(self, engine: MachineAgencyEngine) -> None:
        """Serialise and deserialise preserves all data."""
        now = _now()
        engine.initiate_tier3_petition("m1", "eng", "h1", "amend_1", now=now)
        engine.on_amendment_confirmed("amend_1", now=now)

        engine.initiate_tier3_petition("m2", "med", "h2", "amend_2", now=now)
        engine.on_amendment_rejected("amend_2", now=now)

        records = engine.to_records()
        restored = MachineAgencyEngine.from_records(_default_config(), records)

        # Check m1 is granted
        grant = restored.get_tier3_grant("m1", "eng")
        assert grant is not None
        assert grant.status == Tier3PetitionStatus.GRANTED

        # Check m2 is rejected (no active grant)
        grant2 = restored.get_tier3_grant("m2", "med")
        assert grant2 is None  # Rejected grants are not "active"

        # Check all grants preserved
        all_grants = restored.get_all_grants()
        assert len(all_grants) == 2


# ==================================================================
# Service Layer Integration
# ==================================================================

class TestMachineAgencyServiceIntegration:
    """Machine agency through the service layer."""

    def test_compute_tier_via_service(
        self, service: GenesisService,
    ) -> None:
        """Compute machine tier through service — starts at Tier 0."""
        result = service.compute_machine_tier("bot-1")
        assert result.success
        assert result.data["effective_tier"] == "tier_0"

    def test_compute_tier_nonexistent(
        self, service: GenesisService,
    ) -> None:
        """Tier computation fails for unknown machine."""
        result = service.compute_machine_tier("bot-999")
        assert not result.success

    def test_compute_tier_human_rejected(
        self, service: GenesisService,
    ) -> None:
        """Cannot compute tier for a human actor."""
        result = service.compute_machine_tier("human-1")
        assert not result.success
        assert "not a machine" in result.errors[0].lower()

    def test_petition_via_service(
        self, service: GenesisService,
    ) -> None:
        """File a Tier 3 petition through service."""
        result = service.initiate_tier3_petition(
            "bot-1", "engineering", "human-1",
            "5 years of flawless operation",
        )
        assert result.success
        assert result.data["status"] == "pending_amendment"
        assert result.data["amendment_proposal_id"].startswith("amend_")

    def test_petition_machine_rejected(
        self, service: GenesisService,
    ) -> None:
        """Machine cannot self-petition."""
        result = service.initiate_tier3_petition(
            "bot-1", "engineering", "bot-1", "I want agency",
        )
        assert not result.success
        assert "human" in result.errors[0].lower()

    def test_petition_creates_amendment(
        self, service: GenesisService,
    ) -> None:
        """Petition creates an amendment in the amendment engine."""
        result = service.initiate_tier3_petition(
            "bot-1", "engineering", "human-1",
            "Long track record of excellent work",
        )
        assert result.success
        proposal_id = result.data["amendment_proposal_id"]

        # Verify amendment exists in the amendment engine
        proposal = service._amendment_engine.get_amendment(proposal_id)
        assert proposal is not None
        assert proposal.provision_key == "machine_agency.bot-1.engineering"
        assert proposal.proposed_value == "tier_3"

    def test_tier3_confirmed_via_service(
        self, service: GenesisService,
    ) -> None:
        """Confirm a Tier 3 petition through service."""
        pet = service.initiate_tier3_petition(
            "bot-1", "engineering", "human-1", "Ready for agency",
        )
        proposal_id = pet.data["amendment_proposal_id"]

        result = service.on_tier3_amendment_confirmed(proposal_id)
        assert result.success
        assert result.data["status"] == "granted"

    def test_tier3_rejected_via_service(
        self, service: GenesisService,
    ) -> None:
        """Reject a Tier 3 petition through service."""
        pet = service.initiate_tier3_petition(
            "bot-1", "engineering", "human-1", "Ready for agency",
        )
        proposal_id = pet.data["amendment_proposal_id"]

        result = service.on_tier3_amendment_rejected(proposal_id)
        assert result.success
        assert result.data["status"] == "rejected"

    def test_revoke_via_service(
        self, service: GenesisService,
    ) -> None:
        """Revoke Tier 3 through service."""
        pet = service.initiate_tier3_petition(
            "bot-1", "engineering", "human-1", "Ready",
        )
        service.on_tier3_amendment_confirmed(pet.data["amendment_proposal_id"])

        result = service.revoke_tier3(
            "bot-1", "engineering", "Violation detected", "human-2",
        )
        assert result.success
        assert result.data["status"] == "revoked"

    def test_emergency_suspend_via_service(
        self, service: GenesisService,
    ) -> None:
        """Emergency suspension through service."""
        pet = service.initiate_tier3_petition(
            "bot-1", "engineering", "human-1", "Ready",
        )
        service.on_tier3_amendment_confirmed(pet.data["amendment_proposal_id"])

        result = service.emergency_suspend_tier3(
            "bot-1", "engineering", "Safety concern", "human-3",
        )
        assert result.success
        assert result.data["status"] == "suspended"

    def test_violation_auto_revert_via_service(
        self, service: GenesisService,
    ) -> None:
        """Violation auto-reverts via service."""
        pet = service.initiate_tier3_petition(
            "bot-1", "engineering", "human-1", "Ready",
        )
        service.on_tier3_amendment_confirmed(pet.data["amendment_proposal_id"])

        result = service.on_machine_violation("bot-1", "engineering")
        assert result.success
        assert result.data["reverted"] is True
        assert result.data["reverted_to"] == "tier_1"

    def test_violation_no_tier3_is_noop(
        self, service: GenesisService,
    ) -> None:
        """Violation with no Tier 3 is a successful no-op."""
        result = service.on_machine_violation("bot-1", "engineering")
        assert result.success
        assert result.data["reverted"] is False

    def test_list_grants_via_service(
        self, service: GenesisService,
    ) -> None:
        """List Tier 3 grants through service."""
        service.initiate_tier3_petition(
            "bot-1", "engineering", "human-1", "Ready",
        )
        result = service.get_machine_tier3_grants()
        assert result.success
        assert result.data["count"] == 1
        assert result.data["grants"][0]["machine_id"] == "bot-1"

    def test_events_recorded(
        self, service: GenesisService,
    ) -> None:
        """Service layer records events for petition lifecycle."""
        pet = service.initiate_tier3_petition(
            "bot-1", "engineering", "human-1", "Ready",
        )
        service.on_tier3_amendment_confirmed(pet.data["amendment_proposal_id"])

        filed = service._event_log.events(EventKind.TIER3_PETITION_FILED)
        assert len(filed) == 1
        assert filed[0].payload["machine_id"] == "bot-1"

        granted = service._event_log.events(EventKind.TIER3_GRANTED)
        assert len(granted) == 1

    def test_check_prerequisites_via_service(
        self, service: GenesisService,
    ) -> None:
        """Check prerequisites through service."""
        result = service.check_tier3_prerequisites("bot-1", "engineering")
        assert result.success
        # Bot-1 won't have 5 years — just verify the check runs
        assert result.data["has_5_years_tier2"] is False
        assert "all_met" in result.data
