"""Rehabilitation engine — trust rebuilding after moderate violations.

Only MODERATE severity violations are eligible for rehabilitation.
SEVERE and EGREGIOUS violations result in permanent decommission
with no rehabilitation path.

Rehabilitation process:
1. Suspension expires → actor enters PROBATION status.
2. Actor must complete a minimum number of probation tasks (default 5).
3. Trust is partially restored: min(original × 0.50, 0.30).
4. Rehabilitation must complete within 180 days or it fails.
"""

from __future__ import annotations

import uuid
import enum
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


class RehabStatus(str, enum.Enum):
    """Status of a rehabilitation record."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RehabilitationRecord:
    """A rehabilitation record for a suspended actor."""
    rehab_id: str
    actor_id: str
    case_id: str
    original_trust: float
    severity: str
    suspension_start: datetime
    suspension_end: datetime
    rehab_started_utc: Optional[datetime] = None
    rehab_completed_utc: Optional[datetime] = None
    probation_tasks_required: int = 5
    probation_tasks_completed: int = 0
    trust_restored_to: Optional[float] = None
    status: RehabStatus = RehabStatus.PENDING


class RehabilitationEngine:
    """Trust rebuilding engine for moderate violations.

    Usage:
        engine = RehabilitationEngine(config)
        record = engine.create_rehabilitation(actor_id, case_id, ...)
        record = engine.start_rehabilitation(rehab_id, now)
        record = engine.record_probation_task(rehab_id)
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._records: dict[str, RehabilitationRecord] = {}
        self._records_by_actor: dict[str, str] = {}  # actor_id → rehab_id
        self._probation_tasks_required = config.get("probation_tasks_required", 5)
        self._trust_restoration_fraction = config.get("trust_restoration_fraction", 0.50)
        self._max_restoration_score = config.get("max_restoration_score", 0.30)
        self._rehab_window_days = config.get("rehab_window_days", 180)

    def create_rehabilitation(
        self,
        actor_id: str,
        case_id: str,
        original_trust: float,
        severity: str,
        suspension_start: datetime,
        suspension_end: datetime,
        now: Optional[datetime] = None,
    ) -> RehabilitationRecord:
        """Create a rehabilitation record for a suspended actor.

        Only MODERATE severity is eligible. Raises ValueError for
        SEVERE or EGREGIOUS violations.
        """
        severity_upper = severity.upper()
        if severity_upper in ("SEVERE", "EGREGIOUS"):
            raise ValueError(
                f"Rehabilitation not available for {severity_upper} violations: "
                f"permanent decommission applies"
            )
        if severity_upper not in ("MINOR", "MODERATE"):
            raise ValueError(f"Unknown severity: {severity}")

        rehab_id = f"rehab-{uuid.uuid4().hex[:12]}"
        record = RehabilitationRecord(
            rehab_id=rehab_id,
            actor_id=actor_id,
            case_id=case_id,
            original_trust=original_trust,
            severity=severity,
            suspension_start=suspension_start,
            suspension_end=suspension_end,
            probation_tasks_required=self._probation_tasks_required,
        )
        self._records[rehab_id] = record
        self._records_by_actor[actor_id] = rehab_id
        return record

    def start_rehabilitation(
        self,
        rehab_id: str,
        now: Optional[datetime] = None,
    ) -> RehabilitationRecord:
        """Start the rehabilitation process (called when suspension expires)."""
        record = self._get_record(rehab_id)
        if now is None:
            now = datetime.now(timezone.utc)

        record.rehab_started_utc = now
        record.status = RehabStatus.ACTIVE
        return record

    def record_probation_task(self, rehab_id: str) -> RehabilitationRecord:
        """Record completion of a probation task.

        Automatically completes rehabilitation when enough tasks done.
        """
        record = self._get_record(rehab_id)
        if record.status != RehabStatus.ACTIVE:
            raise ValueError(
                f"Rehabilitation {rehab_id} is not active (status: {record.status.value})"
            )

        record.probation_tasks_completed += 1

        if record.probation_tasks_completed >= record.probation_tasks_required:
            record.trust_restored_to = self.compute_restored_trust(record.original_trust)
            record.rehab_completed_utc = datetime.now(timezone.utc)
            record.status = RehabStatus.COMPLETED

        return record

    def check_rehab_expiry(
        self,
        rehab_id: str,
        now: Optional[datetime] = None,
    ) -> bool:
        """Check if rehabilitation has expired (180-day window).

        Returns True if expired, False if still within window.
        """
        record = self._get_record(rehab_id)
        if now is None:
            now = datetime.now(timezone.utc)

        if record.rehab_started_utc is None:
            return False

        deadline = record.rehab_started_utc + timedelta(days=self._rehab_window_days)
        if now >= deadline and record.status == RehabStatus.ACTIVE:
            record.status = RehabStatus.FAILED
            return True
        return False

    def compute_restored_trust(self, original_trust: float) -> float:
        """Compute the trust score to restore after rehabilitation.

        Returns min(original × restoration_fraction, max_restoration).
        """
        return min(
            original_trust * self._trust_restoration_fraction,
            self._max_restoration_score,
        )

    def get_record(self, rehab_id: str) -> Optional[RehabilitationRecord]:
        """Look up a rehabilitation record."""
        return self._records.get(rehab_id)

    def get_record_for_actor(self, actor_id: str) -> Optional[RehabilitationRecord]:
        """Look up rehabilitation record by actor ID."""
        rehab_id = self._records_by_actor.get(actor_id)
        if rehab_id is None:
            return None
        return self._records.get(rehab_id)

    def _get_record(self, rehab_id: str) -> RehabilitationRecord:
        """Get record or raise ValueError."""
        record = self._records.get(rehab_id)
        if record is None:
            raise ValueError(f"Rehabilitation record not found: {rehab_id}")
        return record
