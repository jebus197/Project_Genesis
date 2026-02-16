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
            mission_reward=Decimal("500.00"),
            worker_id="worker-1",
        )
        assert result.success
        assert result.data["recorded"] is True

        events = service._event_log.events(
            EventKind.CREATOR_ALLOCATION_DISBURSED,
        )
        assert len(events) == 1
        assert events[0].actor_id == "founder"
        assert events[0].payload["mission_id"] == "M-001"
        assert events[0].payload["creator_allocation"] == "10.00"
        assert events[0].payload["rate"] == "0.02"

    def test_skips_zero_allocation(
        self, service: GenesisService,
    ) -> None:
        result = service.record_creator_allocation(
            mission_id="M-002",
            creator_allocation=Decimal("0"),
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
