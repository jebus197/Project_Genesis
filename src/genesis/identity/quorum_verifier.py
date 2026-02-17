"""Human-to-human quorum verification for disability accommodation (Phase D-3).

When an actor cannot complete the voice liveness challenge (e.g. speech
disability, deafness), they may request quorum verification instead.

A panel of randomly selected verified humans in the same geographic region
must unanimously confirm the actor's identity. This is the constitutional
fallback — no one is excluded from participation.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class QuorumVerificationRequest:
    """A quorum-based identity verification request."""

    request_id: str
    actor_id: str               # actor being verified
    quorum_size: int            # e.g. 3
    verifier_ids: list[str]     # randomly selected verified humans
    region_constraint: str      # geographic bound
    votes: dict[str, bool]      # verifier_id -> approved
    created_utc: datetime
    expires_utc: datetime


# ---------------------------------------------------------------------------
# Quorum verifier
# ---------------------------------------------------------------------------

class QuorumVerifier:
    """Manages quorum-based identity verification panels.

    Parameters (via *config* dict):
        min_quorum_size             : int   — minimum panel size (default 3)
        max_quorum_size             : int   — maximum panel size (default 5)
        verification_timeout_hours  : int   — hours until request expires (default 48)
        min_verifier_trust          : float — minimum trust score for verifiers (default 0.60)
        geographic_region_required  : bool  — require same-region verifiers (default True)
    """

    def __init__(self, config: dict) -> None:
        self._min_quorum: int = config.get("min_quorum_size", 3)
        self._max_quorum: int = config.get("max_quorum_size", 5)
        self._timeout_hours: int = config.get("verification_timeout_hours", 48)
        self._min_trust: float = config.get("min_verifier_trust", 0.60)
        self._require_region: bool = config.get("geographic_region_required", True)

        # Active requests: request_id -> QuorumVerificationRequest
        self._requests: dict[str, QuorumVerificationRequest] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request_quorum_verification(
        self,
        actor_id: str,
        region: str,
        available_verifiers: list[tuple[str, float, str]],
        *,
        quorum_size: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> QuorumVerificationRequest:
        """Create a new quorum verification request.

        Args:
            actor_id: The actor requesting identity verification.
            region: The actor's geographic region.
            available_verifiers: List of (verifier_id, trust_score, region)
                                 tuples for candidate verifiers.
            quorum_size: Override quorum size (must be within min/max bounds).
            now: Override current time (for testing).

        Returns:
            A new QuorumVerificationRequest.

        Raises:
            ValueError: If not enough eligible verifiers are available.
        """
        size = quorum_size or self._min_quorum

        if size < self._min_quorum:
            raise ValueError(
                f"Quorum size {size} is below minimum ({self._min_quorum})"
            )
        if size > self._max_quorum:
            raise ValueError(
                f"Quorum size {size} exceeds maximum ({self._max_quorum})"
            )

        # Filter eligible verifiers
        eligible = self._filter_eligible(available_verifiers, region)

        if len(eligible) < size:
            raise ValueError(
                f"Not enough eligible verifiers: need {size}, "
                f"found {len(eligible)} (after trust and region filtering)"
            )

        # Cryptographically random selection
        selected = _secure_sample(eligible, size)
        selected_ids = [vid for vid, _, _ in selected]

        now_utc = now or datetime.now(timezone.utc)

        request = QuorumVerificationRequest(
            request_id=str(uuid.uuid4()),
            actor_id=actor_id,
            quorum_size=size,
            verifier_ids=selected_ids,
            region_constraint=region,
            votes={},
            created_utc=now_utc,
            expires_utc=now_utc + timedelta(hours=self._timeout_hours),
        )

        self._requests[request.request_id] = request
        return request

    def submit_vote(
        self,
        request_id: str,
        verifier_id: str,
        approved: bool,
    ) -> QuorumVerificationRequest:
        """Record a verifier's vote.

        Args:
            request_id: The quorum verification request ID.
            verifier_id: The voting verifier's ID.
            approved: True to approve, False to reject.

        Returns:
            Updated QuorumVerificationRequest.

        Raises:
            KeyError: Unknown request_id.
            ValueError: Verifier not on the panel, or already voted.
        """
        request = self._requests.get(request_id)
        if request is None:
            raise KeyError(f"Unknown request: {request_id}")

        if verifier_id not in request.verifier_ids:
            raise ValueError(
                f"Verifier {verifier_id} is not on the panel for request {request_id}"
            )

        if verifier_id in request.votes:
            raise ValueError(
                f"Verifier {verifier_id} has already voted on request {request_id}"
            )

        request.votes[verifier_id] = approved
        return request

    def check_result(
        self,
        request_id: str,
        *,
        now: Optional[datetime] = None,
    ) -> Optional[bool]:
        """Check the outcome of a quorum verification request.

        Returns:
            None — still pending (not all votes in, not expired).
            True — all votes in and unanimously approved.
            False — any rejection, or request expired without unanimous approval.

        Raises:
            KeyError: Unknown request_id.
        """
        request = self._requests.get(request_id)
        if request is None:
            raise KeyError(f"Unknown request: {request_id}")

        now_utc = now or datetime.now(timezone.utc)

        # Check for explicit rejection
        for verifier_id, approved in request.votes.items():
            if not approved:
                return False

        # Check if all votes are in
        if len(request.votes) == request.quorum_size:
            # All voted — check unanimity
            return all(request.votes.values())

        # Check timeout
        if now_utc >= request.expires_utc:
            return False

        # Still pending
        return None

    def get_request(self, request_id: str) -> Optional[QuorumVerificationRequest]:
        """Retrieve a request by ID (or None if unknown)."""
        return self._requests.get(request_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _filter_eligible(
        self,
        verifiers: list[tuple[str, float, str]],
        region: str,
    ) -> list[tuple[str, float, str]]:
        """Filter verifiers by trust threshold and geographic region."""
        eligible = []
        for verifier_id, trust, verifier_region in verifiers:
            if trust < self._min_trust:
                continue
            if self._require_region and verifier_region != region:
                continue
            eligible.append((verifier_id, trust, verifier_region))
        return eligible


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _secure_sample(
    items: list[tuple[str, float, str]],
    count: int,
) -> list[tuple[str, float, str]]:
    """Select *count* items from *items* using cryptographic randomness."""
    if count > len(items):
        raise ValueError("Cannot sample more items than available")

    pool = list(items)
    selected: list[tuple[str, float, str]] = []
    for _ in range(count):
        idx = secrets.randbelow(len(pool))
        selected.append(pool[idx])
        pool[idx] = pool[-1]
        pool.pop()

    return selected
