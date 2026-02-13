"""Tests for Merkle tree and commitment builder."""

import pytest
from datetime import datetime, timezone

from genesis.crypto.merkle import MerkleTree
from genesis.crypto.commitment_builder import CommitmentBuilder


class TestMerkleTree:
    def test_empty_tree(self) -> None:
        tree = MerkleTree()
        root = tree.compute_root()
        assert root  # Non-empty hash

    def test_single_leaf(self) -> None:
        tree = MerkleTree()
        tree.add_leaf("sha256:" + "a" * 64)
        root = tree.compute_root()
        assert root.startswith("sha256:")

    def test_deterministic(self) -> None:
        """Same leaves produce same root regardless of insertion order."""
        tree1 = MerkleTree()
        tree1.add_leaf("sha256:" + "a" * 64)
        tree1.add_leaf("sha256:" + "b" * 64)
        root1 = tree1.compute_root()

        tree2 = MerkleTree()
        tree2.add_leaf("sha256:" + "b" * 64)
        tree2.add_leaf("sha256:" + "a" * 64)
        root2 = tree2.compute_root()

        assert root1 == root2  # Sorted, so order doesn't matter

    def test_different_leaves_different_roots(self) -> None:
        tree1 = MerkleTree()
        tree1.add_leaf("sha256:" + "a" * 64)
        root1 = tree1.compute_root()

        tree2 = MerkleTree()
        tree2.add_leaf("sha256:" + "b" * 64)
        root2 = tree2.compute_root()

        assert root1 != root2

    def test_inclusion_proof(self) -> None:
        tree = MerkleTree()
        leaf = "sha256:" + "a" * 64
        tree.add_leaf(leaf)
        tree.add_leaf("sha256:" + "b" * 64)
        tree.add_leaf("sha256:" + "c" * 64)
        root = tree.compute_root()

        proof = tree.inclusion_proof(leaf)
        assert proof is not None
        assert proof.leaf_hash == leaf
        assert proof.root == root

    def test_missing_leaf_no_proof(self) -> None:
        tree = MerkleTree()
        tree.add_leaf("sha256:" + "a" * 64)
        tree.compute_root()

        proof = tree.inclusion_proof("sha256:" + "z" * 64)
        assert proof is None

    def test_cannot_add_after_compute(self) -> None:
        tree = MerkleTree()
        tree.add_leaf("sha256:" + "a" * 64)
        tree.compute_root()

        with pytest.raises(RuntimeError):
            tree.add_leaf("sha256:" + "b" * 64)


class TestCommitmentBuilder:
    def test_builds_valid_record(self) -> None:
        builder = CommitmentBuilder(
            version="0.3",
            epoch_id="2026-02-13T13:00Z",
            previous_hash="sha256:" + "f" * 64,
        )
        builder.add_mission_event("sha256:" + "1" * 64)
        builder.add_trust_delta("sha256:" + "2" * 64)
        builder.add_governance_ballot("sha256:" + "3" * 64)
        builder.add_review_decision("sha256:" + "4" * 64)

        ts = datetime(2026, 2, 13, 13, 0, tzinfo=timezone.utc)
        record = builder.build(
            beacon_round=48201537,
            chamber_nonce="sha256:" + "5" * 64,
            timestamp_utc=ts,
        )

        assert record.commitment_version == "0.3"
        assert record.epoch_id == "2026-02-13T13:00Z"
        assert record.mission_event_root.startswith("sha256:")
        assert record.trust_delta_root.startswith("sha256:")
        assert record.governance_ballot_root.startswith("sha256:")
        assert record.review_decision_root.startswith("sha256:")
        assert record.public_beacon_round == 48201537
        assert record.timestamp_utc == "2026-02-13T13:00:00Z"

    def test_canonical_fields_complete(self) -> None:
        builder = CommitmentBuilder(
            version="0.3",
            epoch_id="2026-02-13T13:00Z",
            previous_hash="sha256:" + "f" * 64,
        )
        ts = datetime(2026, 2, 13, 13, 0, tzinfo=timezone.utc)
        record = builder.build(
            beacon_round=1,
            chamber_nonce="sha256:" + "0" * 64,
            timestamp_utc=ts,
        )
        fields = record.canonical_fields()
        assert len(fields) == 10  # All 10 canonical fields present

    def test_deterministic_roots(self) -> None:
        """Same events produce same commitment roots."""
        def make_record() -> object:
            builder = CommitmentBuilder(
                version="0.3",
                epoch_id="2026-02-13T13:00Z",
                previous_hash="sha256:" + "f" * 64,
            )
            builder.add_mission_event("sha256:" + "1" * 64)
            builder.add_trust_delta("sha256:" + "2" * 64)
            ts = datetime(2026, 2, 13, 13, 0, tzinfo=timezone.utc)
            return builder.build(
                beacon_round=1,
                chamber_nonce="sha256:" + "0" * 64,
                timestamp_utc=ts,
            )

        r1 = make_record()
        r2 = make_record()
        assert r1.mission_event_root == r2.mission_event_root
        assert r1.trust_delta_root == r2.trust_delta_root
