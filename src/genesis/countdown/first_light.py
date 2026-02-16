"""First Light sustainability estimator.

Computes a projected date for First Light — the moment Genesis becomes
financially self-sustaining. First Light fires when BOTH conditions are met:

1. Projected monthly commission revenue >= sustainability_ratio * monthly costs
2. Reserve fund balance >= reserve_months_required * monthly costs

The projection uses a 3-layer model:
  Layer 1: Signup velocity (EMA with mild network-effect prior)
  Layer 2: Mission volume projection (missions/human/month * projected humans)
  Layer 3: Revenue vs costs (projected revenue vs actual operating costs)

Constitutional reference: TRUST_CONSTITUTION.md, "First Light" section.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import log, sqrt
from typing import Optional


@dataclass(frozen=True)
class FirstLightEstimate:
    """Result of a First Light sustainability projection."""

    # Current state
    current_humans: int
    current_monthly_revenue: Decimal
    current_monthly_costs: Decimal
    current_sustainability_ratio: float  # revenue / costs (0 if no costs)
    reserve_balance: Decimal
    reserve_target_3mo: Decimal  # reserve_months_required * monthly costs

    # Projections
    projected_sustainability_date: Optional[datetime]
    projected_reserve_date: Optional[datetime]
    estimated_first_light: Optional[datetime]  # later of the two
    optimistic_date: Optional[datetime]
    pessimistic_date: Optional[datetime]

    # Display
    progress_pct: float  # 0-100 composite progress
    sufficient_data: bool
    message: str
    achieved: bool


class FirstLightEstimator:
    """Projects when Genesis will achieve financial sustainability.

    Uses real signup velocity and mission economics to estimate
    when commission revenue will cover operating costs with a
    safety buffer, and when the reserve fund will reach its target.
    """

    def __init__(
        self,
        sustainability_ratio: float = 1.5,
        reserve_months_required: int = 3,
        ema_alpha: float = 0.3,
        network_beta: float = 0.15,
        confidence_sigma: float = 1.0,
        min_data_points: int = 3,
        min_rate_floor: float = 0.01,
    ) -> None:
        self._sustainability_ratio = sustainability_ratio
        self._reserve_months = reserve_months_required
        self._alpha = ema_alpha
        self._beta = network_beta
        self._sigma = confidence_sigma
        self._min_points = min_data_points
        self._min_rate = min_rate_floor

    def estimate(
        self,
        human_registration_timestamps: list[datetime],
        monthly_revenue: Decimal = Decimal("0"),
        monthly_costs: Decimal = Decimal("0"),
        reserve_balance: Decimal = Decimal("0"),
        missions_per_human_per_month: float = 0.0,
        avg_mission_value: Decimal = Decimal("0"),
        commission_rate: Decimal = Decimal("0.05"),
        now: Optional[datetime] = None,
    ) -> FirstLightEstimate:
        """Produce a First Light sustainability estimate.

        Args:
            human_registration_timestamps: UTC timestamps of verified
                human registrations, in chronological order.
            monthly_revenue: Actual commission revenue in last 30 days.
            monthly_costs: Actual operating costs in last 30 days.
            reserve_balance: Current reserve fund balance.
            missions_per_human_per_month: Rolling average missions per
                human per month (from actual data).
            avg_mission_value: Rolling average mission reward value.
            commission_rate: Current commission rate (from engine).
            now: Current time (defaults to utcnow).
        """
        now = now or datetime.now(timezone.utc)
        n = len(human_registration_timestamps)

        # Compute current sustainability metrics
        if monthly_costs > 0:
            sustainability_ratio = float(monthly_revenue / monthly_costs)
        else:
            sustainability_ratio = 0.0

        reserve_target = Decimal(str(self._reserve_months)) * monthly_costs

        # Check if already achieved
        revenue_met = (
            monthly_costs > 0
            and float(monthly_revenue) >= self._sustainability_ratio * float(monthly_costs)
        )
        reserve_met = (
            monthly_costs > 0
            and reserve_balance >= reserve_target
        )

        if revenue_met and reserve_met:
            return FirstLightEstimate(
                current_humans=n,
                current_monthly_revenue=monthly_revenue,
                current_monthly_costs=monthly_costs,
                current_sustainability_ratio=sustainability_ratio,
                reserve_balance=reserve_balance,
                reserve_target_3mo=reserve_target,
                projected_sustainability_date=None,
                projected_reserve_date=None,
                estimated_first_light=None,
                optimistic_date=None,
                pessimistic_date=None,
                progress_pct=100.0,
                sufficient_data=True,
                message="First Light has been achieved.",
                achieved=True,
            )

        # Not enough data to project
        if n < self._min_points:
            return FirstLightEstimate(
                current_humans=n,
                current_monthly_revenue=monthly_revenue,
                current_monthly_costs=monthly_costs,
                current_sustainability_ratio=sustainability_ratio,
                reserve_balance=reserve_balance,
                reserve_target_3mo=reserve_target,
                projected_sustainability_date=None,
                projected_reserve_date=None,
                estimated_first_light=None,
                optimistic_date=None,
                pessimistic_date=None,
                progress_pct=self._compute_progress(
                    sustainability_ratio, reserve_balance, reserve_target,
                ),
                sufficient_data=False,
                message=(
                    f"{n} verified humans registered. "
                    f"Not enough activity to project First Light."
                ),
                achieved=False,
            )

        # Layer 1: Signup velocity (EMA + network effect)
        sorted_ts = sorted(human_registration_timestamps)
        rates = []
        for i in range(len(sorted_ts) - 1):
            delta_days = (sorted_ts[i + 1] - sorted_ts[i]).total_seconds() / 86400.0
            if delta_days > 0:
                rates.append(1.0 / delta_days)
            else:
                rates.append(1.0 / 0.001)

        # EMA of signup rate
        smoothed = rates[0]
        for r in rates[1:]:
            smoothed = self._alpha * r + (1 - self._alpha) * smoothed

        # Network-effect adjustment
        multiplier = 1.0 + self._beta * log(max(n, 1))
        adjusted_signup_rate = max(smoothed * multiplier, self._min_rate)

        # Variance for confidence band
        if len(rates) >= 2:
            ema_var = 0.0
            ema_mean = rates[0]
            for r in rates[1:]:
                ema_mean = self._alpha * r + (1 - self._alpha) * ema_mean
                diff = r - ema_mean
                ema_var = self._alpha * (diff * diff) + (1 - self._alpha) * ema_var
            std = sqrt(max(ema_var, 0.0))
        else:
            std = smoothed * 0.5

        # Can we project financials?
        has_mission_data = missions_per_human_per_month > 0 and avg_mission_value > 0

        if not has_mission_data:
            # No mission data yet — show signup velocity only
            return FirstLightEstimate(
                current_humans=n,
                current_monthly_revenue=monthly_revenue,
                current_monthly_costs=monthly_costs,
                current_sustainability_ratio=sustainability_ratio,
                reserve_balance=reserve_balance,
                reserve_target_3mo=reserve_target,
                projected_sustainability_date=None,
                projected_reserve_date=None,
                estimated_first_light=None,
                optimistic_date=None,
                pessimistic_date=None,
                progress_pct=self._compute_progress(
                    sustainability_ratio, reserve_balance, reserve_target,
                ),
                sufficient_data=False,
                message=(
                    f"{n} verified humans. Mission activity building. "
                    f"Not enough data to project revenue."
                ),
                achieved=False,
            )

        # Layer 2+3: Project forward to find sustainability date
        revenue_target = self._sustainability_ratio * float(monthly_costs) if monthly_costs > 0 else float("inf")

        # Find how many humans needed for revenue target
        # projected_revenue = humans * missions_per_human * avg_value * commission_rate
        revenue_per_human = (
            missions_per_human_per_month
            * float(avg_mission_value)
            * float(commission_rate)
        )

        if revenue_per_human > 0 and monthly_costs > 0:
            humans_needed_for_revenue = revenue_target / revenue_per_human
            humans_remaining = max(humans_needed_for_revenue - n, 0)

            if humans_remaining <= 0:
                # Already have enough humans for revenue
                sustainability_date = now
            else:
                days_to_revenue = humans_remaining / adjusted_signup_rate
                sustainability_date = now + timedelta(days=days_to_revenue)

            # Optimistic/pessimistic for revenue
            opt_rate = max(adjusted_signup_rate + self._sigma * std, self._min_rate)
            pess_rate = max(adjusted_signup_rate - self._sigma * std, self._min_rate)

            if humans_remaining <= 0:
                opt_revenue_date = now
                pess_revenue_date = now
            else:
                opt_revenue_date = now + timedelta(days=humans_remaining / opt_rate)
                pess_revenue_date = now + timedelta(days=humans_remaining / pess_rate)
        else:
            sustainability_date = None
            opt_revenue_date = None
            pess_revenue_date = None

        # Reserve projection
        if monthly_costs > 0 and reserve_balance < reserve_target:
            reserve_gap = reserve_target - reserve_balance
            # Reserve fills from commission surplus
            monthly_surplus = monthly_revenue - monthly_costs
            if monthly_surplus > 0:
                months_to_reserve = float(reserve_gap / monthly_surplus)
                reserve_date = now + timedelta(days=months_to_reserve * 30.44)
            else:
                # No surplus yet — estimate when surplus will start
                if sustainability_date is not None and sustainability_date >= now:
                    # After sustainability, surplus = revenue - costs
                    projected_surplus_monthly = Decimal(str(revenue_target)) - monthly_costs
                    if projected_surplus_monthly > 0:
                        months_after = float(reserve_gap / projected_surplus_monthly)
                        reserve_date = sustainability_date + timedelta(days=months_after * 30.44)
                    else:
                        reserve_date = None
                else:
                    reserve_date = None
        elif monthly_costs > 0:
            reserve_date = now  # Already met
        else:
            reserve_date = None

        # First Light = later of sustainability + reserve
        if sustainability_date is not None and reserve_date is not None:
            first_light_date = max(sustainability_date, reserve_date)
        elif sustainability_date is not None:
            first_light_date = sustainability_date
        else:
            first_light_date = reserve_date

        # Guard: First Light cannot be now if reserve is unmet
        if first_light_date is not None and first_light_date <= now:
            if monthly_costs > 0 and reserve_balance < reserve_target:
                first_light_date = None

        # Optimistic/pessimistic bounds
        if opt_revenue_date is not None and pess_revenue_date is not None:
            # Combine revenue and reserve uncertainty
            opt_date = opt_revenue_date
            pess_date = pess_revenue_date
            # Adjust for reserve if it's the binding constraint
            if reserve_date is not None:
                if reserve_date > opt_date:
                    opt_date = reserve_date
                if reserve_date > pess_date:
                    pess_date = reserve_date
            if opt_date > pess_date:
                opt_date, pess_date = pess_date, opt_date
        else:
            opt_date = None
            pess_date = None

        # Progress
        progress = self._compute_progress(
            sustainability_ratio, reserve_balance, reserve_target,
        )

        # Message
        if revenue_met and not reserve_met:
            message = (
                f"Revenue target met! Building {self._reserve_months}-month reserve: "
                f"{reserve_balance:.0f}/{reserve_target:.0f} USDC."
            )
            if reserve_date is not None:
                message += f" Estimated: {reserve_date.strftime('%B %d, %Y')}."
        elif first_light_date is not None:
            ratio_pct = min(sustainability_ratio / self._sustainability_ratio * 100, 100)
            message = (
                f"Revenue at {ratio_pct:.0f}% of sustainability target."
            )
            if opt_date is not None and pess_date is not None and n >= 8:
                message += (
                    f" Estimated First Light between "
                    f"{opt_date.strftime('%B %d, %Y')} and "
                    f"{pess_date.strftime('%B %d, %Y')}."
                )
            elif first_light_date is not None:
                message += (
                    f" Estimated: {first_light_date.strftime('%B %Y')}"
                    f" (early data — range will narrow)."
                )
        else:
            message = (
                f"{n} verified humans. "
                f"Building toward financial sustainability."
            )

        return FirstLightEstimate(
            current_humans=n,
            current_monthly_revenue=monthly_revenue,
            current_monthly_costs=monthly_costs,
            current_sustainability_ratio=sustainability_ratio,
            reserve_balance=reserve_balance,
            reserve_target_3mo=reserve_target,
            projected_sustainability_date=sustainability_date,
            projected_reserve_date=reserve_date,
            estimated_first_light=first_light_date,
            optimistic_date=opt_date,
            pessimistic_date=pess_date,
            progress_pct=round(progress, 1),
            sufficient_data=True,
            message=message,
            achieved=False,
        )

    def _compute_progress(
        self,
        sustainability_ratio: float,
        reserve_balance: Decimal,
        reserve_target: Decimal,
    ) -> float:
        """Compute composite progress toward First Light (0-100).

        Weighted: 70% revenue sustainability, 30% reserve fund.
        """
        # Revenue progress (0-100)
        if self._sustainability_ratio > 0:
            revenue_pct = min(
                sustainability_ratio / self._sustainability_ratio * 100, 100
            )
        else:
            revenue_pct = 100.0

        # Reserve progress (0-100)
        if reserve_target > 0:
            reserve_pct = min(
                float(reserve_balance / reserve_target) * 100, 100
            )
        else:
            reserve_pct = 100.0

        return 0.7 * revenue_pct + 0.3 * reserve_pct
