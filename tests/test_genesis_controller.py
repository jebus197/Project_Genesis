"""Tests for genesis phase controller — proves one-way phase progression."""

import pytest
from pathlib import Path
from datetime import datetime, timedelta, timezone

from genesis.policy.resolver import PolicyResolver
from genesis.governance.genesis_controller import (
    GenesisPhaseController,
    PhaseState,
    PhaseTransitionError,
)
from genesis.models.governance import GenesisPhase


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def controller(resolver: PolicyResolver) -> GenesisPhaseController:
    return GenesisPhaseController(resolver)


def _now() -> datetime:
    return datetime(2026, 3, 1, tzinfo=timezone.utc)


class TestOneWayProgression:
    def test_g0_to_g1_allowed(self, controller: GenesisPhaseController) -> None:
        state = PhaseState(
            current_phase=GenesisPhase.G0,
            phase_started_utc=_now(),
        )
        allowed, _ = controller.can_transition(state, GenesisPhase.G1, _now())
        assert allowed is True

    def test_g1_to_g0_blocked(self, controller: GenesisPhaseController) -> None:
        state = PhaseState(
            current_phase=GenesisPhase.G1,
            phase_started_utc=_now(),
            human_count=100,
        )
        allowed, reason = controller.can_transition(state, GenesisPhase.G0, _now())
        assert allowed is False
        assert "regress" in reason.lower()

    def test_skip_phase_blocked(self, controller: GenesisPhaseController) -> None:
        state = PhaseState(
            current_phase=GenesisPhase.G0,
            phase_started_utc=_now(),
        )
        allowed, reason = controller.can_transition(state, GenesisPhase.G2, _now())
        assert allowed is False
        assert "skip" in reason.lower()


class TestPopulationThresholds:
    def test_g1_to_g2_needs_population(self, controller: GenesisPhaseController) -> None:
        state = PhaseState(
            current_phase=GenesisPhase.G1,
            phase_started_utc=_now(),
            human_count=100,  # Below G1_max_humans (500)
        )
        allowed, _ = controller.can_transition(state, GenesisPhase.G2, _now())
        assert allowed is False

    def test_g1_to_g2_with_population(self, controller: GenesisPhaseController) -> None:
        state = PhaseState(
            current_phase=GenesisPhase.G1,
            phase_started_utc=_now(),
            human_count=500,  # Meets G1_max_humans
        )
        allowed, _ = controller.can_transition(state, GenesisPhase.G2, _now())
        assert allowed is True

    def test_g2_to_g3_needs_population(self, controller: GenesisPhaseController) -> None:
        state = PhaseState(
            current_phase=GenesisPhase.G2,
            phase_started_utc=_now(),
            human_count=1000,  # Below G2_max_humans (2000)
        )
        allowed, _ = controller.can_transition(state, GenesisPhase.G3, _now())
        assert allowed is False

    def test_g2_to_g3_with_population(self, controller: GenesisPhaseController) -> None:
        state = PhaseState(
            current_phase=GenesisPhase.G2,
            phase_started_utc=_now(),
            human_count=2000,
        )
        allowed, _ = controller.can_transition(state, GenesisPhase.G3, _now())
        assert allowed is True


class TestTimeLimits:
    def test_g0_expiry_detected(self, controller: GenesisPhaseController) -> None:
        state = PhaseState(
            current_phase=GenesisPhase.G0,
            phase_started_utc=_now(),
        )
        future = _now() + timedelta(days=400)  # Past G0_MAX_DAYS (365)
        messages = controller.check_phase_status(state, future)
        assert any("expired" in m.lower() for m in messages)

    def test_g0_with_extension(self, controller: GenesisPhaseController) -> None:
        state = PhaseState(
            current_phase=GenesisPhase.G0,
            phase_started_utc=_now(),
            extension_used=True,
        )
        # With extension: 365 + 180 = 545 days total
        within_extension = _now() + timedelta(days=400)
        messages = controller.check_phase_status(state, within_extension)
        assert not any("expired" in m.lower() for m in messages)

    def test_g1_forced_transition(self, controller: GenesisPhaseController) -> None:
        """G1 time limit forces transition to G2 even without population."""
        state = PhaseState(
            current_phase=GenesisPhase.G1,
            phase_started_utc=_now(),
            human_count=100,  # Below threshold
        )
        future = _now() + timedelta(days=750)  # Past G1_MAX_DAYS (730)
        allowed, reason = controller.can_transition(state, GenesisPhase.G2, future)
        assert allowed is True
        assert "forced" in reason.lower()


class TestExecuteTransition:
    def test_g0_to_g1_sets_ratification_deadline(
        self, controller: GenesisPhaseController
    ) -> None:
        state = PhaseState(
            current_phase=GenesisPhase.G0,
            phase_started_utc=_now(),
        )
        new_state = controller.execute_transition(state, GenesisPhase.G1, _now())
        assert new_state.current_phase == GenesisPhase.G1
        assert new_state.g0_ratification_deadline is not None

    def test_invalid_transition_raises(
        self, controller: GenesisPhaseController
    ) -> None:
        state = PhaseState(
            current_phase=GenesisPhase.G1,
            phase_started_utc=_now(),
            human_count=100,
        )
        with pytest.raises(PhaseTransitionError):
            controller.execute_transition(state, GenesisPhase.G0, _now())
