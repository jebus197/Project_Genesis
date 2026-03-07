"""Tests for persistence layer — proves event log and state store work correctly."""

import pytest
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from genesis.models.mission import (
    DomainType,
    EvidenceRecord,
    Mission,
    MissionClass,
    MissionState,
    ReviewDecision,
    ReviewDecisionVerdict,
    Reviewer,
    RiskTier,
)
from genesis.models.trust import ActorKind, TrustRecord
from genesis.persistence.event_log import EventLog, EventKind, EventRecord, GENESIS_HASH
from genesis.persistence.state_store import StateStore
from genesis.review.roster import ActorRoster, ActorStatus, RosterEntry
from genesis.crypto.epoch_service import GENESIS_PREVIOUS_HASH


# =====================================================================
# EventRecord Tests
# =====================================================================


class TestEventRecord:
    def test_create_produces_hash(self) -> None:
        event = EventRecord.create(
            event_id="E-001",
            event_kind=EventKind.MISSION_CREATED,
            actor_id="alice",
            payload={"mission_id": "M-001"},
        )
        assert event.event_hash.startswith("sha256:")
        assert len(event.event_hash) == 71  # "sha256:" + 64 hex chars

    def test_deterministic_hash(self) -> None:
        ts = datetime(2026, 2, 14, 12, 0, tzinfo=timezone.utc)
        e1 = EventRecord.create("E-1", EventKind.ACTOR_REGISTERED, "bob", {"x": 1}, ts)
        e2 = EventRecord.create("E-1", EventKind.ACTOR_REGISTERED, "bob", {"x": 1}, ts)
        assert e1.event_hash == e2.event_hash

    def test_different_payloads_different_hashes(self) -> None:
        ts = datetime(2026, 2, 14, 12, 0, tzinfo=timezone.utc)
        e1 = EventRecord.create("E-1", EventKind.TRUST_UPDATED, "bob", {"score": 0.5}, ts)
        e2 = EventRecord.create("E-1", EventKind.TRUST_UPDATED, "bob", {"score": 0.9}, ts)
        assert e1.event_hash != e2.event_hash


# =====================================================================
# EventLog Tests
# =====================================================================


class TestEventLog:
    def test_append_and_count(self) -> None:
        log = EventLog()
        event = EventRecord.create("E-1", EventKind.MISSION_CREATED, "alice", {})
        log.append(event)
        assert log.count == 1

    def test_duplicate_id_rejected(self) -> None:
        log = EventLog()
        event = EventRecord.create("E-1", EventKind.MISSION_CREATED, "alice", {})
        log.append(event)
        with pytest.raises(ValueError, match="Duplicate"):
            log.append(event)

    def test_filter_by_kind(self) -> None:
        log = EventLog()
        log.append(EventRecord.create("E-1", EventKind.MISSION_CREATED, "alice", {}))
        log.append(EventRecord.create("E-2", EventKind.TRUST_UPDATED, "bob", {}))
        log.append(EventRecord.create("E-3", EventKind.MISSION_CREATED, "charlie", {}))

        missions = log.events(kind=EventKind.MISSION_CREATED)
        assert len(missions) == 2
        trust = log.events(kind=EventKind.TRUST_UPDATED)
        assert len(trust) == 1

    def test_event_hashes(self) -> None:
        log = EventLog()
        log.append(EventRecord.create("E-1", EventKind.MISSION_CREATED, "alice", {}))
        log.append(EventRecord.create("E-2", EventKind.TRUST_UPDATED, "bob", {}))

        hashes = log.event_hashes()
        assert len(hashes) == 2
        assert all(h.startswith("sha256:") for h in hashes)

    def test_last_event(self) -> None:
        log = EventLog()
        assert log.last_event is None
        log.append(EventRecord.create("E-1", EventKind.MISSION_CREATED, "alice", {}))
        assert log.last_event.event_id == "E-1"

    def test_file_persistence(self, tmp_path: Path) -> None:
        """Events persist to file and can be loaded back."""
        log_path = tmp_path / "events.jsonl"

        # Write events
        log1 = EventLog(storage_path=log_path)
        log1.append(EventRecord.create("E-1", EventKind.MISSION_CREATED, "alice", {"a": 1}))
        log1.append(EventRecord.create("E-2", EventKind.TRUST_UPDATED, "bob", {"b": 2}))

        # Load from file
        log2 = EventLog(storage_path=log_path)
        assert log2.count == 2
        assert log2.events()[0].event_id == "E-1"
        assert log2.events()[1].event_id == "E-2"

    def test_tampered_hash_rejected_on_load(self, tmp_path: Path) -> None:
        """Tampered event_hash in JSONL file must be rejected on recovery."""
        import json
        log_path = tmp_path / "tampered.jsonl"

        # Write a valid event via the log
        log1 = EventLog(storage_path=log_path)
        log1.append(EventRecord.create("E-1", EventKind.MISSION_CREATED, "alice", {"x": 1}))

        # Tamper with the hash on disk
        lines = log_path.read_text().strip().split("\n")
        record = json.loads(lines[0])
        record["event_hash"] = "sha256:" + "0" * 64  # wrong hash
        log_path.write_text(json.dumps(record) + "\n")

        # Loading should fail
        with pytest.raises(ValueError, match="Integrity check failed"):
            EventLog(storage_path=log_path)

    def test_duplicate_id_rejected_on_load(self, tmp_path: Path) -> None:
        """Duplicate event IDs in JSONL file must be rejected on recovery."""
        import json
        log_path = tmp_path / "duped.jsonl"

        # Write two events with same content manually
        event = EventRecord.create("E-DUP", EventKind.MISSION_CREATED, "alice", {"x": 1})
        line = json.dumps({
            "event_id": event.event_id,
            "event_kind": event.event_kind.value,
            "timestamp_utc": event.timestamp_utc,
            "actor_id": event.actor_id,
            "payload": event.payload,
            "event_hash": event.event_hash,
        }, sort_keys=True, ensure_ascii=False)
        log_path.write_text(line + "\n" + line + "\n")

        with pytest.raises(ValueError, match="Duplicate event ID"):
            EventLog(storage_path=log_path)

    def test_events_since(self) -> None:
        log = EventLog()
        ts1 = datetime(2026, 2, 14, 10, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 2, 14, 12, 0, tzinfo=timezone.utc)
        ts3 = datetime(2026, 2, 14, 14, 0, tzinfo=timezone.utc)
        log.append(EventRecord.create("E-1", EventKind.MISSION_CREATED, "a", {}, ts1))
        log.append(EventRecord.create("E-2", EventKind.MISSION_CREATED, "b", {}, ts2))
        log.append(EventRecord.create("E-3", EventKind.TRUST_UPDATED, "c", {}, ts3))

        # Events since noon
        recent = log.events_since("2026-02-14T12:00:00Z")
        assert len(recent) == 2

    def test_recent_events_window(self) -> None:
        log = EventLog()
        for idx in range(1, 6):
            log.append(
                EventRecord.create(
                    f"E-{idx}",
                    EventKind.MISSION_CREATED,
                    "actor",
                    {"idx": idx},
                )
            )

        recent = log.recent_events(limit=2)
        assert [e.event_id for e in recent] == ["E-4", "E-5"]

    def test_recent_events_by_kind(self) -> None:
        log = EventLog()
        log.append(EventRecord.create("E-1", EventKind.MISSION_CREATED, "a", {}))
        log.append(EventRecord.create("E-2", EventKind.TRUST_UPDATED, "a", {}))
        log.append(EventRecord.create("E-3", EventKind.MISSION_CREATED, "a", {}))
        log.append(EventRecord.create("E-4", EventKind.TRUST_UPDATED, "a", {}))
        log.append(EventRecord.create("E-5", EventKind.MISSION_CREATED, "a", {}))

        recent_missions = log.recent_events(limit=2, kind=EventKind.MISSION_CREATED)
        assert [e.event_id for e in recent_missions] == ["E-3", "E-5"]

    # ------------------------------------------------------------------
    # Hash chain tests (P2 fix)
    # ------------------------------------------------------------------

    def test_first_event_links_to_genesis(self) -> None:
        """First event in the log has previous_hash = GENESIS_HASH."""
        log = EventLog()
        event = EventRecord.create("E-1", EventKind.MISSION_CREATED, "alice", {})
        log.append(event)
        assert log.events()[0].previous_hash == GENESIS_HASH

    def test_chain_links_propagate(self) -> None:
        """Each event's previous_hash is the preceding event's event_hash."""
        log = EventLog()
        log.append(EventRecord.create("E-1", EventKind.MISSION_CREATED, "a", {}))
        log.append(EventRecord.create("E-2", EventKind.TRUST_UPDATED, "b", {}))
        log.append(EventRecord.create("E-3", EventKind.MISSION_CREATED, "c", {}))
        events = log.events()
        assert events[0].previous_hash == GENESIS_HASH
        assert events[1].previous_hash == events[0].event_hash
        assert events[2].previous_hash == events[1].event_hash

    def test_chain_head_tracks_latest(self) -> None:
        """chain_head returns the most recent event's hash."""
        log = EventLog()
        assert log.chain_head == GENESIS_HASH
        log.append(EventRecord.create("E-1", EventKind.MISSION_CREATED, "a", {}))
        assert log.chain_head == log.events()[0].event_hash
        log.append(EventRecord.create("E-2", EventKind.TRUST_UPDATED, "b", {}))
        assert log.chain_head == log.events()[1].event_hash

    def test_chain_persists_and_loads(self, tmp_path: Path) -> None:
        """Hash chain survives persistence and reload."""
        log_path = tmp_path / "chain.jsonl"
        log1 = EventLog(storage_path=log_path)
        log1.append(EventRecord.create("E-1", EventKind.MISSION_CREATED, "a", {}))
        log1.append(EventRecord.create("E-2", EventKind.TRUST_UPDATED, "b", {}))

        # Reload
        log2 = EventLog(storage_path=log_path)
        events = log2.events()
        assert events[0].previous_hash == GENESIS_HASH
        assert events[1].previous_hash == events[0].event_hash

    def test_broken_chain_rejected_on_load(self, tmp_path: Path) -> None:
        """Deleted event in persisted log detected on reload.

        Falsification target: can an event be deleted from the middle
        of the log without detection? If yes, reject design.
        """
        import json
        log_path = tmp_path / "broken_chain.jsonl"

        # Write 3 valid chained events
        log1 = EventLog(storage_path=log_path)
        log1.append(EventRecord.create("E-1", EventKind.MISSION_CREATED, "a", {}))
        log1.append(EventRecord.create("E-2", EventKind.TRUST_UPDATED, "b", {}))
        log1.append(EventRecord.create("E-3", EventKind.MISSION_CREATED, "c", {}))

        # Delete the middle event from the file
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 3
        # Keep only first and last events (delete middle)
        log_path.write_text(lines[0] + "\n" + lines[2] + "\n")

        # Loading should detect the broken chain
        with pytest.raises(ValueError, match="Hash chain broken"):
            EventLog(storage_path=log_path)

    def test_legacy_events_without_previous_hash(self, tmp_path: Path) -> None:
        """Legacy events (no previous_hash) load without chain error.

        Backward compatibility: existing JSONL files written before
        the hash chain upgrade don't have previous_hash fields.
        """
        import json
        log_path = tmp_path / "legacy.jsonl"

        # Write a legacy event (no previous_hash field)
        event = EventRecord.create("E-1", EventKind.MISSION_CREATED, "alice", {"x": 1})
        record = {
            "event_id": event.event_id,
            "event_kind": event.event_kind.value,
            "timestamp_utc": event.timestamp_utc,
            "actor_id": event.actor_id,
            "payload": event.payload,
            "event_hash": event.event_hash,
            # No previous_hash field
        }
        log_path.write_text(json.dumps(record, sort_keys=True) + "\n")

        # Should load without error
        log2 = EventLog(storage_path=log_path)
        assert log2.count == 1
        assert log2.events()[0].event_id == "E-1"

    def test_chain_rewiring_not_detected_by_chain_alone(self, tmp_path: Path) -> None:
        """Content replacement with chain rewiring bypasses chain verification.

        Falsification target: can an attacker modify an event's content,
        recompute its hash, and update the next event's previous_hash to
        create a valid-looking chain? If yes, the chain alone does NOT
        catch content replacement — epoch anchoring is the backstop.

        This test PROVES the known limitation: the hash chain guarantees
        ordering integrity (insertion/deletion detection), NOT content
        immutability. Content immutability is guaranteed by epoch anchoring
        to the public blockchain.
        """
        import json
        import hashlib
        log_path = tmp_path / "rewired.jsonl"

        # Write 3 valid chained events
        log1 = EventLog(storage_path=log_path)
        log1.append(EventRecord.create("E-1", EventKind.MISSION_CREATED, "a", {"v": 1}))
        log1.append(EventRecord.create("E-2", EventKind.TRUST_UPDATED, "b", {"v": 2}))
        log1.append(EventRecord.create("E-3", EventKind.MISSION_CREATED, "c", {"v": 3}))

        # Record original event hashes for epoch anchor comparison
        # (Epoch anchoring builds a Merkle tree from ALL event hashes)
        original_event_hashes = [e.event_hash for e in log1.events()]

        # Read the persisted file
        lines = log_path.read_text().strip().split("\n")
        records = [json.loads(line) for line in lines]

        # --- Attack: modify middle event's content ---
        records[1]["payload"] = {"v": 999, "tampered": True}

        # Recompute its event_hash (same algorithm as EventRecord.create)
        canonical = json.dumps({
            "event_id": records[1]["event_id"],
            "event_kind": records[1]["event_kind"],
            "timestamp_utc": records[1]["timestamp_utc"],
            "actor_id": records[1]["actor_id"],
            "payload": records[1]["payload"],
        }, sort_keys=True)
        new_hash = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
        records[1]["event_hash"] = new_hash

        # Rewire: update third event's previous_hash to point to new hash
        # (This is safe because previous_hash is NOT in event_hash)
        records[2]["previous_hash"] = new_hash

        # Write the tampered log
        log_path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n")

        # --- Verification: chain loads without error ---
        # This PROVES the chain alone does not catch content replacement
        log2 = EventLog(storage_path=log_path)
        assert log2.count == 3

        # The tampered content is present
        assert log2.events()[1].payload == {"v": 999, "tampered": True}

        # BUT: the set of event hashes has changed — epoch anchoring
        # builds a Merkle tree from ALL event hashes, so the Merkle
        # root (and therefore the on-chain anchor) would differ.
        tampered_event_hashes = [e.event_hash for e in log2.events()]
        assert tampered_event_hashes != original_event_hashes, (
            "Event hash list must differ after content replacement — "
            "epoch anchoring's Merkle tree detects this discrepancy"
        )


# =====================================================================
# StateStore Tests
# =====================================================================


class TestStateStoreRoster:
    def test_save_and_load_roster(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path / "state.json")

        roster = ActorRoster()
        roster.register(RosterEntry(
            actor_id="alice", actor_kind=ActorKind.HUMAN,
            trust_score=0.75, region="EU", organization="Org1",
            model_family="human_reviewer", method_type="human_reviewer",
        ))
        roster.register(RosterEntry(
            actor_id="bot1", actor_kind=ActorKind.MACHINE,
            trust_score=0.5, region="NA", organization="Org2",
            model_family="gpt", method_type="reasoning_model",
            status=ActorStatus.QUARANTINED,
        ))

        store.save_roster(roster)

        # Load into fresh store
        store2 = StateStore(tmp_path / "state.json")
        loaded = store2.load_roster()
        assert loaded.count == 2
        assert loaded.get("alice").trust_score == 0.75
        assert loaded.get("bot1").status == ActorStatus.QUARANTINED


class TestStateStoreTrust:
    def test_save_and_load_trust(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path / "state.json")

        records = {
            "alice": TrustRecord(
                actor_id="alice", actor_kind=ActorKind.HUMAN,
                score=0.8, quality=0.9, reliability=0.85,
                volume=0.3, effort=0.6,
            ),
        }

        store.save_trust_records(records)

        store2 = StateStore(tmp_path / "state.json")
        loaded = store2.load_trust_records()
        assert "alice" in loaded
        assert loaded["alice"].score == 0.8
        assert loaded["alice"].effort == 0.6


class TestStateStoreMissions:
    def test_save_and_load_missions(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path / "state.json")

        missions = {
            "M-001": Mission(
                mission_id="M-001",
                mission_title="Test mission",
                mission_class=MissionClass.DOCUMENTATION_UPDATE,
                risk_tier=RiskTier.R0,
                domain_type=DomainType.OBJECTIVE,
                state=MissionState.IN_REVIEW,
                worker_id="worker_1",
                reviewers=[
                    Reviewer(
                        id="rev_1", model_family="claude",
                        method_type="reasoning_model",
                        region="NA", organization="Org1",
                    ),
                ],
                review_decisions=[
                    ReviewDecision(
                        reviewer_id="rev_1",
                        decision=ReviewDecisionVerdict.APPROVE,
                    ),
                ],
                evidence=[
                    EvidenceRecord(
                        artifact_hash="sha256:" + "a" * 64,
                        signature="ed25519:" + "b" * 64,
                    ),
                ],
            ),
        }

        store.save_missions(missions)

        store2 = StateStore(tmp_path / "state.json")
        loaded = store2.load_missions()
        assert "M-001" in loaded
        m = loaded["M-001"]
        assert m.state == MissionState.IN_REVIEW
        assert len(m.reviewers) == 1
        assert len(m.review_decisions) == 1
        assert len(m.evidence) == 1
        assert m.evidence[0].artifact_hash == "sha256:" + "a" * 64


class TestStateStoreEpoch:
    def test_save_and_load_epoch_state(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path / "state.json")
        store.save_epoch_state("sha256:" + "f" * 64, 42)

        store2 = StateStore(tmp_path / "state.json")
        prev_hash, count = store2.load_epoch_state()
        assert prev_hash == "sha256:" + "f" * 64
        assert count == 42

    def test_default_epoch_state(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path / "empty_state.json")
        prev_hash, count = store.load_epoch_state()
        assert prev_hash == GENESIS_PREVIOUS_HASH
        assert count == 0


class TestStateStoreEmpty:
    def test_empty_store(self, tmp_path: Path) -> None:
        store = StateStore(tmp_path / "nonexistent.json")
        assert store.load_roster().count == 0
        assert len(store.load_missions()) == 0
        assert len(store.load_trust_records()) == 0
