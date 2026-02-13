# Project Polaris System Blueprint

Status: Draft blueprint for review before commit  
Date: February 13, 2026  
Owner: George Jackson

## 1. Blueprint objective

This document defines how the Polaris moving parts work together as one executable system.

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

  M --> Z["Anchor Builder"]
  Y --> Z
  Z --> AA["Merkle Root Set"]
  AA --> AB["Threshold Decision Certificate"]
  AB --> AC["On Chain Anchor Commit"]
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
  G --> J["Anchor Updated Trust Delta Root"]
```

### 4.1 Trust math

Definitions:
1. `T_H(i)` human constitutional trust for actor `i`.
2. `T_M(j)` machine operational trust for actor `j`.
3. `T_cap = min(T_abs_max, mean(T_H) + k * std(T_H))`.

Update:
1. `T_next_raw = T_now + gain - penalty - dormancy_decay`.
2. `T_next = clip(T_next_raw, T_floor, T_cap)`.
3. `gain = min(alpha * verified_quality, u_max)` and can only be produced from proof-of-trust evidence.

Hard rules:
1. Proof-of-work evidence proves work occurred.
2. Proof-of-trust evidence proves independently verified quality and policy compliance over time.
3. Proof-of-work evidence alone cannot mint trust.

### 4.2 Fast elevation gate

Gate trigger:
1. If `DeltaT > delta_fast` in one epoch, update is suspended.

Current default thresholds:
1. `delta_fast = 0.02`.
2. `q_h >= 30*` independent high-trust human signatures.
3. `r_h >= 3` regions represented.
4. `o_h >= 3` organizations represented.

---

## 5. Constitutional governance flow

```mermaid
flowchart TD
  A["Constitutional Proposal"] --> B["Eligibility Gate T_H >= tau_prop"]
  B --> C["Multi Sponsor Requirement"]
  C --> D["Eligibility Snapshot Anchor"]
  D --> E["Constrained Random Chamber Assignment"]
  E --> F["Proposal Chamber Vote nP kP"]
  F -->|Pass| G["Ratification Chamber Vote nR kR"]
  F -->|Fail| Z["Proposal Rejected"]
  G -->|Pass| H["Public Challenge Window"]
  G -->|Fail| Z
  H --> I["Challenge Chamber Vote nC kC"]
  I -->|Pass| J["Decision Certificate BLS Threshold"]
  I -->|Fail| Z
  J --> K["Amendment Hash Anchor On Chain"]
  K --> L["Activation After Finality"]
  L --> M["Updated Constitution State"]
```

Pass conditions:
1. All required chambers pass threshold.
2. Geographic and organization distribution constraints pass.
3. Non-overlap and conflict-of-interest rules pass.
4. Certificate verifies and chain anchor finalizes.

---

## 6. Cryptographic anchoring and external verification flow

```mermaid
sequenceDiagram
  participant Runtime as Runtime Services
  participant Roots as Root Builder
  participant Committee as Threshold Committee
  participant Chain as L1 Settlement Chain
  participant Verifier as External Verifier

  Runtime->>Roots: Emit canonical records
  Roots->>Roots: Build deterministic Merkle roots SHA-256
  Roots->>Committee: Anchor payload and root set
  Committee->>Committee: Sign decision certificate BLS threshold
  Committee->>Chain: Publish anchor commitment
  Verifier->>Chain: Fetch transaction and anchor hash
  Verifier->>Runtime: Fetch released records and inclusion proofs
  Verifier->>Verifier: Recompute roots and verify signatures
  Verifier->>Verifier: Accept if roots cert and chain commit match
```

Binding crypto defaults:
1. Settlement chain: Ethereum Mainnet (`chain_id = 1`).
2. Anchor interval: `1 hour` plus event-triggered anchors for constitutional lifecycle events.
3. Hash function: `SHA-256`.
4. Identity and event signatures: `Ed25519`.
5. Decision certificate: threshold `BLS12-381`.
6. Canonical JSON: RFC 8785.
7. Sampling seed for constrained-random assignment: `SHA256(public_beacon_value || previous_anchor_hash || chamber_nonce)`.

---

## 7. Deterministic constrained-random chamber selection

```python
def select_chamber_members(
    eligible_pool,
    chamber_size,
    public_beacon_value,
    previous_anchor_hash,
    chamber_nonce,
    region_cap,
    min_regions,
    min_orgs,
    recusal_set,
):
    # 1) Pre-committed seed
    seed = sha256(public_beacon_value + previous_anchor_hash + chamber_nonce)

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
| Task coordination | Mission record, dependency rules | Task graph | DAG validity, no orphan tasks | Block graph activation |
| Worker execution | Task assignment | Output plus evidence bundle | Evidence schema completeness | Reject submission |
| Independent review | Output plus evidence | Approve reject rework decision | No self-review, reviewer independence | Route to rework |
| Trust minting | Verified events plus review outcomes | Trust delta | Proof-of-trust required, PoW alone insufficient | Suspend trust update |
| Fast elevation guard | Proposed trust delta | Applied or suspended delta | `DeltaT <= delta_fast` or quorum path | Open incident and hold delta |
| Constitutional governance | Proposal and eligibility snapshot | Approved or rejected amendment | Chamber thresholds and distribution constraints | Reject amendment |
| Anchoring | Roots plus certificates | On-chain commitment | Deterministic root reproducibility | Block commit |
| Verification | Public records and proofs | Validation report | Signature and inclusion proof validity | Mark state unverifiable |
| Appeals and disputes | Incident or challenge request | Overturn or uphold decision | Signed audit trail and reason codes | Keep prior state active |

---

## 9. Minimum implementation contract

A deployment is not valid unless all are true:
1. Every trust-affecting event is signed and anchor-linked.
2. Every constitutional event is chamber-gated and certificate-signed.
3. Every constrained-random assignment can be independently replayed.
4. Every critical state transition is auditable from public commitments.
5. Any verification failure leaves state unchanged until resolved.

---

## 10. Review notes

Parameters marked with `*` are intentionally flagged for further human review.

Current flagged parameter:
1. `q_h = 30*`

\* subject to review
