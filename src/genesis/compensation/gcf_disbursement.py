"""GCF Disbursement Engine — governance over how the commons spends money.

The Genesis Common Fund accumulates 1% of all mission rewards. This module
governs the outflow: proposals, trust-weighted voting, and execution tracking.

Architecture:
- DisbursementEngine handles governance (proposals, votes, lifecycle).
- GCFTracker handles balance (inflow/outflow accounting).
- Single-responsibility: the engine never touches the balance directly.

Constitutional constraints:
- Proposers must be ACTIVE humans with trust >= tau_prop.
- Voters must be ACTIVE humans with trust >= tau_vote (MACHINE_VOTING_EXCLUSION).
- Trust-weighted simple majority (not headcount) determines outcome.
- GCF_COMPUTE_CEILING limits compute infrastructure spending (constitutional constant).
- Quorum: configurable fraction of eligible voters must participate.

Design test #54: Can a machine vote on GCF disbursement?
If yes, reject design. (MACHINE_VOTING_EXCLUSION is entrenched.)

Design test #55: Can compute infrastructure spending exceed GCF_COMPUTE_CEILING?
If yes, reject design.

Design test #56: Can a disbursement proposal bypass compliance screening?
If yes, reject design.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional


class DisbursementCategory(str, enum.Enum):
    """Categories of GCF spending."""
    COMPUTE_INFRASTRUCTURE = "compute_infrastructure"
    PUBLIC_GOOD_MISSION = "public_good_mission"
    COMMONS_INVESTMENT = "commons_investment"


class DisbursementStatus(str, enum.Enum):
    """Lifecycle state of a disbursement proposal."""
    PROPOSED = "proposed"
    VOTING = "voting"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISBURSED = "disbursed"
    CANCELLED = "cancelled"


class DisbursementVoteChoice(str, enum.Enum):
    """A voter's choice on a disbursement proposal."""
    APPROVE = "approve"
    REJECT = "reject"


@dataclass
class DisbursementProposal:
    """A proposal to spend GCF funds.

    Mutable — transitions through PROPOSED → VOTING → APPROVED/REJECTED → DISBURSED.
    """
    proposal_id: str
    proposer_id: str
    title: str
    description: str
    requested_amount: Decimal
    recipient_description: str
    category: DisbursementCategory
    measurable_deliverables: list[str]
    compliance_verdict: str  # "clear", "flagged", "rejected"
    status: DisbursementStatus = DisbursementStatus.PROPOSED
    created_utc: Optional[datetime] = None
    voting_opens_utc: Optional[datetime] = None
    voting_closes_utc: Optional[datetime] = None
    total_trust_for: Decimal = Decimal("0")
    total_trust_against: Decimal = Decimal("0")
    eligible_voter_count: int = 0
    votes_cast: int = 0
    decided_utc: Optional[datetime] = None
    disbursed_utc: Optional[datetime] = None
    disbursement_id: Optional[str] = None
    listing_id: Optional[str] = None
    workflow_id: Optional[str] = None


@dataclass(frozen=True)
class DisbursementVote:
    """A single vote on a disbursement proposal.

    Frozen — votes are immutable once cast.
    """
    vote_id: str
    proposal_id: str
    voter_id: str
    choice: DisbursementVoteChoice
    trust_weight: Decimal
    cast_utc: datetime
    attestation: str


class DisbursementEngine:
    """Manages disbursement proposal lifecycle and voting.

    This engine handles governance (proposals, votes, decisions).
    It does NOT touch the GCF balance — that's GCFTracker's job.
    The service layer bridges the two.

    Usage:
        engine = DisbursementEngine(config)

        # Create proposal
        proposal = engine.create_proposal(...)

        # Open voting (after compliance screening passes)
        engine.open_voting(proposal_id, eligible_voter_count)

        # Cast votes
        engine.cast_vote(proposal_id, voter_id, trust_weight, HUMAN, APPROVE, "I support this")

        # Close voting (checks quorum + trust-weighted majority)
        proposal, approved = engine.close_voting(proposal_id)
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._proposals: dict[str, DisbursementProposal] = {}
        self._votes: dict[str, list[DisbursementVote]] = {}  # proposal_id → votes
        self._voter_index: dict[str, set[str]] = {}  # proposal_id → voter_ids

    @classmethod
    def from_records(
        cls,
        config: dict[str, Any],
        proposals: list[dict[str, Any]],
        votes: list[dict[str, Any]],
    ) -> DisbursementEngine:
        """Restore engine state from persisted records."""
        engine = cls(config)
        for p in proposals:
            proposal = DisbursementProposal(
                proposal_id=p["proposal_id"],
                proposer_id=p["proposer_id"],
                title=p["title"],
                description=p["description"],
                requested_amount=Decimal(p["requested_amount"]),
                recipient_description=p["recipient_description"],
                category=DisbursementCategory(p["category"]),
                measurable_deliverables=p["measurable_deliverables"],
                compliance_verdict=p["compliance_verdict"],
                status=DisbursementStatus(p["status"]),
                created_utc=datetime.fromisoformat(p["created_utc"]) if p.get("created_utc") else None,
                voting_opens_utc=datetime.fromisoformat(p["voting_opens_utc"]) if p.get("voting_opens_utc") else None,
                voting_closes_utc=datetime.fromisoformat(p["voting_closes_utc"]) if p.get("voting_closes_utc") else None,
                total_trust_for=Decimal(p.get("total_trust_for", "0")),
                total_trust_against=Decimal(p.get("total_trust_against", "0")),
                eligible_voter_count=p.get("eligible_voter_count", 0),
                votes_cast=p.get("votes_cast", 0),
                decided_utc=datetime.fromisoformat(p["decided_utc"]) if p.get("decided_utc") else None,
                disbursed_utc=datetime.fromisoformat(p["disbursed_utc"]) if p.get("disbursed_utc") else None,
                disbursement_id=p.get("disbursement_id"),
                listing_id=p.get("listing_id"),
                workflow_id=p.get("workflow_id"),
            )
            engine._proposals[proposal.proposal_id] = proposal
            engine._votes[proposal.proposal_id] = []
            engine._voter_index[proposal.proposal_id] = set()

        for v in votes:
            vote = DisbursementVote(
                vote_id=v["vote_id"],
                proposal_id=v["proposal_id"],
                voter_id=v["voter_id"],
                choice=DisbursementVoteChoice(v["choice"]),
                trust_weight=Decimal(v["trust_weight"]),
                cast_utc=datetime.fromisoformat(v["cast_utc"]),
                attestation=v["attestation"],
            )
            if vote.proposal_id in engine._votes:
                engine._votes[vote.proposal_id].append(vote)
                engine._voter_index[vote.proposal_id].add(vote.voter_id)

        return engine

    def create_proposal(
        self,
        proposer_id: str,
        title: str,
        description: str,
        requested_amount: Decimal,
        recipient_description: str,
        category: DisbursementCategory,
        measurable_deliverables: list[str],
        compliance_verdict: str,
        now: Optional[datetime] = None,
    ) -> DisbursementProposal:
        """Create a new disbursement proposal.

        Validates:
        - Title and description non-empty.
        - Requested amount positive.
        - At least one measurable deliverable.
        - Compliance verdict is "clear" (not "flagged" or "rejected").
        - Proposer does not exceed max active proposals.

        Trust and eligibility checks are done at the service layer.

        Returns:
            The created DisbursementProposal.

        Raises:
            ValueError: On validation failure.
        """
        if not title.strip():
            raise ValueError("Proposal title must not be empty")
        if not description.strip():
            raise ValueError("Proposal description must not be empty")
        if requested_amount <= Decimal("0"):
            raise ValueError(f"Requested amount must be positive, got {requested_amount}")
        if not measurable_deliverables:
            raise ValueError("At least one measurable deliverable is required")
        if compliance_verdict != "clear":
            raise ValueError(
                f"Proposal failed compliance screening: {compliance_verdict}"
            )

        # Check active proposal limit for this proposer
        max_active = self._config.get("max_proposals_per_proposer_active", 3)
        active_count = sum(
            1 for p in self._proposals.values()
            if p.proposer_id == proposer_id
            and p.status in (DisbursementStatus.PROPOSED, DisbursementStatus.VOTING)
        )
        if active_count >= max_active:
            raise ValueError(
                f"Proposer {proposer_id} already has {active_count} active proposals "
                f"(max: {max_active})"
            )

        if now is None:
            now = datetime.now(timezone.utc)

        proposal_id = f"gcf_prop_{uuid.uuid4().hex[:12]}"
        proposal = DisbursementProposal(
            proposal_id=proposal_id,
            proposer_id=proposer_id,
            title=title.strip(),
            description=description.strip(),
            requested_amount=requested_amount,
            recipient_description=recipient_description.strip(),
            category=category,
            measurable_deliverables=[d.strip() for d in measurable_deliverables],
            compliance_verdict=compliance_verdict,
            created_utc=now,
        )
        self._proposals[proposal_id] = proposal
        self._votes[proposal_id] = []
        self._voter_index[proposal_id] = set()
        return proposal

    def get_proposal(self, proposal_id: str) -> Optional[DisbursementProposal]:
        """Retrieve a proposal by ID."""
        return self._proposals.get(proposal_id)

    def list_proposals(
        self,
        status: Optional[DisbursementStatus] = None,
    ) -> list[DisbursementProposal]:
        """List proposals, optionally filtered by status."""
        if status is None:
            return list(self._proposals.values())
        return [p for p in self._proposals.values() if p.status == status]

    def get_votes(self, proposal_id: str) -> list[DisbursementVote]:
        """Return all votes cast on a proposal."""
        return list(self._votes.get(proposal_id, []))

    def open_voting(
        self,
        proposal_id: str,
        eligible_voter_count: int,
        now: Optional[datetime] = None,
    ) -> DisbursementProposal:
        """Transition a proposal from PROPOSED to VOTING.

        Sets the voting window based on config.

        Args:
            proposal_id: The proposal to open voting on.
            eligible_voter_count: Number of humans eligible to vote.
            now: Timestamp (defaults to UTC now).

        Returns:
            The updated proposal.

        Raises:
            ValueError: If proposal not found or wrong status.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal not found: {proposal_id}")
        if proposal.status != DisbursementStatus.PROPOSED:
            raise ValueError(
                f"Cannot open voting on proposal in status {proposal.status.value}"
            )
        if now is None:
            now = datetime.now(timezone.utc)

        voting_window_days = self._config.get("voting_window_days", 14)
        proposal.status = DisbursementStatus.VOTING
        proposal.voting_opens_utc = now
        proposal.voting_closes_utc = now + timedelta(days=voting_window_days)
        proposal.eligible_voter_count = eligible_voter_count
        return proposal

    def cast_vote(
        self,
        proposal_id: str,
        voter_id: str,
        voter_trust: Decimal,
        voter_kind: str,
        choice: DisbursementVoteChoice,
        attestation: str,
        now: Optional[datetime] = None,
    ) -> DisbursementVote:
        """Cast a trust-weighted vote on a disbursement proposal.

        Validates:
        - Proposal exists and is in VOTING status.
        - Voting window has not closed.
        - Voter is HUMAN (machine voting excluded).
        - Voter has not already voted on this proposal.
        - Attestation is non-empty.

        Trust threshold checks are done at the service layer.

        Returns:
            The recorded DisbursementVote.

        Raises:
            ValueError: On validation failure.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal not found: {proposal_id}")
        if proposal.status != DisbursementStatus.VOTING:
            raise ValueError(
                f"Cannot vote on proposal in status {proposal.status.value}"
            )

        if now is None:
            now = datetime.now(timezone.utc)

        if proposal.voting_closes_utc and now > proposal.voting_closes_utc:
            raise ValueError("Voting window has closed")

        # MACHINE_VOTING_EXCLUSION — entrenched provision
        if voter_kind.lower() != "human":
            raise ValueError("Only humans can vote on GCF disbursements")

        # Duplicate vote check
        if voter_id in self._voter_index.get(proposal_id, set()):
            raise ValueError(f"Voter {voter_id} has already voted on {proposal_id}")

        if not attestation.strip():
            raise ValueError("Vote attestation must not be empty")

        vote_id = f"gcf_vote_{uuid.uuid4().hex[:12]}"
        vote = DisbursementVote(
            vote_id=vote_id,
            proposal_id=proposal_id,
            voter_id=voter_id,
            choice=choice,
            trust_weight=voter_trust,
            cast_utc=now,
            attestation=attestation.strip(),
        )

        self._votes[proposal_id].append(vote)
        self._voter_index[proposal_id].add(voter_id)
        proposal.votes_cast += 1

        if choice == DisbursementVoteChoice.APPROVE:
            proposal.total_trust_for += voter_trust
        else:
            proposal.total_trust_against += voter_trust

        return vote

    def close_voting(
        self,
        proposal_id: str,
        now: Optional[datetime] = None,
    ) -> tuple[DisbursementProposal, bool]:
        """Close voting and determine outcome.

        Checks:
        - Quorum: votes_cast >= quorum_fraction * eligible_voter_count.
        - Trust-weighted simple majority: total_trust_for > total_trust_against.
        - Ties reject (conservative).

        Returns:
            Tuple of (proposal, approved: bool).

        Raises:
            ValueError: If proposal not found or wrong status.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal not found: {proposal_id}")
        if proposal.status != DisbursementStatus.VOTING:
            raise ValueError(
                f"Cannot close voting on proposal in status {proposal.status.value}"
            )

        if now is None:
            now = datetime.now(timezone.utc)

        quorum_fraction = Decimal(str(self._config.get("quorum_fraction", 0.30)))
        quorum_needed = int(
            (quorum_fraction * proposal.eligible_voter_count).to_integral_value()
        )

        # Quorum check
        if proposal.votes_cast < quorum_needed:
            proposal.status = DisbursementStatus.REJECTED
            proposal.decided_utc = now
            return proposal, False

        # Trust-weighted simple majority (ties reject)
        approved = proposal.total_trust_for > proposal.total_trust_against

        proposal.status = (
            DisbursementStatus.APPROVED if approved
            else DisbursementStatus.REJECTED
        )
        proposal.decided_utc = now
        return proposal, approved

    def mark_disbursed(
        self,
        proposal_id: str,
        disbursement_id: str,
        now: Optional[datetime] = None,
    ) -> DisbursementProposal:
        """Mark a proposal as disbursed after funds have been released.

        Called by the service layer after GCFTracker.record_disbursement().

        Args:
            proposal_id: The approved proposal.
            disbursement_id: The disbursement record ID.
            now: Timestamp.

        Returns:
            The updated proposal.

        Raises:
            ValueError: If proposal not found or not APPROVED.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal not found: {proposal_id}")
        if proposal.status != DisbursementStatus.APPROVED:
            raise ValueError(
                f"Cannot disburse proposal in status {proposal.status.value}"
            )
        if now is None:
            now = datetime.now(timezone.utc)

        proposal.status = DisbursementStatus.DISBURSED
        proposal.disbursed_utc = now
        proposal.disbursement_id = disbursement_id
        return proposal
