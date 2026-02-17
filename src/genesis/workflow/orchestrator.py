"""Workflow orchestrator — bridges market, mission, escrow, and compliance.

The orchestrator is a thin coordination layer that wires together the
four independent subsystems (market, mission, escrow, compliance) into
a coherent end-to-end workflow. It does NOT replace any subsystem — it
calls existing methods in the correct sequence and tracks overall state.

Constitutional requirements:
- No listing goes live without escrowed funds (escrow-first).
- All listings screened for compliance before publication.
- Payment disputes route through the justice system (E-3 adjudication).
- Cancellation returns full escrow (including employer creator fee).
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional


class WorkflowStatus(str, enum.Enum):
    """Status of an end-to-end workflow."""
    LISTING_CREATED = "listing_created"
    ESCROW_FUNDED = "escrow_funded"
    LISTING_LIVE = "listing_live"
    BIDS_OPEN = "bids_open"
    WORKER_ALLOCATED = "worker_allocated"
    WORK_IN_PROGRESS = "work_in_progress"
    WORK_SUBMITTED = "work_submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PAYMENT_PROCESSING = "payment_processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"
    REFUNDED = "refunded"


@dataclass
class WorkflowState:
    """Tracks the end-to-end state of a listing→mission→payment workflow."""
    workflow_id: str
    listing_id: str
    creator_id: str
    mission_reward: Decimal
    status: WorkflowStatus = WorkflowStatus.LISTING_CREATED
    mission_id: Optional[str] = None
    escrow_id: Optional[str] = None
    worker_id: Optional[str] = None
    mission_class: Optional[str] = None
    domain_type: Optional[str] = None
    compliance_verdict: Optional[str] = None
    compliance_screened_utc: Optional[datetime] = None
    work_submitted_utc: Optional[datetime] = None
    work_evidence_hashes: list[str] = field(default_factory=list)
    deadline_utc: Optional[datetime] = None
    dispute_case_id: Optional[str] = None
    created_utc: Optional[datetime] = None
    cancelled_utc: Optional[datetime] = None
    completed_utc: Optional[datetime] = None


class WorkflowOrchestrator:
    """Coordinates the end-to-end workflow across subsystems.

    Pure coordination — holds only workflow state. All subsystem state
    lives in the respective subsystem (EscrowManager, ComplianceScreener,
    AdjudicationEngine, etc.). The orchestrator calls them in sequence.

    Usage:
        orch = WorkflowOrchestrator(config)
        wf = orch.create_workflow("listing-1", "creator-1", Decimal("500"))
        wf = orch.record_compliance_screening(wf.workflow_id, "clear")
        wf = orch.record_escrow_funded(wf.workflow_id, "escrow-1")
        ...
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._workflows: dict[str, WorkflowState] = {}
        self._default_deadline_days = config.get("default_deadline_days", 30)

    def create_workflow(
        self,
        listing_id: str,
        creator_id: str,
        mission_reward: Decimal,
        now: Optional[datetime] = None,
    ) -> WorkflowState:
        """Create a new workflow record for a listing.

        Called after the listing has been created. Tracks the overall
        workflow state from listing creation through payment.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        workflow_id = f"wf-{uuid.uuid4().hex[:12]}"
        wf = WorkflowState(
            workflow_id=workflow_id,
            listing_id=listing_id,
            creator_id=creator_id,
            mission_reward=mission_reward,
            status=WorkflowStatus.LISTING_CREATED,
            created_utc=now,
        )
        self._workflows[workflow_id] = wf
        return wf

    def record_compliance_screening(
        self,
        workflow_id: str,
        verdict: str,
        now: Optional[datetime] = None,
    ) -> WorkflowState:
        """Record the compliance screening result on the workflow."""
        wf = self._get(workflow_id)
        if now is None:
            now = datetime.now(timezone.utc)
        wf.compliance_verdict = verdict
        wf.compliance_screened_utc = now
        return wf

    def record_escrow_funded(
        self,
        workflow_id: str,
        escrow_id: str,
    ) -> WorkflowState:
        """Record that escrow has been created and funded (locked)."""
        wf = self._get(workflow_id)
        wf.escrow_id = escrow_id
        wf.status = WorkflowStatus.ESCROW_FUNDED
        return wf

    def record_listing_live(self, workflow_id: str) -> WorkflowState:
        """Record that the listing is now live and accepting bids."""
        wf = self._get(workflow_id)
        wf.status = WorkflowStatus.BIDS_OPEN
        return wf

    def record_worker_allocated(
        self,
        workflow_id: str,
        mission_id: str,
        worker_id: str,
        now: Optional[datetime] = None,
    ) -> WorkflowState:
        """Record that a worker has been allocated and mission created."""
        wf = self._get(workflow_id)
        if now is None:
            now = datetime.now(timezone.utc)
        wf.mission_id = mission_id
        wf.worker_id = worker_id
        wf.status = WorkflowStatus.WORK_IN_PROGRESS
        wf.deadline_utc = now + timedelta(days=self._default_deadline_days)
        return wf

    def record_work_submitted(
        self,
        workflow_id: str,
        evidence_hashes: list[str],
        now: Optional[datetime] = None,
    ) -> WorkflowState:
        """Record that the worker has submitted their work deliverables."""
        wf = self._get(workflow_id)
        if now is None:
            now = datetime.now(timezone.utc)
        wf.work_evidence_hashes = evidence_hashes
        wf.work_submitted_utc = now
        wf.status = WorkflowStatus.WORK_SUBMITTED
        return wf

    def record_approved(self, workflow_id: str) -> WorkflowState:
        """Record that the mission has been approved."""
        wf = self._get(workflow_id)
        wf.status = WorkflowStatus.APPROVED
        return wf

    def record_completed(
        self,
        workflow_id: str,
        now: Optional[datetime] = None,
    ) -> WorkflowState:
        """Record that payment has been processed and workflow is complete."""
        wf = self._get(workflow_id)
        if now is None:
            now = datetime.now(timezone.utc)
        wf.status = WorkflowStatus.COMPLETED
        wf.completed_utc = now
        return wf

    def record_cancelled(
        self,
        workflow_id: str,
        now: Optional[datetime] = None,
    ) -> WorkflowState:
        """Record that the workflow has been cancelled and escrow refunded."""
        wf = self._get(workflow_id)
        if now is None:
            now = datetime.now(timezone.utc)
        wf.status = WorkflowStatus.CANCELLED
        wf.cancelled_utc = now
        return wf

    def record_disputed(
        self,
        workflow_id: str,
        dispute_case_id: str,
    ) -> WorkflowState:
        """Record that a payment dispute has been filed."""
        wf = self._get(workflow_id)
        wf.dispute_case_id = dispute_case_id
        wf.status = WorkflowStatus.DISPUTED
        return wf

    def record_dispute_resolved(
        self,
        workflow_id: str,
        released_to_worker: bool,
        now: Optional[datetime] = None,
    ) -> WorkflowState:
        """Record that a dispute has been resolved."""
        wf = self._get(workflow_id)
        if now is None:
            now = datetime.now(timezone.utc)
        if released_to_worker:
            wf.status = WorkflowStatus.COMPLETED
            wf.completed_utc = now
        else:
            wf.status = WorkflowStatus.REFUNDED
            wf.cancelled_utc = now
        return wf

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowState]:
        """Look up a workflow by ID."""
        return self._workflows.get(workflow_id)

    def _get(self, workflow_id: str) -> WorkflowState:
        """Get workflow or raise ValueError."""
        wf = self._workflows.get(workflow_id)
        if wf is None:
            raise ValueError(f"Workflow not found: {workflow_id}")
        return wf
