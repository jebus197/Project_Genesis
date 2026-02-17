"""Genesis Common Fund (GCF) — the constitutional 1% contribution tracker.

The GCF receives 1% of ALL gross transaction value (mission_reward) on every
completed mission. This is constitutionally mandated, inescapable, and
entrenched — changing the rate requires supermajority + high participation
+ cooling-off + confirmation vote.

Key properties:
- Activates automatically at First Light (no human decision).
- Trust-proportional but individually non-extractable — there is NO
  per-actor balance method. The fund is a shared commons.
- The distributed ledger state IS the fund. No bank. No custodian.
- Deducted from worker_payout (after commission and creator allocation).
- Scope: all human activity that doesn't increase net human suffering.

Constitutional invariant:
    commission + creator_allocation + worker_payout + gcf_contribution == mission_reward
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class GCFContribution:
    """A single contribution to the Genesis Common Fund.

    Every contribution is tied to a specific mission and timestamped.
    Contributions are immutable once recorded.
    """
    amount: Decimal
    mission_id: str
    contributed_utc: datetime


@dataclass
class GCFState:
    """Observable state of the Genesis Common Fund.

    The balance is the sum of all contributions. Individual actor shares
    are architecturally unknowable — no per-actor balance query exists.
    """
    balance: Decimal = Decimal("0")
    total_contributed: Decimal = Decimal("0")
    contribution_count: int = 0
    activated: bool = False
    activated_utc: Optional[datetime] = None


class GCFTracker:
    """Tracks GCF contributions and activation state.

    The GCF activates automatically at First Light. Once activated,
    every completed mission contributes 1% of mission_reward.

    There is deliberately NO method to query per-actor balance.
    The fund is a shared commons — individually non-extractable.

    Usage:
        tracker = GCFTracker()

        # At First Light:
        tracker.activate(now)

        # On each mission payment:
        if tracker.is_active:
            contribution = tracker.record_contribution(
                amount=gcf_amount,
                mission_id="m_123",
                now=now,
            )
    """

    def __init__(self) -> None:
        self._state = GCFState()
        self._contributions: list[GCFContribution] = []

    @property
    def is_active(self) -> bool:
        """Whether the GCF has been activated (First Light fired)."""
        return self._state.activated

    def activate(self, now: Optional[datetime] = None) -> None:
        """Activate the GCF. Called exactly once at First Light.

        Raises ValueError if already activated (idempotency protection).
        """
        if self._state.activated:
            raise ValueError("GCF already activated")
        if now is None:
            now = datetime.now(timezone.utc)
        self._state.activated = True
        self._state.activated_utc = now

    def record_contribution(
        self,
        amount: Decimal,
        mission_id: str,
        now: Optional[datetime] = None,
    ) -> GCFContribution:
        """Record a contribution to the GCF.

        Args:
            amount: The contribution amount (1% of mission_reward).
            mission_id: The mission that generated this contribution.
            now: Timestamp (defaults to UTC now).

        Returns:
            The recorded GCFContribution.

        Raises:
            ValueError: If GCF is not yet activated.
            ValueError: If amount is not positive.
        """
        if not self._state.activated:
            raise ValueError("GCF not yet activated — contributions require First Light")
        if amount <= Decimal("0"):
            raise ValueError(f"GCF contribution must be positive, got {amount}")
        if now is None:
            now = datetime.now(timezone.utc)

        contribution = GCFContribution(
            amount=amount,
            mission_id=mission_id,
            contributed_utc=now,
        )
        self._contributions.append(contribution)
        self._state.balance += amount
        self._state.total_contributed += amount
        self._state.contribution_count += 1
        return contribution

    def get_state(self) -> GCFState:
        """Return the current observable GCF state.

        Returns a snapshot — the state object is mutable internally
        but callers should treat the returned object as read-only.
        """
        return self._state

    def get_contributions(self) -> list[GCFContribution]:
        """Return all recorded contributions (for audit)."""
        return list(self._contributions)
