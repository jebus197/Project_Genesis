"""Trust record and trust-delta data models.

Trust in Genesis is:
- Non-purchasable, non-transferable, identity-bound.
- Computed as T = w_Q * Q + w_R * R + w_V * V + w_E * E (constitutional_params.json).
- E (effort) measures reasoning effort proportional to mission complexity.
- Human floor is always positive; machine floor is zero.
- Fast elevation (delta > delta_fast) triggers automatic suspension.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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

    # Domain-specific decay tracking
    last_active_utc: Optional[datetime] = None

    def is_eligible_to_vote(self, tau_vote: float) -> bool:
        """Check if actor meets voting eligibility threshold.

        Constitutional rule: only humans hold constitutional authority.
        Machines cannot vote regardless of trust score.
        """
        if self.actor_kind != ActorKind.HUMAN:
            return False
        return self.score >= tau_vote and not self.quarantined and not self.decommissioned

    def is_eligible_to_propose(self, tau_prop: float) -> bool:
        """Check if actor meets proposal eligibility threshold (stricter).

        Constitutional rule: only humans hold constitutional authority.
        Machines cannot propose regardless of trust score.
        """
        if self.actor_kind != ActorKind.HUMAN:
            return False
        return self.score >= tau_prop and not self.quarantined and not self.decommissioned
