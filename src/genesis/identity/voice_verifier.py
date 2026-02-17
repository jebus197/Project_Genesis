"""Voice verification scoring engine (Phase D-2).

Compares spoken words against expected challenge words and produces
a VerificationResult. The naturalness_score is a stub (always 1.0)
pending future audio-analysis integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VerificationResult:
    """Outcome of a voice liveness verification attempt."""

    passed: bool
    word_match_score: float     # 0.0 – 1.0
    naturalness_score: float    # 0.0 – 1.0 (stub: always 1.0 for now)
    words_matched: int
    words_expected: int
    details: dict               # per-word breakdown


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------

class VoiceVerifier:
    """Scores spoken-word transcripts against liveness challenges.

    Parameters (via *config* dict):
        word_match_threshold   : float — minimum word_match_score to pass (default 0.85)
        naturalness_threshold  : float — minimum naturalness_score to pass (default 0.70)
    """

    def __init__(self, config: dict) -> None:
        self._word_match_threshold: float = config.get("word_match_threshold", 0.85)
        self._naturalness_threshold: float = config.get("naturalness_threshold", 0.70)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify_transcript(
        self,
        expected_words: list[str],
        spoken_words: list[str],
    ) -> VerificationResult:
        """Compare spoken words against expected challenge words.

        Matching is:
          - Case-insensitive
          - Whitespace-stripped
          - Positional (word N in spoken compared to word N in expected)

        Args:
            expected_words: The challenge word sequence.
            spoken_words: The transcript word sequence.

        Returns:
            VerificationResult with pass/fail and detailed breakdown.
        """
        # Normalise inputs
        normalised_expected = [w.strip().lower() for w in expected_words]
        normalised_spoken = [w.strip().lower() for w in spoken_words]

        words_expected = len(normalised_expected)
        if words_expected == 0:
            return VerificationResult(
                passed=False,
                word_match_score=0.0,
                naturalness_score=1.0,
                words_matched=0,
                words_expected=0,
                details={"error": "no expected words provided"},
            )

        # Positional comparison
        per_word: list[dict] = []
        matched = 0

        for i, expected in enumerate(normalised_expected):
            if i < len(normalised_spoken):
                spoken = normalised_spoken[i]
                is_match = spoken == expected
                if is_match:
                    matched += 1
                per_word.append({
                    "position": i,
                    "expected": expected,
                    "spoken": spoken,
                    "match": is_match,
                })
            else:
                per_word.append({
                    "position": i,
                    "expected": expected,
                    "spoken": None,
                    "match": False,
                })

        word_match_score = matched / words_expected

        # Stub: real audio naturalness analysis deferred
        naturalness_score = 1.0

        passed = (
            word_match_score >= self._word_match_threshold
            and naturalness_score >= self._naturalness_threshold
        )

        return VerificationResult(
            passed=passed,
            word_match_score=word_match_score,
            naturalness_score=naturalness_score,
            words_matched=matched,
            words_expected=words_expected,
            details={"per_word": per_word},
        )

    @property
    def word_match_threshold(self) -> float:
        return self._word_match_threshold

    @property
    def naturalness_threshold(self) -> float:
        return self._naturalness_threshold
