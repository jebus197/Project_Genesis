"""Constitutional Amendment Engine — governance over how the constitution changes.

Manages the full lifecycle of constitutional amendments, from proposal through
multi-chamber voting to final confirmation. Handles both regular amendments
(standard chamber pass thresholds) and entrenched amendments (80% supermajority
+ 50% participation + 90-day cooling-off + confirmation vote).

Architecture:
- AmendmentEngine handles governance (proposals, chamber voting, lifecycle).
- The service layer bridges the engine with roster, trust records, and events.
- Single-responsibility: the engine never touches actor records directly.

Constitutional constraints:
- Proposers must be ACTIVE humans with trust >= tau_prop (service layer check).
- Machine constitutional voting weight is permanently zero (w_M_const = 0).
- Three independent chambers with no member overlap (structural requirement).
- Geographic diversity: R_min regions, c_max concentration per phase.
- Commission rates are formula-determined, not ballot-amendable.
- Entrenched provisions require the full amendment pathway — no shortcuts.

Design test #57: Can a non-entrenched amendment bypass chamber voting?
If yes, reject design.

Design test #58: Can an entrenched amendment skip the 90-day cooling-off?
If yes, reject design.

Design test #59: Can a commission rate be changed by ballot?
If yes, reject design.

Design test #60: Can the cooling-off period be shortened without going through
its own entrenched process? If yes, reject design.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from genesis.models.governance import Chamber, ChamberKind


# Commission rate parameters that are formula-only — not ballot-amendable.
# Design test #39a: commission is deterministic from costs, not ballot-determined.
FORMULA_ONLY_PARAMS: frozenset[str] = frozenset({
    "commission_floor",
    "commission_ceiling",
    "commission_safety_margin",
    "commission_reserve_target_months",
    "commission_min_fee_usdc",
    "commission_window_days",
    "commission_window_min_missions",
    "commission_bootstrap_min_rate",
    "commission_reserve_maintenance_rate",
})


class AmendmentStatus(str, enum.Enum):
    """Lifecycle state of a constitutional amendment.

    Entrenched path:
        PROPOSED → PROPOSAL_CHAMBER_VOTING → RATIFICATION_CHAMBER_VOTING →
        CHALLENGE_WINDOW → CHALLENGE_CHAMBER_VOTING (if challenged) →
        COOLING_OFF → CONFIRMATION_VOTE → CONFIRMED / REJECTED

    Non-entrenched path:
        PROPOSED → PROPOSAL_CHAMBER_VOTING → RATIFICATION_CHAMBER_VOTING →
        CHALLENGE_WINDOW → CHALLENGE_CHAMBER_VOTING (if challenged) →
        CONFIRMED / REJECTED  (skip COOLING_OFF + CONFIRMATION_VOTE)
    """
    PROPOSED = "proposed"
    PROPOSAL_CHAMBER_VOTING = "proposal_chamber_voting"
    RATIFICATION_CHAMBER_VOTING = "ratification_chamber_voting"
    CHALLENGE_WINDOW = "challenge_window"
    CHALLENGE_CHAMBER_VOTING = "challenge_chamber_voting"
    COOLING_OFF = "cooling_off"
    CONFIRMATION_VOTE = "confirmation_vote"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    APPLIED = "applied"


@dataclass(frozen=True)
class AmendmentVote:
    """A single vote in a chamber proceeding or confirmation vote.

    Frozen — votes are immutable once cast.
    """
    vote_id: str
    voter_id: str
    chamber: str  # ChamberKind value or "confirmation"
    vote: bool  # True = approve, False = reject
    attestation: str
    cast_utc: datetime
    region: str
    organization: str


@dataclass
class AmendmentProposal:
    """A proposal to amend the constitution.

    Mutable — transitions through the amendment lifecycle.
    """
    proposal_id: str
    proposer_id: str
    provision_key: str
    current_value: Any
    proposed_value: Any
    justification: str
    is_entrenched: bool
    status: AmendmentStatus = AmendmentStatus.PROPOSED
    created_utc: Optional[datetime] = None
    decided_utc: Optional[datetime] = None
    # Chamber panels: ChamberKind value → list of voter IDs
    chamber_panels: dict[str, list[str]] = field(default_factory=dict)
    # Chamber votes: ChamberKind value → list of AmendmentVote
    chamber_votes: dict[str, list[AmendmentVote]] = field(default_factory=dict)
    challenge_filed: bool = False
    cooling_off_starts_utc: Optional[datetime] = None
    cooling_off_ends_utc: Optional[datetime] = None
    # Confirmation vote (entrenched only)
    confirmation_panel: Optional[list[str]] = None
    confirmation_votes: list[AmendmentVote] = field(default_factory=list)


class ConstitutionalViolation(Exception):
    """Raised when an operation would violate constitutional constraints.

    This is a structural safety gate, not an advisory warning.
    """
    pass


class AmendmentEngine:
    """Manages constitutional amendment proposal lifecycle and voting.

    This engine handles governance (proposals, chamber voting, decisions).
    It does NOT touch actor records or trust — that's the service layer's job.

    Usage:
        engine = AmendmentEngine(config, constitutional_params)

        # Create amendment
        proposal = engine.create_amendment(proposer_id, provision_key, ...)

        # Select chamber panel and vote (sequentially)
        engine.select_chamber_panel(proposal_id, PROPOSAL, eligible, phase)
        engine.cast_chamber_vote(proposal_id, voter_id, PROPOSAL, True, ...)
        passed = engine.close_chamber_voting(proposal_id, PROPOSAL)

        # Continue through ratification, challenge, cooling-off, confirmation...
    """

    def __init__(
        self,
        config: dict[str, Any],
        constitutional_params: dict[str, Any],
    ) -> None:
        self._config = config
        self._params = constitutional_params
        self._proposals: dict[str, AmendmentProposal] = {}

        # Extract entrenched provision keys
        entrenched = self._params.get("entrenched_provisions", {})
        self._entrenched_keys: set[str] = {
            k for k in entrenched
            if not k.startswith("entrenched_")  # skip config params like entrenched_amendment_threshold
        }

    @classmethod
    def from_records(
        cls,
        config: dict[str, Any],
        constitutional_params: dict[str, Any],
        proposals: list[dict[str, Any]],
    ) -> AmendmentEngine:
        """Restore engine state from persisted records."""
        engine = cls(config, constitutional_params)
        for p in proposals:
            # Reconstruct chamber votes
            chamber_votes: dict[str, list[AmendmentVote]] = {}
            for chamber_key, votes_data in p.get("chamber_votes", {}).items():
                chamber_votes[chamber_key] = [
                    AmendmentVote(
                        vote_id=v["vote_id"],
                        voter_id=v["voter_id"],
                        chamber=v["chamber"],
                        vote=v["vote"],
                        attestation=v["attestation"],
                        cast_utc=datetime.fromisoformat(v["cast_utc"]),
                        region=v["region"],
                        organization=v["organization"],
                    )
                    for v in votes_data
                ]
            # Reconstruct confirmation votes
            confirmation_votes = [
                AmendmentVote(
                    vote_id=v["vote_id"],
                    voter_id=v["voter_id"],
                    chamber=v["chamber"],
                    vote=v["vote"],
                    attestation=v["attestation"],
                    cast_utc=datetime.fromisoformat(v["cast_utc"]),
                    region=v["region"],
                    organization=v["organization"],
                )
                for v in p.get("confirmation_votes", [])
            ]
            proposal = AmendmentProposal(
                proposal_id=p["proposal_id"],
                proposer_id=p["proposer_id"],
                provision_key=p["provision_key"],
                current_value=p["current_value"],
                proposed_value=p["proposed_value"],
                justification=p["justification"],
                is_entrenched=p["is_entrenched"],
                status=AmendmentStatus(p["status"]),
                created_utc=datetime.fromisoformat(p["created_utc"]) if p.get("created_utc") else None,
                decided_utc=datetime.fromisoformat(p["decided_utc"]) if p.get("decided_utc") else None,
                chamber_panels=p.get("chamber_panels", {}),
                chamber_votes=chamber_votes,
                challenge_filed=p.get("challenge_filed", False),
                cooling_off_starts_utc=datetime.fromisoformat(p["cooling_off_starts_utc"]) if p.get("cooling_off_starts_utc") else None,
                cooling_off_ends_utc=datetime.fromisoformat(p["cooling_off_ends_utc"]) if p.get("cooling_off_ends_utc") else None,
                confirmation_panel=p.get("confirmation_panel"),
                confirmation_votes=confirmation_votes,
            )
            engine._proposals[proposal.proposal_id] = proposal
        return engine

    def is_provision_entrenched(self, provision_key: str) -> bool:
        """Check if a provision is in the entrenched list."""
        return provision_key in self._entrenched_keys

    def create_amendment(
        self,
        proposer_id: str,
        provision_key: str,
        current_value: Any,
        proposed_value: Any,
        justification: str,
        now: Optional[datetime] = None,
    ) -> AmendmentProposal:
        """Create a new constitutional amendment proposal.

        Validates:
        - Justification non-empty.
        - Provision key is not a formula-only parameter (commission rates).
        - Auto-detects whether the provision is entrenched.

        Trust and eligibility checks are done at the service layer.

        Returns:
            The created AmendmentProposal.

        Raises:
            ValueError: On validation failure.
        """
        if not justification.strip():
            raise ValueError("Amendment justification must not be empty")

        # Commission rates are formula-determined, not ballot-amendable
        if provision_key in FORMULA_ONLY_PARAMS:
            raise ValueError(
                f"Cannot amend '{provision_key}' by ballot — "
                f"commission rates are formula-determined (Design test #39a)"
            )

        if now is None:
            now = datetime.now(timezone.utc)

        is_entrenched = self.is_provision_entrenched(provision_key)

        proposal_id = f"amend_{uuid.uuid4().hex[:12]}"
        proposal = AmendmentProposal(
            proposal_id=proposal_id,
            proposer_id=proposer_id,
            provision_key=provision_key,
            current_value=current_value,
            proposed_value=proposed_value,
            justification=justification.strip(),
            is_entrenched=is_entrenched,
            created_utc=now,
        )
        self._proposals[proposal_id] = proposal
        return proposal

    def get_amendment(self, proposal_id: str) -> Optional[AmendmentProposal]:
        """Retrieve an amendment by ID."""
        return self._proposals.get(proposal_id)

    def list_amendments(
        self,
        status: Optional[AmendmentStatus] = None,
    ) -> list[AmendmentProposal]:
        """List amendments, optionally filtered by status."""
        if status is None:
            return list(self._proposals.values())
        return [p for p in self._proposals.values() if p.status == status]

    # ------------------------------------------------------------------
    # Chamber panel selection
    # ------------------------------------------------------------------

    def select_chamber_panel(
        self,
        proposal_id: str,
        chamber_kind: ChamberKind,
        eligible_voters: list[dict[str, Any]],
        chamber_def: Chamber,
        r_min: int,
        c_max: float,
        now: Optional[datetime] = None,
    ) -> list[str]:
        """Select a geographically diverse chamber panel.

        Args:
            proposal_id: The amendment to select a panel for.
            chamber_kind: Which chamber (PROPOSAL, RATIFICATION, CHALLENGE).
            eligible_voters: List of dicts with keys: actor_id, region, organization.
            chamber_def: Chamber definition with size and pass_threshold.
            r_min: Minimum regions required.
            c_max: Maximum concentration from any single region (0.0-1.0).
            now: Timestamp.

        Returns:
            List of selected voter IDs.

        Raises:
            ValueError: If proposal not found, wrong status, or diversity unmet.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Amendment not found: {proposal_id}")

        # Validate status transitions
        expected_status = {
            ChamberKind.PROPOSAL: AmendmentStatus.PROPOSED,
            ChamberKind.RATIFICATION: AmendmentStatus.PROPOSAL_CHAMBER_VOTING,
            ChamberKind.CHALLENGE: AmendmentStatus.CHALLENGE_WINDOW,
        }
        # Ratification panel is selected after proposal passes
        if chamber_kind == ChamberKind.RATIFICATION:
            if proposal.status != AmendmentStatus.PROPOSAL_CHAMBER_VOTING:
                raise ValueError(
                    f"Cannot select ratification panel in status {proposal.status.value} "
                    f"(expected proposal_chamber_voting after proposal passes)"
                )
        elif chamber_kind == ChamberKind.CHALLENGE:
            if proposal.status != AmendmentStatus.CHALLENGE_WINDOW:
                raise ValueError(
                    f"Cannot select challenge panel in status {proposal.status.value}"
                )
        elif chamber_kind == ChamberKind.PROPOSAL:
            if proposal.status != AmendmentStatus.PROPOSED:
                raise ValueError(
                    f"Cannot select proposal panel in status {proposal.status.value}"
                )

        # Exclude voters already on another chamber panel for this amendment
        existing_panelists: set[str] = set()
        for panel_members in proposal.chamber_panels.values():
            existing_panelists.update(panel_members)

        candidates = [
            v for v in eligible_voters
            if v["actor_id"] not in existing_panelists
        ]

        size = chamber_def.size

        if len(candidates) < size:
            raise ValueError(
                f"Not enough eligible candidates for {chamber_kind.value} chamber: "
                f"need {size}, have {len(candidates)}"
            )

        # Check diversity is achievable
        unique_regions = {c["region"] for c in candidates}
        if len(unique_regions) < r_min:
            raise ValueError(
                f"Not enough regional diversity: need {r_min} regions, "
                f"have {len(unique_regions)}"
            )

        # Greedy diversity-first selection (same pattern as AdjudicationEngine)
        selected: list[dict[str, Any]] = []
        remaining = list(candidates)

        # First pass: ensure minimum region diversity
        selected_regions: set[str] = set()
        for region in unique_regions:
            if len(selected_regions) >= r_min:
                break
            for c in remaining:
                if c["region"] == region and c not in selected:
                    selected.append(c)
                    remaining.remove(c)
                    selected_regions.add(region)
                    break

        # Fill remaining slots respecting c_max concentration
        max_per_region = max(1, int(size * c_max))
        while len(selected) < size and remaining:
            region_counts: dict[str, int] = {}
            for s in selected:
                region_counts[s["region"]] = region_counts.get(s["region"], 0) + 1

            added = False
            for c in remaining:
                if region_counts.get(c["region"], 0) < max_per_region:
                    selected.append(c)
                    remaining.remove(c)
                    added = True
                    break

            if not added:
                # If all remaining violate c_max, we can't fill the panel
                raise ValueError(
                    f"Cannot fill {chamber_kind.value} chamber to size {size} "
                    f"while respecting c_max={c_max}"
                )

        panel_ids = [s["actor_id"] for s in selected]
        proposal.chamber_panels[chamber_kind.value] = panel_ids

        # Advance status for proposal chamber
        if chamber_kind == ChamberKind.PROPOSAL:
            proposal.status = AmendmentStatus.PROPOSAL_CHAMBER_VOTING
            proposal.chamber_votes[chamber_kind.value] = []

        return panel_ids

    # ------------------------------------------------------------------
    # Chamber voting
    # ------------------------------------------------------------------

    def cast_chamber_vote(
        self,
        proposal_id: str,
        voter_id: str,
        chamber_kind: ChamberKind,
        vote: bool,
        attestation: str,
        region: str,
        organization: str,
        now: Optional[datetime] = None,
    ) -> AmendmentVote:
        """Cast a vote in a chamber proceeding.

        Validates:
        - Amendment exists and is in the correct voting status.
        - Voter is a member of the specified chamber panel.
        - No duplicate votes (one vote per member).
        - Attestation is non-empty.

        Returns:
            The recorded AmendmentVote.

        Raises:
            ValueError: On validation failure.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Amendment not found: {proposal_id}")

        # Validate status matches chamber
        expected_status = {
            ChamberKind.PROPOSAL: AmendmentStatus.PROPOSAL_CHAMBER_VOTING,
            ChamberKind.RATIFICATION: AmendmentStatus.RATIFICATION_CHAMBER_VOTING,
            ChamberKind.CHALLENGE: AmendmentStatus.CHALLENGE_CHAMBER_VOTING,
        }
        if proposal.status != expected_status.get(chamber_kind):
            raise ValueError(
                f"Cannot vote in {chamber_kind.value} chamber while in status "
                f"{proposal.status.value}"
            )

        # Validate voter is panel member
        panel = proposal.chamber_panels.get(chamber_kind.value, [])
        if voter_id not in panel:
            raise ValueError(
                f"Voter {voter_id} is not a member of the {chamber_kind.value} panel"
            )

        # Duplicate vote check
        existing_votes = proposal.chamber_votes.get(chamber_kind.value, [])
        if any(v.voter_id == voter_id for v in existing_votes):
            raise ValueError(
                f"Voter {voter_id} has already voted in the {chamber_kind.value} chamber"
            )

        if not attestation.strip():
            raise ValueError("Vote attestation must not be empty")

        if now is None:
            now = datetime.now(timezone.utc)

        vote_id = f"amend_vote_{uuid.uuid4().hex[:12]}"
        amendment_vote = AmendmentVote(
            vote_id=vote_id,
            voter_id=voter_id,
            chamber=chamber_kind.value,
            vote=vote,
            attestation=attestation.strip(),
            cast_utc=now,
            region=region,
            organization=organization,
        )

        if chamber_kind.value not in proposal.chamber_votes:
            proposal.chamber_votes[chamber_kind.value] = []
        proposal.chamber_votes[chamber_kind.value].append(amendment_vote)

        return amendment_vote

    def close_chamber_voting(
        self,
        proposal_id: str,
        chamber_kind: ChamberKind,
        chamber_def: Chamber,
        now: Optional[datetime] = None,
    ) -> tuple[AmendmentProposal, bool]:
        """Close voting in a chamber and determine outcome.

        For entrenched amendments, additionally checks:
        - 80% supermajority of votes cast.
        - 50% participation of panel members.

        Returns:
            Tuple of (proposal, passed: bool).

        Raises:
            ValueError: If proposal not found or wrong status.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Amendment not found: {proposal_id}")

        expected_status = {
            ChamberKind.PROPOSAL: AmendmentStatus.PROPOSAL_CHAMBER_VOTING,
            ChamberKind.RATIFICATION: AmendmentStatus.RATIFICATION_CHAMBER_VOTING,
            ChamberKind.CHALLENGE: AmendmentStatus.CHALLENGE_CHAMBER_VOTING,
        }
        if proposal.status != expected_status.get(chamber_kind):
            raise ValueError(
                f"Cannot close {chamber_kind.value} voting in status "
                f"{proposal.status.value}"
            )

        if now is None:
            now = datetime.now(timezone.utc)

        votes = proposal.chamber_votes.get(chamber_kind.value, [])
        yes_count = sum(1 for v in votes if v.vote)
        no_count = sum(1 for v in votes if not v.vote)
        total_votes = yes_count + no_count
        panel_size = len(proposal.chamber_panels.get(chamber_kind.value, []))

        # Standard chamber pass threshold
        passed = yes_count >= chamber_def.pass_threshold

        # For entrenched amendments, additional constraints
        if proposal.is_entrenched and passed:
            supermajority = self._config.get("entrenched_amendment_threshold", 0.80)
            participation_min = self._config.get("entrenched_participation_minimum", 0.50)

            # Participation check: at least 50% of panel must vote
            if panel_size > 0 and total_votes < (panel_size * participation_min):
                passed = False

            # Supermajority check: at least 80% of votes cast must be yes
            if total_votes > 0 and (yes_count / total_votes) < supermajority:
                passed = False

        if not passed:
            proposal.status = AmendmentStatus.REJECTED
            proposal.decided_utc = now
            return proposal, False

        # Advance to next status
        if chamber_kind == ChamberKind.PROPOSAL:
            # Proposal passed → open ratification
            proposal.status = AmendmentStatus.RATIFICATION_CHAMBER_VOTING
            proposal.chamber_votes[ChamberKind.RATIFICATION.value] = []
        elif chamber_kind == ChamberKind.RATIFICATION:
            # Ratification passed → challenge window
            proposal.status = AmendmentStatus.CHALLENGE_WINDOW
        elif chamber_kind == ChamberKind.CHALLENGE:
            # Challenge passed → cooling-off (entrenched) or confirmed (non-entrenched)
            if proposal.is_entrenched:
                proposal.status = AmendmentStatus.COOLING_OFF
            else:
                proposal.status = AmendmentStatus.CONFIRMED
                proposal.decided_utc = now

        return proposal, True

    # ------------------------------------------------------------------
    # Challenge window
    # ------------------------------------------------------------------

    def file_challenge(
        self,
        proposal_id: str,
        challenger_id: str,
        now: Optional[datetime] = None,
    ) -> AmendmentProposal:
        """File a challenge during the challenge window.

        Returns:
            The updated proposal (now in CHALLENGE_CHAMBER_VOTING).

        Raises:
            ValueError: If proposal not found or wrong status.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Amendment not found: {proposal_id}")
        if proposal.status != AmendmentStatus.CHALLENGE_WINDOW:
            raise ValueError(
                f"Cannot file challenge in status {proposal.status.value}"
            )

        proposal.challenge_filed = True
        proposal.status = AmendmentStatus.CHALLENGE_CHAMBER_VOTING
        proposal.chamber_votes[ChamberKind.CHALLENGE.value] = []
        return proposal

    def advance_past_challenge_window(
        self,
        proposal_id: str,
        now: Optional[datetime] = None,
    ) -> AmendmentProposal:
        """Advance past the challenge window when no challenge is filed.

        Returns:
            The updated proposal.

        Raises:
            ValueError: If proposal not found or wrong status.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Amendment not found: {proposal_id}")
        if proposal.status != AmendmentStatus.CHALLENGE_WINDOW:
            raise ValueError(
                f"Cannot advance past challenge window in status {proposal.status.value}"
            )

        if now is None:
            now = datetime.now(timezone.utc)

        if proposal.is_entrenched:
            proposal.status = AmendmentStatus.COOLING_OFF
        else:
            proposal.status = AmendmentStatus.CONFIRMED
            proposal.decided_utc = now

        return proposal

    # ------------------------------------------------------------------
    # Cooling-off (entrenched only)
    # ------------------------------------------------------------------

    def start_cooling_off(
        self,
        proposal_id: str,
        now: Optional[datetime] = None,
    ) -> AmendmentProposal:
        """Start the 90-day cooling-off period for an entrenched amendment.

        Returns:
            The updated proposal.

        Raises:
            ValueError: If proposal not found, wrong status, or not entrenched.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Amendment not found: {proposal_id}")
        if proposal.status != AmendmentStatus.COOLING_OFF:
            raise ValueError(
                f"Cannot start cooling-off in status {proposal.status.value}"
            )
        if not proposal.is_entrenched:
            raise ValueError("Cooling-off only applies to entrenched amendments")

        if now is None:
            now = datetime.now(timezone.utc)

        cooling_off_days = self._config.get("entrenched_cooling_off_days", 90)
        proposal.cooling_off_starts_utc = now
        proposal.cooling_off_ends_utc = now + timedelta(days=cooling_off_days)
        return proposal

    def check_cooling_off_complete(
        self,
        proposal_id: str,
        now: Optional[datetime] = None,
    ) -> bool:
        """Check if the cooling-off period has elapsed.

        No acceleration. No exceptions. The timer simply counts days.

        Returns:
            True if now >= cooling_off_ends_utc.

        Raises:
            ValueError: If proposal not found.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Amendment not found: {proposal_id}")
        if proposal.cooling_off_ends_utc is None:
            return False

        if now is None:
            now = datetime.now(timezone.utc)

        return now >= proposal.cooling_off_ends_utc

    # ------------------------------------------------------------------
    # Confirmation vote (entrenched only)
    # ------------------------------------------------------------------

    def start_confirmation_vote(
        self,
        proposal_id: str,
        eligible_voters: list[dict[str, Any]],
        chamber_def: Chamber,
        r_min: int,
        c_max: float,
        now: Optional[datetime] = None,
    ) -> list[str]:
        """Select a fresh confirmation panel and start the confirmation vote.

        The confirmation panel must have NO overlap with the original
        ratification panel. This prevents rubber-stamping.

        Returns:
            List of confirmation panel voter IDs.

        Raises:
            ValueError: If cooling-off not complete or other validation failure.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Amendment not found: {proposal_id}")
        if proposal.status != AmendmentStatus.COOLING_OFF:
            raise ValueError(
                f"Cannot start confirmation in status {proposal.status.value}"
            )
        if not self.check_cooling_off_complete(proposal_id, now):
            raise ValueError("Cooling-off period has not elapsed")

        # Exclude original ratification panel members
        original_ratification = set(
            proposal.chamber_panels.get(ChamberKind.RATIFICATION.value, [])
        )
        candidates = [
            v for v in eligible_voters
            if v["actor_id"] not in original_ratification
        ]

        size = chamber_def.size
        if len(candidates) < size:
            raise ValueError(
                f"Not enough eligible candidates for confirmation panel: "
                f"need {size}, have {len(candidates)}"
            )

        # Check diversity
        unique_regions = {c["region"] for c in candidates}
        if len(unique_regions) < r_min:
            raise ValueError(
                f"Not enough regional diversity for confirmation: "
                f"need {r_min} regions, have {len(unique_regions)}"
            )

        # Greedy diversity-first selection
        selected: list[dict[str, Any]] = []
        remaining = list(candidates)

        selected_regions: set[str] = set()
        for region in unique_regions:
            if len(selected_regions) >= r_min:
                break
            for c in remaining:
                if c["region"] == region and c not in selected:
                    selected.append(c)
                    remaining.remove(c)
                    selected_regions.add(region)
                    break

        max_per_region = max(1, int(size * c_max))
        while len(selected) < size and remaining:
            region_counts: dict[str, int] = {}
            for s in selected:
                region_counts[s["region"]] = region_counts.get(s["region"], 0) + 1

            added = False
            for c in remaining:
                if region_counts.get(c["region"], 0) < max_per_region:
                    selected.append(c)
                    remaining.remove(c)
                    added = True
                    break

            if not added:
                raise ValueError(
                    f"Cannot fill confirmation panel to size {size} "
                    f"while respecting c_max={c_max}"
                )

        panel_ids = [s["actor_id"] for s in selected]
        proposal.confirmation_panel = panel_ids
        proposal.confirmation_votes = []
        proposal.status = AmendmentStatus.CONFIRMATION_VOTE
        return panel_ids

    def cast_confirmation_vote(
        self,
        proposal_id: str,
        voter_id: str,
        vote: bool,
        attestation: str,
        region: str,
        organization: str,
        now: Optional[datetime] = None,
    ) -> AmendmentVote:
        """Cast a vote in the confirmation round.

        Same validation as chamber voting.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Amendment not found: {proposal_id}")
        if proposal.status != AmendmentStatus.CONFIRMATION_VOTE:
            raise ValueError(
                f"Cannot cast confirmation vote in status {proposal.status.value}"
            )
        if proposal.confirmation_panel is None:
            raise ValueError("Confirmation panel not yet selected")
        if voter_id not in proposal.confirmation_panel:
            raise ValueError(
                f"Voter {voter_id} is not a member of the confirmation panel"
            )
        if any(v.voter_id == voter_id for v in proposal.confirmation_votes):
            raise ValueError(
                f"Voter {voter_id} has already voted in the confirmation round"
            )
        if not attestation.strip():
            raise ValueError("Vote attestation must not be empty")

        if now is None:
            now = datetime.now(timezone.utc)

        vote_id = f"amend_conf_{uuid.uuid4().hex[:12]}"
        amendment_vote = AmendmentVote(
            vote_id=vote_id,
            voter_id=voter_id,
            chamber="confirmation",
            vote=vote,
            attestation=attestation.strip(),
            cast_utc=now,
            region=region,
            organization=organization,
        )
        proposal.confirmation_votes.append(amendment_vote)
        return amendment_vote

    def close_confirmation_vote(
        self,
        proposal_id: str,
        now: Optional[datetime] = None,
    ) -> tuple[AmendmentProposal, bool]:
        """Close the confirmation vote and determine outcome.

        Checks 80% supermajority + 50% participation.

        Returns:
            Tuple of (proposal, confirmed: bool).
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Amendment not found: {proposal_id}")
        if proposal.status != AmendmentStatus.CONFIRMATION_VOTE:
            raise ValueError(
                f"Cannot close confirmation in status {proposal.status.value}"
            )

        if now is None:
            now = datetime.now(timezone.utc)

        votes = proposal.confirmation_votes
        yes_count = sum(1 for v in votes if v.vote)
        total_votes = len(votes)
        panel_size = len(proposal.confirmation_panel or [])

        supermajority = self._config.get("entrenched_amendment_threshold", 0.80)
        participation_min = self._config.get("entrenched_participation_minimum", 0.50)

        confirmed = True

        # Participation check
        if panel_size > 0 and total_votes < (panel_size * participation_min):
            confirmed = False

        # Supermajority check
        if total_votes > 0 and (yes_count / total_votes) < supermajority:
            confirmed = False

        if total_votes == 0:
            confirmed = False

        proposal.status = (
            AmendmentStatus.CONFIRMED if confirmed
            else AmendmentStatus.REJECTED
        )
        proposal.decided_utc = now
        return proposal, confirmed

    # ------------------------------------------------------------------
    # Amendment application (entrenched guard)
    # ------------------------------------------------------------------

    def validate_amendment_application(
        self,
        proposal: AmendmentProposal,
    ) -> None:
        """Validate that an amendment has completed the required pathway.

        Raises ConstitutionalViolation if:
        1. Status is not CONFIRMED.
        2. Entrenched amendment didn't complete full pathway.
        3. Non-entrenched amendment didn't complete standard pathway.
        """
        if proposal.status != AmendmentStatus.CONFIRMED:
            raise ConstitutionalViolation(
                f"Amendment {proposal.proposal_id} is in status "
                f"{proposal.status.value}, not CONFIRMED"
            )

        # Check that proposal chamber was voted on
        if ChamberKind.PROPOSAL.value not in proposal.chamber_votes:
            raise ConstitutionalViolation(
                f"Amendment {proposal.proposal_id} has no proposal chamber votes"
            )

        # Check that ratification chamber was voted on
        if ChamberKind.RATIFICATION.value not in proposal.chamber_votes:
            raise ConstitutionalViolation(
                f"Amendment {proposal.proposal_id} has no ratification chamber votes"
            )

        if proposal.is_entrenched:
            # Entrenched must have cooling-off times set
            if proposal.cooling_off_starts_utc is None:
                raise ConstitutionalViolation(
                    f"Entrenched amendment {proposal.proposal_id} has no "
                    f"cooling-off record"
                )
            # Entrenched must have confirmation votes
            if not proposal.confirmation_votes:
                raise ConstitutionalViolation(
                    f"Entrenched amendment {proposal.proposal_id} has no "
                    f"confirmation votes"
                )

    def apply_amendment(
        self,
        proposal_id: str,
        config_target: dict[str, Any],
        now: Optional[datetime] = None,
    ) -> AmendmentProposal:
        """Apply a confirmed amendment to the configuration.

        Calls validate_amendment_application() first. On success,
        updates the target config dict with the proposed value.

        Args:
            proposal_id: The confirmed amendment.
            config_target: The config dict to modify (constitutional_params
                           or runtime_policy).
            now: Timestamp.

        Returns:
            The updated proposal (status → APPLIED).

        Raises:
            ConstitutionalViolation: If validation fails.
            ValueError: If proposal not found.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Amendment not found: {proposal_id}")

        self.validate_amendment_application(proposal)

        if now is None:
            now = datetime.now(timezone.utc)

        # Apply the change to the target config
        # Navigate nested keys with dot notation (e.g., "entrenched_provisions.GCF_CONTRIBUTION_RATE")
        keys = proposal.provision_key.split(".")
        target = config_target
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = proposal.proposed_value

        proposal.status = AmendmentStatus.APPLIED
        return proposal
