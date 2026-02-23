"""Tests for facilitated verification safeguards (Phase D-5 / D-5c).

Covers facilitator assignment (single facilitator for accommodation),
verifier cooldown/workload, blind adjudication, high-trust gate,
facilitator attestation, facilitator decline, session protocol, abuse
protection (3-member panel), appeal mechanism, nuke appeal (5-member panel),
and equivalent standard (design test #86).

Phase D-5c: Corrected confabulated 3-5 member panel for accommodation to
single facilitator model. The 3-member panel is correctly used ONLY for
abuse review, not for accommodation verification.
"""

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from genesis.identity.quorum_verifier import (
    QuorumVerifier,
    QuorumVerificationRequest,
    NukeAppealResult,
    AbuseReviewResult,
    SCRIPTED_INTRO_V1,
    PRE_SESSION_BRIEFING_V1,
    PRE_SESSION_BRIEFING_VERSIONS,
    _generate_challenge_phrase,
)
from genesis.identity.wordlists.en import WORDS as EN_WORDS
from genesis.persistence.event_log import EventLog, EventKind
from genesis.persistence.state_store import StateStore
from genesis.policy.resolver import PolicyResolver
from genesis.service import GenesisService
from genesis.models.trust import ActorKind
from genesis.review.roster import ActorStatus, IdentityVerificationStatus
from genesis.persistence.event_log import EventRecord


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safeguard_config(**overrides) -> dict:
    """Full D-5/D-5c facilitated verification config with optional overrides."""
    cfg = {
        "facilitator_count": 1,
        "prefer_domain_expert": True,
        "domain_expert_timeout_hours": 24,
        "verification_timeout_hours": 48,
        "min_verifier_trust": 0.70,
        "geographic_region_required": True,
        "verifier_cooldown_hours": 168,
        "max_panels_per_verifier_per_month": 10,
        "max_concurrent_panels_per_verifier": 3,
        "blind_adjudication": True,
        "require_vote_attestation": True,
        "appeal_window_hours": 72,
        "session_max_seconds": 240,
        "recording_retention_hours": 72,
        "abuse_trust_nuke_to": 0.001,
        "abuse_review_panel_size": 3,
        "abuse_reviewer_min_trust": 0.70,
        "nuke_appeal_panel_size": 5,
        "nuke_appeal_supermajority": 4,
        "nuke_appeal_window_hours": 72,
        "nuke_appeal_reviewer_min_trust": 0.70,
    }
    cfg.update(overrides)
    return cfg


def _eligible_facilitators() -> list[tuple[str, float, str]]:
    """5 high-trust humans in EU — pool for facilitator selection."""
    return [
        ("V-001", 0.80, "EU"),
        ("V-002", 0.75, "EU"),
        ("V-003", 0.90, "EU"),
        ("V-004", 0.85, "EU"),
        ("V-005", 0.78, "EU"),
    ]


def _facilitator_orgs() -> dict[str, str]:
    """Organization mapping for facilitators."""
    return {
        "V-001": "OrgAlpha",
        "V-002": "OrgBeta",
        "V-003": "OrgGamma",
        "V-004": "OrgDelta",
        "V-005": "OrgEpsilon",
    }


NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


# ===========================================================================
# Facilitator Assignment Tests (Phase D-5c)
# ===========================================================================

class TestFacilitatorAssignment:
    """Prove single facilitator assignment for disability accommodation.

    Phase D-5c correction: accommodation uses a SINGLE facilitator, not a panel.
    The 3-member panel is used only for abuse review (TestAbuseProtection).
    """

    def test_single_facilitator_assigned(self) -> None:
        """Accommodation request must assign exactly 1 facilitator."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        assert request.quorum_size == 1
        assert len(request.verifier_ids) == 1

    def test_domain_expert_preferred(self) -> None:
        """When domain experts available, one is selected as facilitator."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            domain_expert_ids={"V-003"},
            now=NOW,
        )
        assert request.verifier_ids == ["V-003"]

    def test_fallback_to_high_trust_when_no_expert(self) -> None:
        """When no domain expert in pool, falls back to any eligible."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            domain_expert_ids=set(),  # no experts
            now=NOW,
        )
        assert len(request.verifier_ids) == 1
        assert request.verifier_ids[0] in {"V-001", "V-002", "V-003", "V-004", "V-005"}

    def test_region_constraint_enforced(self) -> None:
        """Facilitators from wrong region are excluded."""
        qv = QuorumVerifier(_safeguard_config())
        verifiers = [
            ("V-001", 0.80, "US"),  # wrong region
            ("V-002", 0.85, "EU"),  # correct region
        ]
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=verifiers,
            verifier_orgs={"V-001": "OrgA", "V-002": "OrgB"},
            now=NOW,
        )
        assert request.verifier_ids == ["V-002"]

    def test_no_eligible_facilitator_raises(self) -> None:
        """ValueError if no eligible facilitator after filtering."""
        qv = QuorumVerifier(_safeguard_config())
        verifiers = [("V-001", 0.50, "EU")]  # below trust threshold
        with pytest.raises(ValueError, match="Not enough eligible"):
            qv.request_quorum_verification(
                actor_id="ACTOR-001",
                region="EU",
                available_verifiers=verifiers,
                verifier_orgs={"V-001": "OrgA"},
                now=NOW,
            )


# ===========================================================================
# Verifier Cooldown Tests
# ===========================================================================

class TestVerifierCooldown:
    """Prove cooldown and workload enforcement."""

    def test_recently_served_verifier_excluded(self) -> None:
        """Facilitator who served recently should be on cooldown."""
        qv = QuorumVerifier(_safeguard_config())
        # Serve as facilitator
        qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        # Selected facilitator should now be on cooldown
        for vid in qv._verifier_history:
            assert qv.check_verifier_cooldown(vid, NOW + timedelta(hours=1)) is True

    def test_cooldown_expired_verifier_eligible(self) -> None:
        """Verifier should be eligible after cooldown expires."""
        qv = QuorumVerifier(_safeguard_config(verifier_cooldown_hours=24))
        qv._verifier_history["V-001"] = [NOW]
        # After 25 hours, should be off cooldown
        assert qv.check_verifier_cooldown(
            "V-001", NOW + timedelta(hours=25),
        ) is False

    def test_max_panels_per_month_enforced(self) -> None:
        """Verifier hitting monthly limit should have workload violations."""
        qv = QuorumVerifier(_safeguard_config(
            max_panels_per_verifier_per_month=2,
            verifier_cooldown_hours=0,  # disable cooldown for this test
        ))
        # Add 2 panels in the last month
        qv._verifier_history["V-001"] = [
            NOW - timedelta(days=5),
            NOW - timedelta(days=10),
        ]
        violations = qv.check_verifier_workload("V-001", NOW)
        assert len(violations) >= 1
        assert "month" in violations[0].lower()

    def test_max_concurrent_panels_enforced(self) -> None:
        """Verifier hitting concurrent limit should have violations."""
        qv = QuorumVerifier(_safeguard_config(
            max_concurrent_panels_per_verifier=2,
            verifier_cooldown_hours=0,
        ))
        # Add 2 active panels (within timeout_hours=48)
        qv._verifier_history["V-001"] = [
            NOW - timedelta(hours=10),
            NOW - timedelta(hours=20),
        ]
        violations = qv.check_verifier_workload("V-001", NOW)
        assert len(violations) >= 1
        assert "concurrent" in violations[0].lower()


# ===========================================================================
# Blind Adjudication Tests
# ===========================================================================

class TestBlindAdjudication:
    """Prove facilitator sees pseudonym only (blind identity)."""

    def test_request_returns_pseudonym_not_actor_id(self) -> None:
        """Facilitator should see a pseudonym, not the actor's real ID."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="REAL-ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        assert request.applicant_pseudonym != "REAL-ACTOR-001"
        assert request.applicant_pseudonym.startswith("participant-")

    def test_pseudonym_unique_per_request(self) -> None:
        """Each request should get a unique pseudonym."""
        qv = QuorumVerifier(_safeguard_config(
            verifier_cooldown_hours=0,
            max_panels_per_verifier_per_month=1000,
            max_concurrent_panels_per_verifier=1000,
        ))
        pseudonyms = set()
        for i in range(10):
            request = qv.request_quorum_verification(
                actor_id=f"ACTOR-{i:03d}",
                region="EU",
                available_verifiers=_eligible_facilitators(),
                verifier_orgs=_facilitator_orgs(),
                now=NOW + timedelta(seconds=i),
            )
            pseudonyms.add(request.applicant_pseudonym)
        assert len(pseudonyms) == 10


# ===========================================================================
# High Trust Gate Tests
# ===========================================================================

class TestHighTrustGate:
    """Prove high-trust gate (>=0.70) for facilitators."""

    def test_verifier_below_070_excluded(self) -> None:
        """Facilitators with trust < 0.70 should be filtered out."""
        qv = QuorumVerifier(_safeguard_config())
        verifiers = [
            ("V-001", 0.65, "EU"),  # below 0.70
            ("V-002", 0.69, "EU"),  # below 0.70
            ("V-003", 0.50, "EU"),  # below 0.70
            ("V-004", 0.80, "EU"),  # above
        ]
        orgs = {"V-004": "OrgA"}
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=verifiers,
            verifier_orgs=orgs,
            now=NOW,
        )
        assert request.verifier_ids == ["V-004"]

    def test_verifier_at_070_included(self) -> None:
        """Facilitator at exactly 0.70 should be eligible."""
        qv = QuorumVerifier(_safeguard_config())
        verifiers = [
            ("V-001", 0.70, "EU"),
        ]
        orgs = {"V-001": "OrgA"}
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=verifiers,
            verifier_orgs=orgs,
            now=NOW,
        )
        assert len(request.verifier_ids) == 1
        assert request.verifier_ids[0] == "V-001"


# ===========================================================================
# Vote Attestation Tests
# ===========================================================================

class TestFacilitatorAttestation:
    """Prove facilitator attestation enforcement."""

    def test_attestation_requires_written_statement(self) -> None:
        """Attestation without written statement should raise when required."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        vid = request.verifier_ids[0]
        with pytest.raises(ValueError, match="attestation is required"):
            qv.submit_vote(request.request_id, vid, approved=True)

    def test_attestation_accepted_when_not_required(self) -> None:
        """Attestation without written statement should work if not required."""
        qv = QuorumVerifier(_safeguard_config(require_vote_attestation=False))
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        vid = request.verifier_ids[0]
        qv.submit_vote(request.request_id, vid, approved=True)
        assert vid in request.votes

    def test_attestation_stored_in_request(self) -> None:
        """Written attestation should be stored in the request."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        vid = request.verifier_ids[0]
        qv.submit_vote(
            request.request_id, vid, approved=True,
            attestation="Confirmed identity via live session",
        )
        assert request.vote_attestations[vid] == "Confirmed identity via live session"

    def test_single_attestation_determines_result(self) -> None:
        """One facilitator attestation immediately determines the outcome."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        vid = request.verifier_ids[0]
        qv.submit_vote(
            request.request_id, vid, approved=True,
            attestation="Confirmed identity",
        )
        result = qv.check_result(request.request_id, now=NOW)
        assert result is True  # single attestation = immediate approval


# ===========================================================================
# Recusal Tests
# ===========================================================================

class TestFacilitatorDecline:
    """Prove facilitator can decline assignment (recusal).

    In the single-facilitator model, a decline leaves the request with
    no active facilitator. The service layer must assign a replacement.
    """

    def test_facilitator_can_decline(self) -> None:
        """Facilitator can decline — request left with no active facilitator."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        vid = request.verifier_ids[0]
        qv.declare_recusal(request.request_id, vid, "conflict of interest")
        assert vid not in request.verifier_ids
        assert vid in request.recusals
        assert request.quorum_size == 0  # no active facilitator

    def test_decline_reason_recorded(self) -> None:
        """Decline reason should be stored in the request."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        vid = request.verifier_ids[0]
        qv.declare_recusal(request.request_id, vid, "I know this person")
        assert request.recusals[vid] == "I know this person"

    def test_non_assigned_facilitator_cannot_decline(self) -> None:
        """A verifier not assigned to the request cannot decline."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        with pytest.raises(ValueError, match="not assigned"):
            qv.declare_recusal(request.request_id, "NONEXISTENT", "reason")


# ===========================================================================
# Session Protocol Tests
# ===========================================================================

class TestSessionProtocol:
    """Prove session metadata is set correctly."""

    def test_session_max_seconds_set(self) -> None:
        """Request should have session_max_seconds=240 (4 min)."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        assert request.session_max_seconds == 240

    def test_recording_retention_set(self) -> None:
        """Request should have recording_retention_hours=72."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        assert request.recording_retention_hours == 72

    def test_scripted_intro_version_set(self) -> None:
        """Request should reference scripted intro v1."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        assert request.scripted_intro_version == "v1"
        intro = qv.get_scripted_intro("v1")
        assert "verified community member" in intro
        assert "72 hours" in intro
        assert "file a report" in intro


# ===========================================================================
# Abuse Protection Tests
# ===========================================================================

class TestAbuseProtection:
    """Prove abuse complaint and review mechanism."""

    def test_file_complaint_preserves_recording(self) -> None:
        """Filing a complaint should record it in the request."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        qv.file_abuse_complaint(
            request.request_id, "ACTOR-001", "Verifier behaved inappropriately",
        )
        assert "ACTOR-001" in request.abuse_complaints
        assert "inappropriately" in request.abuse_complaints["ACTOR-001"]

    def test_abuse_review_majority_confirms(self) -> None:
        """Majority of review panel confirming -> abuse confirmed."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        qv.file_abuse_complaint(request.request_id, "ACTOR-001", "bad behavior")

        result = qv.review_abuse_complaint(
            request.request_id,
            review_panel=["R-001", "R-002", "R-003"],
            votes={"R-001": True, "R-002": True, "R-003": False},
        )
        assert result.confirmed is True
        assert result.trust_action_taken is True

    def test_abuse_confirmed_trust_nuked_to_0001(self) -> None:
        """Confirmed abuse should result in trust_action_taken=True.

        Actual trust nuking happens in the service layer; here we verify
        the result signals it.
        """
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        qv.file_abuse_complaint(request.request_id, "ACTOR-001", "abuse")

        result = qv.review_abuse_complaint(
            request.request_id,
            review_panel=["R-001", "R-002", "R-003"],
            votes={"R-001": True, "R-002": True, "R-003": True},
        )
        assert result.confirmed is True
        assert result.trust_action_taken is True
        assert qv._abuse_trust_nuke == 0.001

    def test_abuse_review_requires_min_panel(self) -> None:
        """Review panel must have at least abuse_review_panel_size members."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        with pytest.raises(ValueError, match="at least 3"):
            qv.review_abuse_complaint(
                request.request_id,
                review_panel=["R-001", "R-002"],
                votes={"R-001": True, "R-002": True},
            )


# ===========================================================================
# Appeal Tests
# ===========================================================================

class TestAppeal:
    """Prove appeal mechanism — assigns a DIFFERENT single facilitator."""

    def _make_rejected_request(self, qv):
        """Helper: create and reject a facilitated verification request."""
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        vid = request.verifier_ids[0]
        qv.submit_vote(
            request.request_id, vid, approved=False,
            attestation="Could not confirm identity",
        )
        return request

    def test_appeal_within_window_creates_new_request(self) -> None:
        """Appeal within window should create a new request."""
        qv = QuorumVerifier(_safeguard_config(verifier_cooldown_hours=0))
        original = self._make_rejected_request(qv)

        appeal = qv.request_appeal(
            original.request_id,
            _eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW + timedelta(hours=24),
        )
        assert appeal.request_id != original.request_id
        assert appeal.appeal_of == original.request_id
        assert appeal.actor_id == "ACTOR-001"
        assert len(appeal.verifier_ids) == 1  # single facilitator

    def test_appeal_after_window_rejected(self) -> None:
        """Appeal after window should raise ValueError."""
        qv = QuorumVerifier(_safeguard_config(verifier_cooldown_hours=0))
        original = self._make_rejected_request(qv)

        with pytest.raises(ValueError, match="Appeal window has expired"):
            qv.request_appeal(
                original.request_id,
                _eligible_facilitators(),
                verifier_orgs=_facilitator_orgs(),
                now=NOW + timedelta(hours=100),  # well past 72h
            )

    def test_appeal_selects_different_facilitator(self) -> None:
        """Appeal facilitator should not be the same as original facilitator."""
        qv = QuorumVerifier(_safeguard_config(verifier_cooldown_hours=0))
        original = self._make_rejected_request(qv)

        appeal = qv.request_appeal(
            original.request_id,
            _eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW + timedelta(hours=24),
        )
        original_facilitator = set(original.verifier_ids)
        appeal_facilitator = set(appeal.verifier_ids)
        assert original_facilitator.isdisjoint(appeal_facilitator), (
            f"Appeal facilitator {appeal_facilitator} same as original {original_facilitator}"
        )

    def test_appeal_of_approved_request_rejected(self) -> None:
        """Cannot appeal an approved request."""
        qv = QuorumVerifier(_safeguard_config(verifier_cooldown_hours=0))
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        # Facilitator approves
        vid = request.verifier_ids[0]
        qv.submit_vote(
            request.request_id, vid, approved=True,
            attestation="Confirmed identity",
        )

        with pytest.raises(ValueError, match="Can only appeal rejected"):
            qv.request_appeal(
                request.request_id,
                _eligible_facilitators(),
                verifier_orgs=_facilitator_orgs(),
                now=NOW + timedelta(hours=1),
            )


# ===========================================================================
# Service Integration Tests
# ===========================================================================

class TestServiceIntegration:
    """Prove service layer emits events and enforces minted check."""

    @staticmethod
    def _make_service(event_log=None):
        resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
        return GenesisService(resolver, event_log=event_log)

    @staticmethod
    def _setup_active_verifier(service, event_log, actor_id, score=0.80, org="Org"):
        """Register and fully mint a human for use as a facilitator."""
        result = service.register_human(
            actor_id=actor_id, region="EU", organization=org,
            status=ActorStatus.ACTIVE, initial_trust=score,
        )
        assert result.success, f"Registration failed: {result.errors}"
        service.request_verification(actor_id)
        service.complete_verification(actor_id, method="voice_liveness")
        # Add a completed mission event (gate 3 for minting)
        event = EventRecord.create(
            event_id=f"mission-done-{actor_id}",
            event_kind=EventKind.MISSION_TRANSITION,
            actor_id=actor_id,
            payload={
                "mission_id": f"M-{actor_id}",
                "to_state": "approved",
                "from_state": "submitted",
            },
        )
        event_log.append(event)
        mint_result = service.mint_trust_profile(actor_id)
        assert mint_result.success, f"Minting failed for {actor_id}: {mint_result.errors}"

    def test_facilitated_emits_panel_formed_event(self) -> None:
        """request_quorum_verification should emit QUORUM_PANEL_FORMED."""
        event_log = EventLog()
        service = self._make_service(event_log)
        service.open_epoch("test-epoch")

        actor_id = "HUMAN-APPLICANT"
        service.register_human(
            actor_id=actor_id, region="EU", organization="OrgTest",
        )
        service.request_verification(actor_id)

        # Set up 2 facilitator candidates
        for i in range(2):
            self._setup_active_verifier(
                service, event_log, f"VERIFIER-{i:03d}",
                score=0.80, org=f"Org{i}",
            )

        result = service.request_quorum_verification(actor_id)
        assert result.success, f"Facilitated request failed: {result.errors}"
        assert result.data["facilitator_count"] == 1

        panel_events = event_log.events(EventKind.QUORUM_PANEL_FORMED)
        assert len(panel_events) >= 1
        assert panel_events[0].payload["request_id"] == result.data["request_id"]

    def test_facilitated_emits_vote_cast_events(self) -> None:
        """submit_quorum_vote should emit QUORUM_VOTE_CAST."""
        event_log = EventLog()
        service = self._make_service(event_log)
        service.open_epoch("test-epoch")

        actor_id = "HUMAN-APPLICANT-2"
        service.register_human(
            actor_id=actor_id, region="EU", organization="OrgTest",
        )
        service.request_verification(actor_id)

        for i in range(2):
            self._setup_active_verifier(
                service, event_log, f"VOTER-{i:03d}",
                score=0.80, org=f"Org{i}",
            )

        req_result = service.request_quorum_verification(actor_id)
        assert req_result.success
        request_id = req_result.data["request_id"]
        facilitator_ids = req_result.data["facilitator_ids"]

        # Facilitator attests
        vote_result = service.submit_quorum_vote(
            request_id, facilitator_ids[0], approved=True,
            attestation="Confirmed identity via live session",
        )
        assert vote_result.success

        vote_events = event_log.events(EventKind.QUORUM_VOTE_CAST)
        assert len(vote_events) >= 1

    def test_facilitated_emits_completion_event(self) -> None:
        """Facilitator approval should emit QUORUM_VERIFICATION_COMPLETED."""
        event_log = EventLog()
        service = self._make_service(event_log)
        service.open_epoch("test-epoch")

        actor_id = "HUMAN-APPLICANT-3"
        service.register_human(
            actor_id=actor_id, region="EU", organization="OrgTest",
        )
        service.request_verification(actor_id)

        for i in range(2):
            self._setup_active_verifier(
                service, event_log, f"COMPLETE-{i:03d}",
                score=0.80, org=f"Org{i}",
            )

        req_result = service.request_quorum_verification(actor_id)
        assert req_result.success
        request_id = req_result.data["request_id"]
        facilitator_ids = req_result.data["facilitator_ids"]

        # Single facilitator approves — immediate completion
        service.submit_quorum_vote(
            request_id, facilitator_ids[0], approved=True,
            attestation="Confirmed via live session",
        )

        completion_events = event_log.events(EventKind.QUORUM_VERIFICATION_COMPLETED)
        assert len(completion_events) >= 1
        assert completion_events[0].payload["outcome"] == "approved"

    def test_minted_required_for_facilitators(self) -> None:
        """Unminted humans should not be eligible as facilitators."""
        event_log = EventLog()
        service = self._make_service(event_log)
        service.open_epoch("test-epoch")

        actor_id = "HUMAN-APPLICANT-4"
        service.register_human(
            actor_id=actor_id, region="EU", organization="OrgTest",
        )
        service.request_verification(actor_id)

        # Register 2 verified but UN-minted humans
        for i in range(2):
            vid = f"UNMINTED-{i:03d}"
            service.register_human(
                actor_id=vid, region="EU", organization=f"Org{i}",
                status=ActorStatus.ACTIVE, initial_trust=0.80,
            )
            service.request_verification(vid)
            service.complete_verification(vid, method="voice_liveness")
            # NOT minting — no mint_trust_profile() call

        result = service.request_quorum_verification(actor_id)
        # Should fail because no minted facilitators available
        assert result.success is False
        assert any("Not enough" in e for e in result.errors)


# ===========================================================================
# Pre-Session Preparation Tests (Phase D-5b)
# ===========================================================================

class TestPreSessionPreparation:
    """Prove pre-session preparation: briefing, challenge phrase, ready signal."""

    def test_briefing_constant_contains_key_info(self) -> None:
        """Pre-session briefing must mention key elements."""
        assert "UNLIMITED preparation time" in PRE_SESSION_BRIEFING_V1
        assert "challenge phrase" in PRE_SESSION_BRIEFING_V1.lower()
        assert "proof-of-interaction" in PRE_SESSION_BRIEFING_V1
        assert "When you are ready" in PRE_SESSION_BRIEFING_V1
        assert "v1" in PRE_SESSION_BRIEFING_VERSIONS

    def test_request_has_challenge_phrase_and_no_ready_timestamp(self) -> None:
        """New request must have challenge_phrase set, but no ready timestamp."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001", region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(), now=NOW,
        )
        assert request.challenge_phrase is not None
        assert len(request.challenge_phrase.split()) == 6
        assert request.participant_ready_utc is None

    def test_signal_ready_sets_timestamp(self) -> None:
        """signal_participant_ready sets the ready timestamp."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001", region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(), now=NOW,
        )
        ready_time = NOW + timedelta(minutes=15)
        qv.signal_participant_ready(request.request_id, now=ready_time)
        assert request.participant_ready_utc == ready_time

        # Cannot signal twice
        with pytest.raises(ValueError, match="already signalled ready"):
            qv.signal_participant_ready(request.request_id, now=ready_time)

    def test_session_timer_starts_from_ready_not_created(self) -> None:
        """Session expiry should count from participant_ready_utc, not created_utc."""
        qv = QuorumVerifier(_safeguard_config(session_max_seconds=120))
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001", region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        # 10 minutes of prep time — should NOT affect session timer
        ready_time = NOW + timedelta(minutes=10)
        qv.signal_participant_ready(request.request_id, now=ready_time)

        # Before ready: is_session_expired would have returned None
        # 60 seconds after ready: not expired
        assert qv.is_session_expired(
            request.request_id, now=ready_time + timedelta(seconds=60),
        ) is False

        # 121 seconds after ready: expired (session_max_seconds=120)
        assert qv.is_session_expired(
            request.request_id, now=ready_time + timedelta(seconds=121),
        ) is True

    def test_challenge_phrase_is_valid_bip39_words(self) -> None:
        """Challenge phrase must be 6 words, all from BIP39 wordlist."""
        phrase = _generate_challenge_phrase()
        words = phrase.split()
        assert len(words) == 6
        en_word_set = set(EN_WORDS)
        for word in words:
            assert word in en_word_set, f"{word} not in BIP39 wordlist"

        # Each invocation should produce different phrases (probabilistic)
        phrases = {_generate_challenge_phrase() for _ in range(20)}
        assert len(phrases) >= 15  # extremely unlikely to have many collisions


# ===========================================================================
# Nuke Appeal Tests (Phase D-5b)
# ===========================================================================

class TestNukeAppeal:
    """Prove trust-nuke appeal: 5-panel, 4/5 supermajority, one-shot."""

    def _make_abuse_confirmed_request(self, qv, *, now=NOW):
        """Helper: create request, file complaint, confirm abuse."""
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=now,
        )
        qv.file_abuse_complaint(request.request_id, "ACTOR-001", "bad behavior")
        qv.review_abuse_complaint(
            request.request_id,
            review_panel=["R-001", "R-002", "R-003"],
            votes={"R-001": True, "R-002": True, "R-003": True},
            now=now,
        )
        return request

    def test_nuke_appeal_within_window_succeeds(self) -> None:
        """Appeal within 72h window should be accepted."""
        qv = QuorumVerifier(_safeguard_config())
        request = self._make_abuse_confirmed_request(qv)

        appeal_time = NOW + timedelta(hours=24)
        result = qv.appeal_trust_nuke(
            request.request_id,
            appellant_verifier_id="V-001",
            appeal_panel=["AP-1", "AP-2", "AP-3", "AP-4", "AP-5"],
            votes={"AP-1": True, "AP-2": True, "AP-3": True, "AP-4": True, "AP-5": True},
            now=appeal_time,
        )
        assert result.overturned is True
        assert result.trust_restored is True

    def test_nuke_appeal_after_window_rejected(self) -> None:
        """Appeal after 72h window should raise ValueError."""
        qv = QuorumVerifier(_safeguard_config())
        request = self._make_abuse_confirmed_request(qv)

        with pytest.raises(ValueError, match="Nuke appeal window has expired"):
            qv.appeal_trust_nuke(
                request.request_id,
                appellant_verifier_id="V-001",
                appeal_panel=["AP-1", "AP-2", "AP-3", "AP-4", "AP-5"],
                votes={"AP-1": True, "AP-2": True, "AP-3": True, "AP-4": True, "AP-5": True},
                now=NOW + timedelta(hours=100),
            )

    def test_nuke_appeal_4_of_5_overturns(self) -> None:
        """4/5 supermajority should overturn the nuke."""
        qv = QuorumVerifier(_safeguard_config())
        request = self._make_abuse_confirmed_request(qv)

        result = qv.appeal_trust_nuke(
            request.request_id,
            appellant_verifier_id="V-001",
            appeal_panel=["AP-1", "AP-2", "AP-3", "AP-4", "AP-5"],
            votes={"AP-1": True, "AP-2": True, "AP-3": True, "AP-4": True, "AP-5": False},
            now=NOW + timedelta(hours=24),
        )
        assert result.overturned is True
        assert result.trust_restored is True

    def test_nuke_appeal_3_of_5_upholds(self) -> None:
        """3/5 should NOT overturn (need 4/5 supermajority)."""
        qv = QuorumVerifier(_safeguard_config())
        request = self._make_abuse_confirmed_request(qv)

        result = qv.appeal_trust_nuke(
            request.request_id,
            appellant_verifier_id="V-001",
            appeal_panel=["AP-1", "AP-2", "AP-3", "AP-4", "AP-5"],
            votes={"AP-1": True, "AP-2": True, "AP-3": True, "AP-4": False, "AP-5": False},
            now=NOW + timedelta(hours=24),
        )
        assert result.overturned is False
        assert result.trust_restored is False
        assert result.restored_score is None

    def test_nuke_appeal_no_overlap_with_original_panel(self) -> None:
        """Appeal panel must not include members from original abuse panel."""
        qv = QuorumVerifier(_safeguard_config())
        request = self._make_abuse_confirmed_request(qv)

        # "R-001" was on original abuse review panel
        with pytest.raises(ValueError, match="must not overlap"):
            qv.appeal_trust_nuke(
                request.request_id,
                appellant_verifier_id="V-001",
                appeal_panel=["R-001", "AP-2", "AP-3", "AP-4", "AP-5"],
                votes={"R-001": True, "AP-2": True, "AP-3": True, "AP-4": True, "AP-5": True},
                now=NOW + timedelta(hours=24),
            )

    def test_nuke_appeal_one_shot_only(self) -> None:
        """Only one nuke appeal allowed — second attempt raises ValueError."""
        qv = QuorumVerifier(_safeguard_config())
        request = self._make_abuse_confirmed_request(qv)

        # First appeal (fails — 3/5)
        qv.appeal_trust_nuke(
            request.request_id,
            appellant_verifier_id="V-001",
            appeal_panel=["AP-1", "AP-2", "AP-3", "AP-4", "AP-5"],
            votes={"AP-1": True, "AP-2": True, "AP-3": True, "AP-4": False, "AP-5": False},
            now=NOW + timedelta(hours=24),
        )

        # Second attempt
        with pytest.raises(ValueError, match="one appeal only"):
            qv.appeal_trust_nuke(
                request.request_id,
                appellant_verifier_id="V-001",
                appeal_panel=["AP-6", "AP-7", "AP-8", "AP-9", "AP-10"],
                votes={"AP-6": True, "AP-7": True, "AP-8": True, "AP-9": True, "AP-10": True},
                now=NOW + timedelta(hours=25),
            )

    def test_pre_nuke_score_stored_and_restorable(self) -> None:
        """pre_nuke_trust_score should be stored on abuse confirmation."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        qv.file_abuse_complaint(request.request_id, "ACTOR-001", "abuse")

        # Simulate pre-nuke score being set (normally done by service layer)
        request.pre_nuke_trust_score = 0.85

        qv.review_abuse_complaint(
            request.request_id,
            review_panel=["R-001", "R-002", "R-003"],
            votes={"R-001": True, "R-002": True, "R-003": True},
            now=NOW,
        )

        # Appeal should restore to pre-nuke score
        result = qv.appeal_trust_nuke(
            request.request_id,
            appellant_verifier_id="V-001",
            appeal_panel=["AP-1", "AP-2", "AP-3", "AP-4", "AP-5"],
            votes={"AP-1": True, "AP-2": True, "AP-3": True, "AP-4": True, "AP-5": True},
            now=NOW + timedelta(hours=24),
        )
        assert result.overturned is True
        assert result.restored_score == 0.85


# ===========================================================================
# Nuke Appeal Service Integration Tests (Phase D-5b)
# ===========================================================================

class TestNukeAppealServiceIntegration:
    """Prove service-layer nuke appeal: trust restored, events emitted."""

    @staticmethod
    def _make_service(event_log=None):
        resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
        return GenesisService(resolver, event_log=event_log)

    @staticmethod
    def _setup_active_verifier(service, event_log, actor_id, score=0.80, org="Org"):
        """Register and fully mint a human for use as a quorum verifier."""
        result = service.register_human(
            actor_id=actor_id, region="EU", organization=org,
            status=ActorStatus.ACTIVE, initial_trust=score,
        )
        assert result.success, f"Registration failed: {result.errors}"
        service.request_verification(actor_id)
        service.complete_verification(actor_id, method="voice_liveness")
        event = EventRecord.create(
            event_id=f"mission-done-{actor_id}",
            event_kind=EventKind.MISSION_TRANSITION,
            actor_id=actor_id,
            payload={
                "mission_id": f"M-{actor_id}",
                "to_state": "approved",
                "from_state": "submitted",
            },
        )
        event_log.append(event)
        mint_result = service.mint_trust_profile(actor_id)
        assert mint_result.success, f"Minting failed for {actor_id}: {mint_result.errors}"

    def _setup_abuse_scenario(self, service, event_log):
        """Set up: facilitator pool, request, confirmed abuse on facilitator.

        IMPORTANT: Abuse reviewers use AREV- prefix, separate from both
        facilitators (VER-) and appeal panelists (registered later).
        """
        service.open_epoch("test-epoch")

        # Register applicant
        service.register_human(
            actor_id="APPLICANT", region="EU", organization="OrgApp",
        )
        service.request_verification("APPLICANT")

        # Register 2 facilitator candidates with distinct orgs
        for i in range(2):
            self._setup_active_verifier(
                service, event_log, f"VER-{i:03d}", score=0.80, org=f"Org{i}",
            )

        # Register 3 abuse reviewers with distinct orgs
        for i in range(3):
            self._setup_active_verifier(
                service, event_log, f"AREV-{i:03d}", score=0.80, org=f"ARevOrg{i}",
            )

        # Request facilitated verification (single facilitator)
        req_result = service.request_quorum_verification("APPLICANT")
        assert req_result.success, f"Facilitated request failed: {req_result.errors}"
        request_id = req_result.data["request_id"]
        facilitator_ids = req_result.data["facilitator_ids"]

        # File abuse complaint and confirm
        service.file_quorum_abuse_complaint(
            request_id, "APPLICANT", "facilitator was abusive",
        )
        # Use facilitator as offender
        offender = facilitator_ids[0]
        # Abuse reviewers — distinct from both quorum panel and future appeal panel
        abuse_result = service.review_quorum_abuse(
            request_id,
            review_panel_ids=["AREV-000", "AREV-001", "AREV-002"],
            votes={"AREV-000": True, "AREV-001": True, "AREV-002": True},
            offending_verifier_id=offender,
        )
        assert abuse_result.success
        assert abuse_result.data["confirmed"] is True

        return request_id, offender

    def test_nuke_appeal_restores_trust_on_overturn(self) -> None:
        """Overturned nuke appeal should restore verifier's trust score."""
        event_log = EventLog()
        service = self._make_service(event_log)
        request_id, offender = self._setup_abuse_scenario(service, event_log)

        # Offender's trust should be nuked to 0.001
        trust_rec = service._trust_records[offender]
        assert trust_rec.score == pytest.approx(0.001)

        # Register 5 fresh appeal panel members (no overlap with abuse panel)
        for i in range(5):
            self._setup_active_verifier(
                service, event_log, f"NAP-{i:03d}", score=0.80, org=f"NApOrg{i}",
            )
        appeal_panel = [f"NAP-{i:03d}" for i in range(5)]
        votes = {pid: True for pid in appeal_panel}

        result = service.appeal_reviewer_trust_nuke(
            request_id, offender, appeal_panel, votes,
        )
        assert result.success, f"Appeal failed: {result.errors}"
        assert result.data["overturned"] is True
        assert result.data["trust_restored"] is True

        # Trust should be restored
        assert trust_rec.score > 0.001

    def test_nuke_appeal_emits_events(self) -> None:
        """Nuke appeal should emit FILED and RESOLVED events."""
        event_log = EventLog()
        service = self._make_service(event_log)
        request_id, offender = self._setup_abuse_scenario(service, event_log)

        # Register 5 fresh appeal panelists
        for i in range(5):
            self._setup_active_verifier(
                service, event_log, f"EAP-{i:03d}", score=0.80, org=f"EApOrg{i}",
            )
        appeal_panel = [f"EAP-{i:03d}" for i in range(5)]
        votes = {pid: True for pid in appeal_panel}

        service.appeal_reviewer_trust_nuke(
            request_id, offender, appeal_panel, votes,
        )

        filed_events = event_log.events(EventKind.QUORUM_NUKE_APPEAL_FILED)
        assert len(filed_events) >= 1
        assert filed_events[-1].payload["appellant_id"] == offender

        resolved_events = event_log.events(EventKind.QUORUM_NUKE_APPEAL_RESOLVED)
        assert len(resolved_events) >= 1
        assert resolved_events[-1].payload["overturned"] is True

    def test_complainant_trust_unaffected(self) -> None:
        """Complainant's trust should never be affected by nuke appeal."""
        event_log = EventLog()
        service = self._make_service(event_log)

        service.open_epoch("test-epoch")

        # Complainant: a minted verifier
        self._setup_active_verifier(
            service, event_log, "COMPLAINANT", score=0.75, org="CompOrg",
        )
        complainant_trust_before = service._trust_records["COMPLAINANT"].score

        # Register applicant and 2 facilitator candidates
        service.register_human(
            actor_id="VICTIM", region="EU", organization="OrgV",
        )
        service.request_verification("VICTIM")
        for i in range(2):
            self._setup_active_verifier(
                service, event_log, f"CVER-{i:03d}", score=0.80, org=f"COrg{i}",
            )

        req_result = service.request_quorum_verification("VICTIM")
        assert req_result.success
        request_id = req_result.data["request_id"]
        offender = req_result.data["facilitator_ids"][0]

        # Complainant files abuse complaint
        service.file_quorum_abuse_complaint(
            request_id, "COMPLAINANT", "abusive behavior",
        )
        # Confirm abuse (use 3 fresh reviewers)
        for i in range(5, 8):
            self._setup_active_verifier(
                service, event_log, f"CREV-{i:03d}", score=0.80, org=f"CRevOrg{i}",
            )
        service.review_quorum_abuse(
            request_id,
            review_panel_ids=["CREV-005", "CREV-006", "CREV-007"],
            votes={"CREV-005": True, "CREV-006": True, "CREV-007": True},
            offending_verifier_id=offender,
        )

        # Appeal overturns nuke
        for i in range(8, 13):
            self._setup_active_verifier(
                service, event_log, f"CAPP-{i:03d}", score=0.80, org=f"CAppOrg{i}",
            )
        appeal_panel = [f"CAPP-{i:03d}" for i in range(8, 13)]
        votes = {pid: True for pid in appeal_panel}
        service.appeal_reviewer_trust_nuke(
            request_id, offender, appeal_panel, votes,
        )

        # Complainant trust should be unchanged
        complainant_trust_after = service._trust_records["COMPLAINANT"].score
        assert complainant_trust_after == complainant_trust_before


# ===========================================================================
# Equivalent Standard Tests — Design Test #86 (Phase D-5c)
# ===========================================================================

class TestEquivalentStandard:
    """Design test #86: accommodation path must NOT be harder than voice path.

    Voice liveness path: 1 actor reads 6 words → 1 automated check → result.
    Accommodation path: 1 actor + 1 facilitator → 1 attestation → result.

    If the accommodation path requires MORE humans, MORE votes, or a
    HARDER standard (e.g. unanimity among multiple), it is discriminatory.
    """

    def test_accommodation_requires_single_facilitator(self) -> None:
        """Accommodation must require exactly 1 human facilitator."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        assert request.quorum_size == 1, (
            f"Accommodation requires {request.quorum_size} humans — "
            f"voice path requires 0 (automated). Must be 1 for equivalence."
        )
        assert len(request.verifier_ids) == 1

    def test_single_approval_completes_verification(self) -> None:
        """A single facilitator's approval must immediately complete verification."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_eligible_facilitators(),
            verifier_orgs=_facilitator_orgs(),
            now=NOW,
        )
        vid = request.verifier_ids[0]
        qv.submit_vote(
            request.request_id, vid, approved=True,
            attestation="Identity confirmed",
        )
        result = qv.check_result(request.request_id, now=NOW)
        assert result is True, (
            "Single facilitator approval did not immediately complete "
            "verification — accommodation path is harder than voice path"
        )

    def test_config_facilitator_count_is_one(self) -> None:
        """Runtime config must specify facilitator_count=1."""
        import json
        config_path = CONFIG_DIR / "runtime_policy.json"
        policy = json.loads(config_path.read_text())
        qv_config = policy["quorum_verification"]
        assert qv_config["facilitator_count"] == 1, (
            f"facilitator_count is {qv_config['facilitator_count']}, not 1 — "
            f"accommodation would require multiple humans"
        )

    def test_no_unanimity_requirement_in_config(self) -> None:
        """Config must NOT contain 'unanimous_required' (single facilitator, irrelevant)."""
        import json
        config_path = CONFIG_DIR / "runtime_policy.json"
        policy = json.loads(config_path.read_text())
        qv_config = policy["quorum_verification"]
        assert "unanimous_required" not in qv_config, (
            "Config still contains 'unanimous_required' — confabulated panel model"
        )

    def test_no_panel_diversity_in_config(self) -> None:
        """Config must NOT contain panel diversity params (single facilitator)."""
        import json
        config_path = CONFIG_DIR / "runtime_policy.json"
        policy = json.loads(config_path.read_text())
        qv_config = policy["quorum_verification"]
        for key in ("panel_diversity_min_organizations", "panel_diversity_min_regions",
                     "min_quorum_size", "max_quorum_size"):
            assert key not in qv_config, (
                f"Config still contains '{key}' — confabulated panel model"
            )
