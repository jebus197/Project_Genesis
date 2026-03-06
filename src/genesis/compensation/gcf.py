"""Genesis Common Fund (GCF) — the constitutional 1% contribution tracker.

The GCF receives 1% of ALL gross transaction value (mission_reward) on every
completed mission. This is constitutionally mandated, inescapable, and
entrenched — changing the rate requires supermajority + high participation
+ cooling-off + confirmation vote.

Key properties:
- Activates automatically at First Light (no human decision).
- Trust-proportional but individually non-extractable — there is NO
  per-actor balance method. The fund is a shared commons.
- The fund is an accounting identity:
      balance = total_contributed - total_disbursed + total_refunded
  Derived from three immutable record lists. Not a pool, not a vault.
  No bank. No custodian. Every term maps to auditable records.
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


@dataclass(frozen=True)
class GCFRefund:
    """A single refund credited back to the Genesis Common Fund.

    Recorded when a GCF-funded listing is cancelled and escrowed funds
    return to the commons. This is NOT a contribution (no new money in)
    and NOT a disbursement reversal (the disbursement happened). It is a
    separate, auditable event: funds returning from a cancelled operation.
    """
    amount: Decimal
    reason: str
    refunded_utc: datetime


@dataclass
class GCFState:
    """Observable state of the Genesis Common Fund.

    The balance is a derived accounting identity:
        balance = total_contributed - total_disbursed + total_refunded

    Three terms, three immutable record lists, one verifiable invariant.
    Individual actor shares are architecturally unknowable — no per-actor
    balance query exists.
    """
    balance: Decimal = Decimal("0")
    total_contributed: Decimal = Decimal("0")
    total_disbursed: Decimal = Decimal("0")
    total_refunded: Decimal = Decimal("0")
    contribution_count: int = 0
    disbursement_count: int = 0
    refund_count: int = 0
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
        self._refunds: list[GCFRefund] = []

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

        Returns a COPY — mutations to the returned object cannot
        corrupt internal state. The internal accounting identity
        (balance = contributed - disbursed + refunded) is protected.
        """
        return GCFState(
            balance=self._state.balance,
            total_contributed=self._state.total_contributed,
            total_disbursed=self._state.total_disbursed,
            total_refunded=self._state.total_refunded,
            contribution_count=self._state.contribution_count,
            disbursement_count=self._state.disbursement_count,
            refund_count=self._state.refund_count,
            activated=self._state.activated,
            activated_utc=self._state.activated_utc,
        )

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
        now: Optional[datetime] = None,
    ) -> GCFRefund:
        """Credit a refund back to the GCF balance.

        Used when a GCF-funded listing is cancelled — the escrowed funds
        return to the commons. This is NOT a contribution (does not
        increment total_contributed or contribution_count). It is a
        separate, auditable event: funds returning from a cancelled operation.

        The accounting identity after a refund:
            balance = total_contributed - total_disbursed + total_refunded

        Args:
            amount: The refund amount.
            reason: Human-readable reason for the refund.
            now: Timestamp (defaults to UTC now).

        Returns:
            The recorded GCFRefund.

        Raises:
            ValueError: If GCF is not activated, amount is not positive,
                       or refund would exceed net disbursed amount.
        """
        if not self._state.activated:
            raise ValueError("GCF not yet activated — refunds require First Light")
        if amount <= Decimal("0"):
            raise ValueError(f"Refund amount must be positive, got {amount}")
        net_disbursed = self._state.total_disbursed - self._state.total_refunded
        if amount > net_disbursed:
            raise ValueError(
                f"Refund amount {amount} exceeds net disbursed {net_disbursed} "
                f"(total_disbursed={self._state.total_disbursed}, "
                f"total_refunded={self._state.total_refunded}). "
                f"Cannot refund money that was never disbursed."
            )
        if now is None:
            now = datetime.now(timezone.utc)

        refund = GCFRefund(
            amount=amount,
            reason=reason,
            refunded_utc=now,
        )
        self._refunds.append(refund)
        self._state.balance += amount
        self._state.total_refunded += amount
        self._state.refund_count += 1
        return refund

    def get_contributions(self) -> list[GCFContribution]:
        """Return all recorded contributions (for audit)."""
        return list(self._contributions)

    def get_disbursements(self) -> list[GCFDisbursement]:
        """Return all recorded disbursements (for audit)."""
        return list(self._disbursements)

    def get_refunds(self) -> list[GCFRefund]:
        """Return all recorded refunds (for audit)."""
        return list(self._refunds)

    def verify_accounting_identity(self) -> bool:
        """Verify that balance == contributed - disbursed + refunded.

        Returns True if the identity holds. This is the fundamental
        falsification target for GCF integrity: if this returns False,
        something has corrupted the fund state.
        """
        expected = (
            self._state.total_contributed
            - self._state.total_disbursed
            + self._state.total_refunded
        )
        return self._state.balance == expected

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize GCF state for persistence."""
        return {
            "balance": str(self._state.balance),
            "total_contributed": str(self._state.total_contributed),
            "total_disbursed": str(self._state.total_disbursed),
            "total_refunded": str(self._state.total_refunded),
            "contribution_count": self._state.contribution_count,
            "disbursement_count": self._state.disbursement_count,
            "refund_count": self._state.refund_count,
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
            "refunds": [
                {
                    "amount": str(r.amount),
                    "reason": r.reason,
                    "refunded_utc": r.refunded_utc.isoformat(),
                }
                for r in self._refunds
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GCFTracker":
        """Reconstruct a GCFTracker from persisted data.

        After loading all three record lists, re-derives the balance from
        the records and asserts it matches the stored balance. If it
        doesn't, the persisted data has been tampered with or corrupted.

        Raises:
            ValueError: If the stored balance doesn't match the derived
                       balance (integrity violation).
        """
        tracker = cls()
        tracker._state.balance = Decimal(data["balance"])
        tracker._state.total_contributed = Decimal(data["total_contributed"])
        tracker._state.total_disbursed = Decimal(data["total_disbursed"])
        tracker._state.total_refunded = Decimal(data.get("total_refunded", "0"))
        tracker._state.contribution_count = data["contribution_count"]
        tracker._state.disbursement_count = data["disbursement_count"]
        tracker._state.refund_count = data.get("refund_count", 0)
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
        tracker._refunds = [
            GCFRefund(
                amount=Decimal(r["amount"]),
                reason=r["reason"],
                refunded_utc=datetime.fromisoformat(r["refunded_utc"]),
            )
            for r in data.get("refunds", [])
        ]

        # P4 integrity check: re-derive ALL fields from record lists.
        # Catches balance tampering, total tampering, and count tampering.
        derived_contributed = sum(
            (c.amount for c in tracker._contributions), Decimal("0")
        )
        derived_disbursed = sum(
            (d.amount for d in tracker._disbursements), Decimal("0")
        )
        derived_refunded = sum(
            (r.amount for r in tracker._refunds), Decimal("0")
        )
        derived_balance = derived_contributed - derived_disbursed + derived_refunded

        if derived_balance != tracker._state.balance:
            raise ValueError(
                f"GCF integrity violation on recovery: stored balance "
                f"{tracker._state.balance} != derived balance {derived_balance} "
                f"(contributed={derived_contributed}, disbursed={derived_disbursed}, "
                f"refunded={derived_refunded})"
            )

        # Cross-verify totals against record sums
        if derived_contributed != tracker._state.total_contributed:
            raise ValueError(
                f"GCF integrity violation: stored total_contributed "
                f"{tracker._state.total_contributed} != derived {derived_contributed}"
            )
        if derived_disbursed != tracker._state.total_disbursed:
            raise ValueError(
                f"GCF integrity violation: stored total_disbursed "
                f"{tracker._state.total_disbursed} != derived {derived_disbursed}"
            )
        if derived_refunded != tracker._state.total_refunded:
            raise ValueError(
                f"GCF integrity violation: stored total_refunded "
                f"{tracker._state.total_refunded} != derived {derived_refunded}"
            )

        # Cross-verify counts against list lengths
        if len(tracker._contributions) != tracker._state.contribution_count:
            raise ValueError(
                f"GCF integrity violation: stored contribution_count "
                f"{tracker._state.contribution_count} != actual "
                f"{len(tracker._contributions)}"
            )
        if len(tracker._disbursements) != tracker._state.disbursement_count:
            raise ValueError(
                f"GCF integrity violation: stored disbursement_count "
                f"{tracker._state.disbursement_count} != actual "
                f"{len(tracker._disbursements)}"
            )
        if len(tracker._refunds) != tracker._state.refund_count:
            raise ValueError(
                f"GCF integrity violation: stored refund_count "
                f"{tracker._state.refund_count} != actual "
                f"{len(tracker._refunds)}"
            )

        return tracker
