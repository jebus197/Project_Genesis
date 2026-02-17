"""Trust record and trust-delta data models.

Trust in Genesis is:
- Non-purchasable, non-transferable, identity-bound.
- Computed as T = w_Q * Q + w_R * R + w_V * V + w_E * E (constitutional_params.json).
- E (effort) measures reasoning effort proportional to mission complexity.
- Human floor is always positive; machine floor is zero.
- Fast elevation (delta > delta_fast) triggers automatic suspension.
- Domain-specific trust: actors build per-domain reputation alongside global score.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


class ActorKind(str, enum.Enum):
    """Whether an actor is human or machine."""
    HUMAN = "human"
    MACHINE = "machine"


@dataclass(frozen=True)
class TrustDelta:
    """A single trust-score change event.

    If abs(new_score - previous_score) > delta_fast, the delta is
    automatically suspended pending quorum revalidation.
    """
    actor_id: str
    actor_kind: ActorKind
    previous_score: float
    new_score: float
    reason: str
    mission_id: Optional[str] = None
    timestamp_utc: Optional[datetime] = None
    suspended: bool = False

    @property
    def delta(self) -> float:
        return self.new_score - self.previous_score

    @property
    def abs_delta(self) -> float:
        return abs(self.delta)


@dataclass
class TrustRecord:
    """Current trust state for a single actor.

    Invariants enforced externally:
    - Humans: score >= T_floor_H (positive floor).
    - Machines: score >= T_floor_M (0.0 — can decay to zero).
    - Quality score Q must meet Q_min_H or Q_min_M before trust gain.
    - score = w_Q * quality + w_R * reliability + w_V * volume + w_E * effort.
    - Effort (E) measures reasoning effort proportional to mission complexity tier.
    """
    actor_id: str
    actor_kind: ActorKind
    score: float
    quality: float = 0.0
    reliability: float = 0.0
    volume: float = 0.0
    effort: float = 0.0

    # Machine-specific lifecycle fields
    quarantined: bool = False
    recertification_failures: int = 0
    last_recertification_utc: Optional[datetime] = None
    decommissioned: bool = False
    recertification_failure_timestamps: list[datetime] = field(default_factory=list)
    probation_tasks_completed: int = 0

    # Trust profile minting
    trust_minted: bool = False
    trust_minted_utc: Optional[datetime] = None

    # Domain-specific decay tracking
    last_active_utc: Optional[datetime] = None

    # Domain-specific trust scores (empty dict = pre-labour-market mode)
    # Keyed by domain name. Global 'score' is the aggregate.
    domain_scores: dict[str, Any] = field(default_factory=dict)
    # Type: dict[str, DomainTrustScore] — uses Any to avoid circular import.
    # Set via TrustEngine.apply_domain_update().

    def display_score(self) -> int:
        """Return trust score on the 1-1000 display scale.

        Internal math stays 0.0-1.0. This multiplies by 1000 and
        returns an integer for display purposes.
        """
        return int(round(self.score * 1000))

    def is_eligible_to_vote(self, tau_vote: float) -> bool:
        """Check if actor meets voting eligibility threshold.

        Constitutional rules:
        - Only humans hold constitutional authority.
        - Machines cannot vote regardless of trust score.
        - Actor must have a minted trust profile.
        """
        if self.actor_kind != ActorKind.HUMAN:
            return False
        if not self.trust_minted:
            return False
        return self.score >= tau_vote and not self.quarantined and not self.decommissioned

    def is_eligible_to_propose(self, tau_prop: float) -> bool:
        """Check if actor meets proposal eligibility threshold (stricter).

        Constitutional rules:
        - Only humans hold constitutional authority.
        - Machines cannot propose regardless of trust score.
        - Actor must have a minted trust profile.
        """
        if self.actor_kind != ActorKind.HUMAN:
            return False
        if not self.trust_minted:
            return False
        return self.score >= tau_prop and not self.quarantined and not self.decommissioned
