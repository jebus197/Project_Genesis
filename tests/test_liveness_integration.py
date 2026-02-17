"""Tests for voice liveness service integration (Phase D-4).

Proves the full end-to-end flow: start challenge → submit response →
identity verified → mint trust profile. Also tests retry, escalation,
expiry, and the quorum verification alternative path.
"""

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from genesis.models.trust import ActorKind
from genesis.persistence.event_log import EventLog, EventRecord, EventKind
from genesis.persistence.state_store import StateStore
from genesis.policy.resolver import PolicyResolver
from genesis.review.roster import ActorStatus, IdentityVerificationStatus
from genesis.service import GenesisService


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _make_service(event_log=None, state_store=None):
    resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
    return GenesisService(resolver, event_log=event_log, state_store=state_store)


def _setup_actor(service, actor_id="HUMAN-001"):
    """Register a PROVISIONAL human actor and open an epoch."""
    service.open_epoch("test-epoch")
    result = service.register_human(
        actor_id=actor_id, region="EU", organization="Org",
    )
    assert result.success, f"Registration failed: {result.errors}"
    return actor_id


def _setup_active_verifier(service, event_log, actor_id, score=0.75):
    """Register and fully mint a human actor for use as a quorum verifier."""
    result = service.register_human(
        actor_id=actor_id, region="EU", organization="Org",
        status=ActorStatus.ACTIVE, initial_trust=score,
    )
    assert result.success
    # Mark as verified
    service.request_verification(actor_id)
    service.complete_verification(actor_id, method="voice_liveness")
    # Mark as minted
    event = EventRecord.create(
        event_id=f"mission-done-{actor_id}",
        event_kind=EventKind.MISSION_TRANSITION,
        actor_id=actor_id,
        payload={"mission_id": f"M-{actor_id}", "to_state": "approved", "from_state": "submitted"},
    )
    event_log.append(event)
    service.mint_trust_profile(actor_id)


class TestStartLivenessChallenge:
    """Tests for start_liveness_challenge()."""

    def test_start_challenge_returns_words(self) -> None:
        """Starting a challenge should return a list of words."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        actor = _setup_actor(svc)

        svc.request_verification(actor)
        result = svc.start_liveness_challenge(actor)
        assert result.success, f"Failed: {result.errors}"
        assert len(result.data["words"]) == 6  # stage_1_word_count
        assert result.data["stage"] == 1
        assert result.data["state"] == "challenge_issued"
        assert "session_id" in result.data

    def test_start_challenge_requires_pending(self) -> None:
        """Cannot start a challenge if identity is not PENDING."""
        svc = _make_service(event_log=EventLog())
        actor = _setup_actor(svc)

        # Actor is UNVERIFIED, not PENDING
        result = svc.start_liveness_challenge(actor)
        assert not result.success
        assert any("PENDING" in e for e in result.errors)

    def test_start_challenge_unknown_actor(self) -> None:
        svc = _make_service(event_log=EventLog())
        svc.open_epoch("test-epoch")
        result = svc.start_liveness_challenge("GHOST")
        assert not result.success
        assert any("not found" in e for e in result.errors)


class TestSubmitLivenessResponse:
    """Tests for submit_liveness_response()."""

    def test_correct_response_passes_and_verifies(self) -> None:
        """Correct words → PASSED → identity auto-verified."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        actor = _setup_actor(svc)

        svc.request_verification(actor)
        challenge = svc.start_liveness_challenge(actor)
        session_id = challenge.data["session_id"]
        words = challenge.data["words"]

        result = svc.submit_liveness_response(actor, session_id, words)
        assert result.success
        assert result.data["state"] == "passed"
        assert result.data["verification_completed"] is True

        # Identity should now be VERIFIED
        entry = svc.get_actor(actor)
        assert entry.identity_status == IdentityVerificationStatus.VERIFIED

    def test_wrong_response_retries(self) -> None:
        """Wrong words → retry with new challenge."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        actor = _setup_actor(svc)

        svc.request_verification(actor)
        challenge = svc.start_liveness_challenge(actor)
        session_id = challenge.data["session_id"]

        result = svc.submit_liveness_response(actor, session_id, ["wrong"] * 6)
        assert result.success
        assert result.data["state"] == "challenge_issued"
        assert "words" in result.data  # New challenge words provided
        assert len(result.data["words"]) == 6

    def test_exhaust_stage_1_escalates(self) -> None:
        """3 failed attempts on stage 1 → escalates to stage 2 (12 words)."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        actor = _setup_actor(svc)

        svc.request_verification(actor)
        challenge = svc.start_liveness_challenge(actor)
        session_id = challenge.data["session_id"]

        for _ in range(3):
            result = svc.submit_liveness_response(actor, session_id, ["wrong"] * 6)

        assert result.success
        assert result.data["stage"] == 2
        assert len(result.data["words"]) == 12

    def test_exhaust_all_attempts_fails(self) -> None:
        """6 total failures (3 stage 1 + 3 stage 2) → session FAILED."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        actor = _setup_actor(svc)

        svc.request_verification(actor)
        challenge = svc.start_liveness_challenge(actor)
        session_id = challenge.data["session_id"]

        # Stage 1: 3 failures
        for _ in range(3):
            result = svc.submit_liveness_response(actor, session_id, ["wrong"] * 6)

        # Stage 2: 3 failures
        for _ in range(3):
            result = svc.submit_liveness_response(actor, session_id, ["wrong"] * 12)

        assert result.data["state"] == "failed"

    def test_pass_on_stage_2(self) -> None:
        """Fail stage 1, pass stage 2 → verified."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        actor = _setup_actor(svc)

        svc.request_verification(actor)
        challenge = svc.start_liveness_challenge(actor)
        session_id = challenge.data["session_id"]

        # Fail stage 1
        for _ in range(3):
            result = svc.submit_liveness_response(actor, session_id, ["wrong"] * 6)

        # Pass stage 2 with correct words
        words = result.data["words"]
        result = svc.submit_liveness_response(actor, session_id, words)
        assert result.data["state"] == "passed"
        assert result.data["verification_completed"] is True

    def test_expired_session(self) -> None:
        """Submitting after timeout → EXPIRED."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        actor = _setup_actor(svc)
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)

        svc.request_verification(actor)
        challenge = svc.start_liveness_challenge(actor, now=now)
        session_id = challenge.data["session_id"]
        words = challenge.data["words"]

        # Submit after timeout (120 seconds)
        expired = now + timedelta(seconds=121)
        result = svc.submit_liveness_response(actor, session_id, words, now=expired)
        assert result.success
        assert result.data["state"] == "expired"


class TestFullMintLifecycle:
    """End-to-end: register → liveness → mission → mint."""

    def test_full_lifecycle(self) -> None:
        """Complete lifecycle: register, verify via liveness, complete
        mission, mint → ACTIVE with score 1/1000."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        actor = _setup_actor(svc)

        # Step 1: Request verification
        svc.request_verification(actor)

        # Step 2: Pass liveness challenge
        challenge = svc.start_liveness_challenge(actor)
        words = challenge.data["words"]
        result = svc.submit_liveness_response(
            actor, challenge.data["session_id"], words,
        )
        assert result.data["verification_completed"] is True

        # Step 3: Complete a mission (inject event)
        event = EventRecord.create(
            event_id="mission-done-lifecycle",
            event_kind=EventKind.MISSION_TRANSITION,
            actor_id=actor,
            payload={"mission_id": "M-lifecycle", "to_state": "approved", "from_state": "submitted"},
        )
        event_log.append(event)

        # Step 4: Mint trust profile
        result = svc.mint_trust_profile(actor)
        assert result.success, f"Mint failed: {result.errors}"

        entry = svc.get_actor(actor)
        assert entry.status == ActorStatus.ACTIVE

        record = svc._trust_records[actor]
        assert record.score == 0.001
        assert record.trust_minted is True
        assert record.display_score() == 1


class TestQuorumVerificationIntegration:
    """Tests for quorum-based verification via service layer."""

    def test_request_quorum_verification(self) -> None:
        """Can request quorum verification when enough eligible verifiers exist."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        svc.open_epoch("test-epoch")

        # Set up 5 verified, active, minted humans as potential verifiers
        for i in range(5):
            _setup_active_verifier(svc, event_log, f"VERIFIER-{i}", score=0.75)

        # Register the actor to be verified
        svc.register_human(actor_id="SUBJECT-1", region="EU", organization="Org")
        svc.request_verification("SUBJECT-1")

        result = svc.request_quorum_verification("SUBJECT-1")
        assert result.success, f"Failed: {result.errors}"
        assert result.data["quorum_size"] == 3
        assert len(result.data["verifier_ids"]) == 3

    def test_quorum_unanimous_approval_verifies(self) -> None:
        """All verifiers approve → identity verified."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        svc.open_epoch("test-epoch")

        for i in range(5):
            _setup_active_verifier(svc, event_log, f"VERIFIER-{i}", score=0.75)

        svc.register_human(actor_id="SUBJECT-2", region="EU", organization="Org")
        svc.request_verification("SUBJECT-2")

        qr = svc.request_quorum_verification("SUBJECT-2")
        request_id = qr.data["request_id"]
        verifier_ids = qr.data["verifier_ids"]

        # All approve
        for vid in verifier_ids:
            result = svc.submit_quorum_vote(request_id, vid, approved=True)

        assert result.data["outcome"] == "approved"
        assert result.data["verification_completed"] is True

        # Check identity status
        entry = svc.get_actor("SUBJECT-2")
        assert entry.identity_status == IdentityVerificationStatus.VERIFIED

    def test_quorum_rejection(self) -> None:
        """One rejection → verification not completed."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        svc.open_epoch("test-epoch")

        for i in range(5):
            _setup_active_verifier(svc, event_log, f"VERIFIER-{i}", score=0.75)

        svc.register_human(actor_id="SUBJECT-3", region="EU", organization="Org")
        svc.request_verification("SUBJECT-3")

        qr = svc.request_quorum_verification("SUBJECT-3")
        request_id = qr.data["request_id"]
        verifier_ids = qr.data["verifier_ids"]

        # First approves, second rejects
        svc.submit_quorum_vote(request_id, verifier_ids[0], approved=True)
        result = svc.submit_quorum_vote(request_id, verifier_ids[1], approved=False)

        assert result.data["outcome"] == "rejected"

        # Identity still PENDING
        entry = svc.get_actor("SUBJECT-3")
        assert entry.identity_status == IdentityVerificationStatus.PENDING

    def test_quorum_requires_pending_status(self) -> None:
        """Cannot request quorum if actor is not in PENDING status."""
        svc = _make_service(event_log=EventLog())
        actor = _setup_actor(svc)
        # Actor is UNVERIFIED, not PENDING
        result = svc.request_quorum_verification(actor)
        assert not result.success
        assert any("PENDING" in e for e in result.errors)
