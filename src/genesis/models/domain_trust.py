"""Domain-specific trust models — trust per skill domain, decay forecasts.

Trust becomes multi-dimensional: actors build reputation per domain,
not just a single global number. The global TrustRecord.score remains
as the weighted aggregate of all domain scores.

Decay dynamics:
- Hard ceiling at 1.0 (enforced by TrustEngine clamping).
- Passive inactivity decay: trust drifts down without active work.
- Differentiated by ActorKind: HUMAN half-life ~365d, AI ~90d.
- Failure-triggered decay is faster (low quality → low trust directly).
- Deep experience (high volume) decays slower.

TrustStatus is the "dashboard" — every actor can query their decay
forecast at any time. Time-to-half-life is the headline motivational signal.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class DomainTrustScore:
    """Trust score for a single domain.

    Mirrors the global TrustRecord structure but scoped to one domain.
    """
    domain: str
    score: float = 0.0
    quality: float = 0.0
    reliability: float = 0.0
    volume: float = 0.0
    effort: float = 0.0
    mission_count: int = 0
    last_active_utc: Optional[datetime] = None


@dataclass(frozen=True)
class DomainTrustDelta:
    """A domain-specific trust change event."""
    actor_id: str
    domain: str
    previous_score: float
    new_score: float
    reason: str
    mission_id: Optional[str] = None


class DecayUrgency(str, enum.Enum):
    """How urgently an actor needs to work to maintain trust.

    STABLE: recently active, no decay pressure
    DRIFTING: >25% through to half-life, mild pressure
    URGENT: >75% through to half-life, strong pressure
    CRITICAL: past half-life, trust already halved or worse
    """
    STABLE = "stable"
    DRIFTING = "drifting"
    URGENT = "urgent"
    CRITICAL = "critical"


@dataclass(frozen=True)
class DomainDecayForecast:
    """Decay forecast for a single domain."""
    domain: str
    current_score: float
    days_since_active: float
    half_life_days: float
    days_until_half_life: float
    projected_score_at_half_life: float
    urgency: DecayUrgency


@dataclass(frozen=True)
class TrustStatus:
    """Complete trust dashboard for an actor.

    Computed on-demand — no persistence needed.
    Time-to-half-life is the primary motivational signal.
    """
    actor_id: str
    global_score: float
    days_since_last_activity: float
    half_life_days: float
    days_until_half_life: float
    projected_score_at_half_life: float
    urgency: DecayUrgency
    domain_forecasts: list[DomainDecayForecast] = field(default_factory=list)
