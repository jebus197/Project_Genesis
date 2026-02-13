# Project Genesis Threat Model and Invariants (v0.2)

Status: Foundational engineering control
Date: February 13, 2026
Owner: George Jackson

## 1) Plain-language definition

Threat modelling means identifying:

1. what must be protected,
2. who or what might cause harm,
3. how harm could happen,
4. what controls prevent or contain that harm.

In short: it is a structured way to design for failure and attack before they happen.

## 2) Why this exists

Genesis is a trust and governance system. If we do not model threats explicitly, we risk "audit theatre" where controls look strong on paper but fail under pressure.

This file defines the baseline adversaries, trust boundaries, and non-negotiable invariants for Genesis.

## 3) Protected assets

1. Constitutional authority integrity (human-only constitutional governance).
2. Trust score integrity (earned only from verified contribution quality).
3. Review integrity (independent, non-collusive verification pathways).
4. Reviewer heterogeneity (no single model family or method type dominates verification).
5. Evidence integrity (tamper-evident, reproducible event history).
6. Operational safety (high-risk workflows remain fail-closed).
7. Public legitimacy (claims match enforceable behavior).
8. Genesis phase integrity (bootstrap governance cannot be captured or extended indefinitely).
9. Commitment integrity (cryptographic settlement cannot degrade across commitment tiers).
10. Normative legitimacy (subjective disputes require human adjudication, not machine consensus).

## 4) Adversaries and failure actors

1. Malicious worker or reviewer identities.
2. Collusion rings among reviewers.
3. Sybil/farm identities attempting trust inflation.
4. High-throughput low-quality actors attempting metric gaming.
5. Insiders attempting governance capture or policy bypass.
6. External attackers attempting key compromise, replay, or ledger manipulation.
7. Benign but risky failures (operator mistakes, schema drift, weak review discipline).
8. Founder capture during genesis phase (single-party control prolonged beyond bootstrap).
9. Reviewer monoculture (all reviewers share the same model family or method, correlated failure modes).
10. Machine consensus override on normative disputes (displacing human judgment on value-laden questions).

## 5) Trust boundaries

1. Human constitutional governance boundary:
- Constitutional proposal and voting authority is verified-human only.

2. Machine operational trust boundary:
- Machine trust affects operational permissions only, never constitutional voting.

3. Evidence boundary:
- Raw artifacts may be off-chain, but cryptographic commitments and signatures must be verifiable.

4. Policy enforcement boundary:
- No critical state transition is valid unless policy checks and required review gates pass.

## 6) Primary threat scenarios and controls

| Threat scenario | Primary control | Secondary control |
| --- | --- | --- |
| Self-review or reciprocal review approval | Hard no-self-review enforcement | Reviewer non-overlap and conflict checks |
| Review collusion ring | Randomized assignment + quorum review on higher risk | Adversarial test tasks and anomaly detection |
| Throughput gaming (volume over quality) | Quality-gated trust minting (`Q_min`) | Slow-gain/fast-loss trust dynamics |
| Machine trust abuse after severe failures | Zero-trust quarantine at `T_M = 0` | Supervised re-certification + probation |
| Repeat machine failures | Decommission thresholds | Lineage-linked re-entry controls |
| Constitutional capture attempts | Multi-chamber human ratification + constrained-random assignment | Region/org diversity caps + public challenge window |
| Identity-gate bypass logic | Identity signals scoped as support only | No identity signal can grant trust or voting authority |
| Evidence tampering or opaque claims | Signed events + deterministic commitment verification | Independent replay and external verifier checks |
| Founder capture during genesis | Hard time limits on G0 (365d) + mandatory G1 retroactive ratification | One-way phase transitions, no regression |
| Genesis phase stagnation | Hard time limits per phase + extension caps | Population thresholds trigger automatic phase advancement |
| Reviewer monoculture (correlated failures) | R2 requires ≥2 model families + ≥2 method types | R1 requires ≥2 model families; reviewer metadata enforced |
| Machine consensus on normative disputes | `normative_requires_human_adjudication = true` | Normative panel: ≥3 humans, ≥2 regions, ≥2 orgs |
| L1 commitment degradation under cost pressure | Commitment tiers (C0→C2) enforce minimum anchor frequency | Constitutional lifecycle events always anchor to L1 immediately |
| Commitment tier regression | One-way progression C0→C1→C2 tied to population thresholds | `C0_max_humans < C1_max_humans`, strictly increasing |

## 7) Non-negotiable invariants

The system is invalid if any of the following are possible:

### 7.1) Original invariants (v0.1)

1. Machine trust contributes to constitutional voting.
2. Trust is minted from volume without quality gate pass.
3. Trust is minted from proof-of-work evidence alone.
4. A machine at `T_M = 0` can access privileged routing.
5. A machine bypasses re-certification or decommission controls by identity reset.
6. A constitutional change activates without required human chamber thresholds.
7. A critical decision exists without signed evidence and reproducible commitment checks.
8. Identity signals alone grant trust, privileged routing, or constitutional authority.

### 7.2) Genesis protocol invariants (v0.2)

9. The system operates without a defined genesis phase when participant count is below full constitutional thresholds.
10. A genesis phase extends indefinitely without a hard time limit (`G0_MAX_DAYS`, `G1_MAX_DAYS`).
11. The founder retains veto power after provisional chambers activate in G1.
12. G0 provisional decisions survive without retroactive ratification in G1 (within `G0_RATIFICATION_WINDOW_DAYS`).
13. The system regresses from a later genesis phase to an earlier one.
14. Genesis phase thresholds are not strictly increasing (`G0_max_humans < G1_max_humans < G2_max_humans`).
15. G2 geographic constraints are not stricter than G1 (`R_min` must increase, `c_max` must decrease).

### 7.3) Reviewer heterogeneity invariants (v0.2)

16. All reviewers on an R2 task share the same model family (requires `min_model_families ≥ 2`).
17. All reviewers on an R2 task use the same verification method (requires `min_method_types ≥ 2`).
18. All reviewers on an R1 task share the same model family (requires `min_model_families ≥ 2`).
19. A reviewer record omits `model_family` or `method_type` metadata.
20. A `method_type` value is used that is not in the canonical set: `{reasoning_model, retrieval_augmented, rule_based_deterministic, human_reviewer}`.

### 7.4) Normative dispute resolution invariants (v0.2)

21. A normative task is closed by machine consensus alone without human adjudication.
22. A normative adjudication panel has fewer than 3 humans, 2 regions, or 2 organizations.
23. A normative adjudication produces a binding outcome without documented reasoning.
24. A task is processed without a `domain_type` classification (`objective`, `normative`, or `mixed`).

### 7.5) Commitment tier invariants (v0.2)

25. L1 commitment integrity is reduced at any commitment tier.
26. A constitutional lifecycle event (parameter change, decommission, chamber vote) is not anchored to L1 immediately regardless of commitment tier.
27. The C1 anchor interval is not shorter (stricter) than C0.
28. Commitment tier thresholds are not strictly increasing (`C0_max_humans < C1_max_humans`).

## 8) Detection and response posture

1. Detection:
- Continuous policy gate telemetry,
- review anomaly detection,
- trust-volatility monitoring,
- commitment verification failures,
- genesis phase deadline monitoring (approaching `G0_MAX_DAYS`, `G1_MAX_DAYS`),
- reviewer heterogeneity monitoring (model family and method type distribution drift),
- normative escalation rate tracking (fraction of tasks triggering human adjudication),
- commitment tier anchor lag monitoring (time since last L1 anchor vs. tier target).

2. Response:
- fail-closed state hold,
- incident creation and escalation,
- temporary privilege freeze,
- replay audit and corrective action,
- genesis phase extension request (one-time, capped at `G0_EXTENSION_DAYS`),
- forced normative escalation when agreement falls below `NORMATIVE_AGREEMENT_THRESHOLD`.

3. Recovery:
- human adjudication for disputed high-risk outcomes,
- controlled re-certification or formal decommission for machine identities,
- on-chain parameter-change trail for governance updates,
- genesis phase advancement when population threshold is met.

## 9) Review cadence and change triggers

Threat model review is mandatory:

1. quarterly,
2. after any high-severity incident,
3. before expanding into new high-risk domains,
4. before changing constitutional trust parameters.

## 10) Documentation rule

This threat model is a living control document. It must be updated whenever new attack paths or governance failure modes are discovered.

## 11) Executable enforcement hooks

Threat-model controls are not documentation-only. Baseline executable checks:

1. `python3 tools/check_invariants.py` — validates all invariants from sections 7.1–7.5 against machine-readable config.
2. `python3 tools/verify_examples.py` — validates worked examples against runtime policy including heterogeneity, domain type, and reviewer metadata.

Policy artifacts checked:

1. `config/constitutional_params.json` (v0.2 — includes genesis, commitment_tiers, reviewer_heterogeneity, normative_resolution)
2. `config/runtime_policy.json` (v0.2 — includes min_model_families, min_method_types, valid_domain_types, normative_resolution)
3. `examples/worked_examples/low_risk_mission.json` (includes domain_type, reviewer metadata)
4. `examples/worked_examples/high_risk_mission.json` (demonstrates R2 heterogeneity compliance)

## 12) Invariant coverage matrix

| Invariant group | Count | Config enforcement | Executable check | Design test coverage |
| --- | --- | --- | --- | --- |
| Original (v0.1) | 8 | `constitutional_params.json` | `check_invariants.py` | Tests 1–28 |
| Genesis protocol (v0.2) | 7 | `constitutional_params.json` § genesis | `check_invariants.py` § genesis | Tests 29–33 |
| Reviewer heterogeneity (v0.2) | 5 | `runtime_policy.json` § min_model_families/min_method_types | `check_invariants.py` § heterogeneity, `verify_examples.py` | Test 34 |
| Normative resolution (v0.2) | 4 | `runtime_policy.json` § normative_resolution | `check_invariants.py` § normative | Tests 35–36 |
| Commitment tiers (v0.2) | 4 | `constitutional_params.json` § commitment_tiers | `check_invariants.py` § commitment | Test 37 |
| **Total** | **28** | | | |
