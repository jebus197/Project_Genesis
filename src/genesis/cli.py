"""Genesis CLI — command-line interface for the governance engine.

Usage:
    python -m genesis.cli status
    python -m genesis.cli register-actor --id alice --kind human --region NA --org Org1
    python -m genesis.cli create-mission --id M-001 --title "Fix bug" --class documentation_update
    python -m genesis.cli submit-mission --id M-001
    python -m genesis.cli assign-reviewers --id M-001 --seed beacon:12345
    python -m genesis.cli check-invariants
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from genesis.models.mission import DomainType, MissionClass
from genesis.models.trust import ActorKind
from genesis.persistence.event_log import EventLog
from genesis.persistence.state_store import StateStore
from genesis.policy.resolver import PolicyResolver
from genesis.service import GenesisService


DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config"
DEFAULT_DATA = Path(__file__).resolve().parents[2] / "data"


def _make_service(config_dir: Path, data_dir: Path = DEFAULT_DATA) -> GenesisService:
    """Create a GenesisService with durable persistence."""
    data_dir.mkdir(parents=True, exist_ok=True)
    resolver = PolicyResolver.from_config_dir(config_dir)
    event_log = EventLog(storage_path=data_dir / "events.jsonl")
    state_store = StateStore(storage_path=data_dir / "state.json")
    service = GenesisService(
        resolver,
        event_log=event_log,
        state_store=state_store,
    )
    # Ensure an epoch is open so lifecycle/payment commands don't crash
    service._epoch_service.open_epoch()
    return service


def cmd_status(args: argparse.Namespace) -> int:
    service = _make_service(args.config)
    status = service.status()
    print(json.dumps(status, indent=2))
    return 0


def cmd_register_actor(args: argparse.Namespace) -> int:
    service = _make_service(args.config)
    result = service.register_actor(
        actor_id=args.id,
        actor_kind=ActorKind(args.kind),
        region=args.region,
        organization=args.org,
        model_family=args.family or ("human_reviewer" if args.kind == "human" else "unknown"),
        method_type=args.method or ("human_reviewer" if args.kind == "human" else "unknown"),
        initial_trust=args.trust,
        registered_by=getattr(args, "operator", None),
    )
    if result.success:
        print(f"Registered actor: {result.data['actor_id']}")
        return 0
    print(f"Failed: {'; '.join(result.errors)}", file=sys.stderr)
    return 1


def cmd_create_mission(args: argparse.Namespace) -> int:
    service = _make_service(args.config)
    result = service.create_mission(
        mission_id=args.id,
        title=args.title,
        mission_class=MissionClass(args.mission_class),
        domain_type=DomainType(args.domain),
        worker_id=args.worker,
    )
    if result.success:
        print(f"Created mission: {result.data['mission_id']} (tier: {result.data['risk_tier']})")
        return 0
    print(f"Failed: {'; '.join(result.errors)}", file=sys.stderr)
    return 1


def cmd_check_first_light(args: argparse.Namespace) -> int:
    """Evaluate First Light conditions from current financials."""
    from decimal import Decimal

    service = _make_service(args.config)
    result = service.periodic_first_light_check(
        monthly_revenue=Decimal(args.revenue),
        monthly_costs=Decimal(args.costs),
        reserve_balance=Decimal(args.reserve),
    )
    if result.success:
        print(json.dumps(result.data, indent=2, default=str))
        return 0
    print(f"Failed: {'; '.join(result.errors)}", file=sys.stderr)
    return 1


def cmd_process_payment(args: argparse.Namespace) -> int:
    """Process payment for an approved mission."""
    from decimal import Decimal
    from genesis.compensation.ledger import OperationalLedger
    from genesis.models.compensation import ReserveFundState

    service = _make_service(args.config)
    # In production these come from the ledger and reserve subsystems;
    # the CLI provides a manual override for testing and operations.
    ledger = OperationalLedger()
    reserve = ReserveFundState(
        balance=Decimal(args.reserve_balance),
        target=Decimal(args.reserve_target),
        gap=max(Decimal(args.reserve_target) - Decimal(args.reserve_balance), Decimal("0")),
        is_below_target=Decimal(args.reserve_balance) < Decimal(args.reserve_target),
    )

    result = service.process_mission_payment(
        mission_id=args.mission_id,
        mission_reward=Decimal(args.reward),
        ledger=ledger,
        reserve=reserve,
    )
    if result.success:
        print(json.dumps(result.data, indent=2, default=str))
        return 0
    print(f"Failed: {'; '.join(result.errors)}", file=sys.stderr)
    return 1


def cmd_check_invariants(args: argparse.Namespace) -> int:
    """Run constitutional invariant checks."""
    # Import and run the existing check_invariants tool
    tools_dir = Path(__file__).resolve().parents[2] / "tools"
    sys.path.insert(0, str(tools_dir))
    from check_invariants import check
    return check()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="genesis",
        description="Project Genesis — governance engine CLI",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to config directory (default: config/)",
    )
    sub = parser.add_subparsers(dest="command")

    # status
    sub.add_parser("status", help="Show system status")

    # register-actor
    p_reg = sub.add_parser("register-actor", help="Register an actor")
    p_reg.add_argument("--id", required=True, help="Actor ID")
    p_reg.add_argument("--kind", required=True, choices=["human", "machine"])
    p_reg.add_argument("--region", required=True, help="Geographic region")
    p_reg.add_argument("--org", required=True, help="Organisation")
    p_reg.add_argument("--family", help="Model family (default: human_reviewer)")
    p_reg.add_argument("--method", help="Method type (default: human_reviewer)")
    p_reg.add_argument("--trust", type=float, default=0.10, help="Initial trust (default: 0.10)")
    p_reg.add_argument("--operator", help="Human operator ID (required for machine registration)")

    # create-mission
    p_create = sub.add_parser("create-mission", help="Create a new mission")
    p_create.add_argument("--id", required=True, help="Mission ID")
    p_create.add_argument("--title", required=True, help="Mission title")
    p_create.add_argument(
        "--class", dest="mission_class", required=True,
        choices=[c.value for c in MissionClass],
        help="Mission class",
    )
    p_create.add_argument(
        "--domain", default="objective",
        choices=[d.value for d in DomainType],
        help="Domain type (default: objective)",
    )
    p_create.add_argument("--worker", help="Worker ID")

    # check-first-light
    p_fl = sub.add_parser("check-first-light", help="Evaluate First Light conditions")
    p_fl.add_argument("--revenue", required=True, help="Monthly revenue (Decimal)")
    p_fl.add_argument("--costs", required=True, help="Monthly costs (Decimal)")
    p_fl.add_argument("--reserve", required=True, help="Reserve balance (Decimal)")

    # process-payment
    p_pay = sub.add_parser("process-payment", help="Process payment for an approved mission")
    p_pay.add_argument("--mission-id", required=True, help="Mission ID")
    p_pay.add_argument("--reward", required=True, help="Mission reward (Decimal)")
    p_pay.add_argument("--reserve-balance", default="10000", help="Reserve balance")
    p_pay.add_argument("--reserve-target", default="10000", help="Reserve target")

    # check-invariants
    sub.add_parser("check-invariants", help="Run constitutional invariant checks")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "status": cmd_status,
        "register-actor": cmd_register_actor,
        "create-mission": cmd_create_mission,
        "check-first-light": cmd_check_first_light,
        "process-payment": cmd_process_payment,
        "check-invariants": cmd_check_invariants,
    }

    handler = commands.get(args.command)
    if handler is None:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
