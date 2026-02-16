"""Tests for escrow manager — proves escrow lifecycle invariants hold."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from genesis.compensation.escrow import EscrowManager
from genesis.models.compensation import (
    CommissionBreakdown,
    EscrowState,
    ReserveFundState,
    WindowStats,
)


def _now() -> datetime:
    return datetime(2026, 2, 16, 12, 0, 0, tzinfo=timezone.utc)


def _mock_breakdown(
    mission_reward: str = "500",
    rate: str = "0.05",
    creator_allocation_rate: str = "0.02",
) -> CommissionBreakdown:
    """Create a mock commission breakdown for escrow release tests."""
    reward = Decimal(mission_reward)
    r = Decimal(rate)
    commission = reward * r
    creator_alloc = (reward * Decimal(creator_allocation_rate)).quantize(Decimal("0.01"))
    return CommissionBreakdown(
        rate=r,
        raw_rate=r,
        cost_ratio=Decimal("0.04"),
        commission_amount=commission,
        creator_allocation=creator_alloc,
        worker_payout=reward - commission - creator_alloc,
        mission_reward=reward,
        cost_breakdown={"infrastructure": Decimal("10"), "creator_allocation": creator_alloc},
        is_bootstrap=False,
        window_stats=WindowStats(
            missions_in_window=60,
            total_completed_missions=100,
            window_days_actual=60,
            window_days_configured=90,
            min_missions_configured=50,
            is_bootstrap=False,
        ),
        reserve_contribution=Decimal("2"),
        safety_margin=Decimal("1.3"),
    )


class TestEscrowCreation:
    def test_create_escrow(self) -> None:
        manager = EscrowManager()
        record = manager.create_escrow("m1", "poster1", Decimal("500"), now=_now())
        assert record.state == EscrowState.PENDING
        assert record.amount == Decimal("500")
        assert record.mission_id == "m1"
        assert record.staker_id == "poster1"

    def test_create_with_explicit_id(self) -> None:
        manager = EscrowManager()
        record = manager.create_escrow(
            "m1", "poster1", Decimal("500"),
            escrow_id="custom_id", now=_now()
        )
        assert record.escrow_id == "custom_id"

    def test_create_rejects_zero_amount(self) -> None:
        manager = EscrowManager()
        with pytest.raises(ValueError, match="positive"):
            manager.create_escrow("m1", "poster1", Decimal("0"), now=_now())

    def test_create_rejects_negative_amount(self) -> None:
        manager = EscrowManager()
        with pytest.raises(ValueError, match="positive"):
            manager.create_escrow("m1", "poster1", Decimal("-100"), now=_now())


class TestEscrowLifecycle:
    def test_happy_path(self) -> None:
        """PENDING → LOCKED → RELEASING → RELEASED."""
        manager = EscrowManager()
        record = manager.create_escrow(
            "m1", "poster1", Decimal("500"), escrow_id="e1", now=_now()
        )
        assert record.state == EscrowState.PENDING

        record = manager.lock_escrow("e1", now=_now())
        assert record.state == EscrowState.LOCKED
        assert record.locked_utc is not None

        breakdown = _mock_breakdown("500", "0.05")
        record, payout = manager.release_escrow("e1", breakdown, now=_now())
        assert record.state == EscrowState.RELEASED
        assert record.released_utc is not None
        assert payout == Decimal("465")  # 500 - 25 commission - 10 creator
        assert record.commission_amount == Decimal("25")
        assert record.worker_payout == Decimal("465")

    def test_refund_path(self) -> None:
        """PENDING → LOCKED → REFUNDED."""
        manager = EscrowManager()
        record = manager.create_escrow(
            "m1", "poster1", Decimal("500"), escrow_id="e1", now=_now()
        )
        manager.lock_escrow("e1", now=_now())
        record = manager.refund_escrow("e1", now=_now())
        assert record.state == EscrowState.REFUNDED
        assert record.refunded_utc is not None

    def test_dispute_then_release(self) -> None:
        """PENDING → LOCKED → DISPUTED → RELEASED."""
        manager = EscrowManager()
        record = manager.create_escrow(
            "m1", "poster1", Decimal("500"), escrow_id="e1", now=_now()
        )
        manager.lock_escrow("e1", now=_now())
        record = manager.dispute_escrow("e1", now=_now())
        assert record.state == EscrowState.DISPUTED
        assert record.disputed_utc is not None

        breakdown = _mock_breakdown("500", "0.05")
        record, payout = manager.release_escrow("e1", breakdown, now=_now())
        assert record.state == EscrowState.RELEASED
        assert payout == Decimal("465")  # 500 - 25 commission - 10 creator

    def test_dispute_then_refund(self) -> None:
        """PENDING → LOCKED → DISPUTED → REFUNDED."""
        manager = EscrowManager()
        manager.create_escrow(
            "m1", "poster1", Decimal("500"), escrow_id="e1", now=_now()
        )
        manager.lock_escrow("e1", now=_now())
        manager.dispute_escrow("e1", now=_now())
        record = manager.refund_escrow("e1", now=_now())
        assert record.state == EscrowState.REFUNDED


class TestInvalidTransitions:
    def test_cannot_release_from_pending(self) -> None:
        manager = EscrowManager()
        manager.create_escrow(
            "m1", "poster1", Decimal("500"), escrow_id="e1", now=_now()
        )
        with pytest.raises(ValueError, match="Invalid escrow transition"):
            manager.release_escrow("e1", _mock_breakdown(), now=_now())

    def test_cannot_dispute_from_pending(self) -> None:
        manager = EscrowManager()
        manager.create_escrow(
            "m1", "poster1", Decimal("500"), escrow_id="e1", now=_now()
        )
        with pytest.raises(ValueError, match="Invalid escrow transition"):
            manager.dispute_escrow("e1", now=_now())

    def test_cannot_refund_from_released(self) -> None:
        manager = EscrowManager()
        manager.create_escrow(
            "m1", "poster1", Decimal("500"), escrow_id="e1", now=_now()
        )
        manager.lock_escrow("e1", now=_now())
        manager.release_escrow("e1", _mock_breakdown(), now=_now())
        with pytest.raises(ValueError, match="Invalid escrow transition"):
            manager.refund_escrow("e1", now=_now())

    def test_cannot_lock_twice(self) -> None:
        manager = EscrowManager()
        manager.create_escrow(
            "m1", "poster1", Decimal("500"), escrow_id="e1", now=_now()
        )
        manager.lock_escrow("e1", now=_now())
        with pytest.raises(ValueError, match="Invalid escrow transition"):
            manager.lock_escrow("e1", now=_now())

    def test_unknown_escrow_id(self) -> None:
        manager = EscrowManager()
        with pytest.raises(ValueError, match="Unknown escrow ID"):
            manager.lock_escrow("nonexistent", now=_now())


class TestDuplicateEscrowId:
    def test_create_rejects_duplicate_id(self) -> None:
        """Second create with same escrow_id raises ValueError."""
        manager = EscrowManager()
        manager.create_escrow(
            "m1", "poster1", Decimal("500"), escrow_id="e1", now=_now()
        )
        with pytest.raises(ValueError, match="Escrow ID already exists"):
            manager.create_escrow(
                "m2", "poster2", Decimal("300"), escrow_id="e1", now=_now()
            )


class TestBreakdownValidation:
    def test_release_rejects_mismatched_reward(self) -> None:
        """Breakdown for wrong mission amount raises ValueError."""
        manager = EscrowManager()
        manager.create_escrow(
            "m1", "poster1", Decimal("100"), escrow_id="e1", now=_now()
        )
        manager.lock_escrow("e1", now=_now())
        # Breakdown computed for $500, but escrow is $100
        breakdown = _mock_breakdown("500", "0.05")
        with pytest.raises(ValueError, match="does not match escrowed amount"):
            manager.release_escrow("e1", breakdown, now=_now())

    def test_release_rejects_amounts_not_summing(self) -> None:
        """Commission + creator + payout != escrow amount raises ValueError."""
        manager = EscrowManager()
        manager.create_escrow(
            "m1", "poster1", Decimal("500"), escrow_id="e1", now=_now()
        )
        manager.lock_escrow("e1", now=_now())
        # Create a breakdown where mission_reward matches but amounts don't sum
        breakdown = CommissionBreakdown(
            rate=Decimal("0.05"),
            raw_rate=Decimal("0.05"),
            cost_ratio=Decimal("0.04"),
            commission_amount=Decimal("25"),
            creator_allocation=Decimal("10"),
            worker_payout=Decimal("400"),  # 25 + 10 + 400 = 435 ≠ 500
            mission_reward=Decimal("500"),
            cost_breakdown={"infrastructure": Decimal("10")},
            is_bootstrap=False,
            window_stats=WindowStats(
                missions_in_window=60,
                total_completed_missions=100,
                window_days_actual=60,
                window_days_configured=90,
                min_missions_configured=50,
                is_bootstrap=False,
            ),
            reserve_contribution=Decimal("2"),
            safety_margin=Decimal("1.3"),
        )
        with pytest.raises(ValueError, match="does not equal escrowed amount"):
            manager.release_escrow("e1", breakdown, now=_now())


class TestCommissionDeduction:
    def test_commission_deducted_on_release(self) -> None:
        """Worker receives reward minus commission minus creator allocation."""
        manager = EscrowManager()
        manager.create_escrow(
            "m1", "poster1", Decimal("1000"), escrow_id="e1", now=_now()
        )
        manager.lock_escrow("e1", now=_now())
        breakdown = _mock_breakdown("1000", "0.05")
        record, payout = manager.release_escrow("e1", breakdown, now=_now())
        assert payout == Decimal("930")  # 1000 - 50 commission - 20 creator
        assert record.commission_amount == Decimal("50")
