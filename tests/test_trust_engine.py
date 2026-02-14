"""Tests for trust engine — proves trust invariants hold under all conditions."""

import pytest
from pathlib import Path

from genesis.policy.resolver import PolicyResolver
from genesis.trust.engine import TrustEngine
from genesis.models.trust import ActorKind, TrustRecord


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def engine(resolver: PolicyResolver) -> TrustEngine:
    return TrustEngine(resolver)


def _human_record(score: float = 0.5) -> TrustRecord:
    return TrustRecord(
        actor_id="human_1",
        actor_kind=ActorKind.HUMAN,
        score=score,
        quality=0.8,
        reliability=0.7,
        volume=0.3,
    )


def _machine_record(score: float = 0.5) -> TrustRecord:
    return TrustRecord(
        actor_id="machine_1",
        actor_kind=ActorKind.MACHINE,
        score=score,
        quality=0.9,
        reliability=0.95,
        volume=0.2,
    )


class TestTrustComputation:
    def test_weighted_sum(self, engine: TrustEngine) -> None:
        score = engine.compute_score(quality=0.8, reliability=0.7, volume=0.3)
        # w_Q=0.75, w_R=0.2, w_V=0.05
        expected = 0.75 * 0.8 + 0.2 * 0.7 + 0.05 * 0.3
        assert abs(score - expected) < 1e-9


class TestScoreClamping:
    """Trust scores must always be in [0, 1]."""

    def test_score_clamped_at_one(self, engine: TrustEngine) -> None:
        """Inputs > 1.0 must not produce a score > 1.0."""
        score = engine.compute_score(quality=2.0, reliability=2.0, volume=2.0)
        assert score <= 1.0

    def test_score_clamped_at_zero(self, engine: TrustEngine) -> None:
        """Negative inputs must not produce a score < 0.0."""
        score = engine.compute_score(quality=-1.0, reliability=-1.0, volume=-1.0)
        assert score >= 0.0

    def test_apply_update_clamped(self, engine: TrustEngine) -> None:
        """Full update path with extreme inputs stays in [0, 1]."""
        record = _human_record(score=0.5)
        new_record, delta = engine.apply_update(
            record, quality=5.0, reliability=5.0, volume=5.0,
            reason="extreme inputs",
        )
        assert 0.0 <= new_record.score <= 1.0


class TestQualityGate:
    def test_no_gain_below_quality_gate(self, engine: TrustEngine) -> None:
        """If quality < Q_min, trust cannot increase."""
        record = _human_record(score=0.5)
        new_record, delta = engine.apply_update(
            record, quality=0.3, reliability=0.9, volume=0.9,
            reason="low quality work",
        )
        # Q_min_H = 0.7, quality=0.3 < 0.7, so no gain
        assert new_record.score <= record.score

    def test_gain_above_quality_gate(self, engine: TrustEngine) -> None:
        """If quality >= Q_min, trust can increase."""
        record = _human_record(score=0.3)
        new_record, delta = engine.apply_update(
            record, quality=0.9, reliability=0.8, volume=0.4,
            reason="excellent work",
        )
        assert new_record.score >= record.score


class TestTrustFloor:
    def test_human_floor_positive(self, engine: TrustEngine) -> None:
        """Human trust score cannot drop to zero."""
        record = _human_record(score=0.5)
        new_record, delta = engine.apply_update(
            record, quality=0.0, reliability=0.0, volume=0.0,
            reason="total failure",
        )
        assert new_record.score > 0.0

    def test_machine_floor_zero(self, engine: TrustEngine) -> None:
        """Machine trust can drop to zero."""
        record = _machine_record(score=0.5)
        new_record, delta = engine.apply_update(
            record, quality=0.0, reliability=0.0, volume=0.0,
            reason="total failure",
        )
        assert new_record.score == 0.0


class TestFastElevation:
    def test_fast_elevation_suspends(self, engine: TrustEngine) -> None:
        """Large trust jumps are flagged for suspension."""
        record = _human_record(score=0.1)
        new_record, delta = engine.apply_update(
            record, quality=0.95, reliability=0.9, volume=0.5,
            reason="suspiciously fast improvement",
        )
        # delta_fast = 0.02; this should exceed it
        if delta.abs_delta > 0.02:
            assert delta.suspended is True

    def test_small_delta_not_suspended(self, engine: TrustEngine) -> None:
        """Small trust changes are not suspended."""
        record = _human_record(score=0.745)
        # Compute what the score would be at approximately the same level
        new_record, delta = engine.apply_update(
            record, quality=0.8, reliability=0.7, volume=0.3,
            reason="normal work",
        )
        if delta.abs_delta <= 0.02:
            assert delta.suspended is False


class TestQuarantineAndDecommission:
    def test_quarantined_no_gain(self, engine: TrustEngine) -> None:
        record = _machine_record(score=0.3)
        record.quarantined = True
        new_record, delta = engine.apply_update(
            record, quality=0.99, reliability=0.99, volume=0.5,
            reason="trying to escape quarantine",
        )
        assert new_record.score <= record.score

    def test_decommissioned_no_gain(self, engine: TrustEngine) -> None:
        record = _machine_record(score=0.1)
        record.decommissioned = True
        new_record, delta = engine.apply_update(
            record, quality=0.99, reliability=0.99, volume=0.5,
            reason="trying to escape decommission",
        )
        assert new_record.score <= record.score


class TestConstitutionalAuthority:
    """Machines cannot vote or propose — only humans hold constitutional authority."""

    def test_machine_cannot_vote(self) -> None:
        """A machine with high trust must still be ineligible to vote."""
        record = _machine_record(score=0.99)
        assert record.is_eligible_to_vote(tau_vote=0.3) is False

    def test_machine_cannot_propose(self) -> None:
        """A machine with high trust must still be ineligible to propose."""
        record = _machine_record(score=0.99)
        assert record.is_eligible_to_propose(tau_prop=0.3) is False

    def test_human_can_vote_above_threshold(self) -> None:
        """A human above the voting threshold can vote."""
        record = _human_record(score=0.8)
        assert record.is_eligible_to_vote(tau_vote=0.5) is True

    def test_human_can_propose_above_threshold(self) -> None:
        """A human above the proposal threshold can propose."""
        record = _human_record(score=0.8)
        assert record.is_eligible_to_propose(tau_prop=0.5) is True

    def test_human_below_threshold_cannot_vote(self) -> None:
        """A human below the voting threshold cannot vote."""
        record = _human_record(score=0.2)
        assert record.is_eligible_to_vote(tau_vote=0.5) is False

    def test_quarantined_human_cannot_vote(self) -> None:
        """A quarantined human cannot vote even with sufficient trust."""
        record = _human_record(score=0.8)
        record.quarantined = True
        assert record.is_eligible_to_vote(tau_vote=0.5) is False


class TestRecertification:
    def test_healthy_machine(self, engine: TrustEngine) -> None:
        record = _machine_record(score=0.8)
        record.quality = 0.96
        record.reliability = 0.99
        errors = engine.check_recertification(record)
        assert errors == []

    def test_low_quality_fails(self, engine: TrustEngine) -> None:
        record = _machine_record(score=0.5)
        record.quality = 0.85  # Below RECERT_CORRECTNESS_MIN (0.95)
        errors = engine.check_recertification(record)
        assert any("RECERT_CORRECTNESS_MIN" in e for e in errors)

    def test_max_failures_triggers_decommission(self, engine: TrustEngine) -> None:
        record = _machine_record(score=0.3)
        record.recertification_failures = 3  # M_RECERT_FAIL_MAX = 3
        errors = engine.check_recertification(record)
        assert any("decommission" in e for e in errors)

    def test_human_not_checked(self, engine: TrustEngine) -> None:
        record = _human_record(score=0.1)
        errors = engine.check_recertification(record)
        assert errors == []
