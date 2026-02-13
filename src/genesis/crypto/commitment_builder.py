"""Commitment builder — constructs epoch commitment payloads.

Each epoch produces a CommitmentRecord containing Merkle roots over
four domains:
1. Mission events
2. Trust deltas
3. Governance ballots
4. Review decisions

The builder is deterministic: given the same inputs, it produces
the same commitment record.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from genesis.crypto.merkle import MerkleTree
from genesis.models.commitment import CommitmentRecord


class CommitmentBuilder:
    """Builds a commitment payload from epoch data.

    Usage:
        builder = CommitmentBuilder(
            version="0.3",
            epoch_id="2026-02-13T13:00Z",
            previous_hash="sha256:abc...",
        )
        builder.add_mission_event("sha256:event1...")
        builder.add_trust_delta("sha256:delta1...")
        builder.add_governance_ballot("sha256:ballot1...")
        builder.add_review_decision("sha256:decision1...")
        record = builder.build(
            beacon_round=48201537,
            chamber_nonce="sha256:nonce...",
        )
    """

    def __init__(
        self,
        version: str,
        epoch_id: str,
        previous_hash: str,
    ) -> None:
        self._version = version
        self._epoch_id = epoch_id
        self._previous_hash = previous_hash
        self._mission_tree = MerkleTree()
        self._trust_tree = MerkleTree()
        self._governance_tree = MerkleTree()
        self._review_tree = MerkleTree()

    def add_mission_event(self, event_hash: str) -> None:
        """Add a mission event leaf hash."""
        self._mission_tree.add_leaf(event_hash)

    def add_trust_delta(self, delta_hash: str) -> None:
        """Add a trust delta leaf hash."""
        self._trust_tree.add_leaf(delta_hash)

    def add_governance_ballot(self, ballot_hash: str) -> None:
        """Add a governance ballot leaf hash."""
        self._governance_tree.add_leaf(ballot_hash)

    def add_review_decision(self, decision_hash: str) -> None:
        """Add a review decision leaf hash."""
        self._review_tree.add_leaf(decision_hash)

    def build(
        self,
        beacon_round: int,
        chamber_nonce: str,
        timestamp_utc: datetime | None = None,
    ) -> CommitmentRecord:
        """Build the commitment record.

        Computes Merkle roots for all four domains and assembles
        the canonical commitment payload.
        """
        if timestamp_utc is None:
            timestamp_utc = datetime.now(timezone.utc)

        mission_root = self._mission_tree.compute_root()
        trust_root = self._trust_tree.compute_root()
        governance_root = self._governance_tree.compute_root()
        review_root = self._review_tree.compute_root()

        # Ensure sha256: prefix
        mission_root = _ensure_prefix(mission_root)
        trust_root = _ensure_prefix(trust_root)
        governance_root = _ensure_prefix(governance_root)
        review_root = _ensure_prefix(review_root)

        return CommitmentRecord(
            commitment_version=self._version,
            epoch_id=self._epoch_id,
            previous_commitment_hash=self._previous_hash,
            mission_event_root=mission_root,
            trust_delta_root=trust_root,
            governance_ballot_root=governance_root,
            review_decision_root=review_root,
            public_beacon_round=beacon_round,
            chamber_nonce=chamber_nonce,
            timestamp_utc=timestamp_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )


def _ensure_prefix(hash_val: str) -> str:
    """Ensure sha256: prefix on a hash string."""
    if hash_val.startswith("sha256:"):
        return hash_val
    return f"sha256:{hash_val}"
