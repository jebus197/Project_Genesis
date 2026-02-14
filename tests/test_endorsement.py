"""Tests for endorsement engine — peer endorsement with diminishing returns."""

import pytest
from pathlib import Path

from genesis.models.skill import (
    ActorSkillProfile,
    SkillId,
    SkillProficiency,
)
from genesis.models.trust import ActorKind, TrustRecord
from genesis.skills.endorsement import EndorsementEngine
from genesis.policy.resolver import PolicyResolver

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"

PYTHON_ID = SkillId("software_engineering", "python")


@pytest.fixture
def resolver():
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def engine(resolver):
    return EndorsementEngine(resolver)


def _make_profile(
    actor_id: str,
    skill_id: SkillId = PYTHON_ID,
    proficiency: float = 0.6,
    evidence_count: int = 5,
    endorsement_count: int = 0,
) -> ActorSkillProfile:
    return ActorSkillProfile(
        actor_id=actor_id,
        skills={
            skill_id.canonical: SkillProficiency(
                skill_id=skill_id,
                proficiency_score=proficiency,
                evidence_count=evidence_count,
                endorsement_count=endorsement_count,
                source="outcome_derived",
            ),
        },
    )


def _make_trust(actor_id: str, score: float = 0.7) -> TrustRecord:
    return TrustRecord(
        actor_id=actor_id,
        actor_kind=ActorKind.HUMAN,
        score=score,
    )


class TestEndorsementValidation:
    def test_self_endorsement_blocked(self, engine) -> None:
        profile = _make_profile("alice")
        trust = _make_trust("alice")
        result = engine.endorse(
            "alice", profile, trust, profile, PYTHON_ID,
        )
        assert not result.success
        assert "Self-endorsement" in result.errors[0]

    def test_endorser_must_have_skill(self, engine) -> None:
        endorser_profile = ActorSkillProfile(actor_id="endorser", skills={})
        endorser_trust = _make_trust("endorser")
        target_profile = _make_profile("target")

        result = engine.endorse(
            "endorser", endorser_profile, endorser_trust,
            target_profile, PYTHON_ID,
        )
        assert not result.success
        assert "does not have skill" in result.errors[0]

    def test_endorser_below_min_proficiency(self, engine) -> None:
        endorser_profile = _make_profile("endorser", proficiency=0.2)
        endorser_trust = _make_trust("endorser")
        target_profile = _make_profile("target")

        result = engine.endorse(
            "endorser", endorser_profile, endorser_trust,
            target_profile, PYTHON_ID,
        )
        assert not result.success
        assert "below minimum" in result.errors[0]

    def test_target_must_have_skill(self, engine) -> None:
        """Endorsement can only boost existing skills, not create them."""
        endorser_profile = _make_profile("endorser")
        endorser_trust = _make_trust("endorser")
        target_profile = ActorSkillProfile(actor_id="target", skills={})

        result = engine.endorse(
            "endorser", endorser_profile, endorser_trust,
            target_profile, PYTHON_ID,
        )
        assert not result.success
        assert "no existing skill" in result.errors[0]


class TestEndorsementSuccess:
    def test_valid_endorsement(self, engine) -> None:
        endorser_profile = _make_profile("endorser", proficiency=0.8)
        endorser_trust = _make_trust("endorser", score=0.7)
        target_profile = _make_profile("target", proficiency=0.6)

        result = engine.endorse(
            "endorser", endorser_profile, endorser_trust,
            target_profile, PYTHON_ID,
        )
        assert result.success
        assert result.new_proficiency > result.old_proficiency
        assert result.boost_applied > 0

    def test_endorsement_increments_count(self, engine) -> None:
        endorser_profile = _make_profile("endorser", proficiency=0.8)
        endorser_trust = _make_trust("endorser")
        target_profile = _make_profile("target")

        engine.endorse(
            "endorser", endorser_profile, endorser_trust,
            target_profile, PYTHON_ID,
        )
        sp = target_profile.skills[PYTHON_ID.canonical]
        assert sp.endorsement_count == 1

    def test_endorsement_capped_at_one(self, engine) -> None:
        """Proficiency cannot exceed 1.0 even with many endorsements."""
        endorser_profile = _make_profile("endorser", proficiency=0.9)
        endorser_trust = _make_trust("endorser", score=1.0)
        target_profile = _make_profile("target", proficiency=0.99)

        result = engine.endorse(
            "endorser", endorser_profile, endorser_trust,
            target_profile, PYTHON_ID,
        )
        assert result.success
        assert result.new_proficiency <= 1.0


class TestDiminishingReturns:
    def test_diminishing_returns(self, engine) -> None:
        """Each subsequent endorsement has smaller effect."""
        endorser_profile = _make_profile("endorser", proficiency=0.8)
        endorser_trust = _make_trust("endorser", score=0.7)

        # First endorsement
        target1 = _make_profile("target", proficiency=0.5, endorsement_count=0)
        r1 = engine.endorse(
            "endorser", endorser_profile, endorser_trust,
            target1, PYTHON_ID,
        )

        # Second endorsement (on a profile already with 1 endorsement)
        target2 = _make_profile("target", proficiency=0.5, endorsement_count=1)
        r2 = engine.endorse(
            "endorser", endorser_profile, endorser_trust,
            target2, PYTHON_ID,
        )

        # Third endorsement
        target3 = _make_profile("target", proficiency=0.5, endorsement_count=2)
        r3 = engine.endorse(
            "endorser", endorser_profile, endorser_trust,
            target3, PYTHON_ID,
        )

        assert r1.boost_applied > r2.boost_applied > r3.boost_applied

    def test_endorser_trust_affects_boost(self, engine) -> None:
        """Higher endorser trust → larger boost."""
        target1 = _make_profile("target", proficiency=0.5)
        target2 = _make_profile("target2", proficiency=0.5)

        high_trust_endorser = _make_profile("e1", proficiency=0.8)
        high_trust = _make_trust("e1", score=0.9)

        low_trust_endorser = _make_profile("e2", proficiency=0.8)
        low_trust = _make_trust("e2", score=0.3)

        r1 = engine.endorse(
            "e1", high_trust_endorser, high_trust, target1, PYTHON_ID,
        )
        r2 = engine.endorse(
            "e2", low_trust_endorser, low_trust, target2, PYTHON_ID,
        )
        assert r1.boost_applied > r2.boost_applied

    def test_zero_trust_endorser_no_boost(self, engine) -> None:
        """Endorser with zero trust gives zero boost."""
        endorser = _make_profile("endorser", proficiency=0.8)
        trust = _make_trust("endorser", score=0.0)
        target = _make_profile("target")

        result = engine.endorse(
            "endorser", endorser, trust, target, PYTHON_ID,
        )
        assert result.success
        assert result.boost_applied == 0.0
