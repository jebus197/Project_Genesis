"""Tests for quorum verification safeguards (Phase D-5).

Covers panel diversity, verifier cooldown/workload, blind adjudication,
high-trust gate, vote attestation, recusal, session protocol, abuse
protection, and appeal mechanism.
"""

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from genesis.identity.quorum_verifier import (
    QuorumVerifier,
    QuorumVerificationRequest,
    NukeAppealResult,
    PanelDiversityResult,
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
    """Full D-5 quorum config with optional overrides."""
    cfg = {
        "min_quorum_size": 3,
        "max_quorum_size": 5,
        "verification_timeout_hours": 48,
        "min_verifier_trust": 0.70,
        "geographic_region_required": True,
        "panel_diversity_min_organizations": 2,
        "panel_diversity_min_regions": 1,
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


def _diverse_verifiers() -> list[tuple[str, float, str]]:
    """5 high-trust verifiers from different orgs in EU."""
    return [
        ("V-001", 0.80, "EU"),
        ("V-002", 0.75, "EU"),
        ("V-003", 0.90, "EU"),
        ("V-004", 0.85, "EU"),
        ("V-005", 0.78, "EU"),
    ]


def _diverse_orgs() -> dict[str, str]:
    """Organization mapping for diverse panel selection."""
    return {
        "V-001": "OrgAlpha",
        "V-002": "OrgBeta",
        "V-003": "OrgGamma",
        "V-004": "OrgDelta",
        "V-005": "OrgEpsilon",
    }


def _same_org_verifiers() -> list[tuple[str, float, str]]:
    """3 verifiers from the same org — should fail diversity."""
    return [
        ("V-001", 0.80, "EU"),
        ("V-002", 0.85, "EU"),
        ("V-003", 0.90, "EU"),
    ]


def _same_org_map() -> dict[str, str]:
    return {"V-001": "SameOrg", "V-002": "SameOrg", "V-003": "SameOrg"}


NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


# ===========================================================================
# Panel Diversity Tests
# ===========================================================================

class TestPanelDiversity:
    """Prove panel diversity enforcement."""

    def test_panel_meets_diversity_requirements(self) -> None:
        """Panel with distinct orgs and regions passes diversity check."""
        qv = QuorumVerifier(_safeguard_config())
        panel = [
            ("V-001", "OrgAlpha", "EU"),
            ("V-002", "OrgBeta", "EU"),
            ("V-003", "OrgGamma", "EU"),
        ]
        result = qv.check_panel_diversity(panel)
        assert result.meets_requirements is True
        assert result.distinct_organizations == 3
        assert len(result.violations) == 0

    def test_panel_violates_min_organizations(self) -> None:
        """Panel from a single org violates diversity."""
        qv = QuorumVerifier(_safeguard_config())
        panel = [
            ("V-001", "SameOrg", "EU"),
            ("V-002", "SameOrg", "EU"),
            ("V-003", "SameOrg", "EU"),
        ]
        result = qv.check_panel_diversity(panel)
        assert result.meets_requirements is False
        assert result.distinct_organizations == 1
        assert len(result.violations) >= 1
        assert "organizations" in result.violations[0].lower()

    def test_panel_violates_min_regions(self) -> None:
        """Panel with no regions when min_regions=2 violates diversity."""
        qv = QuorumVerifier(_safeguard_config(panel_diversity_min_regions=2))
        panel = [
            ("V-001", "OrgA", "EU"),
            ("V-002", "OrgB", "EU"),
            ("V-003", "OrgC", "EU"),
        ]
        result = qv.check_panel_diversity(panel)
        assert result.meets_requirements is False
        assert result.distinct_regions == 1

    def test_panel_resampled_on_diversity_failure(self) -> None:
        """With diverse verifiers, selection eventually meets diversity."""
        qv = QuorumVerifier(_safeguard_config())
        verifiers = _diverse_verifiers()
        orgs = _diverse_orgs()
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=verifiers,
            verifier_orgs=orgs,
            now=NOW,
        )
        # Panel should have at least 2 distinct orgs
        panel_orgs = set(request.verifier_organizations.values())
        assert len(panel_orgs) >= 2


# ===========================================================================
# Verifier Cooldown Tests
# ===========================================================================

class TestVerifierCooldown:
    """Prove cooldown and workload enforcement."""

    def test_recently_served_verifier_excluded(self) -> None:
        """Verifier who served recently should be on cooldown."""
        qv = QuorumVerifier(_safeguard_config())
        # Serve on a panel
        qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
            now=NOW,
        )
        # All selected verifiers should now be on cooldown
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
    """Prove blind adjudication generates pseudonyms."""

    def test_request_returns_pseudonym_not_actor_id(self) -> None:
        """Request should have a pseudonym, not the actor's real ID."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="REAL-ACTOR-001",
            region="EU",
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
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
                available_verifiers=_diverse_verifiers(),
                verifier_orgs=_diverse_orgs(),
                now=NOW + timedelta(seconds=i),
            )
            pseudonyms.add(request.applicant_pseudonym)
        assert len(pseudonyms) == 10


# ===========================================================================
# High Trust Gate Tests
# ===========================================================================

class TestHighTrustGate:
    """Prove high-trust gate (>=0.70) for quorum verifiers."""

    def test_verifier_below_070_excluded(self) -> None:
        """Verifiers with trust < 0.70 should be filtered out."""
        qv = QuorumVerifier(_safeguard_config())
        verifiers = [
            ("V-001", 0.65, "EU"),  # below 0.70
            ("V-002", 0.69, "EU"),  # below 0.70
            ("V-003", 0.50, "EU"),  # below 0.70
            ("V-004", 0.80, "EU"),  # above
            ("V-005", 0.75, "EU"),  # above
            ("V-006", 0.90, "EU"),  # above
        ]
        orgs = {"V-004": "OrgA", "V-005": "OrgB", "V-006": "OrgC"}
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=verifiers,
            verifier_orgs=orgs,
            now=NOW,
        )
        assert "V-001" not in request.verifier_ids
        assert "V-002" not in request.verifier_ids
        assert "V-003" not in request.verifier_ids

    def test_verifier_at_070_included(self) -> None:
        """Verifier at exactly 0.70 should be eligible."""
        qv = QuorumVerifier(_safeguard_config())
        verifiers = [
            ("V-001", 0.70, "EU"),
            ("V-002", 0.80, "EU"),
            ("V-003", 0.90, "EU"),
        ]
        orgs = {"V-001": "OrgA", "V-002": "OrgB", "V-003": "OrgC"}
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=verifiers,
            verifier_orgs=orgs,
            now=NOW,
        )
        # All 3 should be selected (exactly 3 eligible, quorum=3)
        assert len(request.verifier_ids) == 3


# ===========================================================================
# Vote Attestation Tests
# ===========================================================================

class TestVoteAttestation:
    """Prove vote attestation enforcement."""

    def test_vote_requires_attestation(self) -> None:
        """Vote without attestation should raise ValueError when required."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
            now=NOW,
        )
        vid = request.verifier_ids[0]
        with pytest.raises(ValueError, match="attestation is required"):
            qv.submit_vote(request.request_id, vid, approved=True)

    def test_vote_without_attestation_accepted_when_not_required(self) -> None:
        """Vote without attestation should work if not required."""
        qv = QuorumVerifier(_safeguard_config(require_vote_attestation=False))
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
            now=NOW,
        )
        vid = request.verifier_ids[0]
        qv.submit_vote(request.request_id, vid, approved=True)
        assert vid in request.votes

    def test_attestation_stored_in_request(self) -> None:
        """Attestation text should be stored in the request."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
            now=NOW,
        )
        vid = request.verifier_ids[0]
        qv.submit_vote(
            request.request_id, vid, approved=True,
            attestation="Confirmed identity via live video",
        )
        assert request.vote_attestations[vid] == "Confirmed identity via live video"


# ===========================================================================
# Recusal Tests
# ===========================================================================

class TestRecusal:
    """Prove recusal mechanism."""

    def test_verifier_can_recuse(self) -> None:
        """Verifier can recuse if panel stays above min quorum."""
        qv = QuorumVerifier(_safeguard_config())
        # Need 4+ verifiers so panel of 3 can survive a recusal with min_quorum=3
        verifiers = _diverse_verifiers()
        orgs = _diverse_orgs()
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=verifiers,
            verifier_orgs=orgs,
            quorum_size=4,
            now=NOW,
        )
        vid = request.verifier_ids[0]
        qv.declare_recusal(request.request_id, vid, "conflict of interest")
        assert vid not in request.verifier_ids
        assert vid in request.recusals
        assert request.quorum_size == 3

    def test_recusal_below_quorum_size_errors(self) -> None:
        """Recusal that would drop below min quorum should raise ValueError."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
            now=NOW,
        )
        # Panel is 3, min_quorum is 3 — can't recuse
        vid = request.verifier_ids[0]
        with pytest.raises(ValueError, match="below minimum quorum"):
            qv.declare_recusal(request.request_id, vid, "reason")

    def test_recusal_reason_recorded(self) -> None:
        """Recusal reason should be stored in the request."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
            quorum_size=4,
            now=NOW,
        )
        vid = request.verifier_ids[0]
        qv.declare_recusal(request.request_id, vid, "I know this person")
        assert request.recusals[vid] == "I know this person"


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
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
            now=NOW,
        )
        assert request.session_max_seconds == 240

    def test_recording_retention_set(self) -> None:
        """Request should have recording_retention_hours=72."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
            now=NOW,
        )
        assert request.recording_retention_hours == 72

    def test_scripted_intro_version_set(self) -> None:
        """Request should reference scripted intro v1."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
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
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
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
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
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
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
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
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
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
    """Prove appeal mechanism."""

    def _make_rejected_request(self, qv):
        """Helper: create and reject a quorum request."""
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
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

        # Need extra verifiers for appeal panel (original panel is excluded)
        extra_verifiers = _diverse_verifiers() + [
            ("V-006", 0.85, "EU"),
            ("V-007", 0.80, "EU"),
            ("V-008", 0.75, "EU"),
        ]
        extra_orgs = {**_diverse_orgs(), "V-006": "OrgF", "V-007": "OrgG", "V-008": "OrgH"}

        appeal = qv.request_appeal(
            original.request_id,
            extra_verifiers,
            verifier_orgs=extra_orgs,
            now=NOW + timedelta(hours=24),
        )
        assert appeal.request_id != original.request_id
        assert appeal.appeal_of == original.request_id
        assert appeal.actor_id == "ACTOR-001"

    def test_appeal_after_window_rejected(self) -> None:
        """Appeal after window should raise ValueError."""
        qv = QuorumVerifier(_safeguard_config(verifier_cooldown_hours=0))
        original = self._make_rejected_request(qv)

        extra_verifiers = _diverse_verifiers() + [
            ("V-006", 0.85, "EU"),
            ("V-007", 0.80, "EU"),
            ("V-008", 0.75, "EU"),
        ]
        extra_orgs = {**_diverse_orgs(), "V-006": "OrgF", "V-007": "OrgG", "V-008": "OrgH"}

        with pytest.raises(ValueError, match="Appeal window has expired"):
            qv.request_appeal(
                original.request_id,
                extra_verifiers,
                verifier_orgs=extra_orgs,
                now=NOW + timedelta(hours=100),  # well past 72h
            )

    def test_appeal_selects_different_panel(self) -> None:
        """Appeal panel should not overlap with original panel."""
        qv = QuorumVerifier(_safeguard_config(verifier_cooldown_hours=0))
        original = self._make_rejected_request(qv)

        # Need more verifiers than original panel to have non-overlapping options
        extra_verifiers = _diverse_verifiers() + [
            ("V-006", 0.85, "EU"),
            ("V-007", 0.80, "EU"),
            ("V-008", 0.75, "EU"),
        ]
        extra_orgs = {**_diverse_orgs(), "V-006": "OrgF", "V-007": "OrgG", "V-008": "OrgH"}

        appeal = qv.request_appeal(
            original.request_id,
            extra_verifiers,
            verifier_orgs=extra_orgs,
            now=NOW + timedelta(hours=24),
        )
        original_panel = set(original.verifier_ids)
        appeal_panel = set(appeal.verifier_ids)
        assert original_panel.isdisjoint(appeal_panel), (
            f"Appeal panel {appeal_panel} overlaps with original {original_panel}"
        )

    def test_appeal_of_approved_request_rejected(self) -> None:
        """Cannot appeal an approved request."""
        qv = QuorumVerifier(_safeguard_config(verifier_cooldown_hours=0))
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
            now=NOW,
        )
        # Approve all votes
        for vid in request.verifier_ids:
            qv.submit_vote(
                request.request_id, vid, approved=True,
                attestation="Confirmed identity",
            )

        extra_verifiers = _diverse_verifiers() + [
            ("V-006", 0.85, "EU"),
            ("V-007", 0.80, "EU"),
            ("V-008", 0.75, "EU"),
        ]
        extra_orgs = {**_diverse_orgs(), "V-006": "OrgF", "V-007": "OrgG", "V-008": "OrgH"}

        with pytest.raises(ValueError, match="Can only appeal rejected"):
            qv.request_appeal(
                request.request_id,
                extra_verifiers,
                verifier_orgs=extra_orgs,
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
        """Register and fully mint a human for use as a quorum verifier."""
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

    def test_quorum_emits_panel_formed_event(self) -> None:
        """request_quorum_verification should emit QUORUM_PANEL_FORMED."""
        event_log = EventLog()
        service = self._make_service(event_log)
        service.open_epoch("test-epoch")

        actor_id = "HUMAN-APPLICANT"
        service.register_human(
            actor_id=actor_id, region="EU", organization="OrgTest",
        )
        service.request_verification(actor_id)

        # Set up 5 verifiers with distinct orgs
        for i in range(5):
            self._setup_active_verifier(
                service, event_log, f"VERIFIER-{i:03d}",
                score=0.80, org=f"Org{i}",
            )

        result = service.request_quorum_verification(actor_id)
        assert result.success, f"Quorum request failed: {result.errors}"

        panel_events = event_log.events(EventKind.QUORUM_PANEL_FORMED)
        assert len(panel_events) >= 1
        assert panel_events[0].payload["request_id"] == result.data["request_id"]

    def test_quorum_emits_vote_cast_events(self) -> None:
        """submit_quorum_vote should emit QUORUM_VOTE_CAST."""
        event_log = EventLog()
        service = self._make_service(event_log)
        service.open_epoch("test-epoch")

        actor_id = "HUMAN-APPLICANT-2"
        service.register_human(
            actor_id=actor_id, region="EU", organization="OrgTest",
        )
        service.request_verification(actor_id)

        for i in range(5):
            self._setup_active_verifier(
                service, event_log, f"VOTER-{i:03d}",
                score=0.80, org=f"Org{i}",
            )

        req_result = service.request_quorum_verification(actor_id)
        assert req_result.success
        request_id = req_result.data["request_id"]
        verifier_ids = req_result.data["verifier_ids"]

        # Cast one vote
        vote_result = service.submit_quorum_vote(
            request_id, verifier_ids[0], approved=True,
            attestation="Confirmed identity via video",
        )
        assert vote_result.success

        vote_events = event_log.events(EventKind.QUORUM_VOTE_CAST)
        assert len(vote_events) >= 1

    def test_quorum_emits_completion_event(self) -> None:
        """Unanimous approval should emit QUORUM_VERIFICATION_COMPLETED."""
        event_log = EventLog()
        service = self._make_service(event_log)
        service.open_epoch("test-epoch")

        actor_id = "HUMAN-APPLICANT-3"
        service.register_human(
            actor_id=actor_id, region="EU", organization="OrgTest",
        )
        service.request_verification(actor_id)

        for i in range(5):
            self._setup_active_verifier(
                service, event_log, f"COMPLETE-{i:03d}",
                score=0.80, org=f"Org{i}",
            )

        req_result = service.request_quorum_verification(actor_id)
        assert req_result.success
        request_id = req_result.data["request_id"]
        verifier_ids = req_result.data["verifier_ids"]

        # All vote yes
        for vid in verifier_ids:
            service.submit_quorum_vote(
                request_id, vid, approved=True,
                attestation="Confirmed via live video",
            )

        completion_events = event_log.events(EventKind.QUORUM_VERIFICATION_COMPLETED)
        assert len(completion_events) >= 1
        assert completion_events[0].payload["outcome"] == "approved"

    def test_minted_required_for_verifiers(self) -> None:
        """Unminted verifiers should not be eligible for quorum panels."""
        event_log = EventLog()
        service = self._make_service(event_log)
        service.open_epoch("test-epoch")

        actor_id = "HUMAN-APPLICANT-4"
        service.register_human(
            actor_id=actor_id, region="EU", organization="OrgTest",
        )
        service.request_verification(actor_id)

        # Register 3 verified but UN-minted humans (don't call mint_trust_profile)
        for i in range(3):
            vid = f"UNMINTED-{i:03d}"
            service.register_human(
                actor_id=vid, region="EU", organization=f"Org{i}",
                status=ActorStatus.ACTIVE, initial_trust=0.80,
            )
            service.request_verification(vid)
            service.complete_verification(vid, method="voice_liveness")
            # NOT minting — no mint_trust_profile() call

        result = service.request_quorum_verification(actor_id)
        # Should fail because no minted verifiers available
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
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
            now=NOW,
        )
        assert request.challenge_phrase is not None
        assert len(request.challenge_phrase.split()) == 6
        assert request.participant_ready_utc is None

    def test_signal_ready_sets_timestamp(self) -> None:
        """signal_participant_ready sets the ready timestamp."""
        qv = QuorumVerifier(_safeguard_config())
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
            now=NOW,
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
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
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
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
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
            available_verifiers=_diverse_verifiers(),
            verifier_orgs=_diverse_orgs(),
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
        """Set up: 5 verifiers, quorum request, confirmed abuse on first verifier.

        IMPORTANT: Abuse reviewers use AREV- prefix, separate from both quorum
        verifiers (VER-) and appeal panelists (registered later).
        """
        service.open_epoch("test-epoch")

        # Register applicant
        service.register_human(
            actor_id="APPLICANT", region="EU", organization="OrgApp",
        )
        service.request_verification("APPLICANT")

        # Register 5 verifiers with distinct orgs (quorum panel pool)
        for i in range(5):
            self._setup_active_verifier(
                service, event_log, f"VER-{i:03d}", score=0.80, org=f"Org{i}",
            )

        # Register 3 abuse reviewers with distinct orgs
        for i in range(3):
            self._setup_active_verifier(
                service, event_log, f"AREV-{i:03d}", score=0.80, org=f"ARevOrg{i}",
            )

        # Request quorum verification
        req_result = service.request_quorum_verification("APPLICANT")
        assert req_result.success, f"Quorum request failed: {req_result.errors}"
        request_id = req_result.data["request_id"]
        verifier_ids = req_result.data["verifier_ids"]

        # File abuse complaint and confirm
        service.file_quorum_abuse_complaint(
            request_id, "APPLICANT", "verifier was abusive",
        )
        # Use first verifier as offender
        offender = verifier_ids[0]
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

        # Register applicant and 5 verifiers
        service.register_human(
            actor_id="VICTIM", region="EU", organization="OrgV",
        )
        service.request_verification("VICTIM")
        for i in range(5):
            self._setup_active_verifier(
                service, event_log, f"CVER-{i:03d}", score=0.80, org=f"COrg{i}",
            )

        req_result = service.request_quorum_verification("VICTIM")
        assert req_result.success
        request_id = req_result.data["request_id"]
        offender = req_result.data["verifier_ids"][0]

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
