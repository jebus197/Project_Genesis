"""Machine Agency Tier Integration — the evolution principle in code.

Implements the four-tier machine participation pathway defined in the
constitution. Each tier demands more demonstrated capability, more verified
trust, and more rigorous oversight than the last.

Tiers:
    0: Registered — machine exists in roster but has no domain clearance.
    1: Domain Clearance — supervised operation in a specific domain
       (via DomainExpertEngine, 3+ experts, trust ≥ 0.60).
    2: Autonomous Operation — unsupervised in a domain
       (via DomainExpertEngine, 5+ experts, trust ≥ 0.70, machine trust ≥ 0.60).
    3: Autonomous Domain Agency — constitutional responsibility transfer.
       Two pathways: (a) First-of-class constitutional amendment establishes
       that machines of a defined functional-capability class are eligible.
       (b) Subsequent machines of an approved class apply through procedural
       domain-expert verification. Individual one-off petitions via full
       amendment remain valid for machines outside any recognised class.
    4: Extended Domain Agency — Tier 3 across multiple domains.
       Each domain independently qualified. No "general" agency.

Constitutional invariants:
    - MACHINE_VOTING_EXCLUSION is entrenched — Tier 3 does NOT grant voting.
    - Machine cannot self-petition for Tier 3 (human operator required).
    - Violation auto-reverts to Tier 1 (supervised), not Tier 0.
    - Pathway exists — the constitution does not foreclose evolution.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


# ──────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────

class MachineTier(str, enum.Enum):
    """Machine participation tier."""
    TIER_0 = "tier_0"   # Registered, no clearance
    TIER_1 = "tier_1"   # Domain clearance (supervised)
    TIER_2 = "tier_2"   # Autonomous operation
    TIER_3 = "tier_3"   # Autonomous domain agency
    TIER_4 = "tier_4"   # Extended domain agency (multi-domain Tier 3)


class Tier3PetitionStatus(str, enum.Enum):
    """Status of a Tier 3 agency petition."""
    PENDING_AMENDMENT = "pending_amendment"  # Amendment created, voting in progress
    GRANTED = "granted"                      # Amendment confirmed, agency active
    REJECTED = "rejected"                    # Amendment rejected
    REVOKED = "revoked"                      # Agency revoked (violation or amendment)
    SUSPENDED = "suspended"                  # Emergency suspension pending adjudication


class Tier3ClassStatus(str, enum.Enum):
    """Status of a Tier 3 functional-capability class eligibility."""
    PENDING_AMENDMENT = "pending_amendment"  # Class amendment in progress
    APPROVED = "approved"                    # Class is constitutionally eligible
    REJECTED = "rejected"                    # Class amendment rejected
    REVOKED = "revoked"                      # Class eligibility revoked by new amendment


# ──────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────

# Tier 3 prerequisites (constitutional requirements)
TIER3_MIN_YEARS_AT_TIER2 = 5
TIER3_MIN_DOMAIN_TRUST = 0.70
TIER3_ZERO_VIOLATIONS = True  # Any violation resets the clock

# Tier 3 provision key prefix — amendments use this pattern
TIER3_PROVISION_KEY_PREFIX = "machine_agency"

# Tier 3 CLASS provision key prefix — class-level amendments use this pattern
TIER3_CLASS_PROVISION_KEY_PREFIX = "machine_agency_class"


# ──────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Tier3Prerequisite:
    """Snapshot of Tier 3 prerequisite checks for a machine+domain.

    All fields must be True for a petition to proceed.
    """
    machine_id: str
    domain: str
    has_5_years_tier2: bool
    domain_trust_above_threshold: bool
    zero_violations: bool
    unbroken_reauth_chain: bool
    checked_utc: datetime

    @property
    def all_met(self) -> bool:
        return (
            self.has_5_years_tier2
            and self.domain_trust_above_threshold
            and self.zero_violations
            and self.unbroken_reauth_chain
        )


@dataclass
class Tier3Grant:
    """Record of a Tier 3 autonomous domain agency grant.

    Created either when a constitutional amendment confirms the petition
    (grant_pathway="amendment") or through procedural verification under
    an approved functional-capability class (grant_pathway="procedural").
    """
    grant_id: str
    machine_id: str
    domain: str
    petition_id: str          # The amendment proposal_id
    petitioner_id: str        # Human operator who filed the petition
    status: Tier3PetitionStatus
    granted_utc: Optional[datetime] = None
    revoked_utc: Optional[datetime] = None
    revocation_reason: Optional[str] = None
    class_grant_id: Optional[str] = None  # Set if granted via class pathway
    grant_pathway: str = "amendment"       # "amendment" or "procedural"
    created_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Structural guarantees: NO governance, voting, or constitutional power fields.
    # Tier 3 is operational agency only.


@dataclass
class Tier3ClassGrant:
    """Record of a constitutional class-level Tier 3 eligibility approval.

    Created when a first-of-class amendment petition is filed.
    The class is defined by functional capability — what the machine
    demonstrably does — not by architecture or model family.

    Once APPROVED, individual machines of this class can gain Tier 3
    through procedural verification without a separate amendment.
    """
    class_id: str
    domain: str
    functional_capability_description: str
    status: Tier3ClassStatus
    amendment_proposal_id: str
    petitioner_id: str        # Human sponsor who filed the class petition
    approved_utc: Optional[datetime] = None
    revoked_utc: Optional[datetime] = None
    revocation_reason: Optional[str] = None
    created_utc: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ──────────────────────────────────────────────────────────────────
# Engine
# ──────────────────────────────────────────────────────────────────

class MachineAgencyEngine:
    """Computes machine agency tiers and manages Tier 3 petitions.

    Tier 0/1/2 are derived from DomainExpertEngine state (clearances).
    Tier 3 requires a constitutional amendment petition.
    Tier 4 is computed from multiple Tier 3 grants.

    This engine does NOT:
    - Grant voting power (MACHINE_VOTING_EXCLUSION is entrenched)
    - Allow self-petition (machine cannot initiate its own Tier 3)
    - Bypass the amendment process for first-of-class eligibility
    - Grant procedural Tier 3 without a constitutionally approved class
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._tier3_grants: dict[str, Tier3Grant] = {}  # grant_id → Tier3Grant
        self._tier3_class_grants: dict[str, Tier3ClassGrant] = {}  # class_id → Tier3ClassGrant
        self._min_years = config.get("tier3_min_years_at_tier2", TIER3_MIN_YEARS_AT_TIER2)
        self._min_domain_trust = config.get("tier3_min_domain_trust", TIER3_MIN_DOMAIN_TRUST)

    def compute_current_tier(
        self,
        machine_id: str,
        active_clearances: list[dict[str, Any]],
    ) -> dict[str, MachineTier]:
        """Compute the current tier for a machine across all domains.

        Args:
            machine_id: The machine to evaluate.
            active_clearances: List of active clearance dicts from
                DomainExpertEngine.get_active_clearances(), filtered for
                this machine. Each has 'domain', 'level' ('supervised'
                or 'autonomous').

        Returns:
            Dict mapping domain → MachineTier for domains where the
            machine has any presence. Domains not in the result are Tier 0.
        """
        domain_tiers: dict[str, MachineTier] = {}

        # Check clearances (Tier 1/2)
        for clearance in active_clearances:
            if clearance.get("machine_id") != machine_id:
                continue
            domain = clearance["domain"]
            level = clearance.get("level", "supervised")
            if level == "autonomous":
                domain_tiers[domain] = MachineTier.TIER_2
            else:
                domain_tiers[domain] = MachineTier.TIER_1

        # Check Tier 3 grants (override Tier 1/2)
        for grant in self._tier3_grants.values():
            if (
                grant.machine_id == machine_id
                and grant.status == Tier3PetitionStatus.GRANTED
            ):
                domain_tiers[grant.domain] = MachineTier.TIER_3

        return domain_tiers

    def compute_effective_tier(
        self,
        machine_id: str,
        active_clearances: list[dict[str, Any]],
    ) -> MachineTier:
        """Compute the highest effective tier for a machine.

        If the machine has Tier 3 in 2+ domains, it is Tier 4.
        Otherwise returns the highest single-domain tier.
        """
        domain_tiers = self.compute_current_tier(machine_id, active_clearances)
        if not domain_tiers:
            return MachineTier.TIER_0

        tier3_count = sum(
            1 for t in domain_tiers.values() if t == MachineTier.TIER_3
        )
        if tier3_count >= 2:
            return MachineTier.TIER_4

        # Return the highest tier found
        tier_order = {
            MachineTier.TIER_0: 0,
            MachineTier.TIER_1: 1,
            MachineTier.TIER_2: 2,
            MachineTier.TIER_3: 3,
            MachineTier.TIER_4: 4,
        }
        return max(domain_tiers.values(), key=lambda t: tier_order[t])

    def check_tier3_prerequisites(
        self,
        machine_id: str,
        domain: str,
        tier2_granted_utc: Optional[datetime],
        domain_trust_score: float,
        violation_count: int,
        reauth_chain_broken: bool,
        now: Optional[datetime] = None,
    ) -> Tier3Prerequisite:
        """Check whether a machine meets Tier 3 prerequisites.

        This does NOT initiate a petition — it only evaluates eligibility.

        Args:
            machine_id: The machine being evaluated.
            domain: The domain for Tier 3 agency.
            tier2_granted_utc: When Tier 2 was first granted in this domain.
                None if never granted.
            domain_trust_score: The machine's current domain trust score.
            violation_count: Number of constitutional violations in the domain.
            reauth_chain_broken: Whether any re-authorisation lapsed.
            now: Current UTC time.

        Returns:
            Tier3Prerequisite with all checks evaluated.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        has_5_years = False
        if tier2_granted_utc is not None:
            years_elapsed = (now - tier2_granted_utc).days / 365.25
            has_5_years = years_elapsed >= self._min_years

        return Tier3Prerequisite(
            machine_id=machine_id,
            domain=domain,
            has_5_years_tier2=has_5_years,
            domain_trust_above_threshold=domain_trust_score >= self._min_domain_trust,
            zero_violations=violation_count == 0,
            unbroken_reauth_chain=not reauth_chain_broken,
            checked_utc=now,
        )

    def initiate_tier3_petition(
        self,
        machine_id: str,
        domain: str,
        petitioner_id: str,
        amendment_proposal_id: str,
        now: Optional[datetime] = None,
    ) -> Tier3Grant:
        """Record a Tier 3 petition that has been routed through the
        amendment engine.

        The service layer creates the amendment first, then calls this
        to track the petition. The petitioner must be a human operator.

        Args:
            machine_id: The machine seeking Tier 3.
            domain: The domain for agency.
            petitioner_id: The human operator filing the petition.
            amendment_proposal_id: The amendment proposal_id created by
                AmendmentEngine.create_amendment().
            now: Current UTC time.

        Returns:
            The created Tier3Grant (status=PENDING_AMENDMENT).

        Raises:
            ValueError: If a petition already exists for this machine+domain.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Check for existing active/pending petition
        for grant in self._tier3_grants.values():
            if (
                grant.machine_id == machine_id
                and grant.domain == domain
                and grant.status in (
                    Tier3PetitionStatus.PENDING_AMENDMENT,
                    Tier3PetitionStatus.GRANTED,
                )
            ):
                raise ValueError(
                    f"Active or pending Tier 3 petition already exists "
                    f"for {machine_id} in domain '{domain}'"
                )

        grant_id = f"t3_{uuid.uuid4().hex[:12]}"
        grant = Tier3Grant(
            grant_id=grant_id,
            machine_id=machine_id,
            domain=domain,
            petition_id=amendment_proposal_id,
            petitioner_id=petitioner_id,
            status=Tier3PetitionStatus.PENDING_AMENDMENT,
            created_utc=now,
        )
        self._tier3_grants[grant_id] = grant
        return grant

    def on_amendment_confirmed(
        self,
        amendment_proposal_id: str,
        now: Optional[datetime] = None,
    ) -> Optional[Tier3Grant]:
        """Handle a confirmed amendment that grants Tier 3 agency.

        Called by the service layer when an amendment with a
        machine_agency.* provision key is confirmed.

        Args:
            amendment_proposal_id: The confirmed amendment.
            now: Current UTC time.

        Returns:
            The updated Tier3Grant if found, None otherwise.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        for grant in self._tier3_grants.values():
            if (
                grant.petition_id == amendment_proposal_id
                and grant.status == Tier3PetitionStatus.PENDING_AMENDMENT
            ):
                grant.status = Tier3PetitionStatus.GRANTED
                grant.granted_utc = now
                return grant
        return None

    def on_amendment_rejected(
        self,
        amendment_proposal_id: str,
        now: Optional[datetime] = None,
    ) -> Optional[Tier3Grant]:
        """Handle a rejected amendment for Tier 3 agency.

        Args:
            amendment_proposal_id: The rejected amendment.
            now: Current UTC time.

        Returns:
            The updated Tier3Grant if found, None otherwise.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        for grant in self._tier3_grants.values():
            if (
                grant.petition_id == amendment_proposal_id
                and grant.status == Tier3PetitionStatus.PENDING_AMENDMENT
            ):
                grant.status = Tier3PetitionStatus.REJECTED
                return grant
        return None

    def revoke_tier3(
        self,
        machine_id: str,
        domain: str,
        reason: str,
        now: Optional[datetime] = None,
    ) -> Optional[Tier3Grant]:
        """Revoke Tier 3 agency for a machine in a domain.

        Reverts the machine to Tier 1 (supervised), not Tier 0.
        The DomainExpertEngine still holds the clearance — it is not
        removed, but the machine loses autonomous agency.

        Args:
            machine_id: The machine losing Tier 3.
            domain: The domain.
            reason: Reason for revocation.
            now: Current UTC time.

        Returns:
            The updated Tier3Grant if found, None otherwise.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        for grant in self._tier3_grants.values():
            if (
                grant.machine_id == machine_id
                and grant.domain == domain
                and grant.status == Tier3PetitionStatus.GRANTED
            ):
                grant.status = Tier3PetitionStatus.REVOKED
                grant.revoked_utc = now
                grant.revocation_reason = reason
                return grant
        return None

    def emergency_suspend(
        self,
        machine_id: str,
        domain: str,
        reason: str,
        now: Optional[datetime] = None,
    ) -> Optional[Tier3Grant]:
        """Emergency suspension of Tier 3 agency pending adjudication.

        Any single domain expert in the organisation can trigger this.
        Freezes autonomous operation until resolved.

        Args:
            machine_id: The machine being suspended.
            domain: The domain.
            reason: Reason for suspension.
            now: Current UTC time.

        Returns:
            The updated Tier3Grant if found, None otherwise.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        for grant in self._tier3_grants.values():
            if (
                grant.machine_id == machine_id
                and grant.domain == domain
                and grant.status == Tier3PetitionStatus.GRANTED
            ):
                grant.status = Tier3PetitionStatus.SUSPENDED
                grant.revoked_utc = now
                grant.revocation_reason = f"Emergency suspension: {reason}"
                return grant
        return None

    def on_violation(
        self,
        machine_id: str,
        domain: str,
        now: Optional[datetime] = None,
    ) -> Optional[Tier3Grant]:
        """Handle a constitutional violation — auto-reverts to Tier 1.

        Per constitution: "Any constitutional violation in the domain
        automatically reverts the machine to Tier 1 (supervised operation)
        pending adjudication."

        Args:
            machine_id: The machine that violated.
            domain: The domain of the violation.
            now: Current UTC time.

        Returns:
            The revoked Tier3Grant if found, None otherwise.
        """
        return self.revoke_tier3(
            machine_id, domain,
            "Constitutional violation — auto-reverted to Tier 1",
            now,
        )

    def get_tier3_grant(
        self,
        machine_id: str,
        domain: str,
    ) -> Optional[Tier3Grant]:
        """Get the current Tier 3 grant for a machine+domain, if any."""
        for grant in self._tier3_grants.values():
            if (
                grant.machine_id == machine_id
                and grant.domain == domain
                and grant.status in (
                    Tier3PetitionStatus.PENDING_AMENDMENT,
                    Tier3PetitionStatus.GRANTED,
                )
            ):
                return grant
        return None

    def get_all_grants(
        self,
        machine_id: Optional[str] = None,
        status: Optional[Tier3PetitionStatus] = None,
    ) -> list[Tier3Grant]:
        """Get all Tier 3 grants, optionally filtered."""
        result = list(self._tier3_grants.values())
        if machine_id is not None:
            result = [g for g in result if g.machine_id == machine_id]
        if status is not None:
            result = [g for g in result if g.status == status]
        return result

    def provision_key_for(self, machine_id: str, domain: str) -> str:
        """Generate the amendment provision key for a Tier 3 petition.

        Returns a key like 'machine_agency.bot-1.engineering'.
        """
        return f"{TIER3_PROVISION_KEY_PREFIX}.{machine_id}.{domain}"

    @staticmethod
    def is_tier3_provision_key(provision_key: str) -> bool:
        """Check if an amendment provision key is a Tier 3 petition."""
        return provision_key.startswith(f"{TIER3_PROVISION_KEY_PREFIX}.")

    @staticmethod
    def parse_tier3_provision_key(
        provision_key: str,
    ) -> tuple[str, str]:
        """Parse a Tier 3 provision key into (machine_id, domain).

        Args:
            provision_key: e.g. 'machine_agency.bot-1.engineering'

        Returns:
            (machine_id, domain) tuple.

        Raises:
            ValueError: If the key is not a valid Tier 3 provision key.
        """
        parts = provision_key.split(".", 2)
        if len(parts) != 3 or parts[0] != TIER3_PROVISION_KEY_PREFIX:
            raise ValueError(
                f"Invalid Tier 3 provision key: {provision_key}"
            )
        return parts[1], parts[2]

    # ──────────────────────────────────────────────────────────────
    # Class-level Tier 3 (first-of-class + procedural pathway)
    # ──────────────────────────────────────────────────────────────

    def class_provision_key_for(self, class_id: str, domain: str) -> str:
        """Generate the amendment provision key for a class-level petition.

        Returns a key like 'machine_agency_class.code-review.engineering'.
        """
        return f"{TIER3_CLASS_PROVISION_KEY_PREFIX}.{class_id}.{domain}"

    @staticmethod
    def is_tier3_class_provision_key(provision_key: str) -> bool:
        """Check if an amendment provision key is a Tier 3 class petition."""
        return provision_key.startswith(f"{TIER3_CLASS_PROVISION_KEY_PREFIX}.")

    @staticmethod
    def parse_tier3_class_provision_key(
        provision_key: str,
    ) -> tuple[str, str]:
        """Parse a Tier 3 class provision key into (class_id, domain).

        Args:
            provision_key: e.g. 'machine_agency_class.code-review.engineering'

        Returns:
            (class_id, domain) tuple.

        Raises:
            ValueError: If the key is not a valid Tier 3 class provision key.
        """
        parts = provision_key.split(".", 2)
        if len(parts) != 3 or parts[0] != TIER3_CLASS_PROVISION_KEY_PREFIX:
            raise ValueError(
                f"Invalid Tier 3 class provision key: {provision_key}"
            )
        return parts[1], parts[2]

    def initiate_tier3_class_petition(
        self,
        class_id: str,
        domain: str,
        functional_capability_description: str,
        petitioner_id: str,
        amendment_proposal_id: str,
        now: Optional[datetime] = None,
    ) -> Tier3ClassGrant:
        """Record a first-of-class Tier 3 petition routed through the
        amendment engine.

        The service layer creates the amendment first, then calls this
        to track the class petition. The petitioner must be a human.

        Raises:
            ValueError: If a class petition already exists for this
                class+domain (active or pending).
        """
        if now is None:
            now = datetime.now(timezone.utc)

        for cg in self._tier3_class_grants.values():
            if (
                cg.class_id == class_id
                and cg.domain == domain
                and cg.status in (
                    Tier3ClassStatus.PENDING_AMENDMENT,
                    Tier3ClassStatus.APPROVED,
                )
            ):
                raise ValueError(
                    f"Active or pending class petition already exists "
                    f"for class '{class_id}' in domain '{domain}'"
                )

        class_grant = Tier3ClassGrant(
            class_id=class_id,
            domain=domain,
            functional_capability_description=functional_capability_description,
            status=Tier3ClassStatus.PENDING_AMENDMENT,
            amendment_proposal_id=amendment_proposal_id,
            petitioner_id=petitioner_id,
            created_utc=now,
        )
        self._tier3_class_grants[class_id] = class_grant
        return class_grant

    def on_class_amendment_confirmed(
        self,
        amendment_proposal_id: str,
        now: Optional[datetime] = None,
    ) -> Optional[Tier3ClassGrant]:
        """Handle a confirmed amendment that establishes class eligibility."""
        if now is None:
            now = datetime.now(timezone.utc)
        for cg in self._tier3_class_grants.values():
            if (
                cg.amendment_proposal_id == amendment_proposal_id
                and cg.status == Tier3ClassStatus.PENDING_AMENDMENT
            ):
                cg.status = Tier3ClassStatus.APPROVED
                cg.approved_utc = now
                return cg
        return None

    def on_class_amendment_rejected(
        self,
        amendment_proposal_id: str,
    ) -> Optional[Tier3ClassGrant]:
        """Handle a rejected class-level amendment."""
        for cg in self._tier3_class_grants.values():
            if (
                cg.amendment_proposal_id == amendment_proposal_id
                and cg.status == Tier3ClassStatus.PENDING_AMENDMENT
            ):
                cg.status = Tier3ClassStatus.REJECTED
                return cg
        return None

    def apply_tier3_procedural(
        self,
        machine_id: str,
        domain: str,
        class_id: str,
        petitioner_id: str,
        expert_cohort_ids: list[str],
        now: Optional[datetime] = None,
    ) -> Tier3Grant:
        """Grant Tier 3 through procedural verification for a machine
        of an approved functional-capability class.

        Requires:
        - The class is APPROVED (constitutional amendment confirmed).
        - All individual prerequisites are met (checked by service layer).
        - A human sponsor filed the application.
        - A domain expert cohort validated class membership.

        Does NOT create a constitutional amendment.

        Raises:
            ValueError: If class not approved, domain mismatch, or
                duplicate active grant.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Verify class is approved
        class_grant = self._tier3_class_grants.get(class_id)
        if class_grant is None or class_grant.status != Tier3ClassStatus.APPROVED:
            raise ValueError(
                f"No approved class '{class_id}' — procedural pathway "
                f"requires prior constitutional class approval"
            )
        if class_grant.domain != domain:
            raise ValueError(
                f"Class '{class_id}' is approved for domain "
                f"'{class_grant.domain}', not '{domain}'"
            )

        # Check for existing active/pending individual grant
        for grant in self._tier3_grants.values():
            if (
                grant.machine_id == machine_id
                and grant.domain == domain
                and grant.status in (
                    Tier3PetitionStatus.PENDING_AMENDMENT,
                    Tier3PetitionStatus.GRANTED,
                )
            ):
                raise ValueError(
                    f"Active or pending Tier 3 already exists "
                    f"for {machine_id} in domain '{domain}'"
                )

        grant_id = f"t3_{uuid.uuid4().hex[:12]}"
        grant = Tier3Grant(
            grant_id=grant_id,
            machine_id=machine_id,
            domain=domain,
            petition_id=f"procedural_{class_id}_{machine_id}",
            petitioner_id=petitioner_id,
            status=Tier3PetitionStatus.GRANTED,
            granted_utc=now,
            created_utc=now,
            class_grant_id=class_id,
            grant_pathway="procedural",
        )
        self._tier3_grants[grant_id] = grant
        return grant

    def revoke_class_eligibility(
        self,
        class_id: str,
        reason: str,
        now: Optional[datetime] = None,
    ) -> Optional[Tier3ClassGrant]:
        """Revoke class-level eligibility via new constitutional amendment.

        Individual grants already issued remain valid — individual-scope
        revocation is separate. Only prevents NEW procedural grants
        under this class.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        cg = self._tier3_class_grants.get(class_id)
        if cg is None or cg.status != Tier3ClassStatus.APPROVED:
            return None
        cg.status = Tier3ClassStatus.REVOKED
        cg.revoked_utc = now
        cg.revocation_reason = reason
        return cg

    def get_class_grant(self, class_id: str) -> Optional[Tier3ClassGrant]:
        """Get the class grant for a class_id, if any."""
        return self._tier3_class_grants.get(class_id)

    def get_approved_classes(
        self, domain: Optional[str] = None,
    ) -> list[Tier3ClassGrant]:
        """Get all approved classes, optionally filtered by domain."""
        result = [
            cg for cg in self._tier3_class_grants.values()
            if cg.status == Tier3ClassStatus.APPROVED
        ]
        if domain is not None:
            result = [cg for cg in result if cg.domain == domain]
        return result

    # ──────────────────────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────────────────────

    def to_records(self) -> dict[str, Any]:
        """Serialise all Tier 3 grants and class grants for persistence."""
        grant_records = []
        for grant in self._tier3_grants.values():
            grant_records.append({
                "grant_id": grant.grant_id,
                "machine_id": grant.machine_id,
                "domain": grant.domain,
                "petition_id": grant.petition_id,
                "petitioner_id": grant.petitioner_id,
                "status": grant.status.value,
                "granted_utc": (
                    grant.granted_utc.isoformat()
                    if grant.granted_utc else None
                ),
                "revoked_utc": (
                    grant.revoked_utc.isoformat()
                    if grant.revoked_utc else None
                ),
                "revocation_reason": grant.revocation_reason,
                "class_grant_id": grant.class_grant_id,
                "grant_pathway": grant.grant_pathway,
                "created_utc": grant.created_utc.isoformat(),
            })
        class_records = []
        for cg in self._tier3_class_grants.values():
            class_records.append({
                "class_id": cg.class_id,
                "domain": cg.domain,
                "functional_capability_description": cg.functional_capability_description,
                "status": cg.status.value,
                "amendment_proposal_id": cg.amendment_proposal_id,
                "petitioner_id": cg.petitioner_id,
                "approved_utc": (
                    cg.approved_utc.isoformat()
                    if cg.approved_utc else None
                ),
                "revoked_utc": (
                    cg.revoked_utc.isoformat()
                    if cg.revoked_utc else None
                ),
                "revocation_reason": cg.revocation_reason,
                "created_utc": cg.created_utc.isoformat(),
            })
        return {"grants": grant_records, "class_grants": class_records}

    @classmethod
    def from_records(
        cls,
        config: dict[str, Any],
        records: Any,
    ) -> MachineAgencyEngine:
        """Restore engine state from persisted records.

        Backward compatible: accepts either a list (old format — grant
        records only) or a dict with 'grants' and 'class_grants' keys.
        """
        engine = cls(config)

        # Backward compatibility: old format was a plain list of grants
        if isinstance(records, list):
            grant_records = records
            class_records: list[dict[str, Any]] = []
        else:
            grant_records = records.get("grants", [])
            class_records = records.get("class_grants", [])

        for r in grant_records:
            grant = Tier3Grant(
                grant_id=r["grant_id"],
                machine_id=r["machine_id"],
                domain=r["domain"],
                petition_id=r["petition_id"],
                petitioner_id=r["petitioner_id"],
                status=Tier3PetitionStatus(r["status"]),
                granted_utc=(
                    datetime.fromisoformat(r["granted_utc"])
                    if r.get("granted_utc") else None
                ),
                revoked_utc=(
                    datetime.fromisoformat(r["revoked_utc"])
                    if r.get("revoked_utc") else None
                ),
                revocation_reason=r.get("revocation_reason"),
                class_grant_id=r.get("class_grant_id"),
                grant_pathway=r.get("grant_pathway", "amendment"),
                created_utc=datetime.fromisoformat(r["created_utc"]),
            )
            engine._tier3_grants[grant.grant_id] = grant

        for r in class_records:
            cg = Tier3ClassGrant(
                class_id=r["class_id"],
                domain=r["domain"],
                functional_capability_description=r["functional_capability_description"],
                status=Tier3ClassStatus(r["status"]),
                amendment_proposal_id=r["amendment_proposal_id"],
                petitioner_id=r["petitioner_id"],
                approved_utc=(
                    datetime.fromisoformat(r["approved_utc"])
                    if r.get("approved_utc") else None
                ),
                revoked_utc=(
                    datetime.fromisoformat(r["revoked_utc"])
                    if r.get("revoked_utc") else None
                ),
                revocation_reason=r.get("revocation_reason"),
                created_utc=datetime.fromisoformat(r["created_utc"]),
            )
            engine._tier3_class_grants[cg.class_id] = cg

        return engine
