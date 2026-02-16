"""Tests for Phase 2 constitutional amendments.

Covers:
- Creator allocation (CostCategory, commission_params, event kind)
- Founder's veto (config flag, event kind)
- PoC mode (config, PolicyResolver)
- First Light event (event kind)
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from genesis.models.compensation import CostCategory, OperationalCostEntry
from genesis.persistence.event_log import EventKind, EventRecord


# ---------------------------------------------------------------------------
# WP1a: Creator allocation
# ---------------------------------------------------------------------------

class TestCreatorAllocationCategory:
    """CREATOR_ALLOCATION exists in CostCategory and integrates with the system."""

    def test_creator_allocation_in_cost_category(self) -> None:
        assert CostCategory.CREATOR_ALLOCATION == "creator_allocation"

    def test_creator_allocation_is_str_enum(self) -> None:
        assert isinstance(CostCategory.CREATOR_ALLOCATION, str)

    def test_cost_entry_with_creator_allocation(self) -> None:
        from datetime import datetime, timezone
        entry = OperationalCostEntry(
            cost_id="ca-001",
            category=CostCategory.CREATOR_ALLOCATION,
            amount=Decimal("10.00"),
            timestamp_utc=datetime.now(timezone.utc),
            description="Creator allocation for mission M-001",
        )
        assert entry.category == CostCategory.CREATOR_ALLOCATION
        assert entry.amount == Decimal("10.00")

    def test_creator_allocation_disbursed_event_kind(self) -> None:
        assert EventKind.CREATOR_ALLOCATION_DISBURSED == "creator_allocation_disbursed"

    def test_creator_allocation_event_record(self) -> None:
        record = EventRecord.create(
            event_id="evt-ca-001",
            event_kind=EventKind.CREATOR_ALLOCATION_DISBURSED,
            actor_id="genesis-system",
            payload={"mission_id": "M-001", "amount": "10.00", "recipient": "founder"},
        )
        assert record.event_kind == EventKind.CREATOR_ALLOCATION_DISBURSED
        assert record.event_hash.startswith("sha256:")


class TestCreatorAllocationPolicy:
    """creator_allocation_rate flows through PolicyResolver."""

    @pytest.fixture()
    def resolver(self) -> object:
        from genesis.policy.resolver import PolicyResolver
        config_dir = Path(__file__).resolve().parent.parent / "config"
        return PolicyResolver.from_config_dir(config_dir)

    def test_creator_allocation_rate_in_params(self, resolver) -> None:
        params = resolver.commission_params()
        assert "creator_allocation_rate" in params

    def test_creator_allocation_rate_is_decimal(self, resolver) -> None:
        params = resolver.commission_params()
        rate = params["creator_allocation_rate"]
        assert isinstance(rate, Decimal)
        assert rate == Decimal("0.02")

    def test_params_count_is_ten(self, resolver) -> None:
        params = resolver.commission_params()
        assert len(params) == 10


class TestCreatorAllocationInBreakdown:
    """Creator allocation costs appear in commission breakdown when present."""

    def test_creator_allocation_in_cost_breakdown(self) -> None:
        from datetime import datetime, timezone, timedelta
        from genesis.policy.resolver import PolicyResolver
        from genesis.compensation.engine import CommissionEngine
        from genesis.compensation.ledger import OperationalLedger
        from genesis.models.compensation import (
            CompletedMission, ReserveFundState,
        )

        config_dir = Path(__file__).resolve().parent.parent / "config"
        resolver = PolicyResolver.from_config_dir(config_dir)
        engine = CommissionEngine(resolver)
        ledger = OperationalLedger()
        now = datetime.now(timezone.utc)

        # Populate with enough missions to exit bootstrap
        for i in range(55):
            ledger.record_completed_mission(CompletedMission(
                mission_id=f"M-{i:03d}",
                reward_amount=Decimal("100"),
                completed_utc=now - timedelta(days=80 - i),
                operational_costs=Decimal("5"),
            ))
            # Record infrastructure costs
            ledger.record_operational_cost(OperationalCostEntry(
                cost_id=f"infra-{i:03d}",
                category=CostCategory.INFRASTRUCTURE,
                amount=Decimal("3"),
                timestamp_utc=now - timedelta(days=80 - i),
                description="Server costs",
            ))
            # Record creator allocation costs
            ledger.record_operational_cost(OperationalCostEntry(
                cost_id=f"ca-{i:03d}",
                category=CostCategory.CREATOR_ALLOCATION,
                amount=Decimal("2"),
                timestamp_utc=now - timedelta(days=80 - i),
                description="Creator allocation",
            ))

        reserve = ReserveFundState.compute(
            balance=Decimal("1000"),
            rolling_monthly_ops=Decimal("150"),
            target_months=6,
        )

        breakdown = engine.compute_commission(
            mission_reward=Decimal("500"),
            ledger=ledger,
            reserve=reserve,
            now=now,
        )

        # Creator allocation = 2% of mission reward (500), not 2% of commission
        assert "creator_allocation" in breakdown.cost_breakdown
        assert breakdown.cost_breakdown["creator_allocation"] == Decimal("10.00")
        assert breakdown.creator_allocation == Decimal("10.00")
        # Invariant: commission + creator + worker = reward
        total = breakdown.commission_amount + breakdown.creator_allocation + breakdown.worker_payout
        assert total == breakdown.mission_reward


# ---------------------------------------------------------------------------
# WP1b: Founder's veto
# ---------------------------------------------------------------------------

class TestFounderVeto:
    """Founder veto flag and event kind."""

    @pytest.fixture()
    def resolver(self) -> object:
        from genesis.policy.resolver import PolicyResolver
        config_dir = Path(__file__).resolve().parent.parent / "config"
        return PolicyResolver.from_config_dir(config_dir)

    def test_founder_veto_active_returns_bool(self, resolver) -> None:
        result = resolver.founder_veto_active()
        assert isinstance(result, bool)

    def test_founder_veto_active_is_true_in_default_config(self, resolver) -> None:
        assert resolver.founder_veto_active() is True

    def test_founder_veto_event_kind(self) -> None:
        assert EventKind.FOUNDER_VETO_EXERCISED == "founder_veto_exercised"

    def test_founder_veto_event_record(self) -> None:
        record = EventRecord.create(
            event_id="evt-veto-001",
            event_kind=EventKind.FOUNDER_VETO_EXERCISED,
            actor_id="george-jackson-001",
            payload={"decision_id": "D-001", "reason": "Misaligned with founding vision"},
        )
        assert record.event_kind == EventKind.FOUNDER_VETO_EXERCISED
        assert record.event_hash.startswith("sha256:")


# ---------------------------------------------------------------------------
# WP1d: PoC mode
# ---------------------------------------------------------------------------

class TestPocMode:
    """PoC mode configuration through PolicyResolver."""

    @pytest.fixture()
    def resolver(self) -> object:
        from genesis.policy.resolver import PolicyResolver
        config_dir = Path(__file__).resolve().parent.parent / "config"
        return PolicyResolver.from_config_dir(config_dir)

    def test_poc_mode_returns_dict(self, resolver) -> None:
        result = resolver.poc_mode()
        assert isinstance(result, dict)

    def test_poc_mode_active_by_default(self, resolver) -> None:
        result = resolver.poc_mode()
        assert result["active"] is True

    def test_poc_mode_has_banner_text(self, resolver) -> None:
        result = resolver.poc_mode()
        assert "banner_text" in result
        assert len(result["banner_text"]) > 0

    def test_poc_mode_has_label(self, resolver) -> None:
        result = resolver.poc_mode()
        assert result["label"] == "Proof of Concept"

    def test_poc_mode_defaults_when_not_configured(self) -> None:
        from genesis.policy.resolver import PolicyResolver
        # PolicyResolver with minimal valid config but no poc_mode key
        resolver = PolicyResolver(
            params={"version": "0.1", "genesis": {}},
            policy={"version": "0.1"},
        )
        result = resolver.poc_mode()
        assert result["active"] is False


# ---------------------------------------------------------------------------
# WP1e: First Light
# ---------------------------------------------------------------------------

class TestFirstLight:
    """First Light event kind."""

    def test_first_light_event_kind(self) -> None:
        assert EventKind.FIRST_LIGHT == "first_light"

    def test_first_light_event_record(self) -> None:
        record = EventRecord.create(
            event_id="evt-first-light",
            event_kind=EventKind.FIRST_LIGHT,
            actor_id="genesis-system",
            payload={
                "verified_humans": 50,
                "phase_transition": "G0_to_G1",
                "poc_mode_deactivated": True,
            },
        )
        assert record.event_kind == EventKind.FIRST_LIGHT
        assert record.event_hash.startswith("sha256:")
        assert record.payload["verified_humans"] == 50
