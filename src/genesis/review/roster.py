"""Actor roster — registry of available reviewers and workers.

The roster is the source of truth for who can participate in missions.
It tracks all actors (human and machine) with their metadata required
for constrained-random reviewer selection:
- Trust score (determines eligibility)
- Region and organisation (for geographic/org diversity)
- Model family and method type (for heterogeneity enforcement)
- Actor kind (human vs machine, for constitutional authority checks)
- Availability status (quarantined/decommissioned actors are excluded)

Constitutional invariants enforced:
- Quarantined actors cannot be selected as reviewers.
- Decommissioned actors cannot be selected as reviewers.
- Self-review is structurally prevented (worker excluded from candidate pool).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from genesis.models.trust import ActorKind


class ActorStatus(str, enum.Enum):
    """Operational status of a roster actor."""
    PROVISIONAL = "provisional"
    ACTIVE = "active"
    QUARANTINED = "quarantined"
    DECOMMISSIONED = "decommissioned"
    PROBATION = "probation"
    ON_LEAVE = "on_leave"
    MEMORIALISED = "memorialised"


class IdentityVerificationStatus(str, enum.Enum):
    """Verification state for an actor's identity.

    Identity verification is an anti-abuse control only.
    It cannot mint trust, grant privileged routing, or grant
    constitutional authority (runtime_policy.json constraints).
    """
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    LAPSED = "lapsed"
    FLAGGED = "flagged"


@dataclass
class RosterEntry:
    """A single actor in the roster.

    All fields required for reviewer selection are mandatory.
    Trust score is mutable (updated by the trust engine).
    skill_profile is optional (backward compatible — None before labour market).
    """
    actor_id: str
    actor_kind: ActorKind
    trust_score: float
    region: str
    organization: str
    model_family: str
    method_type: str
    status: ActorStatus = ActorStatus.ACTIVE
    skill_profile: Optional[object] = None
    # Type: Optional[ActorSkillProfile] — untyped to avoid circular import.
    # Set via GenesisService.update_actor_skills().
    registered_by: Optional[str] = None
    # actor_id of the human operator who registered this actor.
    # None for humans (self-registered). Required for machines.
    registered_utc: Optional[datetime] = None
    # UTC timestamp of registration.
    machine_metadata: Optional[dict] = None
    # Machine-specific metadata: model version, API endpoint, capabilities.
    # None for humans.
    lineage_ids: list[str] = field(default_factory=list)
    # IDs of previously decommissioned machines that share lineage with this actor.
    # Required for machines whose operator previously had decommissioned machines.
    # Identity verification fields
    identity_status: IdentityVerificationStatus = IdentityVerificationStatus.UNVERIFIED
    identity_verified_utc: Optional[datetime] = None
    identity_expires_utc: Optional[datetime] = None
    identity_method: Optional[str] = None

    def is_available(self) -> bool:
        """An actor is available if provisional, active, or on probation."""
        return self.status in (
            ActorStatus.PROVISIONAL, ActorStatus.ACTIVE, ActorStatus.PROBATION,
        )


class ActorRoster:
    """Registry of all actors in the Genesis system.

    Thread-safety: this class is not thread-safe. The caller must
    synchronise access if used from multiple threads.
    """

    def __init__(self) -> None:
        self._actors: dict[str, RosterEntry] = {}

    def register(self, entry: RosterEntry) -> None:
        """Register a new actor or update an existing one.

        Raises ValueError if:
        - actor_id is blank/empty
        - trust_score is out of [0, 1]
        """
        canonical_id = entry.actor_id.strip()
        if not canonical_id:
            raise ValueError("Cannot register actor with blank ID")
        if not (0.0 <= entry.trust_score <= 1.0):
            raise ValueError(
                f"Trust score must be in [0, 1], got {entry.trust_score}"
            )
        entry.actor_id = canonical_id
        self._actors[canonical_id] = entry

    def remove(self, actor_id: str) -> None:
        """Remove an actor from the roster."""
        canonical = actor_id.strip()
        if canonical in self._actors:
            del self._actors[canonical]

    def get(self, actor_id: str) -> Optional[RosterEntry]:
        """Look up an actor by ID."""
        return self._actors.get(actor_id.strip())

    def all_actors(self) -> list[RosterEntry]:
        """Return all registered actors."""
        return list(self._actors.values())

    def available_reviewers(
        self,
        exclude_ids: set[str] | None = None,
        min_trust: float = 0.0,
    ) -> list[RosterEntry]:
        """Return actors eligible for reviewer selection.

        Excludes:
        - Actors in exclude_ids (used to prevent self-review)
        - Quarantined actors
        - Decommissioned actors
        - Actors below min_trust threshold
        """
        exclude = exclude_ids or set()
        return [
            a for a in self._actors.values()
            if a.is_available()
            and a.status != ActorStatus.PROVISIONAL
            and a.actor_id not in exclude
            and a.trust_score >= min_trust
        ]

    @property
    def count(self) -> int:
        return len(self._actors)

    @property
    def active_count(self) -> int:
        return sum(1 for a in self._actors.values() if a.is_available())

    @property
    def human_count(self) -> int:
        return sum(
            1 for a in self._actors.values()
            if a.actor_kind == ActorKind.HUMAN and a.is_available()
        )

    @property
    def machine_count(self) -> int:
        return sum(
            1 for a in self._actors.values()
            if a.actor_kind == ActorKind.MACHINE and a.is_available()
        )

    def machines_for_operator(self, operator_id: str) -> list[RosterEntry]:
        """Return all machines registered by a given human operator."""
        return [
            a for a in self._actors.values()
            if a.actor_kind == ActorKind.MACHINE
            and a.registered_by == operator_id
        ]
