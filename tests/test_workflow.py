"""Tests for Phase E-4: Workflow Orchestration.

Covers:
- WorkflowOrchestrator: state tracking, compliance screening, escrow lifecycle
- WorkflowStateMachine: WORK_SUBMITTED state and transitions
- Payment disputes: escrow→DISPUTED→adjudication bridge
- Service integration: full happy path, events, cancellation, disputes
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from genesis.compensation.escrow import EscrowManager
from genesis.models.compensation import CommissionBreakdown, EscrowState, WindowStats
from genesis.models.market import BidState, ListingState
from genesis.models.mission import (
    DomainType,
    EvidenceRecord,
    Mission,
    MissionClass,
    MissionState,
    RiskTier,
)
from genesis.models.skill import SkillId, SkillProficiency, SkillRequirement
from genesis.models.trust import ActorKind
from genesis.engine.state_machine import MissionStateMachine
from genesis.policy.resolver import PolicyResolver
from genesis.service import GenesisService
from genesis.persistence.event_log import EventKind, EventLog
from genesis.workflow.orchestrator import (
    WorkflowOrchestrator,
    WorkflowState,
    WorkflowStatus,
)

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _now() -> datetime:
    return datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc)


def _workflow_config() -> dict[str, Any]:
    return {
        "default_deadline_days": 30,
        "require_compliance_screening": True,
        "require_escrow_before_publish": True,
        "auto_start_bids_on_publish": True,
    }


@pytest.fixture
def resolver():
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def service(resolver):
    event_log = EventLog()
    svc = GenesisService(resolver, event_log=event_log)
    svc.open_epoch()
    return svc


def _register_actors(service: GenesisService) -> None:
    """Register a creator and two workers."""
    service.register_actor(
        "creator-1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5,
    )
    service.register_actor(
        "worker-1", ActorKind.HUMAN, "us", "beta", initial_trust=0.6,
    )
    service.register_actor(
        "worker-2", ActorKind.HUMAN, "apac", "gamma", initial_trust=0.4,
    )


def _make_test_breakdown(mission_reward: Decimal) -> CommissionBreakdown:
    """Create a valid commission breakdown for testing."""
    creator_fee_rate = Decimal("0.05")
    employer_fee = (mission_reward * creator_fee_rate).quantize(Decimal("0.01"))
    commission = (mission_reward * Decimal("0.10")).quantize(Decimal("0.01"))
    creator_alloc = (mission_reward * Decimal("0.045")).quantize(Decimal("0.01"))
    gcf = (mission_reward * Decimal("0.01")).quantize(Decimal("0.01"))
    worker_payout = mission_reward - commission - creator_alloc - gcf

    return CommissionBreakdown(
        rate=Decimal("0.10"),
        raw_rate=Decimal("0.10"),
        cost_ratio=Decimal("0.50"),
        commission_amount=commission,
        creator_allocation=creator_alloc,
        employer_creator_fee=employer_fee,
        worker_payout=worker_payout,
        mission_reward=mission_reward,
        cost_breakdown={"infrastructure": Decimal("10")},
        is_bootstrap=True,
        window_stats=WindowStats(
            missions_in_window=1,
            total_completed_missions=1,
            window_days_actual=30,
            window_days_configured=30,
            min_missions_configured=3,
            is_bootstrap=True,
        ),
        reserve_contribution=Decimal("0"),
        safety_margin=Decimal("0"),
        gcf_contribution=gcf,
    )


# =====================================================================
# TestWorkflowOrchestrator — core orchestrator logic
# =====================================================================

class TestWorkflowOrchestrator:
    """Tests for the WorkflowOrchestrator state tracking."""

    def test_create_workflow(self):
        orch = WorkflowOrchestrator(_workflow_config())
        wf = orch.create_workflow("L-1", "creator-1", Decimal("500"), _now())
        assert wf.workflow_id.startswith("wf-")
        assert wf.listing_id == "L-1"
        assert wf.creator_id == "creator-1"
        assert wf.mission_reward == Decimal("500")
        assert wf.status == WorkflowStatus.LISTING_CREATED

    def test_record_compliance_screening(self):
        orch = WorkflowOrchestrator(_workflow_config())
        wf = orch.create_workflow("L-1", "creator-1", Decimal("500"), _now())
        orch.record_compliance_screening(wf.workflow_id, "clear", _now())
        assert wf.compliance_verdict == "clear"

    def test_record_escrow_funded(self):
        orch = WorkflowOrchestrator(_workflow_config())
        wf = orch.create_workflow("L-1", "creator-1", Decimal("500"), _now())
        orch.record_escrow_funded(wf.workflow_id, "escrow-1")
        assert wf.escrow_id == "escrow-1"
        assert wf.status == WorkflowStatus.ESCROW_FUNDED

    def test_record_listing_live(self):
        orch = WorkflowOrchestrator(_workflow_config())
        wf = orch.create_workflow("L-1", "creator-1", Decimal("500"), _now())
        orch.record_listing_live(wf.workflow_id)
        assert wf.status == WorkflowStatus.BIDS_OPEN

    def test_record_worker_allocated(self):
        orch = WorkflowOrchestrator(_workflow_config())
        wf = orch.create_workflow("L-1", "creator-1", Decimal("500"), _now())
        orch.record_worker_allocated(wf.workflow_id, "M-1", "worker-1", _now())
        assert wf.mission_id == "M-1"
        assert wf.worker_id == "worker-1"
        assert wf.status == WorkflowStatus.WORK_IN_PROGRESS
        assert wf.deadline_utc == _now() + timedelta(days=30)

    def test_record_work_submitted(self):
        orch = WorkflowOrchestrator(_workflow_config())
        wf = orch.create_workflow("L-1", "creator-1", Decimal("500"), _now())
        orch.record_work_submitted(wf.workflow_id, ["hash1", "hash2"], _now())
        assert wf.work_evidence_hashes == ["hash1", "hash2"]
        assert wf.status == WorkflowStatus.WORK_SUBMITTED

    def test_record_completed(self):
        orch = WorkflowOrchestrator(_workflow_config())
        wf = orch.create_workflow("L-1", "creator-1", Decimal("500"), _now())
        orch.record_completed(wf.workflow_id, _now())
        assert wf.status == WorkflowStatus.COMPLETED

    def test_record_cancelled(self):
        orch = WorkflowOrchestrator(_workflow_config())
        wf = orch.create_workflow("L-1", "creator-1", Decimal("500"), _now())
        orch.record_cancelled(wf.workflow_id, _now())
        assert wf.status == WorkflowStatus.CANCELLED

    def test_record_disputed(self):
        orch = WorkflowOrchestrator(_workflow_config())
        wf = orch.create_workflow("L-1", "creator-1", Decimal("500"), _now())
        orch.record_disputed(wf.workflow_id, "adj-001")
        assert wf.dispute_case_id == "adj-001"
        assert wf.status == WorkflowStatus.DISPUTED

    def test_dispute_resolved_to_worker(self):
        orch = WorkflowOrchestrator(_workflow_config())
        wf = orch.create_workflow("L-1", "creator-1", Decimal("500"), _now())
        orch.record_dispute_resolved(wf.workflow_id, True, _now())
        assert wf.status == WorkflowStatus.COMPLETED

    def test_dispute_resolved_refund(self):
        orch = WorkflowOrchestrator(_workflow_config())
        wf = orch.create_workflow("L-1", "creator-1", Decimal("500"), _now())
        orch.record_dispute_resolved(wf.workflow_id, False, _now())
        assert wf.status == WorkflowStatus.REFUNDED

    def test_workflow_not_found_raises(self):
        orch = WorkflowOrchestrator(_workflow_config())
        with pytest.raises(ValueError, match="Workflow not found"):
            orch._get("nonexistent")


# =====================================================================
# TestWorkflowStateMachine — WORK_SUBMITTED state
# =====================================================================

class TestWorkflowStateMachine:
    """Tests for the WORK_SUBMITTED mission state."""

    def test_work_submitted_state_exists(self):
        assert MissionState.WORK_SUBMITTED.value == "work_submitted"

    def test_assigned_to_work_submitted_valid(self, resolver):
        sm = MissionStateMachine(resolver)
        mission = Mission(
            mission_id="M-1",
            mission_title="Test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            state=MissionState.ASSIGNED,
            worker_id="worker-1",
            evidence=[EvidenceRecord(artifact_hash="abc", signature="sig")],
        )
        errors = sm.transition(mission, MissionState.WORK_SUBMITTED)
        assert errors == []

    def test_submitted_to_work_submitted_valid(self, resolver):
        """Workflow path: SUBMITTED → WORK_SUBMITTED (skips ASSIGNED)."""
        sm = MissionStateMachine(resolver)
        mission = Mission(
            mission_id="M-1",
            mission_title="Test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            state=MissionState.SUBMITTED,
            worker_id="worker-1",
            evidence=[EvidenceRecord(artifact_hash="abc", signature="sig")],
        )
        errors = sm.transition(mission, MissionState.WORK_SUBMITTED)
        assert errors == []

    def test_work_submitted_to_in_review_valid(self, resolver):
        sm = MissionStateMachine(resolver)
        mission = Mission(
            mission_id="M-1",
            mission_title="Test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            state=MissionState.WORK_SUBMITTED,
            worker_id="worker-1",
        )
        errors = sm.transition(mission, MissionState.IN_REVIEW)
        assert errors == []

    def test_assigned_to_in_review_still_valid(self, resolver):
        """Backward compat: direct ASSIGNED → IN_REVIEW still works."""
        sm = MissionStateMachine(resolver)
        mission = Mission(
            mission_id="M-1",
            mission_title="Test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            state=MissionState.ASSIGNED,
            worker_id="worker-1",
        )
        errors = sm.transition(mission, MissionState.IN_REVIEW)
        assert errors == []

    def test_work_submitted_requires_evidence(self, resolver):
        sm = MissionStateMachine(resolver)
        mission = Mission(
            mission_id="M-1",
            mission_title="Test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            state=MissionState.ASSIGNED,
            worker_id="worker-1",
            evidence=[],  # No evidence
        )
        errors = sm.transition(mission, MissionState.WORK_SUBMITTED)
        assert len(errors) == 1
        assert "no evidence records" in errors[0]

    def test_work_submitted_cancel_valid(self, resolver):
        sm = MissionStateMachine(resolver)
        mission = Mission(
            mission_id="M-1",
            mission_title="Test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            state=MissionState.WORK_SUBMITTED,
            worker_id="worker-1",
        )
        errors = sm.transition(mission, MissionState.CANCELLED)
        assert errors == []


# =====================================================================
# TestServiceWorkflowIntegration — end-to-end via service
# =====================================================================

class TestServiceWorkflowIntegration:
    """Integration tests for workflow orchestration via the service layer."""

    def test_create_funded_listing(self, service):
        """create_funded_listing creates escrow + listing + workflow."""
        _register_actors(service)
        result = service.create_funded_listing(
            listing_id="L-001",
            title="Build REST API",
            description="Build a Python REST API",
            creator_id="creator-1",
            mission_reward=Decimal("500"),
        )
        assert result.success
        assert result.data["workflow_id"].startswith("wf-")
        assert result.data["listing_id"] == "L-001"
        assert result.data["escrow_id"].startswith("escrow_")
        assert result.data["compliance_verdict"] in ("clear", "flagged")
        assert result.data["mission_reward"] == "500"

    def test_compliance_rejected_blocks_listing(self, service):
        """Compliance REJECTED prevents listing creation."""
        _register_actors(service)
        # Use a title that triggers compliance rejection
        result = service.create_funded_listing(
            listing_id="L-BAD",
            title="Build weapons manufacturing tools",
            description="Manufacturing weapons",
            creator_id="creator-1",
            mission_reward=Decimal("500"),
            domain_tags=["weapons_manufacturing"],
        )
        assert not result.success
        assert "compliance" in result.errors[0].lower() or "rejected" in result.errors[0].lower()

    def test_suspended_actor_cannot_create_funded_listing(self, service):
        """Suspended actors are blocked from creating funded listings."""
        _register_actors(service)
        # Suspend creator
        entry = service._roster.get("creator-1")
        entry.status = __import__("genesis.review.roster", fromlist=["ActorStatus"]).ActorStatus.SUSPENDED
        result = service.create_funded_listing(
            listing_id="L-002",
            title="Test listing",
            description="Test",
            creator_id="creator-1",
            mission_reward=Decimal("500"),
        )
        assert not result.success
        assert "suspended" in result.errors[0].lower()

    def test_fund_and_publish(self, service):
        """fund_and_publish locks escrow and opens listing."""
        _register_actors(service)
        create_result = service.create_funded_listing(
            listing_id="L-003",
            title="Data analysis project",
            description="Analyze data set",
            creator_id="creator-1",
            mission_reward=Decimal("300"),
        )
        assert create_result.success
        wf_id = create_result.data["workflow_id"]

        publish_result = service.fund_and_publish_listing(wf_id)
        assert publish_result.success

        # Verify escrow is locked
        escrow_id = create_result.data["escrow_id"]
        escrow = service._escrow_manager.get_escrow(escrow_id)
        assert escrow.state == EscrowState.LOCKED

        # Verify listing is in ACCEPTING_BIDS
        listing = service.get_listing("L-003")
        assert listing.state == ListingState.ACCEPTING_BIDS

    def test_create_funded_listing_emits_event(self, service):
        """create_funded_listing emits WORKFLOW_CREATED event."""
        _register_actors(service)
        result = service.create_funded_listing(
            listing_id="L-004",
            title="Code review task",
            description="Review code",
            creator_id="creator-1",
            mission_reward=Decimal("200"),
        )
        assert result.success

        events = service._event_log.events(EventKind.WORKFLOW_CREATED)
        assert len(events) >= 1
        last = events[-1]
        assert last.payload["listing_id"] == "L-004"

    def test_cancel_workflow_refunds_escrow(self, service):
        """cancel_workflow refunds escrow and cancels listing."""
        _register_actors(service)
        create = service.create_funded_listing(
            listing_id="L-005",
            title="Cancel me",
            description="Will be cancelled",
            creator_id="creator-1",
            mission_reward=Decimal("100"),
        )
        assert create.success
        wf_id = create.data["workflow_id"]

        # Publish first so escrow is locked
        pub = service.fund_and_publish_listing(wf_id)
        assert pub.success

        # Cancel
        cancel_result = service.cancel_workflow(wf_id, "Changed my mind")
        assert cancel_result.success
        assert cancel_result.data["escrow_refunded"] is True

        # Verify escrow is refunded
        escrow = service._escrow_manager.get_escrow(create.data["escrow_id"])
        assert escrow.state == EscrowState.REFUNDED

        # Verify listing is cancelled
        listing = service.get_listing("L-005")
        assert listing.state == ListingState.CANCELLED

    def test_file_payment_dispute(self, service):
        """file_payment_dispute creates adjudication case and disputes escrow."""
        _register_actors(service)
        create = service.create_funded_listing(
            listing_id="L-006",
            title="Disputeable task",
            description="This will be disputed",
            creator_id="creator-1",
            mission_reward=Decimal("400"),
        )
        assert create.success
        wf_id = create.data["workflow_id"]

        # Publish
        pub = service.fund_and_publish_listing(wf_id)
        assert pub.success

        # Submit bid and allocate
        bid_result = service.submit_bid("B-1", "L-006", "worker-1")
        assert bid_result.success

        alloc = service.allocate_worker_workflow(wf_id)
        assert alloc.success

        # File dispute
        dispute_result = service.file_payment_dispute_workflow(
            wf_id, "creator-1", "Worker did not deliver",
        )
        assert dispute_result.success
        assert dispute_result.data["case_id"].startswith("adj-")

        # Verify escrow is disputed
        escrow = service._escrow_manager.get_escrow(create.data["escrow_id"])
        assert escrow.state == EscrowState.DISPUTED

        # Verify workflow is in DISPUTED state
        wf = service.get_workflow(wf_id)
        assert wf.status == WorkflowStatus.DISPUTED

    def test_dispute_emits_event(self, service):
        """Filing a payment dispute emits PAYMENT_DISPUTE_FILED event."""
        _register_actors(service)
        create = service.create_funded_listing(
            listing_id="L-007",
            title="Dispute event test",
            description="Test dispute events",
            creator_id="creator-1",
            mission_reward=Decimal("300"),
        )
        assert create.success
        wf_id = create.data["workflow_id"]
        pub = service.fund_and_publish_listing(wf_id)
        assert pub.success
        service.submit_bid("B-2", "L-007", "worker-1")
        service.allocate_worker_workflow(wf_id)

        dispute = service.file_payment_dispute_workflow(
            wf_id, "creator-1", "Non-delivery",
        )
        assert dispute.success

        events = service._event_log.events(EventKind.PAYMENT_DISPUTE_FILED)
        assert len(events) >= 1

    def test_submit_work_records_evidence(self, service):
        """submit_work_workflow records evidence and transitions mission."""
        _register_actors(service)
        create = service.create_funded_listing(
            listing_id="L-008",
            title="Work submission test",
            description="Test work submission",
            creator_id="creator-1",
            mission_reward=Decimal("200"),
        )
        assert create.success
        wf_id = create.data["workflow_id"]
        pub = service.fund_and_publish_listing(wf_id)
        assert pub.success
        service.submit_bid("B-3", "L-008", "worker-1")
        alloc = service.allocate_worker_workflow(wf_id)
        assert alloc.success
        mission_id = alloc.data["mission_id"]

        # Submit work (evidence hashes must match sha256:<64-hex-chars> format)
        submit_result = service.submit_work_workflow(
            wf_id, ["sha256:" + "a" * 64, "sha256:" + "b" * 64],
        )
        assert submit_result.success
        assert submit_result.data["evidence_count"] == 2

        # Verify mission state
        mission = service._missions.get(mission_id)
        assert mission.state == MissionState.WORK_SUBMITTED

    def test_workflow_not_found(self, service):
        """Workflow methods return error for nonexistent workflow."""
        result = service.fund_and_publish_listing("nonexistent")
        assert not result.success
        assert "not found" in result.errors[0].lower()

    def test_cancel_emits_event(self, service):
        """cancel_workflow emits WORKFLOW_CANCELLED event."""
        _register_actors(service)
        create = service.create_funded_listing(
            listing_id="L-009",
            title="Cancel event test",
            description="Test cancel events",
            creator_id="creator-1",
            mission_reward=Decimal("150"),
        )
        assert create.success
        wf_id = create.data["workflow_id"]

        cancel = service.cancel_workflow(wf_id, "Testing")
        assert cancel.success

        events = service._event_log.events(EventKind.WORKFLOW_CANCELLED)
        assert len(events) >= 1


# =====================================================================
# TestEscrowIntegration — escrow lifecycle within workflows
# =====================================================================

class TestEscrowIntegration:
    """Tests for escrow lifecycle within workflow orchestration."""

    def test_escrow_amount_includes_employer_fee(self, service):
        """Escrow amount = mission_reward + 5% employer creator fee."""
        _register_actors(service)
        result = service.create_funded_listing(
            listing_id="L-E1",
            title="Escrow test",
            description="Test escrow amount",
            creator_id="creator-1",
            mission_reward=Decimal("1000"),
        )
        assert result.success
        assert result.data["total_escrow"] == "1050.00"

    def test_publish_without_workflow_fails(self, service):
        """fund_and_publish with nonexistent workflow fails."""
        result = service.fund_and_publish_listing("wf-nonexistent")
        assert not result.success

    def test_escrow_refunded_on_cancel(self, service):
        """Full escrow (including employer fee) returned on cancel."""
        _register_actors(service)
        create = service.create_funded_listing(
            listing_id="L-E2",
            title="Refund test",
            description="Will be refunded",
            creator_id="creator-1",
            mission_reward=Decimal("500"),
        )
        assert create.success
        wf_id = create.data["workflow_id"]
        escrow_id = create.data["escrow_id"]

        # Fund and publish
        pub = service.fund_and_publish_listing(wf_id)
        assert pub.success

        # Cancel — full escrow refunded
        cancel = service.cancel_workflow(wf_id)
        assert cancel.success

        escrow = service._escrow_manager.get_escrow(escrow_id)
        assert escrow.state == EscrowState.REFUNDED
        assert escrow.amount == Decimal("525.00")  # 500 + 5% = 525


# =====================================================================
# TestCXRegressions — regression tests for CX review findings
# =====================================================================

class TestCXRegressions:
    """Regression tests for CX P1/P2 findings on Phase E-4 commit ee1da8e.

    P1-1: GCF activation not durable across restart
    P1-2: Orphan escrow leak when create_funded_listing called with duplicate listing_id
    P2:   Hardcoded 0.05 employer fee rate bypassed policy config
    """

    def test_gcf_activation_survives_restart(self, tmp_path):
        """P1 regression: GCF must be active after service restart when First Light was achieved."""
        from genesis.persistence.state_store import StateStore

        store_path = tmp_path / "genesis_state.json"
        log_path = tmp_path / "events.jsonl"

        resolver1 = PolicyResolver.from_config_dir(CONFIG_DIR)
        store1 = StateStore(store_path)
        log1 = EventLog(log_path)

        svc1 = GenesisService(resolver1, event_log=log1, state_store=store1)
        svc1.open_epoch("epoch-1")

        # Register actors for First Light threshold
        for i in range(5):
            svc1.register_actor(
                actor_id=f"h-{i}", actor_kind=ActorKind.HUMAN,
                region="EU", organization="Org",
            )

        # Trigger First Light — this activates GCF
        fl = svc1.check_first_light(
            monthly_revenue=Decimal("2000"),
            monthly_costs=Decimal("1000"),
            reserve_balance=Decimal("5000"),
        )
        assert fl.data["first_light"] is True
        assert svc1._gcf_tracker.is_active is True

        # Restart: fresh service from same persisted state
        store2 = StateStore(store_path)
        log2 = EventLog(log_path)
        resolver2 = PolicyResolver.from_config_dir(CONFIG_DIR)
        svc2 = GenesisService(resolver2, event_log=log2, state_store=store2)
        svc2.open_epoch("epoch-2")

        # GCF must still be active after restart
        assert svc2._gcf_tracker.is_active is True, \
            "GCF tracker must be re-activated on restart when First Light was previously achieved"

    def test_duplicate_listing_does_not_leak_escrow(self, service):
        """P1 regression: duplicate create_funded_listing must not create orphan escrow."""
        _register_actors(service)

        # First call succeeds
        r1 = service.create_funded_listing(
            listing_id="L-DUP",
            title="First listing",
            description="Original listing",
            creator_id="creator-1",
            mission_reward=Decimal("500"),
        )
        assert r1.success

        # Count escrows after first call
        escrows_after_first = len(service._escrow_manager._escrows)

        # Second call with same listing_id must fail WITHOUT creating another escrow
        r2 = service.create_funded_listing(
            listing_id="L-DUP",
            title="Duplicate listing",
            description="Should fail before escrow creation",
            creator_id="creator-1",
            mission_reward=Decimal("500"),
        )
        assert not r2.success
        assert "already exists" in r2.errors[0].lower()

        # Escrow count must not have increased
        escrows_after_second = len(service._escrow_manager._escrows)
        assert escrows_after_second == escrows_after_first, \
            "Duplicate listing must not create orphan escrow records"

    def test_employer_fee_rate_reads_from_policy(self, resolver):
        """P2 regression: employer fee rate must come from commission policy, not hardcoded."""
        # Save original rate
        original_rate = resolver._commission_policy["employer_creator_fee_rate"]

        # Override to 0.06 in the commission_policy config (the source commission_params reads)
        resolver._commission_policy["employer_creator_fee_rate"] = "0.06"

        svc = GenesisService(resolver, event_log=EventLog())
        svc.open_epoch("test-epoch")

        svc.register_actor(
            "creator-1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5,
        )

        result = svc.create_funded_listing(
            listing_id="L-FEE",
            title="Fee rate test",
            description="Testing fee rate from policy",
            creator_id="creator-1",
            mission_reward=Decimal("1000"),
        )
        assert result.success

        # With 0.06 rate: total_escrow = 1000 + 60.00 = 1060.00
        assert result.data["total_escrow"] == "1060.00", \
            f"Expected 1060.00 (6% employer fee), got {result.data['total_escrow']}"

        # Restore original rate
        resolver._commission_policy["employer_creator_fee_rate"] = original_rate


# =====================================================================
# TestWorkflowEscrowPersistence — restart durability for escrow + workflow
# =====================================================================

class TestWorkflowEscrowPersistence:
    """Regression tests for CX P1: workflow/escrow state must survive restart.

    Covers:
    - Workflow state persisted and restored via StateStore
    - Escrow records persisted and restored via StateStore
    - Listing workflow fields (mission_reward, escrow_id, deadline_days) survive restart
    - open_listing blocked when escrow record missing (escrow-first guard)
    """

    def _make_service(self, resolver, store, log):
        """Create a GenesisService with actors registered."""
        svc = GenesisService(resolver, event_log=log, state_store=store)
        svc.open_epoch("epoch-1")
        svc.register_actor(
            "creator-1", ActorKind.HUMAN, "eu", "acme", initial_trust=0.5,
        )
        svc.register_actor(
            "worker-1", ActorKind.HUMAN, "us", "beta", initial_trust=0.6,
        )
        return svc

    def test_workflow_survives_restart(self, tmp_path):
        """Workflow state must be present after service restart."""
        from genesis.persistence.state_store import StateStore

        store_path = tmp_path / "genesis_state.json"
        log_path = tmp_path / "events.jsonl"

        resolver1 = PolicyResolver.from_config_dir(CONFIG_DIR)
        store1 = StateStore(store_path)
        log1 = EventLog(log_path)

        svc1 = self._make_service(resolver1, store1, log1)

        # Create a funded listing (creates workflow + escrow)
        result = svc1.create_funded_listing(
            listing_id="L-RESTART-WF",
            title="Workflow restart test",
            description="Testing workflow persistence",
            creator_id="creator-1",
            mission_reward=Decimal("500"),
        )
        assert result.success
        wf_id = result.data["workflow_id"]

        # Restart: fresh service from same persisted state
        store2 = StateStore(store_path)
        log2 = EventLog(log_path)
        resolver2 = PolicyResolver.from_config_dir(CONFIG_DIR)
        svc2 = GenesisService(resolver2, event_log=log2, state_store=store2)
        svc2.open_epoch("epoch-2")

        # Workflow must exist after restart
        wf = svc2._workflow_orchestrator.get_workflow(wf_id)
        assert wf is not None, "Workflow must survive restart"
        assert wf.listing_id == "L-RESTART-WF"
        assert wf.mission_reward == Decimal("500")

        # fund_and_publish must succeed (requires both workflow and escrow)
        pub = svc2.fund_and_publish_listing(wf_id)
        assert pub.success, f"fund_and_publish failed after restart: {pub.errors}"

    def test_escrow_survives_restart(self, tmp_path):
        """Escrow records must be present with correct state after restart."""
        from genesis.persistence.state_store import StateStore

        store_path = tmp_path / "genesis_state.json"
        log_path = tmp_path / "events.jsonl"

        resolver1 = PolicyResolver.from_config_dir(CONFIG_DIR)
        store1 = StateStore(store_path)
        log1 = EventLog(log_path)

        svc1 = self._make_service(resolver1, store1, log1)

        result = svc1.create_funded_listing(
            listing_id="L-RESTART-ESC",
            title="Escrow restart test",
            description="Testing escrow persistence",
            creator_id="creator-1",
            mission_reward=Decimal("1000"),
        )
        assert result.success
        escrow_id = result.data["escrow_id"]

        # Fund and publish (locks escrow: PENDING → LOCKED)
        wf_id = result.data["workflow_id"]
        pub = svc1.fund_and_publish_listing(wf_id)
        assert pub.success

        # Restart
        store2 = StateStore(store_path)
        log2 = EventLog(log_path)
        resolver2 = PolicyResolver.from_config_dir(CONFIG_DIR)
        svc2 = GenesisService(resolver2, event_log=log2, state_store=store2)

        # Escrow must exist with correct state and amount
        escrow = svc2._escrow_manager.get_escrow(escrow_id)
        assert escrow is not None, "Escrow must survive restart"
        assert escrow.state == EscrowState.LOCKED, \
            f"Escrow state should be LOCKED after restart, got {escrow.state}"
        assert escrow.amount == Decimal("1050.00"), \
            f"Escrow amount should be 1050.00 (1000 + 5%), got {escrow.amount}"

    def test_open_listing_blocked_without_escrow(self, service):
        """open_listing must fail when listing has escrow_id but escrow record is missing."""
        _register_actors(service)

        # Create a funded listing (links escrow_id to listing)
        result = service.create_funded_listing(
            listing_id="L-GUARD",
            title="Escrow guard test",
            description="Testing escrow-first guard",
            creator_id="creator-1",
            mission_reward=Decimal("500"),
        )
        assert result.success
        escrow_id = result.data["escrow_id"]

        # Simulate escrow loss (e.g. restart without persistence)
        del service._escrow_manager._escrows[escrow_id]

        # open_listing must fail because escrow is gone
        open_result = service.open_listing("L-GUARD")
        assert not open_result.success, \
            "open_listing must fail when escrow record is missing"
        assert "escrow record missing" in open_result.errors[0].lower()

    def test_listing_fields_survive_restart(self, tmp_path):
        """Listing mission_reward, escrow_id, deadline_days must persist across restart."""
        from genesis.persistence.state_store import StateStore

        store_path = tmp_path / "genesis_state.json"
        log_path = tmp_path / "events.jsonl"

        resolver1 = PolicyResolver.from_config_dir(CONFIG_DIR)
        store1 = StateStore(store_path)
        log1 = EventLog(log_path)

        svc1 = self._make_service(resolver1, store1, log1)

        result = svc1.create_funded_listing(
            listing_id="L-FIELDS",
            title="Fields persistence test",
            description="Testing listing field persistence",
            creator_id="creator-1",
            mission_reward=Decimal("750"),
            deadline_days=14,
        )
        assert result.success
        escrow_id = result.data["escrow_id"]

        # Restart
        store2 = StateStore(store_path)
        log2 = EventLog(log_path)
        resolver2 = PolicyResolver.from_config_dir(CONFIG_DIR)
        svc2 = GenesisService(resolver2, event_log=log2, state_store=store2)

        listing = svc2._listings.get("L-FIELDS")
        assert listing is not None, "Listing must survive restart"
        assert listing.mission_reward == Decimal("750"), \
            f"mission_reward should be 750, got {listing.mission_reward}"
        assert listing.escrow_id == escrow_id, \
            f"escrow_id should be {escrow_id}, got {listing.escrow_id}"
        assert listing.deadline_days == 14, \
            f"deadline_days should be 14, got {listing.deadline_days}"
