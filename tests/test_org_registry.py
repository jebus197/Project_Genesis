"""Tests for the Organisation Registry — Phase F-2: coordination structures.

Proves constitutional invariants:
- Organisations cannot make binding governance decisions (design test #67).
- Organisational roles grant no additional governance power (design test #68).
- Membership cannot be purchased, transferred, or inherited (design test #69).

Also covers:
- Organisation creation and validation
- Member nomination lifecycle
- Attestation-based membership promotion
- Verification tier progression (SELF_DECLARED → ATTESTED → VERIFIED)
- Member removal
- Founder removal protection
- Machine member nomination (human-only nomination)
- Persistence round-trip (from_records / to_records)
- Service layer integration (with event logging)

Design test #67: Can an organisation make a binding governance decision
(GCF disbursement, constitutional amendment) outside existing
constitutional mechanisms? If yes, reject design.

Design test #68: Can a member's organisational role (CEO, manager, etc.)
grant them additional governance power within Genesis?
If yes, reject design.

Design test #69: Can organisational membership be purchased, transferred,
or inherited? If yes, reject design.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from genesis.governance.org_registry import (
    ATTESTATION_THRESHOLD,
    VERIFIED_MIN_AVG_TRUST,
    VERIFIED_MIN_MEMBERS,
    OrgMember,
    OrgMemberAttestation,
    OrgMembershipStatus,
    OrgRegistryEngine,
    OrgVerificationTier,
    Organisation,
)
from genesis.models.trust import ActorKind
from genesis.persistence.event_log import EventKind, EventLog
from genesis.policy.resolver import PolicyResolver
from genesis.service import GenesisService

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _now() -> datetime:
    return datetime(2026, 2, 20, 12, 0, 0, tzinfo=timezone.utc)


def _default_config() -> dict[str, Any]:
    return {
        "attestation_count_required": 3,
        "verified_min_members": 10,
        "verified_min_avg_trust": 0.50,
    }


def _make_service(resolver: PolicyResolver) -> GenesisService:
    """Create a GenesisService with standard actors for Org Registry tests."""
    svc = GenesisService(resolver, event_log=EventLog())
    svc.open_epoch()
    # Register enough actors for full attestation + tier progression
    for i in range(1, 15):
        region = ["eu", "us", "asia", "af"][i % 4]
        org = ["acme", "beta", "gamma", "delta"][i % 4]
        svc.register_actor(
            f"human-{i}", ActorKind.HUMAN, region, org, initial_trust=0.65,
        )
    # Register a machine actor
    svc.register_machine(
        "bot-1", operator_id="human-1", region="eu", organization="acme",
        model_family="gpt", method_type="reasoning_model",
    )
    return svc


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def engine() -> OrgRegistryEngine:
    return OrgRegistryEngine(_default_config())


@pytest.fixture
def service(resolver: PolicyResolver) -> GenesisService:
    return _make_service(resolver)


# ==================================================================
# Design test #67: No binding governance decisions
# ==================================================================

class TestDesignTest67NoBindingGovernance:
    """Organisations cannot make binding governance decisions."""

    def test_organisation_has_no_governance_power_field(self) -> None:
        """Organisation dataclass has no governance_power, votes, binding,
        or decision fields — structural guarantee."""
        field_names = {f.name for f in dataclasses.fields(Organisation)}
        forbidden = {"governance_power", "votes", "binding", "decision",
                     "authority", "quorum", "ballot"}
        overlap = field_names & forbidden
        assert overlap == set(), f"Organisation has forbidden governance fields: {overlap}"

    def test_engine_has_no_governance_methods(self) -> None:
        """OrgRegistryEngine has no methods for making governance decisions."""
        engine = OrgRegistryEngine(_default_config())
        method_names = [m for m in dir(engine) if not m.startswith("_")]
        governance_terms = {"vote", "ballot", "quorum", "decide", "amend",
                           "constitutional", "disburse"}
        for method in method_names:
            for term in governance_terms:
                assert term not in method.lower(), (
                    f"Engine method '{method}' contains governance term '{term}'"
                )

    def test_org_member_has_no_voting_field(self) -> None:
        """OrgMember has no voting or governance power field."""
        field_names = {f.name for f in dataclasses.fields(OrgMember)}
        forbidden = {"vote_weight", "governance_power", "voting_rights",
                     "ballot", "authority"}
        overlap = field_names & forbidden
        assert overlap == set(), f"OrgMember has forbidden fields: {overlap}"


# ==================================================================
# Design test #68: No organisational role grants governance power
# ==================================================================

class TestDesignTest68NoOrgRolePower:
    """Organisational roles grant no additional governance power."""

    def test_org_member_has_no_role_field(self) -> None:
        """OrgMember has no 'role', 'title', 'position', or 'rank' field.

        CEO and cleaner are constitutionally equal. The data model
        enforces this by having no mechanism to represent organisational
        hierarchy.
        """
        field_names = {f.name for f in dataclasses.fields(OrgMember)}
        forbidden = {"role", "title", "position", "rank", "hierarchy",
                     "level", "seniority", "privilege"}
        overlap = field_names & forbidden
        assert overlap == set(), f"OrgMember has forbidden role fields: {overlap}"

    def test_organisation_has_no_hierarchy_field(self) -> None:
        """Organisation has no hierarchy, leadership, or role structure."""
        field_names = {f.name for f in dataclasses.fields(Organisation)}
        forbidden = {"hierarchy", "leadership", "roles", "ceo",
                     "board", "executives", "management"}
        overlap = field_names & forbidden
        assert overlap == set(), f"Organisation has forbidden hierarchy fields: {overlap}"

    def test_all_members_structurally_equal(self, engine: OrgRegistryEngine) -> None:
        """All members have exactly the same data structure — no differentiation
        between founder, CEO, manager, or cleaner."""
        now = _now()
        org = engine.create_organisation("h1", "human", "TestOrg", "Testing", now=now)

        # Add a second member
        engine.nominate_member(org.org_id, "h2", "human", "h1", now=now)

        founder = org.members["h1"]
        nominee = org.members["h2"]

        # Both have exactly the same set of fields
        founder_fields = {f.name for f in dataclasses.fields(founder)}
        nominee_fields = {f.name for f in dataclasses.fields(nominee)}
        assert founder_fields == nominee_fields


# ==================================================================
# Design test #69: Membership not purchasable/transferable/inheritable
# ==================================================================

class TestDesignTest69NoPurchasableMembership:
    """Membership cannot be purchased, transferred, or inherited."""

    def test_attestation_has_no_payment_field(self) -> None:
        """OrgMemberAttestation has no payment, transfer, or purchase field."""
        field_names = {f.name for f in dataclasses.fields(OrgMemberAttestation)}
        forbidden = {"payment", "price", "fee", "transfer", "purchase",
                     "inherit", "inheritance", "token"}
        overlap = field_names & forbidden
        assert overlap == set(), f"Attestation has forbidden fields: {overlap}"

    def test_org_member_has_no_transfer_field(self) -> None:
        """OrgMember has no transfer, purchase, or inheritance mechanism."""
        field_names = {f.name for f in dataclasses.fields(OrgMember)}
        forbidden = {"transfer_to", "purchased_from", "inherited_from",
                     "transferable", "sellable", "tradeable"}
        overlap = field_names & forbidden
        assert overlap == set(), f"OrgMember has forbidden transfer fields: {overlap}"

    def test_engine_has_no_transfer_methods(self) -> None:
        """OrgRegistryEngine has no methods for transferring or selling membership."""
        engine = OrgRegistryEngine(_default_config())
        method_names = [m for m in dir(engine) if not m.startswith("_")]
        forbidden = {"transfer", "sell", "buy", "purchase", "trade", "inherit"}
        for method in method_names:
            for term in forbidden:
                assert term not in method.lower(), (
                    f"Engine method '{method}' contains forbidden term '{term}'"
                )


# ==================================================================
# Organisation creation
# ==================================================================

class TestOrgCreation:
    """Organisation creation lifecycle."""

    def test_create_organisation(self, engine: OrgRegistryEngine) -> None:
        """Founder creates org at SELF_DECLARED tier."""
        org = engine.create_organisation("h1", "human", "Acme", "Do stuff", now=_now())
        assert org.org_id.startswith("org_")
        assert org.name == "Acme"
        assert org.purpose == "Do stuff"
        assert org.founder_id == "h1"
        assert org.tier == OrgVerificationTier.SELF_DECLARED
        assert org.member_count == 1  # founder
        assert "h1" in org.members
        assert org.members["h1"].status == OrgMembershipStatus.ATTESTED

    def test_create_requires_human_founder(self, engine: OrgRegistryEngine) -> None:
        """Machines cannot create organisations."""
        with pytest.raises(ValueError, match="human"):
            engine.create_organisation("m1", "machine", "BotCo", "Beep", now=_now())

    def test_create_requires_name(self, engine: OrgRegistryEngine) -> None:
        """Empty name is rejected."""
        with pytest.raises(ValueError, match="name"):
            engine.create_organisation("h1", "human", "", "Purpose", now=_now())

    def test_create_requires_purpose(self, engine: OrgRegistryEngine) -> None:
        """Empty purpose is rejected."""
        with pytest.raises(ValueError, match="purpose"):
            engine.create_organisation("h1", "human", "Acme", "", now=_now())

    def test_whitespace_name_rejected(self, engine: OrgRegistryEngine) -> None:
        """Whitespace-only name is rejected."""
        with pytest.raises(ValueError, match="name"):
            engine.create_organisation("h1", "human", "   ", "Purpose", now=_now())


# ==================================================================
# Member nomination
# ==================================================================

class TestMemberNomination:
    """Member nomination lifecycle."""

    def test_nominate_human_member(self, engine: OrgRegistryEngine) -> None:
        """Nominate a human member — starts as PENDING."""
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=_now())
        member = engine.nominate_member(org.org_id, "h2", "human", "h1", now=_now())
        assert member.actor_id == "h2"
        assert member.status == OrgMembershipStatus.PENDING
        assert member.nominated_by is None  # Only set for machines

    def test_nominate_machine_member(self, engine: OrgRegistryEngine) -> None:
        """Machine members require human nominator and record nominated_by."""
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=_now())
        member = engine.nominate_member(org.org_id, "m1", "machine", "h1", now=_now())
        assert member.actor_id == "m1"
        assert member.status == OrgMembershipStatus.PENDING
        assert member.nominated_by == "h1"

    def test_machine_cannot_nominate_machine(self, engine: OrgRegistryEngine) -> None:
        """Machines cannot nominate other machines."""
        now = _now()
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=now)
        # Add machine as attested member (manually for test)
        engine.nominate_member(org.org_id, "m1", "machine", "h1", now=now)
        org.members["m1"].status = OrgMembershipStatus.ATTESTED
        # Machine cannot nominate another machine
        with pytest.raises(ValueError, match="human"):
            engine.nominate_member(org.org_id, "m2", "machine", "m1", now=now)

    def test_duplicate_nomination_rejected(self, engine: OrgRegistryEngine) -> None:
        """Cannot nominate an actor who is already a member."""
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=_now())
        engine.nominate_member(org.org_id, "h2", "human", "h1", now=_now())
        with pytest.raises(ValueError, match="already"):
            engine.nominate_member(org.org_id, "h2", "human", "h1", now=_now())

    def test_nominator_must_be_attested(self, engine: OrgRegistryEngine) -> None:
        """Nominator must be an attested member."""
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=_now())
        engine.nominate_member(org.org_id, "h2", "human", "h1", now=_now())
        # h2 is PENDING — cannot nominate
        with pytest.raises(ValueError, match="attested"):
            engine.nominate_member(org.org_id, "h3", "human", "h2", now=_now())

    def test_nonexistent_org_rejected(self, engine: OrgRegistryEngine) -> None:
        """Nomination into nonexistent org is rejected."""
        with pytest.raises(ValueError, match="not found"):
            engine.nominate_member("org_fake", "h2", "human", "h1", now=_now())

    def test_removed_member_can_be_renominated(self, engine: OrgRegistryEngine) -> None:
        """A removed member can be re-nominated."""
        now = _now()
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=now)
        engine.nominate_member(org.org_id, "h2", "human", "h1", now=now)
        org.members["h2"].status = OrgMembershipStatus.REMOVED
        # Re-nomination should succeed
        member = engine.nominate_member(org.org_id, "h2", "human", "h1", now=now)
        assert member.status == OrgMembershipStatus.PENDING


# ==================================================================
# Attestation and membership promotion
# ==================================================================

class TestAttestation:
    """Attestation-based membership promotion."""

    def _setup_org_with_attestors(self, engine: OrgRegistryEngine) -> str:
        """Create org with founder + 3 attested members for attestation tests."""
        now = _now()
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=now)

        # Manually add attested members for attestation capability
        for i in range(2, 5):
            engine.nominate_member(org.org_id, f"h{i}", "human", "h1", now=now)
            org.members[f"h{i}"].status = OrgMembershipStatus.ATTESTED

        return org.org_id

    def test_attest_member(self, engine: OrgRegistryEngine) -> None:
        """Single attestation is recorded."""
        org_id = self._setup_org_with_attestors(engine)
        engine.nominate_member(org_id, "h5", "human", "h1", now=_now())

        member = engine.attest_member(
            org_id, "h5", "h1", 0.70, "Verified identity", 0.60, now=_now(),
        )
        assert member.attestation_count == 1
        assert member.status == OrgMembershipStatus.PENDING  # needs 3

    def test_promote_on_threshold(self, engine: OrgRegistryEngine) -> None:
        """Member promoted to ATTESTED after 3 attestations."""
        org_id = self._setup_org_with_attestors(engine)
        engine.nominate_member(org_id, "h5", "human", "h1", now=_now())

        for attestor in ["h1", "h2", "h3"]:
            member = engine.attest_member(
                org_id, "h5", attestor, 0.70, "Evidence", 0.60, now=_now(),
            )

        assert member.attestation_count == 3
        assert member.status == OrgMembershipStatus.ATTESTED

    def test_self_attestation_rejected(self, engine: OrgRegistryEngine) -> None:
        """Cannot attest your own membership."""
        org_id = self._setup_org_with_attestors(engine)
        engine.nominate_member(org_id, "h5", "human", "h1", now=_now())
        # Force h5 to be attested for self-attest attempt
        with pytest.raises(ValueError, match="own"):
            engine.attest_member(
                org_id, "h1", "h1", 0.70, "Self", 0.60, now=_now(),
            )

    def test_low_trust_attestor_rejected(self, engine: OrgRegistryEngine) -> None:
        """Attestor below tau_vote threshold is rejected."""
        org_id = self._setup_org_with_attestors(engine)
        engine.nominate_member(org_id, "h5", "human", "h1", now=_now())

        with pytest.raises(ValueError, match="below"):
            engine.attest_member(
                org_id, "h5", "h1", 0.40, "Evidence", 0.60, now=_now(),
            )

    def test_duplicate_attestation_rejected(self, engine: OrgRegistryEngine) -> None:
        """Same attestor cannot attest the same member twice."""
        org_id = self._setup_org_with_attestors(engine)
        engine.nominate_member(org_id, "h5", "human", "h1", now=_now())

        engine.attest_member(org_id, "h5", "h1", 0.70, "First", 0.60, now=_now())
        with pytest.raises(ValueError, match="already"):
            engine.attest_member(org_id, "h5", "h1", 0.70, "Second", 0.60, now=_now())

    def test_attest_removed_member_rejected(self, engine: OrgRegistryEngine) -> None:
        """Cannot attest a removed member."""
        org_id = self._setup_org_with_attestors(engine)
        engine.nominate_member(org_id, "h5", "human", "h1", now=_now())
        engine.remove_member(org_id, "h5")
        with pytest.raises(ValueError, match="removed"):
            engine.attest_member(
                org_id, "h5", "h1", 0.70, "Evidence", 0.60, now=_now(),
            )


# ==================================================================
# Member removal
# ==================================================================

class TestMemberRemoval:
    """Member removal lifecycle."""

    def test_remove_member(self, engine: OrgRegistryEngine) -> None:
        """Remove a member — status changes to REMOVED."""
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=_now())
        engine.nominate_member(org.org_id, "h2", "human", "h1", now=_now())
        member = engine.remove_member(org.org_id, "h2")
        assert member.status == OrgMembershipStatus.REMOVED

    def test_cannot_remove_founder(self, engine: OrgRegistryEngine) -> None:
        """Founder cannot be removed."""
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=_now())
        with pytest.raises(ValueError, match="founder"):
            engine.remove_member(org.org_id, "h1")

    def test_remove_nonexistent_member(self, engine: OrgRegistryEngine) -> None:
        """Removing nonexistent member raises."""
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=_now())
        with pytest.raises(ValueError, match="not found"):
            engine.remove_member(org.org_id, "h99")


# ==================================================================
# Verification tier progression
# ==================================================================

class TestTierProgression:
    """Verification tier calculation."""

    def test_new_org_is_self_declared(self, engine: OrgRegistryEngine) -> None:
        """New org starts at SELF_DECLARED."""
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=_now())
        assert org.tier == OrgVerificationTier.SELF_DECLARED

    def test_attested_tier_with_threshold_members(self, engine: OrgRegistryEngine) -> None:
        """Org becomes ATTESTED with 3+ attested members."""
        now = _now()
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=now)
        for i in range(2, 5):
            engine.nominate_member(org.org_id, f"h{i}", "human", "h1", now=now)
            org.members[f"h{i}"].status = OrgMembershipStatus.ATTESTED

        trusts = {f"h{i}": 0.5 for i in range(1, 5)}
        tier = engine.recalculate_tier(org.org_id, trusts)
        assert tier == OrgVerificationTier.ATTESTED

    def test_verified_tier_requires_10_members_and_high_trust(
        self, engine: OrgRegistryEngine,
    ) -> None:
        """Org becomes VERIFIED with 10+ attested members and avg trust >= 0.50."""
        now = _now()
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=now)
        for i in range(2, 12):
            engine.nominate_member(org.org_id, f"h{i}", "human", "h1", now=now)
            org.members[f"h{i}"].status = OrgMembershipStatus.ATTESTED

        trusts = {f"h{i}": 0.60 for i in range(1, 12)}
        tier = engine.recalculate_tier(org.org_id, trusts)
        assert tier == OrgVerificationTier.VERIFIED

    def test_verified_tier_fails_with_low_trust(
        self, engine: OrgRegistryEngine,
    ) -> None:
        """Verified tier not reached if average trust is below threshold."""
        now = _now()
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=now)
        for i in range(2, 12):
            engine.nominate_member(org.org_id, f"h{i}", "human", "h1", now=now)
            org.members[f"h{i}"].status = OrgMembershipStatus.ATTESTED

        # Average trust of 0.30 is below 0.50 threshold
        trusts = {f"h{i}": 0.30 for i in range(1, 12)}
        tier = engine.recalculate_tier(org.org_id, trusts)
        assert tier == OrgVerificationTier.ATTESTED  # falls back to ATTESTED

    def test_tier_downgrade_on_member_removal(
        self, engine: OrgRegistryEngine,
    ) -> None:
        """Tier recalculation after removals can downgrade tier."""
        now = _now()
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=now)
        # Add 3 members to reach ATTESTED
        for i in range(2, 5):
            engine.nominate_member(org.org_id, f"h{i}", "human", "h1", now=now)
            org.members[f"h{i}"].status = OrgMembershipStatus.ATTESTED

        trusts = {f"h{i}": 0.60 for i in range(1, 5)}
        tier = engine.recalculate_tier(org.org_id, trusts)
        assert tier == OrgVerificationTier.ATTESTED

        # Remove members below threshold
        engine.remove_member(org.org_id, "h2")
        engine.remove_member(org.org_id, "h3")

        trusts_after = {"h1": 0.60, "h4": 0.60}
        tier = engine.recalculate_tier(org.org_id, trusts_after)
        assert tier == OrgVerificationTier.SELF_DECLARED


# ==================================================================
# Listing and querying
# ==================================================================

class TestOrgListing:
    """Organisation listing and retrieval."""

    def test_list_all_orgs(self, engine: OrgRegistryEngine) -> None:
        """List all organisations sorted by creation time."""
        now = _now()
        engine.create_organisation("h1", "human", "Alpha", "First", now=now)
        later = now + timedelta(hours=1)
        engine.create_organisation("h2", "human", "Beta", "Second", now=later)

        orgs = engine.list_organisations()
        assert len(orgs) == 2
        # Most recent first
        assert orgs[0].name == "Beta"
        assert orgs[1].name == "Alpha"

    def test_list_filter_by_tier(self, engine: OrgRegistryEngine) -> None:
        """Filter organisations by verification tier."""
        now = _now()
        engine.create_organisation("h1", "human", "Alpha", "First", now=now)
        org2 = engine.create_organisation("h2", "human", "Beta", "Second", now=now)
        # Manually set tier
        org2.tier = OrgVerificationTier.ATTESTED

        result = engine.list_organisations(tier_filter=OrgVerificationTier.SELF_DECLARED)
        assert len(result) == 1
        assert result[0].name == "Alpha"

    def test_get_nonexistent_org(self, engine: OrgRegistryEngine) -> None:
        """Get nonexistent org returns None."""
        assert engine.get_organisation("org_fake") is None

    def test_is_verified_member(self, engine: OrgRegistryEngine) -> None:
        """Check verified membership status."""
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=_now())
        assert engine.is_verified_member(org.org_id, "h1") is True
        assert engine.is_verified_member(org.org_id, "h99") is False
        assert engine.is_verified_member("org_fake", "h1") is False


# ==================================================================
# Persistence round-trip
# ==================================================================

class TestOrgPersistence:
    """from_records / to_records round-trip."""

    def test_round_trip(self, engine: OrgRegistryEngine) -> None:
        """Serialise and deserialise preserves all data."""
        now = _now()
        org = engine.create_organisation("h1", "human", "Acme", "Test", now=now)
        engine.nominate_member(org.org_id, "h2", "human", "h1", now=now)
        engine.attest_member(org.org_id, "h2", "h1", 0.70, "Evidence", 0.60, now=now)

        records = engine.to_records()
        restored = OrgRegistryEngine.from_records(_default_config(), records)

        assert len(restored.list_organisations()) == 1
        restored_org = restored.list_organisations()[0]
        assert restored_org.name == "Acme"
        assert restored_org.founder_id == "h1"
        assert restored_org.tier == OrgVerificationTier.SELF_DECLARED
        assert "h1" in restored_org.members
        assert "h2" in restored_org.members
        assert restored_org.members["h2"].attestation_count == 1


# ==================================================================
# Service layer integration
# ==================================================================

class TestOrgServiceIntegration:
    """Organisation Registry through the service layer."""

    def test_create_org_via_service(self, service: GenesisService) -> None:
        """Create organisation through service layer."""
        result = service.create_organisation("human-1", "Test Org", "Testing")
        assert result.success
        assert result.data["name"] == "Test Org"
        assert result.data["tier"] == "self_declared"
        assert result.data["member_count"] == 1

    def test_create_org_requires_human(self, service: GenesisService) -> None:
        """Machine actors cannot create organisations via service."""
        result = service.create_organisation("bot-1", "BotOrg", "Beep")
        assert not result.success
        assert "human" in result.errors[0].lower()

    def test_create_org_rejects_unknown_actor(self, service: GenesisService) -> None:
        """Unknown actor cannot create organisations."""
        result = service.create_organisation("unknown", "Org", "Purpose")
        assert not result.success
        assert "not found" in result.errors[0].lower()

    def test_nominate_member_via_service(self, service: GenesisService) -> None:
        """Nominate a member through service layer."""
        create_result = service.create_organisation("human-1", "Acme", "Testing")
        org_id = create_result.data["org_id"]

        result = service.nominate_org_member(org_id, "human-2", "human-1")
        assert result.success
        assert result.data["status"] == "pending"

    def test_attest_member_via_service(self, service: GenesisService) -> None:
        """Attest a member through service layer — uses trust from roster."""
        create_result = service.create_organisation("human-1", "Acme", "Testing")
        org_id = create_result.data["org_id"]

        # Add enough attested members to be attestors
        for i in range(2, 5):
            service.nominate_org_member(org_id, f"human-{i}", "human-1")
            # Manually force attested status for testing
            service._org_registry_engine.get_organisation(org_id).members[
                f"human-{i}"
            ].status = OrgMembershipStatus.ATTESTED

        # Nominate and attest a new member
        service.nominate_org_member(org_id, "human-5", "human-1")
        result = service.attest_org_member(
            org_id, "human-5", "human-1", "Verified identity",
        )
        assert result.success
        assert result.data["attestation_count"] == 1

    def test_remove_member_via_service(self, service: GenesisService) -> None:
        """Remove a member through service layer."""
        create_result = service.create_organisation("human-1", "Acme", "Testing")
        org_id = create_result.data["org_id"]
        service.nominate_org_member(org_id, "human-2", "human-1")

        result = service.remove_org_member(org_id, "human-2")
        assert result.success
        assert result.data["status"] == "removed"

    def test_remove_founder_rejected_via_service(self, service: GenesisService) -> None:
        """Cannot remove founder via service."""
        create_result = service.create_organisation("human-1", "Acme", "Testing")
        org_id = create_result.data["org_id"]

        result = service.remove_org_member(org_id, "human-1")
        assert not result.success
        assert "founder" in result.errors[0].lower()

    def test_list_orgs_via_service(self, service: GenesisService) -> None:
        """List organisations through service layer."""
        service.create_organisation("human-1", "Alpha", "First")
        service.create_organisation("human-2", "Beta", "Second")

        result = service.list_organisations()
        assert result.success
        assert result.data["count"] == 2

    def test_list_orgs_with_tier_filter(self, service: GenesisService) -> None:
        """Filter organisations by tier via service."""
        service.create_organisation("human-1", "Alpha", "First")

        result = service.list_organisations(tier_filter="self_declared")
        assert result.success
        assert result.data["count"] == 1

        result = service.list_organisations(tier_filter="verified")
        assert result.success
        assert result.data["count"] == 0

    def test_get_org_via_service(self, service: GenesisService) -> None:
        """Retrieve organisation details through service layer."""
        create_result = service.create_organisation("human-1", "Acme", "Testing")
        org_id = create_result.data["org_id"]

        result = service.get_organisation(org_id)
        assert result.success
        assert result.data["name"] == "Acme"
        assert len(result.data["members"]) == 1

    def test_get_nonexistent_org_via_service(self, service: GenesisService) -> None:
        """Get nonexistent org returns error via service."""
        result = service.get_organisation("org_fake")
        assert not result.success
        assert "not found" in result.errors[0].lower()

    def test_org_events_emitted(self, service: GenesisService) -> None:
        """Organisation operations emit audit events."""
        result = service.create_organisation("human-1", "Acme", "Testing")
        org_id = result.data["org_id"]

        # Check ORG_CREATED event
        org_events = service._event_log.events(EventKind.ORG_CREATED)
        assert len(org_events) >= 1
        assert org_events[-1].actor_id == "human-1"

    def test_invalid_tier_filter_rejected(self, service: GenesisService) -> None:
        """Invalid tier filter returns error."""
        result = service.list_organisations(tier_filter="nonsense")
        assert not result.success
        assert "invalid" in result.errors[0].lower()
