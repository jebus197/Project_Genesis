"""Governance and chamber data models.

Constitutional governance uses three independent chambers:
- Proposal: initiates changes.
- Ratification: validates proposals.
- Challenge: blocks bad proposals.

All three must pass with strict-majority thresholds.
Machine constitutional voting weight is permanently zero (w_M_const = 0).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class GenesisPhase(str, enum.Enum):
    """Genesis bootstrap protocol phases.

    Progression is one-way. Each phase has time limits and
    population thresholds.
    """
    G0 = "G0"  # Founder stewardship (max G0_MAX_DAYS)
    G1 = "G1"  # Early governance (max G1_MAX_DAYS)
    G2 = "G2"  # Growth governance
    G3 = "G3"  # Full constitutional governance


class ChamberKind(str, enum.Enum):
    """The three constitutional chambers."""
    PROPOSAL = "proposal"
    RATIFICATION = "ratification"
    CHALLENGE = "challenge"


@dataclass(frozen=True)
class Chamber:
    """A constitutional chamber definition.

    Invariants:
    - size > 0
    - pass_threshold > size // 2 (strict majority)
    - pass_threshold <= size
    """
    kind: ChamberKind
    size: int
    pass_threshold: int

    def __post_init__(self) -> None:
        if self.size <= 0:
            raise ValueError(f"{self.kind.value} chamber size must be > 0")
        if self.pass_threshold <= self.size // 2:
            raise ValueError(
                f"{self.kind.value} pass_threshold must be strict majority (> 50%)"
            )
        if self.pass_threshold > self.size:
            raise ValueError(
                f"{self.kind.value} pass_threshold cannot exceed size"
            )


@dataclass(frozen=True)
class ChamberVote:
    """A single vote in a chamber proceeding."""
    voter_id: str
    chamber: ChamberKind
    vote: bool  # True = approve, False = reject
    region: str
    organization: str
    timestamp_utc: Optional[datetime] = None


@dataclass
class GovernanceBallot:
    """A constitutional ballot across all three chambers.

    A ballot passes only if all three chambers independently
    reach their pass_threshold.
    """
    ballot_id: str
    description: str
    chambers: dict[ChamberKind, Chamber] = field(default_factory=dict)
    votes: list[ChamberVote] = field(default_factory=list)
    created_utc: Optional[datetime] = None
    resolved_utc: Optional[datetime] = None
    passed: Optional[bool] = None

    def tally(self) -> dict[ChamberKind, tuple[int, int]]:
        """Return (yes_count, no_count) per chamber."""
        result: dict[ChamberKind, tuple[int, int]] = {}
        for kind in ChamberKind:
            chamber_votes = [v for v in self.votes if v.chamber == kind]
            yes = sum(1 for v in chamber_votes if v.vote)
            no = sum(1 for v in chamber_votes if not v.vote)
            result[kind] = (yes, no)
        return result

    def evaluate(self) -> bool:
        """Evaluate whether the ballot passes all three chambers."""
        tally = self.tally()
        for kind, chamber in self.chambers.items():
            yes_count, _ = tally.get(kind, (0, 0))
            if yes_count < chamber.pass_threshold:
                return False
        return True
