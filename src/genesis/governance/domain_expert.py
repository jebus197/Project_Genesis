"""Domain Expert Pools and Machine Domain Clearance — Phase F-3.

Genesis draws a clear line between governance and operations. Governance
is egalitarian — a hospital cleaner and a neurosurgeon have identical
voting power. Operations are meritocratic — missions match workers with
demonstrated domain trust.

Architecture:
- DomainExpertEngine handles clearance nomination, voting, evaluation,
  renewal, revocation, and autonomous operation authorisation.
- The service layer bridges the engine with roster, trust records, and events.
- Single-responsibility: the engine never touches actor records directly.

Constitutional constraints:
- Domain clearance requires unanimous approval from qualified domain experts.
- Domain clearance does not grant governance power (design test #71).
- Clearance is never permanent — annual re-authorisation required (design test #72).
- Machine clearance requires domain expert verification (design test #70).
- Autonomous operation requires stricter quorum and higher trust thresholds.
- Human operator remains constitutionally responsible for machine actions.
- Any single domain expert can file a revocation request.

Design test #70: Can a machine receive domain clearance without verification
by domain experts? If yes, reject design.

Design test #71: Can a machine's domain clearance transfer governance
voting power? If yes, reject design.

Design test #72: Can autonomous machine operation be authorised without
annual re-authorisation? If yes, reject design.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


class DomainClearanceStatus(str, enum.Enum):
    """Lifecycle status of a domain clearance."""
    PENDING = "pending"        # Nominated, voting in progress
    ACTIVE = "active"          # Unanimously approved, within expiry
    EXPIRED = "expired"        # Past expiry date
    REVOKED = "revoked"        # Revoked by domain expert or adjudication


class ClearanceLevel(str, enum.Enum):
    """Whether clearance is supervised (Tier 1) or autonomous (Tier 2)."""
    SUPERVISED = "supervised"      # Tier 1: supervised domain clearance
    AUTONOMOUS = "autonomous"      # Tier 2: autonomous operation


@dataclass(frozen=True)
class ClearanceVote:
    """A vote by a domain expert on a clearance nomination.

    STRUCTURAL INVARIANT: No 'governance_power', 'constitutional_vote',
    or 'amendment' field exists. Clearance votes are operational, not
    governance actions.
    """
    voter_id: str
    domain_trust: float      # Voter's domain trust at time of vote
    approve: bool
    evidence_summary: str
    voted_utc: datetime


@dataclass
class DomainClearance:
    """A domain clearance record for a machine.

    STRUCTURAL INVARIANT: No 'governance_power', 'voting_rights',
    or 'constitutional_authority' field exists. Domain clearance is
    operational capability, not governance power.
    """
    clearance_id: str
    machine_id: str
    org_id: str
    domain: str
    level: ClearanceLevel
    status: DomainClearanceStatus
    nominated_by: str         # Human member who nominated
    nominated_utc: datetime
    votes: list[ClearanceVote] = field(default_factory=list)
    approved_utc: Optional[datetime] = None
    expires_utc: Optional[datetime] = None  # Always set on approval
    revoked_utc: Optional[datetime] = None
    revoked_by: Optional[str] = None
    renewal_count: int = 0

    @property
    def vote_count(self) -> int:
        return len(self.votes)

    @property
    def approve_count(self) -> int:
        return sum(1 for v in self.votes if v.approve)

    @property
    def reject_count(self) -> int:
        return sum(1 for v in self.votes if not v.approve)


# Constitutional thresholds
CLEARANCE_MIN_QUORUM = 3          # Tier 1: minimum 3 domain experts
CLEARANCE_MIN_DOMAIN_TRUST = 0.60  # Tier 1: voter domain trust >= 0.60
AUTONOMOUS_MIN_QUORUM = 5         # Tier 2: minimum 5 domain experts
AUTONOMOUS_MIN_DOMAIN_TRUST = 0.70  # Tier 2: voter domain trust >= 0.70
AUTONOMOUS_MIN_MACHINE_TRUST = 0.60  # Tier 2: machine domain trust >= 0.60
DEFAULT_CLEARANCE_EXPIRY_DAYS = 365  # Annual re-authorisation


class DomainExpertEngine:
    """Domain clearance nomination, voting, evaluation, and lifecycle.

    Manages the lifecycle of machine domain clearances from nomination
    through expert voting to approval, renewal, and revocation.
    Never directly modifies actor records — that is the service layer's
    responsibility.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialise the Domain Expert engine.

        Args:
            config: Engine configuration containing:
                - clearance_min_quorum (default 3)
                - clearance_min_domain_trust (default 0.60)
                - autonomous_min_quorum (default 5)
                - autonomous_min_domain_trust (default 0.70)
                - autonomous_min_machine_trust (default 0.60)
                - clearance_expiry_days (default 365)
        """
        self._config = config
        self._clearances: dict[str, DomainClearance] = {}
        self._clearance_min_quorum = config.get(
            "clearance_min_quorum", CLEARANCE_MIN_QUORUM
        )
        self._clearance_min_domain_trust = config.get(
            "clearance_min_domain_trust", CLEARANCE_MIN_DOMAIN_TRUST
        )
        self._autonomous_min_quorum = config.get(
            "autonomous_min_quorum", AUTONOMOUS_MIN_QUORUM
        )
        self._autonomous_min_domain_trust = config.get(
            "autonomous_min_domain_trust", AUTONOMOUS_MIN_DOMAIN_TRUST
        )
        self._autonomous_min_machine_trust = config.get(
            "autonomous_min_machine_trust", AUTONOMOUS_MIN_MACHINE_TRUST
        )
        self._clearance_expiry_days = config.get(
            "clearance_expiry_days", DEFAULT_CLEARANCE_EXPIRY_DAYS
        )

    @classmethod
    def from_records(
        cls,
        config: dict[str, Any],
        clearance_data: list[dict[str, Any]],
    ) -> DomainExpertEngine:
        """Restore engine state from persistence records."""
        engine = cls(config)
        for cd in clearance_data:
            votes = [
                ClearanceVote(
                    voter_id=v["voter_id"],
                    domain_trust=v["domain_trust"],
                    approve=v["approve"],
                    evidence_summary=v["evidence_summary"],
                    voted_utc=datetime.fromisoformat(v["voted_utc"]),
                )
                for v in cd.get("votes", [])
            ]
            clearance = DomainClearance(
                clearance_id=cd["clearance_id"],
                machine_id=cd["machine_id"],
                org_id=cd["org_id"],
                domain=cd["domain"],
                level=ClearanceLevel(cd["level"]),
                status=DomainClearanceStatus(cd["status"]),
                nominated_by=cd["nominated_by"],
                nominated_utc=datetime.fromisoformat(cd["nominated_utc"]),
                votes=votes,
                approved_utc=(
                    datetime.fromisoformat(cd["approved_utc"])
                    if cd.get("approved_utc") else None
                ),
                expires_utc=(
                    datetime.fromisoformat(cd["expires_utc"])
                    if cd.get("expires_utc") else None
                ),
                revoked_utc=(
                    datetime.fromisoformat(cd["revoked_utc"])
                    if cd.get("revoked_utc") else None
                ),
                revoked_by=cd.get("revoked_by"),
                renewal_count=cd.get("renewal_count", 0),
            )
            engine._clearances[clearance.clearance_id] = clearance
        return engine

    def nominate_for_clearance(
        self,
        machine_id: str,
        org_id: str,
        domain: str,
        nominator_id: str,
        level: ClearanceLevel = ClearanceLevel.SUPERVISED,
        now: Optional[datetime] = None,
    ) -> DomainClearance:
        """Nominate a machine for domain clearance.

        Args:
            machine_id: The machine to clear.
            org_id: Organisation context.
            domain: Domain for clearance.
            nominator_id: Human member making the nomination.
            level: SUPERVISED (Tier 1) or AUTONOMOUS (Tier 2).
            now: Current UTC time.

        Returns:
            The new PENDING clearance.

        Raises:
            ValueError: If there's already an active/pending clearance for
                this machine+org+domain+level combination.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Check for existing active or pending clearance
        for c in self._clearances.values():
            if (c.machine_id == machine_id
                    and c.org_id == org_id
                    and c.domain == domain
                    and c.level == level
                    and c.status in (
                        DomainClearanceStatus.PENDING,
                        DomainClearanceStatus.ACTIVE,
                    )):
                raise ValueError(
                    f"Machine {machine_id} already has "
                    f"{c.status.value} {level.value} clearance "
                    f"for domain '{domain}' in org {org_id}"
                )

        clearance_id = f"clr_{uuid.uuid4().hex[:12]}"
        clearance = DomainClearance(
            clearance_id=clearance_id,
            machine_id=machine_id,
            org_id=org_id,
            domain=domain,
            level=level,
            status=DomainClearanceStatus.PENDING,
            nominated_by=nominator_id,
            nominated_utc=now,
        )
        self._clearances[clearance_id] = clearance
        return clearance

    def vote_on_clearance(
        self,
        clearance_id: str,
        voter_id: str,
        voter_domain_trust: float,
        approve: bool,
        evidence_summary: str,
        now: Optional[datetime] = None,
    ) -> DomainClearance:
        """Cast a vote on a pending clearance nomination.

        The voter must meet the domain trust threshold for the clearance
        level. Voting is unanimous — a single rejection terminates the
        clearance.

        Args:
            clearance_id: The clearance being voted on.
            voter_id: The domain expert voting.
            voter_domain_trust: Voter's domain trust in the relevant domain.
            approve: Whether the voter approves.
            evidence_summary: Evidence supporting the vote.
            now: Current UTC time.

        Returns:
            The updated clearance.

        Raises:
            ValueError: If validation fails.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        clearance = self._clearances.get(clearance_id)
        if clearance is None:
            raise ValueError(f"Clearance not found: {clearance_id}")
        if clearance.status != DomainClearanceStatus.PENDING:
            raise ValueError(
                f"Clearance {clearance_id} is {clearance.status.value}, "
                f"not pending"
            )

        # Check domain trust threshold
        if clearance.level == ClearanceLevel.SUPERVISED:
            min_trust = self._clearance_min_domain_trust
        else:
            min_trust = self._autonomous_min_domain_trust

        if voter_domain_trust < min_trust:
            raise ValueError(
                f"Voter domain trust {voter_domain_trust:.2f} is below "
                f"threshold {min_trust:.2f} for {clearance.level.value} "
                f"clearance"
            )

        # No duplicate votes
        for v in clearance.votes:
            if v.voter_id == voter_id:
                raise ValueError(
                    f"Voter {voter_id} has already voted on "
                    f"clearance {clearance_id}"
                )

        vote = ClearanceVote(
            voter_id=voter_id,
            domain_trust=voter_domain_trust,
            approve=approve,
            evidence_summary=evidence_summary,
            voted_utc=now,
        )
        clearance.votes.append(vote)

        # Unanimous: any rejection immediately revokes
        if not approve:
            clearance.status = DomainClearanceStatus.REVOKED
            clearance.revoked_utc = now
            clearance.revoked_by = voter_id

        return clearance

    def evaluate_clearance(
        self,
        clearance_id: str,
        machine_domain_trust: float = 0.0,
        now: Optional[datetime] = None,
    ) -> DomainClearance:
        """Evaluate whether a clearance has met its quorum.

        Called after voting to check if enough approvals have been
        received. For autonomous clearance, also checks machine's
        domain trust.

        Args:
            clearance_id: The clearance to evaluate.
            machine_domain_trust: Machine's domain trust (for autonomous).
            now: Current UTC time.

        Returns:
            The updated clearance (may be promoted to ACTIVE).

        Raises:
            ValueError: If clearance not found or not pending.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        clearance = self._clearances.get(clearance_id)
        if clearance is None:
            raise ValueError(f"Clearance not found: {clearance_id}")
        if clearance.status != DomainClearanceStatus.PENDING:
            raise ValueError(
                f"Clearance {clearance_id} is {clearance.status.value}"
            )

        if clearance.level == ClearanceLevel.SUPERVISED:
            min_quorum = self._clearance_min_quorum
        else:
            min_quorum = self._autonomous_min_quorum

        # Check quorum (all votes must be approvals — rejections
        # already set status to REVOKED)
        if clearance.approve_count >= min_quorum:
            # For autonomous, also check machine's domain trust
            if clearance.level == ClearanceLevel.AUTONOMOUS:
                if machine_domain_trust < self._autonomous_min_machine_trust:
                    raise ValueError(
                        f"Machine domain trust {machine_domain_trust:.2f} "
                        f"is below autonomous threshold "
                        f"{self._autonomous_min_machine_trust:.2f}"
                    )

            clearance.status = DomainClearanceStatus.ACTIVE
            clearance.approved_utc = now
            clearance.expires_utc = now + timedelta(
                days=self._clearance_expiry_days
            )

        return clearance

    def revoke_clearance(
        self,
        clearance_id: str,
        revoker_id: str,
        now: Optional[datetime] = None,
    ) -> DomainClearance:
        """Revoke an active clearance.

        Any single domain expert can revoke a clearance.

        Args:
            clearance_id: The clearance to revoke.
            revoker_id: The domain expert revoking.
            now: Current UTC time.

        Returns:
            The updated clearance with REVOKED status.

        Raises:
            ValueError: If clearance not found or not active.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        clearance = self._clearances.get(clearance_id)
        if clearance is None:
            raise ValueError(f"Clearance not found: {clearance_id}")
        if clearance.status != DomainClearanceStatus.ACTIVE:
            raise ValueError(
                f"Clearance {clearance_id} is {clearance.status.value}, "
                f"not active"
            )

        clearance.status = DomainClearanceStatus.REVOKED
        clearance.revoked_utc = now
        clearance.revoked_by = revoker_id
        return clearance

    def check_expirations(
        self,
        now: Optional[datetime] = None,
    ) -> list[DomainClearance]:
        """Expire any clearances past their expiry date.

        Args:
            now: Current UTC time.

        Returns:
            List of clearances that were expired.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        expired: list[DomainClearance] = []
        for c in self._clearances.values():
            if (c.status == DomainClearanceStatus.ACTIVE
                    and c.expires_utc is not None
                    and now >= c.expires_utc):
                c.status = DomainClearanceStatus.EXPIRED
                expired.append(c)

        return expired

    def renew_clearance(
        self,
        clearance_id: str,
        now: Optional[datetime] = None,
    ) -> DomainClearance:
        """Start a renewal process for an expiring clearance.

        Creates a new PENDING clearance for the same machine/org/domain/level
        combination, preserving the renewal chain.

        Args:
            clearance_id: The clearance to renew.
            now: Current UTC time.

        Returns:
            A new PENDING clearance for the renewal vote.

        Raises:
            ValueError: If clearance not found or not active/expired.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        old = self._clearances.get(clearance_id)
        if old is None:
            raise ValueError(f"Clearance not found: {clearance_id}")
        if old.status not in (
            DomainClearanceStatus.ACTIVE,
            DomainClearanceStatus.EXPIRED,
        ):
            raise ValueError(
                f"Clearance {clearance_id} is {old.status.value}, "
                f"cannot renew"
            )

        # Guard against duplicate pending renewals for the same tuple
        for existing in self._clearances.values():
            if (existing.machine_id == old.machine_id
                    and existing.org_id == old.org_id
                    and existing.domain == old.domain
                    and existing.level == old.level
                    and existing.status == DomainClearanceStatus.PENDING
                    and existing.clearance_id != clearance_id):
                raise ValueError(
                    f"Pending renewal already exists for "
                    f"{old.machine_id}/{old.domain}/{old.level.value}: "
                    f"{existing.clearance_id}"
                )

        new_id = f"clr_{uuid.uuid4().hex[:12]}"
        new_clearance = DomainClearance(
            clearance_id=new_id,
            machine_id=old.machine_id,
            org_id=old.org_id,
            domain=old.domain,
            level=old.level,
            status=DomainClearanceStatus.PENDING,
            nominated_by=old.nominated_by,
            nominated_utc=now,
            renewal_count=old.renewal_count + 1,
        )

        # Mark old clearance as expired if still active
        if old.status == DomainClearanceStatus.ACTIVE:
            old.status = DomainClearanceStatus.EXPIRED

        self._clearances[new_id] = new_clearance
        return new_clearance

    def get_clearance(self, clearance_id: str) -> Optional[DomainClearance]:
        """Retrieve a clearance by ID."""
        return self._clearances.get(clearance_id)

    def get_active_clearances(
        self,
        machine_id: Optional[str] = None,
        org_id: Optional[str] = None,
        domain: Optional[str] = None,
        level: Optional[ClearanceLevel] = None,
    ) -> list[DomainClearance]:
        """List active clearances with optional filters."""
        result = []
        for c in self._clearances.values():
            if c.status != DomainClearanceStatus.ACTIVE:
                continue
            if machine_id is not None and c.machine_id != machine_id:
                continue
            if org_id is not None and c.org_id != org_id:
                continue
            if domain is not None and c.domain != domain:
                continue
            if level is not None and c.level != level:
                continue
            result.append(c)
        result.sort(key=lambda c: c.approved_utc or c.nominated_utc,
                     reverse=True)
        return result

    def has_active_clearance(
        self,
        machine_id: str,
        domain: str,
        level: ClearanceLevel = ClearanceLevel.SUPERVISED,
    ) -> bool:
        """Check if a machine has active clearance for a domain at a level."""
        for c in self._clearances.values():
            if (c.machine_id == machine_id
                    and c.domain == domain
                    and c.level == level
                    and c.status == DomainClearanceStatus.ACTIVE):
                return True
        return False

    def to_records(self) -> list[dict[str, Any]]:
        """Serialise all clearances for persistence."""
        records: list[dict[str, Any]] = []
        for c in self._clearances.values():
            votes_data = [
                {
                    "voter_id": v.voter_id,
                    "domain_trust": v.domain_trust,
                    "approve": v.approve,
                    "evidence_summary": v.evidence_summary,
                    "voted_utc": v.voted_utc.isoformat(),
                }
                for v in c.votes
            ]
            records.append({
                "clearance_id": c.clearance_id,
                "machine_id": c.machine_id,
                "org_id": c.org_id,
                "domain": c.domain,
                "level": c.level.value,
                "status": c.status.value,
                "nominated_by": c.nominated_by,
                "nominated_utc": c.nominated_utc.isoformat(),
                "votes": votes_data,
                "approved_utc": (
                    c.approved_utc.isoformat() if c.approved_utc else None
                ),
                "expires_utc": (
                    c.expires_utc.isoformat() if c.expires_utc else None
                ),
                "revoked_utc": (
                    c.revoked_utc.isoformat() if c.revoked_utc else None
                ),
                "revoked_by": c.revoked_by,
                "renewal_count": c.renewal_count,
            })
        return records
