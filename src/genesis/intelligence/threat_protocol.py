"""Auto-immune system — threat signal propagation protocol.

Constitutional requirement: The network defends itself through distributed
intelligence applied to its own health. Threat signals propagate across
the network. High-risk immune responses require randomised domain-expert
human oversight. No entity may become a permanent immune overseer.

This module defines the contract for how threat intelligence propagates.
Like InsightSignal Protocol and PaymentRail Protocol, it defines the
interface before implementation. Any future threat detection pipeline
must satisfy this Protocol.

Design test #93: HIGH/CRITICAL actions require human oversight.
Design test #94: No permanent immune overseer.
Design test #95: The immune system learns from resolved incidents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from genesis.intelligence.insight_protocol import compute_provenance_hash


class ThreatType(str, Enum):
    """Classification of threat signals detected by the immune system."""

    ANOMALOUS_TRUST = "anomalous_trust"         # Fast elevation, pump-dump patterns
    COLLUSION = "collusion"                       # Ring reviews, coordinated actions
    QUALITY_DEGRADATION = "quality_degradation"   # Gradual decline in actor quality
    COMPLIANCE_PATTERN = "compliance_pattern"     # Repeated flags from same source
    BEHAVIOURAL_DRIFT = "behavioural_drift"       # Trusted actor changing pattern
    MANIPULATION = "manipulation"                 # Review gaming, panel stacking


class ThreatSeverity(str, Enum):
    """Severity tier determines response autonomy level.

    Constitutional constraint (design test #93): HIGH and CRITICAL
    responses ALWAYS require human oversight from a randomised
    domain-expert at trust >= IMMUNE_OVERSIGHT_TRUST_MIN.
    """

    LOW = "low"             # Informational — auto-log, no action required
    MEDIUM = "medium"       # Flag for review — auto-flag + queue
    HIGH = "high"           # Requires human oversight before action
    CRITICAL = "critical"   # Requires human oversight + immediate containment


class AutomatedResponseTier(str, Enum):
    """What the system may do automatically at each severity level.

    Constitutional constraint: auto_response_max_severity determines
    the ceiling. By default, only LOW and MEDIUM are auto-handled.
    """

    AUTO_LOG = "auto_log"               # Record only
    AUTO_FLAG = "auto_flag"             # Record + queue for review
    HUMAN_REQUIRED = "human_required"   # Blocked until human overseer approves
    HUMAN_CONTAINMENT = "human_containment"  # Blocked + immediate containment


# Severity → response tier mapping (constitutional)
SEVERITY_RESPONSE_MAP: Dict[ThreatSeverity, AutomatedResponseTier] = {
    ThreatSeverity.LOW: AutomatedResponseTier.AUTO_LOG,
    ThreatSeverity.MEDIUM: AutomatedResponseTier.AUTO_FLAG,
    ThreatSeverity.HIGH: AutomatedResponseTier.HUMAN_REQUIRED,
    ThreatSeverity.CRITICAL: AutomatedResponseTier.HUMAN_CONTAINMENT,
}

# Severities that ALWAYS require human oversight (design test #93)
HUMAN_OVERSIGHT_REQUIRED: frozenset[ThreatSeverity] = frozenset({
    ThreatSeverity.HIGH,
    ThreatSeverity.CRITICAL,
})


@runtime_checkable
class ThreatSignal(Protocol):
    """A unit of threat intelligence that propagates through the network.

    Any concrete threat signal implementation must satisfy this Protocol.
    The protocol is runtime_checkable so the registry can verify
    conformance at registration time.
    """

    @property
    def signal_id(self) -> str:
        """Unique identifier for this threat signal."""
        ...

    @property
    def source_detection(self) -> str:
        """Which detection mechanism raised this (e.g., 'fast_elevation', 'screener')."""
        ...

    @property
    def threat_type(self) -> ThreatType:
        """Classification of the threat."""
        ...

    @property
    def severity(self) -> ThreatSeverity:
        """Determines response autonomy level."""
        ...

    @property
    def confidence(self) -> float:
        """0.0-1.0, derived from detection evidence strength."""
        ...

    @property
    def evidence_hash(self) -> str:
        """SHA-256 of evidence chain."""
        ...

    @property
    def affected_actor_ids(self) -> list[str]:
        """Actors implicated by this threat."""
        ...

    @property
    def recommended_action(self) -> str:
        """Suggested response (for human review at HIGH/CRITICAL)."""
        ...

    @property
    def detected_utc(self) -> datetime:
        """When the threat was detected."""
        ...


@dataclass
class ConcreteThreatSignal:
    """Reference implementation of ThreatSignal for use by the registry."""

    signal_id: str
    source_detection: str
    threat_type: ThreatType
    severity: ThreatSeverity
    confidence: float
    evidence_hash: str
    affected_actor_ids: list[str]
    recommended_action: str
    detected_utc: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class ResolutionRecord:
    """Record of a resolved threat — the immune system's learning unit.

    Design test #95: every human oversight decision is stored as a
    training signal. These records are append-only and queryable.
    """

    threat_signal_id: str
    overseer_decision: str          # "upheld", "rejected_false_positive", "escalated"
    overseer_rationale: str         # Why the decision was made
    outcome_verified: Optional[bool] = None  # Was the decision correct? (post-hoc)
    resolved_utc: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class ThreatRegistry:
    """Registry of threat signals with constitutional enforcement.

    Enforces:
    - HIGH/CRITICAL responses require human oversight (DT #93)
    - No permanent overseer (DT #94) — overseer selection is parameterised
    - Resolution records are append-only (DT #95 — learning foundation)
    - Evidence hash validation
    - Confidence bounds
    - Affected actor IDs non-empty

    Constitutional guard (design test #94): the registry has NO method to
    set a permanent overseer. Overseer selection is a parameter
    ('randomised_domain_expert') resolved at response time, not stored.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._signals: Dict[str, ConcreteThreatSignal] = {}
        self._resolutions: List[ResolutionRecord] = []
        self._config = config or {
            "oversight_trust_min": 0.85,
            "auto_response_max_severity": "medium",
            "overseer_selection": "randomised_domain_expert",
        }

    def register_threat(self, signal: ConcreteThreatSignal) -> None:
        """Register a threat signal after constitutional validation.

        Raises:
            ValueError: If any constitutional constraint is violated.
            TypeError: If the signal doesn't satisfy ThreatSignal Protocol.
        """
        if not isinstance(signal, ThreatSignal):
            raise TypeError(
                f"Signal must satisfy ThreatSignal Protocol, got {type(signal)}"
            )

        violations = self._validate_signal(signal)
        if violations:
            raise ValueError(
                f"Constitutional violations: {'; '.join(violations)}"
            )

        if signal.signal_id in self._signals:
            raise ValueError(
                f"Duplicate signal_id '{signal.signal_id}': threat signals are "
                f"tamper-evident and cannot be overwritten. Each signal_id must "
                f"be unique."
            )

        self._signals[signal.signal_id] = signal

    def get_response_tier(self, severity: ThreatSeverity) -> AutomatedResponseTier:
        """Return the response tier for a given severity.

        Constitutional constraint: severities above auto_response_max_severity
        always require human oversight.
        """
        return SEVERITY_RESPONSE_MAP[severity]

    def requires_human_oversight(self, severity: ThreatSeverity) -> bool:
        """Check whether this severity level requires human oversight.

        Design test #93: HIGH and CRITICAL always return True.
        """
        return severity in HUMAN_OVERSIGHT_REQUIRED

    def record_resolution(self, record: ResolutionRecord) -> None:
        """Record a threat resolution. Append-only — cannot be deleted.

        Design test #95: every human decision is stored as a training signal.
        """
        self._resolutions.append(record)

    def query_resolutions(
        self,
        *,
        threat_signal_id: Optional[str] = None,
        max_results: int = 100,
    ) -> list[ResolutionRecord]:
        """Query resolution records. Open to all — no access restriction.

        Same openness principle as InsightRegistry.query_insights.
        """
        results = []
        for record in self._resolutions:
            if threat_signal_id is not None and record.threat_signal_id != threat_signal_id:
                continue
            results.append(record)
            if len(results) >= max_results:
                break
        return results

    def get_signal(self, signal_id: str) -> Optional[ConcreteThreatSignal]:
        """Retrieve a specific threat signal by ID."""
        return self._signals.get(signal_id)

    @property
    def signal_count(self) -> int:
        """Total registered threat signals."""
        return len(self._signals)

    @property
    def resolution_count(self) -> int:
        """Total resolution records (append-only)."""
        return len(self._resolutions)

    def validate_constitutional_compliance(self) -> list[str]:
        """Check constitutional compliance of all registered signals."""
        all_violations = []
        for signal in self._signals.values():
            violations = self._validate_signal(signal)
            for v in violations:
                all_violations.append(f"{signal.signal_id}: {v}")

        # Verify response tier mapping is constitutionally correct
        for sev in HUMAN_OVERSIGHT_REQUIRED:
            tier = SEVERITY_RESPONSE_MAP.get(sev)
            if tier not in (AutomatedResponseTier.HUMAN_REQUIRED,
                            AutomatedResponseTier.HUMAN_CONTAINMENT):
                all_violations.append(
                    f"Severity {sev.value} maps to {tier} — "
                    f"must require human oversight"
                )

        return all_violations

    def _validate_signal(self, signal: Any) -> list[str]:
        """Validate a threat signal against constitutional constraints."""
        violations = []

        # 1. Evidence hash must be valid SHA-256 (64 hex chars)
        if not signal.evidence_hash or len(signal.evidence_hash) != 64:
            violations.append(
                "Evidence hash must be a valid SHA-256 (64 hex characters)"
            )
        else:
            try:
                int(signal.evidence_hash, 16)
            except ValueError:
                violations.append("Evidence hash contains non-hex characters")

        # 2. Confidence must be in [0.0, 1.0]
        if not (0.0 <= signal.confidence <= 1.0):
            violations.append(
                f"Confidence must be 0.0-1.0, got {signal.confidence}"
            )

        # 3. Threat type must be valid
        if not isinstance(signal.threat_type, ThreatType):
            violations.append(
                f"Threat type must be ThreatType, got {signal.threat_type}"
            )

        # 4. Severity must be valid
        if not isinstance(signal.severity, ThreatSeverity):
            violations.append(
                f"Severity must be ThreatSeverity, got {signal.severity}"
            )

        # 5. Affected actor IDs must be non-empty
        if not signal.affected_actor_ids:
            violations.append("Affected actor IDs must not be empty")

        # 6. Recommended action must be non-empty
        if not signal.recommended_action:
            violations.append("Recommended action must not be empty")

        return violations
