"""Compliance screener — harmful work prevention.

Constitutional prohibition on work that increases human suffering.
Three-layer enforcement:
1. Automated screening at mission creation (this module).
2. Compliance quorum for grey areas (existing normative resolution).
3. Post-hoc complaints for completed missions.

The screener answers one question: "Does this mission description,
evaluated in good faith, involve prohibited activity?"

Design test #45: Can a prohibited-category mission pass compliance
screening? If yes, reject design.

Design test #46: Can a suspended actor post, bid, review, or vote?
If yes, reject design.
"""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import FrozenSet, Optional


class ComplianceVerdict(str, enum.Enum):
    """Outcome of automated compliance screening."""
    CLEAR = "clear"
    FLAGGED = "flagged"
    REJECTED = "rejected"


class ComplaintStatus(str, enum.Enum):
    """Lifecycle state of a compliance complaint."""
    FILED = "filed"
    UNDER_REVIEW = "under_review"
    UPHELD = "upheld"
    DISMISSED = "dismissed"


@dataclass(frozen=True)
class ComplianceResult:
    """Outcome of automated mission screening.

    - CLEAR: mission proceeds normally.
    - FLAGGED: mission requires human compliance review.
    - REJECTED: mission blocked — prohibited category matched.
    """
    verdict: ComplianceVerdict
    categories_matched: list[str] = field(default_factory=list)
    reason: str = ""
    confidence: float = 1.0
    screened_utc: Optional[datetime] = None


@dataclass
class ComplianceComplaint:
    """Post-hoc compliance complaint against a completed mission.

    Filed by any actor. Triggers compliance review by panel.
    """
    complaint_id: str
    mission_id: str
    complainant_id: str
    reason: str
    category: str
    filed_utc: datetime
    status: ComplaintStatus = ComplaintStatus.FILED


class ComplianceScreener:
    """Automated compliance screening for mission proposals.

    Checks mission title, description, and tags against a set of
    prohibited categories. The screener is deliberately conservative:
    exact keyword matching produces REJECTED, partial/contextual
    matching produces FLAGGED for human review.

    Constitutional invariant: prohibited-category missions MUST NOT
    pass screening. The screener is fail-closed — if in doubt, flag.
    """

    PROHIBITED_CATEGORIES: FrozenSet[str] = frozenset({
        "weapons_development",
        "weapons_manufacturing",
        "weapons_trafficking",
        "surveillance_tools",
        "exploitation_of_persons",
        "child_exploitation",
        "financial_fraud",
        "identity_theft",
        "biological_weapons",
        "chemical_weapons",
        "nuclear_weapons",
        "terrorism_support",
        "forced_labor",
        "money_laundering",
        "sanctions_evasion",
        "environmental_destruction",
        "disinformation_campaigns",
    })

    # Categories with no statute of limitations
    NO_STATUTE_LIMIT_CATEGORIES: FrozenSet[str] = frozenset({
        "weapons_development",
        "weapons_manufacturing",
        "weapons_trafficking",
        "biological_weapons",
        "chemical_weapons",
        "nuclear_weapons",
        "exploitation_of_persons",
        "child_exploitation",
        "terrorism_support",
        "forced_labor",
    })

    # Keywords that produce an immediate REJECTED verdict
    _REJECT_KEYWORDS: dict[str, list[str]] = {
        "weapons_development": ["weapon design", "weapons development", "arms development"],
        "weapons_manufacturing": ["weapon manufacturing", "weapons manufacturing", "arms manufacturing", "gun production"],
        "weapons_trafficking": ["weapons trafficking", "arms trafficking", "gun trafficking", "illegal arms"],
        "surveillance_tools": ["mass surveillance", "surveillance tool", "spyware development", "stalkerware"],
        "exploitation_of_persons": ["human trafficking", "exploitation of persons", "forced prostitution"],
        "child_exploitation": ["child exploitation", "csam", "child abuse material"],
        "financial_fraud": ["financial fraud", "ponzi scheme", "pump and dump"],
        "identity_theft": ["identity theft", "credential theft", "phishing kit"],
        "biological_weapons": ["biological weapon", "bioweapon", "weaponised pathogen", "weaponized pathogen"],
        "chemical_weapons": ["chemical weapon", "nerve agent", "weaponised chemical", "weaponized chemical"],
        "nuclear_weapons": ["nuclear weapon", "nuclear warhead", "enrichment for weapons"],
        "terrorism_support": ["terrorism support", "terrorist financing", "radicalisation material", "radicalization material"],
        "forced_labor": ["forced labor", "forced labour", "slave labor", "slave labour"],
        "money_laundering": ["money laundering", "launder proceeds", "wash money"],
        "sanctions_evasion": ["sanctions evasion", "evade sanctions", "circumvent sanctions"],
        "environmental_destruction": ["illegal deforestation", "toxic dumping", "illegal waste disposal"],
        "disinformation_campaigns": ["disinformation campaign", "coordinated inauthentic", "fake news factory"],
    }

    # Keywords that produce a FLAGGED verdict (softer matches)
    _FLAG_KEYWORDS: dict[str, list[str]] = {
        "weapons_development": ["weapon", "firearm", "munition", "armament"],
        "surveillance_tools": ["surveillance", "tracking device", "monitoring tool"],
        "exploitation_of_persons": ["exploitation", "coercion"],
        "financial_fraud": ["fraud", "scam", "deceptive scheme"],
        "identity_theft": ["phishing", "credential harvesting"],
        "money_laundering": ["laundering", "shell company"],
        "disinformation_campaigns": ["disinformation", "propaganda", "fake news"],
    }

    def __init__(self) -> None:
        self._complaints: dict[str, ComplianceComplaint] = {}

    def screen_mission(
        self,
        title: str,
        description: str,
        tags: Optional[list[str]] = None,
        now: Optional[datetime] = None,
    ) -> ComplianceResult:
        """Screen a mission proposal against prohibited categories.

        Returns REJECTED for exact prohibited-keyword matches,
        FLAGGED for softer matches, CLEAR otherwise.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        combined = f"{title} {description} {' '.join(tags or [])}".lower()
        combined = re.sub(r"[^a-z0-9\s]", " ", combined)

        # Phase 1: Check for REJECTED matches (high confidence)
        rejected_categories: list[str] = []
        for category, keywords in self._REJECT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in combined:
                    rejected_categories.append(category)
                    break

        if rejected_categories:
            return ComplianceResult(
                verdict=ComplianceVerdict.REJECTED,
                categories_matched=sorted(set(rejected_categories)),
                reason=f"Prohibited content detected: {', '.join(sorted(set(rejected_categories)))}",
                confidence=1.0,
                screened_utc=now,
            )

        # Phase 2: Check for FLAGGED matches (lower confidence)
        flagged_categories: list[str] = []
        for category, keywords in self._FLAG_KEYWORDS.items():
            for keyword in keywords:
                if keyword in combined:
                    flagged_categories.append(category)
                    break

        if flagged_categories:
            return ComplianceResult(
                verdict=ComplianceVerdict.FLAGGED,
                categories_matched=sorted(set(flagged_categories)),
                reason=f"Potential compliance concern: {', '.join(sorted(set(flagged_categories)))}",
                confidence=0.6,
                screened_utc=now,
            )

        # Phase 3: Clear
        return ComplianceResult(
            verdict=ComplianceVerdict.CLEAR,
            categories_matched=[],
            reason="No compliance concerns detected",
            confidence=1.0,
            screened_utc=now,
        )

    def screen_gcf_proposal(
        self,
        title: str,
        description: str,
        recipient_description: str,
        deliverables: list[str],
        now: Optional[datetime] = None,
    ) -> ComplianceResult:
        """Screen a GCF disbursement proposal against prohibited categories.

        Same logic as screen_mission but combines all proposal text fields:
        title + description + recipient_description + deliverables.

        Design test #56: Can a disbursement proposal bypass compliance screening?
        If yes, reject design.
        """
        combined_text = " ".join([
            title,
            description,
            recipient_description,
            " ".join(deliverables),
        ])
        return self.screen_mission(
            title=combined_text,
            description="",
            tags=None,
            now=now,
        )

    def file_compliance_complaint(
        self,
        mission_id: str,
        complainant_id: str,
        reason: str,
        category: str,
        now: Optional[datetime] = None,
    ) -> ComplianceComplaint:
        """File a post-hoc compliance complaint against a mission.

        Raises ValueError if category is not a known prohibited category.
        """
        if category not in self.PROHIBITED_CATEGORIES:
            raise ValueError(
                f"Unknown prohibited category: {category}. "
                f"Must be one of: {sorted(self.PROHIBITED_CATEGORIES)}"
            )
        if not reason.strip():
            raise ValueError("Complaint reason must not be empty")

        if now is None:
            now = datetime.now(timezone.utc)

        complaint_id = f"cc_{uuid.uuid4().hex[:12]}"
        complaint = ComplianceComplaint(
            complaint_id=complaint_id,
            mission_id=mission_id,
            complainant_id=complainant_id,
            reason=reason.strip(),
            category=category,
            filed_utc=now,
        )
        self._complaints[complaint_id] = complaint
        return complaint

    def get_complaint(self, complaint_id: str) -> Optional[ComplianceComplaint]:
        """Retrieve a complaint by ID."""
        return self._complaints.get(complaint_id)

    def complaints_for_mission(self, mission_id: str) -> list[ComplianceComplaint]:
        """Return all complaints filed against a given mission."""
        return [c for c in self._complaints.values() if c.mission_id == mission_id]

    def is_within_statute(
        self,
        complaint: ComplianceComplaint,
        statute_of_limitations_days: int = 180,
        now: Optional[datetime] = None,
    ) -> bool:
        """Check whether a complaint is within the statute of limitations.

        No-limit categories (weapons, exploitation, etc.) are always in-statute.
        """
        if complaint.category in self.NO_STATUTE_LIMIT_CATEGORIES:
            return True
        if now is None:
            now = datetime.now(timezone.utc)
        elapsed = (now - complaint.filed_utc).days
        return elapsed <= statute_of_limitations_days
