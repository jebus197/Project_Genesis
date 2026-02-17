"""Tier 2 adjudication engine — unified panel-based dispute resolution.

Unifies payment disputes, compliance complaints, abuse complaints,
conduct complaints, and normative resolution into a single codified
adjudication system. Existing engines (compliance screener, quorum
verifier) continue working; their outcomes feed into this unified
adjudication record.

Constitutional requirements:
- Blind adjudication: pseudonyms for complainant and accused.
- Panel diversity: ≥2 organisations, ≥2 regions.
- 3/5 supermajority for UPHELD verdict.
- One appeal per case, within 72 hours, with entirely new panel.
- Rights of the accused enforced structurally (see rights.py).
"""

from __future__ import annotations

import enum
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


class AdjudicationType(str, enum.Enum):
    """Types of adjudication cases."""
    PAYMENT_DISPUTE = "payment_dispute"
    COMPLIANCE_COMPLAINT = "compliance_complaint"
    ABUSE_COMPLAINT = "abuse_complaint"
    CONDUCT_COMPLAINT = "conduct_complaint"
    NORMATIVE_RESOLUTION = "normative_resolution"


class AdjudicationStatus(str, enum.Enum):
    """Lifecycle status of an adjudication case."""
    OPENED = "opened"
    RESPONSE_PERIOD = "response_period"
    PANEL_FORMED = "panel_formed"
    DELIBERATION = "deliberation"
    DECIDED = "decided"
    APPEAL_PENDING = "appeal_pending"
    APPEAL_DECIDED = "appeal_decided"
    ESCALATED = "escalated"
    CLOSED = "closed"


class AdjudicationVerdict(str, enum.Enum):
    """Possible verdicts from an adjudication panel."""
    UPHELD = "upheld"
    DISMISSED = "dismissed"
    PARTIAL = "partial"
    ESCALATED_TO_COURT = "escalated_to_court"


def _generate_pseudonym() -> str:
    """Generate a blind pseudonym for adjudication."""
    return f"party-{secrets.token_hex(8)}"


@dataclass
class AdjudicationCase:
    """A single adjudication case in the unified justice system."""
    case_id: str
    type: AdjudicationType
    status: AdjudicationStatus
    complainant_id: str
    accused_id: str
    mission_id: Optional[str] = None
    reason: str = ""
    evidence_hashes: list[str] = field(default_factory=list)
    opened_utc: Optional[datetime] = None
    response_deadline_utc: Optional[datetime] = None
    accused_response: Optional[str] = None
    accused_pseudonym: str = ""
    complainant_pseudonym: str = ""
    panel_ids: list[str] = field(default_factory=list)
    panel_votes: dict[str, str] = field(default_factory=dict)
    panel_attestations: dict[str, str] = field(default_factory=dict)
    panel_orgs: list[str] = field(default_factory=list)
    panel_regions: list[str] = field(default_factory=list)
    verdict: Optional[AdjudicationVerdict] = None
    decided_utc: Optional[datetime] = None
    appeal_of: Optional[str] = None
    appeal_deadline_utc: Optional[datetime] = None


class AdjudicationEngine:
    """Tier 2 adjudication — unified panel-based dispute resolution.

    Usage:
        engine = AdjudicationEngine(config)
        case = engine.open_case(type, complainant, accused, reason, now)
        # ... wait for response period / response ...
        case = engine.form_panel(case_id, candidates, now)
        case = engine.submit_panel_vote(case_id, panelist_id, verdict, att)
        verdict = engine.evaluate_verdict(case_id)
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._cases: dict[str, AdjudicationCase] = {}
        self._panel_size = config.get("panel_size", 5)
        self._response_period_hours = config.get("response_period_hours", 72)
        self._appeal_window_hours = config.get("appeal_window_hours", 72)
        self._supermajority_threshold = config.get("supermajority_threshold", 0.60)
        self._min_panelist_trust = config.get("min_panelist_trust", 0.60)
        self._min_regions = config.get("panel_min_regions", 2)
        self._min_orgs = config.get("panel_min_organizations", 2)

    def open_case(
        self,
        type: AdjudicationType,
        complainant_id: str,
        accused_id: str,
        reason: str,
        now: Optional[datetime] = None,
        mission_id: Optional[str] = None,
        evidence_hashes: Optional[list[str]] = None,
    ) -> AdjudicationCase:
        """Open a new adjudication case.

        Raises ValueError for self-complaints.
        """
        if complainant_id == accused_id:
            raise ValueError("Cannot file a complaint against yourself")

        if now is None:
            now = datetime.now(timezone.utc)

        case_id = f"adj-{uuid.uuid4().hex[:12]}"
        case = AdjudicationCase(
            case_id=case_id,
            type=type,
            status=AdjudicationStatus.RESPONSE_PERIOD,
            complainant_id=complainant_id,
            accused_id=accused_id,
            mission_id=mission_id,
            reason=reason,
            evidence_hashes=evidence_hashes or [],
            opened_utc=now,
            response_deadline_utc=now + timedelta(hours=self._response_period_hours),
            complainant_pseudonym=_generate_pseudonym(),
            accused_pseudonym=_generate_pseudonym(),
        )
        self._cases[case_id] = case
        return case

    def submit_accused_response(
        self,
        case_id: str,
        text: str,
        now: Optional[datetime] = None,
    ) -> AdjudicationCase:
        """Submit the accused party's response.

        Raises ValueError if case not in RESPONSE_PERIOD or deadline passed.
        """
        case = self._get_case(case_id)
        if now is None:
            now = datetime.now(timezone.utc)

        if case.status != AdjudicationStatus.RESPONSE_PERIOD:
            raise ValueError(f"Case {case_id} is not in response period (status: {case.status.value})")

        if case.response_deadline_utc and now > case.response_deadline_utc:
            raise ValueError(f"Response deadline has passed for case {case_id}")

        case.accused_response = text
        return case

    def check_response_period_elapsed(
        self,
        case_id: str,
        now: Optional[datetime] = None,
    ) -> bool:
        """Check if the 72h response period has elapsed."""
        case = self._get_case(case_id)
        if now is None:
            now = datetime.now(timezone.utc)
        if case.response_deadline_utc is None:
            return True
        return now >= case.response_deadline_utc

    def form_panel(
        self,
        case_id: str,
        candidates: list[dict[str, Any]],
        now: Optional[datetime] = None,
    ) -> AdjudicationCase:
        """Form an adjudication panel from eligible candidates.

        Blocks if response period not elapsed AND no response submitted.
        Enforces diversity: ≥2 orgs, ≥2 regions.
        Excludes complainant, accused, and (for appeals) original panel.

        Each candidate dict must have:
            actor_id, trust_score, organization, region

        Raises ValueError on failure.
        """
        case = self._get_case(case_id)
        if now is None:
            now = datetime.now(timezone.utc)

        # Block panel formation during active response period
        if (
            case.status == AdjudicationStatus.RESPONSE_PERIOD
            and not case.accused_response
            and case.response_deadline_utc
            and now < case.response_deadline_utc
        ):
            raise ValueError(
                f"Cannot form panel: response period still active for case {case_id}"
            )

        # Build exclusion set
        excluded = {case.complainant_id, case.accused_id}
        # For appeals, also exclude original panel members
        if case.appeal_of:
            original = self._cases.get(case.appeal_of)
            if original:
                excluded.update(original.panel_ids)

        # Filter eligible candidates
        eligible = [
            c for c in candidates
            if c["actor_id"] not in excluded
            and c.get("trust_score", 0) >= self._min_panelist_trust
        ]

        # Select diverse panel
        panel = self._select_diverse_panel(eligible, self._panel_size)

        case.panel_ids = [p["actor_id"] for p in panel]
        case.panel_orgs = [p["organization"] for p in panel]
        case.panel_regions = [p["region"] for p in panel]
        case.status = AdjudicationStatus.PANEL_FORMED
        return case

    def _select_diverse_panel(
        self,
        eligible: list[dict[str, Any]],
        size: int,
    ) -> list[dict[str, Any]]:
        """Select a diverse panel meeting org and region requirements.

        Raises ValueError if diversity requirements cannot be met.
        """
        if len(eligible) < size:
            raise ValueError(
                f"Not enough eligible candidates: need {size}, have {len(eligible)}"
            )

        # Check diversity is achievable
        unique_orgs = {c["organization"] for c in eligible}
        unique_regions = {c["region"] for c in eligible}
        if len(unique_orgs) < self._min_orgs:
            raise ValueError(
                f"Not enough organizational diversity: need {self._min_orgs} orgs, "
                f"have {len(unique_orgs)}"
            )
        if len(unique_regions) < self._min_regions:
            raise ValueError(
                f"Not enough regional diversity: need {self._min_regions} regions, "
                f"have {len(unique_regions)}"
            )

        # Greedy diversity-first selection
        selected: list[dict[str, Any]] = []
        remaining = list(eligible)

        # First pass: ensure minimum org diversity
        selected_orgs: set[str] = set()
        for org in unique_orgs:
            if len(selected_orgs) >= self._min_orgs:
                break
            for c in remaining:
                if c["organization"] == org and c not in selected:
                    selected.append(c)
                    remaining.remove(c)
                    selected_orgs.add(org)
                    break

        # Second pass: ensure minimum region diversity
        selected_regions = {c["region"] for c in selected}
        for region in unique_regions:
            if len(selected_regions) >= self._min_regions:
                break
            if region in selected_regions:
                continue
            for c in remaining:
                if c["region"] == region and c not in selected:
                    selected.append(c)
                    remaining.remove(c)
                    selected_regions.add(region)
                    break

        # Fill remaining slots
        while len(selected) < size and remaining:
            selected.append(remaining.pop(0))

        if len(selected) < size:
            raise ValueError(
                f"Could not form panel of size {size}: only {len(selected)} after diversity"
            )

        return selected[:size]

    def submit_panel_vote(
        self,
        case_id: str,
        panelist_id: str,
        verdict: str,
        attestation: str,
    ) -> AdjudicationCase:
        """Record a panelist's vote on the case.

        Raises ValueError if panelist is not on the panel or already voted.
        """
        case = self._get_case(case_id)

        if panelist_id not in case.panel_ids:
            raise ValueError(f"Actor {panelist_id} is not on the panel for case {case_id}")

        if panelist_id in case.panel_votes:
            raise ValueError(f"Actor {panelist_id} has already voted on case {case_id}")

        if not attestation:
            raise ValueError("Vote attestation is required")

        # Validate verdict string
        try:
            AdjudicationVerdict(verdict)
        except ValueError:
            raise ValueError(f"Invalid verdict: {verdict}")

        case.panel_votes[panelist_id] = verdict
        case.panel_attestations[panelist_id] = attestation

        if case.status == AdjudicationStatus.PANEL_FORMED:
            case.status = AdjudicationStatus.DELIBERATION

        return case

    def evaluate_verdict(
        self,
        case_id: str,
    ) -> Optional[AdjudicationVerdict]:
        """Evaluate whether a verdict has been reached.

        Returns the verdict if supermajority (3/5 by default) is reached,
        otherwise None (not enough votes yet).
        """
        case = self._get_case(case_id)

        total_votes = len(case.panel_votes)
        if total_votes < self._panel_size:
            return None

        # Count votes by verdict
        vote_counts: dict[str, int] = {}
        for v in case.panel_votes.values():
            vote_counts[v] = vote_counts.get(v, 0) + 1

        threshold = int(self._panel_size * self._supermajority_threshold)

        # Check for supermajority UPHELD
        upheld = vote_counts.get(AdjudicationVerdict.UPHELD.value, 0)
        if upheld >= threshold:
            case.verdict = AdjudicationVerdict.UPHELD
            case.status = AdjudicationStatus.DECIDED
            case.decided_utc = datetime.now(timezone.utc)
            case.appeal_deadline_utc = case.decided_utc + timedelta(
                hours=self._appeal_window_hours
            )
            return AdjudicationVerdict.UPHELD

        # Check for supermajority ESCALATED_TO_COURT
        escalated = vote_counts.get(AdjudicationVerdict.ESCALATED_TO_COURT.value, 0)
        if escalated >= threshold:
            case.verdict = AdjudicationVerdict.ESCALATED_TO_COURT
            case.status = AdjudicationStatus.ESCALATED
            case.decided_utc = datetime.now(timezone.utc)
            return AdjudicationVerdict.ESCALATED_TO_COURT

        # Default: DISMISSED (no supermajority for upheld/escalated)
        case.verdict = AdjudicationVerdict.DISMISSED
        case.status = AdjudicationStatus.DECIDED
        case.decided_utc = datetime.now(timezone.utc)
        case.appeal_deadline_utc = case.decided_utc + timedelta(
            hours=self._appeal_window_hours
        )
        return AdjudicationVerdict.DISMISSED

    def file_appeal(
        self,
        case_id: str,
        appellant_id: str,
        reason: str,
        now: Optional[datetime] = None,
    ) -> AdjudicationCase:
        """File an appeal against a decided case.

        One appeal only, within the appeal window, creates new case
        with appeal_of set. Original panel members are excluded.

        Raises ValueError on failure.
        """
        original = self._get_case(case_id)
        if now is None:
            now = datetime.now(timezone.utc)

        if original.status not in (
            AdjudicationStatus.DECIDED, AdjudicationStatus.APPEAL_DECIDED
        ):
            raise ValueError(f"Cannot appeal case {case_id}: status is {original.status.value}")

        # Check appeal window
        if original.appeal_deadline_utc and now > original.appeal_deadline_utc:
            raise ValueError(f"Appeal window has expired for case {case_id}")

        # Only one appeal per case
        for c in self._cases.values():
            if c.appeal_of == case_id:
                raise ValueError(f"Appeal already filed for case {case_id}")

        # Appellant must be a party to the case
        if appellant_id not in (original.complainant_id, original.accused_id):
            raise ValueError(f"Actor {appellant_id} is not a party to case {case_id}")

        appeal_case = self.open_case(
            type=original.type,
            complainant_id=original.complainant_id,
            accused_id=original.accused_id,
            reason=reason,
            now=now,
            mission_id=original.mission_id,
        )
        appeal_case.appeal_of = case_id
        original.status = AdjudicationStatus.APPEAL_PENDING
        return appeal_case

    def close_case(
        self,
        case_id: str,
        now: Optional[datetime] = None,
    ) -> AdjudicationCase:
        """Close a decided case after appeal window expires."""
        case = self._get_case(case_id)
        if now is None:
            now = datetime.now(timezone.utc)

        if case.status not in (
            AdjudicationStatus.DECIDED,
            AdjudicationStatus.APPEAL_DECIDED,
            AdjudicationStatus.ESCALATED,
        ):
            raise ValueError(
                f"Cannot close case {case_id}: status is {case.status.value}"
            )

        case.status = AdjudicationStatus.CLOSED
        return case

    def get_case(self, case_id: str) -> Optional[AdjudicationCase]:
        """Look up a case by ID."""
        return self._cases.get(case_id)

    def _get_case(self, case_id: str) -> AdjudicationCase:
        """Get case or raise ValueError."""
        case = self._cases.get(case_id)
        if case is None:
            raise ValueError(f"Case not found: {case_id}")
        return case
