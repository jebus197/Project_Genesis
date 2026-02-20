"""Organisation Registry Engine — coordination structures, not governance bodies.

Organisations allow people with shared interests to coordinate, develop proposals,
and organise operational work. Organisations have no constitutional governance
power — all governance decisions flow through the same mechanisms available to
any individual.

Architecture:
- OrgRegistryEngine handles creation, membership, attestation, and tier calculation.
- The service layer bridges the engine with roster, trust records, and events.
- Single-responsibility: the engine never touches actor records directly.

Constitutional constraints:
- Organisations cannot make binding governance decisions (design test #67).
- Organisational roles grant no additional governance power (design test #68).
- Membership cannot be purchased, transferred, or inherited (design test #69).
- CEO and cleaner are constitutionally equal — no org-level hierarchy.
- Machines may be nominated as members by human members only.
- Verification tiers: SELF_DECLARED → ATTESTED → VERIFIED.
- Organisation-scoped discussions follow Assembly identity rules.

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

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


class OrgVerificationTier(str, enum.Enum):
    """Verification status of an organisation.

    SELF_DECLARED: Created by founder, no external attestation.
    ATTESTED: 3+ high-trust members have attested to legitimacy.
    VERIFIED: 10+ attested members with average trust >= 0.50.
    """
    SELF_DECLARED = "self_declared"
    ATTESTED = "attested"
    VERIFIED = "verified"


class OrgMembershipStatus(str, enum.Enum):
    """Membership lifecycle state."""
    PENDING = "pending"      # Nominated but not yet attested
    ATTESTED = "attested"    # Fully attested (3+ attestations)
    REMOVED = "removed"


@dataclass(frozen=True)
class OrgMemberAttestation:
    """An attestation by an existing member vouching for a new member.

    STRUCTURAL INVARIANT: No 'payment' or 'transfer' field exists.
    Membership is earned through attestation, never purchased.
    """
    attestor_id: str
    attested_utc: datetime
    evidence_summary: str


@dataclass
class OrgMember:
    """A member of an organisation.

    STRUCTURAL INVARIANT: No 'role' field exists. CEO and cleaner are
    constitutionally equal within Genesis governance. The data model
    enforces this by having no mechanism to represent organisational
    hierarchy.
    """
    actor_id: str
    actor_kind: str  # "human" or "machine"
    status: OrgMembershipStatus
    attestations: list[OrgMemberAttestation] = field(default_factory=list)
    joined_utc: Optional[datetime] = None
    nominated_by: Optional[str] = None  # Required for machines

    @property
    def attestation_count(self) -> int:
        return len(self.attestations)


@dataclass
class Organisation:
    """An organisation in the Genesis registry.

    STRUCTURAL INVARIANT: No 'governance_power', 'votes', 'binding',
    'decision', or 'role' fields exist. Organisations are coordination
    structures, not governance bodies.
    """
    org_id: str
    name: str
    purpose: str
    founder_id: str
    tier: OrgVerificationTier
    created_utc: datetime
    members: dict[str, OrgMember] = field(default_factory=dict)

    @property
    def member_count(self) -> int:
        """Count of attested members (excludes pending and removed)."""
        return sum(
            1 for m in self.members.values()
            if m.status == OrgMembershipStatus.ATTESTED
        )


# Attestation threshold for membership confirmation
ATTESTATION_THRESHOLD = 3
# Verified tier requirements
VERIFIED_MIN_MEMBERS = 10
VERIFIED_MIN_AVG_TRUST = 0.50


class OrgRegistryEngine:
    """Organisation creation, membership, and verification engine.

    Manages the lifecycle of organisations from creation through
    membership attestation to verification tier progression.
    Never directly modifies actor records — that is the service layer's
    responsibility.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialise the Organisation Registry engine.

        Args:
            config: Registry configuration containing:
                - attestation_count_required (default 3)
                - verified_min_members (default 10)
                - verified_min_avg_trust (default 0.50)
        """
        self._config = config
        self._orgs: dict[str, Organisation] = {}
        self._attestation_threshold = config.get(
            "attestation_count_required", ATTESTATION_THRESHOLD
        )
        self._verified_min_members = config.get(
            "verified_min_members", VERIFIED_MIN_MEMBERS
        )
        self._verified_min_avg_trust = config.get(
            "verified_min_avg_trust", VERIFIED_MIN_AVG_TRUST
        )

    @classmethod
    def from_records(
        cls,
        config: dict[str, Any],
        orgs_data: list[dict[str, Any]],
    ) -> OrgRegistryEngine:
        """Restore engine state from persistence records."""
        engine = cls(config)
        for od in orgs_data:
            members: dict[str, OrgMember] = {}
            for mid, md in od.get("members", {}).items():
                attestations = [
                    OrgMemberAttestation(
                        attestor_id=a["attestor_id"],
                        attested_utc=datetime.fromisoformat(a["attested_utc"]),
                        evidence_summary=a["evidence_summary"],
                    )
                    for a in md.get("attestations", [])
                ]
                members[mid] = OrgMember(
                    actor_id=mid,
                    actor_kind=md["actor_kind"],
                    status=OrgMembershipStatus(md["status"]),
                    attestations=attestations,
                    joined_utc=(
                        datetime.fromisoformat(md["joined_utc"])
                        if md.get("joined_utc") else None
                    ),
                    nominated_by=md.get("nominated_by"),
                )
            org = Organisation(
                org_id=od["org_id"],
                name=od["name"],
                purpose=od["purpose"],
                founder_id=od["founder_id"],
                tier=OrgVerificationTier(od["tier"]),
                created_utc=datetime.fromisoformat(od["created_utc"]),
                members=members,
            )
            engine._orgs[org.org_id] = org
        return engine

    def create_organisation(
        self,
        founder_id: str,
        founder_kind: str,
        name: str,
        purpose: str,
        now: Optional[datetime] = None,
    ) -> Organisation:
        """Create a new organisation with the founder as sole member.

        Args:
            founder_id: The verified human creating the organisation.
            founder_kind: Must be "human" — machines cannot found orgs.
            name: Organisation name.
            purpose: Stated purpose.
            now: Current UTC time.

        Returns:
            The newly created Organisation (SELF_DECLARED tier).

        Raises:
            ValueError: If name/purpose empty or founder is not human.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        if founder_kind != "human":
            raise ValueError("Only human actors can create organisations")
        if not name or not name.strip():
            raise ValueError("Organisation name cannot be empty")
        if not purpose or not purpose.strip():
            raise ValueError("Organisation purpose cannot be empty")

        org_id = f"org_{uuid.uuid4().hex[:12]}"

        # Founder is automatically an attested member
        founder_member = OrgMember(
            actor_id=founder_id,
            actor_kind="human",
            status=OrgMembershipStatus.ATTESTED,
            attestations=[],  # Founder doesn't need attestation
            joined_utc=now,
        )

        org = Organisation(
            org_id=org_id,
            name=name.strip(),
            purpose=purpose.strip(),
            founder_id=founder_id,
            tier=OrgVerificationTier.SELF_DECLARED,
            created_utc=now,
            members={founder_id: founder_member},
        )

        self._orgs[org_id] = org
        return org

    def nominate_member(
        self,
        org_id: str,
        actor_id: str,
        actor_kind: str,
        nominator_id: str,
        now: Optional[datetime] = None,
    ) -> OrgMember:
        """Nominate an actor for membership in an organisation.

        For machine actors, the nominator must be a human member.

        Args:
            org_id: Target organisation.
            actor_id: Actor to nominate.
            actor_kind: "human" or "machine".
            nominator_id: Existing member making the nomination.
            now: Current UTC time.

        Returns:
            The new PENDING member.

        Raises:
            ValueError: If org/nominator not found, actor already member,
                or machine nominated by non-human.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        org = self._orgs.get(org_id)
        if org is None:
            raise ValueError(f"Organisation not found: {org_id}")

        # Nominator must be an attested member
        nominator = org.members.get(nominator_id)
        if nominator is None or nominator.status != OrgMembershipStatus.ATTESTED:
            raise ValueError(
                f"Nominator {nominator_id} is not an attested member "
                f"of {org_id}"
            )

        # Machine nomination must come from human member
        if actor_kind == "machine" and nominator.actor_kind != "human":
            raise ValueError(
                "Machine members can only be nominated by human members"
            )

        # Check if already a member
        if actor_id in org.members:
            existing = org.members[actor_id]
            if existing.status != OrgMembershipStatus.REMOVED:
                raise ValueError(
                    f"Actor {actor_id} is already a member of {org_id}"
                )

        member = OrgMember(
            actor_id=actor_id,
            actor_kind=actor_kind,
            status=OrgMembershipStatus.PENDING,
            joined_utc=now,
            nominated_by=nominator_id if actor_kind == "machine" else None,
        )

        org.members[actor_id] = member
        return member

    def attest_member(
        self,
        org_id: str,
        member_id: str,
        attestor_id: str,
        attestor_trust: float,
        evidence_summary: str,
        tau_vote: float,
        now: Optional[datetime] = None,
    ) -> OrgMember:
        """Attest a pending member's legitimacy.

        Attestors must be existing attested members with trust >= tau_vote.
        When attestation count reaches the threshold, the member is
        promoted to ATTESTED status and the org tier is recalculated.

        Args:
            org_id: Target organisation.
            member_id: The member being attested.
            attestor_id: The existing member providing attestation.
            attestor_trust: Attestor's current trust score.
            evidence_summary: Brief evidence of legitimacy.
            tau_vote: Minimum trust threshold for attestors.
            now: Current UTC time.

        Returns:
            The updated member.

        Raises:
            ValueError: If validation fails.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        org = self._orgs.get(org_id)
        if org is None:
            raise ValueError(f"Organisation not found: {org_id}")

        member = org.members.get(member_id)
        if member is None:
            raise ValueError(
                f"Member {member_id} not found in {org_id}"
            )
        if member.status == OrgMembershipStatus.REMOVED:
            raise ValueError(
                f"Member {member_id} has been removed from {org_id}"
            )

        # Attestor must be attested member
        attestor = org.members.get(attestor_id)
        if attestor is None or attestor.status != OrgMembershipStatus.ATTESTED:
            raise ValueError(
                f"Attestor {attestor_id} is not an attested member of {org_id}"
            )

        # Self-attestation not allowed
        if attestor_id == member_id:
            raise ValueError("Cannot attest your own membership")

        # Trust threshold check
        if attestor_trust < tau_vote:
            raise ValueError(
                f"Attestor trust {attestor_trust:.2f} is below "
                f"threshold {tau_vote:.2f}"
            )

        # No duplicate attestation from same attestor
        for existing in member.attestations:
            if existing.attestor_id == attestor_id:
                raise ValueError(
                    f"Attestor {attestor_id} has already attested "
                    f"member {member_id}"
                )

        attestation = OrgMemberAttestation(
            attestor_id=attestor_id,
            attested_utc=now,
            evidence_summary=evidence_summary,
        )
        member.attestations.append(attestation)

        # Promote to ATTESTED if threshold met
        if (
            member.status == OrgMembershipStatus.PENDING
            and member.attestation_count >= self._attestation_threshold
        ):
            member.status = OrgMembershipStatus.ATTESTED

        return member

    def remove_member(
        self,
        org_id: str,
        member_id: str,
        now: Optional[datetime] = None,
    ) -> OrgMember:
        """Remove a member from an organisation.

        Args:
            org_id: Target organisation.
            member_id: The member to remove.
            now: Current UTC time.

        Returns:
            The updated member with REMOVED status.

        Raises:
            ValueError: If org/member not found or founder being removed.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        org = self._orgs.get(org_id)
        if org is None:
            raise ValueError(f"Organisation not found: {org_id}")

        member = org.members.get(member_id)
        if member is None:
            raise ValueError(
                f"Member {member_id} not found in {org_id}"
            )
        if member_id == org.founder_id:
            raise ValueError(
                "Cannot remove the founder from the organisation"
            )

        member.status = OrgMembershipStatus.REMOVED
        return member

    def recalculate_tier(
        self,
        org_id: str,
        member_trusts: dict[str, float],
    ) -> OrgVerificationTier:
        """Recalculate the verification tier of an organisation.

        Args:
            org_id: Target organisation.
            member_trusts: Dict of actor_id → current trust score for
                all attested members.

        Returns:
            The new tier (may be unchanged).

        Raises:
            ValueError: If org not found.
        """
        org = self._orgs.get(org_id)
        if org is None:
            raise ValueError(f"Organisation not found: {org_id}")

        attested_members = [
            m for m in org.members.values()
            if m.status == OrgMembershipStatus.ATTESTED
        ]
        attested_count = len(attested_members)

        if attested_count >= self._verified_min_members:
            # Calculate average trust of attested members
            trusts = [
                member_trusts.get(m.actor_id, 0.0)
                for m in attested_members
            ]
            avg_trust = sum(trusts) / len(trusts) if trusts else 0.0
            if avg_trust >= self._verified_min_avg_trust:
                org.tier = OrgVerificationTier.VERIFIED
                return org.tier

        if attested_count >= self._attestation_threshold:
            org.tier = OrgVerificationTier.ATTESTED
            return org.tier

        org.tier = OrgVerificationTier.SELF_DECLARED
        return org.tier

    def get_organisation(self, org_id: str) -> Optional[Organisation]:
        """Retrieve an organisation by ID."""
        return self._orgs.get(org_id)

    def list_organisations(
        self,
        tier_filter: Optional[OrgVerificationTier] = None,
    ) -> list[Organisation]:
        """List organisations, optionally filtered by tier."""
        orgs = list(self._orgs.values())
        if tier_filter is not None:
            orgs = [o for o in orgs if o.tier == tier_filter]
        orgs.sort(key=lambda o: o.created_utc, reverse=True)
        return orgs

    def is_verified_member(self, org_id: str, actor_id: str) -> bool:
        """Check if an actor is an attested member of an organisation."""
        org = self._orgs.get(org_id)
        if org is None:
            return False
        member = org.members.get(actor_id)
        if member is None:
            return False
        return member.status == OrgMembershipStatus.ATTESTED

    def to_records(self) -> list[dict[str, Any]]:
        """Serialise all organisations for persistence."""
        records: list[dict[str, Any]] = []
        for org in self._orgs.values():
            members_data: dict[str, dict[str, Any]] = {}
            for mid, m in org.members.items():
                attestations_data = [
                    {
                        "attestor_id": a.attestor_id,
                        "attested_utc": a.attested_utc.isoformat(),
                        "evidence_summary": a.evidence_summary,
                    }
                    for a in m.attestations
                ]
                members_data[mid] = {
                    "actor_kind": m.actor_kind,
                    "status": m.status.value,
                    "attestations": attestations_data,
                    "joined_utc": (
                        m.joined_utc.isoformat() if m.joined_utc else None
                    ),
                    "nominated_by": m.nominated_by,
                }
            records.append({
                "org_id": org.org_id,
                "name": org.name,
                "purpose": org.purpose,
                "founder_id": org.founder_id,
                "tier": org.tier.value,
                "created_utc": org.created_utc.isoformat(),
                "members": members_data,
            })
        return records
