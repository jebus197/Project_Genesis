"""Cryptographic commitment record model.

Every epoch produces a commitment payload with deterministic Merkle roots
over four domains: mission events, trust deltas, governance ballots,
and review decisions.

The commitment is anchored to L1 (Ethereum) on a cadence determined
by the progressive commitment tier (C0/C1/C2).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


class CommitmentTier(str, enum.Enum):
    """Progressive commitment tiers for L1 anchor frequency."""
    C0 = "C0"  # Early phase: infrequent L1 anchoring
    C1 = "C1"  # Growth phase: moderate L1 anchoring
    C2 = "C2"  # Full scale: every-epoch L1 anchoring


@dataclass(frozen=True)
class CommitmentRecord:
    """A single epoch commitment payload.

    All 10 fields are mandatory per canonical schema.
    The record is immutable once constructed.
    """
    commitment_version: str
    epoch_id: str
    previous_commitment_hash: str
    mission_event_root: str
    trust_delta_root: str
    governance_ballot_root: str
    review_decision_root: str
    public_beacon_round: int
    chamber_nonce: str
    timestamp_utc: str

    def canonical_fields(self) -> tuple[str, ...]:
        """Return all fields in canonical order for hashing."""
        return (
            self.commitment_version,
            self.epoch_id,
            self.previous_commitment_hash,
            self.mission_event_root,
            self.trust_delta_root,
            self.governance_ballot_root,
            self.review_decision_root,
            str(self.public_beacon_round),
            self.chamber_nonce,
            self.timestamp_utc,
        )
