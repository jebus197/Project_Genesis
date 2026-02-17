"""Tests for platform lifecycle features: First Light, creator allocation
event emission, founder dormancy tracking, and PoC mode transition.

These test the service-layer wiring that connects the constitutional
provisions to the event log and policy resolver.
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

from genesis.models.trust import ActorKind
from genesis.persistence.event_log import EventLog, EventKind
from genesis.persistence.state_store import StateStore
from genesis.policy.resolver import PolicyResolver
from genesis.service import GenesisService


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def service(resolver: PolicyResolver) -> GenesisService:
    svc = GenesisService(resolver, event_log=EventLog())
    svc.open_epoch("test-epoch")
    return svc


def _register_humans(service: GenesisService, count: int = 5) -> None:
    """Register enough humans for First Light data requirements."""
    regions = ["NA", "EU", "APAC", "LATAM", "AF"]
    orgs = ["Org1", "Org2", "Org3", "Org4", "Org5"]
    for i in range(count):
        service.register_actor(
            actor_id=f"human-{i}",
            actor_kind=ActorKind.HUMAN,
            region=regions[i % len(regions)],
            organization=orgs[i % len(orgs)],
            initial_trust=0.5,
        )


# ------------------------------------------------------------------
# First Light trigger
# ------------------------------------------------------------------

class TestFirstLight:
    """Prove that check_first_light fires the event and disables PoC."""

    def test_not_achieved_when_revenue_insufficient(
        self, service: GenesisService,
    ) -> None:
        _register_humans(service)
        result = service.check_first_light(
            monthly_revenue=Decimal("100"),
            monthly_costs=Decimal("1000"),
            reserve_balance=Decimal("0"),
        )
        assert result.success
        assert result.data["first_light"] is False
        assert "progress_pct" in result.data

    def test_achieved_fires_event_and_disables_poc(
        self, service: GenesisService,
    ) -> None:
        _register_humans(service)
        result = service.check_first_light(
            monthly_revenue=Decimal("2000"),
            monthly_costs=Decimal("1000"),
            reserve_balance=Decimal("5000"),  # >= 3 months
        )
        assert result.success
        assert result.data["first_light"] is True
        assert result.data["achieved_now"] is True
        assert result.data["poc_mode_disabled"] is True

        # Event was logged
        fl_events = service._event_log.events(EventKind.FIRST_LIGHT)
        assert len(fl_events) == 1
        assert fl_events[0].actor_id == "system"

        # PoC mode is now off
        assert service._resolver.poc_mode()["active"] is False

    def test_first_light_fires_exactly_once(
        self, service: GenesisService,
    ) -> None:
        _register_humans(service)
        # First call triggers
        r1 = service.check_first_light(
            monthly_revenue=Decimal("2000"),
            monthly_costs=Decimal("1000"),
            reserve_balance=Decimal("5000"),
        )
        assert r1.data["achieved_now"] is True

        # Second call is a no-op
        r2 = service.check_first_light(
            monthly_revenue=Decimal("3000"),
            monthly_costs=Decimal("1000"),
            reserve_balance=Decimal("10000"),
        )
        assert r2.data["first_light"] is True
        assert r2.data["already_achieved"] is True

        # Still only one event
        fl_events = service._event_log.events(EventKind.FIRST_LIGHT)
        assert len(fl_events) == 1

    def test_status_reflects_first_light(
        self, service: GenesisService,
    ) -> None:
        status = service.status()
        assert status["first_light"]["achieved"] is False
        assert status["first_light"]["poc_mode_active"] is True

        _register_humans(service)
        service.check_first_light(
            monthly_revenue=Decimal("2000"),
            monthly_costs=Decimal("1000"),
            reserve_balance=Decimal("5000"),
        )

        status = service.status()
        assert status["first_light"]["achieved"] is True
        assert status["first_light"]["poc_mode_active"] is False


# ------------------------------------------------------------------
# Creator allocation event emission
# ------------------------------------------------------------------

class TestCreatorAllocationEvent:
    """Prove that record_creator_allocation emits the audit event."""

    def test_records_positive_allocation(
        self, service: GenesisService,
    ) -> None:
        result = service.record_creator_allocation(
            mission_id="M-001",
            creator_allocation=Decimal("10.00"),
            employer_creator_fee=Decimal("25.00"),
            mission_reward=Decimal("500.00"),
            worker_id="worker-1",
        )
        assert result.success
        assert result.data["recorded"] is True
        assert result.data["worker_side_allocation"] == "10.00"
        assert result.data["employer_side_fee"] == "25.00"
        assert result.data["total_creator_income"] == "35.00"

        events = service._event_log.events(
            EventKind.CREATOR_ALLOCATION_DISBURSED,
        )
        assert len(events) == 1
        assert events[0].actor_id == "founder"
        assert events[0].payload["mission_id"] == "M-001"
        assert events[0].payload["worker_side_allocation"] == "10.00"
        assert events[0].payload["employer_side_fee"] == "25.00"
        assert events[0].payload["worker_side_rate"] == "0.05"
        assert events[0].payload["employer_side_rate"] == "0.05"

    def test_skips_zero_allocation(
        self, service: GenesisService,
    ) -> None:
        result = service.record_creator_allocation(
            mission_id="M-002",
            creator_allocation=Decimal("0"),
            employer_creator_fee=Decimal("0"),
            mission_reward=Decimal("500.00"),
            worker_id="worker-1",
        )
        assert result.success
        assert result.data["recorded"] is False
        assert result.data["reason"] == "zero_allocation"

    def test_multiple_allocations_produce_multiple_events(
        self, service: GenesisService,
    ) -> None:
        for i in range(3):
            service.record_creator_allocation(
                mission_id=f"M-{i:03d}",
                creator_allocation=Decimal("20.00"),
                employer_creator_fee=Decimal("50.00"),
                mission_reward=Decimal("1000.00"),
                worker_id=f"worker-{i}",
            )
        events = service._event_log.events(
            EventKind.CREATOR_ALLOCATION_DISBURSED,
        )
        assert len(events) == 3


# ------------------------------------------------------------------
# Founder dormancy tracking
# ------------------------------------------------------------------

class TestFounderDormancy:
    """Prove founder designation, action tracking, and dormancy check."""

    def test_set_founder_requires_registered_human(
        self, service: GenesisService,
    ) -> None:
        result = service.set_founder("nonexistent")
        assert not result.success
        assert "not found" in result.errors[0].lower()

    def test_set_founder_rejects_machines(
        self, service: GenesisService,
    ) -> None:
        # Register a human operator first
        service.register_actor(
            actor_id="operator", actor_kind=ActorKind.HUMAN,
            region="NA", organization="Org1",
        )
        service.register_machine(
            actor_id="bot-1", operator_id="operator",
            region="NA", organization="Org1",
        )
        result = service.set_founder("bot-1")
        assert not result.success
        assert "human" in result.errors[0].lower()

    def test_set_founder_and_record_action(
        self, service: GenesisService,
    ) -> None:
        service.register_actor(
            actor_id="george", actor_kind=ActorKind.HUMAN,
            region="EU", organization="Genesis",
        )
        result = service.set_founder("george")
        assert result.success
        assert result.data["founder_id"] == "george"

        # Record an action
        action_result = service.record_founder_action()
        assert action_result.success
        assert action_result.data["dormancy_reset"] is True

    def test_record_action_without_founder_fails(
        self, service: GenesisService,
    ) -> None:
        result = service.record_founder_action()
        assert not result.success

    def test_dormancy_not_triggered_when_recent(
        self, service: GenesisService,
    ) -> None:
        service.register_actor(
            actor_id="george", actor_kind=ActorKind.HUMAN,
            region="EU", organization="Genesis",
        )
        service.set_founder("george")
        result = service.check_dormancy()
        assert result.success
        assert result.data["dormancy_triggered"] is False
        assert result.data["elapsed_years"] < 1.0

    def test_dormancy_check_without_founder_fails(
        self, service: GenesisService,
    ) -> None:
        result = service.check_dormancy()
        assert not result.success

    def test_status_reflects_founder(
        self, service: GenesisService,
    ) -> None:
        status = service.status()
        assert status["founder"]["designated"] is False

        service.register_actor(
            actor_id="george", actor_kind=ActorKind.HUMAN,
            region="EU", organization="Genesis",
        )
        service.set_founder("george")

        status = service.status()
        assert status["founder"]["designated"] is True
        assert status["founder"]["founder_id"] == "george"


# ------------------------------------------------------------------
# Restart regression (P1: lifecycle state persistence)
# ------------------------------------------------------------------

class TestLifecyclePersistence:
    """Prove that lifecycle state survives service restarts.

    CX P1 finding: without persistence, First Light would fire
    duplicate events on every restart and the dormancy counter
    would reset to None.
    """

    def test_first_light_survives_restart(self, tmp_path: Path) -> None:
        """First Light fires once, persists, and is suppressed after restart."""
        store_path = tmp_path / "genesis_state.json"
        log_path = tmp_path / "events.jsonl"

        resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
        store = StateStore(store_path)
        log = EventLog(log_path)

        svc1 = GenesisService(resolver, event_log=log, state_store=store)
        svc1.open_epoch("epoch-1")

        # Register humans and trigger First Light
        for i in range(5):
            svc1.register_actor(
                actor_id=f"h-{i}", actor_kind=ActorKind.HUMAN,
                region="EU", organization="Org",
            )
        r1 = svc1.check_first_light(
            monthly_revenue=Decimal("2000"),
            monthly_costs=Decimal("1000"),
            reserve_balance=Decimal("5000"),
        )
        assert r1.data["first_light"] is True
        assert r1.data["achieved_now"] is True

        # Simulate restart: fresh StateStore, EventLog, GenesisService
        store2 = StateStore(store_path)
        log2 = EventLog(log_path)
        resolver2 = PolicyResolver.from_config_dir(CONFIG_DIR)
        svc2 = GenesisService(resolver2, event_log=log2, state_store=store2)
        svc2.open_epoch("epoch-2")

        # First Light should be already-achieved (no new event)
        r2 = svc2.check_first_light(
            monthly_revenue=Decimal("3000"),
            monthly_costs=Decimal("1000"),
            reserve_balance=Decimal("10000"),
        )
        assert r2.data["first_light"] is True
        assert r2.data["already_achieved"] is True

        # PoC mode must still be off after restart
        assert svc2._resolver.poc_mode()["active"] is False

    def test_founder_dormancy_survives_restart(self, tmp_path: Path) -> None:
        """Founder designation and last-action timestamp persist across restart."""
        store_path = tmp_path / "genesis_state.json"

        resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
        store = StateStore(store_path)

        svc1 = GenesisService(resolver, event_log=EventLog(), state_store=store)
        svc1.open_epoch("epoch-1")
        svc1.register_actor(
            actor_id="george", actor_kind=ActorKind.HUMAN,
            region="EU", organization="Genesis",
        )
        svc1.set_founder("george")
        svc1.record_founder_action()

        # Capture the last-action timestamp
        original_ts = svc1._founder_last_action_utc

        # Simulate restart
        store2 = StateStore(store_path)
        resolver2 = PolicyResolver.from_config_dir(CONFIG_DIR)
        svc2 = GenesisService(resolver2, event_log=EventLog(), state_store=store2)

        assert svc2._founder_id == "george"
        assert svc2._founder_last_action_utc is not None
        # Timestamps may lose sub-second precision in JSON round-trip
        assert abs(
            (svc2._founder_last_action_utc - original_ts).total_seconds()
        ) < 2.0

    def test_poc_mode_stays_off_after_restart(self, tmp_path: Path) -> None:
        """PoC mode disabled by First Light must remain off after restart."""
        store_path = tmp_path / "genesis_state.json"

        resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
        store = StateStore(store_path)

        svc1 = GenesisService(resolver, event_log=EventLog(), state_store=store)
        svc1.open_epoch("epoch-1")
        for i in range(5):
            svc1.register_actor(
                actor_id=f"h-{i}", actor_kind=ActorKind.HUMAN,
                region="EU", organization="Org",
            )
        svc1.check_first_light(
            monthly_revenue=Decimal("2000"),
            monthly_costs=Decimal("1000"),
            reserve_balance=Decimal("5000"),
        )
        assert svc1._resolver.poc_mode()["active"] is False

        # Restart with fresh resolver (PoC default = true in config)
        store2 = StateStore(store_path)
        resolver2 = PolicyResolver.from_config_dir(CONFIG_DIR)
        svc2 = GenesisService(resolver2, event_log=EventLog(), state_store=store2)

        # PoC must be off — restored from persisted lifecycle state
        assert svc2._resolver.poc_mode()["active"] is False


# ------------------------------------------------------------------
# Production call-path integration (P2 wiring)
# ------------------------------------------------------------------

class TestProductionCallPaths:
    """Prove that lifecycle methods are wired into production paths.

    CX P2 finding: check_first_light and record_creator_allocation
    had no call sites outside tests. process_mission_payment() now
    wires them into the payment pipeline.
    """

    def test_process_mission_payment_records_creator_allocation(
        self, service: GenesisService,
    ) -> None:
        """Payment processing automatically emits creator allocation event."""
        from genesis.compensation.ledger import OperationalLedger
        from genesis.models.compensation import (
            CompletedMission,
            ReserveFundState,
        )
        from genesis.models.mission import MissionClass, DomainType

        # Register actors (diverse enough for reviewer assignment)
        regions = ["NA", "EU", "APAC", "LATAM", "AF"]
        orgs = ["Org1", "Org2", "Org3", "Org4", "Org5"]
        families = ["gpt", "claude", "gemini", "llama", "mistral"]
        methods = ["llm_judge", "human_reviewer", "reasoning_model",
                    "human_reviewer", "llm_judge"]
        for i in range(5):
            service.register_actor(
                actor_id=f"actor-{i}", actor_kind=ActorKind.HUMAN,
                region=regions[i], organization=orgs[i],
                model_family=families[i], method_type=methods[i],
                initial_trust=0.5,
            )

        # Create and drive mission to APPROVED
        service.create_mission(
            mission_id="M-PAY-001",
            title="Test payment",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
            worker_id="actor-0",
        )
        service.submit_mission("M-PAY-001")
        service.assign_reviewers("M-PAY-001", seed="pay-test")

        mission = service.get_mission("M-PAY-001")
        service.add_evidence(
            "M-PAY-001",
            artifact_hash="sha256:" + "a" * 64,
            signature="ed25519:" + "b" * 64,
        )
        for reviewer in mission.reviewers:
            service.submit_review("M-PAY-001", reviewer.id, "APPROVE")
        service.complete_review("M-PAY-001")
        service.approve_mission("M-PAY-001")

        # Build ledger + reserve for commission computation
        ledger = OperationalLedger()
        now = datetime.now(timezone.utc)
        for i in range(55):
            ledger.record_completed_mission(CompletedMission(
                mission_id=f"hist-{i}",
                reward_amount=Decimal("500.00"),
                completed_utc=now - timedelta(days=30),
                operational_costs=Decimal("10.00"),
            ))
        reserve = ReserveFundState(
            balance=Decimal("10000"),
            target=Decimal("10000"),
            gap=Decimal("0"),
            is_below_target=False,
        )

        # Process payment — should auto-emit both-sides creator allocation
        result = service.process_mission_payment(
            mission_id="M-PAY-001",
            mission_reward=Decimal("500.00"),
            ledger=ledger,
            reserve=reserve,
        )
        assert result.success
        # Worker-side: 5% of worker payout (after commission)
        assert Decimal(result.data["creator_allocation"]) > Decimal("0")
        # Employer-side: 5% of mission reward = 25.00
        assert Decimal(result.data["employer_creator_fee"]) == Decimal("25.00")
        # Total creator income = worker-side + employer-side
        assert Decimal(result.data["total_creator_income"]) > Decimal("25.00")
        # Total escrow = mission_reward + employer_creator_fee
        assert Decimal(result.data["total_escrow"]) == Decimal("525.00")

        # Creator allocation event was emitted through the payment path
        events = service._event_log.events(
            EventKind.CREATOR_ALLOCATION_DISBURSED,
        )
        assert len(events) >= 1
        assert events[-1].payload["mission_id"] == "M-PAY-001"
        assert "worker_side_allocation" in events[-1].payload
        assert "employer_side_fee" in events[-1].payload

    def test_process_mission_payment_rejects_unapproved(
        self, service: GenesisService,
    ) -> None:
        """Payment processing rejects missions not in APPROVED state."""
        from genesis.compensation.ledger import OperationalLedger
        from genesis.models.compensation import ReserveFundState
        from genesis.models.mission import MissionClass, DomainType

        service.create_mission(
            mission_id="M-DRAFT",
            title="Draft mission",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
        )

        result = service.process_mission_payment(
            mission_id="M-DRAFT",
            mission_reward=Decimal("500.00"),
            ledger=OperationalLedger(),
            reserve=ReserveFundState(
                balance=Decimal("10000"),
                target=Decimal("10000"),
                gap=Decimal("0"),
                is_below_target=False,
            ),
        )
        assert not result.success
        assert "APPROVED" in result.errors[0]

    def test_periodic_first_light_check_delegates(
        self, service: GenesisService,
    ) -> None:
        """periodic_first_light_check delegates to check_first_light."""
        _register_humans(service)
        result = service.periodic_first_light_check(
            monthly_revenue=Decimal("100"),
            monthly_costs=Decimal("1000"),
            reserve_balance=Decimal("0"),
        )
        assert result.success
        assert result.data["first_light"] is False


# ------------------------------------------------------------------
# Persistence warning surfacing (P2-a residual)
# ------------------------------------------------------------------

class TestPersistenceWarningSurfacing:
    """Prove that founder lifecycle methods surface persistence warnings."""

    def test_set_founder_surfaces_persist_warning(
        self, service: GenesisService, monkeypatch,
    ) -> None:
        """set_founder returns warning field when persistence degrades."""
        service.register_actor(
            actor_id="george", actor_kind=ActorKind.HUMAN,
            region="EU", organization="Genesis",
        )
        monkeypatch.setattr(
            service, "_safe_persist_post_audit",
            lambda: "Persistence degraded: disk full",
        )
        result = service.set_founder("george")
        assert result.success
        assert "warning" in result.data
        assert "disk full" in result.data["warning"]

    def test_record_founder_action_surfaces_persist_warning(
        self, service: GenesisService, monkeypatch,
    ) -> None:
        """record_founder_action returns warning field when persistence degrades."""
        service.register_actor(
            actor_id="george", actor_kind=ActorKind.HUMAN,
            region="EU", organization="Genesis",
        )
        service.set_founder("george")
        monkeypatch.setattr(
            service, "_safe_persist_post_audit",
            lambda: "Persistence degraded: write failed",
        )
        result = service.record_founder_action()
        assert result.success
        assert "warning" in result.data
        assert "write failed" in result.data["warning"]


# ------------------------------------------------------------------
# CLI adapter integration (P2-b: runtime call sites)
# ------------------------------------------------------------------

class TestCLIAdapterIntegration:
    """Prove that CLI commands wire through to service lifecycle methods.

    CX P2-b finding: production entrypoints had no call sites outside
    tests. These tests verify the CLI adapter is a live call site.
    """

    def test_cli_check_first_light_calls_through(self, tmp_path: Path) -> None:
        """CLI check-first-light calls periodic_first_light_check."""
        from genesis.cli import main

        exit_code = main([
            "--config", str(CONFIG_DIR),
            "check-first-light",
            "--revenue", "100",
            "--costs", "1000",
            "--reserve", "0",
        ])
        assert exit_code == 0

    def test_cli_process_payment_rejects_missing_mission(
        self, tmp_path: Path,
    ) -> None:
        """CLI process-payment returns error for non-existent mission."""
        from genesis.cli import main

        exit_code = main([
            "--config", str(CONFIG_DIR),
            "process-payment",
            "--mission-id", "NONEXISTENT",
            "--reward", "500.00",
        ])
        assert exit_code == 1


class TestNoEpochCrashRegression:
    """CX P1: lifecycle methods must not crash with RuntimeError
    when no epoch is open. They should degrade gracefully.
    """

    def test_check_first_light_achieved_no_epoch_no_crash(
        self, resolver: PolicyResolver,
    ) -> None:
        """First Light achieved path must not crash without an open epoch."""
        svc = GenesisService(resolver, event_log=EventLog())
        # Register humans WITH an epoch (needed for registration)
        svc.open_epoch("setup-epoch")
        _register_humans(svc, 5)
        svc.close_epoch(beacon_round=1)
        # Now NO epoch is open — call check_first_light with achievable financials
        result = svc.check_first_light(
            monthly_revenue=Decimal("2000"),
            monthly_costs=Decimal("500"),
            reserve_balance=Decimal("5000"),
        )
        # Must not raise RuntimeError — should succeed gracefully
        assert result.success is True
        assert result.data["first_light"] is True

    def test_record_creator_allocation_no_epoch_no_crash(
        self, resolver: PolicyResolver,
    ) -> None:
        """Creator allocation recording must not crash without an open epoch."""
        svc = GenesisService(resolver, event_log=EventLog())
        # No epoch opened at all
        result = svc.record_creator_allocation(
            mission_id="test-mission",
            creator_allocation=Decimal("10.00"),
            employer_creator_fee=Decimal("25.00"),
            mission_reward=Decimal("500.00"),
            worker_id="worker-1",
        )
        # Must not raise RuntimeError — should return failure ServiceResult
        assert result.success is False
        assert any("RuntimeError" in e or "epoch" in e.lower() for e in result.errors)
