"""Payment rail abstraction — constitutional payment infrastructure sovereignty.

This module defines the contract that any payment rail must satisfy and
the registry that enforces constitutional minimums.

Constitutional requirement (entrenched): The escrow state machine must be
structurally independent of any specific payment rail. Settlement is a
pluggable backend behind a common interface. Adding or removing a payment
rail must require zero changes to escrow, commission, or GCF logic.

Design tests: #82 (no single-provider shutdown), #83 (multi-rail fallback),
#84 (self-custody), #85 (rail-agnostic architecture).

Provider evaluation test (three criteria — all must pass):
    (a) No leverage: provider cannot unilaterally restrict Genesis.
    (b) No surveillance beyond settlement: no data extraction beyond
        what the settlement protocol structurally requires.
    (c) No lock-in: Genesis can exit within PAYMENT_RAIL_MIGRATION_DAYS,
        with funds intact, without operational disruption.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Protocol, runtime_checkable


class RailType(str, Enum):
    """Settlement rail classification."""

    DECENTRALISED = "decentralised"
    """No single entity can freeze transactions (e.g., BTC, ETH)."""

    CENTRALISED_STABLECOIN = "centralised_stablecoin"
    """Issuer can freeze at smart-contract level (e.g., USDC, USDT)."""

    FIAT_GATEWAY = "fiat_gateway"
    """Traditional payment processor (e.g., Stripe ACS, x402 fiat bridge)."""


@dataclass(frozen=True)
class RailCapability:
    """What a payment rail can do."""

    can_lock_escrow: bool
    can_release_to_address: bool
    can_refund_to_address: bool
    supports_batch_settlement: bool = False


@dataclass(frozen=True)
class SovereigntyAssessment:
    """Result of the three-criteria provider evaluation test.

    Constitutional requirement: all three criteria must pass before
    any payment rail integration is adopted. If any fails, the
    integration must not proceed.
    """

    no_leverage: bool
    """(a) Provider cannot unilaterally restrict Genesis operations."""

    no_surveillance: bool
    """(b) No data extraction beyond what settlement structurally requires."""

    no_lock_in: bool
    """(c) Can exit within migration window, with funds intact."""

    assessed_utc: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    notes: str = ""

    @property
    def passes(self) -> bool:
        """All three criteria must be satisfied."""
        return self.no_leverage and self.no_surveillance and self.no_lock_in

    @property
    def failures(self) -> List[str]:
        """Human-readable list of failed criteria."""
        result: List[str] = []
        if not self.no_leverage:
            result.append("LEVERAGE: provider can restrict Genesis operations")
        if not self.no_surveillance:
            result.append(
                "SURVEILLANCE: provider extracts data beyond settlement needs",
            )
        if not self.no_lock_in:
            result.append("LOCK-IN: cannot exit within migration window")
        return result


@runtime_checkable
class PaymentRail(Protocol):
    """Abstract contract for payment rail implementations.

    Any payment rail integrated with Genesis must implement this Protocol.
    The escrow module and commission engine never interact with payment
    rails directly — they interact with this interface via the registry.

    Adding a new rail = implement this Protocol + register with
    PaymentRailRegistry. Zero changes to escrow, commission, GCF,
    or any other financial module.
    """

    @property
    def rail_id(self) -> str:
        """Unique identifier (e.g., 'btc_native', 'eth_usdc', 'stripe_acs')."""
        ...

    @property
    def rail_type(self) -> RailType:
        """Classification: decentralised, centralised_stablecoin, fiat_gateway."""
        ...

    @property
    def issuing_entity(self) -> Optional[str]:
        """Entity that controls this rail, or None if decentralised."""
        ...

    @property
    def capabilities(self) -> RailCapability:
        """What operations this rail supports."""
        ...

    @property
    def sovereignty_assessment(self) -> SovereigntyAssessment:
        """Three-criteria provider evaluation test result."""
        ...

    def health_check(self) -> bool:
        """Returns True if this rail is currently operational."""
        ...


@dataclass(frozen=True)
class PaymentRailRegistryConfig:
    """Constitutional configuration for the payment rail registry.

    Loaded from config/constitutional_params.json entrenched_provisions.
    All values are entrenched — reducing any requires 4/5 supermajority
    + 50% participation + 90-day cooling-off + confirmation vote.
    """

    minimum_independent_rails: int
    minimum_independent_rails_at_first_light: int
    migration_days: int
    require_at_least_one_decentralised: bool = True

    @classmethod
    def from_constitutional_params(cls) -> PaymentRailRegistryConfig:
        """Load from constitutional_params.json."""
        config_path = (
            Path(__file__).parent.parent.parent.parent
            / "config"
            / "constitutional_params.json"
        )
        params = json.loads(config_path.read_text())
        ep = params["entrenched_provisions"]
        return cls(
            minimum_independent_rails=ep["MINIMUM_INDEPENDENT_PAYMENT_RAILS"],
            minimum_independent_rails_at_first_light=ep[
                "MINIMUM_INDEPENDENT_PAYMENT_RAILS_AT_FIRST_LIGHT"
            ],
            migration_days=ep["PAYMENT_RAIL_MIGRATION_DAYS"],
        )


class PaymentRailRegistry:
    """Registry of active payment rails with constitutional enforcement.

    Enforces:
    - Minimum number of independent rails (scaled by governance phase)
    - At least one decentralised rail
    - All rails pass three-criteria sovereignty assessment
    - No two rails share the same issuing entity (independence)
    """

    def __init__(self, config: PaymentRailRegistryConfig) -> None:
        self._config = config
        self._rails: Dict[str, PaymentRail] = {}
        self._first_light_achieved = False

    @property
    def config(self) -> PaymentRailRegistryConfig:
        """Current constitutional configuration."""
        return self._config

    @property
    def active_minimum(self) -> int:
        """Current constitutional minimum based on governance phase."""
        if self._first_light_achieved:
            return self._config.minimum_independent_rails_at_first_light
        return self._config.minimum_independent_rails

    @property
    def independent_count(self) -> int:
        """Number of registered independent rails."""
        return len(self._rails)

    @property
    def has_decentralised(self) -> bool:
        """At least one decentralised rail exists."""
        return any(
            r.rail_type == RailType.DECENTRALISED for r in self._rails.values()
        )

    @property
    def first_light_achieved(self) -> bool:
        """Whether First Light has been achieved."""
        return self._first_light_achieved

    def register_rail(self, rail: PaymentRail) -> None:
        """Register a payment rail after sovereignty assessment.

        Raises ValueError if the rail fails the three-criteria test
        or shares an issuing entity with an existing rail.
        """
        if not isinstance(rail, PaymentRail):
            raise TypeError(
                f"Rail must implement PaymentRail Protocol, got {type(rail)}",
            )
        # Sovereignty assessment gate
        if not rail.sovereignty_assessment.passes:
            raise ValueError(
                f"Rail '{rail.rail_id}' fails sovereignty assessment: "
                + "; ".join(rail.sovereignty_assessment.failures),
            )
        # Independence: no two rails from the same issuing entity
        if rail.issuing_entity is not None:
            for existing in self._rails.values():
                if existing.issuing_entity == rail.issuing_entity:
                    raise ValueError(
                        f"Rail '{rail.rail_id}' shares issuing entity "
                        f"'{rail.issuing_entity}' with '{existing.rail_id}' — "
                        f"violates independence requirement",
                    )
        # Duplicate ID check
        if rail.rail_id in self._rails:
            raise ValueError(f"Rail ID already registered: {rail.rail_id}")
        self._rails[rail.rail_id] = rail

    def remove_rail(self, rail_id: str) -> None:
        """Remove a payment rail.

        Raises ValueError if removal would violate constitutional minimums
        or remove the last decentralised rail.
        """
        if rail_id not in self._rails:
            raise ValueError(f"Unknown rail: {rail_id}")
        remaining = len(self._rails) - 1
        if remaining < self.active_minimum:
            raise ValueError(
                f"Cannot remove rail '{rail_id}': would leave {remaining} "
                f"rails, below constitutional minimum of {self.active_minimum}",
            )
        rail = self._rails[rail_id]
        if (
            rail.rail_type == RailType.DECENTRALISED
            and self._config.require_at_least_one_decentralised
        ):
            remaining_decentralised = sum(
                1
                for r in self._rails.values()
                if r.rail_id != rail_id
                and r.rail_type == RailType.DECENTRALISED
            )
            if remaining_decentralised < 1:
                raise ValueError(
                    f"Cannot remove rail '{rail_id}': it is the last "
                    f"decentralised rail — constitutional minimum is 1",
                )
        del self._rails[rail_id]

    def notify_first_light(self) -> None:
        """Called when First Light is achieved — escalates minimum.

        This is triggered by the same governance transition that
        deactivates PoC mode and expires the founder's veto.
        """
        self._first_light_achieved = True

    def healthy_rails(self) -> List[PaymentRail]:
        """Return all rails that currently pass health check."""
        return [r for r in self._rails.values() if r.health_check()]

    def get_rail(self, rail_id: str) -> PaymentRail:
        """Get a specific rail by ID."""
        if rail_id not in self._rails:
            raise ValueError(f"Unknown rail: {rail_id}")
        return self._rails[rail_id]

    def list_rails(self) -> List[str]:
        """List all registered rail IDs."""
        return list(self._rails.keys())

    def validate_constitutional_compliance(self) -> List[str]:
        """Check all constitutional requirements.

        Returns empty list if compliant, or list of violation descriptions.
        """
        violations: List[str] = []
        if self.independent_count < self.active_minimum:
            violations.append(
                f"Below minimum independent rails: {self.independent_count} "
                f"< {self.active_minimum}",
            )
        if (
            self._config.require_at_least_one_decentralised
            and not self.has_decentralised
        ):
            violations.append("No decentralised rail registered")
        for rail in self._rails.values():
            if not rail.sovereignty_assessment.passes:
                violations.append(
                    f"Rail '{rail.rail_id}' fails sovereignty assessment",
                )
            if not rail.health_check():
                violations.append(f"Rail '{rail.rail_id}' is unhealthy")
        return violations
