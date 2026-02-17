"""Tier 3 Constitutional Court — highest adjudication authority.

The Constitutional Court handles cases escalated from Tier 2 adjudication.
It issues advisory precedent (not binding) and can uphold, overturn, or
remand decisions.

Constitutional requirements:
- 7-member panel of human-only justices.
- ≥3 regions, ≥3 organisations.
- Trust ≥ 0.70 for all justices.
- 5/7 supermajority required to OVERTURN.
- Simple majority for UPHOLD or REMAND.
- Precedent is advisory only (soft precedent).
"""

from __future__ import annotations

import uuid
import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


class CourtCaseStatus(str, enum.Enum):
    """Lifecycle status of a Constitutional Court case."""
    OPENED = "opened"
    PANEL_FORMED = "panel_formed"
    DELIBERATION = "deliberation"
    DECIDED = "decided"
    CLOSED = "closed"


@dataclass
class ConstitutionalCourtCase:
    """A case before the Constitutional Court."""
    court_case_id: str
    source_adjudication_id: str
    question: str
    panel_ids: list[str] = field(default_factory=list)
    panel_votes: dict[str, str] = field(default_factory=dict)
    panel_attestations: dict[str, str] = field(default_factory=dict)
    panel_orgs: list[str] = field(default_factory=list)
    panel_regions: list[str] = field(default_factory=list)
    verdict: Optional[str] = None
    precedent_note: Optional[str] = None
    opened_utc: Optional[datetime] = None
    decided_utc: Optional[datetime] = None
    status: CourtCaseStatus = CourtCaseStatus.OPENED


@dataclass(frozen=True)
class PrecedentEntry:
    """An advisory precedent from a Constitutional Court decision."""
    precedent_id: str
    court_case_id: str
    question: str
    ruling_summary: str
    decided_utc: datetime
    advisory_only: bool = True


class ConstitutionalCourt:
    """Tier 3 Constitutional Court — highest adjudication authority.

    Usage:
        court = ConstitutionalCourt(config)
        case = court.open_court_case(source_id, question, now)
        case = court.form_court_panel(case_id, candidates, now)
        case = court.submit_court_vote(case_id, justice_id, verdict, att, note)
        verdict = court.evaluate_court_verdict(case_id)
        precedent = court.record_precedent(case_id)
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._cases: dict[str, ConstitutionalCourtCase] = {}
        self._precedents: list[PrecedentEntry] = []
        self._panel_size = config.get("panel_size", 7)
        self._supermajority_threshold = config.get("supermajority_threshold", 5)
        self._min_justice_trust = config.get("min_justice_trust", 0.70)
        self._min_regions = config.get("min_regions", 3)
        self._min_orgs = config.get("min_organizations", 3)
        self._human_only = config.get("human_only", True)

    def open_court_case(
        self,
        source_adjudication_id: str,
        question: str,
        now: Optional[datetime] = None,
    ) -> ConstitutionalCourtCase:
        """Open a new Constitutional Court case."""
        if now is None:
            now = datetime.now(timezone.utc)

        court_case_id = f"court-{uuid.uuid4().hex[:12]}"
        case = ConstitutionalCourtCase(
            court_case_id=court_case_id,
            source_adjudication_id=source_adjudication_id,
            question=question,
            opened_utc=now,
            status=CourtCaseStatus.OPENED,
        )
        self._cases[court_case_id] = case
        return case

    def form_court_panel(
        self,
        court_case_id: str,
        candidates: list[dict[str, Any]],
        now: Optional[datetime] = None,
    ) -> ConstitutionalCourtCase:
        """Form a 7-justice panel for the Constitutional Court.

        Requirements:
        - ≥3 regions, ≥3 orgs.
        - Trust ≥ 0.70.
        - Human only (if configured).

        Each candidate dict must have:
            actor_id, trust_score, organization, region, actor_kind

        Raises ValueError on failure.
        """
        case = self._get_case(court_case_id)

        # Filter eligible: trust >= threshold and human-only
        eligible = [
            c for c in candidates
            if c.get("trust_score", 0) >= self._min_justice_trust
            and (not self._human_only or c.get("actor_kind") == "human")
        ]

        if len(eligible) < self._panel_size:
            raise ValueError(
                f"Not enough eligible justices: need {self._panel_size}, "
                f"have {len(eligible)}"
            )

        # Check diversity
        unique_orgs = {c["organization"] for c in eligible}
        unique_regions = {c["region"] for c in eligible}
        if len(unique_orgs) < self._min_orgs:
            raise ValueError(
                f"Not enough organizational diversity: need {self._min_orgs}, "
                f"have {len(unique_orgs)}"
            )
        if len(unique_regions) < self._min_regions:
            raise ValueError(
                f"Not enough regional diversity: need {self._min_regions}, "
                f"have {len(unique_regions)}"
            )

        # Diversity-first selection
        selected: list[dict[str, Any]] = []
        remaining = list(eligible)

        # Ensure minimum org diversity
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

        # Ensure minimum region diversity
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

        # Fill remaining
        while len(selected) < self._panel_size and remaining:
            selected.append(remaining.pop(0))

        if len(selected) < self._panel_size:
            raise ValueError(
                f"Could not form court panel of size {self._panel_size}"
            )

        case.panel_ids = [p["actor_id"] for p in selected]
        case.panel_orgs = [p["organization"] for p in selected]
        case.panel_regions = [p["region"] for p in selected]
        case.status = CourtCaseStatus.PANEL_FORMED
        return case

    def submit_court_vote(
        self,
        court_case_id: str,
        justice_id: str,
        verdict: str,
        attestation: str,
        precedent_note: Optional[str] = None,
    ) -> ConstitutionalCourtCase:
        """Record a justice's vote on a court case.

        Valid verdicts: "uphold", "overturn", "remand".
        Raises ValueError if justice not on panel or already voted.
        """
        case = self._get_case(court_case_id)

        if justice_id not in case.panel_ids:
            raise ValueError(
                f"Justice {justice_id} is not on the panel for case {court_case_id}"
            )

        if justice_id in case.panel_votes:
            raise ValueError(
                f"Justice {justice_id} has already voted on case {court_case_id}"
            )

        if verdict not in ("uphold", "overturn", "remand"):
            raise ValueError(f"Invalid court verdict: {verdict}")

        if not attestation:
            raise ValueError("Vote attestation is required")

        case.panel_votes[justice_id] = verdict
        case.panel_attestations[justice_id] = attestation
        if precedent_note:
            case.precedent_note = precedent_note

        if case.status == CourtCaseStatus.PANEL_FORMED:
            case.status = CourtCaseStatus.DELIBERATION

        return case

    def evaluate_court_verdict(
        self,
        court_case_id: str,
    ) -> Optional[str]:
        """Evaluate whether a court verdict has been reached.

        - 5/7 supermajority required for OVERTURN.
        - Simple majority for UPHOLD or REMAND.

        Returns the verdict string or None if not enough votes.
        """
        case = self._get_case(court_case_id)

        total_votes = len(case.panel_votes)
        if total_votes < self._panel_size:
            return None

        vote_counts: dict[str, int] = {}
        for v in case.panel_votes.values():
            vote_counts[v] = vote_counts.get(v, 0) + 1

        overturn = vote_counts.get("overturn", 0)
        if overturn >= self._supermajority_threshold:
            case.verdict = "overturn"
            case.status = CourtCaseStatus.DECIDED
            case.decided_utc = datetime.now(timezone.utc)
            return "overturn"

        # Simple majority for uphold or remand
        uphold = vote_counts.get("uphold", 0)
        remand = vote_counts.get("remand", 0)

        if remand > uphold and remand > overturn:
            case.verdict = "remand"
            case.status = CourtCaseStatus.DECIDED
            case.decided_utc = datetime.now(timezone.utc)
            return "remand"

        # Default to uphold
        case.verdict = "uphold"
        case.status = CourtCaseStatus.DECIDED
        case.decided_utc = datetime.now(timezone.utc)
        return "uphold"

    def record_precedent(
        self,
        court_case_id: str,
    ) -> PrecedentEntry:
        """Record an advisory precedent from a decided case.

        Raises ValueError if case is not decided.
        """
        case = self._get_case(court_case_id)
        if case.status != CourtCaseStatus.DECIDED:
            raise ValueError(
                f"Cannot record precedent: case {court_case_id} is not decided"
            )

        precedent = PrecedentEntry(
            precedent_id=f"prec-{uuid.uuid4().hex[:12]}",
            court_case_id=court_case_id,
            question=case.question,
            ruling_summary=case.precedent_note or f"Court {case.verdict}: {case.question}",
            decided_utc=case.decided_utc or datetime.now(timezone.utc),
            advisory_only=True,
        )
        self._precedents.append(precedent)
        return precedent

    def search_precedents(self, keywords: str) -> list[PrecedentEntry]:
        """Search precedents by keyword (simple substring match)."""
        kw_lower = keywords.lower()
        return [
            p for p in self._precedents
            if kw_lower in p.question.lower() or kw_lower in p.ruling_summary.lower()
        ]

    def get_case(self, court_case_id: str) -> Optional[ConstitutionalCourtCase]:
        """Look up a court case by ID."""
        return self._cases.get(court_case_id)

    def _get_case(self, court_case_id: str) -> ConstitutionalCourtCase:
        """Get case or raise ValueError."""
        case = self._cases.get(court_case_id)
        if case is None:
            raise ValueError(f"Court case not found: {court_case_id}")
        return case
