"""Compensation models — escrow, commission, operational costs, and reserve fund.

All monetary values use Decimal for exact arithmetic. No floats in finance.

Constitutional invariants enforced by these models:
- Commission rate bounded by [FLOOR, CEILING]
- Every commission produces a published cost breakdown
- Escrow lifecycle is a strict state machine (no skipped states)
- Reserve fund state is observable and auditable
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional


class CostCategory(str, enum.Enum):
    """Classification of operational costs.

    Each category maps to a line item in the published commission breakdown.
    """
    INFRASTRUCTURE = "infrastructure"
    GAS = "gas"
    LEGAL = "legal"
    ADJUDICATOR = "adjudicator"
    RESERVE_GAP = "reserve_gap"
    RESERVE_MAINTENANCE = "reserve_maintenance"
    CREATOR_ALLOCATION = "creator_allocation"


class EscrowState(str, enum.Enum):
    """Lifecycle state of an escrow record.

    State machine:
        PENDING → LOCKED → RELEASED
        PENDING → LOCKED → REFUNDED
        PENDING → LOCKED → DISPUTED → RELEASED
        PENDING → LOCKED → DISPUTED → REFUNDED
    """
    PENDING = "pending"
    LOCKED = "locked"
    RELEASING = "releasing"
    RELEASED = "released"
    DISPUTED = "disputed"
    REFUNDED = "refunded"


# Valid escrow state transitions
ESCROW_TRANSITIONS: Dict[EscrowState, frozenset] = {
    EscrowState.PENDING: frozenset({EscrowState.LOCKED}),
    EscrowState.LOCKED: frozenset({
        EscrowState.RELEASING,
        EscrowState.DISPUTED,
        EscrowState.REFUNDED,
    }),
    EscrowState.RELEASING: frozenset({EscrowState.RELEASED}),
    EscrowState.DISPUTED: frozenset({
        EscrowState.RELEASED,
        EscrowState.REFUNDED,
    }),
    EscrowState.RELEASED: frozenset(),
    EscrowState.REFUNDED: frozenset(),
}


@dataclass(frozen=True)
class OperationalCostEntry:
    """A single auditable operational cost.

    Every cost entry maps to a line in the published commission breakdown.
    """
    cost_id: str
    category: CostCategory
    amount: Decimal
    timestamp_utc: datetime
    description: str


@dataclass(frozen=True)
class CompletedMission:
    """A completed mission record for rolling window computation.

    Contains only the fields needed for commission calculation —
    the full mission model lives in genesis.models.mission.
    """
    mission_id: str
    reward_amount: Decimal
    completed_utc: datetime
    operational_costs: Decimal


@dataclass(frozen=True)
class WindowStats:
    """Statistics about the rolling window used for rate computation."""
    missions_in_window: int
    total_completed_missions: int
    window_days_actual: int
    window_days_configured: int
    min_missions_configured: int
    is_bootstrap: bool


@dataclass(frozen=True)
class CommissionBreakdown:
    """Full breakdown of a commission computation.

    Published with every transaction — there is nowhere for
    profit extraction to hide.

    Invariant: commission_amount + creator_allocation + worker_payout == mission_reward
    """
    rate: Decimal
    raw_rate: Decimal
    cost_ratio: Decimal
    commission_amount: Decimal
    creator_allocation: Decimal
    worker_payout: Decimal
    mission_reward: Decimal
    cost_breakdown: Dict[str, Decimal]
    is_bootstrap: bool
    window_stats: WindowStats
    reserve_contribution: Decimal
    safety_margin: Decimal


@dataclass(frozen=True)
class ReserveFundState:
    """Observable state of the reserve fund.

    The reserve is self-managing: when below target, gap contribution
    is added to operational costs (rate rises). When at target,
    maintenance only (rate falls). No vote. No review.
    """
    balance: Decimal
    target: Decimal
    gap: Decimal
    is_below_target: bool

    @staticmethod
    def compute(
        balance: Decimal,
        rolling_monthly_ops: Decimal,
        target_months: int,
    ) -> ReserveFundState:
        """Compute reserve state from current balance and rolling costs."""
        target = rolling_monthly_ops * Decimal(str(target_months))
        gap = max(Decimal("0"), target - balance)
        return ReserveFundState(
            balance=balance,
            target=target,
            gap=gap,
            is_below_target=balance < target,
        )


@dataclass
class EscrowRecord:
    """An escrow record tracking staked funds for a mission.

    Mutable — state transitions happen during the mission lifecycle.
    All transitions are validated against the ESCROW_TRANSITIONS map.
    """
    escrow_id: str
    mission_id: str
    staker_id: str
    amount: Decimal
    state: EscrowState = EscrowState.PENDING
    created_utc: Optional[datetime] = None
    locked_utc: Optional[datetime] = None
    released_utc: Optional[datetime] = None
    disputed_utc: Optional[datetime] = None
    refunded_utc: Optional[datetime] = None
    commission_amount: Optional[Decimal] = None
    worker_payout: Optional[Decimal] = None

    def transition_to(self, new_state: EscrowState) -> None:
        """Transition to a new state, validating the transition is legal."""
        allowed = ESCROW_TRANSITIONS.get(self.state, frozenset())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid escrow transition: {self.state.value} → {new_state.value}. "
                f"Allowed: {', '.join(s.value for s in allowed)}"
            )
        self.state = new_state
