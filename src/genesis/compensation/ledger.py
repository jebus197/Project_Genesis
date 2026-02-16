"""Operational ledger — tracks completed missions and costs for rolling window.

The ledger is the data source for the commission engine's rolling window
computation. It records completed missions and operational cost entries.

Storage is in-memory for now. Persistence integration via the event log
is a separate future step — the ledger can be reconstructed from the
append-only event log at any time.

Adaptive dual-threshold window:
- Time window: last WINDOW_DAYS days of completed missions
- Minimum sample: at least WINDOW_MIN_MISSIONS missions
- If fewer than MIN_MISSIONS in the time window, extend back to capture them
- This is inherently adaptive: stretches at low volume, bounds at high volume
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from genesis.models.compensation import CompletedMission, OperationalCostEntry


class OperationalLedger:
    """In-memory ledger of completed missions and operational costs.

    Usage:
        ledger = OperationalLedger()
        ledger.record_completed_mission(mission)
        ledger.record_operational_cost(cost_entry)

        # For commission computation:
        window_missions = ledger.missions_in_window(90, 50, now)
    """

    def __init__(self) -> None:
        self._missions: List[CompletedMission] = []
        self._costs: List[OperationalCostEntry] = []

    def record_completed_mission(self, mission: CompletedMission) -> None:
        """Record a completed mission for rolling window computation."""
        self._missions.append(mission)

    def record_operational_cost(self, entry: OperationalCostEntry) -> None:
        """Record an operational cost entry."""
        self._costs.append(entry)

    def total_completed_missions(self) -> int:
        """Return the total number of completed missions (all time)."""
        return len(self._missions)

    def missions_in_window(
        self,
        window_days: int,
        min_missions: int,
        now: datetime,
    ) -> List[CompletedMission]:
        """Return missions in the adaptive rolling window.

        1. Start with missions completed in the last window_days days.
        2. If fewer than min_missions, extend back to capture min_missions.
        3. If fewer than min_missions exist total, return all of them.
        """
        cutoff = now - timedelta(days=window_days)

        # Filter out future-dated entries, then sort descending
        valid_missions = [m for m in self._missions if m.completed_utc <= now]
        sorted_missions = sorted(
            valid_missions, key=lambda m: m.completed_utc, reverse=True
        )

        # Get missions within the time window
        in_window = [m for m in sorted_missions if m.completed_utc >= cutoff]

        if len(in_window) >= min_missions:
            return in_window

        # Not enough in time window — extend back to capture min_missions
        return sorted_missions[:min_missions]

    def costs_in_window(
        self,
        window_days: int,
        min_missions: int,
        now: datetime,
    ) -> List[OperationalCostEntry]:
        """Return operational costs matching the same window as missions.

        The cost window matches the mission window: if the mission window
        extended back beyond window_days to capture min_missions, the
        cost window extends correspondingly.
        """
        window_missions = self.missions_in_window(window_days, min_missions, now)

        if not window_missions:
            return []

        # Use the earliest mission in the window as the cost cutoff
        earliest_mission = min(m.completed_utc for m in window_missions)
        return [c for c in self._costs if earliest_mission <= c.timestamp_utc <= now]
