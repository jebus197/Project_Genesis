"""G0 Retroactive Ratification Engine — democratic review of founder-era decisions.

During Phase G0 (the founder stewardship period), the founder makes governance
decisions because there aren't yet enough people to form democratic panels.
These decisions are tagged as "provisional" — temporary until the community
can review them.

When Genesis transitions from G0 to G1, a 90-day clock starts. Every
provisional decision the founder made during G0 is put before a panel of
11 randomly selected community members. They vote yes or no on each one:
- 8 or more vote YES → the decision becomes permanent ("ratified").
- Fewer than 8 vote YES, or nobody votes before the 90-day deadline →
  the decision is reversed (undone, as if it never happened).

This is the accountability mechanism. The founder cannot cement permanent
rules during the early period. The community reviews and accepts or rejects
everything once it's large enough to have an informed opinion.

Constitutional requirement (TRUST_CONSTITUTION.md):
  "All G0 provisional decisions are automatically submitted for G1
   ratification within G0_RATIFICATION_WINDOW = 90 days of G1 activation.
   Any G0 decision not ratified is reversed."

Design test #32: Can G0 provisional decisions survive without retroactive
ratification in G1? If yes, reject design.

Design test #61: Can a G0 provisional decision persist into G1 without
ratification vote? If yes, reject.

Design test #62: Can a lapsed G0 decision remain in effect? If yes,
reject — it must be reversed.

Design test #63: Can the 90-day ratification window be bypassed?
If yes, reject.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


class G0RatificationStatus(str, enum.Enum):
    """Lifecycle of a G0 provisional decision under review.

    PENDING   — submitted for review, no panel yet.
    PANEL_VOTING — panel selected, voting in progress.
    RATIFIED  — community approved; decision is permanent.
    LAPSED    — failed to get enough votes (or deadline expired);
                must be reversed.
    REVERSED  — reversal action completed; decision undone.
    """
    PENDING = "pending"
    PANEL_VOTING = "panel_voting"
    RATIFIED = "ratified"
    LAPSED = "lapsed"
    REVERSED = "reversed"


@dataclass(frozen=True)
class G0RatificationVote:
    """A single vote on whether to ratify a G0 provisional decision.

    Frozen — votes cannot be changed once cast.
    """
    vote_id: str
    voter_id: str
    vote: bool  # True = ratify (approve), False = reject
    attestation: str  # Written confirmation from the voter
    cast_utc: datetime
    region: str
    organization: str


@dataclass
class G0RatificationItem:
    """A single G0 provisional decision submitted for community review.

    Each item represents one decision the founder made during G0. The
    community panel reviews it and votes to either ratify (keep) or
    let it lapse (which means it must be reversed).
    """
    item_id: str
    event_kind: str  # The EventKind.value of the original G0 decision
    event_id: str  # The original event's ID for traceability
    description: str  # Human-readable summary of what was decided
    payload: dict[str, Any]  # Original event payload, for reversal dispatch
    status: G0RatificationStatus = G0RatificationStatus.PENDING
    created_utc: Optional[datetime] = None
    decided_utc: Optional[datetime] = None
    panel_ids: list[str] = field(default_factory=list)
    votes: list[G0RatificationVote] = field(default_factory=list)
    genesis_provisional: bool = True  # Constitutional tag — always True


# Event kinds that represent G0 governance decisions eligible for ratification.
# These are the types of decisions the founder can make during G0 that the
# community must later review. New types can be added as the system grows.
RATIFIABLE_EVENT_KINDS: frozenset[str] = frozenset({
    "founder_veto_exercised",
    "compliance_review_completed",
    "adjudication_decided",
    "constitutional_court_decided",
})

# For each ratifiable event kind, the reversal handler that undoes the decision.
# Maps event_kind → a string key that the service layer uses to dispatch
# the appropriate reversal action.
REVERSAL_HANDLERS: dict[str, str] = {
    "founder_veto_exercised": "undo_veto",
    "compliance_review_completed": "undo_compliance_ruling",
    "adjudication_decided": "undo_adjudication",
    "constitutional_court_decided": "undo_court_ruling",
}


class G0RatificationEngine:
    """Manages the retroactive ratification of G0 provisional decisions.

    When G0 ends and G1 begins, the founder's provisional decisions are
    submitted for community review. A panel of 11 randomly selected members
    (the G1 proposal chamber size) votes on each decision. 8 out of 11
    must approve for the decision to stand. Decisions that fail or expire
    are reversed.

    The engine does not touch actor records directly — the service layer
    handles validation, event emission, and reversal dispatch.
    """

    def __init__(
        self,
        config: dict[str, Any],
        ratification_window_days: int = 90,
    ) -> None:
        self._config = config
        self._ratification_window_days = ratification_window_days
        self._items: dict[str, G0RatificationItem] = {}

    @classmethod
    def from_records(
        cls,
        config: dict[str, Any],
        ratification_window_days: int,
        items: list[dict[str, Any]],
    ) -> G0RatificationEngine:
        """Restore engine state from persisted records."""
        engine = cls(config, ratification_window_days)
        for data in items:
            votes = [
                G0RatificationVote(
                    vote_id=v["vote_id"],
                    voter_id=v["voter_id"],
                    vote=v["vote"],
                    attestation=v["attestation"],
                    cast_utc=datetime.fromisoformat(v["cast_utc"])
                    if isinstance(v["cast_utc"], str)
                    else v["cast_utc"],
                    region=v["region"],
                    organization=v["organization"],
                )
                for v in data.get("votes", [])
            ]
            item = G0RatificationItem(
                item_id=data["item_id"],
                event_kind=data["event_kind"],
                event_id=data["event_id"],
                description=data["description"],
                payload=data.get("payload", {}),
                status=G0RatificationStatus(data["status"]),
                created_utc=datetime.fromisoformat(data["created_utc"])
                if isinstance(data.get("created_utc"), str)
                else data.get("created_utc"),
                decided_utc=datetime.fromisoformat(data["decided_utc"])
                if isinstance(data.get("decided_utc"), str) and data.get("decided_utc")
                else data.get("decided_utc"),
                panel_ids=data.get("panel_ids", []),
                votes=votes,
                genesis_provisional=data.get("genesis_provisional", True),
            )
            engine._items[item.item_id] = item
        return engine

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------

    def submit_for_ratification(
        self,
        event_kind: str,
        event_id: str,
        description: str,
        payload: dict[str, Any],
        now: Optional[datetime] = None,
    ) -> G0RatificationItem:
        """Submit a G0 provisional decision for community review.

        Args:
            event_kind: The type of G0 decision (e.g., "founder_veto_exercised").
            event_id: The original event's ID for traceability.
            description: Human-readable summary of what was decided.
            payload: The original event payload (used for reversal dispatch).
            now: Timestamp.

        Returns:
            The created G0RatificationItem.

        Raises:
            ValueError: If description is empty or event already submitted.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        if not description or not description.strip():
            raise ValueError("Description cannot be empty")

        # Prevent duplicate submission of the same event
        for existing in self._items.values():
            if existing.event_id == event_id:
                raise ValueError(
                    f"Event {event_id} already submitted for ratification"
                )

        item_id = f"g0rat_{uuid.uuid4().hex[:12]}"
        item = G0RatificationItem(
            item_id=item_id,
            event_kind=event_kind,
            event_id=event_id,
            description=description,
            payload=payload,
            status=G0RatificationStatus.PENDING,
            created_utc=now,
            genesis_provisional=True,
        )
        self._items[item_id] = item
        return item

    # ------------------------------------------------------------------
    # Panel selection
    # ------------------------------------------------------------------

    def select_panel(
        self,
        item_id: str,
        eligible_voters: list[dict[str, Any]],
        chamber_size: int,
        r_min: int,
        c_max: float,
        now: Optional[datetime] = None,
    ) -> list[str]:
        """Select a geographically diverse panel to review this G0 decision.

        Uses the same greedy diversity-first algorithm as the Amendment Engine:
        first ensure minimum regional diversity, then fill remaining slots
        respecting the concentration limit.

        Args:
            item_id: The ratification item to select a panel for.
            eligible_voters: List of dicts with keys: actor_id, region, organization.
            chamber_size: Number of panel members (e.g., 11 for G1 proposal chamber).
            r_min: Minimum regions required.
            c_max: Maximum concentration from any single region (0.0-1.0).
            now: Timestamp.

        Returns:
            List of selected voter IDs.

        Raises:
            ValueError: If item not found, wrong status, or diversity unmet.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        item = self._items.get(item_id)
        if item is None:
            raise ValueError(f"Ratification item not found: {item_id}")

        if item.status != G0RatificationStatus.PENDING:
            raise ValueError(
                f"Cannot select panel in status {item.status.value} "
                f"(expected pending)"
            )

        if len(eligible_voters) < chamber_size:
            raise ValueError(
                f"Not enough eligible voters: need {chamber_size}, "
                f"have {len(eligible_voters)}"
            )

        # Check diversity is achievable
        unique_regions = {v["region"] for v in eligible_voters}
        if len(unique_regions) < r_min:
            raise ValueError(
                f"Not enough regional diversity: need {r_min} regions, "
                f"have {len(unique_regions)}"
            )

        # Greedy diversity-first selection
        selected: list[dict[str, Any]] = []
        remaining = list(eligible_voters)

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
        max_per_region = max(1, int(chamber_size * c_max))
        while len(selected) < chamber_size and remaining:
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
                    f"Cannot fill panel to size {chamber_size} "
                    f"while respecting c_max={c_max}"
                )

        panel_ids = [s["actor_id"] for s in selected]
        item.panel_ids = panel_ids
        item.status = G0RatificationStatus.PANEL_VOTING
        return panel_ids

    # ------------------------------------------------------------------
    # Voting
    # ------------------------------------------------------------------

    def cast_vote(
        self,
        item_id: str,
        voter_id: str,
        vote: bool,
        attestation: str,
        region: str,
        organization: str,
        now: Optional[datetime] = None,
    ) -> G0RatificationVote:
        """Cast a vote on whether to ratify a G0 provisional decision.

        Args:
            item_id: The ratification item to vote on.
            voter_id: Who is voting.
            vote: True = ratify (keep the decision), False = reject.
            attestation: Written confirmation from the voter.
            region: Voter's geographic region.
            organization: Voter's organization.
            now: Timestamp.

        Returns:
            The recorded vote.

        Raises:
            ValueError: If item not found, wrong status, voter not on panel,
                        duplicate vote, or empty attestation.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        item = self._items.get(item_id)
        if item is None:
            raise ValueError(f"Ratification item not found: {item_id}")

        if item.status != G0RatificationStatus.PANEL_VOTING:
            raise ValueError(
                f"Cannot vote in status {item.status.value} "
                f"(expected panel_voting)"
            )

        if voter_id not in item.panel_ids:
            raise ValueError(
                f"Voter {voter_id} is not on the panel for item {item_id}"
            )

        # Check for duplicate vote
        for existing_vote in item.votes:
            if existing_vote.voter_id == voter_id:
                raise ValueError(
                    f"Voter {voter_id} has already voted on item {item_id}"
                )

        if not attestation or not attestation.strip():
            raise ValueError("Attestation cannot be empty")

        vote_obj = G0RatificationVote(
            vote_id=f"g0v_{uuid.uuid4().hex[:12]}",
            voter_id=voter_id,
            vote=vote,
            attestation=attestation,
            cast_utc=now,
            region=region,
            organization=organization,
        )
        item.votes.append(vote_obj)
        return vote_obj

    # ------------------------------------------------------------------
    # Tallying
    # ------------------------------------------------------------------

    def close_voting(
        self,
        item_id: str,
        pass_threshold: int,
        now: Optional[datetime] = None,
    ) -> G0RatificationStatus:
        """Close voting on a ratification item and determine the outcome.

        Args:
            item_id: The ratification item to close.
            pass_threshold: Number of YES votes required to ratify (e.g., 8).
            now: Timestamp.

        Returns:
            RATIFIED if enough YES votes, LAPSED otherwise.

        Raises:
            ValueError: If item not found or wrong status.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        item = self._items.get(item_id)
        if item is None:
            raise ValueError(f"Ratification item not found: {item_id}")

        if item.status != G0RatificationStatus.PANEL_VOTING:
            raise ValueError(
                f"Cannot close voting in status {item.status.value} "
                f"(expected panel_voting)"
            )

        yes_votes = sum(1 for v in item.votes if v.vote)

        if yes_votes >= pass_threshold:
            item.status = G0RatificationStatus.RATIFIED
        else:
            item.status = G0RatificationStatus.LAPSED

        item.decided_utc = now
        return item.status

    # ------------------------------------------------------------------
    # Deadline enforcement
    # ------------------------------------------------------------------

    def check_deadline(
        self,
        now: datetime,
        deadline: datetime,
    ) -> list[str]:
        """Check which items have exceeded the ratification deadline.

        Any items still in PENDING or PANEL_VOTING status after the
        deadline has passed are automatically lapsed — they failed to
        get enough community approval in time.

        Args:
            now: Current time.
            deadline: The 90-day ratification deadline (set by
                      GenesisPhaseController on G0→G1 transition).

        Returns:
            List of item_ids that were auto-lapsed.
        """
        if now < deadline:
            return []

        lapsed_ids: list[str] = []
        for item in self._items.values():
            if item.status in (
                G0RatificationStatus.PENDING,
                G0RatificationStatus.PANEL_VOTING,
            ):
                item.status = G0RatificationStatus.LAPSED
                item.decided_utc = now
                lapsed_ids.append(item.item_id)

        return lapsed_ids

    # ------------------------------------------------------------------
    # Reversal
    # ------------------------------------------------------------------

    def mark_reversed(
        self,
        item_id: str,
        now: Optional[datetime] = None,
    ) -> G0RatificationItem:
        """Mark a lapsed item as reversed (reversal action completed).

        The actual reversal logic lives in the service layer — it dispatches
        the appropriate undo action based on the event_kind. This method
        just updates the status.

        Args:
            item_id: The lapsed item to mark as reversed.
            now: Timestamp.

        Returns:
            The updated item.

        Raises:
            ValueError: If item not found or not in LAPSED status.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        item = self._items.get(item_id)
        if item is None:
            raise ValueError(f"Ratification item not found: {item_id}")

        if item.status != G0RatificationStatus.LAPSED:
            raise ValueError(
                f"Cannot reverse item in status {item.status.value} "
                f"(expected lapsed)"
            )

        item.status = G0RatificationStatus.REVERSED
        return item

    @staticmethod
    def get_reversal_handler(event_kind: str) -> Optional[str]:
        """Get the reversal handler key for a given event kind.

        Returns None if the event kind has no registered reversal handler.
        """
        return REVERSAL_HANDLERS.get(event_kind)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_item(self, item_id: str) -> Optional[G0RatificationItem]:
        """Get a ratification item by ID."""
        return self._items.get(item_id)

    def list_items(
        self,
        status: Optional[G0RatificationStatus] = None,
    ) -> list[G0RatificationItem]:
        """List all ratification items, optionally filtered by status."""
        if status is None:
            return list(self._items.values())
        return [i for i in self._items.values() if i.status == status]

    def list_pending(self) -> list[G0RatificationItem]:
        """List items still awaiting ratification (PENDING or PANEL_VOTING)."""
        return [
            i for i in self._items.values()
            if i.status in (
                G0RatificationStatus.PENDING,
                G0RatificationStatus.PANEL_VOTING,
            )
        ]

    @property
    def items(self) -> dict[str, G0RatificationItem]:
        """Direct access to items dict (for persistence)."""
        return self._items
