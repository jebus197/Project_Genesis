"""Tests for governance ballot — proves three-chamber and vote-deduplication rules."""

import pytest

from genesis.models.governance import (
    Chamber,
    ChamberKind,
    ChamberVote,
    GovernanceBallot,
)


def _chamber(kind: ChamberKind, size: int = 5, threshold: int = 3) -> Chamber:
    return Chamber(kind=kind, size=size, pass_threshold=threshold)


def _vote(voter_id: str, chamber: ChamberKind, vote: bool = True) -> ChamberVote:
    return ChamberVote(
        voter_id=voter_id,
        chamber=chamber,
        vote=vote,
        region="NA",
        organization="Org1",
    )


def _full_chambers() -> dict[ChamberKind, Chamber]:
    return {
        ChamberKind.PROPOSAL: _chamber(ChamberKind.PROPOSAL),
        ChamberKind.RATIFICATION: _chamber(ChamberKind.RATIFICATION),
        ChamberKind.CHALLENGE: _chamber(ChamberKind.CHALLENGE),
    }


class TestThreeChamberRequirement:
    """A ballot must have all three chambers defined to pass."""

    def test_missing_chamber_fails(self) -> None:
        """A ballot with only two chambers must fail even if both pass."""
        ballot = GovernanceBallot(
            ballot_id="B-MISSING",
            description="Two-chamber ballot",
            chambers={
                ChamberKind.PROPOSAL: _chamber(ChamberKind.PROPOSAL),
                ChamberKind.RATIFICATION: _chamber(ChamberKind.RATIFICATION),
            },
            votes=[
                _vote(f"v{i}", ChamberKind.PROPOSAL)
                for i in range(3)
            ] + [
                _vote(f"v{i}", ChamberKind.RATIFICATION)
                for i in range(3)
            ],
        )
        assert ballot.evaluate() is False

    def test_all_three_chambers_can_pass(self) -> None:
        """A ballot with all three chambers passing should succeed."""
        votes = []
        for kind in ChamberKind:
            for i in range(3):
                votes.append(_vote(f"{kind.value}_v{i}", kind))
        ballot = GovernanceBallot(
            ballot_id="B-FULL",
            description="All three chambers",
            chambers=_full_chambers(),
            votes=votes,
        )
        assert ballot.evaluate() is True


class TestVoteDeduplication:
    """One voter can only count once per chamber."""

    def test_duplicate_votes_not_counted(self) -> None:
        """Same voter voting 3 times should count as 1, not 3."""
        votes = []
        # Proposal: one voter votes 3 times
        for _ in range(3):
            votes.append(_vote("same_voter", ChamberKind.PROPOSAL))
        # Ratification and challenge: enough distinct voters
        for kind in [ChamberKind.RATIFICATION, ChamberKind.CHALLENGE]:
            for i in range(3):
                votes.append(_vote(f"{kind.value}_v{i}", kind))

        ballot = GovernanceBallot(
            ballot_id="B-DUP",
            description="Duplicate voter in proposal",
            chambers=_full_chambers(),
            votes=votes,
        )
        tally = ballot.tally()
        # Proposal should show 1 yes (deduplicated), not 3
        assert tally[ChamberKind.PROPOSAL] == (1, 0)
        # Ballot should fail (1 < threshold of 3)
        assert ballot.evaluate() is False

    def test_tally_counts_unique_voters_only(self) -> None:
        """Tally must reflect unique voters, not total vote records."""
        votes = [
            _vote("v1", ChamberKind.PROPOSAL, vote=True),
            _vote("v1", ChamberKind.PROPOSAL, vote=True),  # Duplicate
            _vote("v2", ChamberKind.PROPOSAL, vote=True),
            _vote("v3", ChamberKind.PROPOSAL, vote=False),
        ]
        ballot = GovernanceBallot(
            ballot_id="B-TALLY",
            description="Tally dedup test",
            chambers=_full_chambers(),
            votes=votes,
        )
        yes, no = ballot.tally()[ChamberKind.PROPOSAL]
        assert yes == 2  # v1 (once) + v2
        assert no == 1   # v3
