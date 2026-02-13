"""Genesis phase controller — manages the one-way G0→G1→G2→G3 transition.

Rules:
- G0: Founder stewardship. Max G0_MAX_DAYS (+ one extension of G0_EXTENSION_DAYS).
      All G0 decisions must be retroactively ratified within G1 (G0_RATIFICATION_WINDOW_DAYS).
- G1: Early governance with scaled-down chambers. Max G1_MAX_DAYS.
      Population < G1_max_humans.
- G2: Growth governance with larger chambers.
      Population < G2_max_humans.
- G3: Full constitutional governance. No time limit.

Phase progression is one-way. No regression.
Time limits are hard — expiry forces transition or shutdown.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from genesis.models.governance import GenesisPhase
from genesis.policy.resolver import PolicyResolver


@dataclass
class PhaseState:
    """Current state of the genesis phase controller."""
    current_phase: GenesisPhase
    phase_started_utc: datetime
    extension_used: bool = False
    g0_ratification_deadline: Optional[datetime] = None
    human_count: int = 0


class PhaseTransitionError(Exception):
    """Raised when a phase transition is invalid."""


class GenesisPhaseController:
    """Controls genesis bootstrap phase transitions.

    Invariants:
    1. Phase progression is one-way (G0 → G1 → G2 → G3).
    2. Time limits are hard gates.
    3. Population thresholds determine when transition becomes available.
    4. G0 decisions must be retroactively ratified in G1.
    """

    def __init__(self, resolver: PolicyResolver) -> None:
        self._resolver = resolver

    def check_phase_status(
        self, state: PhaseState, now: datetime
    ) -> list[str]:
        """Check current phase for deadline violations or available transitions.

        Returns list of status messages. Empty = healthy.
        """
        messages: list[str] = []
        time_limits = self._resolver.genesis_time_limits()
        thresholds = self._resolver.genesis_phase_thresholds()

        if state.current_phase == GenesisPhase.G0:
            max_days = time_limits["G0_MAX_DAYS"]
            if state.extension_used:
                max_days += time_limits["G0_EXTENSION_DAYS"]
            deadline = state.phase_started_utc + timedelta(days=max_days)
            if now >= deadline:
                messages.append(
                    f"G0 time limit expired ({max_days} days). "
                    f"Must transition to G1 or extend (if not already extended)."
                )
            remaining = (deadline - now).days
            if 0 < remaining <= 30:
                messages.append(
                    f"G0 deadline approaching: {remaining} days remaining."
                )

        elif state.current_phase == GenesisPhase.G1:
            max_days = time_limits["G1_MAX_DAYS"]
            deadline = state.phase_started_utc + timedelta(days=max_days)
            if now >= deadline:
                messages.append(
                    f"G1 time limit expired ({max_days} days). "
                    f"Must transition to G2."
                )
            # Check G0 ratification deadline
            if state.g0_ratification_deadline and now >= state.g0_ratification_deadline:
                messages.append(
                    "G0 retroactive ratification deadline has passed."
                )

            # Check if population threshold met for G2 transition
            if state.human_count >= thresholds["G1_max_humans"]:
                messages.append(
                    f"G1 population ({state.human_count}) >= "
                    f"G1_max_humans ({thresholds['G1_max_humans']}). "
                    f"Transition to G2 available."
                )

        elif state.current_phase == GenesisPhase.G2:
            if state.human_count >= thresholds["G2_max_humans"]:
                messages.append(
                    f"G2 population ({state.human_count}) >= "
                    f"G2_max_humans ({thresholds['G2_max_humans']}). "
                    f"Transition to G3 available."
                )

        return messages

    def can_transition(
        self, state: PhaseState, target: GenesisPhase, now: datetime
    ) -> tuple[bool, str]:
        """Check if a phase transition is valid.

        Returns (allowed, reason).
        """
        thresholds = self._resolver.genesis_phase_thresholds()
        time_limits = self._resolver.genesis_time_limits()

        # One-way enforcement
        phase_order = {
            GenesisPhase.G0: 0,
            GenesisPhase.G1: 1,
            GenesisPhase.G2: 2,
            GenesisPhase.G3: 3,
        }

        current_ord = phase_order[state.current_phase]
        target_ord = phase_order[target]

        if target_ord <= current_ord:
            return False, f"Cannot regress from {state.current_phase.value} to {target.value}"

        if target_ord != current_ord + 1:
            return False, f"Cannot skip phases: {state.current_phase.value} → {target.value}"

        # Phase-specific transition conditions
        if state.current_phase == GenesisPhase.G0 and target == GenesisPhase.G1:
            max_days = time_limits["G0_MAX_DAYS"]
            if state.extension_used:
                max_days += time_limits["G0_EXTENSION_DAYS"]
            deadline = state.phase_started_utc + timedelta(days=max_days)
            # Can transition voluntarily or must transition on deadline
            return True, "G0 → G1 transition allowed"

        elif state.current_phase == GenesisPhase.G1 and target == GenesisPhase.G2:
            if state.human_count < thresholds["G1_max_humans"]:
                # Time-forced transition is also valid
                max_days = time_limits["G1_MAX_DAYS"]
                deadline = state.phase_started_utc + timedelta(days=max_days)
                if now >= deadline:
                    return True, "G1 time limit reached — forced transition to G2"
                return (
                    False,
                    f"G1 population ({state.human_count}) < "
                    f"G1_max_humans ({thresholds['G1_max_humans']})",
                )
            return True, "G1 → G2 population threshold met"

        elif state.current_phase == GenesisPhase.G2 and target == GenesisPhase.G3:
            if state.human_count < thresholds["G2_max_humans"]:
                return (
                    False,
                    f"G2 population ({state.human_count}) < "
                    f"G2_max_humans ({thresholds['G2_max_humans']})",
                )
            return True, "G2 → G3 population threshold met"

        return False, "Unknown transition"

    def execute_transition(
        self, state: PhaseState, target: GenesisPhase, now: datetime
    ) -> PhaseState:
        """Execute a phase transition. Raises PhaseTransitionError if invalid."""
        allowed, reason = self.can_transition(state, target, now)
        if not allowed:
            raise PhaseTransitionError(reason)

        time_limits = self._resolver.genesis_time_limits()

        new_state = PhaseState(
            current_phase=target,
            phase_started_utc=now,
            human_count=state.human_count,
        )

        # If transitioning to G1, set G0 ratification deadline
        if target == GenesisPhase.G1:
            ratification_days = time_limits["G0_RATIFICATION_WINDOW_DAYS"]
            new_state.g0_ratification_deadline = now + timedelta(days=ratification_days)

        return new_state
