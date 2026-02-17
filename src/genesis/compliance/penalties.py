"""Penalty escalation engine — proportional consequences for violations.

Severity tiers:
- MINOR: trust penalty -0.10, warning issued.
- MODERATE: trust nuked to 0.001 (1/1000), 90-day suspension.
- SEVERE: trust nuked to 0.0, permanent decommission.
- EGREGIOUS: trust nuked to 0.0, permanent decommission, identity locked.

Pattern escalation:
- Second MODERATE violation within 365 days → SEVERE (permanent).

Constitutional invariant: penalties are proportional but the minimum
penalty for a confirmed prohibited-category violation is MODERATE.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


class PenaltySeverity(str, enum.Enum):
    """Severity of a compliance violation."""
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    EGREGIOUS = "egregious"


class ViolationType(str, enum.Enum):
    """Classification of the violation that triggered a penalty."""
    CONTENT_FLAGGED = "content_flagged"
    PROHIBITED_CATEGORY_CONFIRMED = "prohibited_category_confirmed"
    REPEATED_FLAGGING = "repeated_flagging"
    COMPLAINT_UPHELD = "complaint_upheld"
    ABUSE_CONFIRMED = "abuse_confirmed"
    WEAPONS_OR_EXPLOITATION = "weapons_or_exploitation"
    PATTERN_ESCALATION = "pattern_escalation"


@dataclass(frozen=True)
class PenaltyOutcome:
    """Computed penalty for a violation.

    trust_target: the trust score the actor should be set to.
    suspension_days: days of suspension (0 = no suspension, -1 = permanent).
    permanent: whether the actor is permanently decommissioned.
    identity_locked: whether the identity is locked (egregious only).
    """
    severity: PenaltySeverity
    trust_action: str  # "reduce" or "nuke"
    trust_target: float
    suspension_days: int
    permanent: bool
    identity_locked: bool
    reason: str


@dataclass(frozen=True)
class PriorViolation:
    """Record of a prior violation for escalation computation."""
    severity: PenaltySeverity
    violation_type: ViolationType
    occurred_utc: datetime


class PenaltyEscalationEngine:
    """Compute proportional penalties with pattern escalation.

    The engine maps violation types to severity tiers, then applies
    escalation rules based on prior violations within the lookback window.
    """

    # Default lookback window for pattern detection
    PATTERN_LOOKBACK_DAYS = 365

    # Violation type → base severity mapping
    _BASE_SEVERITY: dict[ViolationType, PenaltySeverity] = {
        ViolationType.CONTENT_FLAGGED: PenaltySeverity.MINOR,
        ViolationType.REPEATED_FLAGGING: PenaltySeverity.MODERATE,
        ViolationType.PROHIBITED_CATEGORY_CONFIRMED: PenaltySeverity.MODERATE,
        ViolationType.COMPLAINT_UPHELD: PenaltySeverity.MODERATE,
        ViolationType.ABUSE_CONFIRMED: PenaltySeverity.SEVERE,
        ViolationType.WEAPONS_OR_EXPLOITATION: PenaltySeverity.EGREGIOUS,
        ViolationType.PATTERN_ESCALATION: PenaltySeverity.SEVERE,
    }

    def compute_penalty(
        self,
        actor_id: str,
        violation_type: ViolationType,
        prior_violations: Optional[list[PriorViolation]] = None,
        now: Optional[datetime] = None,
    ) -> PenaltyOutcome:
        """Compute the penalty for a violation, considering prior history.

        Pattern escalation: if the actor has a prior MODERATE violation
        within PATTERN_LOOKBACK_DAYS, a new MODERATE → SEVERE (permanent).
        """
        if now is None:
            now = datetime.now(timezone.utc)

        base_severity = self._BASE_SEVERITY.get(
            violation_type, PenaltySeverity.MINOR,
        )

        # Check for pattern escalation
        effective_severity = base_severity
        if base_severity == PenaltySeverity.MODERATE and prior_violations:
            lookback_start = now - timedelta(days=self.PATTERN_LOOKBACK_DAYS)
            recent_moderates = [
                v for v in prior_violations
                if v.severity in (PenaltySeverity.MODERATE, PenaltySeverity.SEVERE)
                and v.occurred_utc >= lookback_start
            ]
            if recent_moderates:
                # Second moderate within window → permanent decommission
                effective_severity = PenaltySeverity.SEVERE

        return self._apply_severity(effective_severity, violation_type)

    def _apply_severity(
        self,
        severity: PenaltySeverity,
        violation_type: ViolationType,
    ) -> PenaltyOutcome:
        """Map a severity tier to concrete penalty parameters."""
        if severity == PenaltySeverity.MINOR:
            return PenaltyOutcome(
                severity=PenaltySeverity.MINOR,
                trust_action="reduce",
                trust_target=-0.10,  # Relative reduction
                suspension_days=0,
                permanent=False,
                identity_locked=False,
                reason=f"Minor compliance warning for {violation_type.value}",
            )
        elif severity == PenaltySeverity.MODERATE:
            return PenaltyOutcome(
                severity=PenaltySeverity.MODERATE,
                trust_action="nuke",
                trust_target=0.001,
                suspension_days=90,
                permanent=False,
                identity_locked=False,
                reason=f"Moderate penalty: trust nuked to 0.001, 90-day suspension for {violation_type.value}",
            )
        elif severity == PenaltySeverity.SEVERE:
            return PenaltyOutcome(
                severity=PenaltySeverity.SEVERE,
                trust_action="nuke",
                trust_target=0.0,
                suspension_days=-1,  # Permanent
                permanent=True,
                identity_locked=False,
                reason=f"Severe penalty: permanent decommission for {violation_type.value}",
            )
        else:  # EGREGIOUS
            return PenaltyOutcome(
                severity=PenaltySeverity.EGREGIOUS,
                trust_action="nuke",
                trust_target=0.0,
                suspension_days=-1,  # Permanent
                permanent=True,
                identity_locked=True,
                reason=f"Egregious penalty: permanent decommission + identity locked for {violation_type.value}",
            )
