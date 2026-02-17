"""Tests for voice verifier and quorum verification (Phase D-2/D-3).

Covers transcript scoring, threshold logic, case insensitivity,
and quorum-based verification including region filtering, trust
thresholds, unanimous approval, and rejection paths.
"""

import pytest
from datetime import datetime, timedelta, timezone

from genesis.identity.voice_verifier import VoiceVerifier, VerificationResult
from genesis.identity.quorum_verifier import QuorumVerifier, QuorumVerificationRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_verifier_config() -> dict:
    return {
        "word_match_threshold": 0.85,
        "naturalness_threshold": 0.70,
    }


def _default_quorum_config() -> dict:
    return {
        "min_quorum_size": 3,
        "max_quorum_size": 5,
        "verification_timeout_hours": 48,
        "min_verifier_trust": 0.60,
        "geographic_region_required": True,
        "require_vote_attestation": False,
        "verifier_cooldown_hours": 0,
    }


# ===========================================================================
# Voice Verifier Tests
# ===========================================================================

class TestVoiceVerifier:
    """Prove transcript verification scoring and threshold logic."""

    # ------------------------------------------------------------------
    # 1. Perfect match -> pass
    # ------------------------------------------------------------------

    def test_perfect_match_passes(self) -> None:
        """All words match exactly -> passed = True, score = 1.0."""
        verifier = VoiceVerifier(_default_verifier_config())
        expected = ["apple", "banana", "cherry", "dolphin", "eagle", "forest"]
        spoken = ["apple", "banana", "cherry", "dolphin", "eagle", "forest"]

        result = verifier.verify_transcript(expected, spoken)
        assert result.passed is True
        assert result.word_match_score == 1.0
        assert result.words_matched == 6
        assert result.words_expected == 6

    # ------------------------------------------------------------------
    # 2. Partial match below threshold -> fail
    # ------------------------------------------------------------------

    def test_partial_match_below_threshold_fails(self) -> None:
        """Only 4/6 words match (0.667) — below 0.85 threshold -> fail."""
        verifier = VoiceVerifier(_default_verifier_config())
        expected = ["apple", "banana", "cherry", "dolphin", "eagle", "forest"]
        spoken = ["apple", "banana", "wrong", "wrong", "eagle", "forest"]

        result = verifier.verify_transcript(expected, spoken)
        assert result.passed is False
        assert result.words_matched == 4
        assert result.word_match_score == pytest.approx(4 / 6)

    # ------------------------------------------------------------------
    # 3. Partial match at threshold -> pass
    # ------------------------------------------------------------------

    def test_match_at_threshold_passes(self) -> None:
        """Exactly at threshold (6/7 = 0.857) should pass."""
        config = {"word_match_threshold": 0.85, "naturalness_threshold": 0.70}
        verifier = VoiceVerifier(config)
        expected = ["a", "b", "c", "d", "e", "f", "g"]
        spoken = ["a", "b", "c", "d", "e", "f", "wrong"]

        result = verifier.verify_transcript(expected, spoken)
        # 6/7 = 0.857 >= 0.85
        assert result.passed is True
        assert result.words_matched == 6

    # ------------------------------------------------------------------
    # 4. Case insensitive matching
    # ------------------------------------------------------------------

    def test_case_insensitive_matching(self) -> None:
        """Matching should be case-insensitive."""
        verifier = VoiceVerifier(_default_verifier_config())
        expected = ["apple", "banana", "cherry"]
        spoken = ["APPLE", "Banana", "CHERRY"]

        result = verifier.verify_transcript(expected, spoken)
        assert result.passed is True
        assert result.words_matched == 3

    # ------------------------------------------------------------------
    # 5. Whitespace stripped
    # ------------------------------------------------------------------

    def test_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace should be stripped."""
        verifier = VoiceVerifier(_default_verifier_config())
        expected = ["apple", "banana", "cherry"]
        spoken = ["  apple  ", " banana", "cherry "]

        result = verifier.verify_transcript(expected, spoken)
        assert result.passed is True
        assert result.words_matched == 3

    # ------------------------------------------------------------------
    # 6. Fewer spoken words than expected -> lower score
    # ------------------------------------------------------------------

    def test_fewer_spoken_words(self) -> None:
        """Speaking fewer words than expected reduces the score."""
        verifier = VoiceVerifier(_default_verifier_config())
        expected = ["apple", "banana", "cherry", "dolphin", "eagle", "forest"]
        spoken = ["apple", "banana", "cherry"]  # only 3 of 6

        result = verifier.verify_transcript(expected, spoken)
        assert result.passed is False
        assert result.words_matched == 3
        assert result.words_expected == 6
        assert result.word_match_score == pytest.approx(0.5)

    # ------------------------------------------------------------------
    # 7. Empty expected words -> fail
    # ------------------------------------------------------------------

    def test_empty_expected_fails(self) -> None:
        """No expected words -> automatic fail."""
        verifier = VoiceVerifier(_default_verifier_config())
        result = verifier.verify_transcript([], ["hello"])
        assert result.passed is False
        assert result.words_expected == 0

    # ------------------------------------------------------------------
    # 8. Naturalness score is stubbed to 1.0
    # ------------------------------------------------------------------

    def test_naturalness_score_stub(self) -> None:
        """Naturalness score should be 1.0 (stub) for all inputs."""
        verifier = VoiceVerifier(_default_verifier_config())
        expected = ["apple", "banana"]
        spoken = ["apple", "banana"]

        result = verifier.verify_transcript(expected, spoken)
        assert result.naturalness_score == 1.0

    # ------------------------------------------------------------------
    # 9. Per-word details in result
    # ------------------------------------------------------------------

    def test_per_word_details(self) -> None:
        """Result should contain per-word match breakdown."""
        verifier = VoiceVerifier(_default_verifier_config())
        expected = ["apple", "banana", "cherry"]
        spoken = ["apple", "wrong", "cherry"]

        result = verifier.verify_transcript(expected, spoken)
        per_word = result.details["per_word"]
        assert len(per_word) == 3
        assert per_word[0]["match"] is True
        assert per_word[1]["match"] is False
        assert per_word[2]["match"] is True

    # ------------------------------------------------------------------
    # 10. Low threshold allows more misses
    # ------------------------------------------------------------------

    def test_low_threshold_passes(self) -> None:
        """With a low threshold (0.5), 3/6 words should pass."""
        config = {"word_match_threshold": 0.50, "naturalness_threshold": 0.70}
        verifier = VoiceVerifier(config)
        expected = ["a", "b", "c", "d", "e", "f"]
        spoken = ["a", "b", "c", "wrong", "wrong", "wrong"]

        result = verifier.verify_transcript(expected, spoken)
        assert result.passed is True
        assert result.words_matched == 3


# ===========================================================================
# Quorum Verifier Tests
# ===========================================================================

class TestQuorumVerifier:
    """Prove quorum selection, voting, unanimity, and timeout logic."""

    # ------------------------------------------------------------------
    # Shared fixtures
    # ------------------------------------------------------------------

    @staticmethod
    def _sample_verifiers() -> list[tuple[str, float, str]]:
        """5 verified humans in EU with varying trust scores."""
        return [
            ("V-001", 0.80, "EU"),
            ("V-002", 0.75, "EU"),
            ("V-003", 0.90, "EU"),
            ("V-004", 0.65, "EU"),
            ("V-005", 0.85, "EU"),
        ]

    # ------------------------------------------------------------------
    # 11. Quorum selection from same region
    # ------------------------------------------------------------------

    def test_quorum_selection_same_region(self) -> None:
        """Selected verifiers should all be from the actor's region."""
        qv = QuorumVerifier(_default_quorum_config())
        verifiers = self._sample_verifiers()
        request = qv.request_quorum_verification(
            actor_id="ACTOR-001",
            region="EU",
            available_verifiers=verifiers,
        )
        assert request.quorum_size == 3
        assert len(request.verifier_ids) == 3
        assert request.region_constraint == "EU"

    # ------------------------------------------------------------------
    # 12. Minimum trust filter
    # ------------------------------------------------------------------

    def test_minimum_trust_filter(self) -> None:
        """Verifiers below min_verifier_trust (0.60) should be excluded."""
        qv = QuorumVerifier(_default_quorum_config())
        verifiers = [
            ("V-001", 0.50, "EU"),  # below threshold
            ("V-002", 0.55, "EU"),  # below threshold
            ("V-003", 0.90, "EU"),
            ("V-004", 0.80, "EU"),
            ("V-005", 0.70, "EU"),
        ]
        request = qv.request_quorum_verification(
            actor_id="ACTOR-002",
            region="EU",
            available_verifiers=verifiers,
        )
        # V-001 and V-002 should be excluded; 3 remain and are selected
        assert len(request.verifier_ids) == 3
        assert "V-001" not in request.verifier_ids
        assert "V-002" not in request.verifier_ids

    # ------------------------------------------------------------------
    # 13. Region filter excludes other regions
    # ------------------------------------------------------------------

    def test_region_filter_excludes_others(self) -> None:
        """Verifiers in a different region should be excluded."""
        qv = QuorumVerifier(_default_quorum_config())
        verifiers = [
            ("V-001", 0.80, "EU"),
            ("V-002", 0.80, "US"),   # wrong region
            ("V-003", 0.80, "EU"),
            ("V-004", 0.80, "APAC"), # wrong region
            ("V-005", 0.80, "EU"),
        ]
        request = qv.request_quorum_verification(
            actor_id="ACTOR-003",
            region="EU",
            available_verifiers=verifiers,
        )
        assert len(request.verifier_ids) == 3
        assert "V-002" not in request.verifier_ids
        assert "V-004" not in request.verifier_ids

    # ------------------------------------------------------------------
    # 14. Not enough eligible verifiers raises ValueError
    # ------------------------------------------------------------------

    def test_not_enough_verifiers_raises(self) -> None:
        """Should raise ValueError if eligible verifiers < quorum_size."""
        qv = QuorumVerifier(_default_quorum_config())
        verifiers = [
            ("V-001", 0.80, "EU"),
            ("V-002", 0.80, "EU"),
            # Only 2 eligible but need 3
        ]
        with pytest.raises(ValueError, match="Not enough eligible verifiers"):
            qv.request_quorum_verification(
                actor_id="ACTOR-004",
                region="EU",
                available_verifiers=verifiers,
            )

    # ------------------------------------------------------------------
    # 15. Unanimous approval -> True
    # ------------------------------------------------------------------

    def test_unanimous_approval(self) -> None:
        """All verifiers approve -> check_result returns True."""
        qv = QuorumVerifier(_default_quorum_config())
        verifiers = self._sample_verifiers()
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        request = qv.request_quorum_verification(
            actor_id="ACTOR-005",
            region="EU",
            available_verifiers=verifiers,
            now=now,
        )

        # All vote yes
        for vid in request.verifier_ids:
            qv.submit_vote(request.request_id, vid, approved=True)

        result = qv.check_result(request.request_id, now=now + timedelta(hours=1))
        assert result is True

    # ------------------------------------------------------------------
    # 16. Single rejection -> False
    # ------------------------------------------------------------------

    def test_single_rejection(self) -> None:
        """One rejection -> check_result returns False immediately."""
        qv = QuorumVerifier(_default_quorum_config())
        verifiers = self._sample_verifiers()
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        request = qv.request_quorum_verification(
            actor_id="ACTOR-006",
            region="EU",
            available_verifiers=verifiers,
            now=now,
        )

        # First approves, second rejects
        qv.submit_vote(request.request_id, request.verifier_ids[0], approved=True)
        qv.submit_vote(request.request_id, request.verifier_ids[1], approved=False)

        result = qv.check_result(request.request_id, now=now + timedelta(hours=1))
        assert result is False

    # ------------------------------------------------------------------
    # 17. Pending result (not all votes in)
    # ------------------------------------------------------------------

    def test_pending_result(self) -> None:
        """Not all votes in and not expired -> check_result returns None."""
        qv = QuorumVerifier(_default_quorum_config())
        verifiers = self._sample_verifiers()
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        request = qv.request_quorum_verification(
            actor_id="ACTOR-007",
            region="EU",
            available_verifiers=verifiers,
            now=now,
        )

        # Only one vote
        qv.submit_vote(request.request_id, request.verifier_ids[0], approved=True)

        result = qv.check_result(request.request_id, now=now + timedelta(hours=1))
        assert result is None

    # ------------------------------------------------------------------
    # 18. Timeout without all votes -> False
    # ------------------------------------------------------------------

    def test_timeout_without_all_votes(self) -> None:
        """Request expires without all votes -> check_result returns False."""
        qv = QuorumVerifier(_default_quorum_config())
        verifiers = self._sample_verifiers()
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        request = qv.request_quorum_verification(
            actor_id="ACTOR-008",
            region="EU",
            available_verifiers=verifiers,
            now=now,
        )

        qv.submit_vote(request.request_id, request.verifier_ids[0], approved=True)

        # Check after timeout (48 hours)
        result = qv.check_result(
            request.request_id,
            now=now + timedelta(hours=49),
        )
        assert result is False

    # ------------------------------------------------------------------
    # 19. Duplicate vote raises ValueError
    # ------------------------------------------------------------------

    def test_duplicate_vote_raises(self) -> None:
        """Same verifier voting twice should raise ValueError."""
        qv = QuorumVerifier(_default_quorum_config())
        verifiers = self._sample_verifiers()
        request = qv.request_quorum_verification(
            actor_id="ACTOR-009",
            region="EU",
            available_verifiers=verifiers,
        )

        vid = request.verifier_ids[0]
        qv.submit_vote(request.request_id, vid, approved=True)

        with pytest.raises(ValueError, match="already voted"):
            qv.submit_vote(request.request_id, vid, approved=True)

    # ------------------------------------------------------------------
    # 20. Non-panel verifier vote raises ValueError
    # ------------------------------------------------------------------

    def test_non_panel_verifier_raises(self) -> None:
        """Verifier not on the panel cannot vote."""
        qv = QuorumVerifier(_default_quorum_config())
        verifiers = self._sample_verifiers()
        request = qv.request_quorum_verification(
            actor_id="ACTOR-010",
            region="EU",
            available_verifiers=verifiers,
        )

        with pytest.raises(ValueError, match="not on the panel"):
            qv.submit_vote(request.request_id, "OUTSIDER-999", approved=True)

    # ------------------------------------------------------------------
    # 21. Unknown request_id raises KeyError
    # ------------------------------------------------------------------

    def test_unknown_request_raises(self) -> None:
        """Operations on unknown request ID should raise KeyError."""
        qv = QuorumVerifier(_default_quorum_config())
        with pytest.raises(KeyError):
            qv.submit_vote("fake-request", "V-001", approved=True)
        with pytest.raises(KeyError):
            qv.check_result("fake-request")

    # ------------------------------------------------------------------
    # 22. Quorum size below minimum raises ValueError
    # ------------------------------------------------------------------

    def test_quorum_below_minimum_raises(self) -> None:
        """Quorum size below min_quorum_size should raise ValueError."""
        qv = QuorumVerifier(_default_quorum_config())
        verifiers = self._sample_verifiers()
        with pytest.raises(ValueError, match="below minimum"):
            qv.request_quorum_verification(
                actor_id="ACTOR-011",
                region="EU",
                available_verifiers=verifiers,
                quorum_size=1,
            )

    # ------------------------------------------------------------------
    # 23. Quorum size above maximum raises ValueError
    # ------------------------------------------------------------------

    def test_quorum_above_maximum_raises(self) -> None:
        """Quorum size above max_quorum_size should raise ValueError."""
        qv = QuorumVerifier(_default_quorum_config())
        verifiers = self._sample_verifiers()
        with pytest.raises(ValueError, match="exceeds maximum"):
            qv.request_quorum_verification(
                actor_id="ACTOR-012",
                region="EU",
                available_verifiers=verifiers,
                quorum_size=10,
            )

    # ------------------------------------------------------------------
    # 24. Request has correct expiry time
    # ------------------------------------------------------------------

    def test_request_expiry_time(self) -> None:
        """Request expires_utc should be created_utc + timeout_hours."""
        qv = QuorumVerifier(_default_quorum_config())
        verifiers = self._sample_verifiers()
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        request = qv.request_quorum_verification(
            actor_id="ACTOR-013",
            region="EU",
            available_verifiers=verifiers,
            now=now,
        )
        assert request.expires_utc == now + timedelta(hours=48)
        assert request.created_utc == now
