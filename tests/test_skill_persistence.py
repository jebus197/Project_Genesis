"""Tests for skill profile persistence and mission skill requirement serialization.

Tests round-trip serialization through StateStore for:
- Actor skill profiles
- Mission skill requirements
- Backward compatibility (loading old data without skill fields)
"""

import pytest
from datetime import datetime, timezone
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
from genesis.models.trust import ActorKind
from genesis.persistence.state_store import StateStore
from genesis.policy.resolver import PolicyResolver
from genesis.service import GenesisService


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


# ===================================================================
# Skill profile round-trip
# ===================================================================

class TestSkillProfilePersistence:
    def test_save_and_load_empty(self, tmp_path: Path) -> None:
        """Empty profiles dict round-trips."""
        store = StateStore(tmp_path / "state.json")
        store.save_skill_profiles({})
        loaded = store.load_skill_profiles()
        assert loaded == {}

    def test_save_and_load_single_profile(self, tmp_path: Path) -> None:
        """A single profile with skills round-trips."""
        now = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        profile = ActorSkillProfile(
            actor_id="worker-1",
            skills={
                "software_engineering:python": SkillProficiency(
                    skill_id=SkillId("software_engineering", "python"),
                    proficiency_score=0.85,
                    evidence_count=15,
                    last_demonstrated_utc=now,
                    endorsement_count=2,
                    source="outcome_derived",
                ),
            },
            primary_domains=["software_engineering"],
            updated_utc=now,
        )
        profiles = {"worker-1": profile}

        store = StateStore(tmp_path / "state.json")
        store.save_skill_profiles(profiles)

        store2 = StateStore(tmp_path / "state.json")
        loaded = store2.load_skill_profiles()

        assert "worker-1" in loaded
        p = loaded["worker-1"]
        assert p.actor_id == "worker-1"
        assert len(p.skills) == 1

        sp = p.skills["software_engineering:python"]
        assert sp.proficiency_score == pytest.approx(0.85)
        assert sp.evidence_count == 15
        assert sp.last_demonstrated_utc == now
        assert sp.endorsement_count == 2
        assert sp.source == "outcome_derived"
        assert sp.skill_id.domain == "software_engineering"
        assert sp.skill_id.skill == "python"

        assert p.primary_domains == ["software_engineering"]
        assert p.updated_utc == now

    def test_save_and_load_multiple_profiles(self, tmp_path: Path) -> None:
        """Multiple profiles round-trip correctly."""
        profiles = {
            "a": ActorSkillProfile(
                actor_id="a",
                skills={
                    "data_science:ml_pipelines": SkillProficiency(
                        skill_id=SkillId("data_science", "ml_pipelines"),
                        proficiency_score=0.5,
                        evidence_count=3,
                    ),
                },
            ),
            "b": ActorSkillProfile(
                actor_id="b",
                skills={
                    "legal_analysis:contract_review": SkillProficiency(
                        skill_id=SkillId("legal_analysis", "contract_review"),
                        proficiency_score=0.7,
                        evidence_count=8,
                    ),
                },
            ),
        }

        store = StateStore(tmp_path / "state.json")
        store.save_skill_profiles(profiles)

        store2 = StateStore(tmp_path / "state.json")
        loaded = store2.load_skill_profiles()

        assert len(loaded) == 2
        assert loaded["a"].skills["data_science:ml_pipelines"].proficiency_score == pytest.approx(0.5)
        assert loaded["b"].skills["legal_analysis:contract_review"].proficiency_score == pytest.approx(0.7)

    def test_profile_without_timestamp(self, tmp_path: Path) -> None:
        """Profile with no timestamps round-trips (None values)."""
        profile = ActorSkillProfile(
            actor_id="worker-2",
            skills={
                "documentation:technical_writing": SkillProficiency(
                    skill_id=SkillId("documentation", "technical_writing"),
                    proficiency_score=0.3,
                    evidence_count=1,
                ),
            },
        )

        store = StateStore(tmp_path / "state.json")
        store.save_skill_profiles({"worker-2": profile})

        store2 = StateStore(tmp_path / "state.json")
        loaded = store2.load_skill_profiles()
        p = loaded["worker-2"]
        assert p.updated_utc is None
        sp = p.skills["documentation:technical_writing"]
        assert sp.last_demonstrated_utc is None


# ===================================================================
# Mission skill requirements round-trip
# ===================================================================

class TestMissionSkillRequirementPersistence:
    def test_mission_with_no_requirements_loads(self, tmp_path: Path) -> None:
        """Old missions without skill_requirements field load with empty list."""
        store = StateStore(tmp_path / "state.json")
        mission = Mission(
            mission_id="M-OLD",
            mission_title="Legacy Mission",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
        )
        store.save_missions({"M-OLD": mission})

        store2 = StateStore(tmp_path / "state.json")
        loaded = store2.load_missions()
        assert loaded["M-OLD"].skill_requirements == []

    def test_mission_with_requirements_round_trips(self, tmp_path: Path) -> None:
        """Mission skill requirements serialize and deserialize correctly."""
        reqs = [
            SkillRequirement(
                skill_id=SkillId("software_engineering", "python"),
                minimum_proficiency=0.5,
                required=True,
            ),
            SkillRequirement(
                skill_id=SkillId("data_science", "ml_pipelines"),
                minimum_proficiency=0.3,
                required=False,
            ),
        ]
        mission = Mission(
            mission_id="M-SKILL",
            mission_title="Skill Mission",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            skill_requirements=reqs,
        )

        store = StateStore(tmp_path / "state.json")
        store.save_missions({"M-SKILL": mission})

        store2 = StateStore(tmp_path / "state.json")
        loaded = store2.load_missions()
        m = loaded["M-SKILL"]
        assert len(m.skill_requirements) == 2

        r0 = m.skill_requirements[0]
        assert r0.skill_id.canonical == "software_engineering:python"
        assert r0.minimum_proficiency == pytest.approx(0.5)
        assert r0.required is True

        r1 = m.skill_requirements[1]
        assert r1.skill_id.canonical == "data_science:ml_pipelines"
        assert r1.minimum_proficiency == pytest.approx(0.3)
        assert r1.required is False


# ===================================================================
# Service-level skill management integration
# ===================================================================

class TestServiceSkillManagement:
    @pytest.fixture
    def service(self) -> GenesisService:
        resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
        svc = GenesisService(resolver)
        svc.open_epoch("skill-test-epoch")
        return svc

    def test_update_actor_skills(self, service: GenesisService) -> None:
        """Basic skill update on a registered actor."""
        service.register_actor(
            actor_id="worker-1",
            actor_kind=ActorKind.HUMAN,
            region="NA",
            organization="Org1",
        )
        skills = [
            SkillProficiency(
                skill_id=SkillId("software_engineering", "python"),
                proficiency_score=0.8,
                evidence_count=10,
            ),
        ]
        result = service.update_actor_skills("worker-1", skills)
        assert result.success
        assert result.data["skill_count"] == 1
        assert "software_engineering" in result.data["primary_domains"]

    def test_update_nonexistent_actor_fails(self, service: GenesisService) -> None:
        result = service.update_actor_skills("ghost", [])
        assert not result.success
        assert "not found" in result.errors[0].lower()

    def test_update_with_invalid_skill_fails(self, service: GenesisService) -> None:
        """Invalid skill against taxonomy is rejected."""
        service.register_actor(
            actor_id="worker-2",
            actor_kind=ActorKind.HUMAN,
            region="NA",
            organization="Org1",
        )
        skills = [
            SkillProficiency(
                skill_id=SkillId("nonexistent_domain", "fake_skill"),
                proficiency_score=0.5,
                evidence_count=0,
            ),
        ]
        result = service.update_actor_skills("worker-2", skills)
        assert not result.success
        assert "Unknown domain" in result.errors[0]

    def test_get_actor_skills(self, service: GenesisService) -> None:
        service.register_actor(
            actor_id="worker-3",
            actor_kind=ActorKind.HUMAN,
            region="EU",
            organization="Org2",
        )
        skills = [
            SkillProficiency(
                skill_id=SkillId("documentation", "technical_writing"),
                proficiency_score=0.6,
                evidence_count=4,
            ),
        ]
        service.update_actor_skills("worker-3", skills)

        profile = service.get_actor_skills("worker-3")
        assert profile is not None
        assert profile.has_skill(SkillId("documentation", "technical_writing"))

    def test_get_actor_skills_nonexistent(self, service: GenesisService) -> None:
        assert service.get_actor_skills("ghost") is None

    def test_set_mission_skill_requirements(self, service: GenesisService) -> None:
        service.register_actor(
            actor_id="worker-4",
            actor_kind=ActorKind.HUMAN,
            region="NA",
            organization="Org1",
        )
        service.create_mission(
            mission_id="M-SKILL-REQ",
            title="Skill Test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
            worker_id="worker-4",
        )
        reqs = [
            SkillRequirement(
                skill_id=SkillId("software_engineering", "python"),
                minimum_proficiency=0.5,
            ),
        ]
        result = service.set_mission_skill_requirements("M-SKILL-REQ", reqs)
        assert result.success
        assert result.data["requirement_count"] == 1

        mission = service.get_mission("M-SKILL-REQ")
        assert len(mission.skill_requirements) == 1

    def test_set_requirements_on_non_draft_fails(self, service: GenesisService) -> None:
        """Can only set requirements on DRAFT missions."""
        service.register_actor(
            actor_id="worker-5",
            actor_kind=ActorKind.HUMAN,
            region="NA",
            organization="Org1",
        )
        service.create_mission(
            mission_id="M-SUBMITTED",
            title="Submitted",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
            worker_id="worker-5",
        )
        service.submit_mission("M-SUBMITTED")

        reqs = [
            SkillRequirement(
                skill_id=SkillId("software_engineering", "python"),
            ),
        ]
        result = service.set_mission_skill_requirements("M-SUBMITTED", reqs)
        assert not result.success
        assert "DRAFT" in result.errors[0]

    def test_set_requirements_invalid_skill(self, service: GenesisService) -> None:
        service.register_actor(
            actor_id="worker-6",
            actor_kind=ActorKind.HUMAN,
            region="NA",
            organization="Org1",
        )
        service.create_mission(
            mission_id="M-BAD-REQ",
            title="Bad Requirements",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
        )
        reqs = [
            SkillRequirement(
                skill_id=SkillId("fake_domain", "fake_skill"),
            ),
        ]
        result = service.set_mission_skill_requirements("M-BAD-REQ", reqs)
        assert not result.success

    def test_set_requirements_nonexistent_mission(self, service: GenesisService) -> None:
        result = service.set_mission_skill_requirements("M-GHOST", [])
        assert not result.success
        assert "not found" in result.errors[0].lower()
