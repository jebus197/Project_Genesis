"""Append-only event log — the canonical record of all governance actions.

Every state change in Genesis produces an event record that is appended
to the log. Events are immutable once written. The log serves as:
1. The input to Merkle tree computation for epoch commitments.
2. The audit trail for third-party verification.
3. The source of truth for state reconstruction.

Constitutional invariant: "Can trust decisions occur without audit trail?
If yes, reject design." — This module ensures the answer is always no.
"""

from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class EventKind(str, enum.Enum):
    """Classification of governance events."""
    MISSION_CREATED = "mission_created"
    MISSION_TRANSITION = "mission_transition"
    REVIEWER_ASSIGNED = "reviewer_assigned"
    REVIEW_SUBMITTED = "review_submitted"
    EVIDENCE_ADDED = "evidence_added"
    TRUST_UPDATED = "trust_updated"
    ACTOR_REGISTERED = "actor_registered"
    ACTOR_STATUS_CHANGED = "actor_status_changed"
    EPOCH_OPENED = "epoch_opened"
    EPOCH_CLOSED = "epoch_closed"
    COMMITMENT_ANCHORED = "commitment_anchored"
    GOVERNANCE_BALLOT = "governance_ballot"
    PHASE_TRANSITION = "phase_transition"
    QUALITY_ASSESSED = "quality_assessed"
    # Market events
    LISTING_CREATED = "listing_created"
    LISTING_TRANSITION = "listing_transition"
    BID_SUBMITTED = "bid_submitted"
    WORKER_ALLOCATED = "worker_allocated"
    # Skill lifecycle events
    SKILL_UPDATED = "skill_updated"
    SKILL_ENDORSED = "skill_endorsed"
    SKILL_DECAYED = "skill_decayed"
    # Protected leave events
    LEAVE_REQUESTED = "leave_requested"
    LEAVE_ADJUDICATED = "leave_adjudicated"
    LEAVE_APPROVED = "leave_approved"
    LEAVE_DENIED = "leave_denied"
    LEAVE_RETURNED = "leave_returned"
    LEAVE_PERMANENT = "leave_permanent"  # Legacy — kept for log compat
    LEAVE_MEMORIALISED = "leave_memorialised"
    LEAVE_RESTORED = "leave_restored"
    # Compensation events
    ESCROW_CREATED = "escrow_created"
    ESCROW_LOCKED = "escrow_locked"
    ESCROW_RELEASED = "escrow_released"
    ESCROW_REFUNDED = "escrow_refunded"
    ESCROW_DISPUTED = "escrow_disputed"
    COMMISSION_COMPUTED = "commission_computed"
    OPERATIONAL_COST_RECORDED = "operational_cost_recorded"
    RESERVE_CONTRIBUTION = "reserve_contribution"
    PAYMENT_COMPLETED = "payment_completed"
    CREATOR_ALLOCATION_DISBURSED = "creator_allocation_disbursed"
    # Governance lifecycle events
    FOUNDER_VETO_EXERCISED = "founder_veto_exercised"
    FOUNDER_VETO_EXPIRED = "founder_veto_expired"
    # Platform lifecycle events
    FIRST_LIGHT = "first_light"
    MACHINE_REGISTERED = "machine_registered"
    # Machine immune system events
    MACHINE_QUARANTINED = "machine_quarantined"
    MACHINE_DECOMMISSIONED = "machine_decommissioned"
    MACHINE_RECERTIFICATION_STARTED = "machine_recertification_started"
    MACHINE_RECERTIFICATION_COMPLETED = "machine_recertification_completed"
    MACHINE_RECERTIFICATION_FAILED = "machine_recertification_failed"
    # Identity verification events
    IDENTITY_VERIFICATION_REQUESTED = "identity_verification_requested"
    IDENTITY_VERIFIED = "identity_verified"
    IDENTITY_LAPSED = "identity_lapsed"
    IDENTITY_FLAGGED = "identity_flagged"
    # Trust profile minting events
    TRUST_PROFILE_MINTED = "trust_profile_minted"
    # Quorum verification safeguard events
    QUORUM_PANEL_FORMED = "quorum_panel_formed"
    QUORUM_VOTE_CAST = "quorum_vote_cast"
    QUORUM_RECUSAL_DECLARED = "quorum_recusal_declared"
    QUORUM_VERIFICATION_COMPLETED = "quorum_verification_completed"
    QUORUM_APPEAL_FILED = "quorum_appeal_filed"
    QUORUM_SESSION_EVIDENCE = "quorum_session_evidence"
    QUORUM_ABUSE_COMPLAINT = "quorum_abuse_complaint"
    QUORUM_ABUSE_CONFIRMED = "quorum_abuse_confirmed"
    QUORUM_NUKE_APPEAL_FILED = "quorum_nuke_appeal_filed"
    QUORUM_NUKE_APPEAL_RESOLVED = "quorum_nuke_appeal_resolved"
    # Genesis Common Fund (GCF) events
    GCF_ACTIVATED = "gcf_activated"
    GCF_CONTRIBUTION_RECORDED = "gcf_contribution_recorded"
    # Compliance events (Phase E-2)
    COMPLIANCE_SCREENING_COMPLETED = "compliance_screening_completed"
    COMPLIANCE_COMPLAINT_FILED = "compliance_complaint_filed"
    COMPLIANCE_REVIEW_INITIATED = "compliance_review_initiated"
    COMPLIANCE_REVIEW_COMPLETED = "compliance_review_completed"
    ACTOR_SUSPENDED = "actor_suspended"
    ACTOR_PERMANENTLY_DECOMMISSIONED = "actor_permanently_decommissioned"
    # Adjudication events (Phase E-3: Three-Tier Justice)
    ADJUDICATION_OPENED = "adjudication_opened"
    ADJUDICATION_RESPONSE_SUBMITTED = "adjudication_response_submitted"
    ADJUDICATION_PANEL_FORMED = "adjudication_panel_formed"
    ADJUDICATION_VOTE_CAST = "adjudication_vote_cast"
    ADJUDICATION_DECIDED = "adjudication_decided"
    ADJUDICATION_APPEAL_FILED = "adjudication_appeal_filed"
    ADJUDICATION_CLOSED = "adjudication_closed"
    CONSTITUTIONAL_COURT_OPENED = "constitutional_court_opened"
    CONSTITUTIONAL_COURT_DECIDED = "constitutional_court_decided"
    REHABILITATION_STARTED = "rehabilitation_started"
    # Workflow orchestration events (Phase E-4)
    WORKFLOW_CREATED = "workflow_created"
    ESCROW_WORKFLOW_FUNDED = "escrow_workflow_funded"
    WORK_SUBMITTED = "work_submitted"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    PAYMENT_DISPUTE_FILED = "payment_dispute_filed"
    DISPUTE_RESOLVED = "dispute_resolved"
    # GCF Disbursement events (Phase E-5)
    GCF_DISBURSEMENT_PROPOSED = "gcf_disbursement_proposed"
    GCF_DISBURSEMENT_VOTE_CAST = "gcf_disbursement_vote_cast"
    GCF_DISBURSEMENT_APPROVED = "gcf_disbursement_approved"
    GCF_DISBURSEMENT_REJECTED = "gcf_disbursement_rejected"
    GCF_DISBURSEMENT_EXECUTED = "gcf_disbursement_executed"
    GCF_FUNDED_LISTING_CREATED = "gcf_funded_listing_created"
    # Constitutional amendment events (Phase E-6)
    AMENDMENT_PROPOSED = "amendment_proposed"
    AMENDMENT_CHAMBER_VOTE_CAST = "amendment_chamber_vote_cast"
    AMENDMENT_CHAMBER_PASSED = "amendment_chamber_passed"
    AMENDMENT_CHAMBER_FAILED = "amendment_chamber_failed"
    AMENDMENT_CHALLENGED = "amendment_challenged"
    AMENDMENT_COOLING_OFF_STARTED = "amendment_cooling_off_started"
    AMENDMENT_CONFIRMED = "amendment_confirmed"
    AMENDMENT_REJECTED = "amendment_rejected"
    # G0 retroactive ratification events (Gap 3)
    G0_RATIFICATION_SUBMITTED = "g0_ratification_submitted"
    G0_DECISION_RATIFIED = "g0_decision_ratified"
    G0_DECISION_LAPSED = "g0_decision_lapsed"
    G0_DECISION_REVERSED = "g0_decision_reversed"
    # Open Work Principle events
    VISIBILITY_RESTRICTED = "visibility_restricted"
    VISIBILITY_RESTRICTION_LAPSED = "visibility_restriction_lapsed"
    # Assembly events (Phase F-1)
    ASSEMBLY_TOPIC_CREATED = "assembly_topic_created"
    ASSEMBLY_CONTRIBUTION_ADDED = "assembly_contribution_added"
    ASSEMBLY_TOPIC_ARCHIVED = "assembly_topic_archived"
    # Organisation Registry events (Phase F-2)
    ORG_CREATED = "org_created"
    ORG_MEMBER_NOMINATED = "org_member_nominated"
    ORG_MEMBER_ATTESTED = "org_member_attested"
    ORG_MEMBER_REMOVED = "org_member_removed"
    ORG_TIER_CHANGED = "org_tier_changed"
    # Domain Expert / Machine Clearance events (Phase F-3)
    CLEARANCE_NOMINATED = "clearance_nominated"
    CLEARANCE_VOTE_CAST = "clearance_vote_cast"
    CLEARANCE_APPROVED = "clearance_approved"
    CLEARANCE_REVOKED = "clearance_revoked"
    CLEARANCE_EXPIRED = "clearance_expired"
    CLEARANCE_RENEWAL_STARTED = "clearance_renewal_started"


@dataclass(frozen=True)
class EventRecord:
    """A single immutable event in the governance log.

    Once created, an event cannot be modified. The event_hash is
    computed at creation time and serves as the leaf hash for
    Merkle tree inclusion.
    """
    event_id: str
    event_kind: EventKind
    timestamp_utc: str
    actor_id: str
    payload: dict[str, Any]
    event_hash: str  # SHA-256 of canonical JSON

    @staticmethod
    def create(
        event_id: str,
        event_kind: EventKind,
        actor_id: str,
        payload: dict[str, Any],
        timestamp_utc: Optional[datetime] = None,
    ) -> EventRecord:
        """Create a new event record with computed hash."""
        ts = timestamp_utc or datetime.now(timezone.utc)
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Compute canonical hash
        canonical = json.dumps(
            {
                "event_id": event_id,
                "event_kind": event_kind.value,
                "timestamp_utc": ts_str,
                "actor_id": actor_id,
                "payload": payload,
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()

        return EventRecord(
            event_id=event_id,
            event_kind=event_kind,
            timestamp_utc=ts_str,
            actor_id=actor_id,
            payload=payload,
            event_hash=f"sha256:{digest}",
        )


class EventLog:
    """Append-only event log with optional file persistence.

    Events can only be appended, never modified or deleted.
    The log can be persisted to a JSONL file (one JSON object per line)
    and loaded back for recovery.
    """

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self._events: list[EventRecord] = []
        self._storage_path = storage_path
        self._event_ids: set[str] = set()

        if storage_path and storage_path.exists():
            self._load_from_file(storage_path)

    def append(self, event: EventRecord) -> None:
        """Append an event to the log.

        Raises ValueError if event_id is a duplicate (replay protection).
        """
        if event.event_id in self._event_ids:
            raise ValueError(f"Duplicate event ID: {event.event_id}")

        self._events.append(event)
        self._event_ids.add(event.event_id)

        if self._storage_path:
            self._append_to_file(event)

    def events(self, kind: Optional[EventKind] = None) -> list[EventRecord]:
        """Return events, optionally filtered by kind."""
        if kind is None:
            return list(self._events)
        return [e for e in self._events if e.event_kind == kind]

    def events_since(
        self,
        since_utc: str,
        kind: Optional[EventKind] = None,
    ) -> list[EventRecord]:
        """Return events after a timestamp, optionally filtered by kind."""
        result = [e for e in self._events if e.timestamp_utc >= since_utc]
        if kind is not None:
            result = [e for e in result if e.event_kind == kind]
        return result

    def event_hashes(self, kind: Optional[EventKind] = None) -> list[str]:
        """Return all event hashes for Merkle tree construction."""
        return [e.event_hash for e in self.events(kind)]

    @property
    def count(self) -> int:
        return len(self._events)

    @property
    def last_event(self) -> Optional[EventRecord]:
        return self._events[-1] if self._events else None

    def _append_to_file(self, event: EventRecord) -> None:
        """Append a single event to the JSONL file."""
        record = {
            "event_id": event.event_id,
            "event_kind": event.event_kind.value,
            "timestamp_utc": event.timestamp_utc,
            "actor_id": event.actor_id,
            "payload": event.payload,
            "event_hash": event.event_hash,
        }
        with self._storage_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")

    def _load_from_file(self, path: Path) -> None:
        """Load events from a JSONL file with integrity verification.

        Fail-closed: rejects tampered records (hash mismatch) and
        duplicate event IDs (replay protection on recovery).
        """
        with path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)

                event_id = data["event_id"]

                # Replay protection: reject duplicate IDs on load
                if event_id in self._event_ids:
                    raise ValueError(
                        f"Duplicate event ID on recovery (line {line_num}): {event_id}"
                    )

                # Recompute canonical hash to verify integrity
                canonical = json.dumps(
                    {
                        "event_id": data["event_id"],
                        "event_kind": data["event_kind"],
                        "timestamp_utc": data["timestamp_utc"],
                        "actor_id": data["actor_id"],
                        "payload": data["payload"],
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                ).encode("utf-8")
                expected_hash = f"sha256:{hashlib.sha256(canonical).hexdigest()}"

                if data["event_hash"] != expected_hash:
                    raise ValueError(
                        f"Integrity check failed (line {line_num}): event {event_id} "
                        f"stored hash {data['event_hash']} != computed {expected_hash}"
                    )

                event = EventRecord(
                    event_id=data["event_id"],
                    event_kind=EventKind(data["event_kind"]),
                    timestamp_utc=data["timestamp_utc"],
                    actor_id=data["actor_id"],
                    payload=data["payload"],
                    event_hash=data["event_hash"],
                )
                self._events.append(event)
                self._event_ids.add(event.event_id)
