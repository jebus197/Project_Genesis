"""Integration tests for the full market flow — listing → bid → allocate → mission.

Tests that:
- Full end-to-end market flow works
- Listing lifecycle transitions are enforced
- Bid validation (trust, duplicates) works
- Allocation creates a mission
- Persistence round-trip preserves market state
- Search and query methods work
"""

import pytest
from pathlib import Path

from genesis.models.market import BidState, ListingState
from genesis.models.mission import DomainType, MissionClass, MissionState
from genesis.models.skill import SkillId, SkillProficiency, SkillRequirement
from genesis.models.trust import ActorKind
from genesis.policy.resolver import PolicyResolver
from genesis.service import GenesisService

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def resolver():
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def service(resolver):
    svc = GenesisService(resolver)
    svc.open_epoch()
    return svc


def _register_actors(service: GenesisService) -> None:
    """Register a creator and two workers."""
    service.register_actor(
        "creator-1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5,
    )
    service.register_actor(
        "worker-1", ActorKind.HUMAN, "us", "beta", initial_trust=0.6,
    )
    service.register_actor(
        "worker-2", ActorKind.HUMAN, "apac", "gamma", initial_trust=0.4,
    )
    # Give worker-1 Python skills
    service.update_actor_skills("worker-1", [
        SkillProficiency(
            skill_id=SkillId("software_engineering", "python"),
            proficiency_score=0.85,
            evidence_count=15,
        ),
    ])


class TestFullMarketFlow:
    def test_end_to_end_listing_to_mission(self, service) -> None:
        """Full flow: create listing → open → accept bids → bid → allocate → mission."""
        _register_actors(service)

        # Create listing
        result = service.create_listing(
            listing_id="L-001",
            title="Build REST API",
            description="Build a Python REST API service",
            creator_id="creator-1",
            skill_requirements=[
                SkillRequirement(
                    skill_id=SkillId("software_engineering", "python"),
                    minimum_proficiency=0.3,
                ),
            ],
            domain_tags=["software_engineering"],
        )
        assert result.success
        assert result.data["state"] == "draft"

        # Open listing
        result = service.open_listing("L-001")
        assert result.success
        assert result.data["state"] == "open"

        # Start accepting bids
        result = service.start_accepting_bids("L-001")
        assert result.success
        assert result.data["state"] == "accepting_bids"

        # Worker-1 submits bid
        result = service.submit_bid(
            bid_id="B-001",
            listing_id="L-001",
            worker_id="worker-1",
            notes="I have Python experience",
        )
        assert result.success
        assert result.data["relevance_score"] > 0

        # Worker-2 submits bid
        result = service.submit_bid(
            bid_id="B-002",
            listing_id="L-001",
            worker_id="worker-2",
        )
        assert result.success

        # Evaluate and allocate
        result = service.evaluate_and_allocate("L-001")
        assert result.success
        assert result.data["mission_created"]
        assert result.data["selected_worker_id"] is not None

        # Verify mission was created
        mission_id = result.data["mission_id"]
        mission = service.get_mission(mission_id)
        assert mission is not None
        assert mission.worker_id == result.data["selected_worker_id"]

    def test_skilled_worker_wins(self, service) -> None:
        """Worker with matching skills should win over unskilled worker."""
        _register_actors(service)

        result = service.create_listing(
            listing_id="L-002",
            title="Python Task",
            description="Requires Python",
            creator_id="creator-1",
            skill_requirements=[
                SkillRequirement(
                    skill_id=SkillId("software_engineering", "python"),
                    minimum_proficiency=0.3,
                ),
            ],
        )
        assert result.success

        service.open_listing("L-002")
        service.start_accepting_bids("L-002")

        service.submit_bid("B-010", "L-002", "worker-1")
        service.submit_bid("B-011", "L-002", "worker-2")

        result = service.evaluate_and_allocate("L-002")
        assert result.success
        # worker-1 has Python skills, should be selected
        assert result.data["selected_worker_id"] == "worker-1"


class TestListingValidation:
    def test_duplicate_listing_id(self, service) -> None:
        _register_actors(service)
        result = service.create_listing("L-X", "T", "D", "creator-1")
        assert result.success
        result = service.create_listing("L-X", "T2", "D2", "creator-1")
        assert not result.success
        assert "already exists" in result.errors[0]

    def test_unknown_creator(self, service) -> None:
        result = service.create_listing("L-Y", "T", "D", "nonexistent")
        assert not result.success
        assert "not found" in result.errors[0]

    def test_invalid_transition(self, service) -> None:
        _register_actors(service)
        service.create_listing("L-Z", "T", "D", "creator-1")
        # Can't go directly from DRAFT to ACCEPTING_BIDS
        result = service.start_accepting_bids("L-Z")
        assert not result.success


class TestBidValidation:
    def test_bid_on_nonexistent_listing(self, service) -> None:
        _register_actors(service)
        result = service.submit_bid("B-X", "L-NOPE", "worker-1")
        assert not result.success
        assert "not found" in result.errors[0]

    def test_bid_on_closed_listing(self, service) -> None:
        _register_actors(service)
        service.create_listing("L-C", "T", "D", "creator-1")
        # Listing is in DRAFT — not accepting bids
        result = service.submit_bid("B-X", "L-C", "worker-1")
        assert not result.success
        assert "not accepting bids" in result.errors[0]

    def test_low_trust_bid_rejected(self, service) -> None:
        """Worker below min_trust_to_bid is rejected."""
        _register_actors(service)
        # Register a very low trust worker
        service.register_actor(
            "low-trust", ActorKind.HUMAN, "eu", "omega", initial_trust=0.01,
        )
        service.create_listing("L-LT", "T", "D", "creator-1")
        service.open_listing("L-LT")
        service.start_accepting_bids("L-LT")
        result = service.submit_bid("B-LT", "L-LT", "low-trust")
        assert not result.success
        assert "trust" in result.errors[0].lower()

    def test_duplicate_bid_rejected(self, service) -> None:
        _register_actors(service)
        service.create_listing("L-D", "T", "D", "creator-1")
        service.open_listing("L-D")
        service.start_accepting_bids("L-D")

        result = service.submit_bid("B-D1", "L-D", "worker-1")
        assert result.success

        result = service.submit_bid("B-D2", "L-D", "worker-1")
        assert not result.success
        assert "already has a bid" in result.errors[0]

    def test_unknown_worker_bid_rejected(self, service) -> None:
        _register_actors(service)
        service.create_listing("L-UW", "T", "D", "creator-1")
        service.open_listing("L-UW")
        result = service.submit_bid("B-UW", "L-UW", "ghost")
        assert not result.success
        assert "not found" in result.errors[0]


class TestWithdrawAndCancel:
    def test_withdraw_bid(self, service) -> None:
        _register_actors(service)
        service.create_listing("L-W", "T", "D", "creator-1")
        service.open_listing("L-W")
        service.start_accepting_bids("L-W")
        service.submit_bid("B-W1", "L-W", "worker-1")

        result = service.withdraw_bid("B-W1", "L-W")
        assert result.success
        assert result.data["state"] == "withdrawn"

    def test_cancel_listing(self, service) -> None:
        _register_actors(service)
        service.create_listing("L-CL", "T", "D", "creator-1")
        service.open_listing("L-CL")
        service.start_accepting_bids("L-CL")
        service.submit_bid("B-CL1", "L-CL", "worker-1")

        result = service.cancel_listing("L-CL")
        assert result.success
        assert result.data["state"] == "cancelled"

        # All bids should be withdrawn
        bids = service.get_bids("L-CL")
        for bid in bids:
            assert bid.state == BidState.WITHDRAWN


class TestSearchAndQuery:
    def test_search_by_state(self, service) -> None:
        _register_actors(service)
        service.create_listing("L-S1", "T1", "D1", "creator-1")
        service.create_listing("L-S2", "T2", "D2", "creator-1")
        service.open_listing("L-S1")

        result = service.search_listings(state=ListingState.OPEN)
        assert result.success
        assert result.data["total"] == 1
        assert result.data["listings"][0]["listing_id"] == "L-S1"

    def test_search_by_domain_tags(self, service) -> None:
        _register_actors(service)
        service.create_listing(
            "L-T1", "Python", "D", "creator-1",
            domain_tags=["software_engineering"],
        )
        service.create_listing(
            "L-T2", "Data", "D", "creator-1",
            domain_tags=["data_science"],
        )

        result = service.search_listings(domain_tags=["software_engineering"])
        assert result.success
        assert result.data["total"] == 1

    def test_get_listing(self, service) -> None:
        _register_actors(service)
        service.create_listing("L-G", "T", "D", "creator-1")
        listing = service.get_listing("L-G")
        assert listing is not None
        assert listing.listing_id == "L-G"

    def test_get_bids_empty(self, service) -> None:
        _register_actors(service)
        service.create_listing("L-B", "T", "D", "creator-1")
        bids = service.get_bids("L-B")
        assert bids == []

    def test_status_includes_market(self, service) -> None:
        _register_actors(service)
        service.create_listing("L-ST", "T", "D", "creator-1")
        service.open_listing("L-ST")

        status = service.status()
        assert "market" in status
        assert status["market"]["total_listings"] == 1
        assert status["market"]["open_listings"] == 1


class TestFailClosedMarket:
    """Regression tests: market operations must fail closed when audit recording fails."""

    def test_listing_transition_fails_closed_no_epoch(self, resolver) -> None:
        """open_listing without epoch must fail and leave listing in DRAFT."""
        svc = GenesisService(resolver)
        svc.open_epoch()

        svc.register_actor("c1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5)
        svc.create_listing("L-FC1", "Test", "Desc", "c1")

        # Close epoch — no epoch open for subsequent operations
        svc.close_epoch(beacon_round=99)

        result = svc.open_listing("L-FC1")
        assert not result.success
        assert any("epoch" in e.lower() for e in result.errors)

        # Listing state must still be DRAFT (rollback verified)
        listing = svc.get_listing("L-FC1")
        assert listing.state == ListingState.DRAFT
        assert listing.opened_utc is None

    def test_start_accepting_bids_fails_closed_no_epoch(self, resolver) -> None:
        """start_accepting_bids without epoch must fail and rollback."""
        svc = GenesisService(resolver)
        svc.open_epoch()

        svc.register_actor("c1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5)
        svc.create_listing("L-FC2", "Test", "Desc", "c1")
        svc.open_listing("L-FC2")

        svc.close_epoch(beacon_round=99)

        result = svc.start_accepting_bids("L-FC2")
        assert not result.success

        listing = svc.get_listing("L-FC2")
        assert listing.state == ListingState.OPEN

    def test_allocation_fails_closed_no_epoch(self, resolver) -> None:
        """evaluate_and_allocate without epoch must fail, rollback bids and listing."""
        svc = GenesisService(resolver)
        svc.open_epoch()

        svc.register_actor("c1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5)
        svc.register_actor("w1", ActorKind.HUMAN, "us", "beta", initial_trust=0.6)
        svc.create_listing("L-FC3", "Test", "Desc", "c1")
        svc.open_listing("L-FC3")
        svc.start_accepting_bids("L-FC3")
        svc.submit_bid("B-FC3", "L-FC3", "w1")

        # Close epoch before allocation
        svc.close_epoch(beacon_round=99)

        result = svc.evaluate_and_allocate("L-FC3")
        assert not result.success

        # Listing must NOT be ALLOCATED or CLOSED
        listing = svc.get_listing("L-FC3")
        assert listing.state == ListingState.ACCEPTING_BIDS
        assert listing.allocated_worker_id is None

        # Bid must still be SUBMITTED (not ACCEPTED/REJECTED)
        bids = svc.get_bids("L-FC3")
        assert all(b.state == BidState.SUBMITTED for b in bids)

        # No mission should exist
        assert svc._missions.get("mission-from-L-FC3") is None

    def test_allocation_no_phantom_event_log_on_failure(self, resolver) -> None:
        """On allocation failure, EventLog.count must not increase."""
        from genesis.persistence.event_log import EventLog

        log = EventLog()
        svc = GenesisService(resolver, event_log=log)
        svc.open_epoch()

        svc.register_actor("c1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5)
        svc.register_actor("w1", ActorKind.HUMAN, "us", "beta", initial_trust=0.6)
        svc.create_listing("L-FC4", "Test", "Desc", "c1")
        svc.open_listing("L-FC4")
        svc.start_accepting_bids("L-FC4")
        svc.submit_bid("B-FC4", "L-FC4", "w1")

        count_before = log.count
        svc.close_epoch(beacon_round=99)

        result = svc.evaluate_and_allocate("L-FC4")
        assert not result.success

        # No new events should have been recorded
        assert log.count == count_before

    def test_allocation_no_phantom_event_on_mission_failure(self, resolver) -> None:
        """If mission creation fails during allocation, no WORKER_ALLOCATED event is emitted."""
        from genesis.persistence.event_log import EventLog, EventKind

        log = EventLog()
        svc = GenesisService(resolver, event_log=log)
        svc.open_epoch()

        svc.register_actor("c1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5)
        svc.register_actor("w1", ActorKind.HUMAN, "us", "beta", initial_trust=0.6)
        svc.create_listing("L-dup", "Test", "Desc", "c1")
        svc.open_listing("L-dup")
        svc.start_accepting_bids("L-dup")
        svc.submit_bid("B-dup", "L-dup", "w1")

        # Pre-reserve the mission ID so allocation's create_mission fails
        svc.create_mission(
            mission_id="mission-from-L-dup",
            title="Block",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
            worker_id="w1",
        )

        count_before = log.count
        result = svc.evaluate_and_allocate("L-dup")
        assert not result.success

        # Listing must remain in ACCEPTING_BIDS (not ALLOCATED or CLOSED)
        listing = svc.get_listing("L-dup")
        assert listing.state == ListingState.ACCEPTING_BIDS
        assert listing.allocated_worker_id is None

        # Bid must still be SUBMITTED
        bids = svc.get_bids("L-dup")
        assert all(b.state == BidState.SUBMITTED for b in bids)

        # No WORKER_ALLOCATED event should exist after count_before
        allocation_events = [
            e for e in log._events[count_before:]
            if e.event_kind == EventKind.WORKER_ALLOCATED
        ]
        assert len(allocation_events) == 0, (
            f"Phantom WORKER_ALLOCATED event found: {allocation_events}"
        )


class TestAllocationStagingIntegrity:
    """CX sanity checks: internal mission staging must leave no phantom
    mission events, no phantom state, and no phantom durable records."""

    def test_forced_allocation_append_failure_no_phantom_mission(self, resolver) -> None:
        """Forced WORKER_ALLOCATED append failure: no mission in memory,
        no mission-created event in log."""
        from genesis.persistence.event_log import EventLog, EventKind, EventRecord

        class FailOnAllocationLog(EventLog):
            """EventLog that raises on WORKER_ALLOCATED events only."""
            def append(self, event: EventRecord) -> None:
                if event.event_kind == EventKind.WORKER_ALLOCATED:
                    raise OSError("Simulated allocation event write failure")
                super().append(event)

        log = FailOnAllocationLog()
        svc = GenesisService(resolver, event_log=log)
        svc.open_epoch()

        svc.register_actor("c1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5)
        svc.register_actor("w1", ActorKind.HUMAN, "us", "beta", initial_trust=0.6)
        svc.create_listing("L-stg1", "Test", "Desc", "c1")
        svc.open_listing("L-stg1")
        svc.start_accepting_bids("L-stg1")
        svc.submit_bid("B-stg1", "L-stg1", "w1")

        count_before = log.count
        result = svc.evaluate_and_allocate("L-stg1")
        assert not result.success

        # No mission in memory
        assert svc._missions.get("mission-from-L-stg1") is None

        # No new mission-created event
        mission_events = [
            e for e in log._events[count_before:]
            if e.event_kind == EventKind.MISSION_TRANSITION
            and e.payload.get("mission_id") == "mission-from-L-stg1"
        ]
        assert len(mission_events) == 0, (
            f"Phantom MISSION_TRANSITION event found: {mission_events}"
        )

        # Listing and bids fully rolled back
        listing = svc.get_listing("L-stg1")
        assert listing.state == ListingState.ACCEPTING_BIDS
        bids = svc.get_bids("L-stg1")
        assert all(b.state == BidState.SUBMITTED for b in bids)

    def test_forced_allocation_failure_no_phantom_on_restart(self, resolver, tmp_path) -> None:
        """With StateStore, forced WORKER_ALLOCATED failure must leave
        no mission-from-* in persisted state after restart."""
        from genesis.persistence.event_log import EventLog, EventKind, EventRecord
        from genesis.persistence.state_store import StateStore

        class FailOnAllocationLog(EventLog):
            def append(self, event: EventRecord) -> None:
                if event.event_kind == EventKind.WORKER_ALLOCATED:
                    raise OSError("Simulated allocation event write failure")
                super().append(event)

        store = StateStore(tmp_path / "state.json")
        log = FailOnAllocationLog()
        svc = GenesisService(resolver, state_store=store, event_log=log)
        svc.open_epoch()

        svc.register_actor("c1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5)
        svc.register_actor("w1", ActorKind.HUMAN, "us", "beta", initial_trust=0.6)
        svc.create_listing("L-stg2", "Test", "Desc", "c1")
        svc.open_listing("L-stg2")
        svc.start_accepting_bids("L-stg2")
        svc.submit_bid("B-stg2", "L-stg2", "w1")

        result = svc.evaluate_and_allocate("L-stg2")
        assert not result.success

        # Restart from persisted state
        store2 = StateStore(tmp_path / "state.json")
        svc2 = GenesisService(resolver, state_store=store2)

        # No phantom mission in reloaded state
        assert svc2._missions.get("mission-from-L-stg2") is None

    def test_mission_id_collision_zero_log_growth(self, resolver) -> None:
        """Mission-ID collision: zero WORKER_ALLOCATED events, zero extra log growth."""
        from genesis.persistence.event_log import EventLog, EventKind

        log = EventLog()
        svc = GenesisService(resolver, event_log=log)
        svc.open_epoch()

        svc.register_actor("c1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5)
        svc.register_actor("w1", ActorKind.HUMAN, "us", "beta", initial_trust=0.6)
        svc.create_listing("L-col", "Test", "Desc", "c1")
        svc.open_listing("L-col")
        svc.start_accepting_bids("L-col")
        svc.submit_bid("B-col", "L-col", "w1")

        # Pre-reserve mission ID to cause collision
        svc.create_mission(
            mission_id="mission-from-L-col",
            title="Block",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
            worker_id="w1",
        )

        count_before = log.count
        result = svc.evaluate_and_allocate("L-col")
        assert not result.success

        # Zero extra log growth
        assert log.count == count_before, (
            f"Log grew by {log.count - count_before} events on failed allocation"
        )

        # Zero WORKER_ALLOCATED events in entire log
        alloc_events = [
            e for e in log._events
            if e.event_kind == EventKind.WORKER_ALLOCATED
        ]
        assert len(alloc_events) == 0


class TestPostAuditPersistDegraded:
    """CX sanity checks: after audit event commits, persist failure must NOT
    rollback in-memory state. Instead, state stays consistent with audit trail
    and persistence_degraded flag is set."""

    def test_allocation_persist_failure_keeps_state(self, resolver) -> None:
        """evaluate_and_allocate: persist failure after audit commit keeps
        in-memory state consistent with audit trail."""
        from genesis.persistence.event_log import EventLog, EventKind

        log = EventLog()
        svc = GenesisService(resolver, event_log=log)
        svc.open_epoch()

        svc.register_actor("c1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5)
        svc.register_actor("w1", ActorKind.HUMAN, "us", "beta", initial_trust=0.6)
        svc.create_listing("L-pf1", "Test", "Desc", "c1")
        svc.open_listing("L-pf1")
        svc.start_accepting_bids("L-pf1")
        svc.submit_bid("B-pf1", "L-pf1", "w1")

        count_before = log.count
        # Inject persist failure
        original_persist = svc._persist_state
        def failing_persist():
            raise OSError("Simulated disk full")
        svc._persist_state = failing_persist

        result = svc.evaluate_and_allocate("L-pf1")
        # Operation succeeds (audit committed) but with warning
        assert result.success
        assert "warning" in result.data

        # In-memory state consistent with audit: listing allocated, mission exists
        listing = svc.get_listing("L-pf1")
        assert listing.allocated_worker_id is not None
        assert svc._missions.get("mission-from-L-pf1") is not None

        # Event log grew (audit committed)
        alloc_events = [
            e for e in log._events[count_before:]
            if e.event_kind == EventKind.WORKER_ALLOCATED
        ]
        assert len(alloc_events) == 1

        # Degraded flag set
        assert svc._persistence_degraded is True

    def test_create_mission_persist_failure_keeps_state(self, resolver) -> None:
        """create_mission: persist failure after audit commit keeps mission
        in memory (consistent with audit trail)."""
        svc = GenesisService(resolver)
        svc.open_epoch()
        svc.register_actor("w1", ActorKind.HUMAN, "us", "beta", initial_trust=0.5)

        # Inject persist failure
        original_persist = svc._persist_state
        def failing_persist():
            raise OSError("Simulated save failure")
        svc._persist_state = failing_persist

        result = svc.create_mission(
            mission_id="m-pfail",
            title="Test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
            worker_id="w1",
        )
        assert result.success
        assert "warning" in result.data

        # Mission must remain in memory (consistent with audit)
        assert svc._missions.get("m-pfail") is not None
        assert svc._persistence_degraded is True

    def test_update_trust_persist_failure_keeps_state(self, resolver) -> None:
        """update_trust: persist failure after audit commit keeps trust
        score in memory (consistent with audit trail)."""
        svc = GenesisService(resolver)
        svc.open_epoch()
        svc.register_actor("a1", "HUMAN", "us", "acme", initial_trust=0.5)

        old_record = svc.get_trust("a1")
        old_score = old_record.score

        # Inject persist failure
        original_persist = svc._persist_state
        def failing_persist():
            raise OSError("Simulated save failure")
        svc._persist_state = failing_persist

        result = svc.update_trust("a1", 0.9, 0.8, 0.7, "test", effort=0.5)
        assert result.success
        assert "warning" in result.data

        # Trust score must reflect the update (not rolled back)
        new_record = svc.get_trust("a1")
        assert new_record.score != old_score
        assert svc._persistence_degraded is True

    def test_transition_listing_persist_failure_keeps_state(self, resolver) -> None:
        """_transition_listing: persist failure after audit commit keeps
        listing in new state (consistent with audit trail)."""
        svc = GenesisService(resolver)
        svc.open_epoch()
        svc.register_actor("c1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5)
        svc.create_listing("L-pf4", "Test", "Desc", "c1")

        # Inject persist failure
        original_persist = svc._persist_state
        def failing_persist():
            raise OSError("Simulated save failure")
        svc._persist_state = failing_persist

        result = svc.open_listing("L-pf4")
        assert result.success
        assert "warning" in result.data

        # Listing must be OPEN (consistent with audit, not rolled back)
        listing = svc.get_listing("L-pf4")
        assert listing.state == ListingState.OPEN
        assert listing.opened_utc is not None
        assert svc._persistence_degraded is True

    def test_status_reports_degraded_flag(self, resolver) -> None:
        """status() must report persistence_degraded when set."""
        svc = GenesisService(resolver)
        assert svc.status()["persistence_degraded"] is False

        svc._persistence_degraded = True
        assert svc.status()["persistence_degraded"] is True


class TestExtendedPostAuditPersistDegraded:
    """CX round 6: additional mutators that call raw _persist_state() post-audit
    must also use _safe_persist_post_audit() — no uncaught OSError, degraded flag set."""

    def test_create_listing_persist_failure_returns_success_with_warning(self, resolver) -> None:
        """create_listing: persist failure after listing audit event keeps listing
        in memory and returns success with warning."""
        from genesis.persistence.event_log import EventLog, EventKind

        log = EventLog()
        svc = GenesisService(resolver, event_log=log)
        svc.open_epoch()
        svc.register_actor("c1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5)

        count_before = log.count
        # Inject persist failure
        svc._persist_state = lambda: (_ for _ in ()).throw(OSError("Simulated"))

        result = svc.create_listing("L-ext1", "Test", "Desc", "c1")
        assert result.success
        assert "warning" in result.data

        # Listing remains in memory (consistent with audit)
        assert svc.get_listing("L-ext1") is not None
        # Audit event committed
        listing_events = [
            e for e in log._events[count_before:]
            if e.event_kind == EventKind.LISTING_CREATED
        ]
        assert len(listing_events) == 1
        assert svc._persistence_degraded is True

    def test_submit_bid_persist_failure_returns_success_with_warning(self, resolver) -> None:
        """submit_bid: persist failure after bid audit event keeps bid in memory
        and returns success with warning."""
        from genesis.persistence.event_log import EventLog, EventKind

        log = EventLog()
        svc = GenesisService(resolver, event_log=log)
        svc.open_epoch()
        svc.register_actor("c1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5)
        svc.register_actor("w1", ActorKind.HUMAN, "us", "beta", initial_trust=0.6)
        svc.create_listing("L-ext2", "Test", "Desc", "c1")
        svc.open_listing("L-ext2")
        svc.start_accepting_bids("L-ext2")

        count_before = log.count
        # Inject persist failure
        svc._persist_state = lambda: (_ for _ in ()).throw(OSError("Simulated"))

        result = svc.submit_bid("B-ext2", "L-ext2", "w1")
        assert result.success
        assert "warning" in result.data

        # Bid remains in memory
        bids = svc._bids.get("L-ext2", [])
        assert any(b.bid_id == "B-ext2" for b in bids)
        # Audit event committed
        bid_events = [
            e for e in log._events[count_before:]
            if e.event_kind == EventKind.BID_SUBMITTED
        ]
        assert len(bid_events) == 1
        assert svc._persistence_degraded is True

    def test_mission_transition_persist_failure_returns_success_with_warning(self, resolver) -> None:
        """_transition_mission (via submit_mission): persist failure after mission
        audit event keeps mission in new state and returns success with warning."""
        svc = GenesisService(resolver)
        svc.open_epoch()
        svc.register_actor("w1", ActorKind.HUMAN, "us", "beta", initial_trust=0.5)

        svc.create_mission(
            mission_id="m-ext3",
            title="Test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
            worker_id="w1",
        )

        # Inject persist failure
        svc._persist_state = lambda: (_ for _ in ()).throw(OSError("Simulated"))

        result = svc.submit_mission("m-ext3")
        assert result.success
        assert "warning" in result.data

        # Mission must be in SUBMITTED state (not rolled back)
        mission = svc._missions.get("m-ext3")
        assert mission.state == MissionState.SUBMITTED
        assert svc._persistence_degraded is True

    def test_open_epoch_persist_failure_returns_success_with_warning(self, resolver) -> None:
        """open_epoch: persist failure keeps epoch open in memory and returns
        success with warning (no uncaught OSError)."""
        svc = GenesisService(resolver)

        # Inject persist failure
        svc._persist_state = lambda: (_ for _ in ()).throw(OSError("Simulated"))

        result = svc.open_epoch()
        assert result.success
        assert "warning" in result.data
        assert "epoch_id" in result.data

        # Epoch must remain open in memory
        assert svc._epoch_service.current_epoch is not None
        assert svc._persistence_degraded is True

    def test_close_epoch_persist_failure_returns_success_with_warning(self, resolver) -> None:
        """close_epoch: persist failure keeps epoch closed in memory and returns
        success with warning (no uncaught OSError)."""
        svc = GenesisService(resolver)
        svc.open_epoch()

        # Inject persist failure
        svc._persist_state = lambda: (_ for _ in ()).throw(OSError("Simulated"))

        result = svc.close_epoch(beacon_round=99)
        assert result.success
        assert "warning" in result.data
        assert "epoch_id" in result.data

        # Epoch must be closed in memory
        epoch = svc._epoch_service.current_epoch
        assert epoch is None or epoch.closed
        assert svc._persistence_degraded is True


class TestNonAuditPersistFailClosed:
    """CX round 7: non-audit mutators that call _persist_state() must use
    _safe_persist(on_rollback=...) — no uncaught OSError, state rolled back."""

    def test_withdraw_bid_persist_failure_rolls_back(self, resolver) -> None:
        """withdraw_bid: persist failure rolls back bid state and returns error."""
        svc = GenesisService(resolver)
        svc.open_epoch()
        svc.register_actor("c1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5)
        svc.register_actor("w1", ActorKind.HUMAN, "us", "beta", initial_trust=0.6)
        svc.create_listing("L-wb1", "Test", "Desc", "c1")
        svc.open_listing("L-wb1")
        svc.start_accepting_bids("L-wb1")
        svc.submit_bid("B-wb1", "L-wb1", "w1")

        # Inject persist failure
        svc._persist_state = lambda: (_ for _ in ()).throw(OSError("Simulated"))

        result = svc.withdraw_bid("B-wb1", "L-wb1")
        # Must return failure, not raise
        assert not result.success
        assert result.errors

        # Bid state must be rolled back to SUBMITTED
        bids = svc._bids.get("L-wb1", [])
        bid = [b for b in bids if b.bid_id == "B-wb1"][0]
        assert bid.state == BidState.SUBMITTED

    def test_cancel_listing_persist_failure_rolls_back(self, resolver) -> None:
        """cancel_listing: persist failure rolls back listing+bid states and returns error."""
        svc = GenesisService(resolver)
        svc.open_epoch()
        svc.register_actor("c1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5)
        svc.register_actor("w1", ActorKind.HUMAN, "us", "beta", initial_trust=0.6)
        svc.create_listing("L-cl1", "Test", "Desc", "c1")
        svc.open_listing("L-cl1")
        svc.start_accepting_bids("L-cl1")
        svc.submit_bid("B-cl1", "L-cl1", "w1")

        # Inject persist failure
        svc._persist_state = lambda: (_ for _ in ()).throw(OSError("Simulated"))

        result = svc.cancel_listing("L-cl1")
        # Must return failure, not raise
        assert not result.success
        assert result.errors

        # Listing must be rolled back (not cancelled)
        listing = svc.get_listing("L-cl1")
        assert listing.state == ListingState.ACCEPTING_BIDS

        # Bid must be rolled back to SUBMITTED (not WITHDRAWN)
        bids = svc._bids.get("L-cl1", [])
        bid = [b for b in bids if b.bid_id == "B-cl1"][0]
        assert bid.state == BidState.SUBMITTED

    def test_register_actor_persist_failure_rolls_back(self, resolver) -> None:
        """register_actor: persist failure removes actor from roster and trust records."""
        svc = GenesisService(resolver)

        # Inject persist failure
        svc._persist_state = lambda: (_ for _ in ()).throw(OSError("Simulated"))

        result = svc.register_actor("a-fail", ActorKind.HUMAN, "us", "acme", initial_trust=0.5)
        assert not result.success
        assert result.errors

        # Actor must not exist in roster or trust
        assert svc.get_actor("a-fail") is None
        assert svc.get_trust("a-fail") is None

    def test_quarantine_actor_persist_failure_rolls_back(self, resolver) -> None:
        """quarantine_actor: persist failure restores previous status."""
        from genesis.review.roster import ActorStatus
        svc = GenesisService(resolver)
        svc.register_actor("a-q1", ActorKind.HUMAN, "us", "acme", initial_trust=0.5)

        # Inject persist failure
        svc._persist_state = lambda: (_ for _ in ()).throw(OSError("Simulated"))

        result = svc.quarantine_actor("a-q1")
        assert not result.success

        # Actor must still be ACTIVE (not quarantined)
        actor = svc.get_actor("a-q1")
        assert actor.status == ActorStatus.ACTIVE
        trust = svc.get_trust("a-q1")
        assert trust.quarantined is False


class TestPersistence:
    def test_listing_survives_persistence(self, resolver, tmp_path) -> None:
        """Listings and bids persist across state store save/load."""
        from genesis.persistence.state_store import StateStore

        store = StateStore(tmp_path / "state.json")
        svc = GenesisService(resolver, state_store=store)
        svc.open_epoch()

        svc.register_actor("c1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5)
        svc.register_actor("w1", ActorKind.HUMAN, "us", "beta", initial_trust=0.6)

        svc.create_listing("L-P", "Persist Test", "D", "c1")
        svc.open_listing("L-P")
        svc.start_accepting_bids("L-P")
        svc.submit_bid("B-P1", "L-P", "w1")

        # Reload from state store
        store2 = StateStore(tmp_path / "state.json")
        svc2 = GenesisService(resolver, state_store=store2)

        listing = svc2.get_listing("L-P")
        assert listing is not None
        assert listing.state == ListingState.ACCEPTING_BIDS

        bids = svc2.get_bids("L-P")
        assert len(bids) == 1
        assert bids[0].bid_id == "B-P1"
        assert bids[0].worker_id == "w1"
