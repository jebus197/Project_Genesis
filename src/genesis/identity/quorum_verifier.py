"""Human-to-human quorum verification for disability accommodation (Phase D-3/D-5).

When an actor cannot complete the voice liveness challenge (e.g. speech
disability, deafness), they may request quorum verification instead.

A panel of randomly selected verified humans in the same geographic region
must unanimously confirm the actor's identity. This is the constitutional
fallback — no one is excluded from participation.

Phase D-5 adds: panel diversity enforcement, verifier cooldown/workload,
blind adjudication, vote attestation, recusal, session evidence, abuse
complaint/review, appeal mechanism, and a scripted interaction protocol.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Scripted interaction protocol
# ---------------------------------------------------------------------------

SCRIPTED_INTRO_V1 = (
    "Hello, I'm {verifier_pseudonym}, a verified community member. "
    "This process is simple and entirely private. I'm here to help confirm "
    "your identity so you can participate. You'll be asked to read, write, "
    "or have someone assist you with a short word challenge — the same one "
    "everyone completes. This session is recorded for your protection and "
    "will be automatically deleted in 72 hours if no issues are raised. "
    "If anything makes you uncomfortable, you may stop at any time and "
    "file a report. Let's begin."
)

SCRIPTED_INTRO_VERSIONS: dict[str, str] = {
    "v1": SCRIPTED_INTRO_V1,
}


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

    # --- Phase D-5 safeguard fields ---
    verifier_organizations: dict[str, str] = field(default_factory=dict)
    verifier_regions: dict[str, str] = field(default_factory=dict)
    vote_attestations: dict[str, str] = field(default_factory=dict)
    recusals: dict[str, str] = field(default_factory=dict)
    session_evidence_hash: Optional[str] = None
    appeal_of: Optional[str] = None
    applicant_pseudonym: str = ""
    session_max_seconds: int = 240          # 4 minutes
    recording_retention_hours: int = 72     # auto-delete window
    abuse_complaints: dict[str, str] = field(default_factory=dict)
    scripted_intro_version: str = "v1"


@dataclass(frozen=True)
class PanelDiversityResult:
    """Whether a selected panel meets diversity requirements."""
    meets_requirements: bool
    distinct_organizations: int
    distinct_regions: int
    violations: tuple[str, ...]     # frozen-friendly


@dataclass(frozen=True)
class AbuseReviewResult:
    """Outcome of an abuse complaint review."""
    confirmed: bool
    review_panel: tuple[str, ...]   # reviewer IDs
    votes: dict[str, bool]          # reviewer_id -> confirmed_abuse
    trust_action_taken: bool        # whether trust was nuked


# ---------------------------------------------------------------------------
# Quorum verifier
# ---------------------------------------------------------------------------

class QuorumVerifier:
    """Manages quorum-based identity verification panels.

    Parameters (via *config* dict):
        min_quorum_size                   : int   — minimum panel size (default 3)
        max_quorum_size                   : int   — maximum panel size (default 5)
        verification_timeout_hours        : int   — hours until request expires (default 48)
        min_verifier_trust                : float — minimum trust score for verifiers (default 0.70)
        geographic_region_required        : bool  — require same-region verifiers (default True)
        panel_diversity_min_organizations : int   — min distinct orgs in panel (default 2)
        panel_diversity_min_regions       : int   — min distinct regions in panel (default 1)
        verifier_cooldown_hours           : int   — hours between panel assignments (default 168)
        max_panels_per_verifier_per_month : int   — rate limit (default 10)
        max_concurrent_panels_per_verifier: int   — concurrent panel limit (default 3)
        blind_adjudication                : bool  — use pseudonyms (default True)
        appeal_window_hours               : int   — hours to file appeal (default 72)
        require_vote_attestation          : bool  — written attestation required (default True)
        session_max_seconds               : int   — max live session duration (default 240)
        recording_retention_hours         : int   — auto-delete window (default 72)
        abuse_trust_nuke_to               : float — trust floor for confirmed abusers (default 0.001)
        abuse_review_panel_size           : int   — reviewers for abuse complaints (default 3)
        abuse_reviewer_min_trust          : float — min trust for abuse reviewers (default 0.70)
    """

    def __init__(self, config: dict) -> None:
        # Core settings (Phase D-3)
        self._min_quorum: int = config.get("min_quorum_size", 3)
        self._max_quorum: int = config.get("max_quorum_size", 5)
        self._timeout_hours: int = config.get("verification_timeout_hours", 48)
        self._min_trust: float = config.get("min_verifier_trust", 0.70)
        self._require_region: bool = config.get("geographic_region_required", True)

        # Phase D-5 safeguard settings
        self._panel_min_orgs: int = config.get("panel_diversity_min_organizations", 2)
        self._panel_min_regions: int = config.get("panel_diversity_min_regions", 1)
        self._verifier_cooldown_hours: int = config.get("verifier_cooldown_hours", 168)
        self._max_panels_per_month: int = config.get("max_panels_per_verifier_per_month", 10)
        self._max_concurrent_panels: int = config.get("max_concurrent_panels_per_verifier", 3)
        self._blind_adjudication: bool = config.get("blind_adjudication", True)
        self._appeal_window_hours: int = config.get("appeal_window_hours", 72)
        self._require_vote_attestation: bool = config.get("require_vote_attestation", True)
        self._session_max_seconds: int = config.get("session_max_seconds", 240)
        self._recording_retention_hours: int = config.get("recording_retention_hours", 72)
        self._abuse_trust_nuke: float = config.get("abuse_trust_nuke_to", 0.001)
        self._abuse_review_panel_size: int = config.get("abuse_review_panel_size", 3)
        self._abuse_reviewer_min_trust: float = config.get("abuse_reviewer_min_trust", 0.70)

        # Active requests: request_id -> QuorumVerificationRequest
        self._requests: dict[str, QuorumVerificationRequest] = {}

        # Verifier history for cooldown/workload tracking
        self._verifier_history: dict[str, list[datetime]] = {}

    # ------------------------------------------------------------------
    # Public API — Panel formation
    # ------------------------------------------------------------------

    def request_quorum_verification(
        self,
        actor_id: str,
        region: str,
        available_verifiers: list[tuple[str, float, str]],
        *,
        verifier_orgs: Optional[dict[str, str]] = None,
        quorum_size: Optional[int] = None,
        now: Optional[datetime] = None,
        exclude_verifiers: Optional[set[str]] = None,
        appeal_of: Optional[str] = None,
    ) -> QuorumVerificationRequest:
        """Create a new quorum verification request.

        Args:
            actor_id: The actor requesting identity verification.
            region: The actor's geographic region.
            available_verifiers: List of (verifier_id, trust_score, region) tuples.
            verifier_orgs: Mapping verifier_id -> organization name.
            quorum_size: Override quorum size (must be within min/max bounds).
            now: Override current time (for testing).
            exclude_verifiers: Verifier IDs to exclude (e.g. for appeals).
            appeal_of: If this is an appeal, the original request_id.

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

        now_utc = now or datetime.now(timezone.utc)
        verifier_orgs = verifier_orgs or {}
        exclude = exclude_verifiers or set()

        # Filter eligible verifiers (trust, region, cooldown, workload, exclusions)
        eligible = self._filter_eligible(available_verifiers, region, now_utc, exclude)

        if len(eligible) < size:
            raise ValueError(
                f"Not enough eligible verifiers: need {size}, "
                f"found {len(eligible)} (after trust, region, cooldown, and workload filtering)"
            )

        # Cryptographically random selection with diversity check
        selected = self._select_diverse_panel(eligible, size, verifier_orgs)
        selected_ids = [vid for vid, _, _ in selected]

        # Build org/region maps for the panel
        panel_orgs: dict[str, str] = {}
        panel_regions: dict[str, str] = {}
        for vid, _, vreg in selected:
            panel_orgs[vid] = verifier_orgs.get(vid, "unknown")
            panel_regions[vid] = vreg

        # Generate blind adjudication pseudonym
        pseudonym = (
            f"participant-{uuid.uuid4().hex[:8]}"
            if self._blind_adjudication
            else actor_id
        )

        request = QuorumVerificationRequest(
            request_id=str(uuid.uuid4()),
            actor_id=actor_id,
            quorum_size=size,
            verifier_ids=selected_ids,
            region_constraint=region,
            votes={},
            created_utc=now_utc,
            expires_utc=now_utc + timedelta(hours=self._timeout_hours),
            verifier_organizations=panel_orgs,
            verifier_regions=panel_regions,
            applicant_pseudonym=pseudonym,
            session_max_seconds=self._session_max_seconds,
            recording_retention_hours=self._recording_retention_hours,
            scripted_intro_version="v1",
            appeal_of=appeal_of,
        )

        self._requests[request.request_id] = request

        # Record verifier assignments in history
        for vid in selected_ids:
            self._verifier_history.setdefault(vid, []).append(now_utc)

        return request

    # ------------------------------------------------------------------
    # Public API — Voting
    # ------------------------------------------------------------------

    def submit_vote(
        self,
        request_id: str,
        verifier_id: str,
        approved: bool,
        *,
        attestation: Optional[str] = None,
    ) -> QuorumVerificationRequest:
        """Record a verifier's vote.

        Args:
            request_id: The quorum verification request ID.
            verifier_id: The voting verifier's ID.
            approved: True to approve, False to reject.
            attestation: Written attestation (required if config says so).

        Returns:
            Updated QuorumVerificationRequest.

        Raises:
            KeyError: Unknown request_id.
            ValueError: Verifier not on panel, already voted, or missing attestation.
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

        # Check attestation requirement
        if self._require_vote_attestation and not attestation:
            raise ValueError(
                f"Vote attestation is required but was not provided by {verifier_id}"
            )

        request.votes[verifier_id] = approved
        if attestation:
            request.vote_attestations[verifier_id] = attestation
        return request

    # ------------------------------------------------------------------
    # Public API — Result checking
    # ------------------------------------------------------------------

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
            False — any rejection, or expired without unanimous approval.

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
            return all(request.votes.values())

        # Check timeout
        if now_utc >= request.expires_utc:
            return False

        return None

    # ------------------------------------------------------------------
    # Public API — Recusal
    # ------------------------------------------------------------------

    def declare_recusal(
        self,
        request_id: str,
        verifier_id: str,
        reason: str,
    ) -> QuorumVerificationRequest:
        """Declare a verifier's recusal from a panel.

        The verifier is removed from the active panel. If the remaining
        panel is below min_quorum_size, raises ValueError.

        Raises:
            KeyError: Unknown request_id.
            ValueError: Verifier not on panel, or panel would be too small.
        """
        request = self._requests.get(request_id)
        if request is None:
            raise KeyError(f"Unknown request: {request_id}")

        if verifier_id not in request.verifier_ids:
            raise ValueError(
                f"Verifier {verifier_id} is not on the panel for request {request_id}"
            )

        remaining = len(request.verifier_ids) - 1
        if remaining < self._min_quorum:
            raise ValueError(
                f"Recusal would reduce panel below minimum quorum size "
                f"({remaining} < {self._min_quorum}). Request needs re-paneling."
            )

        request.recusals[verifier_id] = reason
        request.verifier_ids.remove(verifier_id)
        request.quorum_size = len(request.verifier_ids)
        return request

    # ------------------------------------------------------------------
    # Public API — Session evidence
    # ------------------------------------------------------------------

    def attach_session_evidence(
        self,
        request_id: str,
        evidence_hash: str,
    ) -> QuorumVerificationRequest:
        """Attach a SHA-256 hash of the session recording.

        Raises:
            KeyError: Unknown request_id.
        """
        request = self._requests.get(request_id)
        if request is None:
            raise KeyError(f"Unknown request: {request_id}")

        request.session_evidence_hash = evidence_hash
        return request

    # ------------------------------------------------------------------
    # Public API — Abuse complaint + review
    # ------------------------------------------------------------------

    def file_abuse_complaint(
        self,
        request_id: str,
        reporter_id: str,
        complaint_text: str,
    ) -> QuorumVerificationRequest:
        """File an abuse complaint against a quorum session.

        Recording is preserved past the auto-delete window while
        a complaint is active.

        Raises:
            KeyError: Unknown request_id.
        """
        request = self._requests.get(request_id)
        if request is None:
            raise KeyError(f"Unknown request: {request_id}")

        request.abuse_complaints[reporter_id] = complaint_text
        return request

    def review_abuse_complaint(
        self,
        request_id: str,
        review_panel: list[str],
        votes: dict[str, bool],
    ) -> AbuseReviewResult:
        """Review an abuse complaint via a panel of high-trust reviewers.

        Majority of the review panel must confirm abuse for it to be
        marked as confirmed. If confirmed, the service layer nukes
        the offending verifier's trust to 0.001.

        Raises:
            KeyError: Unknown request_id.
            ValueError: Insufficient reviewers or missing votes.
        """
        request = self._requests.get(request_id)
        if request is None:
            raise KeyError(f"Unknown request: {request_id}")

        if len(review_panel) < self._abuse_review_panel_size:
            raise ValueError(
                f"Abuse review requires at least {self._abuse_review_panel_size} "
                f"reviewers, got {len(review_panel)}"
            )

        for reviewer_id in review_panel:
            if reviewer_id not in votes:
                raise ValueError(f"Missing vote from reviewer {reviewer_id}")

        confirms = sum(1 for v in votes.values() if v)
        confirmed = confirms > len(review_panel) // 2  # strict majority

        return AbuseReviewResult(
            confirmed=confirmed,
            review_panel=tuple(review_panel),
            votes=dict(votes),
            trust_action_taken=confirmed,
        )

    # ------------------------------------------------------------------
    # Public API — Appeal
    # ------------------------------------------------------------------

    def request_appeal(
        self,
        original_request_id: str,
        available_verifiers: list[tuple[str, float, str]],
        *,
        verifier_orgs: Optional[dict[str, str]] = None,
        now: Optional[datetime] = None,
    ) -> QuorumVerificationRequest:
        """Appeal a rejected quorum verification.

        Creates a new request with a completely different panel.
        Can only appeal rejected requests within the appeal window.

        Raises:
            KeyError: Unknown original request.
            ValueError: Original wasn't rejected, or appeal window expired.
        """
        original = self._requests.get(original_request_id)
        if original is None:
            raise KeyError(f"Unknown request: {original_request_id}")

        now_utc = now or datetime.now(timezone.utc)

        # Check that the original was actually rejected
        result = self.check_result(original_request_id, now=now_utc)
        if result is not False:
            raise ValueError(
                "Can only appeal rejected requests "
                f"(current result: {'pending' if result is None else 'approved'})"
            )

        # Check appeal window
        appeal_deadline = original.created_utc + timedelta(
            hours=self._appeal_window_hours,
        )
        if now_utc > appeal_deadline:
            raise ValueError(
                f"Appeal window has expired (deadline was "
                f"{appeal_deadline.isoformat()})"
            )

        # Exclude original panel from new selection
        original_panel = set(original.verifier_ids) | set(original.recusals.keys())

        return self.request_quorum_verification(
            actor_id=original.actor_id,
            region=original.region_constraint,
            available_verifiers=available_verifiers,
            verifier_orgs=verifier_orgs,
            now=now_utc,
            exclude_verifiers=original_panel,
            appeal_of=original_request_id,
        )

    # ------------------------------------------------------------------
    # Public API — Panel diversity check
    # ------------------------------------------------------------------

    def check_panel_diversity(
        self,
        panel: list[tuple[str, str, str]],
    ) -> PanelDiversityResult:
        """Check if a panel meets diversity requirements.

        Args:
            panel: List of (verifier_id, organization, region) tuples.

        Returns:
            PanelDiversityResult with violations if any.
        """
        orgs = {org for _, org, _ in panel}
        regions = {reg for _, _, reg in panel}
        violations: list[str] = []

        if len(orgs) < self._panel_min_orgs:
            violations.append(
                f"Need {self._panel_min_orgs} distinct organizations, "
                f"got {len(orgs)}: {sorted(orgs)}"
            )
        if len(regions) < self._panel_min_regions:
            violations.append(
                f"Need {self._panel_min_regions} distinct regions, "
                f"got {len(regions)}: {sorted(regions)}"
            )

        return PanelDiversityResult(
            meets_requirements=len(violations) == 0,
            distinct_organizations=len(orgs),
            distinct_regions=len(regions),
            violations=tuple(violations),
        )

    # ------------------------------------------------------------------
    # Public API — Verifier cooldown + workload
    # ------------------------------------------------------------------

    def check_verifier_cooldown(
        self,
        verifier_id: str,
        now: Optional[datetime] = None,
    ) -> bool:
        """Check if a verifier is on cooldown.

        Returns True if the verifier served on a panel within
        verifier_cooldown_hours.
        """
        now_utc = now or datetime.now(timezone.utc)
        history = self._verifier_history.get(verifier_id, [])
        cutoff = now_utc - timedelta(hours=self._verifier_cooldown_hours)
        return any(ts >= cutoff for ts in history)

    def check_verifier_workload(
        self,
        verifier_id: str,
        now: Optional[datetime] = None,
    ) -> list[str]:
        """Check if a verifier exceeds workload limits.

        Returns a list of violation descriptions (empty = OK).
        """
        now_utc = now or datetime.now(timezone.utc)
        history = self._verifier_history.get(verifier_id, [])
        violations: list[str] = []

        # Max panels per month (30 days)
        month_cutoff = now_utc - timedelta(days=30)
        monthly_count = sum(1 for ts in history if ts >= month_cutoff)
        if monthly_count >= self._max_panels_per_month:
            violations.append(
                f"Exceeded max panels per month: "
                f"{monthly_count} >= {self._max_panels_per_month}"
            )

        # Max concurrent: panels in last timeout_hours that may still be active
        active_cutoff = now_utc - timedelta(hours=self._timeout_hours)
        concurrent_count = sum(1 for ts in history if ts >= active_cutoff)
        if concurrent_count >= self._max_concurrent_panels:
            violations.append(
                f"Exceeded max concurrent panels: "
                f"{concurrent_count} >= {self._max_concurrent_panels}"
            )

        return violations

    # ------------------------------------------------------------------
    # Public API — Misc
    # ------------------------------------------------------------------

    def get_request(self, request_id: str) -> Optional[QuorumVerificationRequest]:
        """Retrieve a request by ID (or None if unknown)."""
        return self._requests.get(request_id)

    def get_scripted_intro(self, version: str = "v1") -> str:
        """Get the scripted introduction text for a given version."""
        return SCRIPTED_INTRO_VERSIONS.get(version, SCRIPTED_INTRO_V1)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _filter_eligible(
        self,
        verifiers: list[tuple[str, float, str]],
        region: str,
        now: datetime,
        exclude: set[str],
    ) -> list[tuple[str, float, str]]:
        """Filter verifiers by trust, region, cooldown, workload, exclusions."""
        eligible = []
        for verifier_id, trust, verifier_region in verifiers:
            if verifier_id in exclude:
                continue
            if trust < self._min_trust:
                continue
            if self._require_region and verifier_region != region:
                continue
            if self.check_verifier_cooldown(verifier_id, now):
                continue
            if self.check_verifier_workload(verifier_id, now):
                continue
            eligible.append((verifier_id, trust, verifier_region))
        return eligible

    def _select_diverse_panel(
        self,
        eligible: list[tuple[str, float, str]],
        size: int,
        verifier_orgs: dict[str, str],
    ) -> list[tuple[str, float, str]]:
        """Select a panel that meets diversity requirements.

        Retries up to 3 times. If diversity cannot be met, returns
        the last selection (caller can check diversity themselves).
        """
        selected = _secure_sample(eligible, size)
        for _attempt in range(3):
            panel_tuples = [
                (vid, verifier_orgs.get(vid, "unknown"), vreg)
                for vid, _, vreg in selected
            ]
            diversity = self.check_panel_diversity(panel_tuples)
            if diversity.meets_requirements:
                return selected
            selected = _secure_sample(eligible, size)

        return selected


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
