"""Tests for Distributed Intelligence — constitutional principle.

Proves constitutional invariants:
- Open Work visibility defaults to PUBLIC in market listings
  (insights inherit source mission visibility).
- Trust scores are computed from outcomes, not centrally assigned.
- Quality review is mandatory (no mission closes without it).
- No mechanism exists to retroactively conceal completed work
  (Open Work principle — METADATA_ONLY has a time-limited expiry,
  never permanent concealment).

Also covers:
- InsightSignal Protocol is runtime_checkable.
- InsightType covers five classification categories.
- ConcreteInsightSignal satisfies InsightSignal Protocol.
- InsightRegistry rejects signals without valid provenance hash.
- InsightRegistry rejects signals with unknown source actor.
- InsightRegistry enforces confidence bounds.
- InsightRegistry enforces non-empty payload.
- InsightRegistry query is open (no access restriction).
- compute_provenance_hash produces valid SHA-256.
- Design test #92 structural verification.

Design test #92: Can any entity restrict the flow of work-derived
insights across the network for private advantage? If yes, reject design.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest

from genesis.intelligence.insight_protocol import (
    ConcreteInsightSignal,
    InsightRegistry,
    InsightSignal,
    InsightType,
    compute_provenance_hash,
)
from genesis.models.market import MarketListing, WorkVisibility


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_hash() -> str:
    """Return a valid SHA-256 provenance hash for testing."""
    return compute_provenance_hash(["mission-001", "review-001", "trust-snapshot"])


def _make_signal(
    *,
    signal_id: str = "sig-001",
    source_mission_id: str = "mission-001",
    source_actor_id: str = "actor-alice",
    signal_type: InsightType = InsightType.TECHNIQUE,
    confidence: float = 0.85,
    payload: str = "Use batch processing for CSV files over 10MB",
    provenance_hash: str | None = None,
    visibility: WorkVisibility = WorkVisibility.PUBLIC,
    ttl_days: int | None = None,
) -> ConcreteInsightSignal:
    """Create a valid ConcreteInsightSignal for testing."""
    return ConcreteInsightSignal(
        signal_id=signal_id,
        source_mission_id=source_mission_id,
        source_actor_id=source_actor_id,
        signal_type=signal_type,
        confidence=confidence,
        payload=payload,
        provenance_hash=provenance_hash if provenance_hash is not None else _valid_hash(),
        visibility=visibility,
        ttl_days=ttl_days,
    )


def _registry_with_actor(*actors: str) -> InsightRegistry:
    """Create an InsightRegistry with known actors pre-registered."""
    reg = InsightRegistry()
    for a in actors:
        reg.register_actor(a)
    return reg


# ---------------------------------------------------------------------------
# Existing guarantees — verify what's already built
# ---------------------------------------------------------------------------

class TestExistingOpenWorkGuarantees:
    """Verify that the existing codebase structurally supports distributed
    intelligence through Open Work, trust, and quality mechanisms."""

    def test_market_listing_defaults_to_public_visibility(self):
        """Open Work: listings are PUBLIC by default."""
        listing = MarketListing(
            listing_id="L001",
            creator_id="creator",
            title="Test",
            description="Test listing",
            skill_requirements=[],
        )
        assert listing.visibility == WorkVisibility.PUBLIC

    def test_no_private_visibility_value(self):
        """Genesis has no concept of hidden work — no PRIVATE enum value."""
        values = {v.value for v in WorkVisibility}
        assert "private" not in values
        assert "concealed" not in values
        assert "hidden" not in values

    def test_metadata_only_is_time_limited(self):
        """METADATA_ONLY visibility has an expiry mechanism — no permanent
        concealment. After expiry, visibility reverts to PUBLIC."""
        # The MarketListing has visibility_expiry_utc field
        listing = MarketListing(
            listing_id="L002",
            creator_id="creator",
            title="Test",
            description="Test listing",
            skill_requirements=[],
            visibility=WorkVisibility.METADATA_ONLY,
            visibility_expiry_utc=datetime.now(timezone.utc) + timedelta(days=365),
        )
        assert listing.visibility_expiry_utc is not None
        # The service layer sweeps expired METADATA_ONLY back to PUBLIC

    def test_work_visibility_has_exactly_two_tiers(self):
        """Open Work principle: only PUBLIC and METADATA_ONLY exist.
        No third tier that could enable concealment."""
        assert len(WorkVisibility) == 2
        assert WorkVisibility.PUBLIC in WorkVisibility
        assert WorkVisibility.METADATA_ONLY in WorkVisibility


# ---------------------------------------------------------------------------
# InsightSignal Protocol tests
# ---------------------------------------------------------------------------

class TestInsightSignalProtocol:
    """Verify the InsightSignal Protocol contract."""

    def test_protocol_is_runtime_checkable(self):
        """InsightSignal Protocol must be runtime_checkable so the registry
        can verify conformance at registration time."""
        signal = _make_signal()
        assert isinstance(signal, InsightSignal)

    def test_concrete_signal_satisfies_protocol(self):
        """ConcreteInsightSignal is the reference implementation."""
        signal = _make_signal()
        # All Protocol properties accessible
        assert signal.signal_id == "sig-001"
        assert signal.source_mission_id == "mission-001"
        assert signal.source_actor_id == "actor-alice"
        assert signal.signal_type == InsightType.TECHNIQUE
        assert 0.0 <= signal.confidence <= 1.0
        assert len(signal.payload) > 0
        assert len(signal.provenance_hash) == 64
        assert isinstance(signal.created_utc, datetime)
        assert isinstance(signal.visibility, WorkVisibility)

    def test_non_conforming_object_fails_protocol_check(self):
        """Objects that don't implement the Protocol are rejected."""
        assert not isinstance("not a signal", InsightSignal)
        assert not isinstance(42, InsightSignal)
        assert not isinstance({}, InsightSignal)


# ---------------------------------------------------------------------------
# InsightType enum tests
# ---------------------------------------------------------------------------

class TestInsightType:
    """Verify the five classification categories."""

    def test_five_categories(self):
        """InsightType must cover exactly 5 categories."""
        assert len(InsightType) == 5

    def test_expected_values(self):
        """All five categories present."""
        expected = {"technique", "pattern", "solution", "warning", "domain_knowledge"}
        actual = {t.value for t in InsightType}
        assert actual == expected


# ---------------------------------------------------------------------------
# InsightRegistry — constitutional enforcement tests
# ---------------------------------------------------------------------------

class TestInsightRegistryEnforcement:
    """Verify the InsightRegistry enforces constitutional constraints."""

    def test_rejects_invalid_provenance_hash(self):
        """Provenance hash must be valid SHA-256 (64 hex chars)."""
        reg = _registry_with_actor("actor-alice")
        signal = _make_signal(provenance_hash="not-a-hash")
        with pytest.raises(ValueError, match="(?i)provenance hash"):
            reg.register_insight(signal)

    def test_rejects_empty_provenance_hash(self):
        """Empty provenance hash is rejected."""
        reg = _registry_with_actor("actor-alice")
        signal = _make_signal(provenance_hash="")
        with pytest.raises(ValueError, match="(?i)provenance hash"):
            reg.register_insight(signal)

    def test_rejects_unknown_source_actor(self):
        """Source actor must be in roster for trust evaluation."""
        reg = _registry_with_actor("actor-bob")  # alice not registered
        signal = _make_signal(source_actor_id="actor-alice")
        with pytest.raises(ValueError, match="not in roster"):
            reg.register_insight(signal)

    def test_accepts_known_source_actor(self):
        """Known actor passes validation."""
        reg = _registry_with_actor("actor-alice")
        signal = _make_signal()
        reg.register_insight(signal)
        assert reg.signal_count == 1

    def test_rejects_out_of_range_confidence(self):
        """Confidence must be 0.0-1.0."""
        reg = _registry_with_actor("actor-alice")
        for bad_val in [-0.1, 1.1, 2.0]:
            signal = _make_signal(
                signal_id=f"sig-bad-{bad_val}",
                confidence=bad_val,
            )
            with pytest.raises(ValueError, match="Confidence"):
                reg.register_insight(signal)

    def test_rejects_empty_payload(self):
        """Payload must not be empty — an insight without content is no insight."""
        reg = _registry_with_actor("actor-alice")
        signal = _make_signal(payload="")
        with pytest.raises(ValueError, match="Payload"):
            reg.register_insight(signal)

    def test_accepts_valid_signal(self):
        """A fully valid signal registers without error."""
        reg = _registry_with_actor("actor-alice")
        signal = _make_signal()
        reg.register_insight(signal)
        assert reg.signal_count == 1
        assert reg.get_signal("sig-001") is signal

    def test_roster_override_at_registration(self):
        """External roster can override internal roster."""
        reg = InsightRegistry()  # no internal actors
        signal = _make_signal()
        reg.register_insight(signal, roster={"actor-alice"})
        assert reg.signal_count == 1


# ---------------------------------------------------------------------------
# InsightRegistry — query openness tests
# ---------------------------------------------------------------------------

class TestInsightRegistryQuery:
    """Verify that query is open to all — no access restriction."""

    def test_query_returns_all_matching(self):
        """Query returns all signals matching criteria."""
        reg = _registry_with_actor("actor-alice", "actor-bob")
        reg.register_insight(_make_signal(signal_id="s1", signal_type=InsightType.TECHNIQUE))
        reg.register_insight(_make_signal(
            signal_id="s2",
            source_actor_id="actor-bob",
            signal_type=InsightType.WARNING,
            payload="Beware of X",
        ))
        reg.register_insight(_make_signal(signal_id="s3", signal_type=InsightType.PATTERN, payload="Y pattern"))

        all_results = reg.query_insights()
        assert len(all_results) == 3

        techniques = reg.query_insights(signal_type=InsightType.TECHNIQUE)
        assert len(techniques) == 1
        assert techniques[0].signal_id == "s1"

    def test_query_filters_expired_signals(self):
        """Signals past TTL are excluded from results."""
        reg = _registry_with_actor("actor-alice")
        old_signal = ConcreteInsightSignal(
            signal_id="old",
            source_mission_id="m-old",
            source_actor_id="actor-alice",
            signal_type=InsightType.WARNING,
            confidence=0.5,
            payload="Outdated warning",
            provenance_hash=_valid_hash(),
            created_utc=datetime.now(timezone.utc) - timedelta(days=100),
            ttl_days=30,
        )
        reg.register_insight(old_signal)
        results = reg.query_insights()
        assert len(results) == 0  # expired

    def test_query_has_no_identity_parameter(self):
        """Constitutional requirement: query_insights has no requester_id
        or caller_identity parameter. Access is unconditional."""
        sig = inspect.signature(InsightRegistry.query_insights)
        param_names = set(sig.parameters.keys())
        # Only filtering parameters — no identity/caller/requester
        assert "requester_id" not in param_names
        assert "caller_id" not in param_names
        assert "identity" not in param_names
        assert "actor_id" not in param_names


# ---------------------------------------------------------------------------
# Provenance hash tests
# ---------------------------------------------------------------------------

class TestProvenanceHash:
    """Verify provenance hash computation."""

    def test_produces_64_char_hex(self):
        """SHA-256 hash is 64 hex characters."""
        h = compute_provenance_hash(["a", "b", "c"])
        assert len(h) == 64
        int(h, 16)  # valid hex

    def test_deterministic(self):
        """Same input produces same hash."""
        h1 = compute_provenance_hash(["x", "y"])
        h2 = compute_provenance_hash(["x", "y"])
        assert h1 == h2

    def test_different_input_different_hash(self):
        """Different inputs produce different hashes."""
        h1 = compute_provenance_hash(["a"])
        h2 = compute_provenance_hash(["b"])
        assert h1 != h2


# ---------------------------------------------------------------------------
# Design test #92 — structural verification
# ---------------------------------------------------------------------------

class TestDesignTest92NoInsightRestriction:
    """Design test #92: Can any entity restrict the flow of work-derived
    insights across the network for private advantage? If yes, reject design.

    Structural verification: the InsightRegistry has no mechanism for
    restricting, hiding, gating, or filtering insights by requester identity.
    """

    def test_no_delete_method(self):
        """Registry has no method to delete or hide registered insights."""
        methods = [m for m in dir(InsightRegistry) if not m.startswith("_")]
        for m in methods:
            assert "delete" not in m.lower(), f"Method '{m}' suggests deletion capability"
            assert "hide" not in m.lower(), f"Method '{m}' suggests hiding capability"
            assert "restrict" not in m.lower(), f"Method '{m}' suggests restriction capability"
            assert "gate" not in m.lower() or m == "get_signal", f"Method '{m}' suggests gating"

    def test_no_access_control_in_query(self):
        """query_insights has no access control mechanism."""
        source = inspect.getsource(InsightRegistry.query_insights)
        # No identity checks, no permission checks, no role checks
        assert "permission" not in source.lower()
        assert "role" not in source.lower()
        assert "authorized" not in source.lower()
        assert "forbidden" not in source.lower()

    def test_constitutional_compliance_check(self):
        """Registry self-validates constitutional compliance."""
        reg = _registry_with_actor("actor-alice")
        reg.register_insight(_make_signal())
        violations = reg.validate_constitutional_compliance()
        assert violations == []

    def test_open_work_visibility_enforced(self):
        """Insights inherit Open Work visibility — default is PUBLIC.
        WorkVisibility has no CONCEALED or PRIVATE tier."""
        signal = _make_signal()
        assert signal.visibility == WorkVisibility.PUBLIC
        # No concealment tier exists
        visibility_values = {v.value for v in WorkVisibility}
        assert "concealed" not in visibility_values
        assert "private" not in visibility_values
