# Project Genesis System Blueprint

Status: Draft blueprint for review before commit (v0.2)
Date: February 13, 2026
Owner: George Jackson

## 1. Blueprint objective

This document defines how the Genesis moving parts work together as one executable system.

Design target:
1. Mission execution must be fast and auditable.
2. Trust must be minted only from cryptographically verifiable, independently reviewed evidence.
3. Constitutional control must remain distributed and anti-capture by construction.
4. Every critical transition must fail closed when validation is incomplete.

Canonical parameter source:
1. `TRUST_CONSTITUTION.md` remains the sole source of parameter truth.
2. This blueprint describes mechanism wiring, execution flow, and verification logic.

---

## 2. End-to-end interaction chart

```mermaid
flowchart TD
  A["Human Mission Owner"] --> B["Mission Intake"]
  B --> C["Mission Layer"]
  C --> D["Coordination Layer"]
  D --> E["Task Graph"]
  E --> F["Worker Agents"]
  F --> G["Evidence Bundles"]
  G --> H["Verification Layer"]
  H --> I["Independent Reviewer Set"]
  I -->|Approve| J["Integrator Agent"]
  I -->|Reject| D
  J --> K["Human Final Gate"]
  K -->|Approve| L["Governance Layer Commit"]
  K -->|Reject| D

  L --> M["Evidence Layer Ledger"]
  M --> N["Trust Engine"]
  N --> O["Delta Guard"]
  O -->|DeltaT <= delta_fast| P["Apply Trust Delta"]
  O -->|DeltaT > delta_fast| Q["Human Revalidation Quorum"]
  Q -->|q_h r_h o_h Pass| P
  Q -->|Fail| R["Suspend Delta and Raise Incident"]

  P --> M
  R --> S["Appeals and Dispute Workflow"]
  S --> M

  L --> T["Constitutional Change Engine"]
  T --> U["Proposal Chamber"]
  U -->|Pass| V["Ratification Chamber"]
  U -->|Fail| W["Change Rejected"]
  V -->|Pass| X["Challenge Chamber"]
  V -->|Fail| W
  X -->|Pass| Y["Amendment Activation"]
  X -->|Fail| W

  M --> Z["Commitment Builder"]
  Y --> Z
  Z --> AA["Merkle Root Set"]
  AA --> AB["Threshold Decision Certificate"]
  AB --> AC["On-Chain Commitment Publish"]
  AC --> AD["Public Verifier"]
```

---

## 3. Mission and task state machine

```mermaid
stateDiagram-v2
  [*] --> Draft
  Draft --> Scoped: "Mission owner defines scope and risk"
  Scoped --> Decomposed: "Planner builds task graph"
  Decomposed --> InProgress: "Workers execute tasks"
  InProgress --> EvidenceAttached: "Evidence bundle submitted"
  EvidenceAttached --> UnderReview: "Independent reviewer routing"
  UnderReview --> Rework: "Review failed or insufficient evidence"
  Rework --> InProgress: "Task corrected"
  UnderReview --> Integrated: "Review approved"
  Integrated --> FinalHumanGate: "Integrator assembles mission output"
  FinalHumanGate --> Completed: "Human approval for required risk class"
  FinalHumanGate --> Rejected: "Human rejection"
  Rejected --> Decomposed: "Re-plan mission path"
  Completed --> [*]
```

Operational rule:
1. No mission in a designated high-risk class can transition to `Completed` without human final approval.

---

## 4. Trust computation and minting pipeline

```mermaid
flowchart LR
  A["Verified Contribution Event"] --> B["Proof of Work Evidence Check"]
  B --> C["Proof of Trust Evidence Check"]
  C --> D["Independent Review Integrity Check"]
  D --> E["Compute Raw Gain and Penalty"]
  E --> F["Apply Delta Guard"]
  F -->|DeltaT <= delta_fast| G["Commit Trust Update"]
  F -->|DeltaT > delta_fast| H["Require Human Revalidation"]
  H -->|Pass| G
  H -->|Fail| I["Suspend Update and Open Incident"]
  G --> J["Publish Updated Trust Delta Root"]
```

### 4.1 Trust math

Definitions:
1. `T_H(i)` human constitutional trust for actor `i`.
2. `T_M(j)` machine operational trust for actor `j`.
3. `T_cap_H = min(T_abs_max_H, mean(T_H) + k_H * std(T_H))`.
4. `T_cap_M = T_abs_max_M`.

Update:
1. `T_H_next = clip(T_H_now + gain_H - penalty_H - dormancy_decay_H, T_floor_H, T_cap_H)`.
2. `T_M_next = clip(T_M_now + gain_M - penalty_M - freshness_decay_M, 0, T_cap_M)`.
3. `gain_H` and `gain_M` can only be produced from proof-of-trust evidence.
4. Machine freshness decay includes verification age and environment drift.

Hard rules:
1. Proof-of-work evidence proves work occurred.
2. Proof-of-trust evidence proves independently verified quality and policy compliance over time.
3. Proof-of-work evidence alone cannot mint trust.
4. Human trust cannot fall below a non-zero floor (`T_floor_H > 0`).
5. Machine trust may decay to zero (`T_floor_M = 0`); `T_M = 0` triggers operational quarantine and supervised re-certification before privileged re-entry.

### 4.2 Fast elevation gate

Gate trigger:
1. If `DeltaT > delta_fast` in one epoch, update is suspended.

Current default thresholds (full constitutional mode, G3):
1. `delta_fast = 0.02`.
2. `q_h >= 30*` independent high-trust human signatures.
3. `r_h >= 3` regions represented.
4. `o_h >= 3` organizations represented.

Genesis-phase scaled thresholds:
1. G1 (50–500 participants): `q_h = 7, r_h = 2, o_h = 2`.
2. G2 (500–2000 participants): `q_h = 15, r_h = 3, o_h = 3`.
3. G3 (2000+ participants): full constitutional thresholds apply.

### 4.3 Risk-tier review policy

Risk-tier execution profile:

| Risk tier | Default review topology | Pass rule | Heterogeneity | Extra controls |
| --- | --- | --- | --- | --- |
| `R0` (low) | `1 worker + 1 reviewer` | Reviewer approval | No constraint | Evidence schema required |
| `R1` (moderate) | `1 worker + 2 reviewers` | `2/2` approval | `≥ 2` model families | Reviewer non-overlap and conflict checks |
| `R2` (high) | `1 worker + 5 reviewers` | `>= 4/5` approval | `≥ 2` model families, `≥ 2` method types | `>= 3` regions, `>= 3` organizations, mandatory human final gate |
| `R3` (constitutional) | Human chambers only | Chamber thresholds in constitution | N/A (human only) | Machine vote weight fixed at `0` |

Hard policy:
1. Trust gain is quality-gated at every tier; if `Q < Q_min`, no trust minting occurs.
2. Swarm review is reserved for higher-risk tiers and cannot be used as a truth oracle by itself.
3. Subjective or normative disputes escalate to human adjudication even when reviewer quorum passes.
4. Every reviewer must declare `model_family` and `method_type` metadata. Valid method types: `{reasoning_model, retrieval_augmented, rule_based_deterministic, human_reviewer}`.
5. Every task must be classified by `domain_type`: `objective` (factual), `normative` (value-laden), or `mixed`. Normative and mixed tasks require human adjudication when agreement falls below `NORMATIVE_AGREEMENT_THRESHOLD = 0.60`.

### 4.4 Identity-signal policy

Identity signals are support controls, not authority controls.

1. Proof-of-personhood/proof-of-agenthood, timing profiles, and hardware attestations can raise abuse alerts.
2. Identity signals alone cannot grant trust gain, privileged routing, or constitutional authority.
3. High-risk decisions require layered evidence: identity history, policy compliance history, independent review, and auditable records.

### 4.5 Runtime policy mapping (executable)

Canonical runtime policy artifacts:
1. `config/runtime_policy.json` (mission-class-to-tier mapping and review topology).
2. `config/constitutional_params.json` (machine-readable constitutional parameter mirror).

Default mission class mapping:
1. `documentation_update -> R0`
2. `internal_operations_change -> R1`
3. `regulated_analysis -> R2`
4. `constitutional_change -> R3`

Execution requirement:
1. Runtime must resolve mission class to risk tier using `config/runtime_policy.json`.
2. Runtime must reject mission execution if mission class is unmapped.
3. Runtime must reject mission execution if requested review topology is weaker than tier minimum.
4. Runtime must reject any non-human constitutional voting path (`R3` must remain human-only).

---

## 5. Constitutional governance flow

```mermaid
flowchart TD
  A["Constitutional Proposal"] --> B["Eligibility Gate T_H >= tau_prop"]
  B --> C["Multi Sponsor Requirement"]
  C --> D["Eligibility Snapshot Commitment"]
  D --> E["Constrained Random Chamber Assignment"]
  E --> F["Proposal Chamber Vote nP kP"]
  F -->|Pass| G["Ratification Chamber Vote nR kR"]
  F -->|Fail| Z["Proposal Rejected"]
  G -->|Pass| H["Public Challenge Window"]
  G -->|Fail| Z
  H --> I["Challenge Chamber Vote nC kC"]
  I -->|Pass| J["Decision Certificate BLS Threshold"]
  I -->|Fail| Z
  J --> K["Publish Amendment Hash Commitment On-Chain"]
  K --> L["Activation After Finality"]
  L --> M["Updated Constitution State"]
```

Pass conditions:
1. All required chambers pass threshold.
2. Geographic and organization distribution constraints pass.
3. Non-overlap and conflict-of-interest rules pass.
4. Certificate verifies and chain commitment reaches finality.
5. Machine constitutional voting weight remains `w_M_const = 0` for all ballots.

### 5.1 Genesis bootstrap protocol

The full constitutional governance flow (above) requires chamber sizes of 41/61/101. Before the participant pool reaches those thresholds, the system operates under a phased genesis protocol:

| Phase | Participants | Chamber sizes (P/R/C) | Geographic constraint | Time limit |
| --- | --- | --- | --- | --- |
| G0 (founder stewardship) | 0–50 | No chambers; founder operates under constitutional principles with public audit trail | N/A | 365 days (+180d extension, one-time) |
| G1 (provisional chambers) | 50–500 | 11 / 17 / 25 | ≥ 3 regions, c_max = 0.40 | 730 days |
| G2 (scaled chambers) | 500–2000 | 21 / 31 / 51 | ≥ 5 regions, c_max = 0.25 | None (advances on threshold) |
| G3 (full constitution) | 2000+ | 41 / 61 / 101 | ≥ 8 regions, per constitution | Steady state |

Hard rules:
1. Phase transitions are one-way; regression to an earlier phase is prohibited.
2. All G0 provisional decisions must be retroactively ratified by G1 chambers within 90 days of G1 activation.
3. The founder loses veto power the moment G1 chambers activate.
4. If G0 exceeds its time limit without reaching 50 participants, the project fails closed.

---

## 6. Cryptographic commitments and external verification flow

```mermaid
sequenceDiagram
  participant Runtime as Runtime Services
  participant Roots as Root Builder
  participant Committee as Threshold Committee
  participant Chain as L1 Settlement Chain
  participant Verifier as External Verifier

  Runtime->>Roots: Emit canonical records
  Roots->>Roots: Build deterministic Merkle roots SHA-256
  Roots->>Committee: Commitment payload and root set
  Committee->>Committee: Sign decision certificate BLS threshold
  Committee->>Chain: Publish commitment transaction
  Verifier->>Chain: Fetch transaction and commitment hash
  Verifier->>Runtime: Fetch released records and inclusion proofs
  Verifier->>Verifier: Recompute roots and verify signatures
  Verifier->>Verifier: Accept if roots cert and chain commit match
```

Binding crypto defaults:
1. Settlement chain: Ethereum Mainnet (`chain_id = 1`).
2. Hash function: `SHA-256`.
3. Identity and event signatures: `Ed25519`.
4. Decision certificate: threshold `BLS12-381`.
5. Canonical JSON: RFC 8785.
6. Sampling seed for constrained-random assignment: `SHA256(public_beacon_value || previous_commitment_hash || chamber_nonce)`.

Progressive commitment strategy:
1. **C0** (≤ 500 participants): L2 rollup primary, L1 anchor every 24 hours. Constitutional lifecycle events anchor to L1 immediately.
2. **C1** (500–5000 participants): L2 rollup primary, L1 anchor every 6 hours. Constitutional lifecycle events anchor to L1 immediately.
3. **C2** (5000+ participants): Full L1 hourly commitments plus event-triggered commitments for constitutional lifecycle events.
4. All commitment tiers maintain identical cryptographic integrity — only anchor frequency changes.
5. Commitment tier progression is one-way (C0 → C1 → C2); regression is prohibited.

---

## 7. Deterministic constrained-random chamber selection

```python
def select_chamber_members(
    eligible_pool,
    chamber_size,
    public_beacon_value,
    previous_commitment_hash,
    chamber_nonce,
    region_cap,
    min_regions,
    min_orgs,
    recusal_set,
):
    # 1) Pre-committed seed
    seed = sha256(public_beacon_value + previous_commitment_hash + chamber_nonce)

    # 2) Deterministic ranking
    ranked = sorted(
        [a for a in eligible_pool if a.id not in recusal_set],
        key=lambda a: sha256(seed + a.id),
    )

    selected = []
    region_count = {}
    org_count = {}

    # 3) Deterministic sampling without replacement with hard constraints
    for actor in ranked:
        if len(selected) == chamber_size:
            break

        if violates_region_cap(actor, selected, region_cap):
            continue
        if violates_conflict_rules(actor):
            continue

        selected.append(actor)
        region_count[actor.region] = region_count.get(actor.region, 0) + 1
        org_count[actor.org] = org_count.get(actor.org, 0) + 1

    # 4) Fail closed if diversity constraints not met
    if len(selected) < chamber_size:
        raise FailClosed("insufficient eligible participants")
    if len(region_count) < min_regions:
        raise FailClosed("region diversity constraint failed")
    if len(org_count) < min_orgs:
        raise FailClosed("organization diversity constraint failed")

    return selected
```

Fail-closed principle:
1. If constraints cannot be satisfied deterministically, selection does not proceed.
2. Governance action remains blocked until constraints are satisfiable.

---

## 8. Control matrix (inputs outputs invariants failure gates)

| Subsystem | Inputs | Outputs | Invariants | Fail-closed gate |
| --- | --- | --- | --- | --- |
| Mission intake | Human mission spec, risk class | Mission record | Required fields complete, risk class present | Reject incomplete mission |
| Risk-tier resolver | Mission class, runtime policy map | Effective risk tier and review topology | Mission class must map to tier, topology must meet tier minimums | Block mission activation |
| Task coordination | Mission record, dependency rules | Task graph | DAG validity, no orphan tasks | Block graph activation |
| Worker execution | Task assignment | Output plus evidence bundle | Evidence schema completeness | Reject submission |
| Independent review | Output plus evidence | Approve reject rework decision | No self-review, reviewer independence | Route to rework |
| Trust minting | Verified events plus review outcomes | Trust delta | Proof-of-trust required, PoW alone insufficient | Suspend trust update |
| Machine lifecycle | Trust state plus re-cert evidence | Active, quarantined, or decommissioned machine state | `T_M = 0` quarantine, re-cert thresholds, decommission thresholds | Block privileged routing |
| Fast elevation guard | Proposed trust delta | Applied or suspended delta | `DeltaT <= delta_fast` or quorum path | Open incident and hold delta |
| Constitutional governance | Proposal and eligibility snapshot | Approved or rejected amendment | Chamber thresholds and distribution constraints | Reject amendment |
| Blockchain commitments | Roots plus certificates | On-chain commitment | Deterministic root reproducibility | Block commit |
| Verification | Public records and proofs | Validation report | Signature and inclusion proof validity | Mark state unverifiable |
| Appeals and disputes | Incident or challenge request | Overturn or uphold decision | Signed audit trail and reason codes | Keep prior state active |
| Genesis phase controller | Participant count, phase clock | Phase transition or fail-closed | Hard time limits, one-way transitions, retroactive ratification | Block operations if phase expired |
| Reviewer heterogeneity gate | Reviewer set metadata | Accept or reject reviewer assignment | Model family and method type diversity per tier | Block review if diversity insufficient |
| Normative resolution | Task domain_type, reviewer agreement | Human adjudication or auto-close | Normative tasks require human panel | Escalate to adjudication |
| Commitment tier controller | Participant count, L1 anchor schedule | Anchor transaction | Minimum anchor frequency per tier, no regression | Force immediate anchor for lifecycle events |

---

## 9. Minimum implementation contract

A deployment is not valid unless all are true:
1. Every trust-affecting event is signed and commitment-linked.
2. Every constitutional event is chamber-gated and certificate-signed.
3. Every constrained-random assignment can be independently replayed.
4. Every critical state transition is auditable from public commitments.
5. Any verification failure leaves state unchanged until resolved.
6. Threat-model invariants in `THREAT_MODEL_AND_INVARIANTS.md` (all 28 invariants, v0.2) are satisfied.
7. At least one low-risk and one high-risk mission flow are reproducible end-to-end from evidence.
8. `tools/check_invariants.py` and `tools/verify_examples.py` both pass against repository policy artifacts.
9. Genesis phase is correctly identified and enforced based on current participant count.
10. Reviewer heterogeneity constraints are enforced per risk tier (model family and method type diversity).
11. Domain type classification is present on all tasks; normative tasks trigger human adjudication when agreement is below threshold.
12. Commitment tier is correctly identified and L1 anchor frequency meets or exceeds tier minimum.

---

## 10. Review notes

Parameters marked with `*` are intentionally flagged for further human review.

Current flagged parameter:
1. `q_h = 30*` (full constitution G3 threshold; genesis-phase values G1=7, G2=15 are derived from population scaling).

\* subject to review

Version history:
1. v0.1 — initial blueprint with core trust, review, and governance mechanisms.
2. v0.2 — added genesis bootstrap protocol (§5.1), progressive commitment strategy (§6), reviewer heterogeneity (§4.3), normative dispute resolution (§4.3), genesis-scaled fast-elevation thresholds (§4.2), and updated control matrix (§8).
