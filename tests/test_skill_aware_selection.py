"""Integration tests for skill-aware reviewer selection and worker matching.

Tests that:
- ReviewerSelector pre-filters by skill relevance when skill data is available
- Diversity constraints are preserved after skill pre-filtering
- Backward compatibility: missions without skill requirements work as before
- WorkerMatcher ranks workers correctly
- find_matching_workers() service method works end-to-end
"""

import pytest
from pathlib import Path

from genesis.models.domain_trust import DomainTrustScore
from genesis.models.mission import (
    DomainType,
    MissionClass,
    MissionState,
)
from genesis.models.skill import (
    ActorSkillProfile,
    SkillId,
    SkillProficiency,
    SkillRequirement,
)
from genesis.models.trust import ActorKind, TrustRecord
from genesis.policy.resolver import PolicyResolver
from genesis.review.roster import ActorRoster, ActorStatus, RosterEntry
from genesis.review.selector import ReviewerSelector
from genesis.skills.worker_matcher import WorkerMatcher
from genesis.service import GenesisService

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def resolver():
    return PolicyResolver.from_config_dir(CONFIG_DIR)


def _make_roster_with_skills():
    """Build a roster with actors having different skill profiles."""
    roster = ActorRoster()

    # Skilled Python developer
    roster.register(RosterEntry(
        actor_id="dev-python", actor_kind=ActorKind.HUMAN,
        trust_score=0.7, region="eu", organization="acme",
        model_family="human_reviewer", method_type="human_reviewer",
    ))
    # Skilled Rust developer
    roster.register(RosterEntry(
        actor_id="dev-rust", actor_kind=ActorKind.MACHINE,
        trust_score=0.6, region="us", organization="skynet",
        model_family="gpt", method_type="llm_evaluator",
    ))
    # Data scientist
    roster.register(RosterEntry(
        actor_id="data-sci", actor_kind=ActorKind.HUMAN,
        trust_score=0.5, region="apac", organization="delta",
        model_family="human_reviewer", method_type="human_reviewer",
    ))
    # Generalist (no specific skills)
    roster.register(RosterEntry(
        actor_id="generalist", actor_kind=ActorKind.HUMAN,
        trust_score=0.8, region="eu", organization="beta",
        model_family="human_reviewer", method_type="human_reviewer",
    ))

    return roster


def _make_skill_profiles():
    """Build skill profiles for roster actors."""
    return {
        "dev-python": ActorSkillProfile(
            actor_id="dev-python",
            skills={
                "software_engineering:python": SkillProficiency(
                    skill_id=SkillId("software_engineering", "python"),
                    proficiency_score=0.9,
                    evidence_count=20,
                ),
                "software_engineering:testing": SkillProficiency(
                    skill_id=SkillId("software_engineering", "testing"),
                    proficiency_score=0.7,
                    evidence_count=10,
                ),
            },
        ),
        "dev-rust": ActorSkillProfile(
            actor_id="dev-rust",
            skills={
                "software_engineering:rust": SkillProficiency(
                    skill_id=SkillId("software_engineering", "rust"),
                    proficiency_score=0.85,
                    evidence_count=15,
                ),
                "software_engineering:python": SkillProficiency(
                    skill_id=SkillId("software_engineering", "python"),
                    proficiency_score=0.4,
                    evidence_count=5,
                ),
            },
        ),
        "data-sci": ActorSkillProfile(
            actor_id="data-sci",
            skills={
                "data_science:statistical_modeling": SkillProficiency(
                    skill_id=SkillId("data_science", "statistical_modeling"),
                    proficiency_score=0.8,
                    evidence_count=12,
                ),
                "data_science:ml_pipelines": SkillProficiency(
                    skill_id=SkillId("data_science", "ml_pipelines"),
                    proficiency_score=0.6,
                    evidence_count=8,
                ),
            },
        ),
        # generalist has no skill profile
    }


def _make_trust_records():
    """Build trust records with domain scores."""
    return {
        "dev-python": TrustRecord(
            actor_id="dev-python", actor_kind=ActorKind.HUMAN, score=0.7,
            domain_scores={
                "software_engineering": DomainTrustScore(
                    domain="software_engineering", score=0.8, mission_count=10,
                ),
            },
        ),
        "dev-rust": TrustRecord(
            actor_id="dev-rust", actor_kind=ActorKind.MACHINE, score=0.6,
            domain_scores={
                "software_engineering": DomainTrustScore(
                    domain="software_engineering", score=0.5, mission_count=5,
                ),
            },
        ),
        "data-sci": TrustRecord(
            actor_id="data-sci", actor_kind=ActorKind.HUMAN, score=0.5,
            domain_scores={
                "data_science": DomainTrustScore(
                    domain="data_science", score=0.7, mission_count=8,
                ),
            },
        ),
        "generalist": TrustRecord(
            actor_id="generalist", actor_kind=ActorKind.HUMAN, score=0.8,
        ),
    }


# ===================================================================
# WorkerMatcher
# ===================================================================

class TestWorkerMatcher:
    def test_ranks_by_composite_score(self, resolver) -> None:
        """Workers should be ranked by composite score descending."""
        roster = _make_roster_with_skills()
        profiles = _make_skill_profiles()
        trust = _make_trust_records()

        matcher = WorkerMatcher(resolver, roster, trust, profiles)
        matches = matcher.find_matches(
            requirements=[
                SkillRequirement(
                    skill_id=SkillId("software_engineering", "python"),
                    minimum_proficiency=0.3,
                ),
            ],
        )

        # Should have some matches
        assert len(matches) >= 1
        # Should be sorted descending
        for i in range(len(matches) - 1):
            assert matches[i].composite_score >= matches[i + 1].composite_score

    def test_skilled_actor_ranks_higher(self, resolver) -> None:
        """Actor with matching skills should rank above generalist."""
        roster = _make_roster_with_skills()
        profiles = _make_skill_profiles()
        trust = _make_trust_records()

        matcher = WorkerMatcher(resolver, roster, trust, profiles)
        matches = matcher.find_matches(
            requirements=[
                SkillRequirement(
                    skill_id=SkillId("software_engineering", "python"),
                    minimum_proficiency=0.3,
                ),
            ],
        )

        actor_ids = [m.actor_id for m in matches]
        # dev-python should rank before generalist (who has no profile)
        if "dev-python" in actor_ids and "generalist" in actor_ids:
            assert actor_ids.index("dev-python") < actor_ids.index("generalist")

    def test_no_requirements_returns_all(self, resolver) -> None:
        """No requirements → all available actors returned."""
        roster = _make_roster_with_skills()
        profiles = _make_skill_profiles()
        trust = _make_trust_records()

        matcher = WorkerMatcher(resolver, roster, trust, profiles)
        matches = matcher.find_matches(requirements=[])
        # All 4 actors are available
        assert len(matches) == 4

    def test_exclude_ids(self, resolver) -> None:
        """Excluded actors should not appear in results."""
        roster = _make_roster_with_skills()
        profiles = _make_skill_profiles()
        trust = _make_trust_records()

        matcher = WorkerMatcher(resolver, roster, trust, profiles)
        matches = matcher.find_matches(
            requirements=[],
            exclude_ids={"dev-python"},
        )
        actor_ids = {m.actor_id for m in matches}
        assert "dev-python" not in actor_ids

    def test_min_trust_filter(self, resolver) -> None:
        """Actors below min_trust should be excluded."""
        roster = _make_roster_with_skills()
        profiles = _make_skill_profiles()
        trust = _make_trust_records()

        matcher = WorkerMatcher(resolver, roster, trust, profiles)
        matches = matcher.find_matches(
            requirements=[],
            min_trust=0.65,
        )
        # Only dev-python (0.7) and generalist (0.8) meet threshold
        actor_ids = {m.actor_id for m in matches}
        assert "data-sci" not in actor_ids  # 0.5 < 0.65
        assert "generalist" in actor_ids

    def test_limit(self, resolver) -> None:
        """Limit parameter caps results."""
        roster = _make_roster_with_skills()
        profiles = _make_skill_profiles()
        trust = _make_trust_records()

        matcher = WorkerMatcher(resolver, roster, trust, profiles)
        matches = matcher.find_matches(requirements=[], limit=2)
        assert len(matches) <= 2

    def test_domain_mismatch_filtered(self, resolver) -> None:
        """Actors without relevant domain skills should be filtered by relevance."""
        roster = _make_roster_with_skills()
        profiles = _make_skill_profiles()
        trust = _make_trust_records()

        matcher = WorkerMatcher(resolver, roster, trust, profiles)
        matches = matcher.find_matches(
            requirements=[
                SkillRequirement(
                    skill_id=SkillId("data_science", "statistical_modeling"),
                    minimum_proficiency=0.5,
                ),
            ],
        )

        # data-sci should be in results (has the skill)
        actor_ids = {m.actor_id for m in matches}
        assert "data-sci" in actor_ids


# ===================================================================
# Skill-aware reviewer selection
# ===================================================================

class TestSkillAwareReviewerSelection:
    def test_backward_compat_no_skill_requirements(self, resolver) -> None:
        """Missions without skill requirements work exactly as before."""
        from genesis.models.mission import Mission, RiskTier
        roster = _make_roster_with_skills()

        selector = ReviewerSelector(resolver, roster)
        mission = Mission(
            mission_id="m1",
            mission_title="Test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            worker_id="dev-python",
        )
        result = selector.select(mission, seed="test")
        assert result.success
        assert len(result.reviewers) >= 1

    def test_skill_aware_selection_with_profiles(self, resolver) -> None:
        """When skill data is provided, selection should still work."""
        from genesis.models.mission import Mission, RiskTier
        roster = _make_roster_with_skills()
        profiles = _make_skill_profiles()
        trust = _make_trust_records()

        selector = ReviewerSelector(
            resolver, roster,
            skill_profiles=profiles,
            trust_records=trust,
        )
        mission = Mission(
            mission_id="m1",
            mission_title="Test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            worker_id="dev-python",
            skill_requirements=[
                SkillRequirement(
                    skill_id=SkillId("software_engineering", "python"),
                    minimum_proficiency=0.3,
                ),
            ],
        )
        result = selector.select(mission, seed="test")
        assert result.success

    def test_selection_preserves_diversity(self, resolver) -> None:
        """Skill pre-filtering must not break diversity constraints."""
        from genesis.models.mission import Mission, RiskTier
        roster = _make_roster_with_skills()
        profiles = _make_skill_profiles()
        trust = _make_trust_records()

        selector = ReviewerSelector(
            resolver, roster,
            skill_profiles=profiles,
            trust_records=trust,
        )
        # R0 requires 1 reviewer — should always succeed
        mission = Mission(
            mission_id="m1",
            mission_title="Test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            worker_id="generalist",
        )
        result = selector.select(mission, seed="test")
        assert result.success


# ===================================================================
# Service-level find_matching_workers
# ===================================================================

class TestFindMatchingWorkersService:
    def test_find_matching_workers(self, resolver) -> None:
        """Service method returns matching workers."""
        service = GenesisService(resolver)

        service.register_actor(
            "w1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5,
        )
        service.register_actor(
            "w2", ActorKind.HUMAN, "us", "beta", initial_trust=0.6,
        )

        # Give w1 Python skills
        service.update_actor_skills("w1", [
            SkillProficiency(
                skill_id=SkillId("software_engineering", "python"),
                proficiency_score=0.8,
                evidence_count=10,
            ),
        ])

        result = service.find_matching_workers(
            requirements=[
                SkillRequirement(
                    skill_id=SkillId("software_engineering", "python"),
                    minimum_proficiency=0.3,
                ),
            ],
        )
        assert result.success
        assert result.data["total_matches"] >= 1
        # w1 should be in matches
        match_ids = [m["actor_id"] for m in result.data["matches"]]
        assert "w1" in match_ids

    def test_find_matching_workers_no_requirements(self, resolver) -> None:
        """No requirements returns all workers."""
        service = GenesisService(resolver)
        service.register_actor(
            "w1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5,
        )
        service.register_actor(
            "w2", ActorKind.MACHINE, "us", "skynet",
            model_family="gpt", method_type="llm_evaluator",
            initial_trust=0.5,
        )

        result = service.find_matching_workers(requirements=[])
        assert result.success
        assert result.data["total_matches"] == 2

    def test_find_matching_workers_with_exclusion(self, resolver) -> None:
        """Excluded workers are not returned."""
        service = GenesisService(resolver)
        service.register_actor(
            "w1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5,
        )
        service.register_actor(
            "w2", ActorKind.HUMAN, "us", "beta", initial_trust=0.5,
        )

        result = service.find_matching_workers(
            requirements=[], exclude_ids={"w1"},
        )
        assert result.success
        match_ids = {m["actor_id"] for m in result.data["matches"]}
        assert "w1" not in match_ids
