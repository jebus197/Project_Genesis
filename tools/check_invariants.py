#!/usr/bin/env python3
"""Genesis invariant checks against executable policy artifacts."""

import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PARAMS_PATH = ROOT / "config" / "constitutional_params.json"
POLICY_PATH = ROOT / "config" / "runtime_policy.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def check_chamber(chambers: dict, label: str, errors: list[str]) -> None:
    """Validate chamber definitions share common structural rules."""
    for chamber_name in ("proposal", "ratification", "challenge"):
        chamber = chambers.get(chamber_name)
        if not chamber:
            errors.append(f"{label} missing chamber definition: {chamber_name}")
            continue
        size = chamber.get("size", 0)
        pass_threshold = chamber.get("pass_threshold", 0)
        if size <= 0:
            errors.append(f"{label} {chamber_name}.size must be > 0")
        if pass_threshold <= size // 2:
            errors.append(
                f"{label} {chamber_name}.pass_threshold must be strict majority (> 50%)"
            )
        if pass_threshold > size:
            errors.append(f"{label} {chamber_name}.pass_threshold cannot exceed size")


def check() -> int:
    params = load_json(PARAMS_PATH)
    policy = load_json(POLICY_PATH)
    errors: list[str] = []

    # --- Constitutional voting invariants ---
    w_h = params["constitutional_voting"]["w_H_const"]
    w_m = params["constitutional_voting"]["w_M_const"]
    if w_h != 1.0:
        errors.append(f"w_H_const must be 1.0, got {w_h}")
    if w_m != 0.0:
        errors.append(f"w_M_const must be 0.0, got {w_m}")

    # --- Trust weight invariants ---
    weights = params["trust_weights"]
    w_q = weights["w_Q"]
    w_r = weights["w_R"]
    w_v = weights["w_V"]
    w_e = weights["w_E"]
    if not math.isclose(w_q + w_r + w_v + w_e, 1.0, rel_tol=0.0, abs_tol=1e-9):
        errors.append("w_Q + w_R + w_V + w_E must equal 1.0")
    if w_q < 0.70:
        errors.append(f"w_Q must be >= 0.70, got {w_q}")
    if w_v > 0.10:
        errors.append(f"w_V must be <= 0.10, got {w_v}")
    if w_e > 0.10:
        errors.append(f"w_E must be <= 0.10, got {w_e}")
    if w_e < 0.0:
        errors.append(f"w_E must be >= 0.0, got {w_e}")

    # --- Effort threshold invariants ---
    effort = params["effort_thresholds"]
    e_min = effort["E_min_per_tier"]
    for tier_id in ("R0", "R1", "R2", "R3"):
        if tier_id not in e_min:
            errors.append(f"E_min_per_tier missing tier: {tier_id}")
        elif not (0.0 <= e_min[tier_id] <= 1.0):
            errors.append(f"E_min_per_tier[{tier_id}] must be in [0, 1]")
    # Higher tiers must require more effort
    tier_order = ["R0", "R1", "R2", "R3"]
    for i in range(len(tier_order) - 1):
        t_low, t_high = tier_order[i], tier_order[i + 1]
        if t_low in e_min and t_high in e_min:
            if e_min[t_high] < e_min[t_low]:
                errors.append(
                    f"E_min_per_tier[{t_high}] must be >= E_min_per_tier[{t_low}]"
                )
    if effort["E_suspicious_low"] < 0:
        errors.append("E_suspicious_low must be >= 0")
    if effort["E_max_credit"] > 1.0:
        errors.append("E_max_credit must be <= 1.0")

    # --- Quality gate invariants ---
    qmin_h = params["quality_gates"]["Q_min_H"]
    qmin_m = params["quality_gates"]["Q_min_M"]
    if not (0.0 <= qmin_h <= 1.0):
        errors.append(f"Q_min_H must be in [0,1], got {qmin_h}")
    if not (0.0 <= qmin_m <= 1.0):
        errors.append(f"Q_min_M must be in [0,1], got {qmin_m}")
    if qmin_m < qmin_h:
        errors.append(
            f"Q_min_M should be >= Q_min_H for stricter machine gate ({qmin_m} < {qmin_h})"
        )

    # --- Trust floor invariants ---
    floors = params["trust_floors"]
    if not floors["T_floor_H_positive"]:
        errors.append("T_floor_H must be positive (human floor > 0)")
    if floors["T_floor_M"] != 0.0:
        errors.append(f"T_floor_M must be 0.0, got {floors['T_floor_M']}")

    # --- Eligibility threshold invariants ---
    eligibility = params["eligibility"]
    if not (0.0 < eligibility["tau_vote"] < 1.0):
        errors.append("tau_vote must be in (0, 1)")
    if not (0.0 < eligibility["tau_prop"] < 1.0):
        errors.append("tau_prop must be in (0, 1)")
    if eligibility["tau_prop"] <= eligibility["tau_vote"]:
        errors.append("tau_prop must be stricter (higher) than tau_vote")

    # --- Fast elevation invariants ---
    fe_global = params["fast_elevation"]
    if fe_global["delta_fast"] <= 0:
        errors.append("delta_fast must be > 0")

    # --- Full constitution invariants ---
    full_const = params["full_constitution"]
    check_chamber(full_const["chambers"], "Full constitution", errors)
    fc_geo = full_const["geo"]
    if fc_geo["R_min"] < 1:
        errors.append("Full constitution R_min must be >= 1")
    if not (0.0 < fc_geo["c_max"] <= 1.0):
        errors.append("Full constitution c_max must be in (0, 1]")
    fc_fe = full_const["fast_elevation"]
    if fc_fe["q_h"] < 1:
        errors.append("Full constitution q_h must be >= 1")
    if fc_fe["r_h"] < 1:
        errors.append("Full constitution r_h must be >= 1")
    if fc_fe["o_h"] < 1:
        errors.append("Full constitution o_h must be >= 1")

    # Full constitution geo must be stricter than G2
    g2_geo_check = params["genesis"]["G2_geo"]
    if fc_geo["R_min"] <= g2_geo_check["R_min"]:
        errors.append("Full constitution R_min must be stricter than G2 R_min")
    if fc_geo["c_max"] >= g2_geo_check["c_max"]:
        errors.append("Full constitution c_max must be stricter than G2 c_max")

    # --- Machine recertification invariants ---
    recert = params["machine_recertification"]
    if recert["RECERT_CORRECTNESS_MIN"] < 0.90:
        errors.append("RECERT_CORRECTNESS_MIN must be >= 0.90")
    if recert["RECERT_SEVERE_ERR_MAX"] > 0.01:
        errors.append("RECERT_SEVERE_ERR_MAX must be <= 0.01")
    if recert["RECERT_REPRO_MIN"] < 0.95:
        errors.append("RECERT_REPRO_MIN must be >= 0.95")
    if recert["RECERT_REVIEW_SIGS"] < 5:
        errors.append("RECERT_REVIEW_SIGS must be >= 5")
    if recert["RECERT_PROBATION_TASKS"] <= 0:
        errors.append("RECERT_PROBATION_TASKS must be > 0")

    # --- Machine decommission invariants ---
    decomm = params["machine_decommission"]
    for key, value in decomm.items():
        if value <= 0:
            errors.append(f"{key} must be > 0, got {value}")

    # --- Genesis protocol invariants ---
    genesis = params["genesis"]
    if genesis["G0_MAX_DAYS"] <= 0:
        errors.append("G0_MAX_DAYS must be > 0")
    if genesis["G0_EXTENSION_DAYS"] <= 0:
        errors.append("G0_EXTENSION_DAYS must be > 0")
    if genesis["G1_MAX_DAYS"] <= 0:
        errors.append("G1_MAX_DAYS must be > 0")
    if genesis["G0_RATIFICATION_WINDOW_DAYS"] <= 0:
        errors.append("G0_RATIFICATION_WINDOW_DAYS must be > 0")

    thresholds = genesis["phase_thresholds"]
    if not (thresholds["G0_max_humans"] < thresholds["G1_max_humans"] < thresholds["G2_max_humans"]):
        errors.append("Genesis phase thresholds must be strictly increasing: G0 < G1 < G2")

    for phase_label, phase_key in [("G1", "G1_chambers"), ("G2", "G2_chambers")]:
        check_chamber(genesis[phase_key], f"Genesis {phase_label}", errors)

    for phase_label, geo_key in [("G1", "G1_geo"), ("G2", "G2_geo")]:
        geo = genesis[geo_key]
        if geo["R_min"] < 1:
            errors.append(f"Genesis {phase_label} R_min must be >= 1")
        if not (0.0 < geo["c_max"] <= 1.0):
            errors.append(f"Genesis {phase_label} c_max must be in (0, 1]")

    for phase_label, fe_key in [("G1", "G1_fast_elevation"), ("G2", "G2_fast_elevation")]:
        fe = genesis[fe_key]
        if fe["q_h"] < 1:
            errors.append(f"Genesis {phase_label} q_h must be >= 1")
        if fe["r_h"] < 1:
            errors.append(f"Genesis {phase_label} r_h must be >= 1")
        if fe["o_h"] < 1:
            errors.append(f"Genesis {phase_label} o_h must be >= 1")

    # Genesis must be stricter as phases advance
    g1_geo = genesis["G1_geo"]
    g2_geo = genesis["G2_geo"]
    if g2_geo["R_min"] <= g1_geo["R_min"]:
        errors.append("G2 R_min must be stricter (higher) than G1 R_min")
    if g2_geo["c_max"] >= g1_geo["c_max"]:
        errors.append("G2 c_max must be stricter (lower) than G1 c_max")

    # --- Commitment tier invariants ---
    ct = params["commitment_tiers"]
    if ct["C0_L1_anchor_interval_hours"] <= 0:
        errors.append("C0_L1_anchor_interval_hours must be > 0")
    if ct["C1_L1_anchor_interval_hours"] <= 0:
        errors.append("C1_L1_anchor_interval_hours must be > 0")
    if ct["C1_L1_anchor_interval_hours"] >= ct["C0_L1_anchor_interval_hours"]:
        errors.append("C1 anchor interval must be shorter (stricter) than C0")
    if ct["C0_max_humans"] >= ct["C1_max_humans"]:
        errors.append("Commitment tier thresholds must be strictly increasing: C0 < C1")

    # --- Commitment tier epoch invariant ---
    if ct.get("EPOCH_HOURS", 0) <= 0:
        errors.append("EPOCH_HOURS must be > 0")

    # --- Commitment committee invariants ---
    cc = params["commitment_committee"]
    if cc["n"] < 1:
        errors.append("Commitment committee n must be >= 1")
    if cc["t"] < 1:
        errors.append("Commitment committee t must be >= 1")
    if cc["t"] > cc["n"]:
        errors.append("Commitment committee t cannot exceed n")
    if cc["t"] <= cc["n"] // 2:
        errors.append("Commitment committee t must be strict majority (> n/2)")

    # --- Key management invariants ---
    km = params["key_management"]
    if km["KEY_ROTATION_DAYS"] <= 0:
        errors.append("KEY_ROTATION_DAYS must be > 0")

    # --- Reviewer heterogeneity invariants ---
    het = params["reviewer_heterogeneity"]
    if het["H_R2_MODEL_FAMILIES"] < 2:
        errors.append("H_R2_MODEL_FAMILIES must be >= 2")
    if het["H_R2_METHOD_TYPES"] < 2:
        errors.append("H_R2_METHOD_TYPES must be >= 2")
    valid_methods = het["valid_method_types"]
    required_methods = {"reasoning_model", "retrieval_augmented", "rule_based_deterministic", "human_reviewer"}
    if set(valid_methods) != required_methods:
        errors.append(f"valid_method_types must be exactly {sorted(required_methods)}")

    # --- Normative resolution invariants ---
    norm = params["normative_resolution"]
    if not (0.0 < norm["NORMATIVE_AGREEMENT_THRESHOLD"] < 1.0):
        errors.append("NORMATIVE_AGREEMENT_THRESHOLD must be in (0, 1)")
    if norm["NORMATIVE_PANEL_SIZE"] < 3:
        errors.append("NORMATIVE_PANEL_SIZE must be >= 3")
    if norm["NORMATIVE_PANEL_REGIONS"] < 2:
        errors.append("NORMATIVE_PANEL_REGIONS must be >= 2")
    if norm["NORMATIVE_PANEL_ORGS"] < 2:
        errors.append("NORMATIVE_PANEL_ORGS must be >= 2")
    valid_domains = norm["valid_domain_types"]
    required_domains = {"objective", "normative", "mixed"}
    if set(valid_domains) != required_domains:
        errors.append(f"valid_domain_types must be exactly {sorted(required_domains)}")

    # --- Risk tier structural invariants ---
    tiers = policy["risk_tiers"]
    required_tiers = {"R0", "R1", "R2", "R3"}
    missing = required_tiers - set(tiers.keys())
    if missing:
        errors.append(f"Missing risk tiers: {sorted(missing)}")

    for tier_id in required_tiers:
        tier = tiers[tier_id]
        if tier_id != "R3":
            if tier["reviewers_required"] <= 0:
                errors.append(f"{tier_id} reviewers_required must be > 0")
            if tier["approvals_required"] > tier["reviewers_required"]:
                errors.append(f"{tier_id} approvals_required cannot exceed reviewers_required")
        if tier["constitutional_flow"] and tier_id != "R3":
            errors.append(f"{tier_id} cannot be constitutional_flow=true")

    r3 = tiers["R3"]
    if not r3["constitutional_flow"]:
        errors.append("R3 must be constitutional_flow=true")
    if "chambers" not in r3:
        errors.append("R3 must define chamber thresholds")
    if not r3["human_final_gate"]:
        errors.append("R3 must enforce human_final_gate=true")

    r2 = tiers["R2"]
    if r2["reviewers_required"] < 5:
        errors.append("R2 reviewers_required must be >= 5")
    if r2["approvals_required"] < 4:
        errors.append("R2 approvals_required must be >= 4")
    if not r2["human_final_gate"]:
        errors.append("R2 must enforce human_final_gate=true")
    if r2["min_regions"] < 3:
        errors.append("R2 min_regions must be >= 3")
    if r2["min_organizations"] < 3:
        errors.append("R2 min_organizations must be >= 3")

    # R2 heterogeneity enforcement
    if r2.get("min_model_families", 0) < 2:
        errors.append("R2 min_model_families must be >= 2")
    if r2.get("min_method_types", 0) < 2:
        errors.append("R2 min_method_types must be >= 2")

    # R1 heterogeneity enforcement
    r1 = tiers["R1"]
    if r1.get("min_model_families", 0) < 2:
        errors.append("R1 min_model_families must be >= 2")

    check_chamber(r3.get("chambers", {}), "R3", errors)

    # --- Mission class mapping invariants ---
    class_map = policy["mission_class_to_tier"]
    for required_class in (
        "documentation_update",
        "internal_operations_change",
        "regulated_analysis",
        "constitutional_change",
    ):
        if required_class not in class_map:
            errors.append(f"Missing mission class mapping: {required_class}")
    if class_map.get("constitutional_change") != "R3":
        errors.append("constitutional_change mission class must map to R3")
    for mission_class, tier_id in class_map.items():
        if tier_id not in required_tiers:
            errors.append(f"{mission_class} maps to unknown tier {tier_id}")

    # --- Normative resolution policy invariants ---
    norm_policy = policy.get("normative_resolution", {})
    if not norm_policy.get("normative_requires_human_adjudication"):
        errors.append("normative_requires_human_adjudication must be true")
    valid_domain_policy = policy.get("valid_domain_types", [])
    if set(valid_domain_policy) != required_domains:
        errors.append(f"Policy valid_domain_types must be exactly {sorted(required_domains)}")

    # --- Identity signal invariants ---
    identity = policy["identity_signals"]
    if not identity.get("signals"):
        errors.append("identity signals list must not be empty")
    if identity["can_mint_trust"]:
        errors.append("identity signals must not mint trust")
    if identity["can_grant_privileged_routing"]:
        errors.append("identity signals must not grant privileged routing")
    if identity["can_grant_constitutional_authority"]:
        errors.append("identity signals must not grant constitutional authority")

    # --- Machine decommission window invariant ---
    if decomm.get("M_RECERT_FAIL_WINDOW_DAYS", 0) <= 0:
        errors.append("M_RECERT_FAIL_WINDOW_DAYS must be > 0")

    # --- Constitutional supermajority invariants ---
    supermajority = eligibility.get("constitutional_supermajority")
    if supermajority is None:
        errors.append("constitutional_supermajority must be defined")
    elif not (0.5 < supermajority <= 1.0):
        errors.append(
            f"constitutional_supermajority must be in (0.5, 1.0], got {supermajority}"
        )

    # --- Identity verification invariants ---
    id_verify = policy.get("identity_verification", {})
    expiry_days = id_verify.get("verification_expiry_days", 0)
    if expiry_days <= 0:
        errors.append("identity_verification.verification_expiry_days must be > 0")
    required_actions = {"constitutional_vote", "constitutional_proposal"}
    reverif_for = set(id_verify.get("reverification_required_for", []))
    missing_actions = required_actions - reverif_for
    if missing_actions:
        errors.append(
            f"reverification_required_for must include {sorted(required_actions)}, "
            f"missing: {sorted(missing_actions)}"
        )

    # --- Voice liveness invariants ---
    voice = policy.get("voice_liveness", {})
    if voice:
        if voice.get("stage_1_word_count", 0) < 1:
            errors.append("voice_liveness.stage_1_word_count must be >= 1")
        if voice.get("stage_2_word_count", 0) <= voice.get("stage_1_word_count", 0):
            errors.append("voice_liveness.stage_2_word_count must be > stage_1_word_count")
        if voice.get("session_timeout_seconds", 0) < 30:
            errors.append("voice_liveness.session_timeout_seconds must be >= 30")
        wmt = voice.get("word_match_threshold", 0)
        if not (0.0 < wmt <= 1.0):
            errors.append("voice_liveness.word_match_threshold must be in (0, 1]")
        nt = voice.get("naturalness_threshold", 0)
        if not (0.0 < nt <= 1.0):
            errors.append("voice_liveness.naturalness_threshold must be in (0, 1]")

    # --- Quorum verification invariants ---
    quorum = policy.get("quorum_verification", {})
    if quorum:
        min_q = quorum.get("min_quorum_size", 0)
        max_q = quorum.get("max_quorum_size", 0)
        if min_q < 3:
            errors.append("quorum_verification.min_quorum_size must be >= 3")
        if max_q < min_q:
            errors.append("quorum_verification.max_quorum_size must be >= min_quorum_size")
        if quorum.get("verification_timeout_hours", 0) <= 0:
            errors.append("quorum_verification.verification_timeout_hours must be > 0")
        mvt = quorum.get("min_verifier_trust", 0)
        if not (0.0 < mvt <= 1.0):
            errors.append("quorum_verification.min_verifier_trust must be in (0, 1]")
        # D-5: High-trust gate — verifiers must be >= 0.70
        if mvt < 0.70:
            errors.append(
                f"quorum_verification.min_verifier_trust must be >= 0.70 "
                f"(high-trust gate), got {mvt}"
            )
        # D-5: Panel diversity
        pdmo = quorum.get("panel_diversity_min_organizations", 0)
        if pdmo < 2:
            errors.append("quorum_verification.panel_diversity_min_organizations must be >= 2")
        # D-5: Verifier cooldown
        vch = quorum.get("verifier_cooldown_hours", 0)
        if vch <= 0:
            errors.append("quorum_verification.verifier_cooldown_hours must be > 0")
        # D-5: Appeal window
        awh = quorum.get("appeal_window_hours", 0)
        if awh <= 0:
            errors.append("quorum_verification.appeal_window_hours must be > 0")
        # D-5: Vote attestation required
        if not quorum.get("require_vote_attestation"):
            errors.append("quorum_verification.require_vote_attestation must be true")
        # D-5: Blind adjudication required
        if not quorum.get("blind_adjudication"):
            errors.append("quorum_verification.blind_adjudication must be true")
        # D-5: Session time limit (max 10 min)
        sms = quorum.get("session_max_seconds", 0)
        if sms <= 0 or sms > 600:
            errors.append(
                f"quorum_verification.session_max_seconds must be in (0, 600], got {sms}"
            )
        # D-5: Recording retention >= appeal window
        rrh = quorum.get("recording_retention_hours", 0)
        if rrh < awh:
            errors.append(
                f"quorum_verification.recording_retention_hours ({rrh}) must be "
                f">= appeal_window_hours ({awh})"
            )
        # D-5: Abuse review panel size
        arps = quorum.get("abuse_review_panel_size", 0)
        if arps < 3:
            errors.append("quorum_verification.abuse_review_panel_size must be >= 3")
        # D-5: Abuse trust nuke must be a severe penalty
        atn = quorum.get("abuse_trust_nuke_to", 1.0)
        if atn > 0.01:
            errors.append(
                f"quorum_verification.abuse_trust_nuke_to must be <= 0.01 "
                f"(severe penalty), got {atn}"
            )
        # D-5b: Nuke appeal panel size (escalation — must be >= 5)
        naps = quorum.get("nuke_appeal_panel_size", 0)
        if naps < 5:
            errors.append(
                f"quorum_verification.nuke_appeal_panel_size must be >= 5, got {naps}"
            )
        # D-5b: Nuke appeal panel must be larger than abuse review panel (escalation)
        if naps <= arps:
            errors.append(
                f"quorum_verification.nuke_appeal_panel_size ({naps}) must be > "
                f"abuse_review_panel_size ({arps}) (escalation requirement)"
            )
        # D-5b: Nuke appeal supermajority (must be >= 4 for 5-panel)
        nasm = quorum.get("nuke_appeal_supermajority", 0)
        if nasm < 4:
            errors.append(
                f"quorum_verification.nuke_appeal_supermajority must be >= 4, got {nasm}"
            )
        # D-5b: Nuke appeal window must be > 0
        nawh = quorum.get("nuke_appeal_window_hours", 0)
        if nawh <= 0:
            errors.append(
                "quorum_verification.nuke_appeal_window_hours must be > 0"
            )
        # D-5b: Nuke appeal reviewer min trust (high-trust gate)
        narmt = quorum.get("nuke_appeal_reviewer_min_trust", 0)
        if narmt < 0.70:
            errors.append(
                f"quorum_verification.nuke_appeal_reviewer_min_trust must be >= 0.70, "
                f"got {narmt}"
            )

    # --- Entrenched provisions invariants (Phase E-1: GCF) ---
    entrenched = params.get("entrenched_provisions", {})
    if not entrenched:
        errors.append("entrenched_provisions section must exist in constitutional_params.json")
    else:
        # GCF contribution rate must exist and be in (0, 0.05]
        gcf_rate_str = entrenched.get("GCF_CONTRIBUTION_RATE")
        if gcf_rate_str is None:
            errors.append("entrenched_provisions.GCF_CONTRIBUTION_RATE must be defined")
        else:
            gcf_rate = float(gcf_rate_str)
            if not (0 < gcf_rate <= 0.05):
                errors.append(
                    f"entrenched_provisions.GCF_CONTRIBUTION_RATE must be in (0, 0.05], got {gcf_rate}"
                )

        # Amendment threshold must be >= 0.80 (supermajority)
        amend_thresh = entrenched.get("entrenched_amendment_threshold", 0)
        if amend_thresh < 0.80:
            errors.append(
                f"entrenched_provisions.entrenched_amendment_threshold must be >= 0.80, got {amend_thresh}"
            )

        # Participation minimum must be >= 0.50
        part_min = entrenched.get("entrenched_participation_minimum", 0)
        if part_min < 0.50:
            errors.append(
                f"entrenched_provisions.entrenched_participation_minimum must be >= 0.50, got {part_min}"
            )

        # Cooling-off must be >= 90 days
        cool_off = entrenched.get("entrenched_cooling_off_days", 0)
        if cool_off < 90:
            errors.append(
                f"entrenched_provisions.entrenched_cooling_off_days must be >= 90, got {cool_off}"
            )

        # Confirmation vote must be required
        if not entrenched.get("entrenched_confirmation_vote_required"):
            errors.append(
                "entrenched_provisions.entrenched_confirmation_vote_required must be true"
            )

        # Core entrenched provisions must exist
        if not entrenched.get("TRUST_FLOOR_H_POSITIVE"):
            errors.append("entrenched_provisions.TRUST_FLOOR_H_POSITIVE must be true")
        if not entrenched.get("NO_BUY_TRUST"):
            errors.append("entrenched_provisions.NO_BUY_TRUST must be true")
        if not entrenched.get("MACHINE_VOTING_EXCLUSION"):
            errors.append("entrenched_provisions.MACHINE_VOTING_EXCLUSION must be true")

    # --- GCF rate in commission policy invariant ---
    commission_path = ROOT / "config" / "commission_policy.json"
    if commission_path.exists():
        commission = load_json(commission_path)
        gcf_cp_rate = commission.get("gcf_contribution_rate")
        if gcf_cp_rate is not None:
            gcf_cp_val = float(gcf_cp_rate)
            if not (0 < gcf_cp_val <= 0.05):
                errors.append(
                    f"commission_policy.gcf_contribution_rate must be in (0, 0.05], got {gcf_cp_val}"
                )
            # Cross-check: commission policy rate must match entrenched rate
            if entrenched and gcf_rate_str is not None:
                if float(gcf_cp_rate) != float(gcf_rate_str):
                    errors.append(
                        f"commission_policy.gcf_contribution_rate ({gcf_cp_rate}) must match "
                        f"entrenched_provisions.GCF_CONTRIBUTION_RATE ({gcf_rate_str})"
                    )

    # --- Compliance invariants (Phase E-2) ---
    compliance = policy.get("compliance", {})
    if not compliance:
        errors.append("compliance section must exist in runtime_policy.json")
    else:
        prohibited = compliance.get("prohibited_categories", [])
        if not prohibited:
            errors.append("compliance.prohibited_categories must not be empty")
        # At minimum, weapons and exploitation must be prohibited
        required_prohibited = {
            "weapons_development", "weapons_manufacturing", "weapons_trafficking",
            "child_exploitation", "exploitation_of_persons",
            "biological_weapons", "chemical_weapons", "nuclear_weapons",
        }
        missing_prohibited = required_prohibited - set(prohibited)
        if missing_prohibited:
            errors.append(
                f"compliance.prohibited_categories must include: {sorted(missing_prohibited)}"
            )
        # No-statute-limit categories must be a subset of prohibited
        no_limit = set(compliance.get("no_statute_limit_categories", []))
        if no_limit and not no_limit.issubset(set(prohibited)):
            errors.append(
                "compliance.no_statute_limit_categories must be subset of prohibited_categories"
            )
        # Statute of limitations must be > 0
        sol = compliance.get("statute_of_limitations_days", 0)
        if sol <= 0:
            errors.append(
                f"compliance.statute_of_limitations_days must be > 0, got {sol}"
            )
        # Penalty escalation bounds
        pe = compliance.get("penalty_escalation", {})
        if pe:
            mtr = pe.get("minor_trust_reduction", 0)
            if not (0 < mtr <= 0.50):
                errors.append(
                    f"compliance.penalty_escalation.minor_trust_reduction must be in (0, 0.50], got {mtr}"
                )
            mtn = pe.get("moderate_trust_nuke_to", 1.0)
            if not (0 < mtn <= 0.01):
                errors.append(
                    f"compliance.penalty_escalation.moderate_trust_nuke_to must be in (0, 0.01], got {mtn}"
                )
            msd = pe.get("moderate_suspension_days", 0)
            if msd <= 0:
                errors.append(
                    f"compliance.penalty_escalation.moderate_suspension_days must be > 0, got {msd}"
                )
            if not pe.get("severe_permanent_decommission"):
                errors.append(
                    "compliance.penalty_escalation.severe_permanent_decommission must be true"
                )
            plb = pe.get("pattern_lookback_days", 0)
            if plb <= 0:
                errors.append(
                    f"compliance.penalty_escalation.pattern_lookback_days must be > 0, got {plb}"
                )
        # Screening must be enabled
        if not compliance.get("screening_enabled"):
            errors.append("compliance.screening_enabled must be true")

    # --- Adjudication invariants (Phase E-3: Three-Tier Justice) ---
    adjudication = policy.get("adjudication", {})
    if adjudication:
        adj_ps = adjudication.get("panel_size", 0)
        if adj_ps < 3:
            errors.append(
                f"adjudication.panel_size must be >= 3, got {adj_ps}"
            )
        if not adjudication.get("blind_adjudication"):
            errors.append("adjudication.blind_adjudication must be true")
        if not adjudication.get("require_vote_attestation"):
            errors.append("adjudication.require_vote_attestation must be true")
        adj_rph = adjudication.get("response_period_hours", 0)
        if adj_rph < 24:
            errors.append(
                f"adjudication.response_period_hours must be >= 24, got {adj_rph}"
            )
        adj_awh = adjudication.get("appeal_window_hours", 0)
        if adj_awh < 24:
            errors.append(
                f"adjudication.appeal_window_hours must be >= 24, got {adj_awh}"
            )
        adj_pmo = adjudication.get("panel_min_organizations", 0)
        if adj_pmo < 2:
            errors.append(
                f"adjudication.panel_min_organizations must be >= 2, got {adj_pmo}"
            )

    # --- Constitutional Court invariants (Phase E-3) ---
    court = policy.get("constitutional_court", {})
    if court:
        court_ps = court.get("panel_size", 0)
        if court_ps < 7:
            errors.append(
                f"constitutional_court.panel_size must be >= 7, got {court_ps}"
            )
        court_sm = court.get("supermajority_threshold", 0)
        if court_sm < 5:
            errors.append(
                f"constitutional_court.supermajority_threshold must be >= 5, got {court_sm}"
            )
        if not court.get("human_only"):
            errors.append("constitutional_court.human_only must be true")
        court_mjt = court.get("min_justice_trust", 0)
        if court_mjt < 0.70:
            errors.append(
                f"constitutional_court.min_justice_trust must be >= 0.70, got {court_mjt}"
            )

    if errors:
        print("Invariant check failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Invariant check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(check())
