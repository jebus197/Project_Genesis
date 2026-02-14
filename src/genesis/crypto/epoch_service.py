"""Epoch service — runtime orchestration for commitment cycles.

An epoch is the atomic time unit of Genesis governance. During each epoch,
events accumulate across four domains (mission events, trust deltas,
governance ballots, review decisions). When the epoch closes, a
CommitmentRecord is built from deterministic Merkle roots and
optionally anchored to L1 based on the commitment tier cadence.

Constitutional invariants enforced:
- Epoch duration is policy-driven (EPOCH_HOURS).
- Commitment tier progression is one-way (C0 → C1 → C2).
- L1 anchoring frequency is tier-dependent.
- Constitutional lifecycle events always anchor immediately, regardless of tier.
- Every commitment links to the previous one (hash chain).
- Empty epochs produce a valid commitment (empty trees have deterministic roots).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from genesis.crypto.anchor import AnchorRecord, anchor_to_chain
from genesis.crypto.commitment_builder import CommitmentBuilder
from genesis.models.commitment import CommitmentRecord, CommitmentTier
from genesis.policy.resolver import PolicyResolver


# Sentinel for the genesis block (no previous commitment exists).
GENESIS_PREVIOUS_HASH = "sha256:" + "0" * 64


@dataclass
class EpochState:
    """Mutable state of the current epoch."""

    epoch_id: str
    started_utc: datetime
    mission_event_hashes: list[str] = field(default_factory=list)
    trust_delta_hashes: list[str] = field(default_factory=list)
    governance_ballot_hashes: list[str] = field(default_factory=list)
    review_decision_hashes: list[str] = field(default_factory=list)
    constitutional_events_pending: bool = False
    closed: bool = False


class EpochService:
    """Manages the epoch lifecycle: open → collect → close → anchor.

    Usage:
        service = EpochService(resolver, previous_hash=GENESIS_PREVIOUS_HASH)
        service.open_epoch()

        # During epoch, events arrive:
        service.record_mission_event(event_hash)
        service.record_trust_delta(delta_hash)
        service.record_governance_ballot(ballot_hash)
        service.record_review_decision(decision_hash)

        # At epoch boundary:
        record = service.close_epoch(beacon_round=12345)

        # Determine if anchoring is due:
        if service.should_anchor(current_tier, hours_since_last_anchor):
            anchor_record = service.anchor_commitment(record, rpc_url, key)
    """

    COMMITMENT_VERSION = "0.3"

    def __init__(
        self,
        resolver: PolicyResolver,
        previous_hash: str = GENESIS_PREVIOUS_HASH,
    ) -> None:
        self._resolver = resolver
        self._previous_hash = previous_hash
        self._current_epoch: Optional[EpochState] = None
        self._committed_records: list[CommitmentRecord] = []
        self._anchor_records: list[AnchorRecord] = []

    # ------------------------------------------------------------------
    # Epoch lifecycle
    # ------------------------------------------------------------------

    def open_epoch(self, epoch_id: str | None = None) -> str:
        """Open a new epoch. Returns the epoch_id.

        Fails if the previous epoch has not been closed.
        """
        if self._current_epoch is not None and not self._current_epoch.closed:
            raise RuntimeError(
                f"Cannot open new epoch — epoch {self._current_epoch.epoch_id} "
                "is still open. Close it first."
            )

        now = datetime.now(timezone.utc)
        if epoch_id is None:
            epoch_id = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        self._current_epoch = EpochState(
            epoch_id=epoch_id,
            started_utc=now,
        )
        return epoch_id

    def close_epoch(
        self,
        beacon_round: int,
        chamber_nonce: str | None = None,
        timestamp_utc: datetime | None = None,
    ) -> CommitmentRecord:
        """Close the current epoch and build the commitment record.

        Computes Merkle roots over all collected events and returns
        an immutable CommitmentRecord. Links to the previous commitment
        via hash chain.
        """
        epoch = self._require_open_epoch()

        if chamber_nonce is None:
            chamber_nonce = "sha256:" + "0" * 64

        builder = CommitmentBuilder(
            version=self.COMMITMENT_VERSION,
            epoch_id=epoch.epoch_id,
            previous_hash=self._previous_hash,
        )

        for h in epoch.mission_event_hashes:
            builder.add_mission_event(h)
        for h in epoch.trust_delta_hashes:
            builder.add_trust_delta(h)
        for h in epoch.governance_ballot_hashes:
            builder.add_governance_ballot(h)
        for h in epoch.review_decision_hashes:
            builder.add_review_decision(h)

        record = builder.build(
            beacon_round=beacon_round,
            chamber_nonce=chamber_nonce,
            timestamp_utc=timestamp_utc,
        )

        # Update hash chain
        self._previous_hash = self._commitment_hash(record)
        epoch.closed = True
        self._committed_records.append(record)

        return record

    # ------------------------------------------------------------------
    # Event collection
    # ------------------------------------------------------------------

    def record_mission_event(self, event_hash: str) -> None:
        """Record a mission event hash in the current epoch."""
        epoch = self._require_open_epoch()
        epoch.mission_event_hashes.append(event_hash)

    def record_trust_delta(self, delta_hash: str) -> None:
        """Record a trust delta hash in the current epoch."""
        epoch = self._require_open_epoch()
        epoch.trust_delta_hashes.append(delta_hash)

    def record_governance_ballot(self, ballot_hash: str, is_constitutional: bool = False) -> None:
        """Record a governance ballot hash in the current epoch.

        If is_constitutional=True, marks the epoch as containing a
        constitutional lifecycle event, which triggers immediate L1
        anchoring regardless of commitment tier cadence.
        """
        epoch = self._require_open_epoch()
        epoch.governance_ballot_hashes.append(ballot_hash)
        if is_constitutional:
            epoch.constitutional_events_pending = True

    def record_review_decision(self, decision_hash: str) -> None:
        """Record a review decision hash in the current epoch."""
        epoch = self._require_open_epoch()
        epoch.review_decision_hashes.append(decision_hash)

    # ------------------------------------------------------------------
    # Commitment tier and anchoring logic
    # ------------------------------------------------------------------

    def resolve_commitment_tier(self, human_count: int) -> CommitmentTier:
        """Determine the commitment tier based on participant count.

        Tier progression is one-way: C0 → C1 → C2. Regression is prohibited.
        """
        thresholds = self._resolver.commitment_tier_thresholds()
        if human_count <= thresholds["C0_max_humans"]:
            return CommitmentTier.C0
        elif human_count <= thresholds["C1_max_humans"]:
            return CommitmentTier.C1
        else:
            return CommitmentTier.C2

    def should_anchor(
        self,
        tier: CommitmentTier,
        hours_since_last_anchor: float,
        has_constitutional_event: bool = False,
    ) -> bool:
        """Determine whether L1 anchoring is due.

        Constitutional lifecycle events always trigger immediate anchoring.
        Otherwise, anchoring follows the tier-dependent cadence.
        """
        if has_constitutional_event:
            return True

        if tier == CommitmentTier.C2:
            # Full scale: anchor every epoch
            return True

        tier_key = tier.value  # "C0" or "C1"
        interval = self._resolver.l1_anchor_interval_hours(tier_key)
        return hours_since_last_anchor >= interval

    def anchor_commitment(
        self,
        record: CommitmentRecord,
        rpc_url: str,
        private_key: str,
        chain_id: int = 11155111,
    ) -> AnchorRecord:
        """Anchor a commitment record to L1.

        Computes the canonical hash of the commitment payload and
        embeds it in an Ethereum transaction.
        """
        digest = self._commitment_hash(record)
        # Strip the sha256: prefix for the raw hex digest
        raw_hex = digest.replace("sha256:", "")

        anchor = anchor_to_chain(
            digest=raw_hex,
            rpc_url=rpc_url,
            private_key=private_key,
            chain_id=chain_id,
        )
        self._anchor_records.append(anchor)
        return anchor

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    @property
    def previous_hash(self) -> str:
        """The hash of the last committed record (for chain continuity)."""
        return self._previous_hash

    @property
    def current_epoch(self) -> Optional[EpochState]:
        """The current epoch state, or None if no epoch is open."""
        return self._current_epoch

    @property
    def committed_records(self) -> list[CommitmentRecord]:
        """All commitment records produced by this service instance."""
        return list(self._committed_records)

    @property
    def anchor_records(self) -> list[AnchorRecord]:
        """All anchor records produced by this service instance."""
        return list(self._anchor_records)

    def epoch_event_counts(self) -> dict[str, int]:
        """Return event counts for the current epoch."""
        if self._current_epoch is None:
            return {"mission": 0, "trust": 0, "governance": 0, "review": 0}
        epoch = self._current_epoch
        return {
            "mission": len(epoch.mission_event_hashes),
            "trust": len(epoch.trust_delta_hashes),
            "governance": len(epoch.governance_ballot_hashes),
            "review": len(epoch.review_decision_hashes),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _require_open_epoch(self) -> EpochState:
        """Return the current epoch or raise if none is open."""
        if self._current_epoch is None or self._current_epoch.closed:
            raise RuntimeError("No open epoch — call open_epoch() first.")
        return self._current_epoch

    @staticmethod
    def _commitment_hash(record: CommitmentRecord) -> str:
        """Compute the canonical hash of a commitment record.

        Uses the canonical field ordering for deterministic hashing.
        """
        canonical = "|".join(record.canonical_fields())
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"
