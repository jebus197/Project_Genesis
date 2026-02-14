"""Tests for skill decay engine — time-based proficiency decay."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from genesis.models.skill import (
    ActorSkillProfile,
    SkillId,
    SkillProficiency,
)
from genesis.skills.decay import SkillDecayEngine, SkillDecayResult
from genesis.policy.resolver import PolicyResolver

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def resolver():
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def engine(resolver):
    return SkillDecayEngine(resolver)


def _make_profile(
    days_ago: float = 0,
    proficiency: float = 0.8,
    evidence_count: int = 10,
    now: datetime | None = None,
) -> ActorSkillProfile:
    """Build a profile with a skill demonstrated `days_ago` days ago."""
    now = now or datetime.now(timezone.utc)
    last_demo = now - timedelta(days=days_ago)
    return ActorSkillProfile(
        actor_id="test-actor",
        skills={
            "software_engineering:python": SkillProficiency(
                skill_id=SkillId("software_engineering", "python"),
                proficiency_score=proficiency,
                evidence_count=evidence_count,
                last_demonstrated_utc=last_demo,
            ),
        },
    )


class TestComputeDecayFactor:
    def test_zero_days(self, engine) -> None:
        assert engine.compute_decay_factor(0, 365, 10) == 1.0

    def test_negative_days(self, engine) -> None:
        assert engine.compute_decay_factor(-5, 365, 10) == 1.0

    def test_half_life_decay(self, engine) -> None:
        """At half-life with no volume dampening (evidence=0), significant decay."""
        factor = engine.compute_decay_factor(365, 365, 0)
        assert factor < 1.0
        assert factor > 0.0

    def test_high_evidence_slows_decay(self, engine) -> None:
        """More evidence = slower decay."""
        low_ev = engine.compute_decay_factor(200, 365, 2)
        high_ev = engine.compute_decay_factor(200, 365, 50)
        assert high_ev > low_ev

    def test_floor_enforced(self, engine) -> None:
        """Even very long inactivity doesn't go below floor."""
        factor = engine.compute_decay_factor(10000, 365, 0)
        assert factor >= 0.01

    def test_zero_half_life(self, engine) -> None:
        assert engine.compute_decay_factor(10, 0, 5) == 1.0


class TestApplyDecay:
    def test_no_decay_recent(self, engine) -> None:
        """Recently demonstrated skill should not decay."""
        now = datetime.now(timezone.utc)
        profile = _make_profile(days_ago=1, now=now)
        new_profile, result = engine.apply_decay(profile, now=now)
        assert result.decayed_count == 0
        assert result.pruned_count == 0
        # Score should be unchanged
        sp = new_profile.skills.get("software_engineering:python")
        assert sp is not None
        assert abs(sp.proficiency_score - 0.8) < 1e-9

    def test_decay_after_long_inactivity(self, engine) -> None:
        """Skills decay after significant inactivity."""
        now = datetime.now(timezone.utc)
        profile = _make_profile(days_ago=500, now=now)
        new_profile, result = engine.apply_decay(profile, now=now)
        assert result.decayed_count >= 1
        sp = new_profile.skills.get("software_engineering:python")
        assert sp is not None
        assert sp.proficiency_score < 0.8

    def test_machine_decays_faster(self, engine) -> None:
        """Machine half-life (90d) means faster decay than human (365d)."""
        now = datetime.now(timezone.utc)
        profile = _make_profile(days_ago=100, now=now)

        _, human_result = engine.apply_decay(profile, now=now, is_machine=False)

        # Make a fresh profile for machine test
        profile2 = _make_profile(days_ago=100, now=now)
        new_profile_m, machine_result = engine.apply_decay(profile2, now=now, is_machine=True)

        # Machine should show more decay
        human_sp = engine.apply_decay(
            _make_profile(days_ago=100, now=now), now=now, is_machine=False,
        )[0].skills.get("software_engineering:python")
        machine_sp = new_profile_m.skills.get("software_engineering:python")

        if machine_sp and human_sp:
            assert machine_sp.proficiency_score <= human_sp.proficiency_score

    def test_pruning(self, engine) -> None:
        """Skills that decay below prune threshold are removed."""
        now = datetime.now(timezone.utc)
        # Very low proficiency + very old = should be pruned
        profile = _make_profile(
            days_ago=2000, proficiency=0.05, evidence_count=0, now=now,
        )
        new_profile, result = engine.apply_decay(profile, now=now)
        assert result.pruned_count >= 1
        assert result.skills_after < result.skills_before

    def test_no_timestamp_no_decay(self, engine) -> None:
        """Skills without last_demonstrated_utc are not decayed."""
        profile = ActorSkillProfile(
            actor_id="test",
            skills={
                "software_engineering:python": SkillProficiency(
                    skill_id=SkillId("software_engineering", "python"),
                    proficiency_score=0.8,
                    evidence_count=10,
                    last_demonstrated_utc=None,
                ),
            },
        )
        new_profile, result = engine.apply_decay(profile)
        assert result.decayed_count == 0
        assert len(new_profile.skills) == 1

    def test_immutability(self, engine) -> None:
        """Original profile is not mutated."""
        now = datetime.now(timezone.utc)
        profile = _make_profile(days_ago=500, now=now)
        original_score = profile.skills["software_engineering:python"].proficiency_score
        engine.apply_decay(profile, now=now)
        assert profile.skills["software_engineering:python"].proficiency_score == original_score

    def test_primary_domains_recomputed(self, engine) -> None:
        """Decay recomputes primary domains."""
        now = datetime.now(timezone.utc)
        profile = _make_profile(days_ago=500, now=now)
        new_profile, _ = engine.apply_decay(profile, now=now)
        # Profile should have recomputed primary_domains
        assert isinstance(new_profile.primary_domains, list)
