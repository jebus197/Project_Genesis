"""Unit tests for domain-specific trust — computation, decay, aggregation, forecasts.

Tests TrustEngine's domain trust methods:
- compute_domain_score()
- apply_domain_update()
- aggregate_global_score()
- compute_decay_factor()
- apply_inactivity_decay()
- compute_decay_forecast()
- _classify_urgency()

Also tests DomainTrustScore, DomainTrustDelta, DecayUrgency, TrustStatus models.
"""

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from genesis.models.domain_trust import (
    DecayUrgency,
    DomainDecayForecast,
    DomainTrustDelta,
    DomainTrustScore,
    TrustStatus,
)
from genesis.models.trust import ActorKind, TrustRecord
from genesis.policy.resolver import PolicyResolver
from genesis.trust.engine import TrustEngine

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def resolver():
    """Resolver with domain trust config loaded (from real config dir)."""
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def engine(resolver):
    return TrustEngine(resolver)


@pytest.fixture
def human_record():
    """A human actor with moderate trust and no domain scores yet."""
    return TrustRecord(
        actor_id="human-1",
        actor_kind=ActorKind.HUMAN,
        score=0.5,
        quality=0.5,
        reliability=0.5,
        volume=0.5,
    )


@pytest.fixture
def machine_record():
    """A machine actor with moderate trust."""
    return TrustRecord(
        actor_id="machine-1",
        actor_kind=ActorKind.MACHINE,
        score=0.5,
        quality=0.5,
        reliability=0.5,
        volume=0.5,
    )


@pytest.fixture
def record_with_domains():
    """Human actor with existing domain scores."""
    now = datetime.now(timezone.utc)
    return TrustRecord(
        actor_id="human-2",
        actor_kind=ActorKind.HUMAN,
        score=0.6,
        quality=0.6,
        reliability=0.6,
        volume=0.6,
        last_active_utc=now,
        domain_scores={
            "software_engineering": DomainTrustScore(
                domain="software_engineering",
                score=0.7,
                quality=0.7,
                reliability=0.6,
                volume=0.5,
                effort=0.4,
                mission_count=10,
                last_active_utc=now,
            ),
            "data_science": DomainTrustScore(
                domain="data_science",
                score=0.4,
                quality=0.4,
                reliability=0.5,
                volume=0.3,
                effort=0.2,
                mission_count=3,
                last_active_utc=now - timedelta(days=100),
            ),
        },
    )


# ===================================================================
# DomainTrustScore model
# ===================================================================

class TestDomainTrustScoreModel:
    def test_default_values(self) -> None:
        ds = DomainTrustScore(domain="test")
        assert ds.domain == "test"
        assert ds.score == 0.0
        assert ds.quality == 0.0
        assert ds.mission_count == 0
        assert ds.last_active_utc is None

    def test_full_construction(self) -> None:
        now = datetime.now(timezone.utc)
        ds = DomainTrustScore(
            domain="se",
            score=0.8,
            quality=0.9,
            reliability=0.7,
            volume=0.5,
            effort=0.3,
            mission_count=5,
            last_active_utc=now,
        )
        assert ds.score == 0.8
        assert ds.mission_count == 5


class TestDomainTrustDeltaModel:
    def test_construction(self) -> None:
        delta = DomainTrustDelta(
            actor_id="a1",
            domain="se",
            previous_score=0.3,
            new_score=0.5,
            reason="test",
            mission_id="m1",
        )
        assert delta.actor_id == "a1"
        assert delta.new_score - delta.previous_score == pytest.approx(0.2)


class TestDecayUrgencyEnum:
    def test_all_values(self) -> None:
        assert DecayUrgency.STABLE.value == "stable"
        assert DecayUrgency.DRIFTING.value == "drifting"
        assert DecayUrgency.URGENT.value == "urgent"
        assert DecayUrgency.CRITICAL.value == "critical"


class TestTrustStatusModel:
    def test_construction(self) -> None:
        status = TrustStatus(
            actor_id="a1",
            global_score=0.5,
            days_since_last_activity=30.0,
            half_life_days=365.0,
            days_until_half_life=335.0,
            projected_score_at_half_life=0.3,
            urgency=DecayUrgency.STABLE,
            domain_forecasts=[],
        )
        assert status.actor_id == "a1"
        assert status.days_until_half_life == 335.0


# ===================================================================
# compute_domain_score
# ===================================================================

class TestComputeDomainScore:
    def test_basic_computation(self, engine) -> None:
        """Domain score uses configured weights."""
        score = engine.compute_domain_score(
            quality=1.0, reliability=1.0, volume=1.0, effort=1.0,
        )
        assert score == pytest.approx(1.0)

    def test_zero_inputs(self, engine) -> None:
        score = engine.compute_domain_score(
            quality=0.0, reliability=0.0, volume=0.0, effort=0.0,
        )
        assert score == 0.0

    def test_clamped_at_one(self, engine) -> None:
        score = engine.compute_domain_score(
            quality=2.0, reliability=2.0, volume=2.0, effort=2.0,
        )
        assert score == 1.0

    def test_quality_dominates(self, engine) -> None:
        """With w_Q=0.70, quality has the biggest influence."""
        high_q = engine.compute_domain_score(quality=1.0, reliability=0.0, volume=0.0, effort=0.0)
        high_r = engine.compute_domain_score(quality=0.0, reliability=1.0, volume=0.0, effort=0.0)
        assert high_q > high_r


# ===================================================================
# apply_domain_update
# ===================================================================

class TestApplyDomainUpdate:
    def test_creates_new_domain(self, engine, human_record) -> None:
        """First domain update creates the domain score."""
        new_record, delta = engine.apply_domain_update(
            record=human_record,
            domain="software_engineering",
            quality=0.8,
            reliability=0.6,
            volume=0.3,
            reason="test",
        )
        assert "software_engineering" in new_record.domain_scores
        ds = new_record.domain_scores["software_engineering"]
        assert ds.score > 0
        assert ds.mission_count == 1
        assert ds.last_active_utc is not None
        assert delta.previous_score == 0.0

    def test_updates_existing_domain(self, engine, record_with_domains) -> None:
        """Subsequent update increments mission count."""
        prev_count = record_with_domains.domain_scores["software_engineering"].mission_count
        new_record, delta = engine.apply_domain_update(
            record=record_with_domains,
            domain="software_engineering",
            quality=0.9,
            reliability=0.7,
            volume=0.5,
            reason="update",
        )
        ds = new_record.domain_scores["software_engineering"]
        assert ds.mission_count == prev_count + 1
        assert delta.previous_score == pytest.approx(0.7)

    def test_does_not_mutate_original(self, engine, human_record) -> None:
        """Original record must not be modified."""
        original_score = human_record.score
        engine.apply_domain_update(
            record=human_record,
            domain="test",
            quality=0.9, reliability=0.9, volume=0.9,
            reason="test",
        )
        assert human_record.score == original_score
        assert "test" not in human_record.domain_scores

    def test_global_score_updated(self, engine, human_record) -> None:
        """Global score should reflect new domain aggregate."""
        new_record, _ = engine.apply_domain_update(
            record=human_record,
            domain="se",
            quality=0.9, reliability=0.8, volume=0.5,
            reason="test",
        )
        # With one domain, global score equals that domain's score
        ds = new_record.domain_scores["se"]
        assert new_record.score == pytest.approx(ds.score, abs=0.01)

    def test_preserves_other_domains(self, engine, record_with_domains) -> None:
        """Updating one domain must not drop the other."""
        new_record, _ = engine.apply_domain_update(
            record=record_with_domains,
            domain="software_engineering",
            quality=0.9, reliability=0.7, volume=0.5,
            reason="test",
        )
        assert "data_science" in new_record.domain_scores

    def test_floor_enforced(self, engine) -> None:
        """Global score respects trust floor even with domain updates."""
        record = TrustRecord(
            actor_id="h1",
            actor_kind=ActorKind.HUMAN,
            score=0.01,
        )
        new_record, _ = engine.apply_domain_update(
            record=record,
            domain="test",
            quality=0.0, reliability=0.0, volume=0.0,
            reason="zero",
        )
        # Human floor is 0.01
        assert new_record.score >= 0.01


# ===================================================================
# aggregate_global_score
# ===================================================================

class TestAggregateGlobalScore:
    def test_empty_domains(self, engine) -> None:
        assert engine.aggregate_global_score({}) == 0.0

    def test_single_domain(self, engine) -> None:
        scores = {
            "se": DomainTrustScore(domain="se", score=0.8, mission_count=5),
        }
        result = engine.aggregate_global_score(scores)
        assert result == pytest.approx(0.8)

    def test_volume_weighting(self, engine) -> None:
        """Domain with more missions should have more influence."""
        scores = {
            "se": DomainTrustScore(domain="se", score=0.9, mission_count=20),
            "ds": DomainTrustScore(domain="ds", score=0.3, mission_count=1),
        }
        result = engine.aggregate_global_score(scores)
        # Volume-weighted: should be much closer to 0.9 than 0.3
        assert result > 0.7

    def test_equal_volumes(self, engine) -> None:
        """Equal mission counts → simple average."""
        scores = {
            "a": DomainTrustScore(domain="a", score=0.8, mission_count=5),
            "b": DomainTrustScore(domain="b", score=0.4, mission_count=5),
        }
        result = engine.aggregate_global_score(scores)
        assert result == pytest.approx(0.6, abs=0.01)

    def test_zero_mission_counts(self, engine) -> None:
        """Zero-mission domains → simple mean."""
        scores = {
            "a": DomainTrustScore(domain="a", score=0.6, mission_count=0),
            "b": DomainTrustScore(domain="b", score=0.4, mission_count=0),
        }
        result = engine.aggregate_global_score(scores)
        assert result == pytest.approx(0.5)

    def test_clamped_to_one(self, engine) -> None:
        """Aggregate should never exceed 1.0."""
        scores = {
            "a": DomainTrustScore(domain="a", score=1.0, mission_count=10),
        }
        result = engine.aggregate_global_score(scores)
        assert result <= 1.0


# ===================================================================
# compute_decay_factor
# ===================================================================

class TestComputeDecayFactor:
    def test_zero_days_no_decay(self, engine) -> None:
        assert engine.compute_decay_factor(0, 365, 10) == 1.0

    def test_negative_days_no_decay(self, engine) -> None:
        assert engine.compute_decay_factor(-5, 365, 10) == 1.0

    def test_at_half_life_low_volume(self, engine) -> None:
        """At half-life with zero volume, should decay significantly."""
        factor = engine.compute_decay_factor(365, 365, 0)
        # 1 - (365/365) / (1 + ln(1)) = 1 - 1/1 = 0.0 → clamped to floor
        assert factor < 0.1

    def test_high_volume_slower_decay(self, engine) -> None:
        """High volume dampens decay."""
        low_vol = engine.compute_decay_factor(200, 365, 1)
        high_vol = engine.compute_decay_factor(200, 365, 50)
        assert high_vol > low_vol

    def test_never_below_floor(self, engine) -> None:
        """Decay factor never goes below floor."""
        factor = engine.compute_decay_factor(10000, 365, 0)
        assert factor >= 0.01

    def test_zero_half_life_no_decay(self, engine) -> None:
        """Zero half-life → no decay (edge case)."""
        assert engine.compute_decay_factor(100, 0, 10) == 1.0


# ===================================================================
# apply_inactivity_decay
# ===================================================================

class TestApplyInactivityDecay:
    def test_no_decay_when_recently_active(self, engine) -> None:
        """Recently active actors should not be decayed."""
        now = datetime.now(timezone.utc)
        record = TrustRecord(
            actor_id="h1",
            actor_kind=ActorKind.HUMAN,
            score=0.8,
            last_active_utc=now,
            domain_scores={
                "se": DomainTrustScore(
                    domain="se", score=0.8, mission_count=5,
                    last_active_utc=now,
                ),
            },
        )
        result = engine.apply_inactivity_decay(record, now=now)
        # Should be the same object (identity — no decay applied)
        assert result is record

    def test_decay_after_long_inactivity(self, engine) -> None:
        """Inactive actors should have decayed scores."""
        old = datetime.now(timezone.utc) - timedelta(days=200)
        now = datetime.now(timezone.utc)
        record = TrustRecord(
            actor_id="h1",
            actor_kind=ActorKind.HUMAN,
            score=0.8,
            last_active_utc=old,
            domain_scores={
                "se": DomainTrustScore(
                    domain="se", score=0.8, mission_count=5,
                    last_active_utc=old,
                ),
            },
        )
        result = engine.apply_inactivity_decay(record, now=now)
        assert result is not record
        assert result.domain_scores["se"].score < 0.8
        assert result.score < record.score

    def test_machine_decays_faster(self, engine) -> None:
        """Machine (90d half-life) decays faster than human (365d)."""
        old = datetime.now(timezone.utc) - timedelta(days=100)
        now = datetime.now(timezone.utc)

        human_rec = TrustRecord(
            actor_id="h1", actor_kind=ActorKind.HUMAN, score=0.8,
            last_active_utc=old,
            domain_scores={
                "se": DomainTrustScore(
                    domain="se", score=0.8, mission_count=5,
                    last_active_utc=old,
                ),
            },
        )
        machine_rec = TrustRecord(
            actor_id="m1", actor_kind=ActorKind.MACHINE, score=0.8,
            last_active_utc=old,
            domain_scores={
                "se": DomainTrustScore(
                    domain="se", score=0.8, mission_count=5,
                    last_active_utc=old,
                ),
            },
        )

        human_result = engine.apply_inactivity_decay(human_rec, now=now)
        machine_result = engine.apply_inactivity_decay(machine_rec, now=now)

        # Machine should have lower score (faster decay)
        assert machine_result.domain_scores["se"].score < human_result.domain_scores["se"].score

    def test_does_not_mutate_original(self, engine) -> None:
        old = datetime.now(timezone.utc) - timedelta(days=200)
        now = datetime.now(timezone.utc)
        record = TrustRecord(
            actor_id="h1", actor_kind=ActorKind.HUMAN, score=0.8,
            last_active_utc=old,
            domain_scores={
                "se": DomainTrustScore(
                    domain="se", score=0.8, mission_count=5,
                    last_active_utc=old,
                ),
            },
        )
        engine.apply_inactivity_decay(record, now=now)
        assert record.domain_scores["se"].score == 0.8

    def test_no_domain_scores_but_has_global(self, engine) -> None:
        """Actor with no domain scores but global last_active should still decay."""
        old = datetime.now(timezone.utc) - timedelta(days=200)
        now = datetime.now(timezone.utc)
        record = TrustRecord(
            actor_id="h1", actor_kind=ActorKind.HUMAN, score=0.8,
            last_active_utc=old,
        )
        result = engine.apply_inactivity_decay(record, now=now)
        # With no domain scores, global decay path should apply
        assert result.score <= record.score


# ===================================================================
# compute_decay_forecast (trust dashboard)
# ===================================================================

class TestComputeDecayForecast:
    def test_recently_active_is_stable(self, engine) -> None:
        now = datetime.now(timezone.utc)
        record = TrustRecord(
            actor_id="h1", actor_kind=ActorKind.HUMAN, score=0.8,
            last_active_utc=now,
        )
        status = engine.compute_decay_forecast(record, now=now)
        assert status.urgency == DecayUrgency.STABLE
        assert status.days_since_last_activity == pytest.approx(0.0, abs=0.01)
        assert status.days_until_half_life == pytest.approx(365.0, abs=1.0)

    def test_drifting_status(self, engine) -> None:
        now = datetime.now(timezone.utc)
        record = TrustRecord(
            actor_id="h1", actor_kind=ActorKind.HUMAN, score=0.8,
            last_active_utc=now - timedelta(days=150),
        )
        status = engine.compute_decay_forecast(record, now=now)
        assert status.urgency == DecayUrgency.DRIFTING

    def test_urgent_status(self, engine) -> None:
        now = datetime.now(timezone.utc)
        record = TrustRecord(
            actor_id="h1", actor_kind=ActorKind.HUMAN, score=0.8,
            last_active_utc=now - timedelta(days=300),
        )
        status = engine.compute_decay_forecast(record, now=now)
        assert status.urgency == DecayUrgency.URGENT

    def test_critical_status(self, engine) -> None:
        now = datetime.now(timezone.utc)
        record = TrustRecord(
            actor_id="h1", actor_kind=ActorKind.HUMAN, score=0.8,
            last_active_utc=now - timedelta(days=400),
        )
        status = engine.compute_decay_forecast(record, now=now)
        assert status.urgency == DecayUrgency.CRITICAL

    def test_machine_shorter_half_life(self, engine) -> None:
        """Machine half-life of 90d means urgency hits faster."""
        now = datetime.now(timezone.utc)
        record = TrustRecord(
            actor_id="m1", actor_kind=ActorKind.MACHINE, score=0.8,
            last_active_utc=now - timedelta(days=80),
        )
        status = engine.compute_decay_forecast(record, now=now)
        assert status.half_life_days == pytest.approx(90.0)
        assert status.urgency == DecayUrgency.URGENT  # 80/90 > 0.75

    def test_domain_forecasts_included(self, engine, record_with_domains) -> None:
        status = engine.compute_decay_forecast(record_with_domains)
        assert len(status.domain_forecasts) == 2
        domains = {f.domain for f in status.domain_forecasts}
        assert "software_engineering" in domains
        assert "data_science" in domains

    def test_projected_score_at_half_life(self, engine) -> None:
        now = datetime.now(timezone.utc)
        record = TrustRecord(
            actor_id="h1", actor_kind=ActorKind.HUMAN, score=0.8,
            last_active_utc=now,
        )
        status = engine.compute_decay_forecast(record, now=now)
        # Projected should be lower than current
        assert status.projected_score_at_half_life < status.global_score

    def test_no_activity_timestamp(self, engine) -> None:
        """Actor with no last_active_utc should not crash."""
        record = TrustRecord(
            actor_id="h1", actor_kind=ActorKind.HUMAN, score=0.8,
        )
        status = engine.compute_decay_forecast(record)
        assert status.days_since_last_activity == 0.0
        assert status.urgency == DecayUrgency.STABLE


# ===================================================================
# _classify_urgency
# ===================================================================

class TestClassifyUrgency:
    def test_zero_is_stable(self) -> None:
        assert TrustEngine._classify_urgency(0, 365) == DecayUrgency.STABLE

    def test_quarter_is_drifting(self) -> None:
        assert TrustEngine._classify_urgency(100, 365) == DecayUrgency.DRIFTING

    def test_three_quarter_is_urgent(self) -> None:
        assert TrustEngine._classify_urgency(280, 365) == DecayUrgency.URGENT

    def test_past_half_life_is_critical(self) -> None:
        assert TrustEngine._classify_urgency(400, 365) == DecayUrgency.CRITICAL

    def test_exact_boundary_stable_drifting(self) -> None:
        # At exactly 25% → DRIFTING (ratio >= 0.25)
        assert TrustEngine._classify_urgency(91.25, 365) == DecayUrgency.DRIFTING

    def test_just_under_quarter(self) -> None:
        assert TrustEngine._classify_urgency(90, 365) == DecayUrgency.STABLE

    def test_zero_half_life_is_critical(self) -> None:
        assert TrustEngine._classify_urgency(1, 0) == DecayUrgency.CRITICAL


# ===================================================================
# Trust record domain_scores backward compatibility
# ===================================================================

class TestDomainScoresBackwardCompat:
    def test_empty_domain_scores_default(self) -> None:
        """TrustRecord without domain_scores works."""
        record = TrustRecord(
            actor_id="a1",
            actor_kind=ActorKind.HUMAN,
            score=0.5,
        )
        assert record.domain_scores == {}

    def test_apply_update_preserves_domain_scores(self, engine) -> None:
        """Global trust update should not lose domain scores."""
        record = TrustRecord(
            actor_id="a1",
            actor_kind=ActorKind.HUMAN,
            score=0.5,
            domain_scores={
                "se": DomainTrustScore(domain="se", score=0.7, mission_count=5),
            },
        )
        new_record, _ = engine.apply_update(
            record, quality=0.6, reliability=0.5, volume=0.5,
            reason="test",
        )
        assert "se" in new_record.domain_scores
        assert new_record.domain_scores["se"].score == 0.7
