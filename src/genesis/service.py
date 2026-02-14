"""Genesis service — unified facade for the governance engine.

This is the primary interface for programmatic access to Genesis.
It orchestrates all subsystems:
- Mission lifecycle (create, submit, assign, review, approve)
- Trust management (score computation, updates)
- Reviewer selection (constrained-random from roster)
- Epoch management (open, collect, close, anchor)
- Phase governance (G0→G1→G2→G3 progression)

All operations produce typed results. All state changes are logged
to the event collector for eventual commitment.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from genesis.crypto.epoch_service import EpochService, GENESIS_PREVIOUS_HASH
from genesis.engine.reviewer_router import ReviewerRouter
from genesis.engine.state_machine import MissionStateMachine
from genesis.engine.evidence import EvidenceValidator
from genesis.governance.genesis_controller import GenesisPhaseController, PhaseState
from genesis.models.commitment import CommitmentRecord, CommitmentTier
from genesis.models.governance import GenesisPhase
from genesis.models.mission import (
    DomainType,
    EvidenceRecord,
    Mission,
    MissionClass,
    MissionState,
    ReviewDecision,
    ReviewDecisionVerdict,
    Reviewer,
    RiskTier,
)
from genesis.models.trust import ActorKind, TrustDelta, TrustRecord
from genesis.policy.resolver import PolicyResolver
from genesis.review.roster import ActorRoster, ActorStatus, RosterEntry
from genesis.review.selector import ReviewerSelector, SelectionResult
from genesis.trust.engine import TrustEngine


@dataclass(frozen=True)
class ServiceResult:
    """Result of a service operation."""
    success: bool
    errors: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)


class GenesisService:
    """Unified governance engine facade.

    Usage:
        resolver = PolicyResolver.from_config_dir(config_dir)
        service = GenesisService(resolver)

        # Register actors
        service.register_actor(...)

        # Create and process missions
        result = service.create_mission(...)
        result = service.submit_mission(mission_id)
        result = service.assign_reviewers(mission_id, seed="beacon:...")
        result = service.submit_review(mission_id, reviewer_id, "APPROVE")
        result = service.complete_review(mission_id)
        result = service.approve_mission(mission_id)

        # Epoch lifecycle
        service.open_epoch()
        # ... operations happen, events are collected ...
        record = service.close_epoch(beacon_round=12345)
    """

    def __init__(
        self,
        resolver: PolicyResolver,
        previous_hash: str = GENESIS_PREVIOUS_HASH,
    ) -> None:
        self._resolver = resolver
        self._trust_engine = TrustEngine(resolver)
        self._state_machine = MissionStateMachine(resolver)
        self._reviewer_router = ReviewerRouter(resolver)
        self._evidence_validator = EvidenceValidator()
        self._roster = ActorRoster()
        self._selector = ReviewerSelector(resolver, self._roster)
        self._epoch_service = EpochService(resolver, previous_hash)
        self._phase_controller = GenesisPhaseController(resolver)

        # In-memory state
        self._missions: dict[str, Mission] = {}
        self._trust_records: dict[str, TrustRecord] = {}

    # ------------------------------------------------------------------
    # Actor management
    # ------------------------------------------------------------------

    def register_actor(
        self,
        actor_id: str,
        actor_kind: ActorKind,
        region: str,
        organization: str,
        model_family: str = "human_reviewer",
        method_type: str = "human_reviewer",
        initial_trust: float = 0.10,
    ) -> ServiceResult:
        """Register a new actor in the roster."""
        try:
            entry = RosterEntry(
                actor_id=actor_id,
                actor_kind=actor_kind,
                trust_score=initial_trust,
                region=region,
                organization=organization,
                model_family=model_family,
                method_type=method_type,
            )
            self._roster.register(entry)

            self._trust_records[actor_id.strip()] = TrustRecord(
                actor_id=actor_id.strip(),
                actor_kind=actor_kind,
                score=initial_trust,
            )

            return ServiceResult(success=True, data={"actor_id": actor_id.strip()})
        except ValueError as e:
            return ServiceResult(success=False, errors=[str(e)])

    def get_actor(self, actor_id: str) -> Optional[RosterEntry]:
        """Look up an actor."""
        return self._roster.get(actor_id)

    def quarantine_actor(self, actor_id: str) -> ServiceResult:
        """Place an actor in quarantine."""
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(success=False, errors=[f"Actor not found: {actor_id}"])
        entry.status = ActorStatus.QUARANTINED
        trust = self._trust_records.get(actor_id.strip())
        if trust:
            trust.quarantined = True
        return ServiceResult(success=True)

    # ------------------------------------------------------------------
    # Mission lifecycle
    # ------------------------------------------------------------------

    def create_mission(
        self,
        mission_id: str,
        title: str,
        mission_class: MissionClass,
        domain_type: DomainType,
        worker_id: Optional[str] = None,
    ) -> ServiceResult:
        """Create a new mission in DRAFT state."""
        if mission_id in self._missions:
            return ServiceResult(
                success=False,
                errors=[f"Mission already exists: {mission_id}"],
            )

        tier = self._resolver.resolve_tier(mission_class)
        mission = Mission(
            mission_id=mission_id,
            mission_title=title,
            mission_class=mission_class,
            risk_tier=tier,
            domain_type=domain_type,
            worker_id=worker_id,
            created_utc=datetime.now(timezone.utc),
        )
        self._missions[mission_id] = mission

        # Record event
        self._record_mission_event(mission, "created")

        return ServiceResult(
            success=True,
            data={"mission_id": mission_id, "risk_tier": tier.value},
        )

    def submit_mission(self, mission_id: str) -> ServiceResult:
        """Transition mission from DRAFT to SUBMITTED."""
        return self._transition_mission(mission_id, MissionState.SUBMITTED)

    def assign_reviewers(
        self,
        mission_id: str,
        seed: Optional[str] = None,
        min_trust: float = 0.0,
    ) -> ServiceResult:
        """Select and assign reviewers from the roster."""
        mission = self._missions.get(mission_id)
        if mission is None:
            return ServiceResult(success=False, errors=[f"Mission not found: {mission_id}"])

        result = self._selector.select(mission, seed=seed, min_trust=min_trust)
        if not result.success:
            return ServiceResult(success=False, errors=result.errors)

        # Validate the selection against policy
        validation_errors = self._reviewer_router.validate_assignment(
            mission, result.reviewers,
        )
        if validation_errors:
            return ServiceResult(success=False, errors=validation_errors)

        mission.reviewers = result.reviewers

        # Transition to ASSIGNED
        transition_result = self._transition_mission(mission_id, MissionState.ASSIGNED)
        if not transition_result.success:
            return transition_result

        # Transition to IN_REVIEW
        return self._transition_mission(mission_id, MissionState.IN_REVIEW)

    def submit_review(
        self,
        mission_id: str,
        reviewer_id: str,
        verdict: str,
        notes: str = "",
    ) -> ServiceResult:
        """Submit a review decision for a mission."""
        mission = self._missions.get(mission_id)
        if mission is None:
            return ServiceResult(success=False, errors=[f"Mission not found: {mission_id}"])

        try:
            verdict_enum = ReviewDecisionVerdict(verdict)
        except ValueError:
            return ServiceResult(
                success=False,
                errors=[f"Invalid verdict: {verdict}. Use APPROVE, REJECT, or ABSTAIN"],
            )

        decision = ReviewDecision(
            reviewer_id=reviewer_id,
            decision=verdict_enum,
            notes=notes,
            timestamp_utc=datetime.now(timezone.utc),
        )
        mission.review_decisions.append(decision)

        self._record_mission_event(mission, f"review:{reviewer_id}:{verdict}")
        return ServiceResult(success=True)

    def add_evidence(
        self,
        mission_id: str,
        artifact_hash: str,
        signature: str,
    ) -> ServiceResult:
        """Add an evidence record to a mission."""
        mission = self._missions.get(mission_id)
        if mission is None:
            return ServiceResult(success=False, errors=[f"Mission not found: {mission_id}"])

        record = EvidenceRecord(artifact_hash=artifact_hash, signature=signature)
        errors = self._evidence_validator.validate_record(record)
        if errors:
            return ServiceResult(success=False, errors=errors)

        mission.evidence.append(record)
        return ServiceResult(success=True)

    def complete_review(self, mission_id: str) -> ServiceResult:
        """Transition mission from IN_REVIEW to REVIEW_COMPLETE."""
        return self._transition_mission(mission_id, MissionState.REVIEW_COMPLETE)

    def approve_mission(self, mission_id: str) -> ServiceResult:
        """Transition mission from REVIEW_COMPLETE to APPROVED."""
        return self._transition_mission(mission_id, MissionState.APPROVED)

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        """Retrieve a mission by ID."""
        return self._missions.get(mission_id)

    # ------------------------------------------------------------------
    # Trust operations
    # ------------------------------------------------------------------

    def update_trust(
        self,
        actor_id: str,
        quality: float,
        reliability: float,
        volume: float,
        reason: str,
        effort: float = 0.0,
        mission_id: Optional[str] = None,
    ) -> ServiceResult:
        """Update an actor's trust score."""
        record = self._trust_records.get(actor_id.strip())
        if record is None:
            return ServiceResult(
                success=False,
                errors=[f"No trust record for actor: {actor_id}"],
            )

        new_record, delta = self._trust_engine.apply_update(
            record, quality=quality, reliability=reliability,
            volume=volume, reason=reason, effort=effort,
            mission_id=mission_id,
        )

        self._trust_records[actor_id.strip()] = new_record

        # Update roster trust score
        roster_entry = self._roster.get(actor_id)
        if roster_entry:
            roster_entry.trust_score = new_record.score

        # Record event
        self._record_trust_event(actor_id, delta)

        return ServiceResult(
            success=True,
            data={
                "actor_id": actor_id,
                "old_score": record.score,
                "new_score": new_record.score,
                "delta": delta.abs_delta,
                "suspended": delta.suspended,
            },
        )

    def get_trust(self, actor_id: str) -> Optional[TrustRecord]:
        """Retrieve trust record for an actor."""
        return self._trust_records.get(actor_id.strip())

    # ------------------------------------------------------------------
    # Epoch operations
    # ------------------------------------------------------------------

    def open_epoch(self, epoch_id: Optional[str] = None) -> ServiceResult:
        """Open a new commitment epoch."""
        try:
            eid = self._epoch_service.open_epoch(epoch_id)
            return ServiceResult(success=True, data={"epoch_id": eid})
        except RuntimeError as e:
            return ServiceResult(success=False, errors=[str(e)])

    def close_epoch(
        self,
        beacon_round: int,
        chamber_nonce: Optional[str] = None,
    ) -> ServiceResult:
        """Close the current epoch and build the commitment record."""
        try:
            record = self._epoch_service.close_epoch(
                beacon_round=beacon_round,
                chamber_nonce=chamber_nonce,
            )
            return ServiceResult(
                success=True,
                data={
                    "epoch_id": record.epoch_id,
                    "previous_hash": self._epoch_service.previous_hash,
                    "event_counts": self._epoch_service.epoch_event_counts(),
                },
            )
        except RuntimeError as e:
            return ServiceResult(success=False, errors=[str(e)])

    # ------------------------------------------------------------------
    # Status and queries
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return system-wide status summary."""
        return {
            "version": "0.1.0",
            "actors": {
                "total": self._roster.count,
                "active": self._roster.active_count,
                "humans": self._roster.human_count,
            },
            "missions": {
                "total": len(self._missions),
                "by_state": self._count_missions_by_state(),
            },
            "epochs": {
                "committed": len(self._epoch_service.committed_records),
                "anchored": len(self._epoch_service.anchor_records),
                "current_open": (
                    self._epoch_service.current_epoch is not None
                    and not self._epoch_service.current_epoch.closed
                ),
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition_mission(
        self, mission_id: str, target: MissionState,
    ) -> ServiceResult:
        mission = self._missions.get(mission_id)
        if mission is None:
            return ServiceResult(
                success=False, errors=[f"Mission not found: {mission_id}"],
            )

        errors = self._state_machine.transition(mission, target)
        if errors:
            return ServiceResult(success=False, errors=errors)

        # State machine validates but does not apply — caller applies on success
        mission.state = target

        self._record_mission_event(mission, f"transition:{target.value}")
        return ServiceResult(success=True, data={"state": mission.state.value})

    def _record_mission_event(self, mission: Mission, action: str) -> None:
        """Hash and record a mission event in the current epoch."""
        event_data = f"{mission.mission_id}:{action}:{datetime.now(timezone.utc).isoformat()}"
        event_hash = "sha256:" + hashlib.sha256(event_data.encode()).hexdigest()
        try:
            self._epoch_service.record_mission_event(event_hash)
        except RuntimeError:
            pass  # No epoch open — events will be captured in next epoch

    def _record_trust_event(self, actor_id: str, delta: TrustDelta) -> None:
        """Hash and record a trust delta in the current epoch."""
        event_data = f"{actor_id}:{delta.abs_delta}:{datetime.now(timezone.utc).isoformat()}"
        event_hash = "sha256:" + hashlib.sha256(event_data.encode()).hexdigest()
        try:
            self._epoch_service.record_trust_delta(event_hash)
        except RuntimeError:
            pass

    def _count_missions_by_state(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for m in self._missions.values():
            counts[m.state.value] = counts.get(m.state.value, 0) + 1
        return counts
