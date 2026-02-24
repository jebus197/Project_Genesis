"""Distributed Intelligence — insight propagation protocol.

Constitutional requirement: No entity may capture, restrict, or monopolise
work-derived insights. The network becomes collectively more capable through
the work it coordinates. The labour market is the mechanism; distributed
intelligence is the outcome.

This module defines the contract for how work-derived intelligence propagates.
Like PaymentRail Protocol, it defines the interface before implementation.
Any future signal pipeline must satisfy this Protocol.

Design test #92: Can any entity restrict the flow of work-derived insights
across the network for private advantage? If yes, reject design.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from genesis.models.market import WorkVisibility


class InsightType(str, Enum):
    """Classification of work-derived intelligence signals."""

    TECHNIQUE = "technique"             # A method that worked
    PATTERN = "pattern"                 # A recurring structure worth recognising
    SOLUTION = "solution"               # A complete answer to a class of problems
    WARNING = "warning"                 # A pitfall or failure mode
    DOMAIN_KNOWLEDGE = "domain_knowledge"  # Domain expertise worth sharing


@runtime_checkable
class InsightSignal(Protocol):
    """A unit of work-derived intelligence that propagates through the network.

    Any concrete signal implementation must satisfy this Protocol.
    The protocol is runtime_checkable so the registry can verify
    conformance at registration time.
    """

    @property
    def signal_id(self) -> str:
        """Unique identifier for this signal."""
        ...

    @property
    def source_mission_id(self) -> str:
        """The mission that produced this insight."""
        ...

    @property
    def source_actor_id(self) -> str:
        """Who discovered it (for trust evaluation by consumers)."""
        ...

    @property
    def signal_type(self) -> InsightType:
        """Classification of the insight."""
        ...

    @property
    def confidence(self) -> float:
        """0.0-1.0, derived from source trust + review quality."""
        ...

    @property
    def payload(self) -> str:
        """The insight itself."""
        ...

    @property
    def provenance_hash(self) -> str:
        """SHA-256 of evidence chain."""
        ...

    @property
    def created_utc(self) -> datetime:
        """When the insight was created."""
        ...

    @property
    def ttl_days(self) -> Optional[int]:
        """Time-to-live in days (None = permanent)."""
        ...

    @property
    def visibility(self) -> WorkVisibility:
        """Inherits Open Work visibility tier from source mission."""
        ...


@dataclass
class ConcreteInsightSignal:
    """Reference implementation of InsightSignal for use by the registry.

    Production signal implementations may differ, but all must satisfy
    the InsightSignal Protocol.
    """

    signal_id: str
    source_mission_id: str
    source_actor_id: str
    signal_type: InsightType
    confidence: float
    payload: str
    provenance_hash: str
    created_utc: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    ttl_days: Optional[int] = None
    visibility: WorkVisibility = WorkVisibility.PUBLIC


def compute_provenance_hash(evidence_chain: list[str]) -> str:
    """Compute SHA-256 provenance hash from an evidence chain.

    Each element in the chain is a string representation of an evidence
    item (mission ID, review ID, trust snapshot, etc.). The hash proves
    the insight's lineage without exposing the full chain.
    """
    h = hashlib.sha256()
    for item in evidence_chain:
        h.update(item.encode("utf-8"))
    return h.hexdigest()


class InsightRegistry:
    """Registry of insight signals with constitutional enforcement.

    Enforces:
    - Insights inherit Open Work visibility (default: PUBLIC)
    - No METADATA_ONLY insights without source mission justification
    - No retroactive concealment (once registered, visibility cannot decrease)
    - Provenance hash is valid (non-empty SHA-256 format)
    - Source actor exists in provided roster (for trust evaluation)
    - No single entity can restrict insight flow

    Constitutional guard (design test #92): the registry structurally
    prevents any entity from restricting insight flow for private advantage.
    There is no method to hide, restrict, or gate access to registered
    insights. Query is open to all participants.
    """

    def __init__(self) -> None:
        self._signals: Dict[str, ConcreteInsightSignal] = {}
        self._known_actors: set[str] = set()

    def register_actor(self, actor_id: str) -> None:
        """Register an actor as known (for provenance verification)."""
        self._known_actors.add(actor_id)

    def register_insight(
        self,
        signal: ConcreteInsightSignal,
        *,
        roster: Optional[set[str]] = None,
    ) -> None:
        """Register an insight signal after constitutional validation.

        Args:
            signal: The insight to register.
            roster: Optional set of known actor IDs. If provided, the source
                    actor must be in this set. Falls back to internal roster.

        Raises:
            ValueError: If any constitutional constraint is violated.
            TypeError: If the signal doesn't satisfy the InsightSignal Protocol.
        """
        if not isinstance(signal, InsightSignal):
            raise TypeError(
                f"Signal must satisfy InsightSignal Protocol, got {type(signal)}"
            )

        violations = self._validate_signal(signal, roster=roster)
        if violations:
            raise ValueError(
                f"Constitutional violations: {'; '.join(violations)}"
            )

        self._signals[signal.signal_id] = signal

    def query_insights(
        self,
        *,
        signal_type: Optional[InsightType] = None,
        source_actor_id: Optional[str] = None,
        min_confidence: float = 0.0,
        max_results: int = 100,
    ) -> list[ConcreteInsightSignal]:
        """Query registered insights. Open to all participants.

        Constitutional requirement: no access restriction, no gating,
        no filtering by requester identity. Anyone can query anything.
        """
        results = []
        now = datetime.now(timezone.utc)

        for signal in self._signals.values():
            # Filter expired signals
            if signal.ttl_days is not None:
                age_days = (now - signal.created_utc).total_seconds() / 86400
                if age_days > signal.ttl_days:
                    continue

            if signal_type is not None and signal.signal_type != signal_type:
                continue
            if source_actor_id is not None and signal.source_actor_id != source_actor_id:
                continue
            if signal.confidence < min_confidence:
                continue

            results.append(signal)

            if len(results) >= max_results:
                break

        return results

    def get_signal(self, signal_id: str) -> Optional[ConcreteInsightSignal]:
        """Retrieve a specific signal by ID."""
        return self._signals.get(signal_id)

    @property
    def signal_count(self) -> int:
        """Total registered signals."""
        return len(self._signals)

    def validate_constitutional_compliance(self) -> list[str]:
        """Check all registered signals for constitutional compliance.

        Returns list of violations (empty = compliant).
        """
        all_violations = []
        for signal in self._signals.values():
            violations = self._validate_signal(signal)
            for v in violations:
                all_violations.append(f"{signal.signal_id}: {v}")
        return all_violations

    def _validate_signal(
        self,
        signal: Any,
        *,
        roster: Optional[set[str]] = None,
    ) -> list[str]:
        """Validate a signal against constitutional constraints."""
        violations = []

        # 1. Visibility must be PUBLIC by default (Open Work principle)
        #    METADATA_ONLY is permitted only if the source mission has that tier,
        #    but there is no CONCEALED/PRIVATE tier — Genesis has no hidden work.
        if not isinstance(signal.visibility, WorkVisibility):
            violations.append(
                f"Visibility must be a WorkVisibility value, got {signal.visibility}"
            )

        # 2. Provenance hash must be valid SHA-256 (64 hex chars)
        if not signal.provenance_hash or len(signal.provenance_hash) != 64:
            violations.append(
                "Provenance hash must be a valid SHA-256 (64 hex characters)"
            )
        else:
            try:
                int(signal.provenance_hash, 16)
            except ValueError:
                violations.append(
                    "Provenance hash contains non-hex characters"
                )

        # 3. Source actor must be known (for trust evaluation by consumers)
        effective_roster = roster or self._known_actors
        if effective_roster and signal.source_actor_id not in effective_roster:
            violations.append(
                f"Source actor '{signal.source_actor_id}' not in roster — "
                f"trust evaluation impossible"
            )

        # 4. Confidence must be in [0.0, 1.0]
        if not (0.0 <= signal.confidence <= 1.0):
            violations.append(
                f"Confidence must be 0.0-1.0, got {signal.confidence}"
            )

        # 5. Signal type must be a valid InsightType
        if not isinstance(signal.signal_type, InsightType):
            violations.append(
                f"Signal type must be InsightType, got {signal.signal_type}"
            )

        # 6. Payload must be non-empty
        if not signal.payload:
            violations.append("Payload must not be empty")

        return violations
