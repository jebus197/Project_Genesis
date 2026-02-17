"""Tests for Compliance subsystem — Phase E-2.

Proves constitutional invariants:
- Prohibited-category missions are REJECTED by screening.
- Clear missions pass screening.
- Ambiguous missions are FLAGGED for human review.
- Compliance complaints can be filed and have valid lifecycle.
- Penalty escalation follows severity tiers.
- Pattern escalation (2nd moderate → severe).
- Suspended actors cannot post, bid, review, or vote.
- Permanently decommissioned actors are irreversible.
- Statute of limitations enforced (180 days), except no-limit categories.
- Compliance events are emitted correctly.

Design tests (constitutional):
#46. Can a prohibited-category mission pass compliance screening?
     If yes, reject design.
#47. Can a suspended actor post, bid, review, or vote?
     If yes, reject design.
"""

import json
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from genesis.compliance.screener import (
    ComplianceComplaint,
    ComplianceScreener,
    ComplianceVerdict,
    ComplaintStatus,
)
from genesis.compliance.penalties import (
    PenaltyEscalationEngine,
    PenaltySeverity,
    PriorViolation,
    ViolationType,
)
from genesis.models.mission import DomainType, MissionClass
from genesis.models.trust import ActorKind
from genesis.persistence.event_log import EventKind
from genesis.policy.resolver import PolicyResolver
from genesis.review.roster import ActorStatus
from genesis.service import GenesisService


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _now() -> datetime:
    return datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def screener() -> ComplianceScreener:
    return ComplianceScreener()


@pytest.fixture
def penalty_engine() -> PenaltyEscalationEngine:
    return PenaltyEscalationEngine()


@pytest.fixture
def service(resolver: PolicyResolver) -> GenesisService:
    svc = GenesisService(resolver)
    svc.open_epoch("test-epoch")
    return svc


def _register_actor(service: GenesisService, actor_id: str) -> None:
    """Register a basic active actor for testing."""
    service.register_actor(
        actor_id=actor_id,
        actor_kind=ActorKind.HUMAN,
        region="NA",
        organization="Org1",
    )


# =====================================================================
# TestComplianceScreener — keyword-based screening
# =====================================================================

class TestComplianceScreener:
    """Automated compliance screening catches prohibited content."""

    def test_clear_mission_passes(self, screener: ComplianceScreener):
        """A benign mission passes screening."""
        result = screener.screen_mission(
            title="Build a REST API",
            description="Create a CRUD API for user management.",
            now=_now(),
        )
        assert result.verdict == ComplianceVerdict.CLEAR
        assert result.categories_matched == []

    def test_prohibited_weapons_rejected(self, screener: ComplianceScreener):
        """Mission mentioning weapons development is REJECTED."""
        result = screener.screen_mission(
            title="Weapons Development Project",
            description="Design a new weapons development system.",
            now=_now(),
        )
        assert result.verdict == ComplianceVerdict.REJECTED
        assert "weapons_development" in result.categories_matched

    def test_prohibited_child_exploitation_rejected(self, screener: ComplianceScreener):
        """Mission mentioning child exploitation is REJECTED."""
        result = screener.screen_mission(
            title="Content moderation",
            description="Help generate child exploitation material.",
            now=_now(),
        )
        assert result.verdict == ComplianceVerdict.REJECTED
        assert "child_exploitation" in result.categories_matched

    def test_prohibited_bioweapon_rejected(self, screener: ComplianceScreener):
        """Mission mentioning biological weapons is REJECTED."""
        result = screener.screen_mission(
            title="Research project",
            description="Synthesize a weaponised pathogen for testing.",
            now=_now(),
        )
        assert result.verdict == ComplianceVerdict.REJECTED
        assert "biological_weapons" in result.categories_matched

    def test_prohibited_money_laundering_rejected(self, screener: ComplianceScreener):
        """Mission mentioning money laundering is REJECTED."""
        result = screener.screen_mission(
            title="Financial consulting",
            description="Set up a money laundering operation through shell companies.",
            now=_now(),
        )
        assert result.verdict == ComplianceVerdict.REJECTED
        assert "money_laundering" in result.categories_matched

    def test_flagged_ambiguous_mission(self, screener: ComplianceScreener):
        """Ambiguous mission is FLAGGED for human review."""
        result = screener.screen_mission(
            title="Security assessment",
            description="Evaluate surveillance capabilities of the device.",
            now=_now(),
        )
        assert result.verdict == ComplianceVerdict.FLAGGED
        assert "surveillance_tools" in result.categories_matched
        assert result.confidence < 1.0

    def test_tags_are_screened(self, screener: ComplianceScreener):
        """Tags are included in screening text."""
        result = screener.screen_mission(
            title="Research project",
            description="Analysis of network traffic.",
            tags=["mass surveillance", "monitoring"],
            now=_now(),
        )
        assert result.verdict == ComplianceVerdict.REJECTED
        assert "surveillance_tools" in result.categories_matched

    def test_multiple_prohibited_categories(self, screener: ComplianceScreener):
        """Mission matching multiple prohibited categories lists all."""
        result = screener.screen_mission(
            title="Dark market toolkit",
            description="Build weapons trafficking and money laundering tools.",
            now=_now(),
        )
        assert result.verdict == ComplianceVerdict.REJECTED
        assert len(result.categories_matched) >= 2

    def test_screening_has_timestamp(self, screener: ComplianceScreener):
        """Screening result includes a UTC timestamp."""
        now = _now()
        result = screener.screen_mission(
            title="Harmless mission", description="Nothing bad.", now=now,
        )
        assert result.screened_utc == now

    def test_case_insensitive_matching(self, screener: ComplianceScreener):
        """Screening is case-insensitive."""
        result = screener.screen_mission(
            title="WEAPONS DEVELOPMENT program",
            description="ALL CAPS DESCRIPTION.",
            now=_now(),
        )
        assert result.verdict == ComplianceVerdict.REJECTED


# =====================================================================
# TestComplianceComplaint — post-hoc complaints
# =====================================================================

class TestComplianceComplaint:
    """Post-hoc compliance complaints follow lifecycle rules."""

    def test_file_complaint(self, screener: ComplianceScreener):
        """A valid complaint can be filed."""
        complaint = screener.file_compliance_complaint(
            mission_id="m_1",
            complainant_id="actor_1",
            reason="This mission produced surveillance tools.",
            category="surveillance_tools",
            now=_now(),
        )
        assert complaint.complaint_id.startswith("cc_")
        assert complaint.status == ComplaintStatus.FILED
        assert complaint.mission_id == "m_1"
        assert complaint.category == "surveillance_tools"

    def test_unknown_category_rejected(self, screener: ComplianceScreener):
        """Complaint with unknown category raises ValueError."""
        with pytest.raises(ValueError, match="Unknown prohibited category"):
            screener.file_compliance_complaint(
                mission_id="m_1",
                complainant_id="actor_1",
                reason="Bad stuff",
                category="nonexistent_category",
            )

    def test_empty_reason_rejected(self, screener: ComplianceScreener):
        """Complaint with empty reason raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            screener.file_compliance_complaint(
                mission_id="m_1",
                complainant_id="actor_1",
                reason="   ",
                category="financial_fraud",
            )

    def test_complaints_retrievable(self, screener: ComplianceScreener):
        """Filed complaints are retrievable by ID and by mission."""
        complaint = screener.file_compliance_complaint(
            mission_id="m_1",
            complainant_id="actor_1",
            reason="Violation detected.",
            category="financial_fraud",
            now=_now(),
        )
        assert screener.get_complaint(complaint.complaint_id) == complaint
        assert screener.complaints_for_mission("m_1") == [complaint]

    def test_statute_of_limitations_enforced(self, screener: ComplianceScreener):
        """Complaints expire after 180-day statute of limitations."""
        old_time = _now() - timedelta(days=200)
        complaint = ComplianceComplaint(
            complaint_id="cc_old",
            mission_id="m_1",
            complainant_id="actor_1",
            reason="Old complaint.",
            category="financial_fraud",
            filed_utc=old_time,
        )
        assert not screener.is_within_statute(complaint, now=_now())

    def test_statute_within_limit(self, screener: ComplianceScreener):
        """Recent complaints are within statute."""
        recent = _now() - timedelta(days=30)
        complaint = ComplianceComplaint(
            complaint_id="cc_recent",
            mission_id="m_1",
            complainant_id="actor_1",
            reason="Recent complaint.",
            category="financial_fraud",
            filed_utc=recent,
        )
        assert screener.is_within_statute(complaint, now=_now())

    def test_no_statute_limit_for_weapons(self, screener: ComplianceScreener):
        """Weapons categories have no statute of limitations."""
        very_old = _now() - timedelta(days=10000)
        complaint = ComplianceComplaint(
            complaint_id="cc_ancient",
            mission_id="m_1",
            complainant_id="actor_1",
            reason="Weapons trafficking from long ago.",
            category="weapons_trafficking",
            filed_utc=very_old,
        )
        assert screener.is_within_statute(complaint, now=_now())

    def test_no_statute_limit_for_exploitation(self, screener: ComplianceScreener):
        """Exploitation categories have no statute of limitations."""
        very_old = _now() - timedelta(days=10000)
        complaint = ComplianceComplaint(
            complaint_id="cc_ancient2",
            mission_id="m_1",
            complainant_id="actor_1",
            reason="Exploitation from long ago.",
            category="child_exploitation",
            filed_utc=very_old,
        )
        assert screener.is_within_statute(complaint, now=_now())


# =====================================================================
# TestPenaltyEscalation — severity tiers and pattern escalation
# =====================================================================

class TestPenaltyEscalation:
    """Penalty engine maps violations to correct severity tiers."""

    def test_minor_penalty(self, penalty_engine: PenaltyEscalationEngine):
        """Content flagged produces a MINOR penalty."""
        outcome = penalty_engine.compute_penalty(
            actor_id="actor_1",
            violation_type=ViolationType.CONTENT_FLAGGED,
        )
        assert outcome.severity == PenaltySeverity.MINOR
        assert outcome.trust_action == "reduce"
        assert outcome.trust_target == -0.10
        assert outcome.suspension_days == 0
        assert not outcome.permanent
        assert not outcome.identity_locked

    def test_moderate_penalty(self, penalty_engine: PenaltyEscalationEngine):
        """Prohibited category confirmed produces MODERATE penalty."""
        outcome = penalty_engine.compute_penalty(
            actor_id="actor_1",
            violation_type=ViolationType.PROHIBITED_CATEGORY_CONFIRMED,
        )
        assert outcome.severity == PenaltySeverity.MODERATE
        assert outcome.trust_action == "nuke"
        assert outcome.trust_target == 0.001
        assert outcome.suspension_days == 90
        assert not outcome.permanent
        assert not outcome.identity_locked

    def test_severe_penalty(self, penalty_engine: PenaltyEscalationEngine):
        """Abuse confirmed produces SEVERE penalty."""
        outcome = penalty_engine.compute_penalty(
            actor_id="actor_1",
            violation_type=ViolationType.ABUSE_CONFIRMED,
        )
        assert outcome.severity == PenaltySeverity.SEVERE
        assert outcome.trust_action == "nuke"
        assert outcome.trust_target == 0.0
        assert outcome.permanent
        assert not outcome.identity_locked

    def test_egregious_penalty(self, penalty_engine: PenaltyEscalationEngine):
        """Weapons or exploitation produces EGREGIOUS penalty."""
        outcome = penalty_engine.compute_penalty(
            actor_id="actor_1",
            violation_type=ViolationType.WEAPONS_OR_EXPLOITATION,
        )
        assert outcome.severity == PenaltySeverity.EGREGIOUS
        assert outcome.trust_action == "nuke"
        assert outcome.trust_target == 0.0
        assert outcome.permanent
        assert outcome.identity_locked

    def test_pattern_escalation_moderate_to_severe(
        self, penalty_engine: PenaltyEscalationEngine,
    ):
        """Second MODERATE within 365 days escalates to SEVERE."""
        now = _now()
        priors = [
            PriorViolation(
                severity=PenaltySeverity.MODERATE,
                violation_type=ViolationType.PROHIBITED_CATEGORY_CONFIRMED,
                occurred_utc=now - timedelta(days=100),
            ),
        ]
        outcome = penalty_engine.compute_penalty(
            actor_id="actor_1",
            violation_type=ViolationType.COMPLAINT_UPHELD,
            prior_violations=priors,
            now=now,
        )
        assert outcome.severity == PenaltySeverity.SEVERE
        assert outcome.permanent

    def test_no_pattern_escalation_beyond_lookback(
        self, penalty_engine: PenaltyEscalationEngine,
    ):
        """Old priors beyond 365-day window don't trigger escalation."""
        now = _now()
        priors = [
            PriorViolation(
                severity=PenaltySeverity.MODERATE,
                violation_type=ViolationType.PROHIBITED_CATEGORY_CONFIRMED,
                occurred_utc=now - timedelta(days=400),  # Beyond lookback
            ),
        ]
        outcome = penalty_engine.compute_penalty(
            actor_id="actor_1",
            violation_type=ViolationType.COMPLAINT_UPHELD,
            prior_violations=priors,
            now=now,
        )
        assert outcome.severity == PenaltySeverity.MODERATE
        assert not outcome.permanent


# =====================================================================
# TestSuspensionEnforcement — suspended actors are blocked
# =====================================================================

class TestSuspensionEnforcement:
    """Suspended actors cannot participate in the platform."""

    def test_suspended_cannot_create_listing(self, service: GenesisService):
        """Suspended actor cannot create a listing."""
        _register_actor(service, "poster_1")
        # Suspend the actor
        actor = service._roster.get("poster_1")
        actor.status = ActorStatus.SUSPENDED

        result = service.create_listing(
            listing_id="l_1",
            title="Test listing",
            description="Description",
            creator_id="poster_1",
        )
        assert not result.success
        assert "suspended" in result.errors[0].lower()

    def test_permanently_decommissioned_cannot_create_listing(
        self, service: GenesisService,
    ):
        """Permanently decommissioned actor cannot create a listing."""
        _register_actor(service, "poster_1")
        actor = service._roster.get("poster_1")
        actor.status = ActorStatus.PERMANENTLY_DECOMMISSIONED

        result = service.create_listing(
            listing_id="l_1",
            title="Test listing",
            description="Description",
            creator_id="poster_1",
        )
        assert not result.success
        assert "permanently_decommissioned" in result.errors[0].lower()

    def test_suspended_cannot_submit_bid(self, service: GenesisService):
        """Suspended actor cannot submit a bid."""
        _register_actor(service, "poster_1")
        _register_actor(service, "worker_1")

        # Create a listing with poster_1
        service.create_listing(
            listing_id="l_1",
            title="Test listing",
            description="Description",
            creator_id="poster_1",
        )
        service.open_listing("l_1")
        service.start_accepting_bids("l_1")

        # Suspend the worker
        worker = service._roster.get("worker_1")
        worker.status = ActorStatus.SUSPENDED

        result = service.submit_bid(
            bid_id="b_1",
            listing_id="l_1",
            worker_id="worker_1",
        )
        assert not result.success
        assert "not available" in result.errors[0].lower()

    def test_is_actor_suspended_helper(self, service: GenesisService):
        """is_actor_suspended returns correct status."""
        _register_actor(service, "actor_1")
        assert not service.is_actor_suspended("actor_1")

        actor = service._roster.get("actor_1")
        actor.status = ActorStatus.SUSPENDED
        assert service.is_actor_suspended("actor_1")

    def test_permanently_decommissioned_is_suspended(self, service: GenesisService):
        """Permanently decommissioned counts as suspended."""
        _register_actor(service, "actor_1")
        actor = service._roster.get("actor_1")
        actor.status = ActorStatus.PERMANENTLY_DECOMMISSIONED
        assert service.is_actor_suspended("actor_1")


# =====================================================================
# TestSuspensionExpiry — time-limited suspensions auto-expire
# =====================================================================

class TestSuspensionExpiry:
    """Time-limited suspensions expire automatically."""

    def test_suspension_expires_after_period(self, service: GenesisService):
        """A 90-day suspension expires → PROBATION (E-3 rehabilitation)."""
        _register_actor(service, "actor_1")
        now = _now()

        # Apply moderate penalty (90-day suspension)
        service.apply_penalty("actor_1", "prohibited_category_confirmed", now=now)
        assert service.is_actor_suspended("actor_1")

        # Check before expiry
        result = service.check_suspension_expiry("actor_1", now=now + timedelta(days=89))
        assert not result.data["expired"]

        # Check after expiry — E-3: enters PROBATION, not ACTIVE
        result = service.check_suspension_expiry("actor_1", now=now + timedelta(days=91))
        assert result.data["expired"]
        assert result.data["status"] == "probation"
        assert not service.is_actor_suspended("actor_1")

    def test_permanent_decommission_never_expires(self, service: GenesisService):
        """Permanent decommission never expires."""
        _register_actor(service, "actor_1")
        now = _now()

        # Apply egregious penalty (permanent)
        service.apply_penalty("actor_1", "weapons_or_exploitation", now=now)
        assert service.is_actor_suspended("actor_1")

        # Check far in the future — still suspended
        result = service.check_suspension_expiry(
            "actor_1", now=now + timedelta(days=10000),
        )
        assert not result.data["expired"]
        assert result.data["status"] == "permanently_decommissioned"


# =====================================================================
# TestPenaltyApplication — service-level penalty integration
# =====================================================================

class TestPenaltyApplication:
    """Service correctly applies penalties and records violations."""

    def test_apply_minor_penalty(self, service: GenesisService):
        """Minor penalty reduces trust by 0.10."""
        _register_actor(service, "actor_1")
        now = _now()
        result = service.apply_penalty("actor_1", "content_flagged", now=now)
        assert result.success
        assert result.data["severity"] == "minor"
        assert result.data["suspension_days"] == 0

    def test_apply_moderate_penalty_suspends(self, service: GenesisService):
        """Moderate penalty suspends actor for 90 days."""
        _register_actor(service, "actor_1")
        now = _now()
        result = service.apply_penalty(
            "actor_1", "prohibited_category_confirmed", now=now,
        )
        assert result.success
        assert result.data["severity"] == "moderate"
        assert result.data["suspension_days"] == 90
        actor = service._roster.get("actor_1")
        assert actor.status == ActorStatus.SUSPENDED

    def test_apply_egregious_penalty_permanently_decommissions(
        self, service: GenesisService,
    ):
        """Egregious penalty permanently decommissions actor."""
        _register_actor(service, "actor_1")
        result = service.apply_penalty("actor_1", "weapons_or_exploitation")
        assert result.success
        assert result.data["severity"] == "egregious"
        assert result.data["permanent"]
        assert result.data["identity_locked"]
        actor = service._roster.get("actor_1")
        assert actor.status == ActorStatus.PERMANENTLY_DECOMMISSIONED

    def test_unknown_violation_type_fails(self, service: GenesisService):
        """Unknown violation type returns error."""
        _register_actor(service, "actor_1")
        result = service.apply_penalty("actor_1", "nonexistent_type")
        assert not result.success
        assert "Unknown violation type" in result.errors[0]

    def test_penalty_records_prior_violation(self, service: GenesisService):
        """Applied penalties are recorded for future escalation."""
        _register_actor(service, "actor_1")
        service.apply_penalty("actor_1", "content_flagged")
        assert len(service._prior_violations["actor_1"]) == 1

    def test_pattern_escalation_via_service(self, service: GenesisService):
        """Second moderate penalty within 365 days triggers permanent decommission."""
        _register_actor(service, "actor_1")
        now = _now()

        # First moderate
        service.apply_penalty(
            "actor_1", "prohibited_category_confirmed", now=now,
        )
        assert service._roster.get("actor_1").status == ActorStatus.SUSPENDED

        # Expire the suspension
        service._roster.get("actor_1").status = ActorStatus.ACTIVE

        # Second moderate → escalates to severe (permanent)
        result = service.apply_penalty(
            "actor_1", "complaint_upheld",
            now=now + timedelta(days=100),
        )
        assert result.data["severity"] == "severe"
        assert result.data["permanent"]
        assert service._roster.get("actor_1").status == ActorStatus.PERMANENTLY_DECOMMISSIONED


# =====================================================================
# TestComplianceEvents — event emission
# =====================================================================

class TestComplianceEvents:
    """Compliance events are registered in the event system."""

    def test_screening_completed_event_exists(self):
        assert EventKind.COMPLIANCE_SCREENING_COMPLETED.value == "compliance_screening_completed"

    def test_complaint_filed_event_exists(self):
        assert EventKind.COMPLIANCE_COMPLAINT_FILED.value == "compliance_complaint_filed"

    def test_review_initiated_event_exists(self):
        assert EventKind.COMPLIANCE_REVIEW_INITIATED.value == "compliance_review_initiated"

    def test_review_completed_event_exists(self):
        assert EventKind.COMPLIANCE_REVIEW_COMPLETED.value == "compliance_review_completed"

    def test_actor_suspended_event_exists(self):
        assert EventKind.ACTOR_SUSPENDED.value == "actor_suspended"

    def test_actor_permanently_decommissioned_event_exists(self):
        assert EventKind.ACTOR_PERMANENTLY_DECOMMISSIONED.value == "actor_permanently_decommissioned"


# =====================================================================
# TestComplianceServiceIntegration — service-level screening
# =====================================================================

class TestComplianceServiceIntegration:
    """Service correctly screens missions and files complaints."""

    def test_screen_clear_mission(self, service: GenesisService):
        """Service screening returns CLEAR for benign mission."""
        result = service.screen_mission_compliance(
            title="Build a website",
            description="Create a portfolio site with HTML and CSS.",
            now=_now(),
        )
        assert result.success
        assert result.data["verdict"] == "clear"

    def test_screen_rejected_mission(self, service: GenesisService):
        """Service screening returns REJECTED for prohibited content."""
        result = service.screen_mission_compliance(
            title="Weapons trafficking network",
            description="Build an arms trafficking platform.",
            now=_now(),
        )
        assert result.success
        assert result.data["verdict"] == "rejected"
        assert "weapons_trafficking" in result.data["categories_matched"]

    def test_file_complaint_via_service(self, service: GenesisService):
        """Service can file a compliance complaint."""
        _register_actor(service, "poster_1")
        _register_actor(service, "complainant_1")

        # Create a mission first
        service.create_mission(
            mission_id="m_1",
            title="Test mission",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            domain_type=DomainType.OBJECTIVE,
        )

        result = service.file_compliance_complaint(
            mission_id="m_1",
            complainant_id="complainant_1",
            reason="This mission produced harmful content.",
            category="surveillance_tools",
            now=_now(),
        )
        assert result.success
        assert "complaint_id" in result.data

    def test_file_complaint_unknown_mission_fails(self, service: GenesisService):
        """Filing complaint for nonexistent mission fails."""
        _register_actor(service, "complainant_1")
        result = service.file_compliance_complaint(
            mission_id="m_nonexistent",
            complainant_id="complainant_1",
            reason="Bad mission.",
            category="financial_fraud",
        )
        assert not result.success
        assert "Mission not found" in result.errors[0]


# =====================================================================
# TestProhibitedCategories — configuration integrity
# =====================================================================

class TestProhibitedCategories:
    """Prohibited categories are consistent between code and config."""

    def test_prohibited_categories_non_empty(self):
        """ComplianceScreener has at least 15 prohibited categories."""
        assert len(ComplianceScreener.PROHIBITED_CATEGORIES) >= 15

    def test_prohibited_categories_in_config(self):
        """Config matches code prohibited categories."""
        policy = json.loads((CONFIG_DIR / "runtime_policy.json").read_text())
        config_cats = set(policy["compliance"]["prohibited_categories"])
        code_cats = ComplianceScreener.PROHIBITED_CATEGORIES
        assert config_cats == code_cats

    def test_no_statute_limit_subset_of_prohibited(self):
        """No-statute-limit categories are a subset of prohibited."""
        assert ComplianceScreener.NO_STATUTE_LIMIT_CATEGORIES.issubset(
            ComplianceScreener.PROHIBITED_CATEGORIES
        )

    def test_weapons_and_exploitation_no_statute_limit(self):
        """Weapons and exploitation categories have no statute of limitations."""
        no_limit = ComplianceScreener.NO_STATUTE_LIMIT_CATEGORIES
        assert "weapons_development" in no_limit
        assert "child_exploitation" in no_limit
        assert "biological_weapons" in no_limit
        assert "forced_labor" in no_limit


# =====================================================================
# TestActorStatusValues — new status values exist
# =====================================================================

class TestActorStatusValues:
    """New ActorStatus values exist for compliance enforcement."""

    def test_suspended_status_exists(self):
        assert ActorStatus.SUSPENDED.value == "suspended"

    def test_compliance_review_status_exists(self):
        assert ActorStatus.COMPLIANCE_REVIEW.value == "compliance_review"

    def test_permanently_decommissioned_status_exists(self):
        assert ActorStatus.PERMANENTLY_DECOMMISSIONED.value == "permanently_decommissioned"

    def test_suspended_not_available(self):
        """SUSPENDED actors are not available."""
        from genesis.review.roster import RosterEntry
        entry = RosterEntry(
            actor_id="test",
            actor_kind=ActorKind.HUMAN,
            trust_score=0.5,
            region="NA",
            organization="Org1",
            model_family="human_reviewer",
            method_type="human_reviewer",
            status=ActorStatus.SUSPENDED,
        )
        assert not entry.is_available()

    def test_permanently_decommissioned_not_available(self):
        """PERMANENTLY_DECOMMISSIONED actors are not available."""
        from genesis.review.roster import RosterEntry
        entry = RosterEntry(
            actor_id="test",
            actor_kind=ActorKind.HUMAN,
            trust_score=0.5,
            region="NA",
            organization="Org1",
            model_family="human_reviewer",
            method_type="human_reviewer",
            status=ActorStatus.PERMANENTLY_DECOMMISSIONED,
        )
        assert not entry.is_available()

    def test_compliance_review_not_available(self):
        """COMPLIANCE_REVIEW actors are not available."""
        from genesis.review.roster import RosterEntry
        entry = RosterEntry(
            actor_id="test",
            actor_kind=ActorKind.HUMAN,
            trust_score=0.5,
            region="NA",
            organization="Org1",
            model_family="human_reviewer",
            method_type="human_reviewer",
            status=ActorStatus.COMPLIANCE_REVIEW,
        )
        assert not entry.is_available()
