"""Voice liveness session lifecycle management (Phase D-2).

Orchestrates the multi-stage challenge flow:
  Stage 1 (6 words)  -- if failed after max attempts, escalates to →
  Stage 2 (12 words) -- if failed after max attempts → session FAILED.

Sessions expire if the underlying challenge times out.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from genesis.identity.challenge import ChallengeGenerator, LivenessChallenge
from genesis.identity.voice_verifier import VoiceVerifier


# ---------------------------------------------------------------------------
# Session state machine
# ---------------------------------------------------------------------------

class SessionState(str, enum.Enum):
    PENDING = "pending"
    CHALLENGE_ISSUED = "challenge_issued"
    RESPONSE_SUBMITTED = "response_submitted"
    PASSED = "passed"
    FAILED = "failed"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Session data
# ---------------------------------------------------------------------------

@dataclass
class LivenessSession:
    """Mutable session tracking a single actor's liveness flow."""

    session_id: str
    actor_id: str
    state: SessionState
    current_stage: int                          # 1 or 2
    attempts_this_stage: int
    challenge: Optional[LivenessChallenge]
    created_utc: datetime
    max_attempts_per_stage: int                 # from config (default 3)
    last_result: Optional[object] = None        # last VerificationResult


# ---------------------------------------------------------------------------
# Session manager
# ---------------------------------------------------------------------------

class SessionManager:
    """Drives the liveness session lifecycle.

    Parameters (via *config* dict):
        max_attempts_per_stage : int — attempts before escalation/failure (default 3)
    """

    def __init__(
        self,
        generator: ChallengeGenerator,
        verifier: VoiceVerifier,
        config: dict,
    ) -> None:
        self._generator = generator
        self._verifier = verifier
        self._max_attempts: int = config.get("max_attempts_per_stage", 3)
        self._sessions: dict[str, LivenessSession] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_session(
        self,
        actor_id: str,
        *,
        language: str = "en",
        now: Optional[datetime] = None,
    ) -> LivenessSession:
        """Create a new liveness session and issue a stage-1 challenge.

        Args:
            actor_id: The actor undergoing verification.
            language: Language for the word challenge.
            now: Override current time (for testing).

        Returns:
            A new LivenessSession in CHALLENGE_ISSUED state.
        """
        challenge = self._generator.generate(language=language, stage=1, now=now)
        now_utc = now or datetime.now(timezone.utc)

        session = LivenessSession(
            session_id=str(uuid.uuid4()),
            actor_id=actor_id,
            state=SessionState.CHALLENGE_ISSUED,
            current_stage=1,
            attempts_this_stage=0,
            challenge=challenge,
            created_utc=now_utc,
            max_attempts_per_stage=self._max_attempts,
        )

        self._sessions[session.session_id] = session
        return session

    def submit_response(
        self,
        session_id: str,
        spoken_words: list[str],
        *,
        now: Optional[datetime] = None,
    ) -> LivenessSession:
        """Submit a spoken-word response for verification.

        State transitions:
          - Passed                            → PASSED
          - Failed, attempts < max            → CHALLENGE_ISSUED (re-issue)
          - Failed, attempts >= max, stage 1  → escalate to stage 2
          - Failed, attempts >= max, stage 2  → FAILED

        Args:
            session_id: Existing session ID.
            spoken_words: Transcript of what the actor said.
            now: Override current time (for testing).

        Returns:
            Updated LivenessSession.

        Raises:
            KeyError: Unknown session_id.
            ValueError: Session not in a submittable state.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Unknown session: {session_id}")

        if session.state not in (
            SessionState.CHALLENGE_ISSUED,
            SessionState.RESPONSE_SUBMITTED,
        ):
            raise ValueError(
                f"Cannot submit response: session state is {session.state.value}"
            )

        # Check expiry first
        if self.check_expiry(session_id, now=now):
            return session  # state already set to EXPIRED

        assert session.challenge is not None

        # Consume the nonce (anti-replay)
        self._generator.validate_nonce(
            session.challenge.challenge_id, session.challenge.nonce,
        )

        # Verify transcript
        result = self._verifier.verify_transcript(
            expected_words=list(session.challenge.words),
            spoken_words=spoken_words,
        )

        session.attempts_this_stage += 1
        session.last_result = result
        session.state = SessionState.RESPONSE_SUBMITTED

        if result.passed:
            session.state = SessionState.PASSED
            return session

        # Failed — decide next step
        if session.attempts_this_stage >= session.max_attempts_per_stage:
            if session.current_stage == 1:
                # Escalate to stage 2
                session.current_stage = 2
                session.attempts_this_stage = 0
                new_challenge = self._generator.generate(
                    language=session.challenge.language,
                    stage=2,
                    now=now,
                )
                session.challenge = new_challenge
                session.state = SessionState.CHALLENGE_ISSUED
            else:
                # Stage 2 exhausted — final failure
                session.state = SessionState.FAILED
        else:
            # Re-issue same-stage challenge
            new_challenge = self._generator.generate(
                language=session.challenge.language,
                stage=session.current_stage,
                now=now,
            )
            session.challenge = new_challenge
            session.state = SessionState.CHALLENGE_ISSUED

        return session

    def check_expiry(
        self,
        session_id: str,
        *,
        now: Optional[datetime] = None,
    ) -> bool:
        """Check if the session's current challenge has expired.

        If expired, sets session state to EXPIRED.

        Returns:
            True if expired, False otherwise.

        Raises:
            KeyError: Unknown session_id.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Unknown session: {session_id}")

        if session.challenge is None:
            return False

        if session.state in (SessionState.PASSED, SessionState.FAILED, SessionState.EXPIRED):
            return session.state == SessionState.EXPIRED

        if self._generator.is_expired(session.challenge, now=now):
            session.state = SessionState.EXPIRED
            return True

        return False

    def get_session(self, session_id: str) -> Optional[LivenessSession]:
        """Retrieve a session by ID (or None if unknown)."""
        return self._sessions.get(session_id)
