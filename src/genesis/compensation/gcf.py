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


@dataclass(frozen=True)
class GCFDisbursement:
    """A single disbursement from the Genesis Common Fund.

    Records when the commons spends money — proposal-linked, timestamped,
    categorised. Disbursements are immutable once recorded.
    """
    disbursement_id: str
    proposal_id: str
    amount: Decimal
    category: str
    recipient_description: str
    disbursed_utc: datetime


@dataclass
class GCFState:
    """Observable state of the Genesis Common Fund.

    The balance is the sum of all contributions. Individual actor shares
    are architecturally unknowable — no per-actor balance query exists.
    """
    balance: Decimal = Decimal("0")
    total_contributed: Decimal = Decimal("0")
    total_disbursed: Decimal = Decimal("0")
    contribution_count: int = 0
    disbursement_count: int = 0
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
        self._disbursements: list[GCFDisbursement] = []

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

    def record_disbursement(
        self,
        disbursement_id: str,
        proposal_id: str,
        amount: Decimal,
        category: str,
        recipient_description: str,
        now: Optional[datetime] = None,
    ) -> GCFDisbursement:
        """Record a disbursement from the GCF.

        Reduces the fund balance. The GCF must be activated and the
        amount must be positive and not exceed the current balance.

        Args:
            disbursement_id: Unique identifier for this disbursement.
            proposal_id: The approved proposal authorising this spend.
            amount: The disbursement amount.
            category: Disbursement category (e.g. COMPUTE_INFRASTRUCTURE).
            recipient_description: Human-readable description of recipient.
            now: Timestamp (defaults to UTC now).

        Returns:
            The recorded GCFDisbursement.

        Raises:
            ValueError: If GCF is not activated, amount invalid, or
                       amount exceeds balance.
        """
        if not self._state.activated:
            raise ValueError("GCF not yet activated — disbursements require First Light")
        if amount <= Decimal("0"):
            raise ValueError(f"Disbursement amount must be positive, got {amount}")
        if amount > self._state.balance:
            raise ValueError(
                f"Disbursement amount {amount} exceeds GCF balance {self._state.balance}"
            )
        if now is None:
            now = datetime.now(timezone.utc)

        disbursement = GCFDisbursement(
            disbursement_id=disbursement_id,
            proposal_id=proposal_id,
            amount=amount,
            category=category,
            recipient_description=recipient_description,
            disbursed_utc=now,
        )
        self._disbursements.append(disbursement)
        self._state.balance -= amount
        self._state.total_disbursed += amount
        self._state.disbursement_count += 1
        return disbursement

    def credit_refund(
        self,
        amount: Decimal,
        reason: str,
    ) -> None:
        """Credit a refund back to the GCF balance.

        Used when a GCF-funded listing is cancelled — the escrowed funds
        return to the commons. This is NOT a contribution (does not
        increment total_contributed or contribution_count). It is a
        reversal of a prior disbursement.

        Args:
            amount: The refund amount.
            reason: Human-readable reason for the refund.

        Raises:
            ValueError: If GCF is not activated or amount is not positive.
        """
        if not self._state.activated:
            raise ValueError("GCF not yet activated — refunds require First Light")
        if amount <= Decimal("0"):
            raise ValueError(f"Refund amount must be positive, got {amount}")
        self._state.balance += amount
        # Note: total_disbursed is NOT decremented — the disbursement happened,
        # the refund is a separate event. Net spend = total_disbursed - refunds.

    def get_contributions(self) -> list[GCFContribution]:
        """Return all recorded contributions (for audit)."""
        return list(self._contributions)

    def get_disbursements(self) -> list[GCFDisbursement]:
        """Return all recorded disbursements (for audit)."""
        return list(self._disbursements)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize GCF state for persistence."""
        return {
            "balance": str(self._state.balance),
            "total_contributed": str(self._state.total_contributed),
            "total_disbursed": str(self._state.total_disbursed),
            "contribution_count": self._state.contribution_count,
            "disbursement_count": self._state.disbursement_count,
            "activated": self._state.activated,
            "activated_utc": (
                self._state.activated_utc.isoformat()
                if self._state.activated_utc
                else None
            ),
            "contributions": [
                {
                    "amount": str(c.amount),
                    "mission_id": c.mission_id,
                    "contributed_utc": c.contributed_utc.isoformat(),
                }
                for c in self._contributions
            ],
            "disbursements": [
                {
                    "disbursement_id": d.disbursement_id,
                    "proposal_id": d.proposal_id,
                    "amount": str(d.amount),
                    "category": d.category,
                    "recipient_description": d.recipient_description,
                    "disbursed_utc": d.disbursed_utc.isoformat(),
                }
                for d in self._disbursements
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GCFTracker":
        """Reconstruct a GCFTracker from persisted data."""
        tracker = cls()
        tracker._state.balance = Decimal(data["balance"])
        tracker._state.total_contributed = Decimal(data["total_contributed"])
        tracker._state.total_disbursed = Decimal(data["total_disbursed"])
        tracker._state.contribution_count = data["contribution_count"]
        tracker._state.disbursement_count = data["disbursement_count"]
        tracker._state.activated = data["activated"]
        if data.get("activated_utc"):
            tracker._state.activated_utc = datetime.fromisoformat(
                data["activated_utc"]
            )
        tracker._contributions = [
            GCFContribution(
                amount=Decimal(c["amount"]),
                mission_id=c["mission_id"],
                contributed_utc=datetime.fromisoformat(c["contributed_utc"]),
            )
            for c in data.get("contributions", [])
        ]
        tracker._disbursements = [
            GCFDisbursement(
                disbursement_id=d["disbursement_id"],
                proposal_id=d["proposal_id"],
                amount=Decimal(d["amount"]),
                category=d["category"],
                recipient_description=d["recipient_description"],
                disbursed_utc=datetime.fromisoformat(d["disbursed_utc"]),
            )
            for d in data.get("disbursements", [])
        ]
        return tracker
