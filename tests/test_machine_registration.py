"""Tests for machine registration — proves only verified humans can register machines."""

import pytest
from pathlib import Path

from genesis.models.trust import ActorKind
from genesis.persistence.event_log import EventKind
from genesis.policy.resolver import PolicyResolver
from genesis.review.roster import ActorStatus
from genesis.service import GenesisService


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def service(resolver: PolicyResolver) -> GenesisService:
    svc = GenesisService(resolver)
    svc.open_epoch("test-epoch")
    return svc


def _register_human(svc: GenesisService, actor_id: str = "human-op") -> None:
    """Register and return a human operator."""
    result = svc.register_human(
        actor_id=actor_id, region="NA", organization="Org1",
    )
    assert result.success, f"Human registration failed: {result.errors}"


class TestMachineRegistration:
    """Prove that machine registration enforcement works."""

    def test_register_machine_with_valid_operator(self, service: GenesisService) -> None:
        _register_human(service, "operator-1")
        result = service.register_machine(
            actor_id="bot-1",
            operator_id="operator-1",
            region="NA",
            organization="Org1",
            model_family="claude",
            method_type="reasoning_model",
        )
        assert result.success
        bot = service.get_actor("bot-1")
        assert bot is not None
        assert bot.actor_kind == ActorKind.MACHINE
        assert bot.registered_by == "operator-1"

    def test_register_machine_without_operator_fails(self, service: GenesisService) -> None:
        result = service.register_machine(
            actor_id="bot-orphan",
            operator_id="nonexistent",
            region="NA",
            organization="Org1",
        )
        assert not result.success
        assert "not found" in result.errors[0].lower()

    def test_register_machine_with_machine_operator_fails(self, service: GenesisService) -> None:
        _register_human(service, "human-op")
        # Register a machine via legacy path
        service.register_actor(
            actor_id="machine-a", actor_kind=ActorKind.MACHINE,
            region="NA", organization="Org1",
        )
        # Now try to have machine-a register another machine
        result = service.register_machine(
            actor_id="machine-b",
            operator_id="machine-a",
            region="NA",
            organization="Org1",
        )
        assert not result.success
        assert "only human" in result.errors[0].lower()

    def test_register_machine_with_quarantined_operator_fails(self, service: GenesisService) -> None:
        _register_human(service, "quarantined-human")
        service.quarantine_actor("quarantined-human")
        result = service.register_machine(
            actor_id="bot-q",
            operator_id="quarantined-human",
            region="NA",
            organization="Org1",
        )
        assert not result.success
        assert "not in an active state" in result.errors[0].lower()

    def test_registered_by_field_set_correctly(self, service: GenesisService) -> None:
        _register_human(service, "op-check")
        service.register_machine(
            actor_id="bot-check",
            operator_id="op-check",
            region="EU",
            organization="Org2",
            model_family="gpt",
            method_type="retrieval_augmented",
        )
        bot = service.get_actor("bot-check")
        assert bot is not None
        assert bot.registered_by == "op-check"
        assert bot.registered_utc is not None

    def test_human_registration_has_no_registered_by(self, service: GenesisService) -> None:
        _register_human(service, "plain-human")
        human = service.get_actor("plain-human")
        assert human is not None
        assert human.registered_by is None
        assert human.registered_utc is not None

    def test_get_operator_machines(self, service: GenesisService) -> None:
        _register_human(service, "multi-op")
        service.register_machine(
            actor_id="bot-m1", operator_id="multi-op",
            region="NA", organization="Org1",
        )
        service.register_machine(
            actor_id="bot-m2", operator_id="multi-op",
            region="EU", organization="Org2",
        )
        machines = service.get_operator_machines("multi-op")
        assert len(machines) == 2
        assert {m.actor_id for m in machines} == {"bot-m1", "bot-m2"}

    def test_machine_trust_independent_from_operator(self, service: GenesisService) -> None:
        _register_human(service, "rich-human")
        # Manually set human trust higher
        human_entry = service.get_actor("rich-human")
        human_entry.trust_score = 0.9

        service.register_machine(
            actor_id="new-bot",
            operator_id="rich-human",
            region="NA",
            organization="Org1",
        )
        bot = service.get_actor("new-bot")
        assert bot.trust_score == 0.10  # default, not inherited

    def test_machine_does_not_affect_human_count(self, service: GenesisService) -> None:
        _register_human(service, "h1")
        _register_human(service, "h2")
        initial_count = service._roster.human_count

        service.register_machine(
            actor_id="bot-no-count",
            operator_id="h1",
            region="NA",
            organization="Org1",
        )
        assert service._roster.human_count == initial_count
        assert service._roster.machine_count == 1


class TestLegacyBackwardCompat:
    """Prove legacy register_actor() still works."""

    def test_legacy_register_human(self, service: GenesisService) -> None:
        result = service.register_actor(
            actor_id="legacy-h", actor_kind=ActorKind.HUMAN,
            region="NA", organization="Org1",
        )
        assert result.success
        actor = service.get_actor("legacy-h")
        assert actor.actor_kind == ActorKind.HUMAN

    def test_legacy_register_machine_without_operator(self, service: GenesisService) -> None:
        """Legacy path allows machine without operator for backward compat."""
        result = service.register_actor(
            actor_id="legacy-bot", actor_kind=ActorKind.MACHINE,
            region="NA", organization="Org1",
            model_family="gpt", method_type="reasoning_model",
        )
        assert result.success
        bot = service.get_actor("legacy-bot")
        assert bot.actor_kind == ActorKind.MACHINE
        assert bot.registered_by is None  # legacy — no operator

    def test_legacy_register_machine_with_operator(self, service: GenesisService) -> None:
        """Legacy path with registered_by delegates to register_machine()."""
        _register_human(service, "legacy-op")
        result = service.register_actor(
            actor_id="legacy-bot-op", actor_kind=ActorKind.MACHINE,
            region="NA", organization="Org1",
            registered_by="legacy-op",
        )
        assert result.success
        bot = service.get_actor("legacy-bot-op")
        assert bot.registered_by == "legacy-op"

    def test_string_actor_kind_normalised(self, service: GenesisService) -> None:
        """String 'HUMAN' is normalised to ActorKind.HUMAN."""
        result = service.register_actor(
            actor_id="str-kind", actor_kind="HUMAN",
            region="NA", organization="Org1",
        )
        assert result.success
