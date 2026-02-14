"""Unit tests for skill matching engine — relevance scoring and filtering.

Tests SkillMatchEngine: compute_relevance, meets_minimum_relevance,
meets_required_skills.
"""

import pytest
from pathlib import Path

from genesis.models.domain_trust import DomainTrustScore
from genesis.models.skill import (
    ActorSkillProfile,
    SkillId,
    SkillProficiency,
    SkillRequirement,
)
from genesis.models.trust import ActorKind, TrustRecord
from genesis.policy.resolver import PolicyResolver
from genesis.skills.matching import SkillMatchEngine

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def resolver():
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def engine(resolver):
    return SkillMatchEngine(resolver)


@pytest.fixture
def python_profile():
    """Actor skilled in Python (software_engineering domain)."""
    return ActorSkillProfile(
        actor_id="worker-1",
        skills={
            "software_engineering:python": SkillProficiency(
                skill_id=SkillId("software_engineering", "python"),
                proficiency_score=0.9,
                evidence_count=20,
            ),
        },
    )


@pytest.fixture
def multi_domain_profile():
    """Actor skilled across software_engineering and data_science."""
    return ActorSkillProfile(
        actor_id="worker-2",
        skills={
            "software_engineering:python": SkillProficiency(
                skill_id=SkillId("software_engineering", "python"),
                proficiency_score=0.9,
                evidence_count=20,
            ),
            "software_engineering:rust": SkillProficiency(
                skill_id=SkillId("software_engineering", "rust"),
                proficiency_score=0.6,
                evidence_count=5,
            ),
            "data_science:statistical_modeling": SkillProficiency(
                skill_id=SkillId("data_science", "statistical_modeling"),
                proficiency_score=0.7,
                evidence_count=10,
            ),
        },
    )


@pytest.fixture
def python_requirement():
    return [
        SkillRequirement(
            skill_id=SkillId("software_engineering", "python"),
            minimum_proficiency=0.5,
        ),
    ]


@pytest.fixture
def trust_record_with_domain():
    return TrustRecord(
        actor_id="worker-1",
        actor_kind=ActorKind.HUMAN,
        score=0.7,
        domain_scores={
            "software_engineering": DomainTrustScore(
                domain="software_engineering",
                score=0.8,
                mission_count=10,
            ),
        },
    )


# ===================================================================
# compute_relevance
# ===================================================================

class TestComputeRelevance:
    def test_no_requirements_returns_one(self, engine, python_profile) -> None:
        """No requirements means everyone is relevant."""
        assert engine.compute_relevance(python_profile, []) == 1.0

    def test_no_profile_returns_zero(self, engine, python_requirement) -> None:
        """No profile means zero relevance."""
        assert engine.compute_relevance(None, python_requirement) == 0.0

    def test_matching_skill(self, engine, python_profile, python_requirement) -> None:
        """Actor with matching skill should have high relevance."""
        relevance = engine.compute_relevance(python_profile, python_requirement)
        assert relevance > 0.5

    def test_missing_skill_low_relevance(self, engine, python_requirement) -> None:
        """Actor missing required skill has low relevance."""
        empty_profile = ActorSkillProfile(actor_id="empty")
        relevance = engine.compute_relevance(empty_profile, python_requirement)
        assert relevance < 0.3

    def test_domain_trust_boosts_relevance(
        self, engine, python_profile, python_requirement, trust_record_with_domain,
    ) -> None:
        """Domain trust component should boost relevance."""
        without_trust = engine.compute_relevance(python_profile, python_requirement)
        with_trust = engine.compute_relevance(
            python_profile, python_requirement, trust_record_with_domain,
        )
        assert with_trust >= without_trust

    def test_partial_match(self, engine, python_profile) -> None:
        """Actor matching some but not all requirements gets partial relevance."""
        requirements = [
            SkillRequirement(
                skill_id=SkillId("software_engineering", "python"),
                minimum_proficiency=0.5,
            ),
            SkillRequirement(
                skill_id=SkillId("software_engineering", "rust"),
                minimum_proficiency=0.5,
            ),
        ]
        relevance = engine.compute_relevance(python_profile, requirements)
        # Has python but not rust → partial match
        assert 0.2 < relevance < 0.8

    def test_multi_domain_match(
        self, engine, multi_domain_profile,
    ) -> None:
        """Actor with skills across multiple domains matches multi-domain mission."""
        requirements = [
            SkillRequirement(
                skill_id=SkillId("software_engineering", "python"),
                minimum_proficiency=0.5,
            ),
            SkillRequirement(
                skill_id=SkillId("data_science", "statistical_modeling"),
                minimum_proficiency=0.3,
            ),
        ]
        relevance = engine.compute_relevance(multi_domain_profile, requirements)
        assert relevance > 0.5

    def test_clamped_to_one(self, engine) -> None:
        """Relevance should never exceed 1.0."""
        profile = ActorSkillProfile(
            actor_id="super",
            skills={
                "software_engineering:python": SkillProficiency(
                    skill_id=SkillId("software_engineering", "python"),
                    proficiency_score=1.0,
                    evidence_count=100,
                ),
            },
        )
        trust = TrustRecord(
            actor_id="super",
            actor_kind=ActorKind.HUMAN,
            score=1.0,
            domain_scores={
                "software_engineering": DomainTrustScore(
                    domain="software_engineering", score=1.0, mission_count=50,
                ),
            },
        )
        requirements = [
            SkillRequirement(
                skill_id=SkillId("software_engineering", "python"),
                minimum_proficiency=0.1,
            ),
        ]
        relevance = engine.compute_relevance(profile, requirements, trust)
        assert relevance <= 1.0


# ===================================================================
# meets_minimum_relevance
# ===================================================================

class TestMeetsMinimumRelevance:
    def test_no_requirements_always_meets(self, engine) -> None:
        assert engine.meets_minimum_relevance(None, []) is True

    def test_skilled_actor_meets(
        self, engine, python_profile, python_requirement,
    ) -> None:
        assert engine.meets_minimum_relevance(python_profile, python_requirement) is True

    def test_unskilled_actor_fails(self, engine, python_requirement) -> None:
        empty = ActorSkillProfile(actor_id="empty")
        assert engine.meets_minimum_relevance(empty, python_requirement) is False

    def test_none_profile_with_requirements_fails(
        self, engine, python_requirement,
    ) -> None:
        assert engine.meets_minimum_relevance(None, python_requirement) is False


# ===================================================================
# meets_required_skills
# ===================================================================

class TestMeetsRequiredSkills:
    def test_no_requirements(self, engine) -> None:
        assert engine.meets_required_skills(None, []) is True

    def test_has_required_skill(self, engine, python_profile) -> None:
        reqs = [
            SkillRequirement(
                skill_id=SkillId("software_engineering", "python"),
                minimum_proficiency=0.5,
                required=True,
            ),
        ]
        assert engine.meets_required_skills(python_profile, reqs) is True

    def test_missing_required_skill(self, engine, python_profile) -> None:
        reqs = [
            SkillRequirement(
                skill_id=SkillId("software_engineering", "rust"),
                minimum_proficiency=0.5,
                required=True,
            ),
        ]
        assert engine.meets_required_skills(python_profile, reqs) is False

    def test_below_minimum_proficiency(self, engine) -> None:
        profile = ActorSkillProfile(
            actor_id="low",
            skills={
                "software_engineering:python": SkillProficiency(
                    skill_id=SkillId("software_engineering", "python"),
                    proficiency_score=0.2,
                    evidence_count=1,
                ),
            },
        )
        reqs = [
            SkillRequirement(
                skill_id=SkillId("software_engineering", "python"),
                minimum_proficiency=0.5,
                required=True,
            ),
        ]
        assert engine.meets_required_skills(profile, reqs) is False

    def test_optional_skill_missing_ok(self, engine) -> None:
        empty = ActorSkillProfile(actor_id="empty")
        reqs = [
            SkillRequirement(
                skill_id=SkillId("software_engineering", "python"),
                minimum_proficiency=0.5,
                required=False,
            ),
        ]
        assert engine.meets_required_skills(empty, reqs) is True

    def test_none_profile_all_optional(self, engine) -> None:
        reqs = [
            SkillRequirement(
                skill_id=SkillId("software_engineering", "python"),
                required=False,
            ),
        ]
        assert engine.meets_required_skills(None, reqs) is True

    def test_none_profile_any_required_fails(self, engine) -> None:
        reqs = [
            SkillRequirement(
                skill_id=SkillId("software_engineering", "python"),
                required=True,
            ),
        ]
        assert engine.meets_required_skills(None, reqs) is False
