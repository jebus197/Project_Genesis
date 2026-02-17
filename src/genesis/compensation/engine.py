"""Commission engine — computes the real-time dynamic commission rate.

The commission rate is computed per-transaction using a rolling window
of operational data. The formula is fully deterministic:

    cost_ratio = rolling_operational_costs / rolling_completed_mission_value
    raw_rate = cost_ratio × SAFETY_MARGIN
    rate = clamp(raw_rate, FLOOR, CEILING)
    commission = max(rate × mission_reward, MIN_FEE)

Both-sides creator allocation (5%):
    worker_side = (mission_reward - commission) × 0.05
    employer_side = mission_reward × 0.05
    total_escrow = mission_reward + employer_side

No human votes on the rate. No ballot sets the margin. The formula IS the rate.

Constitutional invariants:
- Rate is always in [COMMISSION_FLOOR, COMMISSION_CEILING]
- Every computation produces a full published breakdown
- Bootstrap mode applies BOOTSTRAP_MIN_RATE when < MIN_MISSIONS completed
- Reserve fund is self-managing (gap contribution raises rate automatically)
- commission + creator_allocation + worker_payout + gcf_contribution == mission_reward
- total_escrow == mission_reward + employer_creator_fee
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from genesis.compensation.ledger import OperationalLedger
from genesis.models.compensation import (
    CommissionBreakdown,
    CostCategory,
    ReserveFundState,
    WindowStats,
)
from genesis.policy.resolver import PolicyResolver


class CommissionEngine:
    """Computes the real-time dynamic commission for each transaction.

    Usage:
        engine = CommissionEngine(resolver)
        breakdown = engine.compute_commission(
            mission_reward=Decimal("500.00"),
            ledger=ledger,
            reserve=reserve_state,
        )
    """

    def __init__(self, resolver: PolicyResolver) -> None:
        self._resolver = resolver

    def compute_commission(
        self,
        mission_reward: Decimal,
        ledger: OperationalLedger,
        reserve: ReserveFundState,
        now: Optional[datetime] = None,
    ) -> CommissionBreakdown:
        """Compute the full commission breakdown for a mission payout.

        Args:
            mission_reward: The total mission reward amount.
            ledger: The operational ledger with historical data.
            reserve: Current reserve fund state.
            now: Current time (defaults to UTC now).

        Returns:
            A frozen CommissionBreakdown with rate, amounts, and full
            cost breakdown. Published with every transaction.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        params = self._resolver.commission_params()
        floor = params["commission_floor"]
        ceiling = params["commission_ceiling"]
        safety_margin = params["commission_safety_margin"]
        min_fee = params["commission_min_fee_usdc"]
        window_days = int(params["commission_window_days"])
        min_missions = int(params["commission_window_min_missions"])
        bootstrap_min_rate = params["commission_bootstrap_min_rate"]
        reserve_maintenance = params["commission_reserve_maintenance_rate"]

        # Get rolling window data
        window_missions = ledger.missions_in_window(window_days, min_missions, now)
        window_costs = ledger.costs_in_window(window_days, min_missions, now)
        total_completed = ledger.total_completed_missions()
        is_bootstrap = total_completed < min_missions

        # Compute window span in days
        if window_missions:
            earliest = min(m.completed_utc for m in window_missions)
            window_days_actual = max(1, (now - earliest).days)
        else:
            window_days_actual = 0

        window_stats = WindowStats(
            missions_in_window=len(window_missions),
            total_completed_missions=total_completed,
            window_days_actual=window_days_actual,
            window_days_configured=window_days,
            min_missions_configured=min_missions,
            is_bootstrap=is_bootstrap,
        )

        # Rolling totals
        rolling_mission_value = sum(
            (m.reward_amount for m in window_missions), Decimal("0")
        )
        rolling_ops_costs = sum(
            (c.amount for c in window_costs), Decimal("0")
        )

        # Reserve contribution
        reserve_contribution = self._reserve_contribution(
            reserve, rolling_ops_costs, window_days_actual,
            reserve_maintenance, params["commission_reserve_target_months"],
        )
        # Add reserve contribution to operational costs for rate computation
        rolling_ops_costs_with_reserve = rolling_ops_costs + reserve_contribution

        # Cost ratio
        if rolling_mission_value > Decimal("0"):
            cost_ratio = rolling_ops_costs_with_reserve / rolling_mission_value
        else:
            # No completed missions in window — use ceiling
            cost_ratio = ceiling / safety_margin

        # Raw rate
        raw_rate = cost_ratio * safety_margin

        # Apply bootstrap minimum if applicable
        if is_bootstrap:
            raw_rate = max(raw_rate, bootstrap_min_rate)

        # Clamp to constitutional bounds
        rate = max(floor, min(ceiling, raw_rate))

        # Commission amount (with minimum fee enforcement)
        commission_amount = max(
            rate * mission_reward,
            min_fee,
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Cannot exceed the mission reward
        commission_amount = min(commission_amount, mission_reward)

        # --- Both-sides creator allocation (constitutional) ---
        #
        # Worker-side: 5% of worker's payment (after commission, before creator).
        #   worker_payout_before_creator = mission_reward - commission
        #   creator_allocation = worker_payout_before_creator × creator_rate
        #   worker_payout = worker_payout_before_creator - creator_allocation
        #
        # Employer-side: 5% of mission_reward, staked on top in escrow.
        #   employer_creator_fee = mission_reward × employer_fee_rate
        #   Total escrow = mission_reward + employer_creator_fee
        #   Returned in full on cancel/refund.
        #
        # To each party it reads as "5% creator allocation".
        # Invariant: commission + creator_allocation + worker_payout + gcf_contribution == mission_reward
        # Invariant: total_escrow == mission_reward + employer_creator_fee

        creator_rate = params.get("creator_allocation_rate", Decimal("0"))
        employer_fee_rate = params.get("employer_creator_fee_rate", Decimal("0"))

        worker_payout_before_creator = mission_reward - commission_amount

        if creator_rate > Decimal("0") and worker_payout_before_creator > Decimal("0"):
            creator_amount = (worker_payout_before_creator * creator_rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP,
            )
        else:
            creator_amount = Decimal("0")

        worker_payout = worker_payout_before_creator - creator_amount

        if employer_fee_rate > Decimal("0") and mission_reward > Decimal("0"):
            employer_creator_fee = (mission_reward * employer_fee_rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP,
            )
        else:
            employer_creator_fee = Decimal("0")

        # --- Genesis Common Fund (GCF) contribution (constitutional) ---
        #
        # 1% of mission_reward, deducted from worker_payout AFTER commission
        # and creator allocation. The GCF rate is entrenched — changing it
        # requires supermajority + high participation + cooling-off +
        # confirmation vote.
        #
        # Invariant: commission + creator + worker + gcf == mission_reward

        gcf_rate = params.get("gcf_contribution_rate", Decimal("0"))
        if gcf_rate > Decimal("0") and mission_reward > Decimal("0"):
            gcf_contribution = (mission_reward * gcf_rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP,
            )
        else:
            gcf_contribution = Decimal("0")

        # Deduct GCF from worker payout
        worker_payout = worker_payout - gcf_contribution

        # Build cost breakdown by category
        cost_breakdown = self._build_cost_breakdown(window_costs, reserve_contribution)
        if creator_amount > Decimal("0"):
            cost_breakdown["creator_allocation"] = creator_amount
        if employer_creator_fee > Decimal("0"):
            cost_breakdown["employer_creator_fee"] = employer_creator_fee
        if gcf_contribution > Decimal("0"):
            cost_breakdown["gcf_contribution"] = gcf_contribution

        return CommissionBreakdown(
            rate=rate,
            raw_rate=raw_rate,
            cost_ratio=cost_ratio,
            commission_amount=commission_amount,
            creator_allocation=creator_amount,
            employer_creator_fee=employer_creator_fee,
            worker_payout=worker_payout,
            mission_reward=mission_reward,
            cost_breakdown=cost_breakdown,
            is_bootstrap=is_bootstrap,
            window_stats=window_stats,
            reserve_contribution=reserve_contribution,
            safety_margin=safety_margin,
            gcf_contribution=gcf_contribution,
        )

    def _reserve_contribution(
        self,
        reserve: ReserveFundState,
        rolling_ops_costs: Decimal,
        window_days_actual: int,
        maintenance_rate: Decimal,
        target_months: Decimal,
    ) -> Decimal:
        """Compute the reserve fund contribution for this window.

        When below target: gap contribution added proportionally.
        When at target: maintenance only (RESERVE_MAINTENANCE_RATE of ops).
        """
        if not reserve.is_below_target:
            # At or above target — maintenance only
            return rolling_ops_costs * maintenance_rate

        # Below target — add gap contribution proportionally
        # Spread the gap over target_months worth of expected operations
        if window_days_actual > 0:
            monthly_ops = rolling_ops_costs * Decimal("30") / Decimal(str(window_days_actual))
        else:
            monthly_ops = Decimal("0")

        if monthly_ops > Decimal("0"):
            months_to_fill = reserve.gap / monthly_ops
            # Spread gap contribution over the gap-fill period, capped at target_months
            effective_months = min(months_to_fill, target_months)
            if effective_months > Decimal("0"):
                return reserve.gap / effective_months
        return Decimal("0")

    def _build_cost_breakdown(
        self,
        window_costs: list,
        reserve_contribution: Decimal,
    ) -> dict:
        """Build the published cost breakdown by category."""
        breakdown: dict = {}
        for cost in window_costs:
            cat = cost.category.value
            breakdown[cat] = breakdown.get(cat, Decimal("0")) + cost.amount

        # Add reserve contribution
        if reserve_contribution > Decimal("0"):
            breakdown["reserve"] = reserve_contribution

        return breakdown
