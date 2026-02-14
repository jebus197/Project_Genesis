"""Tests for epoch service — proves commitment cycle invariants hold."""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from genesis.policy.resolver import PolicyResolver
from genesis.crypto.epoch_service import (
    EpochService,
    EpochState,
    GENESIS_PREVIOUS_HASH,
)
from genesis.models.commitment import CommitmentTier


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def service(resolver: PolicyResolver) -> EpochService:
    return EpochService(resolver)


def _hash(n: int) -> str:
    """Generate a deterministic test hash."""
    return f"sha256:{n:064x}"


class TestEpochLifecycle:
    def test_open_and_close(self, service: EpochService) -> None:
        epoch_id = service.open_epoch("epoch-1")
        assert epoch_id == "epoch-1"
        assert service.current_epoch is not None
        assert not service.current_epoch.closed

        record = service.close_epoch(beacon_round=1)
        assert service.current_epoch.closed
        assert record.epoch_id == "epoch-1"
        assert record.commitment_version == "0.3"

    def test_cannot_open_twice(self, service: EpochService) -> None:
        service.open_epoch("epoch-1")
        with pytest.raises(RuntimeError, match="still open"):
            service.open_epoch("epoch-2")

    def test_can_reopen_after_close(self, service: EpochService) -> None:
        service.open_epoch("epoch-1")
        service.close_epoch(beacon_round=1)
        # Should succeed now
        epoch_id = service.open_epoch("epoch-2")
        assert epoch_id == "epoch-2"

    def test_close_without_open_fails(self, service: EpochService) -> None:
        with pytest.raises(RuntimeError, match="No open epoch"):
            service.close_epoch(beacon_round=1)

    def test_auto_generated_epoch_id(self, service: EpochService) -> None:
        epoch_id = service.open_epoch()
        assert epoch_id  # Non-empty string
        assert "T" in epoch_id  # ISO timestamp format


class TestEventCollection:
    def test_record_all_event_types(self, service: EpochService) -> None:
        service.open_epoch("epoch-1")
        service.record_mission_event(_hash(1))
        service.record_trust_delta(_hash(2))
        service.record_governance_ballot(_hash(3))
        service.record_review_decision(_hash(4))

        counts = service.epoch_event_counts()
        assert counts == {"mission": 1, "trust": 1, "governance": 1, "review": 1}

    def test_multiple_events_per_domain(self, service: EpochService) -> None:
        service.open_epoch("epoch-1")
        for i in range(5):
            service.record_mission_event(_hash(i))
        for i in range(3):
            service.record_trust_delta(_hash(100 + i))

        counts = service.epoch_event_counts()
        assert counts["mission"] == 5
        assert counts["trust"] == 3

    def test_cannot_record_without_open_epoch(self, service: EpochService) -> None:
        with pytest.raises(RuntimeError, match="No open epoch"):
            service.record_mission_event(_hash(1))

    def test_cannot_record_after_close(self, service: EpochService) -> None:
        service.open_epoch("epoch-1")
        service.close_epoch(beacon_round=1)
        with pytest.raises(RuntimeError, match="No open epoch"):
            service.record_mission_event(_hash(1))

    def test_constitutional_event_flag(self, service: EpochService) -> None:
        service.open_epoch("epoch-1")
        assert not service.current_epoch.constitutional_events_pending
        service.record_governance_ballot(_hash(1), is_constitutional=True)
        assert service.current_epoch.constitutional_events_pending

    def test_empty_epoch_counts(self, service: EpochService) -> None:
        """Event counts when no epoch is open."""
        counts = service.epoch_event_counts()
        assert all(v == 0 for v in counts.values())


class TestHashChain:
    def test_genesis_previous_hash(self, service: EpochService) -> None:
        """First epoch links to genesis sentinel."""
        assert service.previous_hash == GENESIS_PREVIOUS_HASH

    def test_chain_links(self, service: EpochService) -> None:
        """Each epoch links to the previous one."""
        service.open_epoch("epoch-1")
        record1 = service.close_epoch(beacon_round=1)
        hash_after_1 = service.previous_hash

        assert hash_after_1 != GENESIS_PREVIOUS_HASH
        assert hash_after_1.startswith("sha256:")

        service.open_epoch("epoch-2")
        service.record_mission_event(_hash(99))
        record2 = service.close_epoch(beacon_round=2)
        hash_after_2 = service.previous_hash

        # Each close produces a different hash (different epoch data)
        assert hash_after_2 != hash_after_1
        assert record2.previous_commitment_hash == hash_after_1

    def test_deterministic_commitment(self, resolver: PolicyResolver) -> None:
        """Same events produce same commitment hash."""
        ts = datetime(2026, 2, 14, 12, 0, tzinfo=timezone.utc)

        def make_record() -> str:
            svc = EpochService(resolver)
            svc.open_epoch("epoch-det")
            svc.record_mission_event(_hash(1))
            svc.record_trust_delta(_hash(2))
            svc.close_epoch(
                beacon_round=42,
                chamber_nonce="sha256:" + "a" * 64,
                timestamp_utc=ts,
            )
            return svc.previous_hash

        h1 = make_record()
        h2 = make_record()
        assert h1 == h2

    def test_committed_records_accumulate(self, service: EpochService) -> None:
        service.open_epoch("e1")
        service.close_epoch(beacon_round=1)
        service.open_epoch("e2")
        service.close_epoch(beacon_round=2)

        assert len(service.committed_records) == 2
        assert service.committed_records[0].epoch_id == "e1"
        assert service.committed_records[1].epoch_id == "e2"


class TestCommitmentTierResolution:
    def test_c0_small_population(self, service: EpochService) -> None:
        assert service.resolve_commitment_tier(100) == CommitmentTier.C0

    def test_c0_boundary(self, service: EpochService) -> None:
        assert service.resolve_commitment_tier(500) == CommitmentTier.C0

    def test_c1_growth(self, service: EpochService) -> None:
        assert service.resolve_commitment_tier(1000) == CommitmentTier.C1

    def test_c1_boundary(self, service: EpochService) -> None:
        assert service.resolve_commitment_tier(5000) == CommitmentTier.C1

    def test_c2_full_scale(self, service: EpochService) -> None:
        assert service.resolve_commitment_tier(10000) == CommitmentTier.C2

    def test_tier_progression_one_way(self, service: EpochService) -> None:
        """Higher populations never resolve to lower tiers."""
        prev_tier = CommitmentTier.C0
        tier_order = {CommitmentTier.C0: 0, CommitmentTier.C1: 1, CommitmentTier.C2: 2}
        for count in (100, 500, 501, 1000, 5000, 5001, 10000):
            tier = service.resolve_commitment_tier(count)
            assert tier_order[tier] >= tier_order[prev_tier], (
                f"Tier regressed at count={count}: {prev_tier} -> {tier}"
            )
            prev_tier = tier


class TestAnchoringDecision:
    def test_constitutional_event_always_anchors(self, service: EpochService) -> None:
        """Constitutional lifecycle events trigger immediate anchoring."""
        assert service.should_anchor(
            tier=CommitmentTier.C0,
            hours_since_last_anchor=0.0,
            has_constitutional_event=True,
        ) is True

    def test_c2_always_anchors(self, service: EpochService) -> None:
        """C2 tier anchors every epoch."""
        assert service.should_anchor(
            tier=CommitmentTier.C2,
            hours_since_last_anchor=0.0,
        ) is True

    def test_c0_respects_interval(self, service: EpochService) -> None:
        """C0 only anchors after 24 hours."""
        assert service.should_anchor(
            tier=CommitmentTier.C0,
            hours_since_last_anchor=12.0,
        ) is False
        assert service.should_anchor(
            tier=CommitmentTier.C0,
            hours_since_last_anchor=24.0,
        ) is True

    def test_c1_respects_interval(self, service: EpochService) -> None:
        """C1 anchors every 6 hours."""
        assert service.should_anchor(
            tier=CommitmentTier.C1,
            hours_since_last_anchor=3.0,
        ) is False
        assert service.should_anchor(
            tier=CommitmentTier.C1,
            hours_since_last_anchor=6.0,
        ) is True

    def test_c1_faster_than_c0(self, service: EpochService) -> None:
        """C1 anchoring interval is strictly shorter than C0."""
        # At 6 hours: C1 anchors, C0 does not
        assert service.should_anchor(CommitmentTier.C1, 6.0) is True
        assert service.should_anchor(CommitmentTier.C0, 6.0) is False


class TestCommitmentContent:
    def test_empty_epoch_produces_valid_record(self, service: EpochService) -> None:
        """An epoch with no events still produces a valid commitment."""
        service.open_epoch("empty-epoch")
        record = service.close_epoch(beacon_round=1)
        assert record.mission_event_root.startswith("sha256:")
        assert record.trust_delta_root.startswith("sha256:")
        assert record.governance_ballot_root.startswith("sha256:")
        assert record.review_decision_root.startswith("sha256:")

    def test_events_affect_roots(self, resolver: PolicyResolver) -> None:
        """Adding events changes the Merkle roots."""
        ts = datetime(2026, 2, 14, 12, 0, tzinfo=timezone.utc)

        svc1 = EpochService(resolver)
        svc1.open_epoch("e1")
        r1 = svc1.close_epoch(beacon_round=1, timestamp_utc=ts)

        svc2 = EpochService(resolver)
        svc2.open_epoch("e1")
        svc2.record_mission_event(_hash(42))
        r2 = svc2.close_epoch(beacon_round=1, timestamp_utc=ts)

        assert r1.mission_event_root != r2.mission_event_root
        # Other roots should be the same (no events in those domains)
        assert r1.trust_delta_root == r2.trust_delta_root

    def test_all_canonical_fields_present(self, service: EpochService) -> None:
        service.open_epoch("epoch-fields")
        record = service.close_epoch(beacon_round=99)
        fields = record.canonical_fields()
        assert len(fields) == 10
