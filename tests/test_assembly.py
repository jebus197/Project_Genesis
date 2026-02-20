"""Tests for the Assembly — Phase F-1: anonymous deliberation engine.

Proves constitutional invariants:
- Identity blinding: contributions carry NO actor identity (design test #64).
- No binding governance: the Assembly makes no decisions (design test #65).
- No engagement metrics: no likes, upvotes, karma, trending (design test #66).

Also covers:
- Topic creation and contribution lifecycle
- Compliance screening integration
- Machine contribution auto-labelling
- Inactivity-based topic archival
- Archived topic closure (no new contributions)
- from_records persistence round-trip
- Assembly compliance hash architecture (one-way, salted, uncorrelatable)

Design test #64: Can an Assembly contribution be traced to a specific actor
by any system participant? If yes, reject design.

Design test #65: Can the Assembly produce a binding governance decision
without routing through existing constitutional mechanisms?
If yes, reject design.

Design test #66: Does the Assembly include any engagement metric (likes,
upvotes, trending, karma)? If yes, reject design.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from genesis.governance.assembly import (
    AssemblyContribution,
    AssemblyEngine,
    AssemblyTopic,
    AssemblyTopicStatus,
)
from genesis.models.trust import ActorKind
from genesis.persistence.event_log import EventKind, EventLog
from genesis.policy.resolver import PolicyResolver
from genesis.service import GenesisService

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _now() -> datetime:
    return datetime(2026, 2, 20, 12, 0, 0, tzinfo=timezone.utc)


def _default_config() -> dict[str, Any]:
    return {"inactivity_expiry_days": 30}


def _make_service(resolver: PolicyResolver) -> GenesisService:
    """Create a GenesisService with standard actors for Assembly tests."""
    svc = GenesisService(resolver, event_log=EventLog())
    svc.open_epoch()
    svc.register_actor(
        "human-1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5,
    )
    svc.register_actor(
        "human-2", ActorKind.HUMAN, "us", "beta", initial_trust=0.6,
    )
    svc.register_actor(
        "human-3", ActorKind.HUMAN, "asia", "gamma", initial_trust=0.7,
    )
    # Register a machine actor
    svc.register_machine(
        "bot-1", operator_id="human-1", region="eu", organization="acme",
        model_family="gpt", method_type="reasoning_model",
    )
    return svc


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def service(resolver: PolicyResolver) -> GenesisService:
    return _make_service(resolver)


@pytest.fixture
def engine() -> AssemblyEngine:
    return AssemblyEngine(_default_config())


# ======================================================================
# Design Test #64: Identity Blinding
# ======================================================================

class TestDesignTest64IdentityBlinding:
    """Can an Assembly contribution be traced to a specific actor?
    If yes, reject design.
    """

    def test_contribution_has_no_actor_id_field(self):
        """AssemblyContribution dataclass must have NO actor_id field."""
        field_names = {f.name for f in dataclasses.fields(AssemblyContribution)}
        assert "actor_id" not in field_names, (
            "DESIGN TEST #64 VIOLATION: AssemblyContribution has actor_id field"
        )

    def test_contribution_has_no_author_field(self):
        """No alias for actor identity should exist on contributions."""
        field_names = {f.name for f in dataclasses.fields(AssemblyContribution)}
        forbidden = {"actor_id", "author_id", "user_id", "contributor_id",
                     "poster_id", "author", "identity", "participant_id"}
        overlap = field_names & forbidden
        assert not overlap, (
            f"DESIGN TEST #64 VIOLATION: identity fields found: {overlap}"
        )

    def test_topic_has_no_identity_fields(self):
        """AssemblyTopic should not expose contributor identities."""
        field_names = {f.name for f in dataclasses.fields(AssemblyTopic)}
        forbidden = {"author_id", "creator_id", "participant_ids", "members"}
        overlap = field_names & forbidden
        assert not overlap, (
            f"DESIGN TEST #64 VIOLATION: identity fields on topic: {overlap}"
        )

    def test_different_hashes_for_same_actor(self, service: GenesisService):
        """Two contributions by the same actor must produce different hashes."""
        r1 = service.create_assembly_topic(
            "human-1", "Topic A", "Content A", now=_now(),
        )
        assert r1.success
        r2 = service.contribute_to_assembly(
            "human-1", r1.data["topic_id"], "Content B",
            now=_now() + timedelta(minutes=1),
        )
        assert r2.success

        # Read the topic and check hashes are different
        topic = service._assembly_engine.get_topic(r1.data["topic_id"])
        assert topic is not None
        assert len(topic.contributions) == 2
        hash1 = topic.contributions[0].compliance_hash
        hash2 = topic.contributions[1].compliance_hash
        assert hash1 != hash2, (
            "DESIGN TEST #64 VIOLATION: same hash for same actor — "
            "contributions are correlatable"
        )

    def test_get_topic_returns_no_identity(self, service: GenesisService):
        """get_assembly_topic must not return actor identity in any form."""
        r = service.create_assembly_topic(
            "human-1", "Test Topic", "Test content", now=_now(),
        )
        assert r.success

        result = service.get_assembly_topic(r.data["topic_id"])
        assert result.success

        # Check the response data for any identity leakage
        data_str = str(result.data).lower()
        assert "human-1" not in data_str, (
            "DESIGN TEST #64 VIOLATION: actor_id leaked in topic response"
        )

        # Check contributions don't expose compliance_hash in read API
        for c in result.data["contributions"]:
            assert "compliance_hash" not in c, (
                "DESIGN TEST #64 VIOLATION: compliance_hash exposed in read API"
            )


# ======================================================================
# Design Test #65: No Binding Governance
# ======================================================================

class TestDesignTest65NoBindingGovernance:
    """Can the Assembly produce a binding governance decision?
    If yes, reject design.
    """

    def test_topic_has_no_voting_fields(self):
        """AssemblyTopic must have no voting, quorum, or binding fields."""
        field_names = {f.name for f in dataclasses.fields(AssemblyTopic)}
        forbidden = {"votes", "quorum", "binding", "decision", "resolution",
                     "verdict", "approved", "rejected", "outcome", "ballot"}
        overlap = field_names & forbidden
        assert not overlap, (
            f"DESIGN TEST #65 VIOLATION: governance fields on topic: {overlap}"
        )

    def test_contribution_has_no_voting_fields(self):
        """AssemblyContribution must have no voting or governance fields."""
        field_names = {f.name for f in dataclasses.fields(AssemblyContribution)}
        forbidden = {"vote", "weight", "governance_power", "binding",
                     "decision", "approval"}
        overlap = field_names & forbidden
        assert not overlap, (
            f"DESIGN TEST #65 VIOLATION: governance fields on contribution: {overlap}"
        )

    def test_engine_has_no_governance_methods(self):
        """AssemblyEngine must not expose voting or decision methods."""
        forbidden_methods = {"vote", "decide", "approve", "reject",
                             "pass_motion", "create_ballot", "cast_vote"}
        engine_methods = {m for m in dir(AssemblyEngine)
                         if not m.startswith("_")}
        overlap = engine_methods & forbidden_methods
        assert not overlap, (
            f"DESIGN TEST #65 VIOLATION: governance methods on engine: {overlap}"
        )


# ======================================================================
# Design Test #66: No Engagement Metrics
# ======================================================================

class TestDesignTest66NoEngagementMetrics:
    """Does the Assembly include any engagement metric?
    If yes, reject design.
    """

    def test_contribution_has_no_metrics(self):
        """AssemblyContribution must have no engagement metric fields."""
        field_names = {f.name for f in dataclasses.fields(AssemblyContribution)}
        forbidden = {"likes", "upvotes", "downvotes", "karma", "score",
                     "rating", "reactions", "views", "shares", "rank",
                     "trending_score", "popularity"}
        overlap = field_names & forbidden
        assert not overlap, (
            f"DESIGN TEST #66 VIOLATION: engagement metrics on contribution: {overlap}"
        )

    def test_topic_has_no_metrics(self):
        """AssemblyTopic must have no engagement metric fields."""
        field_names = {f.name for f in dataclasses.fields(AssemblyTopic)}
        forbidden = {"likes", "upvotes", "downvotes", "karma", "score",
                     "rating", "trending", "trending_score", "popularity",
                     "view_count", "hot_score", "rank"}
        overlap = field_names & forbidden
        assert not overlap, (
            f"DESIGN TEST #66 VIOLATION: engagement metrics on topic: {overlap}"
        )


# ======================================================================
# Engine-Level Tests: Topic Lifecycle
# ======================================================================

class TestAssemblyTopicLifecycle:
    """Core topic creation and contribution tests."""

    def test_create_topic_happy_path(self, engine: AssemblyEngine):
        """Creating a topic returns the topic with initial contribution."""
        topic = engine.create_topic(
            "Test Title", "Test content", "hash_1", False, _now(),
        )
        assert topic.topic_id.startswith("topic_")
        assert topic.title == "Test Title"
        assert topic.status == AssemblyTopicStatus.ACTIVE
        assert len(topic.contributions) == 1
        assert topic.contributions[0].content == "Test content"
        assert topic.contributions[0].is_machine is False
        assert topic.contributions[0].compliance_hash == "hash_1"

    def test_create_topic_empty_title_rejected(self, engine: AssemblyEngine):
        """Empty title must be rejected."""
        with pytest.raises(ValueError, match="title cannot be empty"):
            engine.create_topic("", "content", "hash", False, _now())

    def test_create_topic_empty_content_rejected(self, engine: AssemblyEngine):
        """Empty content must be rejected."""
        with pytest.raises(ValueError, match="content cannot be empty"):
            engine.create_topic("Title", "", "hash", False, _now())

    def test_contribute_happy_path(self, engine: AssemblyEngine):
        """Contributing to a topic adds to contributions list."""
        topic = engine.create_topic(
            "Title", "First", "hash_1", False, _now(),
        )
        contrib = engine.contribute(
            topic.topic_id, "Second", "hash_2", True,
            _now() + timedelta(hours=1),
        )
        assert contrib.content == "Second"
        assert contrib.is_machine is True
        assert topic.contribution_count == 2
        assert topic.last_activity_utc == _now() + timedelta(hours=1)

    def test_contribute_to_nonexistent_topic(self, engine: AssemblyEngine):
        """Contributing to nonexistent topic raises ValueError."""
        with pytest.raises(ValueError, match="Topic not found"):
            engine.contribute("fake_id", "content", "hash", False, _now())

    def test_contribute_to_archived_topic_rejected(
        self, engine: AssemblyEngine
    ):
        """Cannot contribute to an archived topic."""
        topic = engine.create_topic(
            "Title", "Content", "hash", False, _now(),
        )
        # Force archive
        topic.status = AssemblyTopicStatus.ARCHIVED

        with pytest.raises(ValueError, match="archived topic"):
            engine.contribute(
                topic.topic_id, "New", "hash2", False,
                _now() + timedelta(days=1),
            )

    def test_contribute_empty_content_rejected(self, engine: AssemblyEngine):
        """Empty contribution content must be rejected."""
        topic = engine.create_topic(
            "Title", "Content", "hash", False, _now(),
        )
        with pytest.raises(ValueError, match="content cannot be empty"):
            engine.contribute(topic.topic_id, "  ", "hash2", False, _now())


# ======================================================================
# Inactivity-Based Archival
# ======================================================================

class TestAssemblyInactivityArchival:
    """Topics auto-archive after inactivity period."""

    def test_inactive_topic_archived(self, engine: AssemblyEngine):
        """Topic past inactivity expiry is archived on sweep."""
        topic = engine.create_topic(
            "Old Topic", "Content", "hash", False, _now(),
        )
        # 31 days later — past the 30-day default
        archived = engine.archive_inactive_topics(
            _now() + timedelta(days=31)
        )
        assert topic.topic_id in archived
        assert topic.status == AssemblyTopicStatus.ARCHIVED

    def test_active_topic_not_archived(self, engine: AssemblyEngine):
        """Topic within inactivity period should NOT be archived."""
        topic = engine.create_topic(
            "Recent Topic", "Content", "hash", False, _now(),
        )
        # 29 days later — still within 30-day window
        archived = engine.archive_inactive_topics(
            _now() + timedelta(days=29)
        )
        assert topic.topic_id not in archived
        assert topic.status == AssemblyTopicStatus.ACTIVE

    def test_contribution_resets_inactivity(self, engine: AssemblyEngine):
        """A new contribution resets the inactivity timer."""
        topic = engine.create_topic(
            "Title", "Content", "hash", False, _now(),
        )
        # Contribute at day 20 — resets timer
        engine.contribute(
            topic.topic_id, "New activity", "hash2", False,
            _now() + timedelta(days=20),
        )
        # At day 40 (20 days after last activity) — still within window
        archived = engine.archive_inactive_topics(
            _now() + timedelta(days=40)
        )
        assert topic.topic_id not in archived

        # At day 51 (31 days after last activity) — now expired
        archived = engine.archive_inactive_topics(
            _now() + timedelta(days=51)
        )
        assert topic.topic_id in archived

    def test_archived_topic_remains_readable(self, engine: AssemblyEngine):
        """Archived topics are readable, not deleted."""
        topic = engine.create_topic(
            "Old Topic", "Content", "hash", False, _now(),
        )
        engine.archive_inactive_topics(_now() + timedelta(days=31))

        retrieved = engine.get_topic(topic.topic_id)
        assert retrieved is not None
        assert retrieved.status == AssemblyTopicStatus.ARCHIVED
        assert retrieved.contributions[0].content == "Content"


# ======================================================================
# List and Filter
# ======================================================================

class TestAssemblyListTopics:
    """Topic listing and filtering."""

    def test_list_all_topics(self, engine: AssemblyEngine):
        """List returns all topics ordered by last_activity_utc descending."""
        engine.create_topic("T1", "C1", "h1", False, _now())
        engine.create_topic(
            "T2", "C2", "h2", False, _now() + timedelta(hours=1),
        )
        topics = engine.list_topics()
        assert len(topics) == 2
        assert topics[0].title == "T2"  # Most recent first

    def test_list_filter_active(self, engine: AssemblyEngine):
        """Filter returns only ACTIVE topics."""
        t1 = engine.create_topic("T1", "C1", "h1", False, _now())
        engine.create_topic("T2", "C2", "h2", False, _now())
        t1.status = AssemblyTopicStatus.ARCHIVED  # Force archive

        active = engine.list_topics(status_filter=AssemblyTopicStatus.ACTIVE)
        assert len(active) == 1
        assert active[0].title == "T2"

    def test_list_filter_archived(self, engine: AssemblyEngine):
        """Filter returns only ARCHIVED topics."""
        t1 = engine.create_topic("T1", "C1", "h1", False, _now())
        engine.create_topic("T2", "C2", "h2", False, _now())
        t1.status = AssemblyTopicStatus.ARCHIVED

        archived = engine.list_topics(
            status_filter=AssemblyTopicStatus.ARCHIVED,
        )
        assert len(archived) == 1
        assert archived[0].title == "T1"


# ======================================================================
# Machine Labelling
# ======================================================================

class TestAssemblyMachineLabelling:
    """Machine contributions must be auto-labelled."""

    def test_machine_flag_set(self, engine: AssemblyEngine):
        """Machine contributions have is_machine=True."""
        topic = engine.create_topic(
            "Title", "Machine content", "hash", True, _now(),
        )
        assert topic.contributions[0].is_machine is True

    def test_human_flag_set(self, engine: AssemblyEngine):
        """Human contributions have is_machine=False."""
        topic = engine.create_topic(
            "Title", "Human content", "hash", False, _now(),
        )
        assert topic.contributions[0].is_machine is False

    def test_service_auto_labels_machine(self, service: GenesisService):
        """Service layer auto-labels machine contributions."""
        r = service.create_assembly_topic(
            "bot-1", "Bot Topic", "Bot content", now=_now(),
        )
        assert r.success

        topic = service._assembly_engine.get_topic(r.data["topic_id"])
        assert topic is not None
        assert topic.contributions[0].is_machine is True

    def test_service_auto_labels_human(self, service: GenesisService):
        """Service layer auto-labels human contributions."""
        r = service.create_assembly_topic(
            "human-1", "Human Topic", "Human content", now=_now(),
        )
        assert r.success

        topic = service._assembly_engine.get_topic(r.data["topic_id"])
        assert topic is not None
        assert topic.contributions[0].is_machine is False


# ======================================================================
# Service-Level Integration
# ======================================================================

class TestAssemblyServiceIntegration:
    """Service layer integration tests."""

    def test_create_topic_validates_actor(self, service: GenesisService):
        """Creating a topic requires a valid actor."""
        r = service.create_assembly_topic(
            "nonexistent", "Title", "Content", now=_now(),
        )
        assert not r.success
        assert "Actor not found" in r.errors[0]

    def test_contribute_validates_actor(self, service: GenesisService):
        """Contributing requires a valid actor."""
        r1 = service.create_assembly_topic(
            "human-1", "Title", "Content", now=_now(),
        )
        assert r1.success

        r2 = service.contribute_to_assembly(
            "nonexistent", r1.data["topic_id"], "More", now=_now(),
        )
        assert not r2.success
        assert "Actor not found" in r2.errors[0]

    def test_compliance_rejection(self, service: GenesisService):
        """Content matching prohibited categories is rejected."""
        r = service.create_assembly_topic(
            "human-1", "Weapon Design Plans",
            "Let's discuss weapon design techniques",
            now=_now(),
        )
        assert not r.success
        assert "compliance screening" in r.errors[0].lower()

    def test_list_topics_service(self, service: GenesisService):
        """list_assembly_topics returns topic summaries."""
        service.create_assembly_topic(
            "human-1", "Topic A", "Content A", now=_now(),
        )
        service.create_assembly_topic(
            "human-2", "Topic B", "Content B",
            now=_now() + timedelta(hours=1),
        )

        result = service.list_assembly_topics()
        assert result.success
        assert result.data["count"] == 2
        assert result.data["topics"][0]["title"] == "Topic B"

    def test_list_topics_filter(self, service: GenesisService):
        """list_assembly_topics with status filter."""
        result = service.list_assembly_topics(status_filter="active")
        assert result.success

    def test_list_topics_invalid_filter(self, service: GenesisService):
        """list_assembly_topics with invalid filter returns error."""
        result = service.list_assembly_topics(status_filter="invalid")
        assert not result.success
        assert "Invalid status filter" in result.errors[0]

    def test_get_topic_not_found(self, service: GenesisService):
        """get_assembly_topic with invalid ID returns error."""
        result = service.get_assembly_topic("fake_id")
        assert not result.success
        assert "Topic not found" in result.errors[0]

    def test_archive_inactive_topics(self, service: GenesisService):
        """archive_inactive_assembly_topics sweeps and archives."""
        r = service.create_assembly_topic(
            "human-1", "Old Topic", "Content", now=_now(),
        )
        assert r.success

        result = service.archive_inactive_assembly_topics(
            now=_now() + timedelta(days=31),
        )
        assert result.success
        assert result.data["count"] == 1

    def test_event_emitted_on_create(self, service: GenesisService):
        """ASSEMBLY_TOPIC_CREATED event is emitted on topic creation."""
        r = service.create_assembly_topic(
            "human-1", "Title", "Content", now=_now(),
        )
        assert r.success

        events = service._event_log.events(EventKind.ASSEMBLY_TOPIC_CREATED)
        assert len(events) >= 1
        assert events[-1].payload["topic_id"] == r.data["topic_id"]

    def test_event_emitted_on_contribute(self, service: GenesisService):
        """ASSEMBLY_CONTRIBUTION_ADDED event is emitted on contribution."""
        r1 = service.create_assembly_topic(
            "human-1", "Title", "Content", now=_now(),
        )
        assert r1.success

        r2 = service.contribute_to_assembly(
            "human-2", r1.data["topic_id"], "Reply",
            now=_now() + timedelta(minutes=1),
        )
        assert r2.success

        events = service._event_log.events(
            EventKind.ASSEMBLY_CONTRIBUTION_ADDED,
        )
        assert len(events) >= 1
        assert events[-1].payload["contribution_id"] == r2.data["contribution_id"]


# ======================================================================
# Persistence Round-Trip
# ======================================================================

class TestAssemblyPersistence:
    """from_records / to_records round-trip."""

    def test_round_trip(self, engine: AssemblyEngine):
        """Topics survive serialise → deserialise."""
        topic = engine.create_topic(
            "Title", "Content", "hash_1", False, _now(),
        )
        engine.contribute(
            topic.topic_id, "Reply", "hash_2", True,
            _now() + timedelta(hours=1),
        )

        records = engine.to_records()
        restored = AssemblyEngine.from_records(_default_config(), records)

        assert len(restored._topics) == 1
        rt = restored.get_topic(topic.topic_id)
        assert rt is not None
        assert rt.title == "Title"
        assert rt.status == AssemblyTopicStatus.ACTIVE
        assert len(rt.contributions) == 2
        assert rt.contributions[0].content == "Content"
        assert rt.contributions[0].is_machine is False
        assert rt.contributions[1].content == "Reply"
        assert rt.contributions[1].is_machine is True


# ======================================================================
# Compliance Hash Architecture
# ======================================================================

class TestAssemblyComplianceHash:
    """Compliance hash must be one-way and per-contribution salted."""

    def test_hash_is_one_way(self):
        """The static hash method produces a SHA-256 hex string."""
        h, salt = GenesisService._assembly_compliance_hash("actor-1")
        assert len(h) == 64  # SHA-256 hex length
        assert isinstance(salt, str)
        assert len(salt) == 32  # 16 bytes hex

    def test_same_actor_different_hashes(self):
        """Same actor produces different hashes (salted)."""
        h1, _ = GenesisService._assembly_compliance_hash("actor-1")
        h2, _ = GenesisService._assembly_compliance_hash("actor-1")
        assert h1 != h2, "Hashes must be different per call (per-contribution salt)"

    def test_different_actors_different_hashes(self):
        """Different actors produce different hashes."""
        h1, _ = GenesisService._assembly_compliance_hash("actor-1")
        h2, _ = GenesisService._assembly_compliance_hash("actor-2")
        assert h1 != h2

    def test_compliance_hash_match_works(self, engine: AssemblyEngine):
        """check_compliance_hash_match finds correct contribution."""
        topic = engine.create_topic(
            "Title", "Content", "known_hash", False, _now(),
        )
        cid = topic.contributions[0].contribution_id

        assert engine.check_compliance_hash_match(cid, "known_hash") is True
        assert engine.check_compliance_hash_match(cid, "wrong_hash") is False
        assert engine.check_compliance_hash_match("fake_id", "hash") is None
