"""Escrow manager — manages the escrow lifecycle for mission payments.

Before any mission begins, the work poster must stake the full reward
amount into escrow. The listing does not go live until escrow is confirmed.
This eliminates "work done, never paid" by structural design.

The escrow manager is a pure state machine — no side effects. Event
logging is handled by the service layer.

State machine:
    PENDING → LOCKED        (listing goes live)
    LOCKED → RELEASING      (work approved, commission computed)
    RELEASING → RELEASED    (worker paid)
    LOCKED → DISPUTED       (payment dispute initiated)
    LOCKED → REFUNDED       (mission cancelled)
    DISPUTED → RELEASED     (dispute resolved, worker paid)
    DISPUTED → REFUNDED     (dispute resolved, poster refunded)
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional, Tuple
from uuid import uuid4

from genesis.models.compensation import (
    CommissionBreakdown,
    EscrowRecord,
    EscrowState,
)


class EscrowManager:
    """Manages escrow records for mission payments.

    Usage:
        manager = EscrowManager()
        record = manager.create_escrow("mission_1", "poster_1", Decimal("500.00"))
        record = manager.lock_escrow(record.escrow_id)
        record, worker_payout = manager.release_escrow(
            record.escrow_id, commission_breakdown
        )
    """

    def __init__(self) -> None:
        self._escrows: Dict[str, EscrowRecord] = {}

    def create_escrow(
        self,
        mission_id: str,
        staker_id: str,
        amount: Decimal,
        escrow_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> EscrowRecord:
        """Create a new escrow record in PENDING state.

        Args:
            mission_id: The mission this escrow funds.
            staker_id: The actor staking the funds.
            amount: The full reward amount to stake.
            escrow_id: Optional explicit ID (auto-generated if absent).
            now: Current time (defaults to UTC now).

        Returns:
            The created EscrowRecord.
        """
        if amount <= Decimal("0"):
            raise ValueError("Escrow amount must be positive")
        if now is None:
            now = datetime.now(timezone.utc)
        if escrow_id is None:
            escrow_id = f"escrow_{uuid4().hex[:12]}"

        record = EscrowRecord(
            escrow_id=escrow_id,
            mission_id=mission_id,
            staker_id=staker_id,
            amount=amount,
            state=EscrowState.PENDING,
            created_utc=now,
        )
        self._escrows[escrow_id] = record
        return record

    def lock_escrow(
        self,
        escrow_id: str,
        now: Optional[datetime] = None,
    ) -> EscrowRecord:
        """Lock escrow — listing goes live.

        Transitions: PENDING → LOCKED
        """
        record = self._get(escrow_id)
        if now is None:
            now = datetime.now(timezone.utc)
        record.transition_to(EscrowState.LOCKED)
        record.locked_utc = now
        return record

    def release_escrow(
        self,
        escrow_id: str,
        commission: CommissionBreakdown,
        now: Optional[datetime] = None,
    ) -> Tuple[EscrowRecord, Decimal]:
        """Release escrow — commission deducted, worker paid.

        Transitions: LOCKED → RELEASING → RELEASED
                     or DISPUTED → RELEASED

        Returns:
            Tuple of (updated record, worker payout amount).
        """
        record = self._get(escrow_id)
        if now is None:
            now = datetime.now(timezone.utc)

        if record.state == EscrowState.LOCKED:
            record.transition_to(EscrowState.RELEASING)
            record.transition_to(EscrowState.RELEASED)
        elif record.state == EscrowState.DISPUTED:
            record.transition_to(EscrowState.RELEASED)
        else:
            # Let transition_to raise the proper error
            record.transition_to(EscrowState.RELEASING)

        record.released_utc = now
        record.commission_amount = commission.commission_amount
        record.worker_payout = commission.worker_payout

        return record, commission.worker_payout

    def refund_escrow(
        self,
        escrow_id: str,
        now: Optional[datetime] = None,
    ) -> EscrowRecord:
        """Refund escrow — mission cancelled or dispute resolved for poster.

        Transitions: LOCKED → REFUNDED
                     or DISPUTED → REFUNDED
        """
        record = self._get(escrow_id)
        if now is None:
            now = datetime.now(timezone.utc)
        record.transition_to(EscrowState.REFUNDED)
        record.refunded_utc = now
        return record

    def dispute_escrow(
        self,
        escrow_id: str,
        now: Optional[datetime] = None,
    ) -> EscrowRecord:
        """Mark escrow as disputed — payment dispute initiated.

        Transitions: LOCKED → DISPUTED
        """
        record = self._get(escrow_id)
        if now is None:
            now = datetime.now(timezone.utc)
        record.transition_to(EscrowState.DISPUTED)
        record.disputed_utc = now
        return record

    def get_escrow(self, escrow_id: str) -> EscrowRecord:
        """Get an escrow record by ID."""
        return self._get(escrow_id)

    def _get(self, escrow_id: str) -> EscrowRecord:
        """Internal lookup with clear error on missing ID."""
        record = self._escrows.get(escrow_id)
        if record is None:
            raise ValueError(f"Unknown escrow ID: {escrow_id}")
        return record
