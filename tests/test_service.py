"""Tests for GenesisService — proves the facade orchestrates correctly."""

import pytest
from pathlib import Path

from genesis.models.mission import DomainType, MissionClass, MissionState
from genesis.models.trust import ActorKind
from genesis.policy.resolver import PolicyResolver
from genesis.service import GenesisService


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def service(resolver: PolicyResolver) -> GenesisService:
    return GenesisService(resolver)


def _register_diverse_actors(service: GenesisService) -> None:
    """Register enough actors for R2 selection."""
    actors = [
        ("r1", "NA", "Org1", "claude", "reasoning_model"),
        ("r2", "EU", "Org2", "gpt", "retrieval_augmented"),
        ("r3", "APAC", "Org3", "gemini", "reasoning_model"),
        ("r4", "LATAM", "Org4", "claude", "rule_based_deterministic"),
        ("r5", "AF", "Org5", "gpt", "retrieval_augmented"),
        ("r6", "NA", "Org6", "gemini", "human_reviewer"),
        ("r7", "EU", "Org7", "llama", "reasoning_model"),
    ]
    for id, region, org, family, method in actors:
        service.register_actor(
            actor_id=id, actor_kind=ActorKind.HUMAN,
            region=region, organization=org,
            model_family=family, method_type=method,
            initial_trust=0.5,
        )


class TestActorRegistration:
    def test_register_and_lookup(self, service: GenesisService) -> None:
        result = service.register_actor(
            actor_id="alice", actor_kind=ActorKind.HUMAN,
            region="NA", organization="Org1",
        )
        assert result.success
        assert service.get_actor("alice") is not None

    def test_register_blank_id_fails(self, service: GenesisService) -> None:
        result = service.register_actor(
            actor_id="", actor_kind=ActorKind.HUMAN,
            region="NA", organization="Org1",
        )
        assert not result.success

    def test_register_creates_trust_record(self, service: GenesisService) -> None:
        service.register_actor(
            actor_id="bob", actor_kind=ActorKind.HUMAN,
            region="EU", organization="Org2",
        )
        trust = service.get_trust("bob")
        assert trust is not None
        assert trust.score == 0.10

    def test_quarantine_actor(self, service: GenesisService) -> None:
        service.register_actor(
            actor_id="charlie", actor_kind=ActorKind.MACHINE,
            region="APAC", organization="Org3",
            model_family="gpt", method_type="reasoning_model",
        )
        result = service.quarantine_actor("charlie")
        assert result.success
        assert service.get_actor("charlie").status.value == "quarantined"


class TestMissionLifecycle:
    def test_create_mission(self, service: GenesisService) -> None:
        result = service.create_mission(
            mission_id="M-001", title="Test mission",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
        )
        assert result.success
        assert result.data["risk_tier"] == "R0"

    def test_duplicate_mission_fails(self, service: GenesisService) -> None:
        service.create_mission(
            mission_id="M-001", title="First",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
        )
        result = service.create_mission(
            mission_id="M-001", title="Duplicate",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
        )
        assert not result.success

    def test_submit_mission(self, service: GenesisService) -> None:
        service.create_mission(
            mission_id="M-002", title="Submit test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
        )
        result = service.submit_mission("M-002")
        assert result.success
        assert service.get_mission("M-002").state == MissionState.SUBMITTED

    def test_submit_nonexistent_fails(self, service: GenesisService) -> None:
        result = service.submit_mission("M-DOES-NOT-EXIST")
        assert not result.success


class TestFullR0Flow:
    def test_r0_end_to_end(self, service: GenesisService) -> None:
        """Complete R0 mission lifecycle: create → submit → assign → review → approve."""
        _register_diverse_actors(service)

        # Create
        service.create_mission(
            mission_id="M-R0-E2E", title="E2E test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
            worker_id="worker_x",
        )

        # Submit
        result = service.submit_mission("M-R0-E2E")
        assert result.success

        # Assign reviewers
        result = service.assign_reviewers("M-R0-E2E", seed="e2e-test")
        assert result.success
        mission = service.get_mission("M-R0-E2E")
        assert len(mission.reviewers) == 1

        # Add evidence
        result = service.add_evidence(
            "M-R0-E2E",
            artifact_hash="sha256:" + "a" * 64,
            signature="ed25519:" + "b" * 64,
        )
        assert result.success

        # Submit review
        reviewer_id = mission.reviewers[0].id
        result = service.submit_review("M-R0-E2E", reviewer_id, "APPROVE")
        assert result.success

        # Complete review
        result = service.complete_review("M-R0-E2E")
        assert result.success
        assert mission.state == MissionState.REVIEW_COMPLETE

        # Approve
        result = service.approve_mission("M-R0-E2E")
        assert result.success
        assert mission.state == MissionState.APPROVED


class TestTrustUpdate:
    def test_update_trust(self, service: GenesisService) -> None:
        service.register_actor(
            actor_id="worker_t", actor_kind=ActorKind.HUMAN,
            region="NA", organization="Org1",
        )
        result = service.update_trust(
            actor_id="worker_t",
            quality=0.9, reliability=0.8, volume=0.4,
            reason="good work", effort=0.5,
        )
        assert result.success
        assert result.data["new_score"] > result.data["old_score"]

    def test_update_trust_nonexistent_fails(self, service: GenesisService) -> None:
        result = service.update_trust(
            actor_id="ghost", quality=0.9, reliability=0.8,
            volume=0.4, reason="no record",
        )
        assert not result.success


class TestEpochIntegration:
    def test_epoch_lifecycle(self, service: GenesisService) -> None:
        result = service.open_epoch("test-epoch")
        assert result.success

        # Create a mission (should record event)
        service.create_mission(
            mission_id="M-EP", title="Epoch test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
        )

        result = service.close_epoch(beacon_round=42)
        assert result.success
        assert result.data["epoch_id"] == "test-epoch"

    def test_close_without_open_fails(self, service: GenesisService) -> None:
        result = service.close_epoch(beacon_round=1)
        assert not result.success


class TestStatus:
    def test_status_structure(self, service: GenesisService) -> None:
        status = service.status()
        assert "actors" in status
        assert "missions" in status
        assert "epochs" in status
        assert status["actors"]["total"] == 0
        assert status["missions"]["total"] == 0
