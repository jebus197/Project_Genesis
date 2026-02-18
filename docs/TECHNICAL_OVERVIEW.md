# Project Genesis — Technical Overview

This document covers the full technical architecture of Project Genesis. It is intended for engineers, researchers, auditors, and anyone who wants to understand how the system actually works beneath the governance principles described in the [README](../README.md).

The [Trust Constitution](../TRUST_CONSTITUTION.md) is the canonical source for all parameter values. This document explains the reasoning behind them.

---

## Table of Contents

1. [Trust Model](#trust-model)
2. [Bounded Trust Economy](#bounded-trust-economy)
3. [Risk Tiers and Review Requirements](#risk-tiers-and-review-requirements)
4. [Reviewer Heterogeneity](#reviewer-heterogeneity)
5. [Three-Tier Justice System](#three-tier-justice-system)
6. [Anti-Capture Architecture](#anti-capture-architecture)
7. [Compliance and Harmful Work Prevention](#compliance-and-harmful-work-prevention)
8. [Genesis Bootstrap Protocol](#genesis-bootstrap-protocol)
9. [Skill Taxonomy and Proficiency Model](#skill-taxonomy-and-proficiency-model)
10. [Domain-Specific Trust](#domain-specific-trust)
11. [Labour Market](#labour-market)
12. [Skill Lifecycle](#skill-lifecycle)
13. [Compensation Model](#compensation-model)
14. [Genesis Common Fund](#genesis-common-fund)
15. [Workflow Orchestration](#workflow-orchestration)
16. [Cryptographic Implementation Profile](#cryptographic-implementation-profile)
17. [Blockchain Anchoring](#blockchain-anchoring)
18. [Identity Verification](#identity-verification)
19. [Success Metrics](#success-metrics)
20. [Governance Engine Architecture](#governance-engine-architecture)

---

## Trust Model

Genesis maintains two separate trust domains because humans and machines play fundamentally different roles in the system.

### Human trust (`T_H`)

Human trust determines both operational permissions (which tasks you can take on, which reviews you can conduct) and constitutional authority (whether you can propose or vote on governance changes).

The trust score is a weighted sum of four components:

```
T_H = w_Q · Q_H  +  w_R · R_H  +  w_V · V_H  +  w_E · E_H
```

Where:
- `Q_H` = quality score — derived from review outcomes on work you've produced.
- `R_H` = review reliability — how consistent and accurate your reviews are, measured against subsequent outcomes.
- `V_H` = verification record — your track record of providing valid evidence and following process requirements.
- `E_H` = effort score — measures reasoning effort proportional to mission complexity tier.

Default weights: `w_Q = 0.70`, `w_R = 0.20`, `w_V = 0.05`, `w_E = 0.05`.

These weights mean quality dominates. An actor who produces high volumes of mediocre work will not accumulate meaningful trust, because `Q` stays low regardless of volume. The effort component (`E`) adds a further cost dimension: each risk tier has a minimum effort threshold that increases monotonically (R0: 0.10, R1: 0.30, R2: 0.50, R3: 0.70). This makes gaming more expensive — an attacker cannot simply stamp "approve" on high-risk work without investing proportional reasoning effort. Crucially, effort alone cannot mint trust: the quality gate still applies, so effort without quality produces zero gain.

### Machine trust (`T_M`)

Machine trust uses the same formula but grants only operational permissions. The constitution permanently pins machine constitutional voting weight at zero (`w_M_const = 0`). This means no amount of operational excellence by a machine can translate into governance authority.

Why? Because the system that governs AI must not be governable by AI. This is a permanent architectural boundary, not a tuning parameter.

### Trust eligibility thresholds

Two thresholds gate participation in governance:

- `tau_vote = 0.60` — minimum trust to vote on constitutional matters.
- `tau_prop = 0.75` — minimum trust to propose constitutional changes.

These are deliberately high. Proposing a constitutional change is the most consequential action in the system, so it requires a sustained track record.

---

## Bounded Trust Economy

Unbounded trust accumulation creates the same problem as unbounded wealth accumulation: concentration of power. Genesis prevents this through hard structural limits.

### Starting position

Every verified identity — human or machine — enters the system with the same baseline trust: `T_baseline = 0.10`. This is enough to participate in low-risk tasks but not enough for any governance role.

### Growth rules

- Trust increases only through verified quality contributions. Volume without quality produces zero trust gain because of the quality gate (see below).
- Trust growth is rate-limited: no actor can gain more than a defined amount per epoch. This prevents sudden trust spikes from gaming or coordinated manipulation.

### Quality gate

This is one of the most important controls in the system:

```
If Q < Q_min, then trust gain = 0 (regardless of output volume)
```

Default thresholds: `Q_min_H = 0.60` for humans, `Q_min_M = 0.70` for machines (machines face a higher bar because their failure modes are different — they can produce large volumes of superficially correct but subtly wrong output).

The quality gate means you cannot grind your way to high trust through bulk production. Every contribution must pass a quality threshold before it counts toward trust at all.

### Hard caps

- `T_cap_abs = 0.95` — no actor can exceed this trust level under any circumstances.
- `T_cap_rel` — relative cap that limits any single actor's trust relative to the population, preventing dominance even in small pools.

### Decay

Trust is not permanent. It decays over time if you stop contributing:

- **Human decay** is gradual ("dormancy decay") with a grace period. Humans who step away don't lose trust instantly — the system acknowledges that people take breaks, change jobs, or have life events. However, trust never falls below a non-zero human floor (`T_floor_H > 0`), recognising that a human's accumulated track record has lasting value.
- **Machine decay** is faster ("freshness decay") and the floor is zero (`T_floor_M = 0`). Machines that stop being validated go stale quickly, because an unmonitored AI system's reliability cannot be assumed. A machine at zero trust enters operational quarantine and must be re-certified before regaining privileges.

### Protected leave

Life events — illness, bereavement, disability, mental health crises, caregiving, pregnancy, and child care — are not inactivity. When a human actor is granted protected leave through a quorum of domain-specific experts (minimum 3, blind adjudication, randomised selection), their trust score, domain scores, and skill decay clocks are frozen exactly until return. Adjudicators must hold earned domain trust in the relevant professional field. All adjudications are hashed and epoch-anchored.

Death triggers a separate memorialisation flow: family or friends petition a qualified quorum with verifiable evidence, and if approved the account is permanently frozen as a memorial. If a memorialisation was made in error or through malicious misrepresentation, the affected person may petition a legal quorum with proof-of-life evidence to have the memorialised state reversed and their account restored, subject to equally rigorous evidentiary standards.

### Fast-elevation control

If any actor's trust jumps by more than `delta_fast = 0.02` in a single epoch, the jump is automatically suspended. Activation requires:

- At least `q_h = 30` independent high-trust human reviews (scaled down during genesis phases: G1 = 7, G2 = 15).
- Those reviews must come from at least `r_h = 3` regions and `o_h = 3` organisations.

This prevents both gaming (artificially inflating a single actor's trust) and systemic error (a bug or exploit causing unintended trust spikes).

### Recovery

Trust loss is not a death sentence:

- Humans can recover through a low-risk contribution lane — doing small, verified tasks that gradually rebuild their score.
- Machines can recover through supervised re-certification — a structured process with heightened oversight.
- Actors that remain at zero trust beyond decommission thresholds are retired from the system. For machines, this means permanent decommission. For humans, the floor prevents this scenario entirely.

---

## Risk Tiers and Review Requirements

Not all work requires the same level of oversight. Genesis classifies every mission into one of four risk tiers, each with escalating review requirements.

| Tier | Description | Approvals Required | Human Gate | Evidence |
|---|---|---|---|---|
| R0 | Low risk, routine | 1 reviewer | No | Hash + signature |
| R1 | Moderate risk | 2 reviewers, ≥ 2 model families | No | Hash + signature + provenance |
| R2 | High risk | 3 reviewers, ≥ 2 model families, ≥ 2 method types | Yes | Full evidence chain |
| R3 | Critical / safety | Full panel, human-majority | Yes | Full evidence chain + external audit |

The mapping from mission class to risk tier is defined in `config/runtime_policy.json`. This mapping is itself a constitutional artifact — changing it requires governance approval.

### What "model families" and "method types" mean

- **Model family** refers to the underlying AI system: GPT-4o, Claude Opus, Gemini, Llama, etc. Requiring reviewers from different model families prevents correlated errors — if one model has a systematic blind spot, a different model is likely to catch it.
- **Method type** refers to the verification approach: `reasoning_model` (chain-of-thought analysis), `retrieval_augmented` (grounded in external sources), `rule_based_deterministic` (formal rule checking), or `human_reviewer`. Requiring different method types prevents methodological monoculture.

---

## Reviewer Heterogeneity

For high-risk work, Genesis enforces anti-monoculture rules in reviewer selection:

- **R1 tasks**: reviewers must come from ≥ 2 distinct model families.
- **R2 tasks**: reviewers must come from ≥ 2 model families AND ≥ 2 verification method types.
- Every reviewer must declare their `model_family` and `method_type` metadata at assignment time.

Additionally, the reviewer router enforces:

- **Self-review block**: no actor can review their own work, at any risk tier.
- **Geographic diversity**: reviewers must come from multiple regions (specific minimums depend on the genesis phase).
- **Organisational diversity**: reviewers must come from multiple organisations, preventing any single institution from controlling review outcomes.

These rules are enforced by code in the reviewer routing engine, not by policy documents. The system will refuse to complete a review cycle that violates heterogeneity requirements.

---

## Three-Tier Justice System

Disputes are inevitable in any system where work is evaluated, money changes hands, and trust has consequences. What matters is not whether disputes happen, but how they are resolved. Most platforms handle disputes through customer support tickets, opaque internal review, or terms-of-service clauses that grant the platform unilateral authority. Genesis rejects all of these. Its justice system is formal, transparent, structurally fair, and enforced entirely by code.

This is not an aspirational goal — it is a working implementation. The justice system exists because Genesis recognised that a trust-mediated economy without a formal dispute resolution mechanism is simply a dictatorship with extra steps. If the system can penalise you, the system must give you a fair hearing.

The societal precedent here is significant: Genesis demonstrates that algorithmic governance can include due process, not just enforcement. If this model works at scale, it offers a template for any platform that mediates work, payments, or reputation.

### Domain types

Not all questions have objectively correct answers. Genesis distinguishes between three domain types:

- **Objective** — questions with verifiable right/wrong answers (e.g., "does this code compile?").
- **Normative** — questions involving values, ethics, priorities, or subjective judgement (e.g., "is this policy fair?").
- **Mixed** — questions with both objective and normative components.

For normative and mixed domains, machine consensus alone can never close a dispute — human judgement is required. This reflects a core design principle: machines are excellent at checking objective facts but should not be the final authority on questions of values.

### Tier 1 — Automated compliance screening

The first tier operates silently on every mission listing. Before any work reaches a human, the `ComplianceScreener` checks for prohibited content (see the Compliance section below). This layer handles the vast majority of cases — clear violations are rejected automatically, ambiguous cases are flagged for human review.

### Tier 2 — Adjudication panels

When a dispute arises — payment, compliance, abuse, conduct, or normative disagreement — it is heard by a formal adjudication panel. The implementation is in `AdjudicationEngine` (`src/genesis/legal/adjudication.py`).

**Case types** (`AdjudicationType` enum):

- `PAYMENT_DISPUTE` — disagreement over mission payment or escrow release.
- `COMPLIANCE_COMPLAINT` — allegation of prohibited content or harmful work.
- `ABUSE_COMPLAINT` — allegation of verifier or participant misconduct.
- `CONDUCT_COMPLAINT` — broader conduct violations.
- `NORMATIVE_RESOLUTION` — disputes involving subjective judgement calls.

**How a case proceeds:**

1. **Case opened** (`open_case()`): both parties are assigned pseudonyms (`party-{secrets.token_hex(8)}`) — the panel never sees real identities. This blind adjudication prevents bias based on reputation, history, or personal relationships.

2. **Response period** (72 hours): the accused has a structural right to respond before any panel forms. This is not a courtesy — it is a gate enforced by the `RightsEnforcer` (`src/genesis/legal/rights.py`). The `validate_panel_formation_allowed()` method checks that either the response deadline has elapsed or the accused has submitted a response, and that evidence has been disclosed. The panel literally cannot be assembled until these conditions are met.

3. **Panel formation** (`form_panel()`): 5 panelists are selected from the eligible pool. Selection enforces diversity: at least 2 geographic regions and at least 2 organisations. Panelists must have trust ≥ 0.60 (configurable via `min_panelist_trust`). The complainant, accused, and (for appeals) the original panel are excluded.

4. **Deliberation**: each panelist submits a verdict (`UPHELD`, `DISMISSED`, `PARTIAL`, or `ESCALATED_TO_COURT`) with a mandatory written attestation. The attestation requirement forces panelists to articulate their reasoning — it cannot be empty.

5. **Verdict** (`evaluate_verdict()`): a **3/5 supermajority** is required to uphold a complaint or escalate to the Constitutional Court. If no supermajority is reached, the complaint is dismissed. This threshold ensures that marginal cases default to no action.

**Accused rights** (enforced by `RightsEnforcer`):

The rights of the accused are not policy guidelines — they are structural gates that the system enforces before allowing proceedings to advance:

| Right | Enforcement mechanism |
|---|---|
| Right to respond | 72-hour deadline before panel can form |
| Right to evidence | `evidence_disclosed` flag must be True |
| Right to appeal | One appeal within 72 hours of verdict |
| Presumption of good faith | Default in `AccusedRightsRecord` |

**Appeal** (`file_appeal()`): either party may appeal within 72 hours. The appeal creates a new case heard by an entirely different panel — no overlap with the original panelists. Only one appeal per case is permitted. The appeal panel applies the same diversity and supermajority requirements.

**Configuration** (from `config/runtime_policy.json`):

| Parameter | Value | Purpose |
|---|---|---|
| `panel_size` | 5 | Adjudication panel members |
| `panel_min_regions` | 2 | Geographic diversity |
| `panel_min_organizations` | 2 | Organisational diversity |
| `min_panelist_trust` | 0.60 | Minimum trust for panelists |
| `response_period_hours` | 72 | Accused's response window |
| `appeal_window_hours` | 72 | Window to file appeal |
| `supermajority_threshold` | 0.60 | 3/5 for verdict |

### Tier 3 — Constitutional Court

Cases of constitutional significance can be escalated from Tier 2 to the Constitutional Court. This is the highest adjudicative body in the system — its decisions carry the weight of constitutional interpretation. The implementation is in `ConstitutionalCourt` (`src/genesis/legal/constitutional_court.py`).

**Why it exists:** Some disputes transcend individual cases. A disagreement about whether a particular type of work violates the "no harm" principle, or whether a penalty was proportionate to the offence, may have implications for how the constitution is interpreted going forward. These questions need a different kind of tribunal — one with higher trust requirements, stricter diversity rules, and the authority to set advisory precedent.

**Court panel:**

- **7 justices** (not 5 — the higher number reflects the greater significance).
- **Human only** — machines are structurally excluded from constitutional interpretation (`human_only = true`).
- **Trust ≥ 0.70** — higher than Tier 2's 0.60 threshold.
- **Diversity**: at least 3 geographic regions and at least 3 organisations (stricter than Tier 2's 2/2).

**Verdicts:** justices may vote `"uphold"` (affirm Tier 2), `"overturn"` (reverse), or `"remand"` (return for reconsideration). A **5/7 supermajority** is required to overturn a Tier 2 decision — overturning is deliberately harder than affirming.

**Soft precedent:** when a case is decided, the court may record a `PrecedentEntry` — a summary of the question, the ruling, and the rationale. Crucially, precedent in Genesis is **advisory only** (`advisory_only = True`). Each case is decided on its own merits. This is a deliberate design choice: rigid precedent creates power structures around interpretation, where those who can cite prior rulings gain procedural advantage over those who cannot. Genesis prefers principled judgement over institutional inertia.

Precedents can be searched via `search_precedents()` using keyword matching, so that future panels can consider prior reasoning without being bound by it.

**Configuration** (from `config/runtime_policy.json`):

| Parameter | Value | Purpose |
|---|---|---|
| `panel_size` | 7 | Court justices |
| `supermajority_threshold` | 5 | 5/7 to overturn |
| `min_justice_trust` | 0.70 | Minimum trust for justices |
| `min_regions` | 3 | Geographic diversity |
| `min_organizations` | 3 | Organisational diversity |
| `human_only` | true | Machines excluded |

### Rehabilitation

Genesis believes in second chances — but only where the harm was moderate and the system's integrity is not at risk. The `RehabilitationEngine` (`src/genesis/legal/rehabilitation.py`) provides a structured path back for actors who received moderate penalties.

**Why it exists:** Permanent exclusion for every offence creates a system that is punitive without being restorative. People make mistakes. A platform that offers no path back from a moderate error is not just harsh — it is wasteful, because it permanently loses the future contributions of someone who may have learned from the experience. But rehabilitation must be earned, not assumed, and the bar must be high enough that the system's trust in the outcome is justified.

**How it works:**

1. After a moderate-severity suspension expires, the actor enters `PROBATION` status (not ACTIVE).
2. The actor must complete **5 supervised probation tasks** within **180 days** (`rehab_window_days`).
3. If successful, trust is partially restored — capped at the lower of **half the original trust** or **0.30** (`trust_restoration_fraction = 0.50`, `max_restoration_score = 0.30`).
4. If the 180-day window expires without completing the tasks, rehabilitation fails and the actor remains at their penalty trust level.

**What is excluded:** severe and egregious violations have **no rehabilitation path**. Permanent decommission means permanent decommission. The system distinguishes between people who made a mistake and people who demonstrated a pattern of harm — and it does not pretend that the distinction is difficult.

**Event trail:**

| Event | Trigger |
|---|---|
| `ADJUDICATION_OPENED` | Case filed |
| `ADJUDICATION_RESPONSE_SUBMITTED` | Accused responds |
| `ADJUDICATION_PANEL_FORMED` | Panel assembled |
| `ADJUDICATION_VOTE_CAST` | Individual vote |
| `ADJUDICATION_DECIDED` | Verdict reached |
| `ADJUDICATION_APPEAL_FILED` | Appeal filed |
| `ADJUDICATION_CLOSED` | Case closed |
| `CONSTITUTIONAL_COURT_OPENED` | Case escalated to court |
| `CONSTITUTIONAL_COURT_DECIDED` | Court verdict |
| `REHABILITATION_STARTED` | Probation begins |

---

## Anti-Capture Architecture

"Capture" means a single actor, faction, or interest group gaining disproportionate control over governance. Genesis treats capture as the primary long-term threat and uses structural defences rather than relying on good behaviour.

### Three-chamber model

Constitutional decisions pass through three independent human chambers:

- **Proposal chamber** — evaluates whether a proposal is well-formed and merits consideration.
- **Ratification chamber** — votes on whether to adopt the proposal.
- **Challenge chamber** — provides a final check during a public challenge window.

Each chamber is populated through **constrained-random selection** from the eligible pool. "Constrained-random" means:

1. Members are drawn randomly (using a pre-committed public randomness source for verifiability).
2. But hard constraints are enforced: minimum regional diversity, maximum regional concentration caps, organisation diversity limits, and conflict-of-interest exclusions.
3. No actor can serve on more than one chamber for the same decision.

Chamber sizes scale with the genesis phase (see below).

### Constitutional change requirements

To change the Genesis constitution:

1. A proposal must be sponsored by multiple high-trust participants (not just one person with high trust).
2. The proposal chamber must accept it.
3. The ratification chamber must approve by supermajority (strict majority is not enough).
4. A public challenge window must pass without successful challenge from the challenge chamber.
5. The finalised decision is cryptographically committed to a public blockchain.

No single actor — no matter how high their trust — can unilaterally change the rules.

### Financial isolation

Financial capital has zero role in Genesis governance:

- Money cannot increase trust.
- Money cannot purchase voting power.
- Money cannot buy constitutional authority.
- Sponsorship, donation, or investment create no governance privileges.

This is a deliberate break from most real-world governance systems, where money eventually translates into influence. Genesis treats this as a corruption vector and blocks it structurally.

---

## Compliance and Harmful Work Prevention

Genesis is a white market. It exists to coordinate legitimate, beneficial work — and it enforces this boundary structurally, not aspirationally. The compliance system is not a content moderation layer bolted on after the fact. It is a constitutional constraint that operates at the point of mission creation, before any work reaches a worker, before any escrow is locked, and before any trust is at stake.

### Why this matters

Every platform eventually faces the question of what it will and will not permit. Most answer this question reactively — banning content after it causes harm, suspending accounts after complaints accumulate. Genesis answers it proactively. The prohibited categories are defined upfront, the screening is automated, and the penalties are structural. This means the system's values are not subject to interpretation by a trust-and-safety team or a content moderation contractor — they are encoded in the constitution and enforced by code.

The broader implication is that Genesis provides a model for how a labour platform can have values without having censorship. The prohibited categories are not about taste or opinion — they are about preventing demonstrable harm. A platform that refuses to facilitate weapons development or human trafficking is not being censorious; it is being responsible.

### Prohibited categories

The `ComplianceScreener` (`src/genesis/compliance/screener.py`) defines **17 constitutionally prohibited categories**:

1. Weapons development
2. Weapons manufacturing
3. Weapons trafficking
4. Surveillance tools
5. Exploitation of persons
6. Child exploitation
7. Financial fraud
8. Identity theft
9. Biological weapons
10. Chemical weapons
11. Nuclear weapons
12. Terrorism support
13. Forced labour
14. Money laundering
15. Sanctions evasion
16. Environmental destruction
17. Disinformation campaigns

**Ten categories carry no statute of limitations** for complaints: all weapons categories, exploitation of persons, child exploitation, biological/chemical/nuclear weapons, terrorism support, and forced labour. These are categories where the harm is so severe that the passage of time does not diminish the system's obligation to act. The remaining categories have a 180-day statute of limitations (`statute_of_limitations_days = 180`).

### Three-layer enforcement

Every mission listing passes through three layers of screening:

1. **Automated screening** (`screen_mission()`): the listing title, description, and tags are checked against category-specific keywords. Exact matches produce a `REJECTED` verdict (confidence 1.0). Contextual or partial matches produce a `FLAGGED` verdict (confidence 0.6). Clear listings receive `CLEAR`. This layer handles the vast majority of cases without human involvement.

2. **Human compliance quorum**: flagged listings are reviewed by a blind quorum of qualified legal professionals, compensated from the commission pool and evaluated by the same trust machinery as all other work. This catches cases where automated screening cannot determine intent.

3. **Post-hoc complaints** (`file_compliance_complaint()`): any participant can file a compliance complaint against a live or completed mission. Complaints are tracked by `ComplianceComplaint` records with a `ComplaintStatus` lifecycle (`FILED → UNDER_REVIEW → UPHELD / DISMISSED`).

### Penalty escalation

Confirmed violations trigger a four-tier penalty system implemented in `PenaltyEscalationEngine` (`src/genesis/compliance/penalties.py`).

| Severity | Trust action | Suspension | Permanent | Identity locked |
|---|---|---|---|---|
| **Minor** | Reduced by 0.10 | None | No | No |
| **Moderate** | Nuked to 0.001 | 90 days | No | No |
| **Severe** | Nuked to 0.0 | Permanent | Yes | No |
| **Egregious** | Nuked to 0.0 | Permanent | Yes | Yes (cannot re-register) |

**Violation types** (`ViolationType` enum) map to base severities:

| Violation | Base severity |
|---|---|
| `CONTENT_FLAGGED` | Minor |
| `REPEATED_FLAGGING` | Moderate |
| `PROHIBITED_CATEGORY_CONFIRMED` | Moderate |
| `COMPLAINT_UPHELD` | Moderate |
| `ABUSE_CONFIRMED` | Severe |
| `WEAPONS_OR_EXPLOITATION` | Egregious |

**Pattern escalation**: a second moderate violation within 365 days (`PATTERN_LOOKBACK_DAYS`) automatically escalates to severe — permanent decommission. The system has zero tolerance for patterns of harmful behaviour. This is not a bug or an edge case; it is a deliberate design choice that values platform integrity over individual second chances for repeat offenders.

**Suspension enforcement**: suspended actors (`SUSPENDED` or `PERMANENTLY_DECOMMISSIONED` status) are blocked from all platform participation. The service layer checks suspension status before permitting any meaningful action.

**Actor status values** added for compliance:

| Status | Meaning |
|---|---|
| `SUSPENDED` | Temporarily blocked (moderate penalty) |
| `COMPLIANCE_REVIEW` | Under compliance investigation |
| `PERMANENTLY_DECOMMISSIONED` | Irreversibly removed |

**Event trail:**

| Event | Trigger |
|---|---|
| `COMPLIANCE_SCREENING_COMPLETED` | Automated screening result |
| `COMPLIANCE_COMPLAINT_FILED` | Post-hoc complaint filed |
| `ACTOR_SUSPENDED` | Moderate penalty applied |
| `ACTOR_PERMANENTLY_DECOMMISSIONED` | Severe/egregious penalty |

---

## Genesis Bootstrap Protocol

The full constitutional governance model requires large participant pools (chamber sizes of 41/61/101). Before those numbers are reached, the system operates under a phased bootstrap protocol with reduced thresholds and additional safeguards.

| Phase | Participants | Chamber Sizes | Regions Required | Max Regional Share | Key Rules |
|---|---|---|---|---|---|
| **G0** | 0 – 50 | No chambers | N/A | N/A | Founder stewardship. All decisions provisional. Public audit trail. Hard time limit: 365 days (one extension of 180 days). |
| **G1** | 50 – 500 | 11 / 17 / 25 | ≥ 3 | 0.40 | Provisional chambers activate. Founder loses veto. All G0 decisions must be retroactively ratified within 90 days. |
| **G2** | 500 – 2,000 | 21 / 31 / 51 | ≥ 5 | 0.25 | Intermediate chambers. Stricter geographic constraints. |
| **G3** | 2,000+ | 41 / 61 / 101 | Full | Full | Full constitutional governance. All constraints active. |

Critical rules:

- Phase transitions are **one-way**. The system cannot regress from G2 to G1, or from G1 to G0.
- If G0 time limits expire without reaching 50 participants, **the project fails closed** — it does not limp along indefinitely under founder control.
- The founder's authority is explicitly time-limited and structurally eliminated in G1.

---

## Skill Taxonomy and Proficiency Model

Genesis tracks what each participant can actually do — not what they claim to be capable of.

### Two-level taxonomy

Skills are organised in a two-level hierarchy: **domains** contain **skills**. The default taxonomy defines 6 domains with 3–5 skills each (configuration: `config/skill_taxonomy.json`).

Example:
```
software_engineering/
  ├── code_review
  ├── system_design
  ├── testing
  └── documentation
```

Every skill is identified by a canonical string (`domain/skill_name`) and validated against the taxonomy at every API boundary.

### Actor skill profiles

Each participant has an `ActorSkillProfile` containing:

- **Proficiency scores** (`0.0` – `1.0`) per skill — earned through mission outcomes, not self-reported.
- **Evidence count** — how many verified outcomes back the score.
- **Last demonstrated timestamp** — drives the decay engine.
- **Endorsement count** — peer endorsements received for this skill.
- **Source tag** — `outcome_derived` or `peer_endorsed`, so the origin is always traceable.

### Mission skill requirements

Missions declare a list of `SkillRequirement` entries, each specifying a skill and a minimum proficiency. The matching and allocation engines use these to find qualified workers.

---

## Domain-Specific Trust

A single trust score conflates too many things. Someone excellent at medical research might be mediocre at software development. Genesis resolves this by tracking **per-domain trust** alongside the global score.

### How it works

When a mission is completed, the system identifies which domains the work touched (from the mission's skill requirements). Trust updates flow to those specific domains, not just the global score:

```
domain_trust_update(domain, quality, reliability, volume)
→ domain_score = weighted_combination(quality, reliability, volume)
→ global_score = aggregate(all_domain_scores, global_weights)
```

The global score is recomputed after every domain update using configurable aggregation (default: weighted average with recency bias). Configuration: `config/skill_trust_params.json`.

### Inactivity decay per domain

Each domain trust score decays independently:

- **Human half-life:** 365 days per domain.
- **Machine half-life:** 90 days per domain.
- Domains where you have deep experience (high evidence count) decay more slowly.

The decay formula uses volume dampening:

```
factor = max(floor, 1 - (days / half_life) / (1 + ln(1 + evidence_count)))
```

This means a doctor who hasn't coded in a year loses their software trust but retains their medical trust — which is how the real world works.

### Trust status dashboard

For any actor, the system can compute a full status report: days until half-life per domain, urgency indicators (green / amber / red), projected scores, and recommended actions. This is computed on demand, not stored.

---

## Labour Market

Genesis includes a built-in job board that connects workers to tasks using the skill and trust data described above.

### Listing lifecycle

A market listing moves through a defined state machine:

```
DRAFT → OPEN → ACCEPTING_BIDS → EVALUATING → ALLOCATED → CLOSED
                                                          ↑
                                   CANCELLED ←────── (any non-terminal)
```

Every transition is fail-closed: if the audit event for a transition cannot be recorded, the transition does not happen.

### Bid scoring

When bids are evaluated, each worker receives a composite score:

```
bid_score = 0.50 × relevance  +  0.20 × global_trust  +  0.30 × domain_trust
```

Where:
- **Relevance** = how well the worker's skill profile matches the listing's requirements (computed by the `SkillMatchEngine`).
- **Global trust** = the worker's overall trust score.
- **Domain trust** = trust in the specific domains the listing requires.

The highest-scoring bidder wins. The formula is transparent — workers can see exactly why they were or were not selected.

### Transactional allocation

Allocation is a single atomic operation. Either everything succeeds — listing state, bid states, mission creation, and audit event — or everything rolls back cleanly. There is no partial allocation state.

The `WORKER_ALLOCATED` audit event is the single commit point. All mutations before it are staged without side effects. If the audit write fails, nothing has changed. If it succeeds, all in-memory state is committed.

### Persistence safety

Every mutating operation in the service layer is protected against storage failures:

- **Post-audit paths** (after an audit event has been durably committed): if the state store write fails, the operation succeeds with a degradation warning. In-memory state stays aligned with the audit trail. The `persistence_degraded` flag is set for operator visibility.
- **Non-audit paths** (no audit event committed yet): if the state store write fails, all in-memory mutations are rolled back and the operation returns a typed error.

No mutating API call can raise an uncaught storage exception.

---

## Skill Lifecycle

Skills are living things in Genesis. They grow, they can be boosted by peers, and they fade if unused.

### Outcome-derived proficiency

When a mission completes, the system automatically updates the worker's skill profile based on the outcome:

- **Approved missions** increase proficiency in all required skills.
- **Rejected missions** decrease proficiency.
- The magnitude scales with the mission's complexity and the worker's current proficiency level (it's harder to improve at high levels).

This is the **primary path** for skill creation. A skill can only appear on a profile through a verified mission outcome.

### Peer endorsement

Participants can endorse each other's skills, but with strict guardrails:

- **Self-endorsement is structurally blocked.**
- **You can only endorse skills you possess yourself** (at sufficient proficiency).
- **You can only endorse skills that already exist** on the target's profile. Endorsement boosts — it never creates.
- **Diminishing returns** prevent endorsement gaming:

```
boost = base_boost × endorser_trust / (1 + existing_endorsements)
```

The first endorsement has the most impact. Each subsequent one has less. After a configurable cap (default: 10 per skill), further endorsements have negligible effect.

### Decay

Skills fade without practice. The decay engine runs periodically and applies time-based decay to all proficiency scores:

```
factor = max(floor, 1 - (days / half_life) / (1 + ln(1 + evidence_count)))
```

Key properties:
- **Humans** have a 365-day half-life. Step away for a year, and your skills noticeably fade. But deep experience (high evidence count) fades more slowly.
- **Machines** have a 90-day half-life. An AI model that hasn't been validated in three months loses proficiency quickly.
- **Materiality threshold** — trivially small floating-point decay (less than 0.1%) is ignored. Only meaningful decay is recorded.
- **Pruning** — skills that decay below a configurable floor are removed from the profile entirely.

Configuration: `config/skill_lifecycle_params.json`.

---

## Compensation Model

Trust without compensation is volunteerism. Genesis operates a self-financing compensation model that is structurally transparent and inversely tied to platform health.

### Settlement

Genesis settles exclusively in cryptocurrency: `ACCEPTED_CURRENCIES = [BTC, ETH, USDC, USDT]`. No Genesis-branded token exists or can be created — a native token would create a tradeable asset that contradicts the core rule. Stablecoins (USDC/USDT) are the recommended default to avoid exchange rate risk.

### Escrow and staking

Before any mission listing goes live, the work poster must stake the full reward into escrow. This is non-negotiable — it eliminates "work done, never paid" structurally. The listing is not published until escrow is confirmed. On completion, escrow is released, commission deducted, and the remainder paid to the worker. On cancellation, funds return to the poster minus partial-completion obligations. During disputes, escrow remains locked until quorum resolution.

### Dynamic commission (real-time)

The commission rate is computed **per-transaction in real-time**, not set by fiat or adjusted periodically:

```
cost_ratio = rolling_operational_costs / rolling_completed_mission_value
commission_rate = clamp(cost_ratio × COMMISSION_SAFETY_MARGIN, COMMISSION_FLOOR, COMMISSION_CEILING)
commission = max(commission_rate × mission_reward, COMMISSION_MIN_FEE)
```

The rate is pegged to a **rolling window** of recent operational data (last 90 days or at least 50 completed missions, whichever captures more data). During bootstrap (< 50 completed missions), a minimum rate of 5% prevents artificially low early rates.

Constitutional constants (all require constitutional amendment to change):
- `COMMISSION_FLOOR = 0.02` (2%) — minimum infrastructure coverage.
- `COMMISSION_CEILING = 0.10` (10%) — prevents extraction.
- `COMMISSION_SAFETY_MARGIN = 1.3` — constitutional constant, not governable by ballot.
- `COMMISSION_RESERVE_TARGET_MONTHS = 6` — constitutional constant. Reserve fills/drains automatically.
- `COMMISSION_MIN_FEE = 5 USDC equivalent` — constitutional constant. Covers gas on small missions.
- `COMMISSION_WINDOW_DAYS = 90` — rolling window recency horizon.
- `COMMISSION_WINDOW_MIN_MISSIONS = 50` — minimum sample for statistical reliability.
- `COMMISSION_BOOTSTRAP_MIN_RATE = 0.05` — bootstrap floor, auto-expires.
- `COMMISSION_RESERVE_MAINTENANCE_RATE = 0.005` — reserve maintenance when target met.

No human votes on the rate. The formula is deterministic, the inputs are auditable, and the output is independently verifiable. Every commission computation produces a mandatory published cost breakdown recorded in the audit trail. The rate trends toward the floor as volume grows. In early operation it sits near the ceiling.

Reserve fund mechanism: when below target, gap contribution is added to operational costs (rate rises automatically). When at target, only maintenance contribution (rate falls). No vote, no review — the formula observes the gap and responds.

Commission funds: infrastructure, blockchain anchoring, legal compliance quorum, leave/dispute adjudicator compensation, and reserve fund.

### Legal compliance

All mission listings pass through a legal compliance layer:
1. **Automated screening** (first pass) — category checks, sanctions lists, jurisdiction cross-reference. Handles the vast majority of listings.
2. **Legal compliance quorum** (edge cases) — minimum 3 adjudicators with earned domain trust in legal/compliance. Blind review, same diversity requirements as all quorums. Compensated from commission pool.

### Crypto volatility protection

Volatile crypto stakes (BTC/ETH) are displayed as stablecoin equivalent at time of staking. If value drops >20% during mission execution, poster is prompted to top up. If >50% crash, emergency protocol pauses mission with 72-hour top-up window. Stablecoin stakes are exempt — no volatility risk.

### Payment dispute resolution

Either party can raise a dispute within `ESCROW_HOLD_PERIOD = 48 hours` after completion. Escrow stays locked. Quorum adjudication determines outcome: full payment, full refund, partial payment, or escalation. Vexatious disputes may reduce the disputing party's trust.

### Payment parameters

All commission parameters are constitutional constants requiring 3-chamber supermajority amendment. Non-commission compensation parameters (accepted currencies, volatility threshold, escrow hold period, minimum reward, KYC threshold) are governed by ballot.

---

## Genesis Common Fund

One percent of every completed mission's value is automatically directed to a shared commons fund. This is not a tax, a fee, or a discretionary allocation. It is a constitutional commitment — a structural deduction that occurs before any participant receives payment, without any vote or approval process.

### Why this matters

Most platforms extract value for shareholders. Some pledge charitable donations. None structurally embed a commons contribution into the economic machinery itself. The Genesis Common Fund (GCF) is different in kind: it is not a promise, it is an invariant. The 1% deduction is as much a part of the commission calculation as the commission rate itself. It cannot be turned off, reduced, or redirected without clearing the highest amendment threshold in the constitution.

The societal implication is that Genesis creates a model for automatic, non-discretionary collective contribution — a commons fund that grows in proportion to the value the platform creates, without requiring anyone to choose generosity. The scope is deliberately broad: "all meaningful human activity that doesn't increase net human suffering." This encompasses education, healthcare, infrastructure, arts, community development, and scientific research.

### How it works

The `GCFTracker` (`src/genesis/compensation/gcf.py`) manages the fund state:

- **Activation**: the fund activates at First Light (financial sustainability trigger). Before First Light, no contributions are collected. Activation is a one-time event — once activated, it cannot be deactivated.
- **Contribution**: on every successful mission completion, 1% of the `mission_reward` (gross value) is deducted from the worker's payout and recorded as a `GCFContribution`. The contribution rate is loaded from `config/commission_policy.json` (`gcf_contribution_rate = "0.01"`).
- **Accounting invariant**: `commission + creator_allocation + worker_payout + gcf_contribution == mission_reward`. This invariant is tested automatically.
- **Non-extractability**: the fund tracks total balance, total contributed, and contribution count — but it has **no per-actor balance method**. No individual can determine the precise value of their own contributions, because the fund is trust-proportional and architecturally opaque at the individual level. The distributed ledger state is the fund. There is no bank account, no custodian, no external financial intermediary.

**GCFState fields:**

| Field | Type | Purpose |
|---|---|---|
| `balance` | Decimal | Current fund balance |
| `total_contributed` | Decimal | Lifetime total |
| `contribution_count` | int | Number of contributions |
| `activated` | bool | Whether First Light has been reached |
| `activated_utc` | datetime | When activation occurred |

### Entrenched provision

The GCF contribution rate is one of four **entrenched provisions** — constitutional parameters protected by the highest amendment threshold in the system:

1. `GCF_CONTRIBUTION_RATE` — the 1% commons contribution.
2. `TRUST_FLOOR_H_POSITIVE` — human trust can never decay to zero.
3. `NO_BUY_TRUST` — financial capital cannot purchase trust.
4. `MACHINE_VOTING_EXCLUSION` — machines permanently excluded from constitutional voting.

Changing any entrenched provision requires: **80% supermajority** across three independent chambers, **50% participation**, a **90-day cooling-off period**, and a **confirmation vote**. This is deliberately harder to change than any other parameter in the system.

### Founder dormancy

After the 50-year dormancy clause, the founder's creator allocation (the 5% both-sides mechanism) redirects to STEM and medical charitable recipients selected by supermajority. This ensures that the founder's economic interest in the platform has a finite lifetime, and that after that lifetime, the value flows to public benefit rather than to an estate or successor.

**Event trail:**

| Event | Trigger |
|---|---|
| `GCF_ACTIVATED` | First Light reached |
| `GCF_CONTRIBUTION_RECORDED` | Mission payment processed |

---

## Workflow Orchestration

The systems described above — trust, skills, labour market, escrow, compliance, justice — are powerful individually but must be coordinated to produce a coherent workflow. The `WorkflowOrchestrator` (`src/genesis/workflow/orchestrator.py`) is the thin stateful coordinator that bridges these subsystems into a single, auditable lifecycle for every piece of work on the platform.

### Why this matters

Without a coordinator, each subsystem operates independently. Escrow might lock funds for a listing that fails compliance screening. A worker might be allocated to a mission that has no escrow backing. A completed mission might trigger payment without compliance clearance. The workflow orchestrator exists to prevent these inconsistencies — to ensure that every mission follows the correct sequence of gates, and that no step can be skipped.

This is also the layer that makes Genesis's "escrow-first" guarantee meaningful. The claim that "no listing goes live without staked funds" is not a policy — it is enforced by the orchestrator's state machine. The system literally cannot advance a listing to the `LISTING_LIVE` state without a confirmed escrow record.

### Workflow lifecycle

Every mission follows a defined state machine (`WorkflowStatus` enum):

```
LISTING_CREATED → ESCROW_FUNDED → LISTING_LIVE → BIDS_OPEN → WORKER_ALLOCATED
    → WORK_IN_PROGRESS → WORK_SUBMITTED → IN_REVIEW → APPROVED
    → PAYMENT_PROCESSING → COMPLETED

    (from most states) → CANCELLED → REFUNDED
    (from WORK_IN_PROGRESS onward) → DISPUTED → COMPLETED / REFUNDED
```

**Key transitions:**

| Method | From → To | What happens |
|---|---|---|
| `create_funded_listing()` | — → LISTING_CREATED | Creates listing + escrow + runs compliance screening |
| `fund_and_publish()` | ESCROW_FUNDED → LISTING_LIVE | Publishes listing (only after escrow confirmed) |
| `allocate_worker()` | BIDS_OPEN → WORK_IN_PROGRESS | Assigns worker, creates mission, sets deadline |
| `submit_work()` | WORK_IN_PROGRESS → WORK_SUBMITTED | Worker submits deliverables with evidence hashes |
| `complete_and_pay()` | APPROVED → COMPLETED | Triggers escrow release, commission, GCF, creator allocation |
| `cancel()` | Most states → CANCELLED | Returns full escrow including employer creator fee |
| `file_dispute()` | Post-allocation → DISPUTED | Opens Tier 2 adjudication case |
| `resolve_dispute()` | DISPUTED → COMPLETED/REFUNDED | Adjudication verdict determines outcome |

**Escrow-first guarantee**: the `create_funded_listing()` method creates the escrow record and locks funds (`mission_reward + employer_creator_fee`) before creating the workflow. A preflight check prevents duplicate escrow records for the same listing. If escrow creation fails, the listing is never created.

**Compliance gate**: all listings are screened by the `ComplianceScreener` before publication. A listing that receives a `REJECTED` verdict cannot advance to `LISTING_LIVE`.

**Dispute bridge**: payment disputes filed through the workflow are automatically routed to the Tier 2 adjudication system. The adjudication verdict determines whether escrow is released to the worker or refunded to the employer.

**Persistence**: the orchestrator supports durable state through `WorkflowOrchestrator.from_records()` and `StateStore.save_workflows()` / `load_workflows()`. All 8 workflow methods call `_safe_persist_post_audit()` after state changes.

**Configuration** (from `config/runtime_policy.json`):

| Parameter | Value | Purpose |
|---|---|---|
| `default_deadline_days` | 30 | Default mission deadline |
| `require_compliance_screening` | true | Compliance gate active |
| `require_escrow_before_publish` | true | Escrow-first enforcement |
| `auto_start_bids_on_publish` | true | Bids open when listing goes live |

**Event trail:**

| Event | Trigger |
|---|---|
| `WORKFLOW_CREATED` | New workflow initialised |
| `ESCROW_WORKFLOW_FUNDED` | Escrow confirmed for listing |
| `WORK_SUBMITTED` | Worker submits deliverables |
| `WORKFLOW_CANCELLED` | Mission cancelled |
| `PAYMENT_DISPUTE_FILED` | Dispute opened |
| `DISPUTE_RESOLVED` | Adjudication verdict applied |

---

## Cryptographic Implementation Profile

This section describes the specific cryptographic mechanisms Genesis uses. Version: v0.2.

### Settlement chain

Constitutional commitments are published to Ethereum Mainnet (`chain_id = 1`) for production. Development and testing use Ethereum Sepolia (`chain_id = 11155111`).

### Commitment tiers (progressive on-chain publication)

On-chain publication is expensive at scale. Genesis uses a tiered approach:

| Tier | Participants | Strategy | L1 Anchor Frequency |
|---|---|---|---|
| **C0** | ≤ 500 | L2 rollup primary | Every 24 hours |
| **C1** | 500 – 5,000 | L2 rollup primary | Every 6 hours |
| **C2** | 5,000+ | Full L1 commitments | Hourly |

**Exception:** Constitutional lifecycle events — parameter changes, decommissions, chamber votes — always anchor to L1 immediately, regardless of commitment tier.

Tier progression is one-way (C0 → C1 → C2). Regression is prohibited.

### Commitment payload

Each commitment is a canonical JSON object (RFC 8785) containing:

| Field | Purpose |
|---|---|
| `commitment_version` | Schema version for forward compatibility. |
| `epoch_id` | The time period this commitment covers. |
| `previous_commitment_hash` | Links to the prior commitment, forming a verifiable chain. |
| `mission_event_root` | Merkle root of all mission events in this epoch. |
| `trust_delta_root` | Merkle root of all trust changes in this epoch. |
| `governance_ballot_root` | Merkle root of all governance votes in this epoch. |
| `review_decision_root` | Merkle root of all review decisions in this epoch. |
| `public_beacon_round` | External randomness source identifier (for constrained-random selection). |
| `chamber_nonce` | Anti-replay value for chamber operations. |
| `timestamp_utc` | When the commitment was generated. |

### Hashing and Merkle trees

- **Hash function:** SHA-256 throughout.
- **Merkle tree structure:** Binary Merkle tree with deterministic leaf ordering by `(event_type, event_id, event_timestamp, actor_id)`. This means anyone with the raw records can independently reconstruct the tree and verify the root matches the published commitment.
- **Leaf hash:** `SHA-256(canonical_json(event_record))` — the event is serialised to canonical JSON before hashing, ensuring deterministic output regardless of field ordering.

### Signature suite

| Use Case | Algorithm | Notes |
|---|---|---|
| Identity and event signatures | Ed25519 | Fast, compact, well-audited. |
| Constitutional decision certificates | BLS12-381 threshold signature | Allows a committee to produce a single valid signature. Default: `n = 15` committee members, `t = 10` threshold (two-thirds). |

### Randomness for constrained-random selection

The randomness used for chamber selection must be publicly verifiable and not manipulable by any participant:

```
seed = SHA-256(public_beacon_value || previous_commitment_hash || chamber_nonce)
```

- `public_beacon_value` — from an external, pre-committed randomness source (e.g., drand).
- `previous_commitment_hash` — ties the randomness to the chain state.
- `chamber_nonce` — prevents replay across different selection events.

Selection uses deterministic sampling without replacement from the eligible pool, constrained by the diversity requirements described above.

### Verification

Any third party can:

1. Recompute all published Merkle roots from released event records and verify they match the on-chain commitments.
2. Verify decision certificate signatures against the known committee public keys.
3. Verify chain commitment inclusion proofs.

No Genesis infrastructure is required for verification. The proofs are self-contained.

### Privacy boundary

- Sensitive raw evidence (e.g., personal data, proprietary content) remains off-chain in encrypted storage.
- On-chain commitments contain only hashes, Merkle roots, certificates, and inclusion references — never raw content.

### Key management

- Signing keys are HSM-backed (hardware security modules).
- Key rotation interval: 90 days.
- Emergency compromise path: immediate key revocation, replacement certificate issuance, and recommitment on-chain.

---

## Blockchain Anchoring

### Historical foundations

The idea of using cryptography to prove a document existed at a particular time predates blockchain technology by nearly two decades.

In 1991, Stuart Haber and W. Scott Stornetta published *"How to Time-Stamp a Digital Document"*, proposing a system in which documents are hashed and the hashes linked into a chain — each entry referencing the previous one — creating a tamper-evident chronological record. Their follow-up work introduced Merkle trees to batch multiple timestamps efficiently. These two papers are among the most cited references in Satoshi Nakamoto's 2008 Bitcoin whitepaper, which extended the concept by replacing a trusted timestamping authority with a decentralised proof-of-work consensus mechanism.

From 1995 onward, a company called Surety put these ideas into practice, publishing hash chains in the *New York Times* classified section — making it the longest-running cryptographic timestamp chain in history.

Once Bitcoin launched in 2009, the blockchain itself became a natural public timestamping medium. Bitcoin's `OP_RETURN` opcode (available since Bitcoin Core 0.9.0, March 2014) formalised the practice of embedding arbitrary data — including document hashes — into transactions. Services emerged to make this accessible:

- **OpenTimestamps** — an open protocol that uses Bitcoin as a timestamp notary, batching many hashes into a single daily transaction via Merkle aggregation.
- **Stampery** — published a formal Blockchain Timestamping Architecture (BTA) in 2014.
- **OriginStamp** — a multi-chain timestamping service anchoring to Bitcoin, Ethereum, and others simultaneously.

The existing field uses various terms — "blockchain timestamping", "data anchoring", "cryptographic stamping" — but the underlying technique is the same: embed a hash in a public blockchain transaction, and the blockchain serves as a permanent, independent witness to the document's existence at that point in time.

### What blockchain anchoring is

Blockchain anchoring is the practice of embedding a cryptographic hash of a document into a standard blockchain transaction, creating permanent, public, tamper-evident proof that the document existed in a specific form at a specific time.

The process is deliberately simple:

1. Compute the SHA-256 hash of the document.
2. Send a standard Ethereum transaction where the `data` field contains that hash.
3. The transaction is mined into a block with a timestamp.
4. The hash is now permanently recorded on a public, immutable ledger.

No code executes on-chain. No smart contract is deployed. The blockchain is a passive witness — a notary, not an actor.

### How it differs from smart contracts

This distinction matters because the two are frequently confused:

| | Blockchain Anchoring | Smart Contracts |
|---|---|---|
| **What's on-chain** | A hash (32 bytes of data) | Executable code and state |
| **What executes** | Nothing — the blockchain is a passive witness | The contract code runs on every node |
| **Cost** | Minimal (one standard transaction) | High (proportional to computation and storage) |
| **Complexity** | Trivial — hash a document, send a transaction | Significant — requires Solidity/Vyper, auditing, gas optimisation |
| **Purpose** | Prove a document existed at a point in time | Execute logic on-chain (token transfers, DeFi, DAOs) |

Genesis uses anchoring, not smart contracts. The blockchain is a witness, not an actor.

### How Genesis uses anchoring

Genesis adopts and formalises blockchain anchoring as a core governance primitive. The first document anchored — the Genesis constitution (`TRUST_CONSTITUTION.md`) — serves as both a governance act and a concrete demonstration of the technique.

**What was anchored:**

| Field | Value |
|---|---|
| Document | `TRUST_CONSTITUTION.md` |
| SHA-256 | `33f2b00386aef7e166ce0e23f082a31ae484294d9ff087ddb45c702ddd324a06` |
| Chain | Ethereum Sepolia (Chain ID 11155111) |
| Block | 10255231 |
| Sender | [`0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE`](https://sepolia.etherscan.io/address/0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE) |
| Transaction | [`031617e3...`](https://sepolia.etherscan.io/tx/031617e394e0aee1875102fb5ba39ad5ad18ea775e1eeb44fd452ecd9d8a3bdb) |
| Anchored | 2026-02-13T23:47:25Z |

**What this proves:**

1. The constitution existed in its exact byte-for-byte form at the recorded time.
2. No party — including the project owner — can alter the anchored version without the mismatch being publicly detectable.
3. The proof is permanent, does not expire, and does not depend on any Genesis infrastructure.

The constitution is the foundational document of Genesis, first anchored on the blockchain before any user existed (see [`docs/GENESIS_EVENTS.md`](GENESIS_EVENTS.md) for the full anchoring history).

### Verification process

Any third party can verify an anchoring event independently. No trust in Genesis is required — only a hash function and a block explorer.

1. Compute the SHA-256 hash of the document locally: `shasum -a 256 TRUST_CONSTITUTION.md`
2. Look up the transaction on Etherscan (or any Ethereum block explorer).
3. Inspect the transaction's Input Data field — it contains the hash.
4. If the locally computed hash matches the on-chain hash, the document is verified as unchanged since the anchor time.
5. The block timestamp proves when the anchor was recorded.

The verification depends only on SHA-256 (a public standard) and the Ethereum blockchain (a public ledger). No API calls, no Genesis software, no trust in any party.

### Why anchoring matters for governance

Traditional institutions prove the integrity of their founding documents through physical custody, legal witnesses, and institutional reputation. All of these depend on trusting the institution itself — the very thing that may need to be verified.

Blockchain anchoring breaks this circularity. The proof is mathematical, the witness is a public network with no relationship to Genesis, and verification can be performed by anyone with a computer. This means Genesis can credibly commit to its own rules in a way that does not require anyone to take its word for it.

For a project whose foundational principle is that trust must be earned rather than assumed, this is not just a technical feature — it is the first act of practising what it preaches.

---

## Identity Verification

Genesis needs to know that each participant is real — present, alive, and not a duplicate. But it does not need to know who they are. The verification system is designed as an anti-Sybil defence: it proves personhood without collecting personal information. This distinction matters deeply. In a world where identity systems routinely become surveillance infrastructure, Genesis demonstrates that you can verify a person's existence without cataloguing their life.

Identity verification tells you that someone is a distinct participant. It does not tell you whether they should be trusted. Trust comes from behaviour over time. Passing an identity check cannot mint trust, grant voting power, or create constitutional authority — it simply opens the door to earning those things through verified contribution.

### Why this matters

Most identity verification systems today — KYC, facial recognition, government ID databases — trade privacy for certainty. They work by accumulating personal data, which creates a target for theft, a tool for surveillance, and a barrier for people who lack conventional documentation. Genesis rejects this trade-off. Its verification system asks one question: "Is this a real, present human being?" It deliberately does not ask "Who are they?" This is a design philosophy, not a technical limitation.

The societal implication is significant: Genesis creates a model for identity verification that could work for the stateless, the undocumented, and the privacy-conscious — anyone excluded from systems that demand government-issued credentials. If this model proves viable at scale, it has implications far beyond Genesis itself.

### The liveness challenge

The participant is presented with a sequence of randomly selected words and asked to read them aloud on video. The words are drawn from the BIP39 wordlist — the same 2,048-word cryptographic standard that underpins Bitcoin wallet recovery phrases. This connection is deliberate: Genesis roots its proof-of-personhood in the same cryptographic heritage that made trustless digital currency possible.

Technical implementation:

- **ChallengeGenerator** (`src/genesis/identity/challenge.py`) selects words using a cryptographic Fisher-Yates shuffle with Python's `secrets` module. Each challenge produces a `LivenessChallenge` — a frozen (immutable) dataclass containing the word sequence, a unique `challenge_id`, and a single-use `nonce` (anti-replay token generated via `secrets.token_hex(16)`).
- **Stage 1** presents 6 words. If the participant fails after 3 attempts, the challenge escalates to **Stage 2** with 12 words and 3 more attempts. This escalation raises the bar for automated attacks without penalising honest participants who stumble on their first try.
- Each challenge expires after **120 seconds**. The nonce is consumed on first verification attempt and cannot be reused — preventing replay attacks where a recording of a previous session is submitted.
- **VoiceVerifier** (`src/genesis/identity/voice_verifier.py`) performs positional word matching: did the participant say the right words in the right order? The `word_match_threshold` is 0.85 (5 of 6 words correct). A `naturalness_threshold` of 0.70 is defined but currently returns a stub value — actual speech-to-text and spectral analysis are infrastructure items for production deployment.
- **SessionManager** (`src/genesis/identity/session.py`) tracks the full lifecycle: `CHALLENGE_ISSUED → RESPONSE_SUBMITTED → PASSED / FAILED / EXPIRED`. On pass, it automatically triggers identity verification completion.

Configuration parameters (from `config/runtime_policy.json`):

| Parameter | Value | Purpose |
|---|---|---|
| `stage_1_word_count` | 6 | Words in initial challenge |
| `stage_2_word_count` | 12 | Words in escalated challenge |
| `max_attempts_per_stage` | 3 | Retries before escalation/failure |
| `session_timeout_seconds` | 120 | Challenge expiry |
| `word_match_threshold` | 0.85 | Minimum word accuracy |
| `naturalness_threshold` | 0.70 | Minimum naturalness score |

### Identity verification lifecycle

Every actor's identity follows a tracked lifecycle managed through the `IdentityVerificationStatus` enum (`src/genesis/review/roster.py`):

```
UNVERIFIED → PENDING → VERIFIED → LAPSED (after 365 days)
                                 ↘ FLAGGED (anti-abuse)
```

- **UNVERIFIED**: initial state for all new registrations.
- **PENDING**: verification has been requested and is in progress (liveness challenge active or quorum panel forming).
- **VERIFIED**: passed liveness or quorum verification. Sets `identity_verified_utc` and `identity_expires_utc` (365 days from verification). Records `identity_method` ("voice_liveness" or "quorum_verification").
- **LAPSED**: verification expired. Must re-verify for constitutional actions.
- **FLAGGED**: manually flagged for anti-abuse investigation.

Constitutional actions — voting, proposing amendments, high-risk adjudication — require VERIFIED status with a non-expired verification. This is a structural gate enforced by the service layer (`check_identity_for_high_stakes`), not a policy recommendation.

### Disability accommodation: the quorum verification path

Not everyone can read words aloud on video. Speech impediments, deafness, motor disabilities, cognitive conditions, and other circumstances can make the standard liveness challenge impossible. Genesis does not treat this as an edge case to be handled later — it treats it as a constitutional design requirement that must be solved before the system can claim to serve all humans.

This decision reflects a deeper principle: a system that claims to be intelligence-agnostic and universally accessible cannot exclude people based on physical ability. The disability accommodation protocol exists because Genesis takes its own stated values seriously.

When a participant cannot complete the voice challenge, a quorum of verified humans conducts a live verification session. The implementation is in `QuorumVerifier` (`src/genesis/identity/quorum_verifier.py`).

**Panel formation:**

- Panel size: 3 to 5 members (configurable via `min_quorum_size` / `max_quorum_size`).
- All panelists must have trust ≥ 0.70, be ACTIVE, HUMAN, with a minted trust profile.
- Same geographic region as the applicant (`geographic_region_required = true`).
- **Diversity enforcement**: at least 2 different organisations and at least 1 distinct region must be represented. The `_select_diverse_panel()` method uses greedy diversity-first selection from the eligible pool.
- **Blind adjudication**: the applicant is identified only by a pseudonym (`participant-{UUID[:8]}`). Panelists never see the real `actor_id`.

**Pre-session preparation (Phase D-5b):**

Before the live session begins, the participant receives a versioned briefing (`PRE_SESSION_BRIEFING_V1`) that explains the process, their rights, and what to expect. A 6-word BIP39 challenge phrase is generated as a proof-of-interaction token — evidence that the session actually occurred.

The participant has **unlimited preparation time**. The session timer does not start until they explicitly signal readiness via `signal_participant_ready()`. This is a deliberate accommodation: someone with a cognitive disability, anxiety, or unfamiliarity with video calls should never be penalised for needing extra time to prepare.

**The live session:**

A versioned scripted introduction (`SCRIPTED_INTRO_V1`) is read by the verifier to ensure consistency across all sessions. The participant completes the same word challenge that the voice system uses — but they may do so by speaking, writing, or through a caregiver. The method of interaction is adapted to the participant's circumstances.

- **Session maximum**: 4 minutes (from ready signal, not from session creation). Configurable via `session_max_seconds = 240`.
- **Recording**: every session is recorded. Recordings are retained for **72 hours** (`recording_retention_hours = 72`), then automatically deleted unless a complaint has been filed.
- **Vote**: each panelist submits a vote (approve/reject) with a mandatory written attestation (`require_vote_attestation = true`). The result must be **unanimous** — any single rejection means the verification fails.

**Verifier safeguards:**

The system prevents panelist fatigue, burnout, and abuse of the verification role:

| Control | Value | Purpose |
|---|---|---|
| `verifier_cooldown_hours` | 168 (7 days) | Minimum gap between panel assignments |
| `max_panels_per_verifier_per_month` | 10 | Monthly workload cap |
| `max_concurrent_panels_per_verifier` | 3 | Prevents overcommitment |
| `appeal_window_hours` | 72 | Window for rejected applicants to appeal |

**Recusal**: any panelist can withdraw for any reason via `declare_recusal()`, provided the remaining panel still meets the minimum quorum size.

**Abuse handling:**

If a participant believes a verifier acted improperly during a session, they can file an abuse complaint (`file_abuse_complaint()`). The complaint preserves the session recording past the normal 72-hour auto-delete window.

A review panel of 3 high-trust (≥ 0.70) reviewers examines the complaint. If a majority confirms abuse:

- The offending verifier's trust is reduced to **0.001** (1/1000th of its maximum value). This is not a slap on the wrist — it effectively removes the verifier from all meaningful participation.
- The pre-nuke trust score is stored for potential restoration.

The nuked verifier may appeal once (`appeal_trust_nuke()`). The appeal goes to a 5-member panel requiring a **4/5 supermajority** to overturn. The appeal panel must have **no overlap** with the original abuse review panel. This is a one-shot mechanism — there is no second appeal.

If the appeal succeeds, the verifier's trust is restored to its pre-nuke value. The complainant's trust is never affected regardless of outcome.

**Appeal for rejected applicants:**

A rejected applicant can appeal within 72 hours via `request_appeal()`. The appeal creates an entirely new verification request with a completely different panel — no overlap with the original panelists. The same diversity and trust requirements apply.

### Event trail

Every identity verification action produces a durable audit event:

| Event | Trigger |
|---|---|
| `IDENTITY_VERIFICATION_REQUESTED` | Actor requests verification |
| `IDENTITY_VERIFIED` | Liveness or quorum verification passed |
| `IDENTITY_LAPSED` | 365-day expiry reached |
| `IDENTITY_FLAGGED` | Manual anti-abuse flag |
| `QUORUM_PANEL_FORMED` | Panel assembled for quorum verification |
| `QUORUM_VOTE_CAST` | Individual panelist vote recorded |
| `QUORUM_RECUSAL_DECLARED` | Panelist withdraws |
| `QUORUM_VERIFICATION_COMPLETED` | Final outcome (approved/rejected) |
| `QUORUM_APPEAL_FILED` | Rejected applicant appeals |
| `QUORUM_SESSION_EVIDENCE` | Session recording hash attached |
| `QUORUM_ABUSE_COMPLAINT` | Abuse complaint filed |
| `QUORUM_ABUSE_CONFIRMED` | Abuse review upheld |
| `QUORUM_NUKE_APPEAL_FILED` | Nuked verifier appeals |
| `QUORUM_NUKE_APPEAL_RESOLVED` | Nuke appeal outcome |

---

## Success Metrics

Genesis defines success through measurable outcomes, not narrative claims.

| Metric | What It Measures | Why It Matters |
|---|---|---|
| First-pass review acceptance rate | How often work passes review on the first attempt | Indicates overall production quality |
| Post-approval defect/rework rate | How often approved work turns out to be wrong | Catches failures in the review process |
| Time-to-completion by risk tier | How long missions take at each risk level | Tracks operational efficiency vs. governance overhead |
| Reviewer disagreement rate | How often reviewers reach different conclusions | High disagreement may signal ambiguous criteria or poor task design |
| Resolution quality | How well disputes are resolved (measured by subsequent outcomes) | Tests whether the adjudication process works |
| Audit completeness | Percentage of actions with full evidence trails | Measures whether the logging system is actually working |
| Abuse detection vs. escape rate | How many gaming attempts are caught vs. missed | Tests the effectiveness of anti-capture controls |
| Sustained human confidence | Whether human participants continue to trust the system over time | The ultimate measure — if humans lose confidence, nothing else matters |

If these metrics improve over time, the system is working. If they don't, the governance framework needs revision — and the constitution provides the mechanism to do that.

---

## Governance Engine Architecture

The runtime software implements the governance framework described above. The codebase is organised as follows:

```
src/genesis/
├── models/          Data models (mission, trust, commitment, governance, market, skill, leave)
├── policy/          Policy resolver (loads constitutional, runtime, and market config)
├── engine/          Mission state machine, evidence validation, reviewer routing
├── trust/           Trust scoring, domain trust, decay, quality gates, fast-elevation control
├── quality/         Quality assessment engine (derives worker and reviewer quality from outcomes)
├── skills/          Skill taxonomy, decay, endorsement, outcome updates, matching
├── market/          Labour market: listing state machine, bid scoring, allocation engine
├── governance/      Genesis phase controller (G0→G1→G2→G3 progression)
├── crypto/          Merkle trees, commitment builder, blockchain anchoring, epoch service
├── review/          Actor roster, skill-aware constrained-random reviewer selector
├── persistence/     Event log (append-only JSONL) and state store (JSON)
├── identity/        BIP39 challenge, voice verifier, session manager, quorum verifier
├── compliance/      Compliance screener (17 categories), penalty escalation engine
├── legal/           Adjudication panels, Constitutional Court, rights enforcer, rehabilitation
├── compensation/    Commission calculator, escrow manager, GCF tracker
├── workflow/        Workflow orchestrator (escrow-first coordination layer)
├── leave/           Protected leave engine, adjudication, trust freeze
├── countdown/       First Light estimator
├── service.py       Unified service facade (orchestrates all subsystems)
└── cli.py           Command-line interface
```

Key design principles:

1. **Fail-closed**: if the system encounters an ambiguous state, it blocks rather than proceeding. A mission that cannot prove compliance stays open. A storage failure after an audit commit does not crash — it degrades gracefully.
2. **Parameter-driven**: all constitutional values are loaded from `config/constitutional_params.json`. Market and skill parameters from their respective config files. No magic numbers in code.
3. **Auditable transitions**: every state change — in missions, listings, bids, trust, and skills — is an explicit, logged event with a tamper-evident hash.
4. **Self-review impossible**: the reviewer router structurally prevents any actor from reviewing their own work.
5. **Engine purity**: computation engines (trust, quality, matching, decay, endorsement, allocation) are pure functions with no side effects. The service layer handles all persistence and event recording.
6. **Transactional safety**: every mutating service operation either fully succeeds or fully rolls back. Post-audit operations degrade rather than roll back to prevent audit/state mismatch.

All constitutional invariants are tested automatically. The test suite (1244 tests) covers every critical rule described in this document — including identity verification, compliance screening, three-tier justice, the genesis common fund, workflow orchestration, the labour market, skill lifecycle, domain trust, and persistence safety.

```bash
python3 -m pytest tests/ -q            # Run full test suite
python3 tools/check_invariants.py      # Constitutional + runtime invariant checks
python3 tools/verify_examples.py       # Worked-example policy validation
```

### Deployment

The project includes containerised deployment and continuous integration:

- **Dockerfile** — Python 3.13-slim based image that installs the project, runs the full test suite during build as verification, and defaults to running invariant checks.
- **GitHub Actions CI** — matrix testing on Python 3.11, 3.12, and 3.13. Each run executes: invariant checks (`check_invariants.py`), example verification (`verify_examples.py`), the full pytest suite, and a CLI smoke test. Docker image build runs on main-branch pushes after tests pass.

---

*This document describes the technical architecture as of Genesis Block 7 (2026-02-18). It covers the full trust model, skill taxonomy, domain-specific trust, labour market mediation, skill lifecycle, identity verification (BIP39 liveness and quorum verification with disability accommodation), compliance screening (17 prohibited categories and penalty escalation), three-tier justice (adjudication panels, Constitutional Court, and rehabilitation), the Genesis Common Fund, workflow orchestration (escrow-first coordination), cryptographic profile, and governance engine. Changes to constitutional parameters require governance approval as described above.*

\* subject to review
