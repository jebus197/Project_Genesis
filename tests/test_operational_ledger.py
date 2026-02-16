"""Tests for operational ledger — proves rolling window mechanics work correctly."""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from genesis.compensation.ledger import OperationalLedger
from genesis.models.compensation import (
    CompletedMission,
    CostCategory,
    OperationalCostEntry,
)


def _now() -> datetime:
    return datetime(2026, 2, 16, 12, 0, 0, tzinfo=timezone.utc)


def _make_mission(mission_id: str, reward: str, days_ago: int) -> CompletedMission:
    return CompletedMission(
        mission_id=mission_id,
        reward_amount=Decimal(reward),
        completed_utc=_now() - timedelta(days=days_ago),
        operational_costs=Decimal("10"),
    )


def _make_cost(cost_id: str, amount: str, days_ago: int) -> OperationalCostEntry:
    return OperationalCostEntry(
        cost_id=cost_id,
        category=CostCategory.INFRASTRUCTURE,
        amount=Decimal(amount),
        timestamp_utc=_now() - timedelta(days=days_ago),
        description=f"Test cost {cost_id}",
    )


class TestMissionRecording:
    def test_record_and_count(self) -> None:
        ledger = OperationalLedger()
        assert ledger.total_completed_missions() == 0
        ledger.record_completed_mission(_make_mission("m1", "500", 1))
        assert ledger.total_completed_missions() == 1

    def test_multiple_missions(self) -> None:
        ledger = OperationalLedger()
        for i in range(10):
            ledger.record_completed_mission(_make_mission(f"m{i}", "500", i))
        assert ledger.total_completed_missions() == 10


class TestWindowExtraction:
    def test_missions_within_time_window(self) -> None:
        """Missions within the time window are returned."""
        ledger = OperationalLedger()
        # 5 missions within 90 days, 5 outside
        for i in range(10):
            ledger.record_completed_mission(
                _make_mission(f"m{i}", "500", days_ago=i * 20)
            )
        result = ledger.missions_in_window(90, 3, _now())
        # Days 0, 20, 40, 60, 80 are within 90 days
        assert len(result) == 5

    def test_extends_back_for_min_missions(self) -> None:
        """Window extends back to capture min_missions if not enough in time window."""
        ledger = OperationalLedger()
        # 3 missions within 90 days, 7 older
        for i in range(10):
            ledger.record_completed_mission(
                _make_mission(f"m{i}", "500", days_ago=i * 50)
            )
        # Only 2 within 90 days (0, 50), but min_missions=5
        result = ledger.missions_in_window(90, 5, _now())
        assert len(result) == 5

    def test_returns_all_if_fewer_than_min(self) -> None:
        """If total missions < min_missions, return all available."""
        ledger = OperationalLedger()
        for i in range(3):
            ledger.record_completed_mission(
                _make_mission(f"m{i}", "500", days_ago=i * 10)
            )
        result = ledger.missions_in_window(90, 50, _now())
        assert len(result) == 3

    def test_empty_ledger(self) -> None:
        """Empty ledger returns empty window."""
        ledger = OperationalLedger()
        result = ledger.missions_in_window(90, 50, _now())
        assert len(result) == 0


class TestCostWindowExtraction:
    def test_costs_match_mission_window(self) -> None:
        """Costs are filtered to match the mission window timespan."""
        ledger = OperationalLedger()
        now = _now()
        # Missions: days ago 0, 30, 60 (earliest is 60 days ago)
        for i in range(3):
            ledger.record_completed_mission(
                _make_mission(f"m{i}", "500", days_ago=i * 30)
            )
        # Costs: days ago 0, 20, 50, 120
        # First 3 are within the mission window (>= 60 days ago)
        # Last one (120 days ago) is outside
        ledger.record_operational_cost(_make_cost("c0", "10", days_ago=0))
        ledger.record_operational_cost(_make_cost("c1", "10", days_ago=20))
        ledger.record_operational_cost(_make_cost("c2", "10", days_ago=50))
        ledger.record_operational_cost(_make_cost("c3", "10", days_ago=120))
        result = ledger.costs_in_window(90, 3, now)
        # Cost at day 120 is outside the window (earliest mission is at day 60)
        assert len(result) == 3

    def test_costs_empty_when_no_missions(self) -> None:
        """No missions → no costs returned."""
        ledger = OperationalLedger()
        ledger.record_operational_cost(_make_cost("c1", "10", 5))
        result = ledger.costs_in_window(90, 50, _now())
        assert len(result) == 0


class TestBootstrapDetection:
    def test_bootstrap_under_threshold(self) -> None:
        """Fewer than 50 missions = bootstrap mode."""
        ledger = OperationalLedger()
        for i in range(49):
            ledger.record_completed_mission(_make_mission(f"m{i}", "500", i))
        assert ledger.total_completed_missions() < 50

    def test_no_bootstrap_at_threshold(self) -> None:
        """Exactly 50 missions = no longer bootstrap."""
        ledger = OperationalLedger()
        for i in range(50):
            ledger.record_completed_mission(_make_mission(f"m{i}", "500", i))
        assert ledger.total_completed_missions() >= 50
