"""Tests for Payment Infrastructure Sovereignty — constitutional amendment.

Proves constitutional invariants:
- No single payment provider can shut down Genesis escrow operations
  (design test #82).
- Genesis cannot become dependent on a single payment rail with no
  tested fallback (design test #83).
- No external custodian can hold Genesis funds or freeze/redirect them
  (design test #84).
- Adding or removing a payment rail requires zero changes to escrow
  logic, commission computation, or GCF contribution code
  (design test #85).

Also covers:
- PaymentRail Protocol is runtime_checkable
- PaymentRailRegistry enforces sovereignty assessment
- PaymentRailRegistry enforces independence (no shared issuing entity)
- PaymentRailRegistry enforces constitutional minimums on removal
- PaymentRailRegistry escalates minimum at First Light
- PaymentRailRegistryConfig loads from constitutional_params.json
- SovereigntyAssessment three-criteria evaluation

Design test #82: Can any single payment provider, stablecoin issuer,
or financial intermediary freeze, restrict, or shut down Genesis escrow
operations? If yes, reject design.

Design test #83: Can Genesis become operationally dependent on a single
payment rail with no tested fallback? If yes, reject design.

Design test #84: Can an external custodian hold Genesis funds or possess
the ability to freeze or redirect them? If yes, reject design.

Design test #85: Does adding or removing a payment rail require changes
to escrow logic, commission computation, or GCF contribution code? If
yes, reject design.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pytest

from genesis.compensation.payment_rail import (
    PaymentRail,
    PaymentRailRegistry,
    PaymentRailRegistryConfig,
    RailCapability,
    RailType,
    SovereigntyAssessment,
)

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "genesis"


# ---- Helpers: mock payment rails for testing ----


@dataclass
class MockRail:
    """A mock payment rail implementing the PaymentRail Protocol."""

    _rail_id: str
    _rail_type: RailType
    _issuing_entity: Optional[str]
    _capabilities: RailCapability
    _sovereignty: SovereigntyAssessment
    _healthy: bool = True

    @property
    def rail_id(self) -> str:
        return self._rail_id

    @property
    def rail_type(self) -> RailType:
        return self._rail_type

    @property
    def issuing_entity(self) -> Optional[str]:
        return self._issuing_entity

    @property
    def capabilities(self) -> RailCapability:
        return self._capabilities

    @property
    def sovereignty_assessment(self) -> SovereigntyAssessment:
        return self._sovereignty

    def health_check(self) -> bool:
        return self._healthy


def _sovereign_assessment() -> SovereigntyAssessment:
    """Assessment that passes all three criteria."""
    return SovereigntyAssessment(
        no_leverage=True,
        no_surveillance=True,
        no_lock_in=True,
    )


def _default_capabilities() -> RailCapability:
    return RailCapability(
        can_lock_escrow=True,
        can_release_to_address=True,
        can_refund_to_address=True,
    )


def _btc_rail() -> MockRail:
    """Decentralised BTC rail — no single entity can freeze."""
    return MockRail(
        _rail_id="btc_native",
        _rail_type=RailType.DECENTRALISED,
        _issuing_entity=None,
        _capabilities=_default_capabilities(),
        _sovereignty=_sovereign_assessment(),
    )


def _eth_rail() -> MockRail:
    """Decentralised ETH rail — no single entity can freeze."""
    return MockRail(
        _rail_id="eth_native",
        _rail_type=RailType.DECENTRALISED,
        _issuing_entity=None,
        _capabilities=_default_capabilities(),
        _sovereignty=_sovereign_assessment(),
    )


def _usdc_rail() -> MockRail:
    """Centralised stablecoin — issuer (Circle) can freeze."""
    return MockRail(
        _rail_id="eth_usdc",
        _rail_type=RailType.CENTRALISED_STABLECOIN,
        _issuing_entity="circle",
        _capabilities=_default_capabilities(),
        _sovereignty=_sovereign_assessment(),
    )


def _stripe_rail() -> MockRail:
    """Fiat gateway — Stripe can restrict."""
    return MockRail(
        _rail_id="stripe_acs",
        _rail_type=RailType.FIAT_GATEWAY,
        _issuing_entity="stripe",
        _capabilities=_default_capabilities(),
        _sovereignty=_sovereign_assessment(),
    )


def _default_config() -> PaymentRailRegistryConfig:
    return PaymentRailRegistryConfig(
        minimum_independent_rails=2,
        minimum_independent_rails_at_first_light=3,
        migration_days=30,
    )


def _registry_with_two_rails() -> PaymentRailRegistry:
    """Registry meeting G0 minimum: BTC + USDC (two independent rails)."""
    registry = PaymentRailRegistry(_default_config())
    registry.register_rail(_btc_rail())
    registry.register_rail(_usdc_rail())
    return registry


# ===========================================================================
# Design Test #82: No single provider shutdown
# ===========================================================================


class TestDesignTest82NoSingleProviderShutdown:
    """Can any single payment provider, stablecoin issuer, or financial
    intermediary freeze, restrict, or shut down Genesis escrow operations?
    If yes, reject design.

    Verification strategy:
    - Escrow module contains zero references to any payment provider,
      stablecoin issuer, or financial intermediary
    - Escrow module has no network calls or external service dependencies
    - EscrowManager is a pure state machine with zero side effects
    """

    def test_escrow_has_no_provider_references(self) -> None:
        """Escrow source code must not reference any specific provider."""
        escrow_path = SRC_DIR / "compensation" / "escrow.py"
        source = escrow_path.read_text()
        # No provider names in escrow module
        provider_names = [
            "stripe", "circle", "tether", "coinbase", "binance",
            "paypal", "visa", "mastercard", "usdc", "usdt",
        ]
        source_lower = source.lower()
        for name in provider_names:
            assert name not in source_lower, (
                f"Escrow module references provider '{name}' — "
                f"violates design test #82 (no single-provider dependency)"
            )

    def test_escrow_has_no_network_imports(self) -> None:
        """Escrow module must not import networking libraries."""
        escrow_path = SRC_DIR / "compensation" / "escrow.py"
        tree = ast.parse(escrow_path.read_text())
        network_modules = {
            "requests", "httpx", "aiohttp", "urllib", "socket",
            "http", "websocket", "grpc",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root not in network_modules, (
                        f"Escrow module imports '{alias.name}' — "
                        f"pure state machine must have no network dependencies"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    assert root not in network_modules, (
                        f"Escrow module imports from '{node.module}' — "
                        f"pure state machine must have no network dependencies"
                    )

    def test_escrow_is_pure_state_machine(self) -> None:
        """EscrowManager must be constructible with zero external deps."""
        from genesis.compensation.escrow import EscrowManager
        # Must work with zero arguments — no configs, no connections
        mgr = EscrowManager()
        assert mgr is not None

    def test_sovereignty_assessment_rejects_leverage(self) -> None:
        """A rail where provider has leverage must fail sovereignty test."""
        assessment = SovereigntyAssessment(
            no_leverage=False,
            no_surveillance=True,
            no_lock_in=True,
        )
        assert not assessment.passes
        assert any("LEVERAGE" in f for f in assessment.failures)


# ===========================================================================
# Design Test #83: Multi-rail fallback
# ===========================================================================


class TestDesignTest83MultiRailFallback:
    """Can Genesis become operationally dependent on a single payment
    rail with no tested fallback? If yes, reject design.

    Verification strategy:
    - Constitutional minimum exists and is >= 2
    - Escalated minimum at First Light is >= 3
    - Registry enforces minimum on removal
    - Registry requires at least one decentralised rail
    """

    def test_constitutional_minimum_exists(self) -> None:
        """constitutional_params.json must define MINIMUM_INDEPENDENT_PAYMENT_RAILS."""
        params = json.loads((CONFIG_DIR / "constitutional_params.json").read_text())
        ep = params["entrenched_provisions"]
        assert "MINIMUM_INDEPENDENT_PAYMENT_RAILS" in ep
        assert ep["MINIMUM_INDEPENDENT_PAYMENT_RAILS"] >= 2

    def test_constitutional_minimum_at_first_light(self) -> None:
        """Escalated minimum at First Light must be >= 3."""
        params = json.loads((CONFIG_DIR / "constitutional_params.json").read_text())
        ep = params["entrenched_provisions"]
        assert "MINIMUM_INDEPENDENT_PAYMENT_RAILS_AT_FIRST_LIGHT" in ep
        assert ep["MINIMUM_INDEPENDENT_PAYMENT_RAILS_AT_FIRST_LIGHT"] >= 3

    def test_migration_days_defined(self) -> None:
        """PAYMENT_RAIL_MIGRATION_DAYS must exist and be reasonable."""
        params = json.loads((CONFIG_DIR / "constitutional_params.json").read_text())
        ep = params["entrenched_provisions"]
        assert "PAYMENT_RAIL_MIGRATION_DAYS" in ep
        assert ep["PAYMENT_RAIL_MIGRATION_DAYS"] <= 90  # must be actionable

    def test_registry_enforces_minimum_on_removal(self) -> None:
        """Cannot remove a rail if it would drop below constitutional minimum."""
        registry = _registry_with_two_rails()
        # 2 rails, minimum is 2 — cannot remove either
        with pytest.raises(ValueError, match="below constitutional minimum"):
            registry.remove_rail("btc_native")

    def test_registry_allows_removal_above_minimum(self) -> None:
        """Can remove a rail if count remains >= minimum after removal."""
        registry = _registry_with_two_rails()
        registry.register_rail(_stripe_rail())  # Now 3 rails, minimum 2
        registry.remove_rail("stripe_acs")  # Back to 2, still >= minimum
        assert registry.independent_count == 2

    def test_registry_escalates_at_first_light(self) -> None:
        """First Light escalates the constitutional minimum."""
        registry = _registry_with_two_rails()
        assert registry.active_minimum == 2
        registry.notify_first_light()
        assert registry.active_minimum == 3

    def test_removal_blocked_after_first_light_escalation(self) -> None:
        """After First Light, 3-rail minimum blocks removal down to 2."""
        registry = _registry_with_two_rails()
        registry.register_rail(_stripe_rail())  # 3 rails
        registry.notify_first_light()  # minimum now 3
        with pytest.raises(ValueError, match="below constitutional minimum"):
            registry.remove_rail("stripe_acs")

    def test_at_least_one_decentralised_required(self) -> None:
        """Cannot remove the last decentralised rail."""
        config = PaymentRailRegistryConfig(
            minimum_independent_rails=1,
            minimum_independent_rails_at_first_light=3,
            migration_days=30,
        )
        registry = PaymentRailRegistry(config)
        registry.register_rail(_btc_rail())
        registry.register_rail(_usdc_rail())
        # Removing the only decentralised rail must fail
        with pytest.raises(ValueError, match="last decentralised rail"):
            registry.remove_rail("btc_native")

    def test_payment_sovereignty_flag_entrenched(self) -> None:
        """PAYMENT_SOVEREIGNTY must be true in entrenched provisions."""
        params = json.loads((CONFIG_DIR / "constitutional_params.json").read_text())
        ep = params["entrenched_provisions"]
        assert ep.get("PAYMENT_SOVEREIGNTY") is True


# ===========================================================================
# Design Test #84: Self-custody
# ===========================================================================


class TestDesignTest84SelfCustody:
    """Can an external custodian hold Genesis funds or possess the
    ability to freeze or redirect them? If yes, reject design.

    Verification strategy:
    - Escrow module has no custodian references
    - GCF module has no custodian references
    - No third-party key management in financial modules
    """

    def test_escrow_no_custody_references(self) -> None:
        """Escrow module must not reference external custodians."""
        escrow_path = SRC_DIR / "compensation" / "escrow.py"
        source = escrow_path.read_text().lower()
        custody_terms = [
            "custodian", "custody_provider", "third_party_wallet",
            "hosted_wallet", "managed_wallet",
        ]
        for term in custody_terms:
            assert term not in source, (
                f"Escrow module references '{term}' — "
                f"violates design test #84 (self-custody)"
            )

    def test_gcf_no_custody_dependencies(self) -> None:
        """GCF module must not depend on external custody services.

        Note: the GCF docstring says "No bank. No custodian." — this is
        a sovereignty affirmation, not a dependency. We check for custody
        *service* patterns (imports, class references), not docstring
        language that affirms self-custody.
        """
        gcf_path = SRC_DIR / "compensation" / "gcf.py"
        tree = ast.parse(gcf_path.read_text())
        custody_modules = {
            "custody", "custodial", "fireblocks", "bitgo",
            "copper", "anchorage",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                module_lower = node.module.lower()
                for term in custody_modules:
                    assert term not in module_lower, (
                        f"GCF imports from '{node.module}' — "
                        f"violates design test #84 (self-custody)"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name_lower = alias.name.lower()
                    for term in custody_modules:
                        assert term not in name_lower, (
                            f"GCF imports '{alias.name}' — "
                            f"violates design test #84 (self-custody)"
                        )

    def test_sovereignty_assessment_rejects_lock_in(self) -> None:
        """A rail with lock-in (cannot exit within migration window) must fail."""
        assessment = SovereigntyAssessment(
            no_leverage=True,
            no_surveillance=True,
            no_lock_in=False,
        )
        assert not assessment.passes
        assert any("LOCK-IN" in f for f in assessment.failures)

    def test_sovereignty_assessment_rejects_surveillance(self) -> None:
        """A rail with surveillance beyond settlement must fail."""
        assessment = SovereigntyAssessment(
            no_leverage=True,
            no_surveillance=False,
            no_lock_in=True,
        )
        assert not assessment.passes
        assert any("SURVEILLANCE" in f for f in assessment.failures)


# ===========================================================================
# Design Test #85: Rail-agnostic architecture
# ===========================================================================


class TestDesignTest85RailAgnosticArchitecture:
    """Does adding or removing a payment rail require changes to escrow
    logic, commission computation, or GCF contribution code? If yes,
    reject design.

    Verification strategy:
    - PaymentRail Protocol exists and is runtime_checkable
    - Escrow module imports nothing from payment_rail module
    - Commission engine imports nothing from payment_rail module
    - GCF module imports nothing from payment_rail module
    - Registry enforces sovereignty assessment gate on registration
    - Registry enforces independence (no shared issuing entity)
    """

    def test_payment_rail_protocol_exists(self) -> None:
        """PaymentRail Protocol must exist and be runtime_checkable."""
        assert isinstance(PaymentRail, type)
        rail = _btc_rail()
        assert isinstance(rail, PaymentRail)

    def test_escrow_does_not_import_payment_rail(self) -> None:
        """Escrow module must have zero imports from payment_rail.

        This is the architectural proof: the escrow state machine is
        structurally independent of any payment rail. The registry is
        the bridge — escrow never touches it.
        """
        escrow_path = SRC_DIR / "compensation" / "escrow.py"
        tree = ast.parse(escrow_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "payment_rail" not in node.module, (
                    f"Escrow imports from '{node.module}' — "
                    f"escrow must be structurally independent of payment rails"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert "payment_rail" not in alias.name, (
                        f"Escrow imports '{alias.name}' — "
                        f"escrow must be structurally independent of payment rails"
                    )

    def test_commission_engine_does_not_import_payment_rail(self) -> None:
        """Commission engine must have zero imports from payment_rail."""
        engine_path = SRC_DIR / "compensation" / "engine.py"
        tree = ast.parse(engine_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "payment_rail" not in node.module, (
                    f"Commission engine imports from '{node.module}' — "
                    f"must be structurally independent of payment rails"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert "payment_rail" not in alias.name, (
                        f"Commission engine imports '{alias.name}' — "
                        f"must be structurally independent of payment rails"
                    )

    def test_gcf_does_not_import_payment_rail(self) -> None:
        """GCF module must have zero imports from payment_rail."""
        gcf_path = SRC_DIR / "compensation" / "gcf.py"
        tree = ast.parse(gcf_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "payment_rail" not in node.module, (
                    f"GCF imports from '{node.module}' — "
                    f"must be structurally independent of payment rails"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert "payment_rail" not in alias.name, (
                        f"GCF imports '{alias.name}' — "
                        f"must be structurally independent of payment rails"
                    )

    def test_registry_rejects_non_sovereign_rail(self) -> None:
        """Registry must refuse rails that fail sovereignty assessment."""
        registry = PaymentRailRegistry(_default_config())
        bad_rail = MockRail(
            _rail_id="bad_provider",
            _rail_type=RailType.FIAT_GATEWAY,
            _issuing_entity="bad_corp",
            _capabilities=_default_capabilities(),
            _sovereignty=SovereigntyAssessment(
                no_leverage=False,
                no_surveillance=True,
                no_lock_in=True,
            ),
        )
        with pytest.raises(ValueError, match="fails sovereignty assessment"):
            registry.register_rail(bad_rail)

    def test_registry_rejects_shared_issuing_entity(self) -> None:
        """Two rails from the same issuing entity violate independence."""
        registry = PaymentRailRegistry(_default_config())
        registry.register_rail(_usdc_rail())  # issuing_entity = "circle"
        # Second Circle-issued rail must be rejected
        usdc_v2 = MockRail(
            _rail_id="eth_usdc_v2",
            _rail_type=RailType.CENTRALISED_STABLECOIN,
            _issuing_entity="circle",
            _capabilities=_default_capabilities(),
            _sovereignty=_sovereign_assessment(),
        )
        with pytest.raises(ValueError, match="shares issuing entity"):
            registry.register_rail(usdc_v2)

    def test_decentralised_rails_are_independent(self) -> None:
        """Multiple decentralised rails (no issuing entity) can coexist."""
        registry = PaymentRailRegistry(_default_config())
        registry.register_rail(_btc_rail())
        registry.register_rail(_eth_rail())
        assert registry.independent_count == 2

    def test_registry_config_loads_from_constitutional_params(self) -> None:
        """PaymentRailRegistryConfig.from_constitutional_params() must work."""
        config = PaymentRailRegistryConfig.from_constitutional_params()
        assert config.minimum_independent_rails >= 2
        assert config.minimum_independent_rails_at_first_light >= 3
        assert config.migration_days > 0

    def test_validate_compliance_reports_violations(self) -> None:
        """validate_constitutional_compliance catches all violation types."""
        config = PaymentRailRegistryConfig(
            minimum_independent_rails=3,
            minimum_independent_rails_at_first_light=5,
            migration_days=30,
        )
        registry = PaymentRailRegistry(config)
        registry.register_rail(_btc_rail())  # only 1, minimum 3
        violations = registry.validate_constitutional_compliance()
        assert any("Below minimum" in v for v in violations)

    def test_unhealthy_rail_reported(self) -> None:
        """validate_constitutional_compliance reports unhealthy rails."""
        registry = _registry_with_two_rails()
        # Make BTC unhealthy via a new unhealthy rail
        sick_rail = MockRail(
            _rail_id="sick_rail",
            _rail_type=RailType.FIAT_GATEWAY,
            _issuing_entity="sick_corp",
            _capabilities=_default_capabilities(),
            _sovereignty=_sovereign_assessment(),
            _healthy=False,
        )
        registry.register_rail(sick_rail)
        violations = registry.validate_constitutional_compliance()
        assert any("unhealthy" in v for v in violations)

    def test_healthy_rails_filters_correctly(self) -> None:
        """healthy_rails() must return only operational rails."""
        registry = _registry_with_two_rails()
        sick_rail = MockRail(
            _rail_id="sick_rail",
            _rail_type=RailType.FIAT_GATEWAY,
            _issuing_entity="sick_corp",
            _capabilities=_default_capabilities(),
            _sovereignty=_sovereign_assessment(),
            _healthy=False,
        )
        registry.register_rail(sick_rail)
        healthy = registry.healthy_rails()
        assert len(healthy) == 2  # btc + usdc healthy, sick excluded
        ids = {r.rail_id for r in healthy}
        assert "sick_rail" not in ids
