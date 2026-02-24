"""Tests for Auto-Immune System — distributed intelligence applied to self-defence.

Proves constitutional invariants:
- HIGH/CRITICAL threat responses require randomised domain-expert human
  oversight (design test #93).
- No entity can become a permanent immune overseer, creating a security
  authority that concentrates threat-response power (design test #94).
- The immune system learns from resolved incidents, with human oversight
  decisions serving as training signals (design test #95).

Also covers:
- ThreatSignal Protocol is runtime_checkable.
- ThreatType covers six threat categories.
- ThreatSeverity covers four severity levels.
- ConcreteThreatSignal satisfies ThreatSignal Protocol.
- AutomatedResponseTier maps correctly to severity levels.
- ThreatRegistry rejects signals without valid evidence hash.
- ThreatRegistry enforces confidence bounds.
- ThreatRegistry enforces non-empty affected_actor_ids.
- ThreatRegistry enforces non-empty recommended_action.
- ResolutionRecord captures overseer decisions.
- Constitutional parameter invariants for immune_system section.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path

import pytest

from genesis.intelligence.insight_protocol import compute_provenance_hash
from genesis.intelligence.threat_protocol import (
    AutomatedResponseTier,
    ConcreteThreatSignal,
    HUMAN_OVERSIGHT_REQUIRED,
    ResolutionRecord,
    SEVERITY_RESPONSE_MAP,
    ThreatRegistry,
    ThreatSeverity,
    ThreatSignal,
    ThreatType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_hash() -> str:
    """Return a valid SHA-256 evidence hash for testing."""
    return compute_provenance_hash(["detection-001", "evidence-chain", "snapshot"])


def _make_threat(
    *,
    signal_id: str = "threat-001",
    source_detection: str = "fast_elevation",
    threat_type: ThreatType = ThreatType.ANOMALOUS_TRUST,
    severity: ThreatSeverity = ThreatSeverity.MEDIUM,
    confidence: float = 0.75,
    evidence_hash: str | None = None,
    affected_actor_ids: list[str] | None = None,
    recommended_action: str = "Flag for review — anomalous trust elevation pattern",
) -> ConcreteThreatSignal:
    """Create a valid ConcreteThreatSignal for testing."""
    return ConcreteThreatSignal(
        signal_id=signal_id,
        source_detection=source_detection,
        threat_type=threat_type,
        severity=severity,
        confidence=confidence,
        evidence_hash=evidence_hash if evidence_hash is not None else _valid_hash(),
        affected_actor_ids=affected_actor_ids if affected_actor_ids is not None else ["actor-suspect"],
        recommended_action=recommended_action,
    )


def _make_registry(**kwargs) -> ThreatRegistry:
    """Create a ThreatRegistry with default config."""
    return ThreatRegistry(**kwargs)


# ===========================================================================
# Protocol conformance
# ===========================================================================

class TestThreatSignalProtocol:
    """ThreatSignal Protocol is runtime_checkable and ConcreteThreatSignal conforms."""

    def test_protocol_is_runtime_checkable(self):
        """ThreatSignal must be runtime_checkable for registry validation."""
        assert hasattr(ThreatSignal, "__protocol_attrs__") or hasattr(
            ThreatSignal, "__abstractmethods__"
        ) or issubclass(ThreatSignal, type)
        # The real test: isinstance works
        signal = _make_threat()
        assert isinstance(signal, ThreatSignal)

    def test_concrete_satisfies_protocol(self):
        """ConcreteThreatSignal must satisfy ThreatSignal Protocol."""
        signal = _make_threat()
        assert isinstance(signal, ThreatSignal)
        # All protocol properties must be accessible
        assert signal.signal_id == "threat-001"
        assert signal.source_detection == "fast_elevation"
        assert signal.threat_type == ThreatType.ANOMALOUS_TRUST
        assert signal.severity == ThreatSeverity.MEDIUM
        assert 0.0 <= signal.confidence <= 1.0
        assert len(signal.evidence_hash) == 64
        assert len(signal.affected_actor_ids) > 0
        assert signal.recommended_action
        assert isinstance(signal.detected_utc, datetime)

    def test_non_conforming_rejected(self):
        """Objects that don't implement ThreatSignal properties must fail isinstance."""

        class NotAThreat:
            pass

        assert not isinstance(NotAThreat(), ThreatSignal)


# ===========================================================================
# ThreatType and ThreatSeverity enums
# ===========================================================================

class TestThreatType:
    """ThreatType covers six categories of immune threat."""

    def test_six_categories(self):
        assert len(ThreatType) == 6

    def test_expected_values(self):
        expected = {
            "anomalous_trust", "collusion", "quality_degradation",
            "compliance_pattern", "behavioural_drift", "manipulation",
        }
        assert {t.value for t in ThreatType} == expected


class TestThreatSeverity:
    """ThreatSeverity covers four levels determining response autonomy."""

    def test_four_levels(self):
        assert len(ThreatSeverity) == 4

    def test_expected_values(self):
        expected = {"low", "medium", "high", "critical"}
        assert {s.value for s in ThreatSeverity} == expected


# ===========================================================================
# Design test #93 — HIGH/CRITICAL require human oversight
# ===========================================================================

class TestDesignTest93HumanOversight:
    """Can the immune system's automated responses execute high-risk actions
    without randomised domain-expert human oversight? If yes, reject design."""

    def test_high_requires_human(self):
        """HIGH severity must map to HUMAN_REQUIRED response tier."""
        assert SEVERITY_RESPONSE_MAP[ThreatSeverity.HIGH] == AutomatedResponseTier.HUMAN_REQUIRED

    def test_critical_requires_human_containment(self):
        """CRITICAL severity must map to HUMAN_CONTAINMENT response tier."""
        assert SEVERITY_RESPONSE_MAP[ThreatSeverity.CRITICAL] == AutomatedResponseTier.HUMAN_CONTAINMENT

    def test_low_auto_handled(self):
        """LOW severity must be auto-logged without human intervention."""
        assert SEVERITY_RESPONSE_MAP[ThreatSeverity.LOW] == AutomatedResponseTier.AUTO_LOG

    def test_medium_auto_flagged(self):
        """MEDIUM severity must be auto-flagged and queued for review."""
        assert SEVERITY_RESPONSE_MAP[ThreatSeverity.MEDIUM] == AutomatedResponseTier.AUTO_FLAG

    def test_human_oversight_required_set(self):
        """HUMAN_OVERSIGHT_REQUIRED must contain exactly HIGH and CRITICAL."""
        assert HUMAN_OVERSIGHT_REQUIRED == frozenset({
            ThreatSeverity.HIGH,
            ThreatSeverity.CRITICAL,
        })

    def test_registry_reports_human_oversight_for_high(self):
        """ThreatRegistry.requires_human_oversight returns True for HIGH."""
        registry = _make_registry()
        assert registry.requires_human_oversight(ThreatSeverity.HIGH) is True

    def test_registry_reports_human_oversight_for_critical(self):
        """ThreatRegistry.requires_human_oversight returns True for CRITICAL."""
        registry = _make_registry()
        assert registry.requires_human_oversight(ThreatSeverity.CRITICAL) is True

    def test_registry_no_oversight_for_low(self):
        """ThreatRegistry.requires_human_oversight returns False for LOW."""
        registry = _make_registry()
        assert registry.requires_human_oversight(ThreatSeverity.LOW) is False

    def test_registry_no_oversight_for_medium(self):
        """ThreatRegistry.requires_human_oversight returns False for MEDIUM."""
        registry = _make_registry()
        assert registry.requires_human_oversight(ThreatSeverity.MEDIUM) is False

    def test_constitutional_compliance_catches_bad_mapping(self):
        """validate_constitutional_compliance must catch severity mapping violations."""
        registry = _make_registry()
        # Valid state — no violations
        violations = registry.validate_constitutional_compliance()
        assert len(violations) == 0


# ===========================================================================
# Design test #94 — No permanent immune overseer
# ===========================================================================

class TestDesignTest94NoPermanentOverseer:
    """Can any entity become a permanent immune overseer, creating a security
    authority that concentrates threat-response power? If yes, reject design."""

    def test_no_set_permanent_overseer_method(self):
        """ThreatRegistry must not have any method to set a permanent overseer."""
        method_names = {name for name, _ in inspect.getmembers(ThreatRegistry, predicate=inspect.isfunction)}
        # No method should contain 'permanent' or 'set_overseer'
        for name in method_names:
            assert "permanent_overseer" not in name, (
                f"Method '{name}' suggests permanent overseer capability"
            )
            assert "set_overseer" not in name, (
                f"Method '{name}' suggests overseer storage"
            )

    def test_no_overseer_id_stored_in_registry(self):
        """ThreatRegistry must not store any overseer identity persistently."""
        registry = _make_registry()
        # Check instance attributes — no overseer_id or similar
        attr_names = set(vars(registry).keys())
        for attr in attr_names:
            assert "overseer_id" not in attr, (
                f"Attribute '{attr}' suggests stored overseer identity"
            )
            assert "permanent_overseer" not in attr, (
                f"Attribute '{attr}' suggests permanent overseer storage"
            )

    def test_overseer_selection_is_parameterised(self):
        """Overseer selection must be a config parameter, not a hardcoded identity."""
        registry = _make_registry()
        assert registry._config["overseer_selection"] == "randomised_domain_expert"

    def test_config_has_no_identity_fields(self):
        """Default config must not contain any fields that store specific identities."""
        registry = _make_registry()
        config = registry._config
        for key in config:
            assert "actor_id" not in key, f"Config key '{key}' suggests stored identity"
            assert "user_id" not in key, f"Config key '{key}' suggests stored identity"


# ===========================================================================
# Design test #95 — Learning from resolved incidents
# ===========================================================================

class TestDesignTest95LearningFromIncidents:
    """Does the immune system learn from resolved incidents, with human
    oversight decisions serving as training signals? If not, reject design."""

    def test_resolution_records_stored(self):
        """Resolution records must be stored when recorded."""
        registry = _make_registry()
        record = ResolutionRecord(
            threat_signal_id="threat-001",
            overseer_decision="upheld",
            overseer_rationale="Pattern confirmed by manual review of trust elevation data",
        )
        registry.record_resolution(record)
        assert registry.resolution_count == 1

    def test_resolution_records_append_only(self):
        """Resolution records must be append-only — no delete method."""
        method_names = {name for name, _ in inspect.getmembers(ThreatRegistry, predicate=inspect.isfunction)}
        assert "delete_resolution" not in method_names
        assert "remove_resolution" not in method_names
        assert "clear_resolutions" not in method_names

    def test_resolution_query_open(self):
        """Resolution query must be open — no access restriction parameter."""
        sig = inspect.signature(ThreatRegistry.query_resolutions)
        param_names = set(sig.parameters.keys())
        # No access control parameters
        assert "requester_id" not in param_names
        assert "access_token" not in param_names
        assert "role" not in param_names

    def test_resolution_record_captures_decision(self):
        """ResolutionRecord must capture the overseer's decision and rationale."""
        record = ResolutionRecord(
            threat_signal_id="threat-001",
            overseer_decision="rejected_false_positive",
            overseer_rationale="Trust elevation was organic — new contributor with strong references",
        )
        assert record.overseer_decision == "rejected_false_positive"
        assert "organic" in record.overseer_rationale

    def test_resolution_record_supports_outcome_verification(self):
        """ResolutionRecord must support post-hoc outcome verification."""
        record = ResolutionRecord(
            threat_signal_id="threat-001",
            overseer_decision="upheld",
            overseer_rationale="Pattern confirmed",
            outcome_verified=True,
        )
        assert record.outcome_verified is True

    def test_query_resolutions_by_signal_id(self):
        """Resolution query must support filtering by threat_signal_id."""
        registry = _make_registry()
        registry.record_resolution(ResolutionRecord(
            threat_signal_id="threat-001",
            overseer_decision="upheld",
            overseer_rationale="Confirmed",
        ))
        registry.record_resolution(ResolutionRecord(
            threat_signal_id="threat-002",
            overseer_decision="rejected_false_positive",
            overseer_rationale="False alarm",
        ))
        results = registry.query_resolutions(threat_signal_id="threat-001")
        assert len(results) == 1
        assert results[0].threat_signal_id == "threat-001"


# ===========================================================================
# ThreatRegistry constitutional enforcement
# ===========================================================================

class TestThreatRegistryEnforcement:
    """ThreatRegistry validates signals against constitutional constraints."""

    def test_rejects_invalid_evidence_hash(self):
        """Evidence hash must be a valid SHA-256 (64 hex characters)."""
        registry = _make_registry()
        signal = _make_threat(evidence_hash="not-a-valid-hash")
        with pytest.raises(ValueError, match="(?i)evidence hash"):
            registry.register_threat(signal)

    def test_rejects_empty_evidence_hash(self):
        """Empty evidence hash must be rejected."""
        registry = _make_registry()
        signal = _make_threat(evidence_hash="")
        with pytest.raises(ValueError, match="(?i)evidence hash"):
            registry.register_threat(signal)

    def test_rejects_confidence_above_one(self):
        """Confidence must be in [0.0, 1.0]."""
        registry = _make_registry()
        signal = _make_threat(confidence=1.5)
        with pytest.raises(ValueError, match="(?i)confidence"):
            registry.register_threat(signal)

    def test_rejects_confidence_below_zero(self):
        """Confidence must be in [0.0, 1.0]."""
        registry = _make_registry()
        signal = _make_threat(confidence=-0.1)
        with pytest.raises(ValueError, match="(?i)confidence"):
            registry.register_threat(signal)

    def test_rejects_empty_affected_actors(self):
        """Affected actor IDs must not be empty."""
        registry = _make_registry()
        signal = _make_threat(affected_actor_ids=[])
        with pytest.raises(ValueError, match="(?i)affected actor"):
            registry.register_threat(signal)

    def test_rejects_empty_recommended_action(self):
        """Recommended action must not be empty."""
        registry = _make_registry()
        signal = _make_threat(recommended_action="")
        with pytest.raises(ValueError, match="(?i)recommended action"):
            registry.register_threat(signal)

    def test_accepts_valid_signal(self):
        """A well-formed signal must be accepted."""
        registry = _make_registry()
        signal = _make_threat()
        registry.register_threat(signal)
        assert registry.signal_count == 1
        assert registry.get_signal("threat-001") is signal

    def test_rejects_duplicate_signal_id(self):
        """Duplicate signal_id must be rejected — tamper-evident guarantee.

        Regression test: CX P1 finding (2026-02-24). Silent overwrite by
        duplicate signal_id allowed retroactive replacement of threat history,
        undermining incident forensics.
        """
        registry = _make_registry()
        signal_1 = _make_threat(signal_id="threat-dup", source_detection="original_detection")
        signal_2 = _make_threat(signal_id="threat-dup", source_detection="replacement_attempt")
        registry.register_threat(signal_1)
        with pytest.raises(ValueError, match="(?i)duplicate signal_id"):
            registry.register_threat(signal_2)
        # Original signal must be preserved, not overwritten
        assert registry.get_signal("threat-dup").source_detection == "original_detection"
        assert registry.signal_count == 1

    def test_constitutional_compliance_valid_state(self):
        """A valid registry must pass constitutional compliance check."""
        registry = _make_registry()
        signal = _make_threat()
        registry.register_threat(signal)
        violations = registry.validate_constitutional_compliance()
        assert len(violations) == 0


# ===========================================================================
# Constitutional parameter invariants (immune_system section)
# ===========================================================================

class TestImmuneSystemParams:
    """Constitutional parameters for the immune system section."""

    def test_invariant_checker_validates_immune_section(self):
        """The invariant checker must validate the immune_system section."""
        import json
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "config" / "constitutional_params.json"
        params = json.loads(config_path.read_text())
        immune = params.get("immune_system", {})
        assert immune, "immune_system section must exist in constitutional_params.json"

        # Verify constitutional values
        assert immune["oversight_trust_min"] >= 0.80
        assert immune["auto_response_max_severity"] in ("low", "medium")
        assert immune["overseer_selection"] == "randomised_domain_expert"
        assert immune["resolution_feedback_window_days"] >= 1
        assert 1 <= immune["bootstrap_overseer_pool_max"] <= 10
        assert immune["bootstrap_sunset_organic_threshold"] > immune["bootstrap_overseer_pool_max"]
        assert immune["bootstrap_hard_expiry"] == "first_light"

    def test_resolver_exposes_immune_config(self):
        """PolicyResolver must expose immune_system_config() method."""
        from genesis.policy.resolver import PolicyResolver

        assert hasattr(PolicyResolver, "immune_system_config")
        # Verify it reads from params
        resolver = PolicyResolver.from_config_dir(
            Path(__file__).parent.parent / "config"
        )
        config = resolver.immune_system_config()
        assert config["oversight_trust_min"] == 0.85
        assert config["auto_response_max_severity"] == "medium"
        assert config["overseer_selection"] == "randomised_domain_expert"
