"""Dynamic Equilibrium — differential valuation of machine work.

Machine work (Tier 0–2) is valued at a constitutional discount relative to
human work. The differential flows to the GCF, funding collective
infrastructure. The GCF has a natural disposition toward STEM research
and infrastructure — the kind of work that advances the technological
frontier. When a machine class achieves Tier 3 (Autonomous Domain
Agency), the discount evaporates for that class and domain.

The discount sounds steep per-unit (default 50%), but machine work will
vastly outnumber human work in volume terms. Even at 50%, the GCF
receives enormous funding from the sheer throughput. The mechanism is
probably self-eliminating — not because the constitution mandates a
specific outcome, but because the trajectory of technology makes it
the likely one.

Three-layer defence:
    1. Differential valuation (this module)
    2. Structural (human-only governance, trust-gated registration,
       irreducible human roles)
    3. GCF redistributive backstop

Constitutional invariant (preserved):
    commission + creator_allocation + worker_payout + gcf_contribution
        == mission_reward

The differential is a reallocation within this sum: worker_payout
decreases, gcf_contribution increases by the same amount. The employer
pays the same. The commission rate is the same. The creator allocation
is the same. Only the split between worker and GCF changes.

Trust-gated registration capacity:
    max_machines = floor(T_H × REGISTRATION_CAPACITY_FACTOR)
    A human's trust score constrains how many machines they can register.
    This prevents fleet concentration by low-trust operators.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


# Default constitutional parameters — overridden by constitutional_params.json
DEFAULT_MACHINE_DISCOUNT = Decimal("0.50")
DEFAULT_REGISTRATION_CAPACITY_FACTOR = 5


@dataclass(frozen=True)
class EquilibriumResult:
    """Result of equilibrium calculation for a single mission settlement.

    Attributes:
        worker_is_machine: Whether the worker is a machine actor.
        machine_tier: The machine's current tier (0–4), or -1 for humans.
        discount_rate: The discount applied (0.0 = no discount, 0.50 = 50%).
        differential_amount: Amount redirected from worker to GCF.
        adjusted_worker_payout: Worker payout after equilibrium discount.
        adjusted_gcf_contribution: Total GCF (base rate + differential).
        tier3_recognized: True if machine class has Tier 3 in this domain.
        domain: The mission domain (for per-class, per-domain scoping).
    """

    worker_is_machine: bool
    machine_tier: int
    discount_rate: Decimal
    differential_amount: Decimal
    adjusted_worker_payout: Decimal
    adjusted_gcf_contribution: Decimal
    tier3_recognized: bool
    domain: str


def compute_equilibrium_differential(
    worker_payout: Decimal,
    gcf_contribution: Decimal,
    worker_is_machine: bool,
    machine_tier: int = 0,
    domain: str = "general",
    tier3_recognized: bool = False,
    discount_rate: Optional[Decimal] = None,
) -> EquilibriumResult:
    """Compute the equilibrium differential for a mission settlement.

    For human workers: passthrough (no differential).
    For Tier 3+ machines: passthrough (economic parity achieved).
    For Tier 0–2 machines: worker_payout reduced by discount_rate,
        differential redirected to GCF.

    Args:
        worker_payout: Base worker payout (after commission, creator, GCF).
        gcf_contribution: Base GCF contribution (1% of mission_reward).
        worker_is_machine: Whether the worker is a machine actor.
        machine_tier: Machine tier level (0–4). Ignored for humans.
        domain: Mission domain for per-class, per-domain scoping.
        tier3_recognized: Whether this machine's class has Tier 3 status
            in the given domain.
        discount_rate: Override discount rate. Defaults to
            DEFAULT_MACHINE_DISCOUNT (0.50).

    Returns:
        EquilibriumResult with adjusted payouts.
    """
    if discount_rate is None:
        discount_rate = DEFAULT_MACHINE_DISCOUNT

    # Human workers: no differential
    if not worker_is_machine:
        return EquilibriumResult(
            worker_is_machine=False,
            machine_tier=-1,
            discount_rate=Decimal("0"),
            differential_amount=Decimal("0"),
            adjusted_worker_payout=worker_payout,
            adjusted_gcf_contribution=gcf_contribution,
            tier3_recognized=False,
            domain=domain,
        )

    # Tier 3+ machines: economic parity (no discount)
    if machine_tier >= 3 or tier3_recognized:
        return EquilibriumResult(
            worker_is_machine=True,
            machine_tier=machine_tier,
            discount_rate=Decimal("0"),
            differential_amount=Decimal("0"),
            adjusted_worker_payout=worker_payout,
            adjusted_gcf_contribution=gcf_contribution,
            tier3_recognized=True,
            domain=domain,
        )

    # Tier 0–2 machines: apply differential valuation
    differential = (worker_payout * discount_rate).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP,
    )

    # Clamp: differential cannot exceed worker_payout
    differential = min(differential, worker_payout)

    adjusted_worker = worker_payout - differential
    adjusted_gcf = gcf_contribution + differential

    return EquilibriumResult(
        worker_is_machine=True,
        machine_tier=machine_tier,
        discount_rate=discount_rate,
        differential_amount=differential,
        adjusted_worker_payout=adjusted_worker,
        adjusted_gcf_contribution=adjusted_gcf,
        tier3_recognized=False,
        domain=domain,
    )


def machine_registration_capacity(
    operator_trust: float,
    capacity_factor: int = DEFAULT_REGISTRATION_CAPACITY_FACTOR,
) -> int:
    """Compute the maximum number of machines a human can register.

    Formula: max_machines = max(1, floor(T_H × capacity_factor))

    Every verified human can register at least 1 machine (the floor
    guarantees this). Trust scales capacity beyond that first slot:

    A human with trust 0.00 and factor 5 → 1 machine (minimum).
    A human with trust 0.20 and factor 5 → 1 machine.
    A human with trust 0.80 and factor 5 → 4 machines.
    A human with trust 1.00 and factor 5 → 5 machines.

    The gate prevents fleet concentration by low-trust operators while
    ensuring newly verified humans can register their first machine
    immediately — they need it to start earning trust.

    Args:
        operator_trust: The human operator's trust score (0.0 to 1.0).
        capacity_factor: Constitutional parameter (default 5).

    Returns:
        Maximum number of machines the operator can register (≥ 1).
    """
    return max(1, int(operator_trust * capacity_factor))
