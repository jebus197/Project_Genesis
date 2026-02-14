"""Tests for skill outcome updater — proficiency updates from mission outcomes."""

import pytest
from pathlib import Path

from genesis.models.mission import (
    DomainType,
    Mission,
    MissionClass,
    MissionState,
    RiskTier,
)
from genesis.models.skill import (
    ActorSkillProfile,
    SkillId,
    SkillProficiency,
    SkillRequirement,
)
from genesis.skills.outcome_updater import SkillOutcomeUpdater
from genesis.policy.resolver import PolicyResolver

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"

PYTHON_ID = SkillId("software_engineering", "python")
TESTING_ID = SkillId("software_engineering", "testing")


@pytest.fixture
def resolver():
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def updater(resolver):
    return SkillOutcomeUpdater(resolver)


_DEFAULT_REQUIREMENTS = [
    SkillRequirement(skill_id=PYTHON_ID, minimum_proficiency=0.3),
]


def _make_mission(
    tier: RiskTier = RiskTier.R0,
    state: MissionState = MissionState.APPROVED,
    requirements: list[SkillRequirement] | None = None,
) -> Mission:
    reqs = _DEFAULT_REQUIREMENTS if requirements is None else requirements
    return Mission(
        mission_id="m-001",
        mission_title="Test Mission",
        mission_class=MissionClass.DOCUMENTATION_UPDATE,
        risk_tier=tier,
        domain_type=DomainType.OBJECTIVE,
        state=state,
        worker_id="worker-1",
        skill_requirements=reqs,
    )


def _make_profile(
    proficiency: float = 0.5,
    evidence_count: int = 5,
) -> ActorSkillProfile:
    return ActorSkillProfile(
        actor_id="worker-1",
        skills={
            PYTHON_ID.canonical: SkillProficiency(
                skill_id=PYTHON_ID,
                proficiency_score=proficiency,
                evidence_count=evidence_count,
                source="outcome_derived",
            ),
        },
    )


class TestApprovalBoost:
    def test_approval_increases_proficiency(self, updater) -> None:
        profile = _make_profile(proficiency=0.5)
        mission = _make_mission()
        result = updater.update_from_outcome(profile, mission, approved=True)
        assert result.skills_updated == 1
        assert result.updates[0].new_proficiency > 0.5

    def test_higher_tier_bigger_boost(self, updater) -> None:
        """R2 missions give bigger boost than R0."""
        p1 = _make_profile(proficiency=0.5)
        p2 = _make_profile(proficiency=0.5)

        m_r0 = _make_mission(tier=RiskTier.R0)
        m_r2 = _make_mission(tier=RiskTier.R2)

        r0_result = updater.update_from_outcome(p1, m_r0, approved=True)
        r2_result = updater.update_from_outcome(p2, m_r2, approved=True)

        assert r2_result.updates[0].delta > r0_result.updates[0].delta

    def test_diminishing_returns_near_ceiling(self, updater) -> None:
        """Boost is smaller when already near 1.0."""
        low_profile = _make_profile(proficiency=0.3)
        high_profile = _make_profile(proficiency=0.9)

        mission = _make_mission()
        r_low = updater.update_from_outcome(low_profile, mission, approved=True)
        r_high = updater.update_from_outcome(high_profile, mission, approved=True)

        assert r_low.updates[0].delta > r_high.updates[0].delta

    def test_capped_at_one(self, updater) -> None:
        profile = _make_profile(proficiency=0.99)
        mission = _make_mission()
        result = updater.update_from_outcome(profile, mission, approved=True)
        assert result.updates[0].new_proficiency <= 1.0


class TestRejectionPenalty:
    def test_rejection_decreases_proficiency(self, updater) -> None:
        profile = _make_profile(proficiency=0.5)
        mission = _make_mission()
        result = updater.update_from_outcome(profile, mission, approved=False)
        assert result.skills_updated == 1
        assert result.updates[0].new_proficiency < 0.5

    def test_rejection_smaller_than_approval(self, updater) -> None:
        """Rejection penalty is smaller than approval boost."""
        p_approve = _make_profile(proficiency=0.5)
        p_reject = _make_profile(proficiency=0.5)
        mission = _make_mission()

        r_approve = updater.update_from_outcome(p_approve, mission, approved=True)
        r_reject = updater.update_from_outcome(p_reject, mission, approved=False)

        assert abs(r_reject.updates[0].delta) < abs(r_approve.updates[0].delta)

    def test_rejection_floored_at_zero(self, updater) -> None:
        profile = _make_profile(proficiency=0.01)
        mission = _make_mission()
        result = updater.update_from_outcome(profile, mission, approved=False)
        assert result.updates[0].new_proficiency >= 0.0


class TestNewSkillCreation:
    def test_creates_new_skill_on_approval(self, updater) -> None:
        """If worker doesn't have the required skill, create it."""
        profile = ActorSkillProfile(actor_id="worker-1", skills={})
        mission = _make_mission()
        result = updater.update_from_outcome(profile, mission, approved=True)
        assert result.skills_updated == 1
        assert PYTHON_ID.canonical in profile.skills


class TestEvidenceTracking:
    def test_evidence_count_incremented(self, updater) -> None:
        profile = _make_profile(evidence_count=5)
        mission = _make_mission()
        updater.update_from_outcome(profile, mission, approved=True)
        sp = profile.skills[PYTHON_ID.canonical]
        assert sp.evidence_count == 6

    def test_source_is_outcome_derived(self, updater) -> None:
        profile = _make_profile()
        mission = _make_mission()
        updater.update_from_outcome(profile, mission, approved=True)
        sp = profile.skills[PYTHON_ID.canonical]
        assert sp.source == "outcome_derived"


class TestMultiSkillUpdate:
    def test_multiple_skills_updated(self, updater) -> None:
        """All mission skill requirements get updated."""
        profile = ActorSkillProfile(
            actor_id="worker-1",
            skills={
                PYTHON_ID.canonical: SkillProficiency(
                    skill_id=PYTHON_ID,
                    proficiency_score=0.5,
                    evidence_count=5,
                ),
                TESTING_ID.canonical: SkillProficiency(
                    skill_id=TESTING_ID,
                    proficiency_score=0.4,
                    evidence_count=3,
                ),
            },
        )
        mission = _make_mission(requirements=[
            SkillRequirement(skill_id=PYTHON_ID, minimum_proficiency=0.3),
            SkillRequirement(skill_id=TESTING_ID, minimum_proficiency=0.2),
        ])
        result = updater.update_from_outcome(profile, mission, approved=True)
        assert result.skills_updated == 2

    def test_no_requirements_no_update(self, updater) -> None:
        profile = _make_profile()
        mission = _make_mission(requirements=[])
        result = updater.update_from_outcome(profile, mission, approved=True)
        assert result.skills_updated == 0
