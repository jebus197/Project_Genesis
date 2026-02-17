"""Voice liveness challenge generator (Phase D-2).

Generates cryptographically random word challenges for voice-based
proof-of-personhood verification. Each challenge is frozen (immutable),
carries a nonce for anti-replay, and expires after a configurable timeout.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from genesis.identity.wordlists.en import WORDS as EN_WORDS


# ---------------------------------------------------------------------------
# Registry of word lists keyed by language code
# ---------------------------------------------------------------------------
_WORDLISTS: dict[str, list[str]] = {
    "en": EN_WORDS,
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LivenessChallenge:
    """An immutable voice liveness challenge issued to an actor."""

    challenge_id: str       # UUID
    words: tuple[str, ...]  # tuple for immutability (frozen dataclass)
    language: str           # e.g. "en"
    stage: int              # 1 or 2
    created_utc: datetime
    expires_utc: datetime
    nonce: str              # anti-replay token


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class ChallengeGenerator:
    """Creates and tracks voice liveness challenges.

    Parameters (via *config* dict):
        stage_1_word_count  : int   — words for stage 1 (default 6)
        stage_2_word_count  : int   — words for stage 2 (default 12)
        session_timeout_seconds : int — seconds until challenge expires (default 120)
        supported_languages : list[str] — e.g. ["en"] (default ["en"])
    """

    def __init__(self, config: dict) -> None:
        self._stage_1_count: int = config.get("stage_1_word_count", 6)
        self._stage_2_count: int = config.get("stage_2_word_count", 12)
        self._timeout: int = config.get("session_timeout_seconds", 120)
        self._languages: list[str] = config.get("supported_languages", ["en"])

        # Track used nonces: nonce → True (consumed)
        self._used_nonces: dict[str, bool] = {}

        # Track challenges by id (for nonce lookup)
        self._challenges: dict[str, LivenessChallenge] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        language: str = "en",
        stage: int = 1,
        *,
        now: Optional[datetime] = None,
    ) -> LivenessChallenge:
        """Generate a new liveness challenge.

        Args:
            language: Language code (must be in supported_languages).
            stage: 1 or 2. Stage 2 has more words (harder).
            now: Override current time (for testing).

        Returns:
            A frozen LivenessChallenge.

        Raises:
            ValueError: If language is unsupported or stage is invalid.
        """
        if language not in self._languages:
            raise ValueError(
                f"Unsupported language '{language}'. "
                f"Supported: {self._languages}"
            )
        if stage not in (1, 2):
            raise ValueError(f"Stage must be 1 or 2, got {stage}")

        wordlist = _WORDLISTS.get(language)
        if wordlist is None:
            raise ValueError(f"No word list available for language '{language}'")

        word_count = self._stage_1_count if stage == 1 else self._stage_2_count

        if word_count > len(wordlist):
            raise ValueError(
                f"Requested {word_count} words but word list only has "
                f"{len(wordlist)} entries"
            )

        # Cryptographically random selection with no repeats
        selected = _sample_no_repeats(wordlist, word_count)

        now_utc = now or datetime.now(timezone.utc)
        nonce = secrets.token_hex(16)
        challenge_id = str(uuid.uuid4())

        challenge = LivenessChallenge(
            challenge_id=challenge_id,
            words=tuple(selected),
            language=language,
            stage=stage,
            created_utc=now_utc,
            expires_utc=now_utc + timedelta(seconds=self._timeout),
            nonce=nonce,
        )

        self._challenges[challenge_id] = challenge
        self._used_nonces[nonce] = False  # Not yet consumed

        return challenge

    def validate_nonce(self, challenge_id: str, nonce: str) -> bool:
        """Validate and consume a challenge nonce (anti-replay).

        Returns True if the nonce is valid and has not been used before.
        Returns False if the nonce was already consumed, does not match,
        or the challenge_id is unknown.

        Each nonce can only be validated once — subsequent calls return False.
        """
        challenge = self._challenges.get(challenge_id)
        if challenge is None:
            return False

        if challenge.nonce != nonce:
            return False

        if self._used_nonces.get(nonce, True):
            # Already consumed (or unknown)
            return False

        # Consume the nonce
        self._used_nonces[nonce] = True
        return True

    def is_expired(
        self,
        challenge: LivenessChallenge,
        *,
        now: Optional[datetime] = None,
    ) -> bool:
        """Check whether a challenge has expired."""
        now_utc = now or datetime.now(timezone.utc)
        return now_utc >= challenge.expires_utc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_no_repeats(wordlist: list[str], count: int) -> list[str]:
    """Select *count* distinct words from *wordlist* using secrets."""
    if count > len(wordlist):
        raise ValueError("Cannot sample more words than available")

    # Use Fisher-Yates partial shuffle with secrets for randomness
    pool = list(wordlist)
    selected: list[str] = []
    for _ in range(count):
        idx = secrets.randbelow(len(pool))
        selected.append(pool[idx])
        # Swap chosen element to end and shrink pool
        pool[idx] = pool[-1]
        pool.pop()

    return selected
