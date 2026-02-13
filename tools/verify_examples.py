#!/usr/bin/env python3
"""Validate worked-example bundles against runtime risk-tier policy."""

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "runtime_policy.json"
PARAMS_PATH = ROOT / "config" / "constitutional_params.json"
EXAMPLES_DIR = ROOT / "examples" / "worked_examples"
EXAMPLE_FILES = [
    EXAMPLES_DIR / "low_risk_mission.json",
    EXAMPLES_DIR / "high_risk_mission.json",
]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_example(example: dict, policy: dict, params: dict) -> list[str]:
    errors: list[str] = []
    class_map = policy["mission_class_to_tier"]
    tiers = policy["risk_tiers"]

    mission_class = example["mission_class"]
    if mission_class not in class_map:
        return [f"unknown mission_class {mission_class}"]

    expected_tier = class_map[mission_class]
    if example["risk_tier"] != expected_tier:
        errors.append(
            f"mission {example['mission_id']} tier mismatch: "
            f"expected {expected_tier}, got {example['risk_tier']}"
        )

    tier = tiers[expected_tier]
    worker_id = example.get("worker_id")
    reviewers = example.get("reviewers", [])
    reviewer_ids = [r["id"] for r in reviewers]

    if worker_id and worker_id in reviewer_ids:
        errors.append("worker cannot be a reviewer on the same mission")

    # --- Domain type validation ---
    valid_domains = set(policy.get("valid_domain_types", []))
    domain_type = example.get("domain_type")
    if not domain_type:
        errors.append(f"{example['mission_id']} must include domain_type")
    elif domain_type not in valid_domains:
        errors.append(
            f"{example['mission_id']} domain_type '{domain_type}' not in {sorted(valid_domains)}"
        )

    # --- Reviewer metadata validation ---
    het_params = params.get("reviewer_heterogeneity", {})
    valid_methods = set(het_params.get("valid_method_types", []))

    for idx, rev in enumerate(reviewers):
        if "model_family" not in rev:
            errors.append(f"{example['mission_id']} reviewer[{idx}] missing model_family")
        if "method_type" not in rev:
            errors.append(f"{example['mission_id']} reviewer[{idx}] missing method_type")
        elif rev["method_type"] not in valid_methods:
            errors.append(
                f"{example['mission_id']} reviewer[{idx}] method_type "
                f"'{rev['method_type']}' not in {sorted(valid_methods)}"
            )

    if not tier["constitutional_flow"]:
        required_reviewers = tier["reviewers_required"]
        if len(reviewers) != required_reviewers:
            errors.append(
                f"{example['mission_id']} requires {required_reviewers} reviewers, got {len(reviewers)}"
            )

        decisions = example.get("review_decisions", [])
        approvals = sum(1 for d in decisions if d["decision"] == "APPROVE")
        if approvals < tier["approvals_required"]:
            errors.append(
                f"{example['mission_id']} needs {tier['approvals_required']} approvals, got {approvals}"
            )

        approved_reviewer_ids = {
            d["reviewer_id"] for d in decisions if d["decision"] == "APPROVE"
        }
        approved_reviewers = [r for r in reviewers if r["id"] in approved_reviewer_ids]
        regions = {r["region"] for r in approved_reviewers}
        orgs = {r["organization"] for r in approved_reviewers}
        if len(regions) < tier["min_regions"]:
            errors.append(
                f"{example['mission_id']} needs {tier['min_regions']} regions among approvals, got {len(regions)}"
            )
        if len(orgs) < tier["min_organizations"]:
            errors.append(
                f"{example['mission_id']} needs {tier['min_organizations']} organizations among approvals, got {len(orgs)}"
            )

        # --- Heterogeneity validation ---
        min_families = tier.get("min_model_families", 1)
        min_methods = tier.get("min_method_types", 1)
        families = {r["model_family"] for r in reviewers if "model_family" in r}
        methods = {r["method_type"] for r in reviewers if "method_type" in r}
        if len(families) < min_families:
            errors.append(
                f"{example['mission_id']} needs {min_families} model families, got {len(families)}: {sorted(families)}"
            )
        if len(methods) < min_methods:
            errors.append(
                f"{example['mission_id']} needs {min_methods} method types, got {len(methods)}: {sorted(methods)}"
            )

    if tier["human_final_gate"] and not example.get("human_final_approval", False):
        errors.append(f"{example['mission_id']} requires human_final_approval=true")

    evidence = example.get("evidence", [])
    if not evidence:
        errors.append(f"{example['mission_id']} must include at least one evidence record")
    else:
        for idx, item in enumerate(evidence):
            if "artifact_hash" not in item:
                errors.append(f"{example['mission_id']} evidence[{idx}] missing artifact_hash")
            if "signature" not in item:
                errors.append(f"{example['mission_id']} evidence[{idx}] missing signature")

    commitment = example.get("commitment", {})
    for key in (
        "commitment_version",
        "epoch_id",
        "previous_commitment_hash",
        "mission_event_root",
        "trust_delta_root",
        "governance_ballot_root",
        "review_decision_root",
        "public_beacon_round",
        "chamber_nonce",
        "timestamp_utc",
    ):
        if key not in commitment:
            errors.append(f"{example['mission_id']} commitment missing {key}")

    return errors


def main() -> int:
    policy = load_json(POLICY_PATH)
    params = load_json(PARAMS_PATH)
    all_errors: list[str] = []
    for path in EXAMPLE_FILES:
        example = load_json(path)
        errs = validate_example(example, policy, params)
        all_errors.extend(errs)

    if all_errors:
        print("Example verification failed:")
        for err in all_errors:
            print(f"- {err}")
        return 1

    print("Example verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
