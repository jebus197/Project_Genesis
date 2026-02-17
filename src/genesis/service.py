"""Genesis service — unified facade for the governance engine.

This is the primary interface for programmatic access to Genesis.
It orchestrates all subsystems:
- Mission lifecycle (create, submit, assign, review, approve)
- Quality assessment (derives quality from mission outcomes)
- Trust management (score computation, updates)
- Reviewer selection (constrained-random from roster)
- Epoch management (open, collect, close, anchor)
- Phase governance (G0→G1→G2→G3 progression)
- First Light monitoring (financial sustainability trigger)
- Persistence (event log, state store)

All operations produce typed results. All state changes are logged
to the event collector for eventual commitment. Audit-trail events
are never silently dropped — if no epoch is open, the operation fails
closed rather than proceeding without an audit record.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

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
from genesis.models.quality import (
    MissionQualityReport,
    ReviewerQualityAssessment,
)
from genesis.models.skill import (
    ActorSkillProfile,
    SkillId,
    SkillProficiency,
    SkillRequirement,
)
from genesis.models.domain_trust import DomainTrustScore, TrustStatus
from genesis.models.leave import (
    AdjudicationVerdict,
    LeaveAdjudication,
    LeaveCategory,
    LeaveRecord,
    LeaveState,
)
from genesis.models.market import (
    AllocationResult,
    Bid,
    BidState,
    ListingState,
    MarketListing,
)
from genesis.models.trust import ActorKind, TrustDelta, TrustRecord
from genesis.leave.engine import LeaveAdjudicationEngine
from genesis.market.allocator import AllocationEngine
from genesis.market.listing_state_machine import ListingStateMachine
from genesis.skills.decay import SkillDecayEngine
from genesis.skills.endorsement import EndorsementEngine
from genesis.skills.matching import SkillMatchEngine
from genesis.skills.outcome_updater import SkillOutcomeUpdater
from genesis.skills.worker_matcher import WorkerMatcher
from genesis.persistence.event_log import EventLog, EventRecord, EventKind
from genesis.persistence.state_store import StateStore
from genesis.policy.resolver import PolicyResolver
from genesis.quality.engine import QualityEngine
from genesis.review.roster import (
    ActorRoster,
    ActorStatus,
    IdentityVerificationStatus,
    RosterEntry,
)
from genesis.review.selector import ReviewerSelector, SelectionResult
from genesis.countdown.first_light import FirstLightEstimator
from genesis.skills.taxonomy import SkillTaxonomy
from genesis.identity.challenge import ChallengeGenerator
from genesis.identity.voice_verifier import VoiceVerifier
from genesis.identity.session import SessionManager, SessionState
from genesis.identity.quorum_verifier import QuorumVerifier
from genesis.trust.engine import TrustEngine
from genesis.compensation.gcf import GCFTracker
from genesis.compensation.escrow import EscrowManager
from genesis.compliance.screener import ComplianceScreener, ComplianceVerdict
from genesis.compliance.penalties import (
    PenaltyEscalationEngine,
    PenaltySeverity,
    PriorViolation,
    ViolationType,
)
from genesis.legal.adjudication import (
    AdjudicationEngine,
    AdjudicationType as LegalAdjudicationType,
    AdjudicationVerdict as LegalAdjudicationVerdict,
)
from genesis.legal.constitutional_court import ConstitutionalCourt
from genesis.legal.rights import RightsEnforcer
from genesis.legal.rehabilitation import RehabilitationEngine
from genesis.workflow.orchestrator import WorkflowOrchestrator, WorkflowStatus


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

    Persistence (optional):
        service = GenesisService(resolver, event_log=log, state_store=store)
        # State is persisted on each mutation and loaded on construction.
    """

    def __init__(
        self,
        resolver: PolicyResolver,
        previous_hash: str = GENESIS_PREVIOUS_HASH,
        event_log: Optional[EventLog] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        self._resolver = resolver
        self._trust_engine = TrustEngine(resolver)
        self._quality_engine = QualityEngine(resolver)
        self._state_machine = MissionStateMachine(resolver)
        self._reviewer_router = ReviewerRouter(resolver)
        self._evidence_validator = EvidenceValidator()
        self._phase_controller = GenesisPhaseController(resolver)

        # Skill taxonomy (optional — pre-labour-market mode if absent)
        self._taxonomy: Optional[SkillTaxonomy] = None
        if resolver.has_skill_taxonomy():
            self._taxonomy = SkillTaxonomy(resolver.skill_taxonomy_data())

        # Persistence layer (optional — in-memory if not provided)
        self._event_log = event_log
        self._state_store = state_store

        # Market layer
        self._allocation_engine = AllocationEngine(resolver)
        self._listing_sm = ListingStateMachine()
        self._match_engine = SkillMatchEngine(resolver)

        # Skill lifecycle engines
        self._skill_decay_engine = SkillDecayEngine(resolver)
        self._endorsement_engine = EndorsementEngine(resolver)
        self._skill_outcome_updater = SkillOutcomeUpdater(resolver)

        # Protected leave engine
        self._leave_engine = LeaveAdjudicationEngine(resolver)

        # Voice liveness subsystem (Phase D)
        vl_cfg = resolver.voice_liveness_config()
        self._challenge_generator = ChallengeGenerator(vl_cfg)
        self._voice_verifier = VoiceVerifier(vl_cfg)
        self._session_manager = SessionManager(
            self._challenge_generator, self._voice_verifier, vl_cfg,
        )
        self._quorum_verifier = QuorumVerifier(resolver.quorum_verification_config())

        # First Light sustainability monitor — extract config from policy
        fl_cfg = resolver._policy.get("first_light", {})
        self._first_light_estimator = FirstLightEstimator(
            sustainability_ratio=fl_cfg.get("sustainability_ratio", 1.5),
            reserve_months_required=fl_cfg.get("reserve_months_required", 3),
            ema_alpha=fl_cfg.get("ema_alpha", 0.3),
            network_beta=fl_cfg.get("network_beta", 0.15),
            confidence_sigma=fl_cfg.get("confidence_sigma", 1.0),
            min_data_points=fl_cfg.get("min_data_points", 3),
            min_rate_floor=fl_cfg.get("min_rate_floor_per_day", 0.01),
        )
        self._first_light_achieved: bool = False

        # Genesis Common Fund tracker — activates at First Light
        self._gcf_tracker = GCFTracker()

        # Escrow manager — manages escrow lifecycle for mission payments
        self._escrow_manager = EscrowManager()

        # Compliance subsystem (Phase E-2)
        self._compliance_screener = ComplianceScreener()
        self._penalty_engine = PenaltyEscalationEngine()
        self._prior_violations: dict[str, list[PriorViolation]] = {}
        self._suspended_until: dict[str, datetime] = {}

        # Legal framework (Phase E-3: Three-Tier Justice)
        adj_cfg = resolver.adjudication_config()
        self._adjudication_engine = AdjudicationEngine(adj_cfg)
        self._constitutional_court = ConstitutionalCourt(
            resolver.constitutional_court_config()
        )
        self._rights_enforcer = RightsEnforcer(
            response_period_hours=adj_cfg.get("response_period_hours", 72)
        )
        self._rehabilitation_engine = RehabilitationEngine(
            resolver.rehabilitation_config()
        )

        # Workflow orchestrator (Phase E-4)
        self._workflow_orchestrator = WorkflowOrchestrator(
            resolver.workflow_config()
        )
        self._workflows: dict[str, Any] = {}  # workflow_id → WorkflowState

        # Founder dormancy tracking — last cryptographically signed action.
        # Any signed action (login, transaction, governance, proof-of-life
        # attestation) resets the 50-year dormancy counter.
        self._founder_id: Optional[str] = None
        self._founder_last_action_utc: Optional[datetime] = None

        # Load persisted state or start fresh
        if state_store is not None:
            self._roster = state_store.load_roster()
            self._trust_records = state_store.load_trust_records()
            self._missions = state_store.load_missions()
            self._reviewer_assessment_history = state_store.load_reviewer_histories()
            self._skill_profiles = state_store.load_skill_profiles()
            self._listings, self._bids = state_store.load_listings()
            self._leave_records = state_store.load_leave_records()
            stored_hash, _ = state_store.load_epoch_state()
            self._epoch_service = EpochService(resolver, stored_hash)
            # Restore lifecycle state (First Light, founder dormancy)
            lifecycle = state_store.load_lifecycle_state()
            self._first_light_achieved = lifecycle["first_light_achieved"]
            self._founder_id = lifecycle["founder_id"]
            self._founder_last_action_utc = lifecycle["founder_last_action_utc"]
            # Restore PoC mode override and GCF activation if First Light was previously achieved
            if self._first_light_achieved:
                self._resolver._policy.setdefault("poc_mode", {})["active"] = False
                if not self._gcf_tracker.is_active:
                    self._gcf_tracker.activate(now=datetime.now(timezone.utc))
            # Restore escrow and workflow state
            escrow_records = state_store.load_escrows()
            if escrow_records:
                self._escrow_manager = EscrowManager.from_records(escrow_records)
            workflow_records = state_store.load_workflows()
            if workflow_records:
                self._workflow_orchestrator = WorkflowOrchestrator.from_records(
                    resolver.workflow_config(), workflow_records,
                )
        else:
            self._roster = ActorRoster()
            self._trust_records: dict[str, TrustRecord] = {}
            self._missions: dict[str, Mission] = {}
            self._reviewer_assessment_history: dict[str, list[ReviewerQualityAssessment]] = {}
            self._skill_profiles: dict[str, ActorSkillProfile] = {}
            self._listings: dict[str, MarketListing] = {}
            self._bids: dict[str, list[Bid]] = {}
            self._leave_records: dict[str, LeaveRecord] = {}
            self._epoch_service = EpochService(resolver, previous_hash)

        self._selector = ReviewerSelector(
            resolver, self._roster,
            skill_profiles=self._skill_profiles,
            trust_records=self._trust_records,
        )
        # Initialize counter from persisted log to avoid ID collision on restart
        self._event_counter = event_log.count if event_log is not None else 0
        # Leave ID counter: initialise from persisted records
        self._leave_counter = len(self._leave_records)

        # Persistence health flag: set to True if a StateStore write fails
        # after an audit event has been durably committed. In-memory state
        # remains correct (aligned with audit trail), but the StateStore is
        # stale and needs operator intervention or event-log replay.
        self._persistence_degraded: bool = False

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
        registered_by: Optional[str] = None,
        status: ActorStatus = ActorStatus.ACTIVE,
    ) -> ServiceResult:
        """Register a new actor in the roster.

        For human actors, delegates to register_human().
        For machine actors with registered_by, delegates to register_machine()
        which validates the operator.

        Actors default to PROVISIONAL status with score 0.0.
        Pass status=ActorStatus.ACTIVE for test convenience or legacy flows.
        """
        # Normalise actor_kind to enum if passed as string
        if isinstance(actor_kind, str):
            try:
                actor_kind = ActorKind(actor_kind.lower())
            except ValueError:
                return ServiceResult(
                    success=False,
                    errors=[f"Unknown actor kind: {actor_kind}"],
                )
        if actor_kind == ActorKind.HUMAN:
            return self.register_human(
                actor_id=actor_id,
                region=region,
                organization=organization,
                model_family=model_family,
                method_type=method_type,
                initial_trust=initial_trust,
                status=status,
            )
        elif actor_kind == ActorKind.MACHINE:
            if registered_by is not None:
                return self.register_machine(
                    actor_id=actor_id,
                    operator_id=registered_by,
                    region=region,
                    organization=organization,
                    model_family=model_family,
                    method_type=method_type,
                    initial_trust=initial_trust,
                    status=status,
                )
            # No legacy path — machines MUST have a human operator
            return ServiceResult(
                success=False,
                errors=["Machine registration requires a human operator (registered_by)."],
            )
        return ServiceResult(success=False, errors=[f"Unknown actor kind: {actor_kind}"])

    def register_human(
        self,
        actor_id: str,
        region: str,
        organization: str,
        model_family: str = "human_reviewer",
        method_type: str = "human_reviewer",
        initial_trust: float = 0.0,
        status: ActorStatus = ActorStatus.PROVISIONAL,
    ) -> ServiceResult:
        """Register a human actor (self-registration).

        Actors start as PROVISIONAL with score 0.0. They must complete
        liveness verification + first mission to mint their trust profile,
        which transitions them to ACTIVE with score 1/1000.
        """
        try:
            now = datetime.now(timezone.utc)
            entry = RosterEntry(
                actor_id=actor_id,
                actor_kind=ActorKind.HUMAN,
                trust_score=initial_trust,
                region=region,
                organization=organization,
                model_family=model_family,
                method_type=method_type,
                status=status,
                registered_utc=now,
            )
            self._roster.register(entry)

            aid = actor_id.strip()
            self._trust_records[aid] = TrustRecord(
                actor_id=aid,
                actor_kind=ActorKind.HUMAN,
                score=initial_trust,
            )

            # Log registration event
            if self._event_log is not None:
                try:
                    event = EventRecord.create(
                        event_id=self._next_event_id(),
                        event_kind=EventKind.ACTOR_REGISTERED,
                        actor_id=aid,
                        payload={"actor_kind": "human", "region": region},
                    )
                    self._event_log.append(event)
                except (ValueError, OSError):
                    pass  # Non-critical — roster update is the primary action

            def _rollback() -> None:
                self._roster._actors.pop(aid, None)
                self._trust_records.pop(aid, None)

            err = self._safe_persist(on_rollback=_rollback)
            if err:
                return ServiceResult(success=False, errors=[err])
            return ServiceResult(success=True, data={"actor_id": aid})
        except ValueError as e:
            return ServiceResult(success=False, errors=[str(e)])

    def register_machine(
        self,
        actor_id: str,
        operator_id: str,
        region: str,
        organization: str,
        model_family: str = "generic_model",
        method_type: str = "inference",
        initial_trust: float = 0.0,
        machine_metadata: Optional[dict] = None,
        status: ActorStatus = ActorStatus.PROVISIONAL,
    ) -> ServiceResult:
        """Register a machine actor under a verified human operator.

        Validates that the operator exists, is human, and is active.
        Machines cannot self-register — only verified humans can
        register machines.

        Actors start as PROVISIONAL with score 0.0. They must complete
        their first mission to mint their trust profile.
        """
        # Validate operator
        operator = self._roster.get(operator_id)
        if operator is None:
            return ServiceResult(
                success=False,
                errors=[f"Operator not found: {operator_id}"],
            )
        if operator.actor_kind != ActorKind.HUMAN:
            return ServiceResult(
                success=False,
                errors=["Only human actors can register machines"],
            )
        if not operator.is_available():
            return ServiceResult(
                success=False,
                errors=[f"Operator {operator_id} is not in an active state"],
            )

        # Lineage validation: if operator has decommissioned machines,
        # new registration must declare lineage_ids in machine_metadata.
        decommissioned_machines = [
            m for m in self._roster.machines_for_operator(operator_id)
            if m.status == ActorStatus.DECOMMISSIONED
        ]
        lineage_ids = (machine_metadata or {}).get("lineage_ids", [])
        if decommissioned_machines and not lineage_ids:
            return ServiceResult(
                success=False,
                errors=[
                    "Operator has decommissioned machines — new registration must "
                    "declare lineage_ids in machine_metadata"
                ],
            )

        try:
            now = datetime.now(timezone.utc)
            entry = RosterEntry(
                actor_id=actor_id,
                actor_kind=ActorKind.MACHINE,
                trust_score=initial_trust,
                region=region,
                organization=organization,
                model_family=model_family,
                method_type=method_type,
                status=status,
                registered_by=operator_id,
                registered_utc=now,
                machine_metadata=machine_metadata,
                lineage_ids=lineage_ids if lineage_ids else [],
            )
            self._roster.register(entry)

            aid = actor_id.strip()
            self._trust_records[aid] = TrustRecord(
                actor_id=aid,
                actor_kind=ActorKind.MACHINE,
                score=initial_trust,
            )

            # Log machine registration event
            if self._event_log is not None:
                try:
                    event = EventRecord.create(
                        event_id=self._next_event_id(),
                        event_kind=EventKind.MACHINE_REGISTERED,
                        actor_id=aid,
                        payload={
                            "actor_kind": "machine",
                            "registered_by": operator_id,
                            "model_family": model_family,
                            "method_type": method_type,
                            "region": region,
                        },
                    )
                    self._event_log.append(event)
                except (ValueError, OSError):
                    pass  # Non-critical — roster update is the primary action

            def _rollback() -> None:
                self._roster._actors.pop(aid, None)
                self._trust_records.pop(aid, None)

            err = self._safe_persist(on_rollback=_rollback)
            if err:
                return ServiceResult(success=False, errors=[err])
            return ServiceResult(success=True, data={"actor_id": aid})
        except ValueError as e:
            return ServiceResult(success=False, errors=[str(e)])

    def get_operator_machines(self, operator_id: str) -> list[RosterEntry]:
        """Return all machines registered under a human operator."""
        return self._roster.machines_for_operator(operator_id)

    def get_actor(self, actor_id: str) -> Optional[RosterEntry]:
        """Look up an actor."""
        return self._roster.get(actor_id)

    def quarantine_actor(self, actor_id: str) -> ServiceResult:
        """Place an actor in quarantine.

        Emits MACHINE_QUARANTINED event for machine actors.
        Rolls back on event or persistence failure.
        """
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(success=False, errors=[f"Actor not found: {actor_id}"])
        prev_status = entry.status
        entry.status = ActorStatus.QUARANTINED
        trust = self._trust_records.get(actor_id.strip())
        prev_quarantined = trust.quarantined if trust else None
        if trust:
            trust.quarantined = True

        def _rollback() -> None:
            entry.status = prev_status
            if trust and prev_quarantined is not None:
                trust.quarantined = prev_quarantined

        # Emit lifecycle event for machines
        if entry.actor_kind == ActorKind.MACHINE:
            err = self._record_actor_lifecycle_event(
                actor_id,
                EventKind.MACHINE_QUARANTINED,
                {"previous_status": prev_status.value},
            )
            if err:
                _rollback()
                return ServiceResult(success=False, errors=[err])

        err = self._safe_persist(on_rollback=_rollback)
        if err:
            return ServiceResult(success=False, errors=[err])
        return ServiceResult(success=True)

    # ------------------------------------------------------------------
    # Machine immune system — recertification lifecycle
    # ------------------------------------------------------------------

    def start_recertification(
        self,
        actor_id: str,
        reviewer_signatures: list[str],
    ) -> ServiceResult:
        """Begin the recertification process for a quarantined machine.

        Validates:
        - Actor exists, is a MACHINE, is QUARANTINED, and not decommissioned.
        - At least RECERT_REVIEW_SIGS unique valid reviewer signatures provided.

        Transitions: QUARANTINED → PROBATION. Resets probation counter.
        """
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(success=False, errors=[f"Actor not found: {actor_id}"])
        if entry.actor_kind != ActorKind.MACHINE:
            return ServiceResult(success=False, errors=["Only machines can be recertified"])
        if entry.status != ActorStatus.QUARANTINED:
            return ServiceResult(
                success=False,
                errors=[f"Actor must be quarantined to start recertification, got {entry.status.value}"],
            )
        trust = self._trust_records.get(actor_id.strip())
        if trust and trust.decommissioned:
            return ServiceResult(success=False, errors=["Decommissioned actors cannot be recertified"])

        # Validate reviewer signatures
        recert = self._resolver.recertification_requirements()
        required_sigs = recert["RECERT_REVIEW_SIGS"]
        unique_sigs = set(reviewer_signatures)
        # Filter out invalid / non-existent / self-referencing reviewers
        valid_sigs = set()
        for sig_id in unique_sigs:
            reviewer = self._roster.get(sig_id)
            if reviewer and reviewer.is_available() and sig_id != actor_id:
                valid_sigs.add(sig_id)
        if len(valid_sigs) < required_sigs:
            return ServiceResult(
                success=False,
                errors=[f"Need {required_sigs} valid reviewer signatures, got {len(valid_sigs)}"],
            )

        # Snapshot for rollback
        prev_status = entry.status
        prev_probation = trust.probation_tasks_completed if trust else 0

        entry.status = ActorStatus.PROBATION
        if trust:
            trust.probation_tasks_completed = 0

        # Emit lifecycle event
        err = self._record_actor_lifecycle_event(
            actor_id,
            EventKind.MACHINE_RECERTIFICATION_STARTED,
            {
                "reviewer_signatures": sorted(valid_sigs),
                "signature_count": len(valid_sigs),
            },
        )
        if err:
            entry.status = prev_status
            if trust:
                trust.probation_tasks_completed = prev_probation
            return ServiceResult(success=False, errors=[err])

        def _rollback() -> None:
            entry.status = prev_status
            if trust:
                trust.probation_tasks_completed = prev_probation

        err = self._safe_persist(on_rollback=_rollback)
        if err:
            return ServiceResult(success=False, errors=[err])
        return ServiceResult(success=True, data={"actor_id": actor_id, "status": "probation"})

    def complete_recertification(self, actor_id: str) -> ServiceResult:
        """Complete recertification for a machine on probation.

        Checks:
        - probation_tasks_completed >= RECERT_PROBATION_TASKS
        - quality >= RECERT_CORRECTNESS_MIN
        - reliability >= RECERT_REPRO_MIN

        Success: PROBATION → ACTIVE, quarantined=False.
        Failure: increments failure counter, may trigger auto-decommission.
        """
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(success=False, errors=[f"Actor not found: {actor_id}"])
        if entry.actor_kind != ActorKind.MACHINE:
            return ServiceResult(success=False, errors=["Only machines can complete recertification"])
        if entry.status != ActorStatus.PROBATION:
            return ServiceResult(
                success=False,
                errors=[f"Actor must be on probation, got {entry.status.value}"],
            )
        trust = self._trust_records.get(actor_id.strip())
        if trust is None:
            return ServiceResult(success=False, errors=[f"No trust record for {actor_id}"])

        recert = self._resolver.recertification_requirements()
        failures: list[str] = []
        if trust.probation_tasks_completed < recert["RECERT_PROBATION_TASKS"]:
            failures.append(
                f"Insufficient probation tasks: {trust.probation_tasks_completed}/{recert['RECERT_PROBATION_TASKS']}"
            )
        if trust.quality < recert["RECERT_CORRECTNESS_MIN"]:
            failures.append(
                f"Quality below minimum: {trust.quality:.4f} < {recert['RECERT_CORRECTNESS_MIN']}"
            )
        if trust.reliability < recert["RECERT_REPRO_MIN"]:
            failures.append(
                f"Reliability below minimum: {trust.reliability:.4f} < {recert['RECERT_REPRO_MIN']}"
            )

        if failures:
            # Recertification failed — increment failure counter
            now_ts = datetime.now(timezone.utc)
            fail_timestamps = list(trust.recertification_failure_timestamps) + [now_ts]
            trust.recertification_failures += 1
            trust.recertification_failure_timestamps = fail_timestamps

            # Emit failure event
            err = self._record_actor_lifecycle_event(
                actor_id,
                EventKind.MACHINE_RECERTIFICATION_FAILED,
                {"failures": failures, "failure_count": trust.recertification_failures},
            )
            if err:
                trust.recertification_failures -= 1
                trust.recertification_failure_timestamps = fail_timestamps[:-1]
                return ServiceResult(success=False, errors=[err])

            # Check windowed threshold for auto-decommission
            decomm = self._resolver.decommission_rules()
            windowed = self._trust_engine.count_windowed_failures(trust, now_ts)
            if windowed >= decomm["M_RECERT_FAIL_MAX"]:
                entry.status = ActorStatus.DECOMMISSIONED
                trust.decommissioned = True
                trust.score = 0.0
                derr = self._record_actor_lifecycle_event(
                    actor_id,
                    EventKind.MACHINE_DECOMMISSIONED,
                    {"reason": "recertification_failure_threshold", "windowed_failures": windowed},
                )
                if derr:
                    # Rollback decommission but keep failure recorded
                    entry.status = ActorStatus.PROBATION
                    trust.decommissioned = False

            persist_err = self._safe_persist(on_rollback=lambda: None)
            return ServiceResult(
                success=False,
                errors=failures,
                data={
                    "actor_id": actor_id,
                    "recertification_failures": trust.recertification_failures,
                    "decommissioned": trust.decommissioned,
                },
            )

        # Recertification succeeded
        prev_status = entry.status
        prev_quarantined = trust.quarantined
        entry.status = ActorStatus.ACTIVE
        trust.quarantined = False
        trust.last_recertification_utc = datetime.now(timezone.utc)

        err = self._record_actor_lifecycle_event(
            actor_id,
            EventKind.MACHINE_RECERTIFICATION_COMPLETED,
            {
                "probation_tasks": trust.probation_tasks_completed,
                "quality": trust.quality,
                "reliability": trust.reliability,
            },
        )
        if err:
            entry.status = prev_status
            trust.quarantined = prev_quarantined
            trust.last_recertification_utc = None
            return ServiceResult(success=False, errors=[err])

        def _rollback() -> None:
            entry.status = prev_status
            trust.quarantined = prev_quarantined

        err = self._safe_persist(on_rollback=_rollback)
        if err:
            return ServiceResult(success=False, errors=[err])
        return ServiceResult(success=True, data={"actor_id": actor_id, "status": "active"})

    def decommission_actor(self, actor_id: str, reason: str) -> ServiceResult:
        """Explicitly decommission an actor.

        Sets trust score to 0, marks decommissioned, updates roster.
        Emits MACHINE_DECOMMISSIONED event.
        """
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(success=False, errors=[f"Actor not found: {actor_id}"])
        if entry.status == ActorStatus.DECOMMISSIONED:
            return ServiceResult(success=False, errors=["Actor already decommissioned"])

        trust = self._trust_records.get(actor_id.strip())
        prev_status = entry.status
        prev_score = trust.score if trust else None
        prev_decomm = trust.decommissioned if trust else None
        prev_quarantined = trust.quarantined if trust else None

        entry.status = ActorStatus.DECOMMISSIONED
        if trust:
            trust.score = 0.0
            trust.decommissioned = True
            trust.quarantined = True

        err = self._record_actor_lifecycle_event(
            actor_id,
            EventKind.MACHINE_DECOMMISSIONED,
            {"reason": reason, "previous_status": prev_status.value},
        )
        if err:
            entry.status = prev_status
            if trust:
                trust.score = prev_score
                trust.decommissioned = prev_decomm
                trust.quarantined = prev_quarantined
            return ServiceResult(success=False, errors=[err])

        def _rollback() -> None:
            entry.status = prev_status
            if trust:
                trust.score = prev_score
                trust.decommissioned = prev_decomm
                trust.quarantined = prev_quarantined

        err = self._safe_persist(on_rollback=_rollback)
        if err:
            return ServiceResult(success=False, errors=[err])

        # Update roster trust score
        if trust:
            roster_entry = self._roster.get(actor_id)
            if roster_entry:
                roster_entry.trust_score = 0.0

        return ServiceResult(success=True, data={"actor_id": actor_id, "status": "decommissioned"})

    def check_auto_decommission(self) -> ServiceResult:
        """Auto-decommission machines quarantined with T=0 for too long.

        Checks all quarantined machines with trust score 0. If quarantined
        for >= M_ZERO_DECOMMISSION_DAYS, auto-decommissions.
        Should be called periodically (e.g. daily).
        """
        decomm = self._resolver.decommission_rules()
        threshold_days = decomm["M_ZERO_DECOMMISSION_DAYS"]
        now = datetime.now(timezone.utc)
        decommissioned: list[str] = []

        for actor_id, trust in list(self._trust_records.items()):
            if trust.actor_kind != ActorKind.MACHINE:
                continue
            if trust.decommissioned:
                continue
            if not trust.quarantined or trust.score > 0.0:
                continue

            entry = self._roster.get(actor_id)
            if entry is None or entry.status != ActorStatus.QUARANTINED:
                continue

            # Check how long quarantined — use last_active_utc as proxy
            quarantine_start = trust.last_active_utc or trust.last_recertification_utc
            if quarantine_start is None:
                continue  # No timestamp to judge duration

            if (now - quarantine_start).days >= threshold_days:
                entry.status = ActorStatus.DECOMMISSIONED
                trust.decommissioned = True
                trust.score = 0.0

                err = self._record_actor_lifecycle_event(
                    actor_id,
                    EventKind.MACHINE_DECOMMISSIONED,
                    {
                        "reason": "auto_decommission_zero_trust",
                        "quarantine_days": (now - quarantine_start).days,
                    },
                )
                if not err:
                    decommissioned.append(actor_id)
                    if entry:
                        entry.trust_score = 0.0

        if decommissioned:
            self._safe_persist(on_rollback=lambda: None)

        return ServiceResult(
            success=True,
            data={"decommissioned_count": len(decommissioned), "actors": decommissioned},
        )

    # ------------------------------------------------------------------
    # Identity verification lifecycle
    # ------------------------------------------------------------------

    def request_verification(self, actor_id: str) -> ServiceResult:
        """Request identity verification for an actor.

        Transitions: UNVERIFIED → PENDING.
        """
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(success=False, errors=[f"Actor not found: {actor_id}"])
        if entry.identity_status not in (
            IdentityVerificationStatus.UNVERIFIED,
            IdentityVerificationStatus.LAPSED,
        ):
            return ServiceResult(
                success=False,
                errors=[f"Cannot request verification from status {entry.identity_status.value}"],
            )

        prev_status = entry.identity_status
        entry.identity_status = IdentityVerificationStatus.PENDING

        err = self._record_actor_lifecycle_event(
            actor_id,
            EventKind.IDENTITY_VERIFICATION_REQUESTED,
            {"previous_status": prev_status.value},
        )
        if err:
            entry.identity_status = prev_status
            return ServiceResult(success=False, errors=[err])

        def _rollback() -> None:
            entry.identity_status = prev_status

        err = self._safe_persist(on_rollback=_rollback)
        if err:
            return ServiceResult(success=False, errors=[err])
        return ServiceResult(success=True, data={"actor_id": actor_id, "status": "pending"})

    def complete_verification(
        self,
        actor_id: str,
        method: str,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Complete identity verification for an actor.

        Transitions: PENDING → VERIFIED. Sets expiry based on config.
        """
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(success=False, errors=[f"Actor not found: {actor_id}"])
        if entry.identity_status != IdentityVerificationStatus.PENDING:
            return ServiceResult(
                success=False,
                errors=[f"Actor must be in PENDING status, got {entry.identity_status.value}"],
            )

        now = now or datetime.now(timezone.utc)
        id_config = self._resolver.identity_verification_config()
        expiry_days = id_config["verification_expiry_days"]

        prev_status = entry.identity_status
        prev_verified = entry.identity_verified_utc
        prev_expires = entry.identity_expires_utc
        prev_method = entry.identity_method

        entry.identity_status = IdentityVerificationStatus.VERIFIED
        entry.identity_verified_utc = now
        entry.identity_expires_utc = now + timedelta(days=expiry_days)
        entry.identity_method = method

        err = self._record_actor_lifecycle_event(
            actor_id,
            EventKind.IDENTITY_VERIFIED,
            {"method": method, "expires_utc": entry.identity_expires_utc.isoformat()},
        )
        if err:
            entry.identity_status = prev_status
            entry.identity_verified_utc = prev_verified
            entry.identity_expires_utc = prev_expires
            entry.identity_method = prev_method
            return ServiceResult(success=False, errors=[err])

        def _rollback() -> None:
            entry.identity_status = prev_status
            entry.identity_verified_utc = prev_verified
            entry.identity_expires_utc = prev_expires
            entry.identity_method = prev_method

        err = self._safe_persist(on_rollback=_rollback)
        if err:
            return ServiceResult(success=False, errors=[err])
        return ServiceResult(
            success=True,
            data={
                "actor_id": actor_id,
                "status": "verified",
                "expires_utc": entry.identity_expires_utc.isoformat(),
            },
        )

    # ------------------------------------------------------------------
    # Voice liveness challenge (Phase D)
    # ------------------------------------------------------------------

    def start_liveness_challenge(
        self,
        actor_id: str,
        language: str = "en",
        *,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Start a voice liveness challenge session for an actor.

        The actor must have a PENDING identity verification (call
        request_verification() first). Returns the challenge words
        that the actor must read aloud.
        """
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(success=False, errors=[f"Actor not found: {actor_id}"])

        if entry.identity_status != IdentityVerificationStatus.PENDING:
            return ServiceResult(
                success=False,
                errors=[
                    f"Actor must be in PENDING verification status to start liveness challenge, "
                    f"got {entry.identity_status.value}. Call request_verification() first."
                ],
            )

        try:
            session = self._session_manager.start_session(
                actor_id=actor_id, language=language, now=now,
            )
        except ValueError as exc:
            return ServiceResult(success=False, errors=[str(exc)])

        return ServiceResult(
            success=True,
            data={
                "session_id": session.session_id,
                "actor_id": actor_id,
                "words": list(session.challenge.words),
                "stage": session.current_stage,
                "state": session.state.value,
            },
        )

    def submit_liveness_response(
        self,
        actor_id: str,
        session_id: str,
        spoken_words: list[str],
        *,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Submit a spoken-word response for a liveness challenge.

        If the response passes, the actor's identity verification is
        automatically completed (PENDING → VERIFIED) with method
        'voice_liveness'.

        If the response fails but attempts remain, a new challenge is
        issued (retry). If all attempts are exhausted, the session
        fails and the actor must start over.
        """
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(success=False, errors=[f"Actor not found: {actor_id}"])

        try:
            session = self._session_manager.submit_response(
                session_id=session_id,
                spoken_words=spoken_words,
                now=now,
            )
        except (KeyError, ValueError) as exc:
            return ServiceResult(success=False, errors=[str(exc)])

        if session.actor_id != actor_id:
            return ServiceResult(
                success=False,
                errors=[f"Session {session_id} belongs to {session.actor_id}, not {actor_id}"],
            )

        result_data: dict[str, Any] = {
            "session_id": session_id,
            "actor_id": actor_id,
            "state": session.state.value,
            "stage": session.current_stage,
        }

        if session.last_result is not None:
            result_data["word_match_score"] = session.last_result.word_match_score
            result_data["words_matched"] = session.last_result.words_matched
            result_data["words_expected"] = session.last_result.words_expected

        if session.state == SessionState.PASSED:
            # Auto-complete identity verification on liveness pass
            verification_result = self.complete_verification(
                actor_id=actor_id, method="voice_liveness", now=now,
            )
            result_data["verification_completed"] = verification_result.success
            if not verification_result.success:
                result_data["verification_errors"] = verification_result.errors

        elif session.state == SessionState.CHALLENGE_ISSUED:
            # Retry — new challenge words available
            result_data["words"] = list(session.challenge.words)

        return ServiceResult(success=True, data=result_data)

    def request_quorum_verification(
        self,
        actor_id: str,
        *,
        quorum_size: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Request quorum-based identity verification (disability accommodation).

        An alternative to voice liveness. A panel of randomly selected
        verified humans in the same geographic region must unanimously
        confirm the actor's identity via live video.

        The actor must be in PENDING verification status.
        Verifiers must be ACTIVE, HUMAN, VERIFIED, trust-minted, and high-trust (>=0.70).
        """
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(success=False, errors=[f"Actor not found: {actor_id}"])

        if entry.identity_status != IdentityVerificationStatus.PENDING:
            return ServiceResult(
                success=False,
                errors=[
                    f"Actor must be in PENDING verification status, "
                    f"got {entry.identity_status.value}"
                ],
            )

        # Gather eligible verifiers: ACTIVE, HUMAN, VERIFIED, minted
        available_verifiers: list[tuple[str, float, str]] = []
        verifier_orgs: dict[str, str] = {}
        for roster_entry in self._roster.all_actors():
            if roster_entry.actor_id == actor_id:
                continue  # Can't verify yourself
            if roster_entry.status != ActorStatus.ACTIVE:
                continue
            if roster_entry.actor_kind != ActorKind.HUMAN:
                continue
            if roster_entry.identity_status != IdentityVerificationStatus.VERIFIED:
                continue
            trust_rec = self._trust_records.get(roster_entry.actor_id)
            if not trust_rec or not trust_rec.trust_minted:
                continue  # Must be trust-minted
            score = trust_rec.score
            available_verifiers.append(
                (roster_entry.actor_id, score, roster_entry.region)
            )
            verifier_orgs[roster_entry.actor_id] = roster_entry.organization

        try:
            request = self._quorum_verifier.request_quorum_verification(
                actor_id=actor_id,
                region=entry.region,
                available_verifiers=available_verifiers,
                verifier_orgs=verifier_orgs,
                quorum_size=quorum_size,
                now=now,
            )
        except ValueError as exc:
            return ServiceResult(success=False, errors=[str(exc)])

        # Emit QUORUM_PANEL_FORMED event
        self._record_actor_lifecycle_event(
            actor_id=actor_id,
            event_kind=EventKind.QUORUM_PANEL_FORMED,
            payload={
                "request_id": request.request_id,
                "quorum_size": request.quorum_size,
                "verifier_ids": request.verifier_ids,
                "applicant_pseudonym": request.applicant_pseudonym,
                "session_max_seconds": request.session_max_seconds,
                "scripted_intro_version": request.scripted_intro_version,
                "region_constraint": request.region_constraint,
                "has_challenge_phrase": request.challenge_phrase is not None,
            },
        )

        return ServiceResult(
            success=True,
            data={
                "request_id": request.request_id,
                "actor_id": actor_id,
                "quorum_size": request.quorum_size,
                "verifier_ids": request.verifier_ids,
                "region_constraint": request.region_constraint,
                "expires_utc": request.expires_utc.isoformat(),
                "applicant_pseudonym": request.applicant_pseudonym,
                "session_max_seconds": request.session_max_seconds,
                "scripted_intro": self._quorum_verifier.get_scripted_intro(
                    request.scripted_intro_version,
                ),
                "challenge_phrase": request.challenge_phrase,
                "pre_session_briefing": self._quorum_verifier.get_pre_session_briefing(
                    request.pre_session_briefing_version,
                ),
            },
        )

    def submit_quorum_vote(
        self,
        request_id: str,
        verifier_id: str,
        approved: bool,
        *,
        attestation: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Submit a verifier's vote on a quorum verification request.

        If all votes are in and unanimously approved, the actor's identity
        verification is automatically completed.
        """
        try:
            request = self._quorum_verifier.submit_vote(
                request_id=request_id,
                verifier_id=verifier_id,
                approved=approved,
                attestation=attestation,
            )
        except (KeyError, ValueError) as exc:
            return ServiceResult(success=False, errors=[str(exc)])

        # Emit QUORUM_VOTE_CAST event
        self._record_actor_lifecycle_event(
            actor_id=verifier_id,
            event_kind=EventKind.QUORUM_VOTE_CAST,
            payload={
                "request_id": request_id,
                "verifier_id": verifier_id,
                "approved": approved,
                "has_attestation": attestation is not None,
            },
        )

        # Check result
        result = self._quorum_verifier.check_result(request_id, now=now)

        result_data: dict[str, Any] = {
            "request_id": request_id,
            "verifier_id": verifier_id,
            "approved": approved,
            "votes_cast": len(request.votes),
            "quorum_size": request.quorum_size,
        }

        if result is True:
            # Unanimous approval — complete verification
            verification_result = self.complete_verification(
                actor_id=request.actor_id,
                method="quorum_verification",
                now=now,
            )
            result_data["verification_completed"] = verification_result.success
            result_data["outcome"] = "approved"
            self._record_actor_lifecycle_event(
                actor_id=request.actor_id,
                event_kind=EventKind.QUORUM_VERIFICATION_COMPLETED,
                payload={"request_id": request_id, "outcome": "approved"},
            )
        elif result is False:
            result_data["outcome"] = "rejected"
            self._record_actor_lifecycle_event(
                actor_id=request.actor_id,
                event_kind=EventKind.QUORUM_VERIFICATION_COMPLETED,
                payload={"request_id": request_id, "outcome": "rejected"},
            )
        else:
            result_data["outcome"] = "pending"

        return ServiceResult(success=True, data=result_data)

    def declare_quorum_recusal(
        self,
        request_id: str,
        verifier_id: str,
        reason: str,
    ) -> ServiceResult:
        """Declare a verifier's recusal from a quorum panel."""
        try:
            request = self._quorum_verifier.declare_recusal(
                request_id=request_id,
                verifier_id=verifier_id,
                reason=reason,
            )
        except (KeyError, ValueError) as exc:
            return ServiceResult(success=False, errors=[str(exc)])

        self._record_actor_lifecycle_event(
            actor_id=verifier_id,
            event_kind=EventKind.QUORUM_RECUSAL_DECLARED,
            payload={
                "request_id": request_id,
                "verifier_id": verifier_id,
                "reason": reason,
            },
        )
        return ServiceResult(
            success=True,
            data={"request_id": request_id, "recused": verifier_id},
        )

    def attach_quorum_evidence(
        self,
        request_id: str,
        evidence_hash: str,
    ) -> ServiceResult:
        """Attach session recording evidence hash to a quorum request."""
        try:
            request = self._quorum_verifier.attach_session_evidence(
                request_id=request_id,
                evidence_hash=evidence_hash,
            )
        except KeyError as exc:
            return ServiceResult(success=False, errors=[str(exc)])

        self._record_actor_lifecycle_event(
            actor_id=request.actor_id,
            event_kind=EventKind.QUORUM_SESSION_EVIDENCE,
            payload={
                "request_id": request_id,
                "evidence_hash": evidence_hash,
            },
        )
        return ServiceResult(
            success=True,
            data={"request_id": request_id, "evidence_hash": evidence_hash},
        )

    def file_quorum_abuse_complaint(
        self,
        request_id: str,
        reporter_id: str,
        complaint: str,
    ) -> ServiceResult:
        """File an abuse complaint against a quorum verification session."""
        try:
            request = self._quorum_verifier.file_abuse_complaint(
                request_id=request_id,
                reporter_id=reporter_id,
                complaint_text=complaint,
            )
        except KeyError as exc:
            return ServiceResult(success=False, errors=[str(exc)])

        self._record_actor_lifecycle_event(
            actor_id=reporter_id,
            event_kind=EventKind.QUORUM_ABUSE_COMPLAINT,
            payload={
                "request_id": request_id,
                "reporter_id": reporter_id,
            },
        )
        return ServiceResult(
            success=True,
            data={
                "request_id": request_id,
                "reporter_id": reporter_id,
                "recording_preserved": True,
            },
        )

    def review_quorum_abuse(
        self,
        request_id: str,
        review_panel_ids: list[str],
        votes: dict[str, bool],
        *,
        offending_verifier_id: Optional[str] = None,
    ) -> ServiceResult:
        """Review an abuse complaint. If confirmed, nuke offending verifier's trust.

        The review panel must be high-trust members (>=0.70). If majority
        confirms abuse, the offending verifier's trust is set to 0.001 (1/1000).
        """
        try:
            result = self._quorum_verifier.review_abuse_complaint(
                request_id=request_id,
                review_panel=review_panel_ids,
                votes=votes,
            )
        except (KeyError, ValueError) as exc:
            return ServiceResult(success=False, errors=[str(exc)])

        if result.confirmed and offending_verifier_id:
            # Store pre-nuke score on the request for potential appeal
            request = self._quorum_verifier.get_request(request_id)
            trust_rec = self._trust_records.get(offending_verifier_id)
            if trust_rec and request:
                request.pre_nuke_trust_score = trust_rec.score
                # Trust nuke: set offender's trust to 0.001
                trust_rec.score = self._quorum_verifier._abuse_trust_nuke
            elif trust_rec:
                trust_rec.score = self._quorum_verifier._abuse_trust_nuke

            self._record_actor_lifecycle_event(
                actor_id=offending_verifier_id,
                event_kind=EventKind.QUORUM_ABUSE_CONFIRMED,
                payload={
                    "request_id": request_id,
                    "offending_verifier_id": offending_verifier_id,
                    "trust_nuked_to": self._quorum_verifier._abuse_trust_nuke,
                    "review_panel": review_panel_ids,
                    "votes": votes,
                },
            )

        return ServiceResult(
            success=True,
            data={
                "request_id": request_id,
                "confirmed": result.confirmed,
                "trust_action_taken": result.trust_action_taken,
            },
        )

    def appeal_quorum_verification(
        self,
        actor_id: str,
        original_request_id: str,
        *,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Appeal a rejected quorum verification. Creates a new panel."""
        # Gather eligible verifiers (same logic as request_quorum_verification)
        available_verifiers: list[tuple[str, float, str]] = []
        verifier_orgs: dict[str, str] = {}
        for roster_entry in self._roster.all_actors():
            if roster_entry.actor_id == actor_id:
                continue
            if roster_entry.status != ActorStatus.ACTIVE:
                continue
            if roster_entry.actor_kind != ActorKind.HUMAN:
                continue
            if roster_entry.identity_status != IdentityVerificationStatus.VERIFIED:
                continue
            trust_rec = self._trust_records.get(roster_entry.actor_id)
            if not trust_rec or not trust_rec.trust_minted:
                continue
            score = trust_rec.score
            available_verifiers.append(
                (roster_entry.actor_id, score, roster_entry.region)
            )
            verifier_orgs[roster_entry.actor_id] = roster_entry.organization

        try:
            request = self._quorum_verifier.request_appeal(
                original_request_id=original_request_id,
                available_verifiers=available_verifiers,
                verifier_orgs=verifier_orgs,
                now=now,
            )
        except (KeyError, ValueError) as exc:
            return ServiceResult(success=False, errors=[str(exc)])

        self._record_actor_lifecycle_event(
            actor_id=actor_id,
            event_kind=EventKind.QUORUM_APPEAL_FILED,
            payload={
                "appeal_request_id": request.request_id,
                "original_request_id": original_request_id,
                "new_panel": request.verifier_ids,
            },
        )

        return ServiceResult(
            success=True,
            data={
                "appeal_request_id": request.request_id,
                "original_request_id": original_request_id,
                "verifier_ids": request.verifier_ids,
                "applicant_pseudonym": request.applicant_pseudonym,
            },
        )

    def signal_quorum_participant_ready(
        self,
        request_id: str,
        *,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Signal that the participant is ready to begin the live session.

        The session timer starts from this moment, not from request creation.
        This gives the participant unlimited preparation time.
        """
        try:
            request = self._quorum_verifier.signal_participant_ready(
                request_id, now=now,
            )
        except (KeyError, ValueError) as exc:
            return ServiceResult(success=False, errors=[str(exc)])

        return ServiceResult(
            success=True,
            data={
                "request_id": request_id,
                "participant_ready_utc": request.participant_ready_utc.isoformat(),
            },
        )

    def appeal_reviewer_trust_nuke(
        self,
        request_id: str,
        appellant_id: str,
        appeal_panel_ids: list[str],
        votes: dict[str, bool],
        *,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Appeal a trust-nuke decision via escalated 5-panel review.

        A reviewer whose trust was nuked to 0.001 can appeal once.
        Requires 4/5 supermajority to overturn. The appeal panel must
        be ACTIVE, HUMAN, trust-minted, >=0.70 trust, and must NOT
        overlap with the original abuse review panel.

        If overturned, the reviewer's trust is restored to pre-nuke level.
        Complainant trust is never affected.
        """
        # Validate appeal panel members
        for panel_member_id in appeal_panel_ids:
            entry = self._roster.get(panel_member_id)
            if entry is None:
                return ServiceResult(
                    success=False, errors=[f"Panel member not found: {panel_member_id}"],
                )
            if entry.status != ActorStatus.ACTIVE:
                return ServiceResult(
                    success=False,
                    errors=[f"Panel member {panel_member_id} is not ACTIVE"],
                )
            if entry.actor_kind != ActorKind.HUMAN:
                return ServiceResult(
                    success=False,
                    errors=[f"Panel member {panel_member_id} is not HUMAN"],
                )
            trust_rec = self._trust_records.get(panel_member_id)
            if not trust_rec or not trust_rec.trust_minted:
                return ServiceResult(
                    success=False,
                    errors=[f"Panel member {panel_member_id} is not trust-minted"],
                )
            if trust_rec.score < 0.70:
                return ServiceResult(
                    success=False,
                    errors=[
                        f"Panel member {panel_member_id} trust {trust_rec.score} "
                        f"is below 0.70 minimum"
                    ],
                )

        # Emit appeal filed event
        self._record_actor_lifecycle_event(
            actor_id=appellant_id,
            event_kind=EventKind.QUORUM_NUKE_APPEAL_FILED,
            payload={
                "request_id": request_id,
                "appellant_id": appellant_id,
                "appeal_panel_ids": appeal_panel_ids,
            },
        )

        try:
            appeal_result = self._quorum_verifier.appeal_trust_nuke(
                request_id=request_id,
                appellant_verifier_id=appellant_id,
                appeal_panel=appeal_panel_ids,
                votes=votes,
                now=now,
            )
        except (KeyError, ValueError) as exc:
            return ServiceResult(success=False, errors=[str(exc)])

        # If overturned, restore trust
        if appeal_result.overturned and appeal_result.restored_score is not None:
            trust_rec = self._trust_records.get(appellant_id)
            if trust_rec:
                trust_rec.score = appeal_result.restored_score

        # Emit resolution event
        self._record_actor_lifecycle_event(
            actor_id=appellant_id,
            event_kind=EventKind.QUORUM_NUKE_APPEAL_RESOLVED,
            payload={
                "request_id": request_id,
                "appellant_id": appellant_id,
                "overturned": appeal_result.overturned,
                "trust_restored": appeal_result.trust_restored,
                "restored_score": appeal_result.restored_score,
            },
        )

        return ServiceResult(
            success=True,
            data={
                "request_id": request_id,
                "appellant_id": appellant_id,
                "overturned": appeal_result.overturned,
                "trust_restored": appeal_result.trust_restored,
                "restored_score": appeal_result.restored_score,
            },
        )

    def lapse_verification(self, actor_id: str) -> ServiceResult:
        """Lapse a verified actor's identity (expired or manual).

        Transitions: VERIFIED → LAPSED.
        """
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(success=False, errors=[f"Actor not found: {actor_id}"])
        if entry.identity_status != IdentityVerificationStatus.VERIFIED:
            return ServiceResult(
                success=False,
                errors=[f"Can only lapse VERIFIED actors, got {entry.identity_status.value}"],
            )

        prev_status = entry.identity_status
        entry.identity_status = IdentityVerificationStatus.LAPSED

        err = self._record_actor_lifecycle_event(
            actor_id,
            EventKind.IDENTITY_LAPSED,
            {"previous_verified_utc": entry.identity_verified_utc.isoformat() if entry.identity_verified_utc else None},
        )
        if err:
            entry.identity_status = prev_status
            return ServiceResult(success=False, errors=[err])

        def _rollback() -> None:
            entry.identity_status = prev_status

        err = self._safe_persist(on_rollback=_rollback)
        if err:
            return ServiceResult(success=False, errors=[err])
        return ServiceResult(success=True, data={"actor_id": actor_id, "status": "lapsed"})

    def flag_identity(self, actor_id: str, reason: str) -> ServiceResult:
        """Flag an actor's identity for investigation.

        Transitions: Any → FLAGGED.
        """
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(success=False, errors=[f"Actor not found: {actor_id}"])

        prev_status = entry.identity_status
        entry.identity_status = IdentityVerificationStatus.FLAGGED

        err = self._record_actor_lifecycle_event(
            actor_id,
            EventKind.IDENTITY_FLAGGED,
            {"reason": reason, "previous_status": prev_status.value},
        )
        if err:
            entry.identity_status = prev_status
            return ServiceResult(success=False, errors=[err])

        def _rollback() -> None:
            entry.identity_status = prev_status

        err = self._safe_persist(on_rollback=_rollback)
        if err:
            return ServiceResult(success=False, errors=[err])
        return ServiceResult(success=True, data={"actor_id": actor_id, "status": "flagged"})

    def check_identity_for_high_stakes(
        self,
        actor_id: str,
        action_type: str,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Gate check: does this actor have valid identity for a high-stakes action?

        Returns success if:
        - action_type is NOT in reverification_required_for, OR
        - actor is VERIFIED and not expired.

        Auto-lapses expired actors. Blocks FLAGGED actors.
        """
        id_config = self._resolver.identity_verification_config()
        required_for = id_config.get("reverification_required_for", [])

        if action_type not in required_for:
            return ServiceResult(success=True, data={"gate": "not_required"})

        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(success=False, errors=[f"Actor not found: {actor_id}"])

        if entry.identity_status == IdentityVerificationStatus.FLAGGED:
            return ServiceResult(
                success=False,
                errors=["Identity flagged — high-stakes actions blocked"],
            )

        if entry.identity_status != IdentityVerificationStatus.VERIFIED:
            return ServiceResult(
                success=False,
                errors=[f"Identity verification required for {action_type}, status is {entry.identity_status.value}"],
            )

        # Check expiry
        now = now or datetime.now(timezone.utc)
        if entry.identity_expires_utc and now > entry.identity_expires_utc:
            # Auto-lapse
            self.lapse_verification(actor_id)
            return ServiceResult(
                success=False,
                errors=[f"Identity expired — re-verification required for {action_type}"],
            )

        return ServiceResult(success=True, data={"gate": "verified"})

    def check_lapsed_identities(self, now: Optional[datetime] = None) -> ServiceResult:
        """Batch check: lapse any VERIFIED actors whose identity has expired.

        Should be called periodically (e.g. daily).
        """
        now = now or datetime.now(timezone.utc)
        lapsed: list[str] = []

        for entry in self._roster.all_actors():
            if entry.identity_status != IdentityVerificationStatus.VERIFIED:
                continue
            if entry.identity_expires_utc and now > entry.identity_expires_utc:
                result = self.lapse_verification(entry.actor_id)
                if result.success:
                    lapsed.append(entry.actor_id)

        return ServiceResult(
            success=True,
            data={"lapsed_count": len(lapsed), "actors": lapsed},
        )

    # ------------------------------------------------------------------
    # Trust profile minting
    # ------------------------------------------------------------------

    def mint_trust_profile(self, actor_id: str) -> ServiceResult:
        """Mint an actor's trust profile — the ceremony that grants standing.

        Requirements (all three gates):
        1. Actor is PROVISIONAL (first mint) OR has LAPSED identity (re-mint)
        2. Identity verification status is VERIFIED
        3. Actor has completed at least 1 mission since registration/lapse

        On first mint: PROVISIONAL → ACTIVE, score set to 0.001 (displayed as 1/1000).
        On re-mint: status stays ACTIVE, score keeps current (decayed) value.
        """
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(
                success=False,
                errors=[f"Actor not found: {actor_id}"],
            )

        # Determine if first mint or re-mint
        is_first_mint = entry.status == ActorStatus.PROVISIONAL
        is_remint = (
            entry.status == ActorStatus.ACTIVE
            and entry.identity_status == IdentityVerificationStatus.VERIFIED
        )

        if not is_first_mint and not is_remint:
            return ServiceResult(
                success=False,
                errors=[
                    f"Cannot mint: actor {actor_id} must be PROVISIONAL "
                    f"(first mint) or ACTIVE with re-verified identity (re-mint). "
                    f"Current status: {entry.status.value}"
                ],
            )

        # Gate 2: Identity must be VERIFIED
        if entry.identity_status != IdentityVerificationStatus.VERIFIED:
            return ServiceResult(
                success=False,
                errors=[
                    f"Cannot mint: identity status must be VERIFIED, "
                    f"got {entry.identity_status.value}"
                ],
            )

        # Gate 3: At least 1 completed mission
        # Scan event log for MISSION_TRANSITION events with actor as worker
        # and payload indicating completion
        has_completed_mission = False
        for event in self._event_log.events(EventKind.MISSION_TRANSITION):
            if event.actor_id == actor_id:
                to_state = event.payload.get("to_state", "")
                if to_state in ("approved", "completed"):
                    has_completed_mission = True
                    break
            # Also check if actor was the worker (payload may have worker_id)
            if event.payload.get("worker_id") == actor_id:
                to_state = event.payload.get("to_state", "")
                if to_state in ("approved", "completed"):
                    has_completed_mission = True
                    break
        if not has_completed_mission:
            return ServiceResult(
                success=False,
                errors=[
                    "Cannot mint: actor must have at least 1 completed mission"
                ],
            )

        # All gates passed — mint the trust profile
        now = datetime.now(timezone.utc)

        # Update roster status
        if is_first_mint:
            entry.status = ActorStatus.ACTIVE

        # Update trust record
        record = self._trust_records.get(actor_id)
        if record is None:
            return ServiceResult(
                success=False,
                errors=[f"Trust record not found: {actor_id}"],
            )

        if is_first_mint:
            record.score = 0.001  # Displayed as 1/1000

        record.trust_minted = True
        record.trust_minted_utc = now

        # Update roster trust score to match
        entry.trust_score = record.score

        # Emit event
        self._record_actor_lifecycle_event(
            actor_id=actor_id,
            event_kind=EventKind.TRUST_PROFILE_MINTED,
            payload={
                "remint": not is_first_mint,
                "score": record.score,
                "display_score": record.display_score(),
                "identity_method": entry.identity_method,
            },
        )

        return ServiceResult(
            success=True,
            data={
                "actor_id": actor_id,
                "remint": not is_first_mint,
                "score": record.score,
                "display_score": record.display_score(),
                "minted_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    # ------------------------------------------------------------------
    # Skill profile management
    # ------------------------------------------------------------------

    def update_actor_skills(
        self,
        actor_id: str,
        skills: list[SkillProficiency],
    ) -> ServiceResult:
        """Update an actor's skill profile.

        Validates each skill against the taxonomy (if loaded).
        Creates the profile if it doesn't exist; merges otherwise.
        """
        actor = self._roster.get(actor_id)
        if actor is None:
            return ServiceResult(
                success=False,
                errors=[f"Actor not found: {actor_id}"],
            )

        # Validate skills against taxonomy
        if self._taxonomy is not None:
            errors: list[str] = []
            for sp in skills:
                skill_errors = self._taxonomy.validate_skill_id(sp.skill_id)
                errors.extend(skill_errors)
            if errors:
                return ServiceResult(success=False, errors=errors)

        # Snapshot pre-state for rollback
        old_profile = self._skill_profiles.get(actor_id)
        old_roster_profile = actor.skill_profile
        # Deep copy: snapshot old skill keys+values if profile existed
        old_skills = dict(old_profile.skills) if old_profile else None
        old_domains = list(old_profile.primary_domains) if old_profile else None
        old_updated = old_profile.updated_utc if old_profile else None

        # Get or create profile
        profile = self._skill_profiles.get(actor_id)
        if profile is None:
            profile = ActorSkillProfile(actor_id=actor_id)
            self._skill_profiles[actor_id] = profile

        # Merge skills
        for sp in skills:
            profile.skills[sp.skill_id.canonical] = sp

        profile.recompute_primary_domains()
        profile.updated_utc = datetime.now(timezone.utc)

        # Attach to roster entry for future matching
        actor.skill_profile = profile

        def _rollback() -> None:
            if old_profile is None:
                self._skill_profiles.pop(actor_id, None)
            else:
                old_profile.skills = old_skills  # type: ignore[assignment]
                old_profile.primary_domains = old_domains  # type: ignore[assignment]
                old_profile.updated_utc = old_updated
            actor.skill_profile = old_roster_profile

        err = self._safe_persist(on_rollback=_rollback)
        if err:
            return ServiceResult(success=False, errors=[err])
        return ServiceResult(
            success=True,
            data={
                "actor_id": actor_id,
                "skill_count": len(profile.skills),
                "primary_domains": profile.primary_domains,
            },
        )

    def get_actor_skills(self, actor_id: str) -> Optional[ActorSkillProfile]:
        """Retrieve an actor's skill profile."""
        return self._skill_profiles.get(actor_id)

    def set_mission_skill_requirements(
        self,
        mission_id: str,
        requirements: list[SkillRequirement],
    ) -> ServiceResult:
        """Set skill requirements on a mission.

        Requirements are validated against the taxonomy (if loaded).
        Can only be set on missions in DRAFT state.
        """
        mission = self._missions.get(mission_id)
        if mission is None:
            return ServiceResult(
                success=False,
                errors=[f"Mission not found: {mission_id}"],
            )

        if mission.state != MissionState.DRAFT:
            return ServiceResult(
                success=False,
                errors=[
                    f"Skill requirements can only be set on DRAFT missions, "
                    f"got {mission.state.value}"
                ],
            )

        # Validate against taxonomy
        if self._taxonomy is not None:
            errors = self._taxonomy.validate_requirements(requirements)
            if errors:
                return ServiceResult(success=False, errors=errors)

        prev_reqs = mission.skill_requirements
        mission.skill_requirements = list(requirements)

        def _rollback() -> None:
            mission.skill_requirements = prev_reqs

        err = self._safe_persist(on_rollback=_rollback)
        if err:
            return ServiceResult(success=False, errors=[err])
        return ServiceResult(
            success=True,
            data={
                "mission_id": mission_id,
                "requirement_count": len(requirements),
            },
        )

    def find_matching_workers(
        self,
        requirements: list[SkillRequirement],
        exclude_ids: set[str] | None = None,
        min_trust: float = 0.0,
        limit: int = 10,
    ) -> ServiceResult:
        """Find workers matching the given skill requirements.

        Returns ranked list of matching workers sorted by composite
        score (relevance * 0.50 + global_trust * 0.20 + domain_trust * 0.30).
        """
        matcher = WorkerMatcher(
            self._resolver,
            self._roster,
            self._trust_records,
            self._skill_profiles,
        )
        matches = matcher.find_matches(
            requirements=requirements,
            exclude_ids=exclude_ids,
            min_trust=min_trust,
            limit=limit,
        )
        return ServiceResult(
            success=True,
            data={
                "matches": [
                    {
                        "actor_id": m.actor_id,
                        "relevance_score": m.relevance_score,
                        "global_trust": m.global_trust,
                        "domain_trust": m.domain_trust,
                        "composite_score": m.composite_score,
                    }
                    for m in matches
                ],
                "total_matches": len(matches),
            },
        )

    # ------------------------------------------------------------------
    # Skill lifecycle — decay, endorsement, outcome updates
    # ------------------------------------------------------------------

    def endorse_skill(
        self,
        endorser_id: str,
        target_id: str,
        skill_id: SkillId,
    ) -> ServiceResult:
        """Endorse a peer's skill.

        Rules:
        - Self-endorsement blocked.
        - Endorser must have the skill at sufficient proficiency.
        - Target must already have the skill (outcome-derived).
        - Diminishing returns on repeated endorsements.
        """
        endorser_profile = self._skill_profiles.get(endorser_id)
        if endorser_profile is None:
            return ServiceResult(
                success=False,
                errors=[f"Endorser has no skill profile: {endorser_id}"],
            )

        endorser_trust = self._trust_records.get(endorser_id)
        if endorser_trust is None:
            return ServiceResult(
                success=False,
                errors=[f"No trust record for endorser: {endorser_id}"],
            )

        target_profile = self._skill_profiles.get(target_id)
        if target_profile is None:
            return ServiceResult(
                success=False,
                errors=[f"Target has no skill profile: {target_id}"],
            )

        # Snapshot target skill for rollback
        old_sp = target_profile.skills.get(skill_id.canonical)

        result = self._endorsement_engine.endorse(
            endorser_id=endorser_id,
            endorser_profile=endorser_profile,
            endorser_trust=endorser_trust,
            target_profile=target_profile,
            skill_id=skill_id,
        )

        if not result.success:
            return ServiceResult(success=False, errors=result.errors)

        def _rollback() -> None:
            if old_sp is not None:
                target_profile.skills[skill_id.canonical] = old_sp
            else:
                target_profile.skills.pop(skill_id.canonical, None)

        err = self._safe_persist(on_rollback=_rollback)
        if err:
            return ServiceResult(success=False, errors=[err])
        return ServiceResult(
            success=True,
            data={
                "endorser_id": endorser_id,
                "target_id": target_id,
                "skill": skill_id.canonical,
                "old_proficiency": result.old_proficiency,
                "new_proficiency": result.new_proficiency,
                "boost_applied": result.boost_applied,
            },
        )

    def run_skill_decay(
        self,
        actor_id: str | None = None,
    ) -> ServiceResult:
        """Apply skill decay to one actor or all actors.

        Should be called periodically (e.g. daily). Decays skill
        proficiencies that haven't been demonstrated recently.
        Skills below the prune threshold are removed.

        Args:
            actor_id: If specified, only decay this actor. If None, all.
        """
        if actor_id is not None:
            profiles_to_decay = {actor_id: self._skill_profiles.get(actor_id)}
            if profiles_to_decay[actor_id] is None:
                return ServiceResult(
                    success=False,
                    errors=[f"No skill profile for actor: {actor_id}"],
                )
        else:
            profiles_to_decay = dict(self._skill_profiles)

        results: list[dict[str, Any]] = []
        total_decayed = 0
        total_pruned = 0
        # Snapshot for rollback: {actor_id: (old_profile, old_roster_profile)}
        snapshots: dict[str, tuple[Any, Any]] = {}

        for aid, profile in profiles_to_decay.items():
            if profile is None:
                continue
            # Skip actors on protected leave — skill decay is frozen
            if self.is_actor_on_leave(aid):
                continue
            is_machine = False
            trust_rec = self._trust_records.get(aid)
            if trust_rec:
                is_machine = trust_rec.actor_kind == ActorKind.MACHINE

            new_profile, decay_result = self._skill_decay_engine.apply_decay(
                profile, is_machine=is_machine,
            )

            if decay_result.decayed_count > 0 or decay_result.pruned_count > 0:
                roster_entry = self._roster.get(aid)
                snapshots[aid] = (profile, roster_entry.skill_profile if roster_entry else None)
                self._skill_profiles[aid] = new_profile
                # Update roster entry skill profile
                if roster_entry:
                    roster_entry.skill_profile = new_profile

                total_decayed += decay_result.decayed_count
                total_pruned += decay_result.pruned_count
                results.append({
                    "actor_id": aid,
                    "decayed": decay_result.decayed_count,
                    "pruned": decay_result.pruned_count,
                    "skills_remaining": decay_result.skills_after,
                })

        if results:
            def _rollback() -> None:
                for s_aid, (old_prof, old_roster_prof) in snapshots.items():
                    self._skill_profiles[s_aid] = old_prof
                    r_entry = self._roster.get(s_aid)
                    if r_entry:
                        r_entry.skill_profile = old_roster_prof

            err = self._safe_persist(on_rollback=_rollback)
            if err:
                return ServiceResult(success=False, errors=[err])

        return ServiceResult(
            success=True,
            data={
                "actors_affected": len(results),
                "total_decayed": total_decayed,
                "total_pruned": total_pruned,
                "details": results,
            },
        )

    def _update_skills_from_outcome(
        self,
        worker_id: str,
        mission: Mission,
        approved: bool,
    ) -> Optional[dict[str, Any]]:
        """Internal: update worker skills after mission completion.

        Called by _assess_and_update_quality when a mission reaches
        a terminal state with skill requirements.
        """
        if not mission.skill_requirements:
            return None

        profile = self._skill_profiles.get(worker_id)
        if profile is None:
            # Create a new profile for the worker
            profile = ActorSkillProfile(actor_id=worker_id)
            self._skill_profiles[worker_id] = profile

        result = self._skill_outcome_updater.update_from_outcome(
            profile, mission, approved,
        )

        if result.skills_updated > 0:
            # Update roster entry
            roster_entry = self._roster.get(worker_id)
            if roster_entry:
                roster_entry.skill_profile = profile

        return {
            "skills_updated": result.skills_updated,
            "updates": [
                {
                    "skill": u.skill_id,
                    "old": u.old_proficiency,
                    "new": u.new_proficiency,
                    "delta": u.delta,
                }
                for u in result.updates
            ],
        }

    # ------------------------------------------------------------------
    # Labour market — listings and bids
    # ------------------------------------------------------------------

    def create_listing(
        self,
        listing_id: str,
        title: str,
        description: str,
        creator_id: str,
        skill_requirements: list[SkillRequirement] | None = None,
        domain_tags: list[str] | None = None,
        preferences: dict[str, Any] | None = None,
    ) -> ServiceResult:
        """Create a new market listing in DRAFT state."""
        if listing_id in self._listings:
            return ServiceResult(
                success=False,
                errors=[f"Listing already exists: {listing_id}"],
            )

        # Verify creator is registered
        creator = self._roster.get(creator_id)
        if creator is None:
            return ServiceResult(
                success=False,
                errors=[f"Creator not found: {creator_id}"],
            )

        # Compliance: suspended/decommissioned actors cannot post listings
        if creator.status in (
            ActorStatus.SUSPENDED,
            ActorStatus.PERMANENTLY_DECOMMISSIONED,
        ):
            return ServiceResult(
                success=False,
                errors=[
                    f"Actor {creator_id} is {creator.status.value} and cannot "
                    f"create listings"
                ],
            )

        # Validate skill requirements against taxonomy
        reqs = skill_requirements or []
        if self._taxonomy is not None and reqs:
            errors = self._taxonomy.validate_requirements(reqs)
            if errors:
                return ServiceResult(success=False, errors=errors)

        listing = MarketListing(
            listing_id=listing_id,
            title=title,
            description=description,
            creator_id=creator_id,
            state=ListingState.DRAFT,
            skill_requirements=reqs,
            created_utc=datetime.now(timezone.utc),
            domain_tags=domain_tags or [],
            preferences=preferences or {},
        )
        self._listings[listing_id] = listing
        self._bids[listing_id] = []

        # Record audit event
        err = self._record_listing_event(listing, "created")
        if err:
            del self._listings[listing_id]
            del self._bids[listing_id]
            return ServiceResult(success=False, errors=[err])

        warning = self._safe_persist_post_audit()
        data: dict[str, Any] = {
            "listing_id": listing_id,
            "state": listing.state.value,
        }
        if warning:
            data["warning"] = warning
        return ServiceResult(success=True, data=data)

    def open_listing(self, listing_id: str) -> ServiceResult:
        """Transition listing from DRAFT → OPEN.

        If the listing has an escrow_id linked (from create_funded_listing),
        the escrow record must still exist. This enforces the escrow-first
        structural guarantee after service restart.
        """
        listing = self._listings.get(listing_id)
        if listing is None:
            return ServiceResult(
                success=False,
                errors=[f"Listing not found: {listing_id}"],
            )
        if listing.escrow_id is not None:
            try:
                self._escrow_manager.get_escrow(listing.escrow_id)
            except ValueError:
                return ServiceResult(
                    success=False,
                    errors=[
                        f"Escrow record missing for listing {listing_id} "
                        f"(escrow_id={listing.escrow_id}). "
                        f"Cannot open listing without valid escrow linkage."
                    ],
                )
        return self._transition_listing(listing_id, ListingState.OPEN)

    def start_accepting_bids(self, listing_id: str) -> ServiceResult:
        """Transition listing from OPEN → ACCEPTING_BIDS."""
        return self._transition_listing(listing_id, ListingState.ACCEPTING_BIDS)

    def submit_bid(
        self,
        bid_id: str,
        listing_id: str,
        worker_id: str,
        notes: str = "",
    ) -> ServiceResult:
        """Submit a bid on a listing.

        Auto-computes relevance and trust scores for the worker.
        Validates bid eligibility (trust threshold, duplicate check).
        """
        listing = self._listings.get(listing_id)
        if listing is None:
            return ServiceResult(
                success=False,
                errors=[f"Listing not found: {listing_id}"],
            )

        if listing.state not in (ListingState.OPEN, ListingState.ACCEPTING_BIDS):
            return ServiceResult(
                success=False,
                errors=[
                    f"Listing {listing_id} is not accepting bids "
                    f"(state: {listing.state.value})"
                ],
            )

        # Verify worker exists and is available
        worker = self._roster.get(worker_id)
        if worker is None:
            return ServiceResult(
                success=False,
                errors=[f"Worker not found: {worker_id}"],
            )
        if not worker.is_available():
            return ServiceResult(
                success=False,
                errors=[f"Worker {worker_id} is not available (status: {worker.status.value})"],
            )

        # Check bid requirements
        bid_reqs = self._resolver.market_bid_requirements()
        min_trust = bid_reqs.get("min_trust_to_bid", 0.10)
        trust_record = self._trust_records.get(worker_id)
        global_trust = trust_record.score if trust_record else 0.0
        if global_trust < min_trust:
            return ServiceResult(
                success=False,
                errors=[
                    f"Worker trust {global_trust:.2f} below minimum "
                    f"{min_trust:.2f} to bid"
                ],
            )

        # Check duplicate bids
        if not bid_reqs.get("allow_multiple_bids_per_worker", False):
            existing_bids = self._bids.get(listing_id, [])
            for b in existing_bids:
                if b.worker_id == worker_id and b.state == BidState.SUBMITTED:
                    return ServiceResult(
                        success=False,
                        errors=[f"Worker {worker_id} already has a bid on listing {listing_id}"],
                    )

        # Check max bids
        listing_defaults = self._resolver.market_listing_defaults()
        max_bids = listing_defaults.get("max_bids_per_listing", 50)
        active_bids = [
            b for b in self._bids.get(listing_id, [])
            if b.state == BidState.SUBMITTED
        ]
        if len(active_bids) >= max_bids:
            return ServiceResult(
                success=False,
                errors=[f"Listing {listing_id} has reached maximum bids ({max_bids})"],
            )

        # Compute relevance score
        profile = self._skill_profiles.get(worker_id)
        relevance = self._match_engine.compute_relevance(
            profile, listing.skill_requirements, trust_record,
        )

        # Compute domain trust
        domain_trust = 0.0
        if trust_record and listing.skill_requirements:
            domains = {r.skill_id.domain for r in listing.skill_requirements}
            domain_scores = [
                trust_record.domain_scores[d].score
                for d in domains
                if d in trust_record.domain_scores
            ]
            if domain_scores:
                domain_trust = sum(domain_scores) / len(domains)

        # Compute composite score
        w_rel, w_global, w_domain = self._allocation_engine._allocation_weights()
        composite = (
            w_rel * relevance
            + w_global * global_trust
            + w_domain * domain_trust
        )

        bid = Bid(
            bid_id=bid_id,
            listing_id=listing_id,
            worker_id=worker_id,
            state=BidState.SUBMITTED,
            relevance_score=relevance,
            global_trust=global_trust,
            domain_trust=domain_trust,
            composite_score=composite,
            submitted_utc=datetime.now(timezone.utc),
            notes=notes,
        )
        self._bids.setdefault(listing_id, []).append(bid)

        # Record bid event
        err = self._record_bid_event(bid)
        if err:
            self._bids[listing_id].pop()
            return ServiceResult(success=False, errors=[err])

        warning = self._safe_persist_post_audit()
        data: dict[str, Any] = {
            "bid_id": bid_id,
            "listing_id": listing_id,
            "worker_id": worker_id,
            "relevance_score": relevance,
            "global_trust": global_trust,
            "domain_trust": domain_trust,
            "composite_score": composite,
        }
        if warning:
            data["warning"] = warning
        return ServiceResult(success=True, data=data)

    def withdraw_bid(self, bid_id: str, listing_id: str) -> ServiceResult:
        """Withdraw a previously submitted bid."""
        listing = self._listings.get(listing_id)
        if listing is None:
            return ServiceResult(
                success=False,
                errors=[f"Listing not found: {listing_id}"],
            )

        bids = self._bids.get(listing_id, [])
        for bid in bids:
            if bid.bid_id == bid_id:
                if bid.state != BidState.SUBMITTED:
                    return ServiceResult(
                        success=False,
                        errors=[f"Bid {bid_id} cannot be withdrawn (state: {bid.state.value})"],
                    )
                prev_state = bid.state
                bid.state = BidState.WITHDRAWN

                def _rollback() -> None:
                    bid.state = prev_state

                err = self._safe_persist(on_rollback=_rollback)
                if err:
                    return ServiceResult(success=False, errors=[err])
                return ServiceResult(
                    success=True,
                    data={"bid_id": bid_id, "state": bid.state.value},
                )

        return ServiceResult(
            success=False,
            errors=[f"Bid not found: {bid_id}"],
        )

    def evaluate_and_allocate(
        self,
        listing_id: str,
        mission_class: MissionClass = MissionClass.DOCUMENTATION_UPDATE,
        domain_type: DomainType = DomainType.OBJECTIVE,
    ) -> ServiceResult:
        """Close bidding, evaluate bids, allocate worker, create mission.

        Full flow:
        1. Transition listing to EVALUATING
        2. Score and rank all bids
        3. Select best bid → ALLOCATED
        4. Auto-create mission from listing
        5. Optionally close listing
        """
        listing = self._listings.get(listing_id)
        if listing is None:
            return ServiceResult(
                success=False,
                errors=[f"Listing not found: {listing_id}"],
            )

        # Snapshot listing state before any mutation (for rollback)
        initial_listing_state = listing.state

        # Transition to EVALUATING (validates current state)
        if listing.state == ListingState.ACCEPTING_BIDS:
            errors = ListingStateMachine.apply_transition(listing, ListingState.EVALUATING)
            if errors:
                return ServiceResult(success=False, errors=errors)
        elif listing.state != ListingState.EVALUATING:
            return ServiceResult(
                success=False,
                errors=[
                    f"Cannot evaluate listing in state {listing.state.value}. "
                    f"Expected ACCEPTING_BIDS or EVALUATING."
                ],
            )

        bids = self._bids.get(listing_id, [])
        submitted_bids = [b for b in bids if b.state == BidState.SUBMITTED]

        if not submitted_bids:
            # Rollback EVALUATING transition
            listing.state = initial_listing_state
            return ServiceResult(
                success=False,
                errors=[f"No submitted bids for listing {listing_id}"],
            )

        # Evaluate and allocate
        result = self._allocation_engine.evaluate_and_allocate(listing, submitted_bids)
        if result is None:
            listing.state = initial_listing_state
            return ServiceResult(
                success=False,
                errors=["Allocation failed — no valid bids after scoring"],
            )

        # Snapshot bid states for rollback
        prior_bid_states = {bid.bid_id: bid.state for bid in bids}

        # Update bid states
        for bid in bids:
            if bid.bid_id == result.selected_bid_id:
                bid.state = BidState.ACCEPTED
            elif bid.state == BidState.SUBMITTED:
                bid.state = BidState.REJECTED

        # Snapshot listing fields for rollback
        prior_allocated_worker_id = listing.allocated_worker_id
        prior_allocated_utc = listing.allocated_utc
        prior_allocated_mission_id = listing.allocated_mission_id

        # Transition listing to ALLOCATED
        errors = ListingStateMachine.apply_transition(listing, ListingState.ALLOCATED)
        if errors:
            # Rollback bid states and EVALUATING transition
            listing.state = initial_listing_state
            for bid in bids:
                if bid.bid_id in prior_bid_states:
                    bid.state = prior_bid_states[bid.bid_id]
            return ServiceResult(success=False, errors=errors)

        listing.allocated_worker_id = result.selected_worker_id
        listing.allocated_utc = datetime.now(timezone.utc)

        def _rollback_allocation() -> None:
            """Rollback all allocation mutations to initial state."""
            listing.state = initial_listing_state
            listing.allocated_worker_id = prior_allocated_worker_id
            listing.allocated_utc = prior_allocated_utc
            listing.allocated_mission_id = prior_allocated_mission_id
            for bid in bids:
                if bid.bid_id in prior_bid_states:
                    bid.state = prior_bid_states[bid.bid_id]

        # --- Internal mission staging (no side effects until commit) ---
        # Do NOT call public create_mission() — it is a committed
        # operation with its own audit event + persist. Using it here
        # creates phantom mission events if the allocation audit fails.
        # Instead: validate, construct, audit-commit, then insert.
        mission_id = f"mission-from-{listing_id}"

        # Step 1: Validate — mission ID must be unique
        if mission_id in self._missions:
            _rollback_allocation()
            return ServiceResult(
                success=False,
                errors=[f"Allocation failed: mission already exists: {mission_id}"],
            )

        # Step 2: Construct mission object (pure — no side effects)
        tier = self._resolver.resolve_tier(mission_class)
        staged_mission = Mission(
            mission_id=mission_id,
            mission_title=listing.title,
            mission_class=mission_class,
            risk_tier=tier,
            domain_type=domain_type,
            worker_id=result.selected_worker_id,
            created_utc=datetime.now(timezone.utc),
        )
        if listing.skill_requirements:
            staged_mission.skill_requirements = list(listing.skill_requirements)

        listing.allocated_mission_id = mission_id

        # Step 3: Record allocation audit event — the single durable
        # commit point for the entire transaction. The allocation event
        # payload contains listing_id, worker_id, and mission_id, serving
        # as the audit record for both allocation and mission creation.
        # If this fails, nothing has been written — clean rollback.
        err = self._record_allocation_event(listing, result)
        if err:
            _rollback_allocation()
            return ServiceResult(success=False, errors=[err])

        # Step 4: Commit — insert staged mission into memory. The
        # allocation audit event is already durable, so this is safe.
        self._missions[mission_id] = staged_mission

        # Auto-close if configured
        pre_close_state = listing.state
        defaults = self._resolver.market_listing_defaults()
        if defaults.get("auto_close_on_allocation", True):
            ListingStateMachine.apply_transition(listing, ListingState.CLOSED)

        # Audit event committed — do NOT rollback in-memory state
        persist_warning = self._safe_persist_post_audit()
        result_data: dict[str, Any] = {
            "listing_id": listing_id,
            "selected_bid_id": result.selected_bid_id,
            "selected_worker_id": result.selected_worker_id,
            "composite_score": result.composite_score,
            "runner_up_count": len(result.runner_up_bid_ids),
            "mission_id": mission_id,
            "mission_created": True,
        }
        if persist_warning:
            result_data["warning"] = persist_warning
        return ServiceResult(success=True, data=result_data)

    def cancel_listing(self, listing_id: str) -> ServiceResult:
        """Cancel a listing. Withdraws all submitted bids."""
        listing = self._listings.get(listing_id)
        if listing is None:
            return ServiceResult(
                success=False,
                errors=[f"Listing not found: {listing_id}"],
            )

        # Snapshot for rollback
        prev_listing_state = listing.state
        bid_snapshots = [
            (bid, bid.state) for bid in self._bids.get(listing_id, [])
        ]

        errors = ListingStateMachine.apply_transition(listing, ListingState.CANCELLED)
        if errors:
            return ServiceResult(success=False, errors=errors)

        # Withdraw all submitted bids
        for bid in self._bids.get(listing_id, []):
            if bid.state == BidState.SUBMITTED:
                bid.state = BidState.WITHDRAWN

        def _rollback() -> None:
            listing.state = prev_listing_state
            for bid_obj, prev_bid_state in bid_snapshots:
                bid_obj.state = prev_bid_state

        err = self._safe_persist(on_rollback=_rollback)
        if err:
            return ServiceResult(success=False, errors=[err])
        return ServiceResult(
            success=True,
            data={"listing_id": listing_id, "state": listing.state.value},
        )

    def search_listings(
        self,
        state: ListingState | None = None,
        domain_tags: list[str] | None = None,
        creator_id: str | None = None,
        limit: int = 20,
    ) -> ServiceResult:
        """Search for listings with optional filters."""
        results: list[dict[str, Any]] = []
        for listing in self._listings.values():
            if state is not None and listing.state != state:
                continue
            if creator_id is not None and listing.creator_id != creator_id:
                continue
            if domain_tags:
                if not any(tag in listing.domain_tags for tag in domain_tags):
                    continue
            bid_count = len([
                b for b in self._bids.get(listing.listing_id, [])
                if b.state == BidState.SUBMITTED
            ])
            results.append({
                "listing_id": listing.listing_id,
                "title": listing.title,
                "state": listing.state.value,
                "creator_id": listing.creator_id,
                "skill_requirements": len(listing.skill_requirements),
                "bid_count": bid_count,
                "domain_tags": listing.domain_tags,
            })
            if len(results) >= limit:
                break

        return ServiceResult(
            success=True,
            data={
                "listings": results,
                "total": len(results),
            },
        )

    def get_listing(self, listing_id: str) -> Optional[MarketListing]:
        """Retrieve a listing by ID."""
        return self._listings.get(listing_id)

    def get_bids(self, listing_id: str) -> list[Bid]:
        """Retrieve all bids for a listing."""
        return list(self._bids.get(listing_id, []))

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

        # Record audit event (fail-closed: errors propagate)
        err = self._record_mission_event(mission, "created")
        if err:
            del self._missions[mission_id]
            return ServiceResult(success=False, errors=[err])

        # Audit event is now committed — do NOT rollback in-memory state
        persist_warning = self._safe_persist_post_audit()
        result_data: dict[str, Any] = {
            "mission_id": mission_id, "risk_tier": tier.value,
        }
        if persist_warning:
            result_data["warning"] = persist_warning
        return ServiceResult(success=True, data=result_data)

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

        err = self._record_mission_event(mission, f"review:{reviewer_id}:{verdict}")
        if err:
            mission.review_decisions.pop()
            return ServiceResult(success=False, errors=[err])

        warning = self._safe_persist_post_audit()
        if warning:
            return ServiceResult(success=True, data={"warning": warning})
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
        """Approve a mission — routes through human gate if policy requires it.

        For R2+ missions with human_final_gate=true, this transitions to
        HUMAN_GATE_PENDING. Use human_gate_approve() to complete.
        For other missions, transitions directly to APPROVED.
        """
        mission = self._missions.get(mission_id)
        if mission is None:
            return ServiceResult(success=False, errors=[f"Mission not found: {mission_id}"])

        policy = self._resolver.tier_policy(mission.risk_tier)
        if policy.human_final_gate and not mission.human_final_approval:
            # Route to human gate — cannot skip
            return self._transition_mission(mission_id, MissionState.HUMAN_GATE_PENDING)

        result = self._transition_mission(mission_id, MissionState.APPROVED)
        if result.success:
            qa_result = self._assess_and_update_quality(mission_id)
            result.data["quality_assessment"] = qa_result.data
        return result

    def human_gate_approve(
        self,
        mission_id: str,
        approver_id: str,
    ) -> ServiceResult:
        """Human final approval for high-risk missions.

        This is the only path to APPROVED for missions that require
        human_final_gate. The approver must be a registered human actor.
        """
        mission = self._missions.get(mission_id)
        if mission is None:
            return ServiceResult(success=False, errors=[f"Mission not found: {mission_id}"])

        if mission.state != MissionState.HUMAN_GATE_PENDING:
            return ServiceResult(
                success=False,
                errors=[f"Mission {mission_id} not in HUMAN_GATE_PENDING state"],
            )

        # Verify approver is a registered human
        entry = self._roster.get(approver_id)
        if entry is None:
            return ServiceResult(
                success=False,
                errors=[f"Approver not found: {approver_id}"],
            )
        if entry.actor_kind != ActorKind.HUMAN:
            return ServiceResult(
                success=False,
                errors=[f"Human gate requires human approver; {approver_id} is {entry.actor_kind.value}"],
            )

        mission.human_final_approval = True

        err = self._record_mission_event(mission, f"human_gate_approve:{approver_id}")
        if err:
            mission.human_final_approval = False
            return ServiceResult(success=False, errors=[err])

        result = self._transition_mission(mission_id, MissionState.APPROVED)
        if result.success:
            qa_result = self._assess_and_update_quality(mission_id)
            result.data["quality_assessment"] = qa_result.data
        return result

    def human_gate_reject(
        self,
        mission_id: str,
        rejector_id: str,
    ) -> ServiceResult:
        """Human final rejection for high-risk missions."""
        mission = self._missions.get(mission_id)
        if mission is None:
            return ServiceResult(success=False, errors=[f"Mission not found: {mission_id}"])

        if mission.state != MissionState.HUMAN_GATE_PENDING:
            return ServiceResult(
                success=False,
                errors=[f"Mission {mission_id} not in HUMAN_GATE_PENDING state"],
            )

        # Verify rejector is a registered human
        entry = self._roster.get(rejector_id)
        if entry is None:
            return ServiceResult(
                success=False,
                errors=[f"Rejector not found: {rejector_id}"],
            )
        if entry.actor_kind != ActorKind.HUMAN:
            return ServiceResult(
                success=False,
                errors=[f"Human gate requires human actor; {rejector_id} is {entry.actor_kind.value}"],
            )

        err = self._record_mission_event(mission, f"human_gate_reject:{rejector_id}")
        if err:
            return ServiceResult(success=False, errors=[err])

        result = self._transition_mission(mission_id, MissionState.REJECTED)
        if result.success:
            qa_result = self._assess_and_update_quality(mission_id)
            result.data["quality_assessment"] = qa_result.data
        return result

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
        """Update an actor's trust score.

        Enforces machine recertification: after applying the trust update,
        checks recertification requirements for machine actors. Failures
        increment the recertification counter and may trigger quarantine
        or decommission per constitutional rules.
        """
        record = self._trust_records.get(actor_id.strip())
        if record is None:
            return ServiceResult(
                success=False,
                errors=[f"No trust record for actor: {actor_id}"],
            )

        # Trust freeze: actors on protected leave cannot gain or lose trust
        if self.is_actor_on_leave(actor_id.strip()):
            return ServiceResult(
                success=False,
                errors=[
                    f"Actor {actor_id.strip()} is on protected leave; "
                    f"trust is frozen (no gain, no loss)"
                ],
            )

        new_record, delta = self._trust_engine.apply_update(
            record, quality=quality, reliability=reliability,
            volume=volume, reason=reason, effort=effort,
            mission_id=mission_id,
        )

        # Snapshot roster state for rollback
        roster_entry = self._roster.get(actor_id)
        prior_roster_status = roster_entry.status if roster_entry else None

        # Machine recertification enforcement
        recert_issues: list[str] = []
        now_ts = datetime.now(timezone.utc)
        if new_record.actor_kind == ActorKind.MACHINE:
            recert_issues = self._trust_engine.check_recertification(new_record)
            if recert_issues:
                # Append failure timestamp + increment counter
                fail_timestamps = list(new_record.recertification_failure_timestamps) + [now_ts]
                new_record = TrustRecord(
                    actor_id=new_record.actor_id,
                    actor_kind=new_record.actor_kind,
                    score=new_record.score,
                    quality=new_record.quality,
                    reliability=new_record.reliability,
                    volume=new_record.volume,
                    effort=new_record.effort,
                    quarantined=new_record.quarantined,
                    recertification_failures=new_record.recertification_failures + 1,
                    last_recertification_utc=new_record.last_recertification_utc,
                    decommissioned=new_record.decommissioned,
                    last_active_utc=new_record.last_active_utc,
                    recertification_failure_timestamps=fail_timestamps,
                    probation_tasks_completed=new_record.probation_tasks_completed,
                )
                # Use windowed failure count for decommission threshold
                decomm = self._resolver.decommission_rules()
                windowed_count = self._trust_engine.count_windowed_failures(
                    new_record, now_ts,
                )
                if windowed_count >= decomm["M_RECERT_FAIL_MAX"]:
                    new_record = TrustRecord(
                        actor_id=new_record.actor_id,
                        actor_kind=new_record.actor_kind,
                        score=0.0,
                        quality=new_record.quality,
                        reliability=new_record.reliability,
                        volume=new_record.volume,
                        effort=new_record.effort,
                        quarantined=True,
                        recertification_failures=new_record.recertification_failures,
                        last_recertification_utc=new_record.last_recertification_utc,
                        decommissioned=True,
                        last_active_utc=new_record.last_active_utc,
                        recertification_failure_timestamps=new_record.recertification_failure_timestamps,
                        probation_tasks_completed=new_record.probation_tasks_completed,
                    )
                    # Update roster status
                    if roster_entry:
                        roster_entry.status = ActorStatus.DECOMMISSIONED
            else:
                # Successful update — increment probation counter for PROBATION machines
                if roster_entry and roster_entry.status == ActorStatus.PROBATION:
                    new_record = TrustRecord(
                        actor_id=new_record.actor_id,
                        actor_kind=new_record.actor_kind,
                        score=new_record.score,
                        quality=new_record.quality,
                        reliability=new_record.reliability,
                        volume=new_record.volume,
                        effort=new_record.effort,
                        quarantined=new_record.quarantined,
                        recertification_failures=new_record.recertification_failures,
                        last_recertification_utc=new_record.last_recertification_utc,
                        decommissioned=new_record.decommissioned,
                        last_active_utc=new_record.last_active_utc,
                        recertification_failure_timestamps=new_record.recertification_failure_timestamps,
                        probation_tasks_completed=new_record.probation_tasks_completed + 1,
                    )

        self._trust_records[actor_id.strip()] = new_record

        # Update roster trust score
        if roster_entry:
            roster_entry.trust_score = new_record.score

        # Record event (fail-closed)
        err = self._record_trust_event(actor_id, delta)
        if err:
            # Full rollback: trust record, roster score, AND roster status
            self._trust_records[actor_id.strip()] = record
            if roster_entry:
                roster_entry.trust_score = record.score
                roster_entry.status = prior_roster_status
            return ServiceResult(success=False, errors=[err])

        # Audit event committed — do NOT rollback in-memory state
        persist_warning = self._safe_persist_post_audit()

        result_data: dict[str, Any] = {
            "actor_id": actor_id,
            "old_score": record.score,
            "new_score": new_record.score,
            "delta": delta.abs_delta,
            "suspended": delta.suspended,
        }
        if recert_issues:
            result_data["recertification_issues"] = recert_issues
            result_data["recertification_failures"] = new_record.recertification_failures
            result_data["decommissioned"] = new_record.decommissioned
        if persist_warning:
            result_data["warning"] = persist_warning

        return ServiceResult(success=True, data=result_data)

    def get_trust(self, actor_id: str) -> Optional[TrustRecord]:
        """Retrieve trust record for an actor."""
        return self._trust_records.get(actor_id.strip())

    def get_domain_trust(
        self, actor_id: str, domain: str,
    ) -> Optional[DomainTrustScore]:
        """Retrieve an actor's trust score for a specific domain."""
        record = self._trust_records.get(actor_id.strip())
        if record is None:
            return None
        return record.domain_scores.get(domain)

    def get_trust_status(self, actor_id: str) -> Optional[TrustStatus]:
        """Compute the full trust dashboard for an actor.

        Returns TrustStatus with days-until-half-life, urgency
        indicators, per-domain forecasts, and projected scores.
        Computed on-demand — no persistence needed.
        """
        record = self._trust_records.get(actor_id.strip())
        if record is None:
            return None
        return self._trust_engine.compute_decay_forecast(record)

    def decay_inactive_actors(self) -> ServiceResult:
        """Apply inactivity decay to all actors.

        Should be called periodically (e.g. daily). Decays both
        domain-specific and global trust for inactive actors.
        Differentiated by ActorKind: HUMAN 365-day half-life,
        MACHINE 90-day half-life.
        """
        if not self._resolver.has_skill_trust_config():
            return ServiceResult(
                success=False,
                errors=["No skill trust config loaded — decay not available"],
            )

        decayed_actors: list[dict[str, Any]] = []
        # Snapshot for rollback: {actor_id: (old_record, old_roster_score)}
        snapshots: dict[str, tuple[TrustRecord, float | None]] = {}

        for actor_id, record in list(self._trust_records.items()):
            # Skip actors on protected leave — trust is frozen
            if self.is_actor_on_leave(actor_id):
                continue
            new_record = self._trust_engine.apply_inactivity_decay(record)
            if new_record is not record:  # identity check — was actually decayed
                roster_entry = self._roster.get(actor_id)
                snapshots[actor_id] = (
                    record,
                    roster_entry.trust_score if roster_entry else None,
                )
                self._trust_records[actor_id] = new_record
                # Update roster trust score
                if roster_entry:
                    roster_entry.trust_score = new_record.score
                decayed_actors.append({
                    "actor_id": actor_id,
                    "old_score": record.score,
                    "new_score": new_record.score,
                })

        if decayed_actors:
            def _rollback() -> None:
                for s_aid, (old_rec, old_roster_score) in snapshots.items():
                    self._trust_records[s_aid] = old_rec
                    r_entry = self._roster.get(s_aid)
                    if r_entry and old_roster_score is not None:
                        r_entry.trust_score = old_roster_score

            err = self._safe_persist(on_rollback=_rollback)
            if err:
                return ServiceResult(success=False, errors=[err])

        return ServiceResult(
            success=True,
            data={
                "decayed_count": len(decayed_actors),
                "actors": decayed_actors,
            },
        )

    # ------------------------------------------------------------------
    # Protected leave
    # ------------------------------------------------------------------

    def request_leave(
        self,
        actor_id: str,
        category: LeaveCategory,
        reason_summary: str = "",
    ) -> ServiceResult:
        """Submit a protected leave request.

        Validates actor exists and is active, checks anti-gaming
        constraints, creates a PENDING leave record.
        """
        actor_id = actor_id.strip()
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(
                success=False, errors=[f"Actor not found: {actor_id}"],
            )
        # Protected leave is for human life events only
        if entry.actor_kind != ActorKind.HUMAN:
            return ServiceResult(
                success=False,
                errors=["Only human actors can request protected leave"],
            )
        # DEATH category must use petition_memorialisation() — third-party petitioned
        if category == LeaveCategory.DEATH:
            return ServiceResult(
                success=False,
                errors=[
                    "Death memorialisation must be petitioned by a third party "
                    "using petition_memorialisation(), not self-requested"
                ],
            )
        # PROOF_OF_LIFE must use petition_memorialisation_reversal()
        if category == LeaveCategory.PROOF_OF_LIFE:
            return ServiceResult(
                success=False,
                errors=[
                    "Proof-of-life reversal must use "
                    "petition_memorialisation_reversal()"
                ],
            )
        if not entry.is_available():
            return ServiceResult(
                success=False,
                errors=[f"Actor status is {entry.status.value}; must be active or probation"],
            )

        # Anti-gaming checks
        existing_leaves = [
            r for r in self._leave_records.values()
            if r.actor_id == actor_id
        ]
        violations = self._leave_engine.check_anti_gaming(
            actor_id, existing_leaves,
        )
        if violations:
            return ServiceResult(success=False, errors=violations)

        # Create PENDING record
        now = datetime.now(timezone.utc)
        self._leave_counter += 1
        leave_id = f"LEAVE-{self._leave_counter:06d}"

        record = LeaveRecord(
            leave_id=leave_id,
            actor_id=actor_id,
            category=category,
            state=LeaveState.PENDING,
            reason_summary=reason_summary,
            requested_utc=now,
        )
        self._leave_records[leave_id] = record

        # Three-step event recording
        err = self._record_leave_event(record, "requested")
        if err:
            del self._leave_records[leave_id]
            self._leave_counter -= 1
            return ServiceResult(success=False, errors=[err])

        warning = self._safe_persist_post_audit()
        data: dict[str, Any] = {"leave_id": leave_id, "state": record.state.value}
        if warning:
            data["warning"] = warning
        return ServiceResult(success=True, data=data)

    def adjudicate_leave(
        self,
        leave_id: str,
        adjudicator_id: str,
        verdict: AdjudicationVerdict,
        notes: str = "",
    ) -> ServiceResult:
        """Submit an adjudication verdict on a leave request.

        Validates adjudicator eligibility (human, domain trust, not self,
        not duplicate). If quorum is reached, transitions to APPROVED
        (activating trust freeze) or DENIED.
        """
        record = self._leave_records.get(leave_id)
        if record is None:
            return ServiceResult(
                success=False, errors=[f"Leave record not found: {leave_id}"],
            )
        if record.state != LeaveState.PENDING:
            return ServiceResult(
                success=False,
                errors=[f"Leave is {record.state.value}; can only adjudicate PENDING"],
            )

        # For death petitions, check if actor already memorialised by another record
        if record.category == LeaveCategory.DEATH:
            actor_entry = self._roster.get(record.actor_id)
            if actor_entry and actor_entry.status == ActorStatus.MEMORIALISED:
                return ServiceResult(
                    success=False,
                    errors=[f"Actor {record.actor_id} is already memorialised"],
                )

        adjudicator_id = adjudicator_id.strip()

        # Duplicate vote check
        for adj in record.adjudications:
            if adj.adjudicator_id == adjudicator_id:
                return ServiceResult(
                    success=False,
                    errors=[f"Adjudicator {adjudicator_id} has already voted"],
                )

        # Enforce max_adjudicators cap
        adj_config = self._resolver.leave_adjudication_config()
        max_adjudicators = adj_config.get("max_adjudicators")
        if max_adjudicators is not None and len(record.adjudications) >= max_adjudicators:
            return ServiceResult(
                success=False,
                errors=[
                    f"Maximum adjudicator cap reached ({max_adjudicators}); "
                    f"no further votes accepted"
                ],
            )

        # Eligibility check via engine
        adj_entry = self._roster.get(adjudicator_id)
        if adj_entry is None:
            return ServiceResult(
                success=False,
                errors=[f"Adjudicator not found: {adjudicator_id}"],
            )
        adj_trust = self._trust_records.get(adjudicator_id)
        if adj_trust is None:
            return ServiceResult(
                success=False,
                errors=[f"No trust record for adjudicator: {adjudicator_id}"],
            )

        eligibility = self._leave_engine.check_adjudicator_eligibility(
            adj_entry, adj_trust, record.category, record.actor_id,
        )
        if not eligibility.eligible:
            return ServiceResult(success=False, errors=eligibility.errors)

        # Snapshot for rollback
        old_adjudications = list(record.adjudications)
        old_state = record.state
        old_approved_utc = record.approved_utc
        old_denied_utc = record.denied_utc

        # Add adjudication
        now = datetime.now(timezone.utc)
        adjudication = LeaveAdjudication(
            adjudicator_id=adjudicator_id,
            verdict=verdict,
            domain_qualified=eligibility.qualifying_domain,
            trust_score_at_decision=adj_trust.score,
            notes=notes,
            timestamp_utc=now,
        )
        record.adjudications.append(adjudication)

        # Record adjudication event
        err = self._record_leave_event(record, "adjudicated")
        if err:
            record.adjudications = old_adjudications
            return ServiceResult(success=False, errors=[err])

        # Check quorum
        quorum_result = self._leave_engine.evaluate_quorum(record)
        activation_data: dict[str, Any] | None = None

        if quorum_result.quorum_reached:
            if quorum_result.approved:
                # Diversity check: non-abstain adjudicators must meet
                # configured org/region diversity thresholds
                non_abstain_entries: dict[str, RosterEntry] = {}
                for adj in record.adjudications:
                    if adj.verdict != AdjudicationVerdict.ABSTAIN:
                        e = self._roster.get(adj.adjudicator_id)
                        if e is not None:
                            non_abstain_entries[adj.adjudicator_id] = e
                diversity_violations = (
                    self._leave_engine.check_adjudicator_diversity(
                        non_abstain_entries,
                    )
                )
                if diversity_violations:
                    # Quorum count is met but diversity is not —
                    # leave stays PENDING, more adjudicators needed
                    warning = self._safe_persist_post_audit()
                    data_pending: dict[str, Any] = {
                        "leave_id": leave_id,
                        "state": record.state.value,
                        "quorum_reached": False,
                        "diversity_unmet": diversity_violations,
                        "approve_count": quorum_result.approve_count,
                        "deny_count": quorum_result.deny_count,
                        "abstain_count": quorum_result.abstain_count,
                    }
                    if warning:
                        data_pending["warning"] = warning
                    return ServiceResult(success=True, data=data_pending)

                # DEATH category → memorialise (seal forever)
                # PROOF_OF_LIFE → restore memorialised account
                # All other categories → activate leave (temporary freeze)
                if record.category == LeaveCategory.DEATH:
                    activation_data = self._memorialise_account(record, now)
                    err = self._record_leave_event(record, "memorialised")
                    if err:
                        # Rollback memorialisation
                        self._undo_memorialisation(record, old_state,
                                                    old_approved_utc, old_adjudications)
                        return ServiceResult(success=False, errors=[err])
                elif record.category == LeaveCategory.PROOF_OF_LIFE:
                    activation_data = self._restore_memorialised_account(
                        record, now,
                    )
                    err = self._record_leave_event(record, "restored")
                    if err:
                        # Rollback restoration
                        self._undo_restoration(
                            record, old_state, old_approved_utc,
                            old_adjudications,
                            activation_data.get("_rollback"),
                        )
                        return ServiceResult(success=False, errors=[err])
                else:
                    activation_data = self._activate_leave(record, now)
                    err = self._record_leave_event(record, "approved")
                    if err:
                        self._undo_leave_activation(record, old_state,
                                                    old_approved_utc, old_adjudications)
                        return ServiceResult(success=False, errors=[err])
            else:
                # Deny
                record.state = LeaveState.DENIED
                record.denied_utc = now
                err = self._record_leave_event(record, "denied")
                if err:
                    record.state = old_state
                    record.denied_utc = old_denied_utc
                    record.adjudications = old_adjudications
                    return ServiceResult(success=False, errors=[err])

        warning = self._safe_persist_post_audit()
        data: dict[str, Any] = {
            "leave_id": leave_id,
            "state": record.state.value,
            "quorum_reached": quorum_result.quorum_reached,
            "approve_count": quorum_result.approve_count,
            "deny_count": quorum_result.deny_count,
            "abstain_count": quorum_result.abstain_count,
        }
        if activation_data:
            data["trust_frozen"] = True
            data["trust_score_at_freeze"] = activation_data["trust_score_at_freeze"]
        if warning:
            data["warning"] = warning
        return ServiceResult(success=True, data=data)

    def return_from_leave(self, leave_id: str) -> ServiceResult:
        """Return an actor from active leave.

        Restores ACTIVE status. Resets last_active_utc to now so
        decay resumes from the return moment, not from the original
        last-activity. Trust score is preserved from the freeze.
        """
        record = self._leave_records.get(leave_id)
        if record is None:
            return ServiceResult(
                success=False, errors=[f"Leave record not found: {leave_id}"],
            )
        if record.state == LeaveState.MEMORIALISED:
            return ServiceResult(
                success=False,
                errors=[
                    "Cannot return from memorialised leave — "
                    "account is permanently sealed"
                ],
            )
        if record.state != LeaveState.ACTIVE:
            return ServiceResult(
                success=False,
                errors=[f"Leave is {record.state.value}; can only return from ACTIVE"],
            )

        now = datetime.now(timezone.utc)
        actor_id = record.actor_id

        # Snapshot for rollback
        entry = self._roster.get(actor_id)
        old_status = entry.status if entry else None
        trust = self._trust_records.get(actor_id)
        old_last_active = trust.last_active_utc if trust else None
        # Snapshot per-domain last_active timestamps for rollback
        old_domain_last_active: dict[str, Any] = {}
        if trust:
            for domain, ds in trust.domain_scores.items():
                if hasattr(ds, "last_active_utc"):
                    old_domain_last_active[domain] = ds.last_active_utc

        # Transition
        record.state = LeaveState.RETURNED
        record.returned_utc = now
        if entry:
            # Restore pre-leave status (prevents PROBATION → ACTIVE escalation)
            restored_status = ActorStatus.ACTIVE
            if record.pre_leave_status:
                try:
                    restored_status = ActorStatus(record.pre_leave_status)
                except ValueError:
                    restored_status = ActorStatus.ACTIVE
            entry.status = restored_status
        # Reset last_active to now — decay resumes from return
        if trust:
            trust.last_active_utc = now
            # Also reset domain last_active timestamps
            for ds in trust.domain_scores.values():
                if hasattr(ds, "last_active_utc"):
                    ds.last_active_utc = now

        err = self._record_leave_event(record, "returned")
        if err:
            record.state = LeaveState.ACTIVE
            record.returned_utc = None
            if entry and old_status is not None:
                entry.status = old_status
            if trust:
                if old_last_active is not None:
                    trust.last_active_utc = old_last_active
                # Restore per-domain timestamps
                for domain, old_ts in old_domain_last_active.items():
                    ds = trust.domain_scores.get(domain)
                    if ds and hasattr(ds, "last_active_utc"):
                        ds.last_active_utc = old_ts
            return ServiceResult(success=False, errors=[err])

        warning = self._safe_persist_post_audit()
        data: dict[str, Any] = {
            "leave_id": leave_id,
            "actor_id": actor_id,
            "state": record.state.value,
        }
        if warning:
            data["warning"] = warning
        return ServiceResult(success=True, data=data)

    def petition_memorialisation(
        self,
        actor_id: str,
        petitioner_id: str,
        reason_summary: str = "",
    ) -> ServiceResult:
        """Petition to memorialise a deceased actor's account.

        Filed by a third party (relative, friend, colleague) — not
        self-requested. Creates a PENDING leave record with category
        DEATH. The same quorum adjudication process applies: qualified
        professionals assess the evidence and vote.

        On approval, the account is permanently sealed:
        - Status becomes MEMORIALISED (not ON_LEAVE).
        - Trust frozen forever — no gain, no loss, no decay.
        - Account can never be reactivated.
        - The person's verified record stands honestly.
        """
        actor_id = actor_id.strip()
        petitioner_id = petitioner_id.strip()

        # Validate actor exists
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(
                success=False, errors=[f"Actor not found: {actor_id}"],
            )
        # Only human accounts can be memorialised
        if entry.actor_kind != ActorKind.HUMAN:
            return ServiceResult(
                success=False,
                errors=["Only human actors can be memorialised"],
            )
        # Cannot memorialise an already-memorialised account
        if entry.status == ActorStatus.MEMORIALISED:
            return ServiceResult(
                success=False,
                errors=[f"Actor {actor_id} is already memorialised"],
            )
        # Block duplicate death petitions — no parallel pending/active death records
        existing_death_leaves = [
            r for r in self._leave_records.values()
            if r.actor_id == actor_id
            and r.category == LeaveCategory.DEATH
            and r.state in (LeaveState.PENDING, LeaveState.ACTIVE, LeaveState.MEMORIALISED)
        ]
        if existing_death_leaves:
            return ServiceResult(
                success=False,
                errors=[
                    f"Actor {actor_id} already has an active death "
                    f"memorialisation record (state: {existing_death_leaves[0].state.value})"
                ],
            )

        # Petitioner must be a different registered human
        pet_entry = self._roster.get(petitioner_id)
        if pet_entry is None:
            return ServiceResult(
                success=False,
                errors=[f"Petitioner not found: {petitioner_id}"],
            )
        if petitioner_id == actor_id:
            return ServiceResult(
                success=False,
                errors=["Cannot petition memorialisation for yourself"],
            )
        if pet_entry.actor_kind != ActorKind.HUMAN:
            return ServiceResult(
                success=False,
                errors=["Only human actors can petition memorialisation"],
            )

        # Create PENDING death leave record
        now = datetime.now(timezone.utc)
        self._leave_counter += 1
        leave_id = f"LEAVE-{self._leave_counter:06d}"

        record = LeaveRecord(
            leave_id=leave_id,
            actor_id=actor_id,
            category=LeaveCategory.DEATH,
            state=LeaveState.PENDING,
            reason_summary=reason_summary,
            petitioner_id=petitioner_id,
            requested_utc=now,
        )
        self._leave_records[leave_id] = record

        err = self._record_leave_event(record, "requested")
        if err:
            del self._leave_records[leave_id]
            self._leave_counter -= 1
            return ServiceResult(success=False, errors=[err])

        warning = self._safe_persist_post_audit()
        data: dict[str, Any] = {"leave_id": leave_id, "state": record.state.value}
        if warning:
            data["warning"] = warning
        return ServiceResult(success=True, data=data)

    def petition_memorialisation_reversal(
        self,
        actor_id: str,
        reason_summary: str = "",
    ) -> ServiceResult:
        """Petition to reverse a memorialisation — proof-of-life.

        Filed by the supposedly-deceased actor themselves. This is the
        one case where the affected person petitions directly, because
        they are asserting their own existence.

        Creates a PENDING leave record with category PROOF_OF_LIFE.
        The same quorum adjudication process applies, but routed to
        legal experts. The evidentiary standard is equally rigorous
        as the original memorialisation.

        On approval:
        - The original DEATH record transitions to RESTORED.
        - Actor status returns to pre-memorialisation state.
        - Trust is unfrozen: score and domain scores preserved.
        - last_active_utc reset to now (decay resumes from return).
        """
        actor_id = actor_id.strip()

        # Validate actor exists
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(
                success=False, errors=[f"Actor not found: {actor_id}"],
            )
        # Must currently be memorialised
        if entry.status != ActorStatus.MEMORIALISED:
            return ServiceResult(
                success=False,
                errors=[
                    f"Actor {actor_id} is not memorialised "
                    f"(status: {entry.status.value})"
                ],
            )
        # Must be human (only human accounts can be memorialised)
        if entry.actor_kind != ActorKind.HUMAN:
            return ServiceResult(
                success=False,
                errors=["Only human actors can petition for restoration"],
            )
        # Block duplicate proof-of-life petitions
        existing_pol = [
            r for r in self._leave_records.values()
            if r.actor_id == actor_id
            and r.category == LeaveCategory.PROOF_OF_LIFE
            and r.state == LeaveState.PENDING
        ]
        if existing_pol:
            return ServiceResult(
                success=False,
                errors=[
                    f"Actor {actor_id} already has a pending "
                    f"proof-of-life petition"
                ],
            )

        # Create PENDING proof-of-life leave record
        now = datetime.now(timezone.utc)
        self._leave_counter += 1
        leave_id = f"LEAVE-{self._leave_counter:06d}"

        record = LeaveRecord(
            leave_id=leave_id,
            actor_id=actor_id,
            category=LeaveCategory.PROOF_OF_LIFE,
            state=LeaveState.PENDING,
            reason_summary=reason_summary,
            petitioner_id=actor_id,  # Self-petitioned — they're alive
            requested_utc=now,
        )
        self._leave_records[leave_id] = record

        err = self._record_leave_event(record, "requested")
        if err:
            del self._leave_records[leave_id]
            self._leave_counter -= 1
            return ServiceResult(success=False, errors=[err])

        warning = self._safe_persist_post_audit()
        data: dict[str, Any] = {"leave_id": leave_id, "state": record.state.value}
        if warning:
            data["warning"] = warning
        return ServiceResult(success=True, data=data)

    def _memorialise_account(
        self, record: LeaveRecord, now: datetime,
    ) -> dict[str, Any]:
        """Seal a deceased actor's account. Called when death quorum approves.

        - Snapshots trust (same as _activate_leave).
        - Sets actor status to MEMORIALISED (not ON_LEAVE).
        - Sets leave state to MEMORIALISED.
        - Account can never be reactivated.
        """
        actor_id = record.actor_id
        trust = self._trust_records.get(actor_id)
        entry = self._roster.get(actor_id)

        # Snapshot pre-memorialisation status
        if entry:
            record.pre_leave_status = entry.status.value

        # Snapshot trust state for permanent freeze
        if trust:
            record.trust_score_at_freeze = trust.score
            record.last_active_utc_at_freeze = trust.last_active_utc
            record.domain_scores_at_freeze = {
                domain: DomainTrustScore(
                    domain=ds.domain,
                    score=ds.score,
                    quality=ds.quality,
                    reliability=ds.reliability,
                    volume=ds.volume,
                    effort=ds.effort,
                    mission_count=ds.mission_count,
                    last_active_utc=ds.last_active_utc,
                )
                for domain, ds in trust.domain_scores.items()
                if isinstance(ds, DomainTrustScore)
            }

        # Seal the account
        record.state = LeaveState.MEMORIALISED
        record.approved_utc = now
        record.memorialised_utc = now
        if entry:
            entry.status = ActorStatus.MEMORIALISED

        return {
            "trust_score_at_freeze": record.trust_score_at_freeze,
            "memorialised": True,
        }

    def check_leave_expiries(self) -> ServiceResult:
        """Periodic sweep: auto-return actors whose leave has expired.

        Categories with duration limits (e.g., pregnancy: 365 days,
        child_care: 365 days) get an expires_utc at approval time.
        When now > expires_utc, the leave auto-transitions to RETURNED.
        Extension requires a new adjudication (same quorum process).
        """
        expired: list[dict[str, Any]] = []
        errors_found: list[str] = []

        for leave_id, record in list(self._leave_records.items()):
            if self._leave_engine.check_leave_expiry(record):
                result = self.return_from_leave(leave_id)
                if result.success:
                    expired.append({
                        "leave_id": leave_id,
                        "actor_id": record.actor_id,
                        "category": record.category.value,
                    })
                else:
                    errors_found.extend(result.errors)

        return ServiceResult(
            success=len(errors_found) == 0,
            errors=errors_found,
            data={"expired_count": len(expired), "expired": expired},
        )

    def get_leave_record(self, leave_id: str) -> Optional[LeaveRecord]:
        """Look up a leave record."""
        return self._leave_records.get(leave_id)

    def get_actor_leaves(self, actor_id: str) -> list[LeaveRecord]:
        """Get all leave records for an actor."""
        return [
            r for r in self._leave_records.values()
            if r.actor_id == actor_id.strip()
        ]

    def is_actor_on_leave(self, actor_id: str) -> bool:
        """Check if an actor has an ACTIVE or MEMORIALISED leave record.

        Both states freeze trust: ACTIVE is temporary, MEMORIALISED is
        permanent (death). Either way the constitutional guarantee is the
        same — no gain, no loss, decay clock stopped.
        """
        return any(
            r.state in (LeaveState.ACTIVE, LeaveState.MEMORIALISED)
            for r in self._leave_records.values()
            if r.actor_id == actor_id.strip()
        )

    def get_leave_status(self) -> dict[str, Any]:
        """System-wide leave statistics."""
        by_state: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._leave_records.values():
            by_state[r.state.value] = by_state.get(r.state.value, 0) + 1
            if r.state in (LeaveState.ACTIVE, LeaveState.PENDING, LeaveState.MEMORIALISED):
                by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
        return {
            "total_records": len(self._leave_records),
            "by_state": by_state,
            "active_by_category": by_category,
        }

    # ------------------------------------------------------------------
    # Protected leave — internal helpers
    # ------------------------------------------------------------------

    def _activate_leave(
        self, record: LeaveRecord, now: datetime,
    ) -> dict[str, Any]:
        """Activate an approved leave — snapshot trust, set ON_LEAVE.

        Returns activation data for the service result.
        """
        actor_id = record.actor_id
        trust = self._trust_records.get(actor_id)
        entry = self._roster.get(actor_id)

        # Snapshot pre-leave actor status (to restore on return)
        if entry:
            record.pre_leave_status = entry.status.value

        # Snapshot trust state for freeze
        if trust:
            record.trust_score_at_freeze = trust.score
            record.last_active_utc_at_freeze = trust.last_active_utc
            # Deep-copy domain scores
            record.domain_scores_at_freeze = {
                domain: DomainTrustScore(
                    domain=ds.domain,
                    score=ds.score,
                    quality=ds.quality,
                    reliability=ds.reliability,
                    volume=ds.volume,
                    effort=ds.effort,
                    mission_count=ds.mission_count,
                    last_active_utc=ds.last_active_utc,
                )
                for domain, ds in trust.domain_scores.items()
                if isinstance(ds, DomainTrustScore)
            }

        # Set leave state
        record.state = LeaveState.ACTIVE
        record.approved_utc = now

        # Compute expiry if category has duration limit
        record.expires_utc = self._leave_engine.compute_expires_utc(
            record.category, now,
        )
        if record.expires_utc:
            # Extract granted duration from config
            duration_config = self._resolver.leave_duration_config()
            overrides = duration_config.get("category_overrides", {})
            default_max = duration_config.get("default_max_days")
            record.granted_duration_days = overrides.get(
                record.category.value, default_max,
            )

        # Set roster status to ON_LEAVE
        if entry:
            entry.status = ActorStatus.ON_LEAVE

        return {
            "trust_score_at_freeze": record.trust_score_at_freeze,
            "expires_utc": (
                record.expires_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                if record.expires_utc else None
            ),
        }

    def _undo_leave_activation(
        self,
        record: LeaveRecord,
        old_state: LeaveState,
        old_approved_utc: Optional[datetime],
        old_adjudications: list[LeaveAdjudication],
    ) -> None:
        """Rollback helper for a failed leave activation."""
        actor_id = record.actor_id
        record.state = old_state
        record.approved_utc = old_approved_utc
        record.adjudications = old_adjudications
        # Restore pre-leave status
        pre_status = record.pre_leave_status
        record.trust_score_at_freeze = None
        record.last_active_utc_at_freeze = None
        record.domain_scores_at_freeze = {}
        record.expires_utc = None
        record.granted_duration_days = None
        record.pre_leave_status = None
        entry = self._roster.get(actor_id)
        if entry:
            if pre_status:
                try:
                    entry.status = ActorStatus(pre_status)
                except ValueError:
                    entry.status = ActorStatus.ACTIVE
            else:
                entry.status = ActorStatus.ACTIVE

    def _undo_memorialisation(
        self,
        record: LeaveRecord,
        old_state: LeaveState,
        old_approved_utc: Optional[datetime],
        old_adjudications: list[LeaveAdjudication],
    ) -> None:
        """Rollback helper for a failed memorialisation."""
        actor_id = record.actor_id
        record.state = old_state
        record.approved_utc = old_approved_utc
        record.memorialised_utc = None
        record.adjudications = old_adjudications
        # Restore pre-memorialisation status
        pre_status = record.pre_leave_status
        record.trust_score_at_freeze = None
        record.last_active_utc_at_freeze = None
        record.domain_scores_at_freeze = {}
        record.pre_leave_status = None
        entry = self._roster.get(actor_id)
        if entry:
            if pre_status:
                try:
                    entry.status = ActorStatus(pre_status)
                except ValueError:
                    entry.status = ActorStatus.ACTIVE
            else:
                entry.status = ActorStatus.ACTIVE

    def _restore_memorialised_account(
        self, record: LeaveRecord, now: datetime,
    ) -> dict[str, Any]:
        """Restore a memorialised account — proof-of-life approved.

        Finds the original DEATH record, transitions it to RESTORED,
        restores the actor's pre-memorialisation status, and resets
        last_active_utc to now (decay resumes from return moment).
        """
        actor_id = record.actor_id
        entry = self._roster.get(actor_id)
        trust = self._trust_records.get(actor_id)

        # Find the original DEATH/MEMORIALISED record
        death_record = None
        for r in self._leave_records.values():
            if (r.actor_id == actor_id
                    and r.category == LeaveCategory.DEATH
                    and r.state == LeaveState.MEMORIALISED):
                death_record = r
                break

        # Snapshot for rollback
        rollback_data: dict[str, Any] = {}
        if death_record:
            rollback_data["death_leave_id"] = death_record.leave_id
            rollback_data["death_old_state"] = death_record.state.value
        if entry:
            rollback_data["old_actor_status"] = entry.status.value
        if trust:
            rollback_data["old_last_active"] = trust.last_active_utc
            # Snapshot per-domain last_active timestamps for rollback
            rollback_data["old_domain_last_active"] = {
                domain: ds.last_active_utc
                for domain, ds in trust.domain_scores.items()
                if isinstance(ds, DomainTrustScore)
                and hasattr(ds, "last_active_utc")
            }

        # Transition the original death record to RESTORED
        if death_record:
            death_record.state = LeaveState.RESTORED
            death_record.restored_utc = now

        # Mark the proof-of-life record as approved
        record.state = LeaveState.RESTORED
        record.approved_utc = now
        record.restored_utc = now

        # Restore actor status to pre-memorialisation state
        if entry and death_record and death_record.pre_leave_status:
            try:
                entry.status = ActorStatus(death_record.pre_leave_status)
            except ValueError:
                entry.status = ActorStatus.ACTIVE
        elif entry:
            entry.status = ActorStatus.ACTIVE

        # Reset last_active_utc to now (decay resumes from return)
        if trust:
            trust.last_active_utc = now
            # Reset per-domain last_active timestamps too
            for ds in trust.domain_scores.values():
                if isinstance(ds, DomainTrustScore) and hasattr(ds, "last_active_utc"):
                    ds.last_active_utc = now

        return {
            "trust_score_at_freeze": (
                death_record.trust_score_at_freeze if death_record else None
            ),
            "restored": True,
            "_rollback": rollback_data,
        }

    def _undo_restoration(
        self,
        record: LeaveRecord,
        old_state: LeaveState,
        old_approved_utc: Optional[datetime],
        old_adjudications: list[LeaveAdjudication],
        rollback_data: Optional[dict[str, Any]] = None,
    ) -> None:
        """Rollback helper for a failed restoration."""
        actor_id = record.actor_id
        record.state = old_state
        record.approved_utc = old_approved_utc
        record.restored_utc = None
        record.adjudications = old_adjudications

        if rollback_data:
            # Restore the death record
            death_leave_id = rollback_data.get("death_leave_id")
            if death_leave_id:
                death_record = self._leave_records.get(death_leave_id)
                if death_record:
                    death_record.state = LeaveState.MEMORIALISED
                    death_record.restored_utc = None

            # Restore actor status
            entry = self._roster.get(actor_id)
            old_status = rollback_data.get("old_actor_status")
            if entry and old_status:
                try:
                    entry.status = ActorStatus(old_status)
                except ValueError:
                    entry.status = ActorStatus.MEMORIALISED

            # Restore trust last_active (global + per-domain)
            trust = self._trust_records.get(actor_id)
            if trust and "old_last_active" in rollback_data:
                trust.last_active_utc = rollback_data["old_last_active"]
            old_domain_last_active = rollback_data.get(
                "old_domain_last_active", {},
            )
            if trust:
                for domain, old_ts in old_domain_last_active.items():
                    ds = trust.domain_scores.get(domain)
                    if ds is not None and isinstance(ds, DomainTrustScore):
                        ds.last_active_utc = old_ts

    def _record_leave_event(
        self, record: LeaveRecord, action: str,
    ) -> Optional[str]:
        """Record a leave event. Returns error string or None.

        Three-step ordering (same pattern as all other event recording):
        1. Pre-check epoch availability (fail fast).
        2. Durable append (if it fails, epoch stays clean).
        3. Epoch hash insertion (guaranteed to succeed).
        """
        # 1. Pre-check: verify epoch is open
        epoch = self._epoch_service.current_epoch
        if epoch is None or epoch.closed:
            return (
                "Audit-trail failure (no epoch open): "
                "No open epoch — call open_epoch() first."
            )

        event_data = (
            f"{record.leave_id}:{record.actor_id}:{action}:"
            f"{datetime.now(timezone.utc).isoformat()}"
        )
        event_hash = "sha256:" + hashlib.sha256(event_data.encode()).hexdigest()

        # Map action to EventKind
        action_to_kind = {
            "requested": EventKind.LEAVE_REQUESTED,
            "adjudicated": EventKind.LEAVE_ADJUDICATED,
            "approved": EventKind.LEAVE_APPROVED,
            "denied": EventKind.LEAVE_DENIED,
            "returned": EventKind.LEAVE_RETURNED,
            "permanent": EventKind.LEAVE_PERMANENT,
            "memorialised": EventKind.LEAVE_MEMORIALISED,
            "restored": EventKind.LEAVE_RESTORED,
        }
        event_kind = action_to_kind.get(action, EventKind.LEAVE_REQUESTED)

        # 2. Durable append
        if self._event_log is not None:
            try:
                event = EventRecord.create(
                    event_id=self._next_event_id(),
                    event_kind=event_kind,
                    actor_id=record.actor_id,
                    payload={
                        "leave_id": record.leave_id,
                        "actor_id": record.actor_id,
                        "category": record.category.value,
                        "action": action,
                        "state": record.state.value,
                        "event_hash": event_hash,
                    },
                )
                self._event_log.append(event)
            except (ValueError, OSError) as e:
                return f"Event log failure: {e}"

        # 3. Epoch hash insertion
        self._epoch_service.record_mission_event(event_hash)
        return None

    # ------------------------------------------------------------------
    # Quality assessment
    # ------------------------------------------------------------------

    def assess_quality(self, mission_id: str) -> ServiceResult:
        """Manually trigger quality assessment for a completed mission.

        Use this for:
        - Re-assessment after normative adjudication resolves
        - Debugging and auditing
        - Missions that were completed before the quality engine was active

        Automatically updates trust for worker and reviewers unless
        normative escalation is triggered.
        """
        return self._assess_and_update_quality(mission_id)

    def _assess_and_update_quality(self, mission_id: str) -> ServiceResult:
        """Internal: assess quality for a completed mission and update trust.

        Steps (fail-closed ordering):
        1. Validate mission is in terminal state.
        2. Run QualityEngine to derive worker + reviewer quality.
        3. If normative escalation triggered, return without trust update.
        4. Record quality assessment audit event.
        5. Update worker trust with derived quality.
        6. Update each reviewer's trust with their derived quality.
        7. Update reviewer assessment history sliding window.
        8. Persist state.
        """
        mission = self._missions.get(mission_id)
        if mission is None:
            return ServiceResult(
                success=False,
                errors=[f"Mission not found: {mission_id}"],
            )

        # Terminal state check (QualityEngine also validates, but fail early)
        terminal = {MissionState.APPROVED, MissionState.REJECTED}
        if mission.state not in terminal:
            return ServiceResult(
                success=False,
                errors=[
                    f"Quality assessment requires terminal state, "
                    f"got {mission.state.value}"
                ],
            )

        try:
            report = self._quality_engine.assess_mission(
                mission=mission,
                trust_records=self._trust_records,
                reviewer_histories=self._reviewer_assessment_history,
            )
        except ValueError as e:
            return ServiceResult(success=False, errors=[str(e)])

        # Normative escalation: skip auto trust update
        if report.normative_escalation_triggered:
            return ServiceResult(
                success=True,
                data={
                    "mission_id": mission_id,
                    "normative_escalation": True,
                    "worker_derived_quality": report.worker_assessment.derived_quality,
                    "message": (
                        "Normative escalation triggered — trust updates "
                        "deferred until human adjudication resolves."
                    ),
                },
            )

        # Record quality assessment audit event (fail-closed)
        err = self._record_quality_event(mission_id, report)
        if err:
            return ServiceResult(success=False, errors=[err])

        # Update worker trust with derived quality
        worker_result = self.update_trust(
            actor_id=report.worker_assessment.worker_id,
            quality=report.worker_assessment.derived_quality,
            reliability=self._trust_records.get(
                report.worker_assessment.worker_id, TrustRecord(
                    actor_id="", actor_kind=ActorKind.HUMAN, score=0.0,
                ),
            ).reliability,
            volume=self._trust_records.get(
                report.worker_assessment.worker_id, TrustRecord(
                    actor_id="", actor_kind=ActorKind.HUMAN, score=0.0,
                ),
            ).volume,
            reason=f"quality_assessment:{mission_id}",
            mission_id=mission_id,
        )

        # Update each reviewer's trust
        reviewer_results: list[dict[str, Any]] = []
        for ra in report.reviewer_assessments:
            reviewer_record = self._trust_records.get(ra.reviewer_id)
            if reviewer_record is None:
                continue  # Reviewer may have been removed

            rev_result = self.update_trust(
                actor_id=ra.reviewer_id,
                quality=ra.derived_quality,
                reliability=reviewer_record.reliability,
                volume=reviewer_record.volume,
                reason=f"reviewer_quality_assessment:{mission_id}",
                mission_id=mission_id,
            )
            reviewer_results.append({
                "reviewer_id": ra.reviewer_id,
                "derived_quality": ra.derived_quality,
                "alignment": ra.alignment_score,
                "calibration": ra.calibration_score,
                "trust_updated": rev_result.success,
            })

            # Update reviewer assessment history sliding window
            _, window_size = self._resolver.calibration_config()
            history = self._reviewer_assessment_history.get(ra.reviewer_id, [])
            history.append(ra)
            # Trim to window size
            if len(history) > window_size:
                history = history[-window_size:]
            self._reviewer_assessment_history[ra.reviewer_id] = history

        # Domain-specific trust update (if mission has skill requirements)
        domain_updates: list[dict[str, Any]] = []
        if (
            hasattr(report.worker_assessment, "domains")
            and report.worker_assessment.domains
            and self._resolver.has_skill_trust_config()
        ):
            worker_record = self._trust_records.get(
                report.worker_assessment.worker_id
            )
            if worker_record is not None:
                for domain in report.worker_assessment.domains:
                    # Get existing domain score components or use current record
                    existing_ds = worker_record.domain_scores.get(domain)
                    reliability = existing_ds.reliability if existing_ds else worker_record.reliability
                    volume = existing_ds.volume if existing_ds else worker_record.volume

                    new_record, domain_delta = self._trust_engine.apply_domain_update(
                        record=worker_record,
                        domain=domain,
                        quality=report.worker_assessment.derived_quality,
                        reliability=reliability,
                        volume=volume,
                        reason=f"domain_quality_assessment:{mission_id}",
                        mission_id=mission_id,
                    )
                    self._trust_records[report.worker_assessment.worker_id] = new_record
                    worker_record = new_record  # chain updates

                    # Update roster trust score to reflect new aggregate
                    roster_entry = self._roster.get(report.worker_assessment.worker_id)
                    if roster_entry:
                        roster_entry.trust_score = new_record.score

                    domain_updates.append({
                        "domain": domain,
                        "old_score": domain_delta.previous_score,
                        "new_score": domain_delta.new_score,
                    })

        # Skill outcome update (if mission has skill requirements)
        skill_update_data = None
        if mission.skill_requirements and mission.worker_id:
            approved = mission.state == MissionState.APPROVED
            skill_update_data = self._update_skills_from_outcome(
                mission.worker_id, mission, approved,
            )

        warning = self._safe_persist_post_audit()

        result_data: dict[str, Any] = {
            "mission_id": mission_id,
            "normative_escalation": False,
            "worker_derived_quality": report.worker_assessment.derived_quality,
            "worker_trust_updated": worker_result.success,
            "reviewer_assessments": reviewer_results,
        }
        if domain_updates:
            result_data["domain_trust_updates"] = domain_updates
        if skill_update_data:
            result_data["skill_updates"] = skill_update_data
        if warning:
            result_data["warning"] = warning

        return ServiceResult(
            success=True,
            data=result_data,
        )

    # ------------------------------------------------------------------
    # Epoch operations
    # ------------------------------------------------------------------

    def open_epoch(self, epoch_id: Optional[str] = None) -> ServiceResult:
        """Open a new commitment epoch."""
        try:
            eid = self._epoch_service.open_epoch(epoch_id)
            warning = self._safe_persist_post_audit()
            data: dict[str, Any] = {"epoch_id": eid}
            if warning:
                data["warning"] = warning
            return ServiceResult(success=True, data=data)
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
            warning = self._safe_persist_post_audit()
            data: dict[str, Any] = {
                "epoch_id": record.epoch_id,
                "previous_hash": self._epoch_service.previous_hash,
                "event_counts": self._epoch_service.epoch_event_counts(),
            }
            if warning:
                data["warning"] = warning
            return ServiceResult(success=True, data=data)
        except RuntimeError as e:
            return ServiceResult(success=False, errors=[str(e)])

    # ------------------------------------------------------------------
    # First Light and platform lifecycle
    # ------------------------------------------------------------------

    def check_first_light(
        self,
        monthly_revenue: "Decimal",
        monthly_costs: "Decimal",
        reserve_balance: "Decimal",
        missions_per_human_per_month: float = 0.0,
        avg_mission_value: "Decimal" = None,
        commission_rate: "Decimal" = None,
    ) -> ServiceResult:
        """Check whether First Light conditions are met and fire the event.

        First Light is the irreversible sustainability trigger:
        - monthly_revenue >= 1.5× monthly_costs, AND
        - reserve_balance >= 3-month reserve target.

        Once fired, PoC mode is disabled permanently. The event is
        logged exactly once — subsequent calls after achievement are
        no-ops that return the existing state.
        """
        from decimal import Decimal

        if self._first_light_achieved:
            return ServiceResult(
                success=True,
                data={"first_light": True, "already_achieved": True},
            )

        if avg_mission_value is None:
            avg_mission_value = Decimal("0")
        if commission_rate is None:
            commission_rate = Decimal("0.05")

        # Collect human registration timestamps from roster
        human_timestamps = [
            entry.registered_utc
            for entry in self._roster.all_actors()
            if entry.actor_kind == ActorKind.HUMAN
            and entry.registered_utc is not None
        ]

        estimate = self._first_light_estimator.estimate(
            human_registration_timestamps=human_timestamps,
            monthly_revenue=monthly_revenue,
            monthly_costs=monthly_costs,
            reserve_balance=reserve_balance,
            missions_per_human_per_month=missions_per_human_per_month,
            avg_mission_value=avg_mission_value,
            commission_rate=commission_rate,
        )

        if not estimate.achieved:
            return ServiceResult(
                success=True,
                data={
                    "first_light": False,
                    "progress_pct": estimate.progress_pct,
                    "estimated_date": (
                        estimate.estimated_first_light.isoformat()
                        if estimate.estimated_first_light else None
                    ),
                    "message": estimate.message,
                },
            )

        # --- First Light achieved — fire the event (exactly once) ---
        self._first_light_achieved = True

        # 1. Log the FIRST_LIGHT event
        if self._event_log is not None:
            try:
                event = EventRecord.create(
                    event_id=self._next_event_id(),
                    event_kind=EventKind.FIRST_LIGHT,
                    actor_id="system",
                    payload={
                        "monthly_revenue": str(monthly_revenue),
                        "monthly_costs": str(monthly_costs),
                        "sustainability_ratio": str(estimate.current_sustainability_ratio),
                        "reserve_balance": str(reserve_balance),
                        "reserve_target_3mo": str(estimate.reserve_target_3mo),
                        "human_count": estimate.current_humans,
                    },
                )
                # Epoch write FIRST — if this fails, event is not appended
                self._epoch_service.record_mission_event(event.event_hash)
                self._event_log.append(event)
            except (ValueError, OSError, RuntimeError):
                pass  # Event log append is best-effort for lifecycle events

        # 2. Disable PoC mode — First Light is irreversible
        self._resolver._policy.setdefault("poc_mode", {})["active"] = False

        # 3. Activate Genesis Common Fund — constitutional, non-discretionary
        now = datetime.now(timezone.utc)
        if not self._gcf_tracker.is_active:
            self._gcf_tracker.activate(now)
            # Log the GCF activation event
            if self._event_log is not None:
                try:
                    gcf_event = EventRecord.create(
                        event_id=self._next_event_id(),
                        event_kind=EventKind.GCF_ACTIVATED,
                        actor_id="system",
                        payload={
                            "activated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "gcf_contribution_rate": "0.01",
                            "trigger": "first_light",
                        },
                    )
                    self._epoch_service.record_mission_event(gcf_event.event_hash)
                    self._event_log.append(gcf_event)
                except (ValueError, OSError, RuntimeError):
                    pass  # Best-effort for lifecycle events

        warning = self._safe_persist_post_audit()
        data: dict[str, Any] = {
            "first_light": True,
            "achieved_now": True,
            "poc_mode_disabled": True,
            "gcf_activated": True,
            "human_count": estimate.current_humans,
            "sustainability_ratio": estimate.current_sustainability_ratio,
        }
        if warning:
            data["warning"] = warning
        return ServiceResult(success=True, data=data)

    def record_creator_allocation(
        self,
        mission_id: str,
        creator_allocation: "Decimal",
        employer_creator_fee: "Decimal",
        mission_reward: "Decimal",
        worker_id: str,
    ) -> ServiceResult:
        """Record creator allocation disbursement events (both sides).

        Called after commission computation to emit the constitutional
        CREATOR_ALLOCATION_DISBURSED event. Both the worker-side (5% of
        worker payment) and employer-side (5% of mission reward) are
        recorded as a single audit event with full breakdown.

        The allocation itself is computed by the CommissionEngine — this
        method logs the audit trail.
        """
        from decimal import Decimal

        total_creator = creator_allocation + employer_creator_fee
        if total_creator <= Decimal("0"):
            return ServiceResult(
                success=True,
                data={"recorded": False, "reason": "zero_allocation"},
            )

        if self._event_log is not None:
            try:
                params = self._resolver.commission_params()
                event = EventRecord.create(
                    event_id=self._next_event_id(),
                    event_kind=EventKind.CREATOR_ALLOCATION_DISBURSED,
                    actor_id="founder",
                    payload={
                        "mission_id": mission_id,
                        "worker_side_allocation": str(creator_allocation),
                        "employer_side_fee": str(employer_creator_fee),
                        "total_creator_income": str(total_creator),
                        "mission_reward": str(mission_reward),
                        "worker_id": worker_id,
                        "worker_side_rate": str(params.get("creator_allocation_rate", Decimal("0"))),
                        "employer_side_rate": str(params.get("employer_creator_fee_rate", Decimal("0"))),
                    },
                )
                # Epoch write FIRST — if this fails, event is not appended
                self._epoch_service.record_mission_event(event.event_hash)
                self._event_log.append(event)
            except (ValueError, OSError, RuntimeError) as exc:
                return ServiceResult(
                    success=False,
                    errors=[f"Failed to record creator allocation: {exc}"],
                )

        warning = self._safe_persist_post_audit()
        data: dict[str, Any] = {
            "recorded": True,
            "mission_id": mission_id,
            "worker_side_allocation": str(creator_allocation),
            "employer_side_fee": str(employer_creator_fee),
            "total_creator_income": str(total_creator),
        }
        if warning:
            data["warning"] = warning
        return ServiceResult(success=True, data=data)

    def set_founder(self, actor_id: str) -> ServiceResult:
        """Designate the platform founder for dormancy tracking.

        Must be called once during platform bootstrap. The founder's
        last-action timestamp is initialised to now. Any subsequent
        signed action (via record_founder_action) resets the 50-year
        dormancy counter.
        """
        entry = self._roster.get(actor_id)
        if entry is None:
            return ServiceResult(
                success=False,
                errors=[f"Actor not found: {actor_id}"],
            )
        if entry.actor_kind != ActorKind.HUMAN:
            return ServiceResult(
                success=False,
                errors=["Founder must be a verified human"],
            )
        self._founder_id = actor_id
        self._founder_last_action_utc = datetime.now(timezone.utc)
        warning = self._safe_persist_post_audit()
        data: dict[str, Any] = {
            "founder_id": actor_id,
            "last_action_utc": self._founder_last_action_utc.isoformat(),
        }
        if warning:
            data["warning"] = warning
        return ServiceResult(success=True, data=data)

    def record_founder_action(self) -> ServiceResult:
        """Reset the 50-year dormancy counter.

        Called on any cryptographically signed founder action: login,
        transaction, governance action, or explicit proof-of-life
        attestation. Resets the dormancy clock to now.
        """
        if self._founder_id is None:
            return ServiceResult(
                success=False,
                errors=["No founder designated — call set_founder() first"],
            )
        self._founder_last_action_utc = datetime.now(timezone.utc)
        warning = self._safe_persist_post_audit()
        data: dict[str, Any] = {
            "founder_id": self._founder_id,
            "last_action_utc": self._founder_last_action_utc.isoformat(),
            "dormancy_reset": True,
        }
        if warning:
            data["warning"] = warning
        return ServiceResult(success=True, data=data)

    def check_dormancy(self) -> ServiceResult:
        """Check whether the 50-year founder dormancy threshold is met.

        Returns the elapsed time since the founder's last signed action
        and whether the dormancy trigger would fire. Does NOT execute
        distribution — that requires multi-source time verification
        (NIST, PTB, BIPM/NPL, Ethereum) and governance ballot, which
        are external dependencies.
        """
        if self._founder_id is None:
            return ServiceResult(
                success=False,
                errors=["No founder designated"],
            )
        if self._founder_last_action_utc is None:
            return ServiceResult(
                success=False,
                errors=["No founder action recorded"],
            )

        now = datetime.now(timezone.utc)
        elapsed = now - self._founder_last_action_utc
        elapsed_years = elapsed.total_seconds() / (365.25 * 24 * 3600)
        dormancy_threshold_years = 50.0

        return ServiceResult(
            success=True,
            data={
                "founder_id": self._founder_id,
                "last_action_utc": self._founder_last_action_utc.isoformat(),
                "elapsed_years": round(elapsed_years, 4),
                "dormancy_threshold_years": dormancy_threshold_years,
                "dormancy_triggered": elapsed_years >= dormancy_threshold_years,
                "note": (
                    "Actual distribution requires multi-source time "
                    "verification (NIST, PTB, BIPM/NPL, Ethereum) and "
                    "3-chamber supermajority recipient selection."
                ),
            },
        )

    # ------------------------------------------------------------------
    # Production call-path integration (P2 wiring)
    # ------------------------------------------------------------------

    def process_mission_payment(
        self,
        mission_id: str,
        mission_reward: "Decimal",
        ledger: "OperationalLedger",
        reserve: "ReserveFundState",
    ) -> ServiceResult:
        """Process payment for an approved mission.

        Orchestrates the full payment flow:
        1. Validates mission is in APPROVED state.
        2. Computes commission via CommissionEngine.
        3. Records creator allocation event (audit trail).
        4. Returns the full breakdown for escrow settlement.

        This is the production call site that wires
        record_creator_allocation into the payment pipeline.
        """
        from decimal import Decimal
        from genesis.compensation.engine import CommissionEngine

        mission = self._missions.get(mission_id)
        if mission is None:
            return ServiceResult(
                success=False,
                errors=[f"Mission not found: {mission_id}"],
            )
        if mission.state != MissionState.APPROVED:
            return ServiceResult(
                success=False,
                errors=[f"Mission {mission_id} not APPROVED (state: {mission.state.value})"],
            )

        engine = CommissionEngine(self._resolver)
        breakdown = engine.compute_commission(
            mission_reward=mission_reward,
            ledger=ledger,
            reserve=reserve,
        )

        # Wire: record both-sides creator allocation event in the audit trail
        if breakdown.total_creator_income > Decimal("0"):
            alloc_result = self.record_creator_allocation(
                mission_id=mission_id,
                creator_allocation=breakdown.creator_allocation,
                employer_creator_fee=breakdown.employer_creator_fee,
                mission_reward=mission_reward,
                worker_id=mission.worker_id or "unknown",
            )
            if not alloc_result.success:
                return alloc_result

        # Wire: record GCF contribution if active and non-zero
        gcf_recorded = False
        if (
            self._gcf_tracker.is_active
            and breakdown.gcf_contribution > Decimal("0")
        ):
            self._gcf_tracker.record_contribution(
                amount=breakdown.gcf_contribution,
                mission_id=mission_id,
            )
            gcf_recorded = True
            # Log the GCF contribution event
            if self._event_log is not None:
                try:
                    gcf_event = EventRecord.create(
                        event_id=self._next_event_id(),
                        event_kind=EventKind.GCF_CONTRIBUTION_RECORDED,
                        actor_id="system",
                        payload={
                            "mission_id": mission_id,
                            "gcf_contribution": str(breakdown.gcf_contribution),
                            "gcf_balance": str(self._gcf_tracker.get_state().balance),
                            "mission_reward": str(mission_reward),
                        },
                    )
                    self._epoch_service.record_mission_event(gcf_event.event_hash)
                    self._event_log.append(gcf_event)
                except (ValueError, OSError, RuntimeError):
                    pass  # Best-effort for audit trail

        data: dict[str, Any] = {
            "mission_id": mission_id,
            "commission_rate": str(breakdown.rate),
            "commission_amount": str(breakdown.commission_amount),
            "creator_allocation": str(breakdown.creator_allocation),
            "employer_creator_fee": str(breakdown.employer_creator_fee),
            "total_creator_income": str(breakdown.total_creator_income),
            "worker_payout": str(breakdown.worker_payout),
            "mission_reward": str(mission_reward),
            "total_escrow": str(breakdown.total_escrow),
            "gcf_contribution": str(breakdown.gcf_contribution),
            "gcf_recorded": gcf_recorded,
        }
        return ServiceResult(success=True, data=data)

    def periodic_first_light_check(
        self,
        monthly_revenue: "Decimal",
        monthly_costs: "Decimal",
        reserve_balance: "Decimal",
        missions_per_human_per_month: float = 0.0,
        avg_mission_value: "Decimal" = None,
        commission_rate: "Decimal" = None,
    ) -> ServiceResult:
        """Production entry point for periodic First Light evaluation.

        This wraps check_first_light() and provides a deterministic
        call site for scheduled tasks or post-payment pipelines.
        Intended to be called from a cron-like scheduler or after
        each batch of mission completions.

        Returns the same result as check_first_light().
        """
        return self.check_first_light(
            monthly_revenue=monthly_revenue,
            monthly_costs=monthly_costs,
            reserve_balance=reserve_balance,
            missions_per_human_per_month=missions_per_human_per_month,
            avg_mission_value=avg_mission_value,
            commission_rate=commission_rate,
        )

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
            "market": {
                "total_listings": len(self._listings),
                "open_listings": sum(
                    1 for l in self._listings.values()
                    if l.state in (ListingState.OPEN, ListingState.ACCEPTING_BIDS)
                ),
                "total_bids": sum(len(b) for b in self._bids.values()),
            },
            "leave": {
                "total_records": len(self._leave_records),
                "active_leaves": sum(
                    1 for r in self._leave_records.values()
                    if r.state == LeaveState.ACTIVE
                ),
                "pending_requests": sum(
                    1 for r in self._leave_records.values()
                    if r.state == LeaveState.PENDING
                ),
            },
            "epochs": {
                "committed": len(self._epoch_service.committed_records),
                "anchored": len(self._epoch_service.anchor_records),
                "current_open": (
                    self._epoch_service.current_epoch is not None
                    and not self._epoch_service.current_epoch.closed
                ),
            },
            "first_light": {
                "achieved": self._first_light_achieved,
                "poc_mode_active": self._resolver.poc_mode().get("active", False),
            },
            "founder": {
                "designated": self._founder_id is not None,
                "founder_id": self._founder_id,
                "last_action_utc": (
                    self._founder_last_action_utc.isoformat()
                    if self._founder_last_action_utc else None
                ),
            },
            "persistence_degraded": self._persistence_degraded,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition_listing(
        self, listing_id: str, target: ListingState,
    ) -> ServiceResult:
        """Validate and apply a listing state transition.

        Fail-closed: if audit recording fails, the state transition
        is fully rolled back and an error is returned.
        """
        listing = self._listings.get(listing_id)
        if listing is None:
            return ServiceResult(
                success=False,
                errors=[f"Listing not found: {listing_id}"],
            )

        # Snapshot for rollback
        prior_state = listing.state
        prior_opened_utc = listing.opened_utc

        errors = ListingStateMachine.apply_transition(listing, target)
        if errors:
            return ServiceResult(success=False, errors=errors)

        if target == ListingState.OPEN:
            listing.opened_utc = datetime.now(timezone.utc)

        err = self._record_listing_event(listing, f"transition:{target.value}")
        if err:
            # Rollback: restore prior state and derived fields
            listing.state = prior_state
            listing.opened_utc = prior_opened_utc
            return ServiceResult(success=False, errors=[err])

        # Audit event committed — do NOT rollback in-memory state
        persist_warning = self._safe_persist_post_audit()
        result_data: dict[str, Any] = {
            "listing_id": listing_id, "state": listing.state.value,
        }
        if persist_warning:
            result_data["warning"] = persist_warning
        return ServiceResult(success=True, data=result_data)

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
        previous_state = mission.state
        mission.state = target

        err = self._record_mission_event(mission, f"transition:{target.value}")
        if err:
            mission.state = previous_state  # Rollback
            return ServiceResult(success=False, errors=[err])

        warning = self._safe_persist_post_audit()
        data: dict[str, Any] = {"state": mission.state.value}
        if warning:
            data["warning"] = warning
        return ServiceResult(success=True, data=data)

    def _next_event_id(self) -> str:
        """Generate a monotonically increasing unique event ID."""
        self._event_counter += 1
        return f"EVT-{self._event_counter:08d}"

    def _record_mission_event(self, mission: Mission, action: str) -> Optional[str]:
        """Hash and record a mission event. Returns error string or None.

        Fail-closed: if no epoch is open, returns an error rather than
        silently dropping the audit event.

        Three-step ordering ensures no phantom records in either store:
        1. Pre-check epoch availability (fail fast — nothing written yet).
        2. Durable append (if it fails, epoch stays clean).
        3. Epoch hash insertion (guaranteed to succeed — already validated).
        """
        # 1. Pre-check: verify epoch is open before writing anything
        epoch = self._epoch_service.current_epoch
        if epoch is None or epoch.closed:
            return "Audit-trail failure (no epoch open): No open epoch — call open_epoch() first."

        event_data = f"{mission.mission_id}:{action}:{datetime.now(timezone.utc).isoformat()}"
        event_hash = "sha256:" + hashlib.sha256(event_data.encode()).hexdigest()

        # 2. Durable append — if this fails, epoch stays clean
        if self._event_log is not None:
            try:
                event = EventRecord.create(
                    event_id=self._next_event_id(),
                    event_kind=EventKind.MISSION_TRANSITION,
                    actor_id=mission.worker_id or "system",
                    payload={
                        "mission_id": mission.mission_id,
                        "action": action,
                        "event_hash": event_hash,
                    },
                )
                self._event_log.append(event)
            except (ValueError, OSError) as e:
                return f"Event log failure: {e}"

        # 3. Epoch hash insertion — epoch was validated open in step 1
        self._epoch_service.record_mission_event(event_hash)

        return None

    def _record_trust_event(self, actor_id: str, delta: TrustDelta) -> Optional[str]:
        """Hash and record a trust delta. Returns error string or None.

        Fail-closed: if no epoch is open, returns an error.

        Three-step ordering ensures no phantom records in either store:
        1. Pre-check epoch availability (fail fast — nothing written yet).
        2. Durable append (if it fails, epoch stays clean).
        3. Epoch hash insertion (guaranteed to succeed — already validated).
        """
        # 1. Pre-check: verify epoch is open before writing anything
        epoch = self._epoch_service.current_epoch
        if epoch is None or epoch.closed:
            return "Audit-trail failure (no epoch open): No open epoch — call open_epoch() first."

        event_data = f"{actor_id}:{delta.abs_delta}:{datetime.now(timezone.utc).isoformat()}"
        event_hash = "sha256:" + hashlib.sha256(event_data.encode()).hexdigest()

        # 2. Durable append — if this fails, epoch stays clean
        if self._event_log is not None:
            try:
                event = EventRecord.create(
                    event_id=self._next_event_id(),
                    event_kind=EventKind.TRUST_UPDATED,
                    actor_id=actor_id,
                    payload={
                        "delta": delta.abs_delta,
                        "suspended": delta.suspended,
                        "event_hash": event_hash,
                    },
                )
                self._event_log.append(event)
            except (ValueError, OSError) as e:
                return f"Event log failure: {e}"

        # 3. Epoch hash insertion — epoch was validated open in step 1
        self._epoch_service.record_trust_delta(event_hash)

        return None

    def _record_quality_event(
        self, mission_id: str, report: MissionQualityReport,
    ) -> Optional[str]:
        """Hash and record a quality assessment event. Returns error or None.

        Three-step ordering (same pattern as mission/trust events):
        1. Pre-check epoch availability.
        2. Durable append.
        3. Epoch hash insertion.
        """
        # 1. Pre-check: verify epoch is open before writing anything
        epoch = self._epoch_service.current_epoch
        if epoch is None or epoch.closed:
            return (
                "Audit-trail failure (no epoch open): "
                "No open epoch — call open_epoch() first."
            )

        event_data = (
            f"{mission_id}:quality_assessed:"
            f"{report.worker_assessment.derived_quality:.4f}:"
            f"{datetime.now(timezone.utc).isoformat()}"
        )
        event_hash = "sha256:" + hashlib.sha256(
            event_data.encode()
        ).hexdigest()

        # 2. Durable append — if this fails, epoch stays clean
        if self._event_log is not None:
            try:
                event = EventRecord.create(
                    event_id=self._next_event_id(),
                    event_kind=EventKind.QUALITY_ASSESSED,
                    actor_id=report.worker_assessment.worker_id,
                    payload={
                        "mission_id": mission_id,
                        "worker_quality": report.worker_assessment.derived_quality,
                        "reviewer_count": len(report.reviewer_assessments),
                        "normative_escalation": report.normative_escalation_triggered,
                        "event_hash": event_hash,
                    },
                )
                self._event_log.append(event)
            except (ValueError, OSError) as e:
                return f"Event log failure: {e}"

        # 3. Epoch hash insertion — epoch was validated open in step 1
        self._epoch_service.record_mission_event(event_hash)

        return None

    def _record_listing_event(
        self, listing: MarketListing, action: str,
    ) -> Optional[str]:
        """Record a listing event. Returns error string or None."""
        epoch = self._epoch_service.current_epoch
        if epoch is None or epoch.closed:
            return "Audit-trail failure (no epoch open): No open epoch — call open_epoch() first."

        event_data = f"{listing.listing_id}:{action}:{datetime.now(timezone.utc).isoformat()}"
        event_hash = "sha256:" + hashlib.sha256(event_data.encode()).hexdigest()

        if self._event_log is not None:
            try:
                event = EventRecord.create(
                    event_id=self._next_event_id(),
                    event_kind=EventKind.LISTING_CREATED if action == "created" else EventKind.LISTING_TRANSITION,
                    actor_id=listing.creator_id,
                    payload={
                        "listing_id": listing.listing_id,
                        "action": action,
                        "event_hash": event_hash,
                    },
                )
                self._event_log.append(event)
            except (ValueError, OSError) as e:
                return f"Event log failure: {e}"

        self._epoch_service.record_mission_event(event_hash)
        return None

    def _record_bid_event(self, bid: Bid) -> Optional[str]:
        """Record a bid submission event. Returns error string or None."""
        epoch = self._epoch_service.current_epoch
        if epoch is None or epoch.closed:
            return "Audit-trail failure (no epoch open): No open epoch — call open_epoch() first."

        event_data = f"{bid.bid_id}:{bid.listing_id}:{bid.worker_id}:{datetime.now(timezone.utc).isoformat()}"
        event_hash = "sha256:" + hashlib.sha256(event_data.encode()).hexdigest()

        if self._event_log is not None:
            try:
                event = EventRecord.create(
                    event_id=self._next_event_id(),
                    event_kind=EventKind.BID_SUBMITTED,
                    actor_id=bid.worker_id,
                    payload={
                        "bid_id": bid.bid_id,
                        "listing_id": bid.listing_id,
                        "worker_id": bid.worker_id,
                        "composite_score": bid.composite_score,
                        "event_hash": event_hash,
                    },
                )
                self._event_log.append(event)
            except (ValueError, OSError) as e:
                return f"Event log failure: {e}"

        self._epoch_service.record_mission_event(event_hash)
        return None

    def _record_allocation_event(
        self, listing: MarketListing, result: AllocationResult,
    ) -> Optional[str]:
        """Record a worker allocation event. Returns error string or None."""
        epoch = self._epoch_service.current_epoch
        if epoch is None or epoch.closed:
            return "Audit-trail failure (no epoch open): No open epoch — call open_epoch() first."

        event_data = (
            f"{listing.listing_id}:{result.selected_worker_id}:"
            f"{result.composite_score}:{datetime.now(timezone.utc).isoformat()}"
        )
        event_hash = "sha256:" + hashlib.sha256(event_data.encode()).hexdigest()

        if self._event_log is not None:
            try:
                event = EventRecord.create(
                    event_id=self._next_event_id(),
                    event_kind=EventKind.WORKER_ALLOCATED,
                    actor_id=listing.creator_id,
                    payload={
                        "listing_id": listing.listing_id,
                        "selected_bid_id": result.selected_bid_id,
                        "selected_worker_id": result.selected_worker_id,
                        "composite_score": result.composite_score,
                        "mission_id": listing.allocated_mission_id,
                        "event_hash": event_hash,
                    },
                )
                self._event_log.append(event)
            except (ValueError, OSError) as e:
                return f"Event log failure: {e}"

        self._epoch_service.record_mission_event(event_hash)
        return None

    def _record_actor_lifecycle_event(
        self,
        actor_id: str,
        event_kind: EventKind,
        payload: dict[str, Any],
    ) -> Optional[str]:
        """Record an actor lifecycle event. Returns error string or None.

        Reusable 3-step event recorder for machine immune system and
        identity verification events. Same epoch-before-append ordering
        as all other event helpers.
        """
        # 1. Pre-check: verify epoch is open before writing anything
        epoch = self._epoch_service.current_epoch
        if epoch is None or epoch.closed:
            return "Audit-trail failure (no epoch open): No open epoch — call open_epoch() first."

        event_data = f"{actor_id}:{event_kind.value}:{datetime.now(timezone.utc).isoformat()}"
        event_hash = "sha256:" + hashlib.sha256(event_data.encode()).hexdigest()

        # 2. Durable append — if this fails, epoch stays clean
        if self._event_log is not None:
            try:
                payload_with_hash = {**payload, "event_hash": event_hash}
                event = EventRecord.create(
                    event_id=self._next_event_id(),
                    event_kind=event_kind,
                    actor_id=actor_id,
                    payload=payload_with_hash,
                )
                self._event_log.append(event)
            except (ValueError, OSError) as e:
                return f"Event log failure: {e}"

        # 3. Epoch hash insertion — epoch was validated open in step 1
        self._epoch_service.record_mission_event(event_hash)
        return None

    def _persist_state(self) -> None:
        """Persist current state to the state store (if wired).

        NOTE: This method can raise OSError. High-impact mutators
        should use _safe_persist() instead for fail-closed behavior.
        """
        if self._state_store is None:
            return
        self._state_store.save_roster(self._roster)
        self._state_store.save_trust_records(self._trust_records)
        self._state_store.save_missions(self._missions)
        self._state_store.save_reviewer_histories(self._reviewer_assessment_history)
        self._state_store.save_skill_profiles(self._skill_profiles)
        self._state_store.save_listings(self._listings, self._bids)
        self._state_store.save_leave_records(self._leave_records)
        self._state_store.save_epoch_state(
            self._epoch_service.previous_hash,
            len(self._epoch_service.committed_records),
        )
        self._state_store.save_lifecycle_state(
            self._first_light_achieved,
            self._founder_id,
            self._founder_last_action_utc,
        )
        self._state_store.save_escrows(self._escrow_manager._escrows)
        self._state_store.save_workflows(self._workflow_orchestrator._workflows)

    def _safe_persist(
        self,
        on_rollback: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Persist state with fail-closed error handling (pre-audit mode).

        Use this BEFORE audit events have been committed. On failure:
        1. Executes the rollback callback to undo in-memory mutations.
        2. Returns an error string for the caller to include in
           a ServiceResult.

        On success, returns None.
        """
        try:
            self._persist_state()
            return None
        except OSError as e:
            if on_rollback is not None:
                on_rollback()
            return f"Persistence failure: {e}"

    def _safe_persist_post_audit(self) -> Optional[str]:
        """Persist state after audit events have been committed.

        MUST NOT rollback in-memory state — the audit trail is already
        durable. If persist fails, in-memory state remains correct
        (aligned with audit events), but StateStore is stale.

        Sets _persistence_degraded flag for operator awareness and
        returns a warning string (not a hard error).
        """
        try:
            self._persist_state()
            return None
        except OSError as e:
            self._persistence_degraded = True
            return f"Persistence degraded: {e} — state committed in audit trail but StateStore is stale"

    # ------------------------------------------------------------------
    # Compliance (Phase E-2)
    # ------------------------------------------------------------------

    def screen_mission_compliance(
        self,
        title: str,
        description: str,
        tags: Optional[list[str]] = None,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Screen a mission proposal for compliance violations.

        Returns screening result with verdict (CLEAR/FLAGGED/REJECTED).
        """
        if now is None:
            now = datetime.now(timezone.utc)

        result = self._compliance_screener.screen_mission(
            title=title, description=description, tags=tags, now=now,
        )

        # Emit screening event
        self._record_actor_lifecycle_event(
            "system",
            EventKind.COMPLIANCE_SCREENING_COMPLETED,
            {
                "verdict": result.verdict.value,
                "categories_matched": result.categories_matched,
                "reason": result.reason,
                "confidence": result.confidence,
            },
        )

        return ServiceResult(
            success=True,
            data={
                "verdict": result.verdict.value,
                "categories_matched": result.categories_matched,
                "reason": result.reason,
                "confidence": result.confidence,
            },
        )

    def file_compliance_complaint(
        self,
        mission_id: str,
        complainant_id: str,
        reason: str,
        category: str,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """File a post-hoc compliance complaint against a mission."""
        if now is None:
            now = datetime.now(timezone.utc)

        # Verify complainant exists
        complainant = self._roster.get(complainant_id)
        if complainant is None:
            return ServiceResult(
                success=False,
                errors=[f"Complainant not found: {complainant_id}"],
            )

        # Verify mission exists
        if mission_id not in self._missions:
            return ServiceResult(
                success=False,
                errors=[f"Mission not found: {mission_id}"],
            )

        try:
            complaint = self._compliance_screener.file_compliance_complaint(
                mission_id=mission_id,
                complainant_id=complainant_id,
                reason=reason,
                category=category,
                now=now,
            )
        except ValueError as e:
            return ServiceResult(success=False, errors=[str(e)])

        # Emit complaint event
        self._record_actor_lifecycle_event(
            complainant_id,
            EventKind.COMPLIANCE_COMPLAINT_FILED,
            {
                "complaint_id": complaint.complaint_id,
                "mission_id": mission_id,
                "category": category,
                "reason": reason,
            },
        )

        return ServiceResult(
            success=True,
            data={
                "complaint_id": complaint.complaint_id,
                "mission_id": mission_id,
                "category": category,
            },
        )

    def apply_penalty(
        self,
        actor_id: str,
        violation_type: str,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Apply a compliance penalty to an actor.

        Computes penalty based on violation type and prior violations.
        Updates trust, status, and emits events as appropriate.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        actor = self._roster.get(actor_id)
        if actor is None:
            return ServiceResult(
                success=False,
                errors=[f"Actor not found: {actor_id}"],
            )

        # Resolve violation type
        try:
            vtype = ViolationType(violation_type)
        except ValueError:
            return ServiceResult(
                success=False,
                errors=[f"Unknown violation type: {violation_type}"],
            )

        # Compute penalty with prior violation history
        priors = self._prior_violations.get(actor_id, [])
        outcome = self._penalty_engine.compute_penalty(
            actor_id=actor_id,
            violation_type=vtype,
            prior_violations=priors,
            now=now,
        )

        # Apply trust action
        trust_record = self._trust_records.get(actor_id)
        if outcome.trust_action == "nuke":
            actor.trust_score = outcome.trust_target
            if trust_record is not None:
                trust_record.score = outcome.trust_target
        elif outcome.trust_action == "reduce" and trust_record is not None:
            new_score = max(0.0, trust_record.score + outcome.trust_target)
            actor.trust_score = new_score
            trust_record.score = new_score

        # Apply status change
        if outcome.permanent:
            actor.status = ActorStatus.PERMANENTLY_DECOMMISSIONED
            self._record_actor_lifecycle_event(
                actor_id,
                EventKind.ACTOR_PERMANENTLY_DECOMMISSIONED,
                {
                    "severity": outcome.severity.value,
                    "reason": outcome.reason,
                    "identity_locked": outcome.identity_locked,
                },
            )
        elif outcome.suspension_days > 0:
            actor.status = ActorStatus.SUSPENDED
            suspension_end = now + timedelta(days=outcome.suspension_days)
            self._suspended_until[actor_id] = suspension_end
            self._record_actor_lifecycle_event(
                actor_id,
                EventKind.ACTOR_SUSPENDED,
                {
                    "severity": outcome.severity.value,
                    "reason": outcome.reason,
                    "suspension_days": outcome.suspension_days,
                    "suspended_until_utc": suspension_end.isoformat(),
                },
            )

        # Record this violation for future escalation
        self._prior_violations.setdefault(actor_id, []).append(
            PriorViolation(
                severity=outcome.severity,
                violation_type=vtype,
                occurred_utc=now,
            )
        )

        self._safe_persist_post_audit()

        return ServiceResult(
            success=True,
            data={
                "actor_id": actor_id,
                "severity": outcome.severity.value,
                "trust_action": outcome.trust_action,
                "trust_target": outcome.trust_target,
                "suspension_days": outcome.suspension_days,
                "permanent": outcome.permanent,
                "identity_locked": outcome.identity_locked,
                "reason": outcome.reason,
            },
        )

    def is_actor_suspended(self, actor_id: str) -> bool:
        """Check whether an actor is currently suspended."""
        actor = self._roster.get(actor_id)
        if actor is None:
            return False
        return actor.status in (
            ActorStatus.SUSPENDED,
            ActorStatus.PERMANENTLY_DECOMMISSIONED,
        )

    def check_suspension_expiry(
        self,
        actor_id: str,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Check and auto-expire suspensions that have elapsed.

        Returns the actor's current status after check.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        actor = self._roster.get(actor_id)
        if actor is None:
            return ServiceResult(
                success=False,
                errors=[f"Actor not found: {actor_id}"],
            )

        # Permanently decommissioned actors never expire
        if actor.status == ActorStatus.PERMANENTLY_DECOMMISSIONED:
            return ServiceResult(
                success=True,
                data={"actor_id": actor_id, "status": actor.status.value, "expired": False},
            )

        # Check if suspension has elapsed
        if actor.status == ActorStatus.SUSPENDED and actor_id in self._suspended_until:
            if now >= self._suspended_until[actor_id]:
                suspension_end = self._suspended_until[actor_id]
                del self._suspended_until[actor_id]
                # E-3: Expired suspensions enter PROBATION + rehabilitation
                actor.status = ActorStatus.PROBATION
                # Create rehabilitation record if applicable
                original_trust = actor.trust_score
                try:
                    rehab = self._rehabilitation_engine.create_rehabilitation(
                        actor_id=actor_id,
                        case_id=f"suspension-{actor_id}",
                        original_trust=original_trust,
                        severity="moderate",
                        suspension_start=suspension_end - timedelta(days=90),
                        suspension_end=suspension_end,
                        now=now,
                    )
                    self._rehabilitation_engine.start_rehabilitation(rehab.rehab_id, now)
                    self._record_actor_lifecycle_event(
                        actor_id,
                        EventKind.REHABILITATION_STARTED,
                        {
                            "rehab_id": rehab.rehab_id,
                            "original_trust": original_trust,
                            "status": "active",
                        },
                    )
                except ValueError:
                    pass  # Severe/egregious — should not happen for suspended actors
                return ServiceResult(
                    success=True,
                    data={
                        "actor_id": actor_id,
                        "status": actor.status.value,
                        "expired": True,
                    },
                )

        return ServiceResult(
            success=True,
            data={"actor_id": actor_id, "status": actor.status.value, "expired": False},
        )

    # ------------------------------------------------------------------
    # Three-Tier Justice (Phase E-3)
    # ------------------------------------------------------------------

    def open_adjudication(
        self,
        type: str,
        complainant_id: str,
        accused_id: str,
        reason: str,
        mission_id: Optional[str] = None,
        evidence_hashes: Optional[list[str]] = None,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Open a Tier 2 adjudication case.

        Validates both actors exist, opens case, creates rights record,
        discloses evidence, and emits ADJUDICATION_OPENED event.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Validate actors exist
        complainant = self._roster.get(complainant_id)
        if complainant is None:
            return ServiceResult(
                success=False,
                errors=[f"Complainant not found: {complainant_id}"],
            )

        accused = self._roster.get(accused_id)
        if accused is None:
            return ServiceResult(
                success=False,
                errors=[f"Accused not found: {accused_id}"],
            )

        try:
            adj_type = LegalAdjudicationType(type)
        except ValueError:
            return ServiceResult(
                success=False,
                errors=[f"Unknown adjudication type: {type}"],
            )

        try:
            case = self._adjudication_engine.open_case(
                type=adj_type,
                complainant_id=complainant_id,
                accused_id=accused_id,
                reason=reason,
                now=now,
                mission_id=mission_id,
                evidence_hashes=evidence_hashes,
            )
        except ValueError as e:
            return ServiceResult(success=False, errors=[str(e)])

        # Create rights record and disclose evidence
        self._rights_enforcer.create_rights_record(case.case_id, accused_id, now)
        self._rights_enforcer.mark_evidence_disclosed(case.case_id)

        self._record_actor_lifecycle_event(
            complainant_id,
            EventKind.ADJUDICATION_OPENED,
            {
                "case_id": case.case_id,
                "type": type,
                "accused_id": accused_id,
                "reason": reason,
            },
        )

        return ServiceResult(
            success=True,
            data={
                "case_id": case.case_id,
                "type": type,
                "status": case.status.value,
                "response_deadline_utc": case.response_deadline_utc.isoformat()
                if case.response_deadline_utc else None,
            },
        )

    def submit_adjudication_response(
        self,
        case_id: str,
        accused_id: str,
        text: str,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Submit the accused's response to an adjudication case."""
        if now is None:
            now = datetime.now(timezone.utc)

        # Validate identity: only the accused can respond
        case = self._adjudication_engine.get_case(case_id)
        if case is None:
            return ServiceResult(
                success=False,
                errors=[f"Case not found: {case_id}"],
            )

        if case.accused_id != accused_id:
            return ServiceResult(
                success=False,
                errors=[f"Actor {accused_id} is not the accused in case {case_id}"],
            )

        try:
            self._adjudication_engine.submit_accused_response(case_id, text, now)
            self._rights_enforcer.mark_response_submitted(case_id)
        except ValueError as e:
            return ServiceResult(success=False, errors=[str(e)])

        self._record_actor_lifecycle_event(
            accused_id,
            EventKind.ADJUDICATION_RESPONSE_SUBMITTED,
            {"case_id": case_id},
        )

        return ServiceResult(
            success=True,
            data={"case_id": case_id, "response_submitted": True},
        )

    def form_adjudication_panel(
        self,
        case_id: str,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Form an adjudication panel for a case.

        Checks rights enforcer gate, builds candidates from roster,
        forms panel, emits ADJUDICATION_PANEL_FORMED.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Check rights enforcer gate
        rights_record = self._rights_enforcer.get_record(case_id)
        if rights_record is None:
            return ServiceResult(
                success=False,
                errors=[f"No rights record for case: {case_id}"],
            )

        violations = self._rights_enforcer.validate_panel_formation_allowed(
            rights_record, now
        )
        if violations:
            return ServiceResult(
                success=False,
                errors=[f"Rights violations: {'; '.join(violations)}"],
            )

        # Build candidates from roster
        adj_cfg = self._resolver.adjudication_config()
        min_trust = adj_cfg.get("min_panelist_trust", 0.60)
        candidates = [
            {
                "actor_id": a.actor_id,
                "trust_score": a.trust_score,
                "organization": a.organization,
                "region": a.region,
            }
            for a in self._roster.available_reviewers(min_trust=min_trust)
        ]

        try:
            case = self._adjudication_engine.form_panel(case_id, candidates, now)
        except ValueError as e:
            return ServiceResult(success=False, errors=[str(e)])

        self._record_actor_lifecycle_event(
            case.complainant_id,
            EventKind.ADJUDICATION_PANEL_FORMED,
            {
                "case_id": case_id,
                "panel_ids": case.panel_ids,
                "panel_size": len(case.panel_ids),
            },
        )

        return ServiceResult(
            success=True,
            data={
                "case_id": case_id,
                "panel_ids": case.panel_ids,
                "status": case.status.value,
            },
        )

    def submit_adjudication_vote(
        self,
        case_id: str,
        panelist_id: str,
        verdict: str,
        attestation: str,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Submit a panelist's vote on an adjudication case.

        Records vote, evaluates verdict. If UPHELD, calls apply_penalty().
        """
        if now is None:
            now = datetime.now(timezone.utc)

        try:
            self._adjudication_engine.submit_panel_vote(
                case_id, panelist_id, verdict, attestation
            )
        except ValueError as e:
            return ServiceResult(success=False, errors=[str(e)])

        self._record_actor_lifecycle_event(
            panelist_id,
            EventKind.ADJUDICATION_VOTE_CAST,
            {"case_id": case_id, "verdict": verdict},
        )

        # Evaluate verdict
        final_verdict = self._adjudication_engine.evaluate_verdict(case_id)
        if final_verdict is not None:
            case = self._adjudication_engine.get_case(case_id)
            self._record_actor_lifecycle_event(
                case.accused_id if case else panelist_id,
                EventKind.ADJUDICATION_DECIDED,
                {
                    "case_id": case_id,
                    "verdict": final_verdict.value,
                },
            )

            # If upheld, apply penalty to the accused
            if final_verdict == LegalAdjudicationVerdict.UPHELD and case:
                self.apply_penalty(
                    case.accused_id,
                    ViolationType.COMPLAINT_UPHELD.value,
                    now=now,
                )

        return ServiceResult(
            success=True,
            data={
                "case_id": case_id,
                "voted": True,
                "verdict_reached": final_verdict.value if final_verdict else None,
            },
        )

    def file_adjudication_appeal(
        self,
        case_id: str,
        appellant_id: str,
        reason: str,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """File an appeal against a decided adjudication case."""
        if now is None:
            now = datetime.now(timezone.utc)

        try:
            appeal_case = self._adjudication_engine.file_appeal(
                case_id, appellant_id, reason, now
            )
        except ValueError as e:
            return ServiceResult(success=False, errors=[str(e)])

        # Create rights record for appeal
        self._rights_enforcer.create_rights_record(
            appeal_case.case_id, appeal_case.accused_id, now
        )
        self._rights_enforcer.mark_evidence_disclosed(appeal_case.case_id)

        self._record_actor_lifecycle_event(
            appellant_id,
            EventKind.ADJUDICATION_APPEAL_FILED,
            {
                "original_case_id": case_id,
                "appeal_case_id": appeal_case.case_id,
                "reason": reason,
            },
        )

        return ServiceResult(
            success=True,
            data={
                "appeal_case_id": appeal_case.case_id,
                "original_case_id": case_id,
            },
        )

    def escalate_to_constitutional_court(
        self,
        case_id: str,
        question: str,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Escalate a Tier 2 case to the Constitutional Court (Tier 3).

        Only cases with ESCALATED_TO_COURT verdict can be escalated.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        case = self._adjudication_engine.get_case(case_id)
        if case is None:
            return ServiceResult(
                success=False,
                errors=[f"Case not found: {case_id}"],
            )

        if case.verdict != LegalAdjudicationVerdict.ESCALATED_TO_COURT:
            return ServiceResult(
                success=False,
                errors=[
                    f"Case {case_id} verdict is {case.verdict}, "
                    f"not ESCALATED_TO_COURT"
                ],
            )

        court_case = self._constitutional_court.open_court_case(
            source_adjudication_id=case_id,
            question=question,
            now=now,
        )

        self._record_actor_lifecycle_event(
            case.complainant_id,
            EventKind.CONSTITUTIONAL_COURT_OPENED,
            {
                "court_case_id": court_case.court_case_id,
                "source_case_id": case_id,
                "question": question,
            },
        )

        return ServiceResult(
            success=True,
            data={
                "court_case_id": court_case.court_case_id,
                "source_case_id": case_id,
            },
        )

    def submit_court_vote(
        self,
        court_case_id: str,
        justice_id: str,
        verdict: str,
        attestation: str,
        precedent_note: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Submit a justice's vote on a Constitutional Court case.

        Records vote, evaluates verdict, records precedent.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        try:
            self._constitutional_court.submit_court_vote(
                court_case_id, justice_id, verdict, attestation, precedent_note
            )
        except ValueError as e:
            return ServiceResult(success=False, errors=[str(e)])

        # Evaluate verdict
        court_verdict = self._constitutional_court.evaluate_court_verdict(court_case_id)
        if court_verdict is not None:
            # Record precedent
            self._constitutional_court.record_precedent(court_case_id)

            court_case = self._constitutional_court.get_case(court_case_id)
            self._record_actor_lifecycle_event(
                justice_id,
                EventKind.CONSTITUTIONAL_COURT_DECIDED,
                {
                    "court_case_id": court_case_id,
                    "verdict": court_verdict,
                    "source_case_id": court_case.source_adjudication_id
                    if court_case else None,
                },
            )

        return ServiceResult(
            success=True,
            data={
                "court_case_id": court_case_id,
                "voted": True,
                "verdict_reached": court_verdict,
            },
        )

    # ------------------------------------------------------------------
    # Workflow Orchestration (Phase E-4)
    # ------------------------------------------------------------------

    def create_funded_listing(
        self,
        listing_id: str,
        title: str,
        description: str,
        creator_id: str,
        mission_reward: "Decimal",
        mission_class: MissionClass = MissionClass.DOCUMENTATION_UPDATE,
        domain_type: DomainType = DomainType.OBJECTIVE,
        skill_requirements: list[Any] | None = None,
        domain_tags: list[str] | None = None,
        deadline_days: int | None = None,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Create a funded listing: compliance screen → escrow → listing.

        Orchestrated flow:
        1. Compliance screen (title + description).
        2. Create escrow (mission_reward + employer_creator_fee).
        3. Create listing with escrow link.
        4. Track in workflow orchestrator.
        """
        from decimal import Decimal as D

        if now is None:
            now = datetime.now(timezone.utc)

        # Validate creator
        creator = self._roster.get(creator_id)
        if creator is None:
            return ServiceResult(success=False, errors=[f"Creator not found: {creator_id}"])
        if creator.status in (
            ActorStatus.SUSPENDED,
            ActorStatus.PERMANENTLY_DECOMMISSIONED,
        ):
            return ServiceResult(
                success=False,
                errors=[f"Actor {creator_id} is {creator.status.value} and cannot create listings"],
            )

        wf_cfg = self._resolver.workflow_config()

        # Step 1: Compliance screening
        if wf_cfg.get("require_compliance_screening", True):
            screening = self._compliance_screener.screen_mission(
                title=title, description=description, tags=domain_tags, now=now,
            )
            if screening.verdict == ComplianceVerdict.REJECTED:
                return ServiceResult(
                    success=False,
                    errors=[f"Listing rejected by compliance screening: {screening.reason}"],
                    data={"compliance_verdict": "rejected", "categories": screening.categories_matched},
                )
            compliance_verdict = screening.verdict.value
        else:
            compliance_verdict = "skipped"

        # Step 2: Preflight — check listing doesn't already exist (before creating escrow)
        if listing_id in self._listings:
            return ServiceResult(
                success=False,
                errors=[f"Listing already exists: {listing_id}"],
            )

        # Step 3: Create escrow
        reward = D(str(mission_reward)) if not isinstance(mission_reward, D) else mission_reward
        comm_params = self._resolver.commission_params()
        creator_fee_rate = D(str(comm_params.get("employer_creator_fee_rate", "0.05")))
        employer_fee = (reward * creator_fee_rate).quantize(D("0.01"))
        total_escrow = reward + employer_fee

        escrow_record = self._escrow_manager.create_escrow(
            mission_id=listing_id,  # placeholder — will be updated on allocation
            staker_id=creator_id,
            amount=total_escrow,
            now=now,
        )

        # Step 4: Create listing
        listing_result = self.create_listing(
            listing_id=listing_id,
            title=title,
            description=description,
            creator_id=creator_id,
            skill_requirements=skill_requirements,
            domain_tags=domain_tags,
        )
        if not listing_result.success:
            return listing_result

        # Link escrow and reward to listing
        listing = self._listings[listing_id]
        listing.mission_reward = reward
        listing.escrow_id = escrow_record.escrow_id
        listing.deadline_days = deadline_days or wf_cfg.get("default_deadline_days", 30)

        # Step 5: Create workflow state
        wf = self._workflow_orchestrator.create_workflow(
            listing_id=listing_id,
            creator_id=creator_id,
            mission_reward=reward,
            now=now,
        )
        wf.mission_class = mission_class.value
        wf.domain_type = domain_type.value
        wf.escrow_id = escrow_record.escrow_id
        self._workflow_orchestrator.record_compliance_screening(
            wf.workflow_id, compliance_verdict, now,
        )
        self._workflows[wf.workflow_id] = wf

        # Emit event
        self._record_actor_lifecycle_event(
            creator_id,
            EventKind.WORKFLOW_CREATED,
            {
                "workflow_id": wf.workflow_id,
                "listing_id": listing_id,
                "escrow_id": escrow_record.escrow_id,
                "mission_reward": str(reward),
                "total_escrow": str(total_escrow),
                "compliance_verdict": compliance_verdict,
            },
        )

        # Persist workflow + escrow state (listing already persisted by create_listing)
        self._safe_persist_post_audit()

        return ServiceResult(
            success=True,
            data={
                "workflow_id": wf.workflow_id,
                "listing_id": listing_id,
                "escrow_id": escrow_record.escrow_id,
                "mission_reward": str(reward),
                "total_escrow": str(total_escrow),
                "compliance_verdict": compliance_verdict,
                "status": wf.status.value,
            },
        )

    def fund_and_publish_listing(
        self,
        workflow_id: str,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Lock escrow and publish listing: escrow lock → open → bids.

        Orchestrated flow:
        1. Lock escrow (PENDING → LOCKED).
        2. Open listing (DRAFT → OPEN).
        3. Start accepting bids (OPEN → ACCEPTING_BIDS).
        """
        wf = self._workflow_orchestrator.get_workflow(workflow_id)
        if wf is None:
            return ServiceResult(success=False, errors=[f"Workflow not found: {workflow_id}"])

        if wf.escrow_id is None:
            return ServiceResult(success=False, errors=["No escrow linked to workflow"])

        if now is None:
            now = datetime.now(timezone.utc)

        # Step 1: Lock escrow
        try:
            self._escrow_manager.lock_escrow(wf.escrow_id, now)
        except ValueError as e:
            return ServiceResult(success=False, errors=[str(e)])

        self._workflow_orchestrator.record_escrow_funded(workflow_id, wf.escrow_id)

        # Step 2: Open listing
        open_result = self.open_listing(wf.listing_id)
        if not open_result.success:
            return open_result

        # Step 3: Start accepting bids
        wf_cfg = self._resolver.workflow_config()
        if wf_cfg.get("auto_start_bids_on_publish", True):
            bids_result = self.start_accepting_bids(wf.listing_id)
            if not bids_result.success:
                return bids_result

        self._workflow_orchestrator.record_listing_live(workflow_id)

        # Emit event
        self._record_actor_lifecycle_event(
            wf.creator_id,
            EventKind.ESCROW_WORKFLOW_FUNDED,
            {
                "workflow_id": workflow_id,
                "listing_id": wf.listing_id,
                "escrow_id": wf.escrow_id,
            },
        )

        # Persist escrow lock + workflow progression
        self._safe_persist_post_audit()

        return ServiceResult(
            success=True,
            data={
                "workflow_id": workflow_id,
                "listing_id": wf.listing_id,
                "escrow_id": wf.escrow_id,
                "status": wf.status.value,
            },
        )

    def allocate_worker_workflow(
        self,
        workflow_id: str,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Evaluate bids and allocate worker via workflow.

        Calls existing evaluate_and_allocate() and tracks in workflow.
        """
        wf = self._workflow_orchestrator.get_workflow(workflow_id)
        if wf is None:
            return ServiceResult(success=False, errors=[f"Workflow not found: {workflow_id}"])

        if now is None:
            now = datetime.now(timezone.utc)

        # Parse mission class and domain type
        mc = MissionClass(wf.mission_class) if wf.mission_class else MissionClass.DOCUMENTATION_UPDATE
        dt = DomainType(wf.domain_type) if wf.domain_type else DomainType.OBJECTIVE

        result = self.evaluate_and_allocate(wf.listing_id, mc, dt)
        if not result.success:
            return result

        mission_id = result.data.get("mission_id", "")
        worker_id = result.data.get("selected_worker_id", "")

        # Advance mission: DRAFT → SUBMITTED (workflow skips ASSIGNED —
        # worker allocation happens via market, not mission assignment)
        sub = self._transition_mission(mission_id, MissionState.SUBMITTED)
        if not sub.success:
            return sub

        self._workflow_orchestrator.record_worker_allocated(
            workflow_id, mission_id, worker_id, now,
        )

        # Persist workflow progression
        self._safe_persist_post_audit()

        result.data["workflow_id"] = workflow_id
        result.data["status"] = wf.status.value
        return result

    def submit_work_workflow(
        self,
        workflow_id: str,
        evidence_hashes: list[str],
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Submit work deliverables: evidence → WORK_SUBMITTED transition.

        Adds evidence to the mission and transitions to WORK_SUBMITTED.
        """
        wf = self._workflow_orchestrator.get_workflow(workflow_id)
        if wf is None:
            return ServiceResult(success=False, errors=[f"Workflow not found: {workflow_id}"])

        if wf.mission_id is None:
            return ServiceResult(success=False, errors=["No mission linked to workflow"])

        mission = self._missions.get(wf.mission_id)
        if mission is None:
            return ServiceResult(success=False, errors=[f"Mission not found: {wf.mission_id}"])

        if now is None:
            now = datetime.now(timezone.utc)

        # Add evidence records
        for h in evidence_hashes:
            # Generate deterministic ed25519 signature from hash
            sig_hex = hashlib.sha256(h.encode()).hexdigest() * 2  # 128 hex chars
            ev_result = self.add_evidence(wf.mission_id, h, f"ed25519:{sig_hex[:128]}")
            if not ev_result.success:
                return ev_result

        # Transition mission to WORK_SUBMITTED
        transition_result = self._transition_mission(wf.mission_id, MissionState.WORK_SUBMITTED)
        if not transition_result.success:
            return transition_result

        self._workflow_orchestrator.record_work_submitted(
            workflow_id, evidence_hashes, now,
        )

        # Emit event
        self._record_actor_lifecycle_event(
            wf.worker_id or "unknown",
            EventKind.WORK_SUBMITTED,
            {
                "workflow_id": workflow_id,
                "mission_id": wf.mission_id,
                "evidence_count": len(evidence_hashes),
            },
        )

        # Persist workflow + evidence state
        self._safe_persist_post_audit()

        return ServiceResult(
            success=True,
            data={
                "workflow_id": workflow_id,
                "mission_id": wf.mission_id,
                "evidence_count": len(evidence_hashes),
                "status": wf.status.value,
            },
        )

    def complete_and_pay_workflow(
        self,
        workflow_id: str,
        ledger: Any,
        reserve: Any,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Complete workflow: process payment → release escrow.

        Validates mission is APPROVED, processes payment, releases escrow.
        """
        wf = self._workflow_orchestrator.get_workflow(workflow_id)
        if wf is None:
            return ServiceResult(success=False, errors=[f"Workflow not found: {workflow_id}"])

        if wf.mission_id is None:
            return ServiceResult(success=False, errors=["No mission linked to workflow"])
        if wf.escrow_id is None:
            return ServiceResult(success=False, errors=["No escrow linked to workflow"])

        if now is None:
            now = datetime.now(timezone.utc)

        # Step 1: Process payment
        payment_result = self.process_mission_payment(
            wf.mission_id, wf.mission_reward, ledger, reserve,
        )
        if not payment_result.success:
            return payment_result

        # Step 2: Release escrow (build commission breakdown for validation)
        from decimal import Decimal as D
        from genesis.compensation.engine import CommissionEngine

        engine = CommissionEngine(self._resolver)
        breakdown = engine.compute_commission(
            mission_reward=wf.mission_reward,
            ledger=ledger,
            reserve=reserve,
        )

        try:
            self._escrow_manager.release_escrow(
                wf.escrow_id, breakdown, now,
            )
        except ValueError as e:
            return ServiceResult(success=False, errors=[f"Escrow release failed: {e}"])

        self._workflow_orchestrator.record_completed(workflow_id, now)

        # Persist final workflow + escrow state
        self._safe_persist_post_audit()

        payment_result.data["workflow_id"] = workflow_id
        payment_result.data["status"] = wf.status.value
        payment_result.data["escrow_released"] = True
        return payment_result

    def cancel_workflow(
        self,
        workflow_id: str,
        reason: str = "",
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Cancel workflow: cancel listing → refund escrow.

        Full escrow returned including employer creator fee.
        """
        wf = self._workflow_orchestrator.get_workflow(workflow_id)
        if wf is None:
            return ServiceResult(success=False, errors=[f"Workflow not found: {workflow_id}"])

        if now is None:
            now = datetime.now(timezone.utc)

        # Cancel listing if it exists and is not yet terminal
        listing = self._listings.get(wf.listing_id)
        if listing is not None and not self._listing_sm.is_terminal(listing.state):
            cancel_result = self.cancel_listing(wf.listing_id)
            if not cancel_result.success:
                return cancel_result

        # Refund escrow
        if wf.escrow_id is not None:
            try:
                self._escrow_manager.refund_escrow(wf.escrow_id, now)
            except ValueError:
                pass  # Escrow may already be in terminal state

        self._workflow_orchestrator.record_cancelled(workflow_id, now)

        # Emit event
        self._record_actor_lifecycle_event(
            wf.creator_id,
            EventKind.WORKFLOW_CANCELLED,
            {
                "workflow_id": workflow_id,
                "listing_id": wf.listing_id,
                "reason": reason,
            },
        )

        # Persist cancellation + escrow refund
        self._safe_persist_post_audit()

        return ServiceResult(
            success=True,
            data={
                "workflow_id": workflow_id,
                "listing_id": wf.listing_id,
                "status": wf.status.value,
                "escrow_refunded": True,
            },
        )

    def file_payment_dispute_workflow(
        self,
        workflow_id: str,
        complainant_id: str,
        reason: str,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """File a payment dispute: escrow → DISPUTED, adjudication opened.

        Routes through the Three-Tier Justice system (E-3).
        """
        wf = self._workflow_orchestrator.get_workflow(workflow_id)
        if wf is None:
            return ServiceResult(success=False, errors=[f"Workflow not found: {workflow_id}"])

        if wf.escrow_id is None:
            return ServiceResult(success=False, errors=["No escrow linked to workflow"])

        if now is None:
            now = datetime.now(timezone.utc)

        # Step 1: Dispute escrow
        try:
            self._escrow_manager.dispute_escrow(wf.escrow_id, now)
        except ValueError as e:
            return ServiceResult(success=False, errors=[str(e)])

        # Determine accused (the other party)
        if wf.worker_id is None:
            return ServiceResult(success=False, errors=["No worker allocated — cannot determine accused party"])
        accused_id = wf.worker_id if complainant_id == wf.creator_id else wf.creator_id

        # Step 2: Open adjudication case
        adj_result = self.open_adjudication(
            type=LegalAdjudicationType.PAYMENT_DISPUTE,
            complainant_id=complainant_id,
            accused_id=accused_id,
            reason=reason,
            mission_id=wf.mission_id,
            now=now,
        )
        if not adj_result.success:
            return adj_result

        case_id = adj_result.data.get("case_id", "")
        self._workflow_orchestrator.record_disputed(workflow_id, case_id)

        # Emit event
        self._record_actor_lifecycle_event(
            complainant_id,
            EventKind.PAYMENT_DISPUTE_FILED,
            {
                "workflow_id": workflow_id,
                "escrow_id": wf.escrow_id,
                "case_id": case_id,
                "complainant_id": complainant_id,
                "accused_id": accused_id,
            },
        )

        # Persist dispute state
        self._safe_persist_post_audit()

        return ServiceResult(
            success=True,
            data={
                "workflow_id": workflow_id,
                "case_id": case_id,
                "escrow_id": wf.escrow_id,
                "status": wf.status.value,
            },
        )

    def resolve_payment_dispute_workflow(
        self,
        workflow_id: str,
        release_to_worker: bool,
        ledger: Any = None,
        reserve: Any = None,
        now: Optional[datetime] = None,
    ) -> ServiceResult:
        """Resolve a payment dispute: release or refund escrow.

        If release_to_worker=True, escrow is released to worker.
        If False, escrow is refunded to poster.
        """
        wf = self._workflow_orchestrator.get_workflow(workflow_id)
        if wf is None:
            return ServiceResult(success=False, errors=[f"Workflow not found: {workflow_id}"])

        if wf.escrow_id is None:
            return ServiceResult(success=False, errors=["No escrow linked to workflow"])

        if now is None:
            now = datetime.now(timezone.utc)

        if release_to_worker:
            # Release to worker — need commission breakdown
            if ledger is None or reserve is None:
                return ServiceResult(
                    success=False,
                    errors=["Ledger and reserve required to release escrow to worker"],
                )
            from decimal import Decimal as D
            from genesis.compensation.engine import CommissionEngine

            engine = CommissionEngine(self._resolver)
            breakdown = engine.compute_commission(
                mission_reward=wf.mission_reward,
                ledger=ledger,
                reserve=reserve,
            )
            try:
                self._escrow_manager.release_escrow(wf.escrow_id, breakdown, now)
            except ValueError as e:
                return ServiceResult(success=False, errors=[f"Escrow release failed: {e}"])
        else:
            # Refund to poster
            try:
                self._escrow_manager.refund_escrow(wf.escrow_id, now)
            except ValueError as e:
                return ServiceResult(success=False, errors=[f"Escrow refund failed: {e}"])

        self._workflow_orchestrator.record_dispute_resolved(
            workflow_id, release_to_worker, now,
        )

        # Emit event
        self._record_actor_lifecycle_event(
            "system",
            EventKind.DISPUTE_RESOLVED,
            {
                "workflow_id": workflow_id,
                "escrow_id": wf.escrow_id,
                "released_to_worker": release_to_worker,
                "case_id": wf.dispute_case_id,
            },
        )

        # Persist dispute resolution
        self._safe_persist_post_audit()

        return ServiceResult(
            success=True,
            data={
                "workflow_id": workflow_id,
                "released_to_worker": release_to_worker,
                "status": wf.status.value,
            },
        )

    def get_workflow(self, workflow_id: str) -> Optional[Any]:
        """Retrieve a workflow state by ID."""
        return self._workflow_orchestrator.get_workflow(workflow_id)

    def _count_missions_by_state(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for m in self._missions.values():
            counts[m.state.value] = counts.get(m.state.value, 0) + 1
        return counts
