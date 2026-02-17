"""Integration tests for domain-specific trust — end-to-end through the service layer.

Tests that domain trust flows correctly through:
- Mission completion → quality assessment → domain trust update
- Trust dashboard (get_trust_status)
- Domain trust queries (get_domain_trust)
- Inactivity decay (decay_inactive_actors)
- State persistence round-trip (save/load with domain scores)
"""

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from genesis.models.domain_trust import (
    DecayUrgency,
    DomainTrustScore,
    TrustStatus,
)
from genesis.models.mission import (
    DomainType,
    MissionClass,
    MissionState,
    ReviewDecisionVerdict,
)
from genesis.models.skill import SkillId, SkillRequirement
from genesis.models.trust import ActorKind, TrustRecord
from genesis.persistence.event_log import EventLog
from genesis.persistence.state_store import StateStore
from genesis.policy.resolver import PolicyResolver
from genesis.review.roster import ActorStatus
from genesis.service import GenesisService

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def resolver():
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def service(resolver):
    """Service without persistence — in-memory only."""
    return GenesisService(resolver)


@pytest.fixture
def service_with_persistence(resolver):
    """Service with state store for round-trip persistence tests."""
    tmpdir = TemporaryDirectory()
    store_path = Path(tmpdir.name) / "state.json"
    log_path = Path(tmpdir.name) / "events.jsonl"
    store = StateStore(store_path)
    log = EventLog(log_path)
    svc = GenesisService(resolver, event_log=log, state_store=store)
    yield svc, store, tmpdir
    tmpdir.cleanup()


def _setup_actors(service):
    """Register a worker and enough reviewers for R0 missions."""
    service.register_actor(
        "worker-1", ActorKind.HUMAN, "eu", "acme",
        initial_trust=0.5, status=ActorStatus.ACTIVE,
    )
    service.register_actor(
        "reviewer-1", ActorKind.HUMAN, "eu", "acme",
        initial_trust=0.5, status=ActorStatus.ACTIVE,
    )
    service.register_actor(
        "reviewer-2-operator", ActorKind.HUMAN, "us", "skynet",
        initial_trust=0.5, status=ActorStatus.ACTIVE,
    )
    service.register_actor(
        "reviewer-2", ActorKind.MACHINE, "us", "skynet",
        model_family="gpt", method_type="llm_evaluator",
        initial_trust=0.5, status=ActorStatus.ACTIVE,
        registered_by="reviewer-2-operator",
    )
    service.register_actor(
        "reviewer-3", ActorKind.HUMAN, "apac", "delta",
        initial_trust=0.5, status=ActorStatus.ACTIVE,
    )


def _create_and_approve_mission(
    service, mission_id="m1", skill_domains=None,
):
    """Create, submit, assign, review, and approve a mission.

    Optionally sets skill requirements so domain trust updates fire.
    """
    service.open_epoch()

    result = service.create_mission(
        mission_id=mission_id,
        title="Test Mission",
        mission_class=MissionClass.DOCUMENTATION_UPDATE,
        domain_type=DomainType.OBJECTIVE,
        worker_id="worker-1",
    )
    assert result.success

    # Set skill requirements if domains provided
    if skill_domains:
        # Map each domain to one valid skill from the taxonomy
        _domain_skill_map = {
            "software_engineering": "python",
            "data_science": "statistical_modeling",
            "legal_analysis": "contract_review",
            "financial_audit": "risk_assessment",
            "policy_research": "literature_review",
            "documentation": "technical_writing",
        }
        requirements = [
            SkillRequirement(
                skill_id=SkillId(domain=d, skill=_domain_skill_map.get(d, "python")),
                minimum_proficiency=0.0,
            )
            for d in skill_domains
        ]
        result = service.set_mission_skill_requirements(mission_id, requirements)
        assert result.success

    result = service.submit_mission(mission_id)
    assert result.success

    result = service.assign_reviewers(mission_id, seed="test-seed")
    assert result.success

    # All reviewers approve
    mission = service.get_mission(mission_id)
    for r in mission.reviewers:
        result = service.submit_review(mission_id, r.id, "APPROVE")
        assert result.success

    # Add evidence
    result = service.add_evidence(
        mission_id,
        artifact_hash="sha256:" + "a" * 64,
        signature="ed25519:" + "b" * 64,
    )
    assert result.success

    result = service.complete_review(mission_id)
    assert result.success

    result = service.approve_mission(mission_id)
    assert result.success

    return result


# ===================================================================
# Domain trust updates via mission completion
# ===================================================================

class TestDomainTrustViaMissionCompletion:
    def test_approved_mission_with_skill_requirements_updates_domain_trust(
        self, service,
    ) -> None:
        """When a mission with skill_requirements is approved, domain trust
        should be updated for the worker."""
        _setup_actors(service)
        result = _create_and_approve_mission(
            service,
            skill_domains=["software_engineering"],
        )
        assert result.success

        # Worker should now have domain trust for software_engineering
        worker_record = service.get_trust("worker-1")
        assert worker_record is not None
        assert "software_engineering" in worker_record.domain_scores
        ds = worker_record.domain_scores["software_engineering"]
        assert ds.score > 0
        assert ds.mission_count == 1

    def test_mission_without_skill_requirements_no_domain_update(
        self, service,
    ) -> None:
        """Missions without skill requirements should not trigger domain trust."""
        _setup_actors(service)
        result = _create_and_approve_mission(service)
        assert result.success

        worker_record = service.get_trust("worker-1")
        assert worker_record is not None
        assert len(worker_record.domain_scores) == 0

    def test_multi_domain_mission_updates_all_domains(self, service) -> None:
        """A mission requiring multiple domains updates all of them."""
        _setup_actors(service)
        result = _create_and_approve_mission(
            service,
            skill_domains=["software_engineering", "data_science"],
        )
        assert result.success

        worker_record = service.get_trust("worker-1")
        assert "software_engineering" in worker_record.domain_scores
        assert "data_science" in worker_record.domain_scores

    def test_domain_trust_updates_appear_in_result(self, service) -> None:
        """ServiceResult should include domain_trust_updates in quality_assessment."""
        _setup_actors(service)
        result = _create_and_approve_mission(
            service,
            skill_domains=["software_engineering"],
        )
        # domain_trust_updates is inside the quality_assessment sub-dict
        qa = result.data.get("quality_assessment", result.data)
        assert "domain_trust_updates" in qa
        updates = qa["domain_trust_updates"]
        assert len(updates) >= 1
        assert updates[0]["domain"] == "software_engineering"

    def test_consecutive_missions_accumulate_domain_trust(self, service) -> None:
        """Multiple missions in the same domain should accumulate."""
        _setup_actors(service)

        _create_and_approve_mission(
            service, mission_id="m1",
            skill_domains=["software_engineering"],
        )
        _create_and_approve_mission(
            service, mission_id="m2",
            skill_domains=["software_engineering"],
        )

        record = service.get_trust("worker-1")
        ds = record.domain_scores["software_engineering"]
        assert ds.mission_count == 2


# ===================================================================
# get_domain_trust
# ===================================================================

class TestGetDomainTrust:
    def test_returns_domain_score(self, service) -> None:
        _setup_actors(service)
        _create_and_approve_mission(
            service, skill_domains=["software_engineering"],
        )
        ds = service.get_domain_trust("worker-1", "software_engineering")
        assert ds is not None
        assert ds.score > 0

    def test_returns_none_for_missing_domain(self, service) -> None:
        _setup_actors(service)
        ds = service.get_domain_trust("worker-1", "nonexistent")
        assert ds is None

    def test_returns_none_for_missing_actor(self, service) -> None:
        ds = service.get_domain_trust("nobody", "software_engineering")
        assert ds is None


# ===================================================================
# get_trust_status (trust dashboard)
# ===================================================================

class TestGetTrustStatus:
    def test_returns_trust_status(self, service) -> None:
        _setup_actors(service)
        status = service.get_trust_status("worker-1")
        assert status is not None
        assert isinstance(status, TrustStatus)
        assert status.actor_id == "worker-1"

    def test_recently_registered_is_stable(self, service) -> None:
        _setup_actors(service)
        status = service.get_trust_status("worker-1")
        # New actor without last_active_utc → STABLE
        assert status.urgency == DecayUrgency.STABLE

    def test_includes_domain_forecasts(self, service) -> None:
        _setup_actors(service)
        _create_and_approve_mission(
            service, skill_domains=["software_engineering"],
        )
        status = service.get_trust_status("worker-1")
        assert len(status.domain_forecasts) >= 1
        domains = {f.domain for f in status.domain_forecasts}
        assert "software_engineering" in domains

    def test_returns_none_for_unknown_actor(self, service) -> None:
        assert service.get_trust_status("nobody") is None

    def test_half_life_reflects_actor_kind(self, service) -> None:
        _setup_actors(service)
        human_status = service.get_trust_status("worker-1")
        machine_status = service.get_trust_status("reviewer-2")
        # Human: 365, Machine: 90
        assert human_status.half_life_days > machine_status.half_life_days


# ===================================================================
# decay_inactive_actors
# ===================================================================

class TestDecayInactiveActors:
    def test_no_decay_without_config(self, resolver) -> None:
        """If no skill trust config, decay returns error."""
        # Build resolver without skill trust config
        bare_resolver = PolicyResolver(
            resolver._params, resolver._policy,
            taxonomy=None, skill_trust=None,
        )
        svc = GenesisService(bare_resolver)
        result = svc.decay_inactive_actors()
        assert not result.success

    def test_no_meaningful_decay_for_recent_actors(self, service) -> None:
        """Recently active actors should not have meaningful decay."""
        _setup_actors(service)
        _create_and_approve_mission(
            service, skill_domains=["software_engineering"],
        )
        old_score = service.get_trust("worker-1").score
        result = service.decay_inactive_actors()
        assert result.success
        # Score should remain essentially unchanged (sub-microsecond rounding only)
        new_score = service.get_trust("worker-1").score
        assert new_score == pytest.approx(old_score, abs=1e-6)

    def test_decay_applied_to_inactive_actors(self, service) -> None:
        """Actors inactive for a long time should be decayed."""
        _setup_actors(service)
        _create_and_approve_mission(
            service, skill_domains=["software_engineering"],
        )

        # Manually set last_active_utc to 200 days ago
        worker_record = service.get_trust("worker-1")
        old_time = datetime.now(timezone.utc) - timedelta(days=200)
        worker_record.last_active_utc = old_time
        for ds in worker_record.domain_scores.values():
            ds.last_active_utc = old_time

        old_score = worker_record.score
        result = service.decay_inactive_actors()
        assert result.success
        assert result.data["decayed_count"] >= 1

        new_record = service.get_trust("worker-1")
        assert new_record.score <= old_score


# ===================================================================
# Persistence round-trip
# ===================================================================

class TestDomainTrustPersistence:
    def test_domain_scores_survive_round_trip(
        self, service_with_persistence,
    ) -> None:
        """Domain trust scores should be saved and reloaded correctly."""
        svc, store, tmpdir = service_with_persistence

        _setup_actors(svc)
        _create_and_approve_mission(
            svc, skill_domains=["software_engineering"],
        )

        # Verify domain trust was saved
        records = store.load_trust_records()
        worker_record = records.get("worker-1")
        assert worker_record is not None
        assert "software_engineering" in worker_record.domain_scores
        ds = worker_record.domain_scores["software_engineering"]
        assert ds.score > 0
        assert ds.mission_count == 1
        assert ds.last_active_utc is not None

    def test_domain_scores_reload_with_timestamps(
        self, service_with_persistence, resolver,
    ) -> None:
        """Reloaded domain scores should have correct UTC timestamps."""
        svc, store, tmpdir = service_with_persistence

        _setup_actors(svc)
        _create_and_approve_mission(
            svc, skill_domains=["software_engineering"],
        )

        # Reload from store
        records = store.load_trust_records()
        ds = records["worker-1"].domain_scores["software_engineering"]
        assert ds.last_active_utc is not None
        assert ds.last_active_utc.tzinfo is not None  # timezone-aware

    def test_empty_domain_scores_backward_compat(
        self, service_with_persistence,
    ) -> None:
        """Records saved without domain_scores should load cleanly."""
        svc, store, tmpdir = service_with_persistence

        _setup_actors(svc)

        # Load records — no missions completed, no domain scores
        records = store.load_trust_records()
        worker_record = records.get("worker-1")
        assert worker_record is not None
        assert worker_record.domain_scores == {}
