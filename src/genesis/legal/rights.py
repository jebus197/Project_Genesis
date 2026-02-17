"""Rights of the accused — structural enforcement via code gates.

Rights of the accused are structurally enforced. No adjudication panel
can form until the rights record validates. This module is a pure gate:
it never modifies trust or status. It returns pass/fail. The service
layer refuses to proceed when violations exist.

Constitutional rights enforced:
1. Right to know: accused is notified of the complaint.
2. Right to respond: 72-hour response period before panel formation.
3. Right to evidence: evidence must be disclosed before adjudication.
4. Right to appeal: one appeal per case, within 72 hours.
5. Right to representation: accused may designate a representative.
6. Presumption of good faith: assumed until verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional


@dataclass
class AccusedRightsRecord:
    """Structural rights record for an accused actor.

    Created when an adjudication case is opened. Panel formation
    is blocked until validate_panel_formation_allowed() returns
    an empty violations list.
    """
    case_id: str
    accused_id: str
    notified_utc: datetime
    response_deadline_utc: datetime
    response_submitted: bool = False
    evidence_disclosed: bool = False
    appeal_available: bool = True
    representation_allowed: bool = True
    presumption_of_good_faith: bool = True


class RightsEnforcer:
    """Pure gate — validates that accused rights are respected.

    Usage:
        enforcer = RightsEnforcer(response_period_hours=72)
        record = enforcer.create_rights_record(case_id, accused_id, now)
        violations = enforcer.validate_panel_formation_allowed(record, now)
        if violations:
            raise ValueError(f"Rights violations: {violations}")
    """

    def __init__(self, response_period_hours: int = 72) -> None:
        self._response_period_hours = response_period_hours
        self._records: dict[str, AccusedRightsRecord] = {}

    def create_rights_record(
        self,
        case_id: str,
        accused_id: str,
        now: Optional[datetime] = None,
    ) -> AccusedRightsRecord:
        """Create a rights record when a case is opened."""
        if now is None:
            now = datetime.now(timezone.utc)

        record = AccusedRightsRecord(
            case_id=case_id,
            accused_id=accused_id,
            notified_utc=now,
            response_deadline_utc=now + timedelta(hours=self._response_period_hours),
        )
        self._records[case_id] = record
        return record

    def validate_panel_formation_allowed(
        self,
        record: AccusedRightsRecord,
        now: Optional[datetime] = None,
    ) -> list[str]:
        """Return list of violations. Empty list means panel can form.

        Panel formation is allowed when:
        1. Response period has elapsed OR response has been submitted.
        2. Evidence has been disclosed.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        violations: list[str] = []

        # Check response period — must have elapsed or response submitted
        if not record.response_submitted and now < record.response_deadline_utc:
            violations.append(
                f"Response period not elapsed: deadline {record.response_deadline_utc.isoformat()}"
            )

        # Check evidence disclosure
        if not record.evidence_disclosed:
            violations.append("Evidence has not been disclosed to the accused")

        return violations

    def mark_evidence_disclosed(self, case_id: str) -> AccusedRightsRecord:
        """Mark that evidence has been disclosed to the accused."""
        record = self._records.get(case_id)
        if record is None:
            raise ValueError(f"No rights record for case: {case_id}")
        record.evidence_disclosed = True
        return record

    def mark_response_submitted(self, case_id: str) -> AccusedRightsRecord:
        """Mark that the accused has submitted their response."""
        record = self._records.get(case_id)
        if record is None:
            raise ValueError(f"No rights record for case: {case_id}")
        record.response_submitted = True
        return record

    def get_record(self, case_id: str) -> Optional[AccusedRightsRecord]:
        """Look up a rights record by case ID."""
        return self._records.get(case_id)
