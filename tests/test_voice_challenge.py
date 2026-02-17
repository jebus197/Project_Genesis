"""Tests for voice liveness challenge generator and session lifecycle (Phase D-2).

Covers challenge generation, nonce anti-replay, expiry detection,
and the full session state machine including stage escalation.
"""

import pytest
from datetime import datetime, timedelta, timezone

from genesis.identity.challenge import ChallengeGenerator, LivenessChallenge
from genesis.identity.voice_verifier import VoiceVerifier
from genesis.identity.session import SessionManager, SessionState, LivenessSession
from genesis.identity.wordlists.en import WORDS as EN_WORDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_generator_config() -> dict:
    return {
        "stage_1_word_count": 6,
        "stage_2_word_count": 12,
        "session_timeout_seconds": 120,
        "supported_languages": ["en"],
    }


def _default_verifier_config() -> dict:
    return {
        "word_match_threshold": 0.85,
        "naturalness_threshold": 0.70,
    }


def _default_session_config() -> dict:
    return {
        "max_attempts_per_stage": 3,
    }


def _make_session_manager(
    gen_config=None,
    ver_config=None,
    sess_config=None,
) -> SessionManager:
    gen = ChallengeGenerator(gen_config or _default_generator_config())
    ver = VoiceVerifier(ver_config or _default_verifier_config())
    return SessionManager(gen, ver, sess_config or _default_session_config())


# ===========================================================================
# Challenge Generator Tests
# ===========================================================================

class TestChallengeGenerator:
    """Prove challenge generation, word counts, nonce replay, and expiry."""

    # ------------------------------------------------------------------
    # 1. Stage 1 generates correct word count
    # ------------------------------------------------------------------

    def test_stage_1_word_count(self) -> None:
        """Stage 1 challenge should have 6 words."""
        gen = ChallengeGenerator(_default_generator_config())
        challenge = gen.generate(language="en", stage=1)
        assert len(challenge.words) == 6

    # ------------------------------------------------------------------
    # 2. Stage 2 generates correct word count
    # ------------------------------------------------------------------

    def test_stage_2_word_count(self) -> None:
        """Stage 2 challenge should have 12 words."""
        gen = ChallengeGenerator(_default_generator_config())
        challenge = gen.generate(language="en", stage=2)
        assert len(challenge.words) == 12

    # ------------------------------------------------------------------
    # 3. No duplicate words in a challenge
    # ------------------------------------------------------------------

    def test_no_duplicate_words(self) -> None:
        """All words in a challenge should be unique."""
        gen = ChallengeGenerator(_default_generator_config())
        for _ in range(50):
            challenge = gen.generate(language="en", stage=2)
            assert len(set(challenge.words)) == len(challenge.words)

    # ------------------------------------------------------------------
    # 4. All words come from the word list
    # ------------------------------------------------------------------

    def test_words_from_wordlist(self) -> None:
        """Every word in the challenge should exist in EN_WORDS."""
        gen = ChallengeGenerator(_default_generator_config())
        word_set = set(EN_WORDS)
        for _ in range(20):
            challenge = gen.generate(language="en", stage=1)
            for w in challenge.words:
                assert w in word_set, f"Word '{w}' not in word list"

    # ------------------------------------------------------------------
    # 5. Nonce anti-replay: first use succeeds
    # ------------------------------------------------------------------

    def test_nonce_first_use_succeeds(self) -> None:
        """First nonce validation should succeed."""
        gen = ChallengeGenerator(_default_generator_config())
        challenge = gen.generate(language="en", stage=1)
        assert gen.validate_nonce(challenge.challenge_id, challenge.nonce) is True

    # ------------------------------------------------------------------
    # 6. Nonce anti-replay: second use fails
    # ------------------------------------------------------------------

    def test_nonce_replay_fails(self) -> None:
        """Second nonce validation (replay) should fail."""
        gen = ChallengeGenerator(_default_generator_config())
        challenge = gen.generate(language="en", stage=1)
        gen.validate_nonce(challenge.challenge_id, challenge.nonce)
        assert gen.validate_nonce(challenge.challenge_id, challenge.nonce) is False

    # ------------------------------------------------------------------
    # 7. Nonce with wrong challenge_id fails
    # ------------------------------------------------------------------

    def test_nonce_wrong_challenge_id(self) -> None:
        """Nonce validation with unknown challenge_id should fail."""
        gen = ChallengeGenerator(_default_generator_config())
        challenge = gen.generate(language="en", stage=1)
        assert gen.validate_nonce("fake-id", challenge.nonce) is False

    # ------------------------------------------------------------------
    # 8. Nonce with wrong nonce value fails
    # ------------------------------------------------------------------

    def test_nonce_wrong_value(self) -> None:
        """Nonce validation with incorrect nonce should fail."""
        gen = ChallengeGenerator(_default_generator_config())
        challenge = gen.generate(language="en", stage=1)
        assert gen.validate_nonce(challenge.challenge_id, "wrong-nonce") is False

    # ------------------------------------------------------------------
    # 9. Challenge expires after timeout
    # ------------------------------------------------------------------

    def test_challenge_expires_after_timeout(self) -> None:
        """Challenge should be expired after session_timeout_seconds."""
        gen = ChallengeGenerator(_default_generator_config())
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        challenge = gen.generate(language="en", stage=1, now=now)

        # Not expired just before timeout
        before_expiry = now + timedelta(seconds=119)
        assert gen.is_expired(challenge, now=before_expiry) is False

        # Expired at exact timeout
        at_expiry = now + timedelta(seconds=120)
        assert gen.is_expired(challenge, now=at_expiry) is True

        # Expired well after timeout
        after_expiry = now + timedelta(seconds=300)
        assert gen.is_expired(challenge, now=after_expiry) is True

    # ------------------------------------------------------------------
    # 10. Unsupported language raises ValueError
    # ------------------------------------------------------------------

    def test_unsupported_language(self) -> None:
        """Unsupported language should raise ValueError."""
        gen = ChallengeGenerator(_default_generator_config())
        with pytest.raises(ValueError, match="Unsupported language"):
            gen.generate(language="zz", stage=1)

    # ------------------------------------------------------------------
    # 11. Invalid stage raises ValueError
    # ------------------------------------------------------------------

    def test_invalid_stage(self) -> None:
        """Stage other than 1 or 2 should raise ValueError."""
        gen = ChallengeGenerator(_default_generator_config())
        with pytest.raises(ValueError, match="Stage must be 1 or 2"):
            gen.generate(language="en", stage=3)

    # ------------------------------------------------------------------
    # 12. Challenge is frozen (immutable)
    # ------------------------------------------------------------------

    def test_challenge_is_frozen(self) -> None:
        """LivenessChallenge should be immutable (frozen dataclass)."""
        gen = ChallengeGenerator(_default_generator_config())
        challenge = gen.generate(language="en", stage=1)
        with pytest.raises(AttributeError):
            challenge.stage = 2  # type: ignore[misc]

    # ------------------------------------------------------------------
    # 13. Each challenge gets a unique ID and nonce
    # ------------------------------------------------------------------

    def test_unique_ids_and_nonces(self) -> None:
        """Every challenge should have a unique challenge_id and nonce."""
        gen = ChallengeGenerator(_default_generator_config())
        challenges = [gen.generate(language="en", stage=1) for _ in range(50)]
        ids = [c.challenge_id for c in challenges]
        nonces = [c.nonce for c in challenges]
        assert len(set(ids)) == 50
        assert len(set(nonces)) == 50


# ===========================================================================
# Session Lifecycle Tests
# ===========================================================================

class TestSessionLifecycle:
    """Prove session state machine: start, pass, fail, escalation, expiry."""

    # ------------------------------------------------------------------
    # 14. Happy path: stage 1 pass
    # ------------------------------------------------------------------

    def test_happy_path_stage_1_pass(self) -> None:
        """Actor speaks all words correctly on first attempt -> PASSED."""
        mgr = _make_session_manager()
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        session = mgr.start_session("ACTOR-001", now=now)

        assert session.state == SessionState.CHALLENGE_ISSUED
        assert session.current_stage == 1

        # Speak words perfectly
        spoken = list(session.challenge.words)
        session = mgr.submit_response(
            session.session_id, spoken, now=now + timedelta(seconds=10),
        )
        assert session.state == SessionState.PASSED

    # ------------------------------------------------------------------
    # 15. Fail stage 1, retry within attempts
    # ------------------------------------------------------------------

    def test_fail_stage_1_retry(self) -> None:
        """Failed attempt stays on stage 1 if attempts < max."""
        mgr = _make_session_manager()
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        session = mgr.start_session("ACTOR-002", now=now)

        # Speak wrong words
        session = mgr.submit_response(
            session.session_id, ["wrong"] * 6, now=now + timedelta(seconds=5),
        )
        assert session.state == SessionState.CHALLENGE_ISSUED
        assert session.current_stage == 1
        assert session.attempts_this_stage == 1

    # ------------------------------------------------------------------
    # 16. Exhaust stage 1 attempts -> escalate to stage 2
    # ------------------------------------------------------------------

    def test_escalate_to_stage_2(self) -> None:
        """After max failed attempts on stage 1, escalate to stage 2."""
        mgr = _make_session_manager()
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        session = mgr.start_session("ACTOR-003", now=now)

        # Fail 3 times on stage 1
        for i in range(3):
            session = mgr.submit_response(
                session.session_id,
                ["wrong"] * 6,
                now=now + timedelta(seconds=5 + i),
            )

        assert session.current_stage == 2
        assert session.attempts_this_stage == 0
        assert session.state == SessionState.CHALLENGE_ISSUED
        # Stage 2 should have 12 words
        assert len(session.challenge.words) == 12

    # ------------------------------------------------------------------
    # 17. Exhaust both stages -> FAILED
    # ------------------------------------------------------------------

    def test_exhaust_all_attempts_failed(self) -> None:
        """Fail both stages completely -> session FAILED."""
        mgr = _make_session_manager()
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        session = mgr.start_session("ACTOR-004", now=now)

        # Fail stage 1: 3 attempts
        for i in range(3):
            session = mgr.submit_response(
                session.session_id,
                ["wrong"] * 6,
                now=now + timedelta(seconds=5 + i),
            )

        assert session.current_stage == 2

        # Fail stage 2: 3 attempts
        for i in range(3):
            session = mgr.submit_response(
                session.session_id,
                ["wrong"] * 12,
                now=now + timedelta(seconds=15 + i),
            )

        assert session.state == SessionState.FAILED

    # ------------------------------------------------------------------
    # 18. Session expiry detection
    # ------------------------------------------------------------------

    def test_session_expiry(self) -> None:
        """Challenge expires after timeout -> session EXPIRED."""
        mgr = _make_session_manager()
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        session = mgr.start_session("ACTOR-005", now=now)

        # Not expired yet
        assert mgr.check_expiry(
            session.session_id,
            now=now + timedelta(seconds=60),
        ) is False

        # Expired
        assert mgr.check_expiry(
            session.session_id,
            now=now + timedelta(seconds=121),
        ) is True

        assert session.state == SessionState.EXPIRED

    # ------------------------------------------------------------------
    # 19. Submit response after expiry raises ValueError
    # ------------------------------------------------------------------

    def test_submit_after_expiry(self) -> None:
        """Submitting response on expired session sets EXPIRED state."""
        mgr = _make_session_manager()
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        session = mgr.start_session("ACTOR-006", now=now)

        # Submit after expiry
        session = mgr.submit_response(
            session.session_id,
            list(session.challenge.words),
            now=now + timedelta(seconds=200),
        )
        assert session.state == SessionState.EXPIRED

    # ------------------------------------------------------------------
    # 20. Pass on stage 2 after stage 1 escalation
    # ------------------------------------------------------------------

    def test_pass_stage_2_after_escalation(self) -> None:
        """Escalate to stage 2, then pass on first stage-2 attempt."""
        mgr = _make_session_manager()
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        session = mgr.start_session("ACTOR-007", now=now)

        # Exhaust stage 1
        for i in range(3):
            session = mgr.submit_response(
                session.session_id,
                ["wrong"] * 6,
                now=now + timedelta(seconds=5 + i),
            )

        assert session.current_stage == 2

        # Pass stage 2
        spoken = list(session.challenge.words)
        session = mgr.submit_response(
            session.session_id,
            spoken,
            now=now + timedelta(seconds=20),
        )
        assert session.state == SessionState.PASSED

    # ------------------------------------------------------------------
    # 21. Unknown session_id raises KeyError
    # ------------------------------------------------------------------

    def test_unknown_session_raises(self) -> None:
        """Operations on unknown session ID should raise KeyError."""
        mgr = _make_session_manager()
        with pytest.raises(KeyError):
            mgr.submit_response("fake-session-id", ["hello"])
        with pytest.raises(KeyError):
            mgr.check_expiry("fake-session-id")

    # ------------------------------------------------------------------
    # 22. Submit on PASSED session raises ValueError
    # ------------------------------------------------------------------

    def test_submit_on_passed_session(self) -> None:
        """Cannot submit response on already-passed session."""
        mgr = _make_session_manager()
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        session = mgr.start_session("ACTOR-008", now=now)

        spoken = list(session.challenge.words)
        session = mgr.submit_response(
            session.session_id, spoken, now=now + timedelta(seconds=5),
        )
        assert session.state == SessionState.PASSED

        with pytest.raises(ValueError, match="Cannot submit response"):
            mgr.submit_response(
                session.session_id, spoken, now=now + timedelta(seconds=10),
            )
