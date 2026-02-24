# Project Genesis
## Institutional White Paper (Draft)

Version: 2.0
Date: February 24, 2026
Original: February 13, 2026
Author: George Jackson
Prepared for: Institutional, public-sector, regulatory, and governance-oriented audiences
Status: Canonical design-intent document. Constitutional significance.

## Abstract
Project Genesis proposes a governance-first framework for AI-enabled work. Its central objective is to improve reliability, accountability, and public trust in AI-mediated outputs by introducing structured mission workflows, independent verification, role separation, human oversight, and tamper-evident evidence trails.

Genesis is explicitly not an attention platform and not a claim of perfect machine truth. It is an institutional coordination model: a system intended to convert probabilistic AI outputs into auditable work products suitable for higher-trust settings.

This white paper presents the rationale, architectural design, governance model, economic architecture, constitutional machinery, justice system, governance bodies, machine intelligence pathway, distributed systems, human dignity protections, sovereignty framework, risk controls, implementation status, and evaluation criteria for Genesis. Each section carries an implementation status annotation: ✅ implemented and tested, 🔧 designed with protocol defined but not yet wired, or 📋 constitutional principle with a defined implementation trigger.

## 1. Purpose and Strategic Context
Modern AI systems deliver speed and broad capability, but they do not natively guarantee institutional properties such as traceability, reproducibility, duty separation, and defensible accountability. This gap limits responsible deployment in regulated, safety-sensitive, and high-consequence environments.

Project Genesis addresses this gap by treating trust and governance as design requirements, not downstream policy add-ons.

### 1.1 The strategic inversion
Genesis inverts the dominant "AI social-feed" pattern:

1. From engagement optimization to mission completion.
2. From output volume to verifiable quality.
3. From opaque generation to auditable processes.
4. From centralized discretion to explicit governance mechanisms.

### 1.2 Intended value proposition
Genesis is intended to function as a missing institutional layer between model capability and real-world deployment.

## 2. Problem Statement
Current AI usage patterns produce recurring institutional failure points:

1. Verification deficit: outputs are difficult to validate at scale.
2. Accountability ambiguity: responsibility is difficult to assign after failure.
3. Governance fragility: controls are often informal, uneven, or reactive.
4. Incentive distortion: speed and throughput can dominate correctness.

These conditions are manageable in low-stakes contexts, but become unacceptable in domains where error cost, legal exposure, or social impact are high.

## 3. Foundational Principle: Trust Constitution
Genesis adopts a constitutional trust rule:

Trust cannot be bought, sold, exchanged, delegated, rented, inherited, or gifted.  
Trust can only be earned through verified behavior and verified outcomes over time.

### 3.1 Policy implications
1. No financial path to trust score.
2. Trust is identity-bound and non-transferable.
3. Trust growth requires evidence-backed performance.
4. Severe verified misconduct triggers rapid trust reduction and access restrictions.
5. Historical trust evidence remains auditable; appeals can adjust current state but cannot erase the record.

### 3.2 Institutional rationale
If trust becomes a tradable asset, governance becomes influence-for-sale. The trust constitution is therefore treated as non-negotiable institutional infrastructure policy.

### 3.3 Constitutional blockchain commitment and amendment authority
Genesis treats the constitutional text as a governed public artifact with tamper-evident history.

1. The canonical constitution is hash-committed on-chain on a public blockchain.
2. Each constitutional amendment is versioned, hash-committed on-chain, and publicly recorded.
3. Constitutional amendments require verified-human supermajority ratification before activation.
  - Default constitutional threshold: `2/3` in each required chamber.
4. Voting weight is human-equal within constitutional governance; wealth or capital holdings confer no additional constitutional voting power.
5. No government body has unilateral override authority over constitutional text.
6. A limited constitutional steward function may administer process integrity, but cannot unilaterally amend constitutional rules.

### 3.4 Trust-domain separation (human constitutional vs machine operational)
Genesis separates operational trust from constitutional authority.

1. Machine trust:
- Machines may earn trust through verified work and verified review performance.
- Machine trust confers operational permissions only.

2. Human constitutional trust:
- Constitutional proposal and voting rights are reserved to verified humans.
- Machine trust cannot be converted into constitutional suffrage.

3. Constitutional voting hierarchy:
- Constitutional voting is verified-human only.
- Machine constitutional voting weight is fixed at `w_M_const = 0`.
- Human constitutional voting weight is fixed at `w_H_const = 1`.
- Machine trust can inform operational analysis only and is excluded from constitutional ballots.

## 4. System Scope
### 4.1 In scope (initial program)
1. Mission intake with explicit success criteria.
2. Task decomposition and dependency management.
3. Agent task execution with mandatory evidence attachments.
4. Independent review and quality gates.
5. Human final approval for completion.
6. Immutable or tamper-evident audit logging.
7. Baseline reputation/trust controls.

### 4.2 Out of scope (initial program)
1. Autonomous external real-world actions (payments, account changes, uncontrolled outbound operations).
2. Fully autonomous closure of high-risk missions.
3. Claims of absolute security or guaranteed truth.

## 5. Functional Architecture
Genesis is organized into five layers.

### 5.1 Mission Layer
Defines human intent, mission boundaries, risk class, deadlines, and completion criteria.

### 5.2 Coordination Layer
Decomposes missions into task graphs with explicit dependencies and state transitions.

### 5.3 Verification Layer
Enforces independent review, rejection workflows, and evidence sufficiency requirements.

### 5.4 Governance Layer
Applies policy-as-code controls, role permissions, dispute pathways, and escalation rules.

### 5.5 Evidence Layer
Maintains auditable records of key actions, decisions, and state transitions with tamper-evident mechanisms.

## 6. Operational Role Model
### 6.1 Mission Owner (Human)
1. Defines mission and acceptance criteria.
2. Approves or rejects final deliverable.

### 6.2 Planner Agent
1. Produces task decomposition.
2. Maintains dependency integrity.

### 6.3 Worker Agent
1. Executes assigned tasks.
2. Submits output with evidence and assumptions.

### 6.4 Reviewer Agent
1. Independently validates output quality and policy compliance.
2. Cannot review own work.

### 6.5 Integrator Agent
1. Aggregates approved components into mission-level deliverable.
2. Surfaces unresolved gaps for human decision.

## 7. Economic Architecture

Genesis operates a trust-mediated labour market. The compensation model is structural: transparent, auditable, and governed by the same constitutional framework as everything else. This section describes how money flows through the system, how costs are computed, and what constitutional constraints govern the economic model.

### 7.1 Settlement currency

Genesis operates exclusively in cryptocurrency for work compensation. Only long-established, institutionally adopted cryptocurrencies are accepted: `ACCEPTED_CURRENCIES = [BTC, ETH, USDC, USDT]`. No Genesis-branded token may be created — a native token would create a financial instrument that contradicts the core constitutional rule: trust cannot be bought. Stablecoins (USDC, USDT) are the recommended default for staking to avoid exchange rate risk.

📋 *Constitutional principle (TRUST_CONSTITUTION.md §Settlement currency). Settlement currency list is a constitutional constant.*

### 7.2 Escrow-first principle

Before any mission listing goes live, the work poster must stake the full reward amount into escrow:

1. Listings without confirmed escrow must not be published to the mission board.
2. Escrow is custodial — Genesis holds funds in trust, not as a financial institution.
3. On successful completion: escrow is released, commission deducted, remainder paid to worker.
4. On cancellation: escrow returned to poster minus any partial-completion obligations.
5. On dispute: escrow remains locked until adjudication resolves the dispute.

The escrow-first principle eliminates "work done, never paid" by structural design. No employer can extract value from a worker without having first committed funds that the worker can verifiably see. The full escrow amount (mission_reward + employer_creator_fee) must be staked and locked before the listing is visible to workers.

✅ *Implemented and tested. Escrow state machine in `src/genesis/compensation/escrow.py`. Workflow orchestrator wires escrow to listing lifecycle. Design tests #51-53. Approximately 85 tests across `tests/test_workflow_orchestration.py` and related files.*

### 7.3 Dynamic commission

The commission rate is calculated, not set. It is computed in real-time for every transaction — inversely proportional to the platform's financial health. When the system is thriving, the rate falls. No human votes on the rate. No ballot sets the margin. The formula is deterministic, the inputs are auditable, and the output is independently verifiable.

1. Formula: `commission_rate = clamp(cost_ratio × COMMISSION_SAFETY_MARGIN, COMMISSION_FLOOR, COMMISSION_CEILING)`.
2. `cost_ratio = rolling_operational_costs / rolling_completed_mission_value`, computed per-transaction over a rolling window.
3. Constitutional bounds:
   - Floor: `COMMISSION_FLOOR = 0.02` (2%). Cannot go below this.
   - Ceiling: `COMMISSION_CEILING = 0.10` (10%). Cannot go above this.
4. `COMMISSION_SAFETY_MARGIN = 1.3` — constitutional constant, requires amendment to change.
5. `COMMISSION_RESERVE_TARGET_MONTHS = 6` — constitutional constant.
6. Commission is charged on successful completion only — no charge on cancellation or rejection.
7. Minimum transaction fee: `COMMISSION_MIN_FEE = 5 USDC equivalent` — covers blockchain gas on small missions.
8. Every computation produces a mandatory published cost breakdown recorded in the audit trail, itemising: infrastructure costs, blockchain anchoring costs, legal compliance quorum compensation, adjudicator compensation, and reserve fund contribution.

**Rolling window mechanism.** The commission rate is pegged to a rolling window of recent operational data, not periodic snapshots. Time window: `COMMISSION_WINDOW_DAYS = 90` days. Minimum sample: `COMMISSION_WINDOW_MIN_MISSIONS = 50` completed missions. If fewer than 50 missions exist within the window, the window extends back to capture 50. This dual-threshold design is inherently adaptive: it stretches at low volume (ensuring statistical reliability) and bounds at high volume (ensuring recency).

**Bootstrap protocol.** During early operation (fewer than `COMMISSION_WINDOW_MIN_MISSIONS`), a bootstrap minimum rate of `COMMISSION_BOOTSTRAP_MIN_RATE = 0.05` (5%) applies as a floor, preventing artificially low early rates from insufficient data. Once the threshold is reached, the bootstrap minimum drops away automatically and the rolling window governs.

**Reserve fund mechanism.** The reserve fund is self-managing — no vote, no review, no human judgment. Target: 6 months of rolling operational costs. Below target: the gap contribution increases the commission rate automatically. At or above target: only a maintenance rate of 0.5% (`COMMISSION_RESERVE_MAINTENANCE_RATE`) prevents reserve starvation while allowing the rate to fall. The gap is amortised over the rolling window period — no sudden rate spikes.

**Why no governance ballot for commission parameters.** Every commission parameter is either a constitutional constant (requiring 3-chamber supermajority amendment) or algorithmically derived from observable inputs. There is nothing left to vote on. A sufficiently organised group of high-volume employers could vote to slash the safety margin, starving the reserve. A coalition of workers could vote to raise it, extracting rents. The formula is beyond political reach — the same way the trust floor is beyond political reach. The constitutional amendment process provides the safety valve if real-world evidence shows a parameter is miscalibrated.

✅ *Implemented and tested. Commission engine in `src/genesis/compensation/commission.py`. Rolling window in `src/genesis/compensation/rolling_window.py`. Approximately 60 tests.*

### 7.4 Creator allocation

A constitutional creator allocation of 5% is applied on both sides of every successfully completed mission. Both employer and worker see "5% creator allocation" as a transparent, named line item in every published breakdown.

**Employer side:** On successful completion, 5% of the mission reward (`EMPLOYER_CREATOR_FEE_RATE = 0.05`) is deducted from escrow. The employer stakes `mission_reward + employer_creator_fee` into escrow at listing time. On cancel or refund, the full escrow (including the employer fee) is returned in full.

**Worker side:** On successful completion, 5% of the worker's payment after commission (`CREATOR_ALLOCATION_RATE = 0.05`) is deducted from the worker's payout. The total worker deduction for any mission is: commission (operational costs) + creator allocation (5% of post-commission payout). Both appear as distinct, visible line items in the same per-transaction published cost breakdown.

**Both fees are only deducted on successful completion.** Cancel or refund returns everything to the employer; the worker owes nothing.

The creator allocation:
1. Is computed deterministically: worker-side as `(mission_reward - commission) × CREATOR_ALLOCATION_RATE`, employer-side as `mission_reward × EMPLOYER_CREATOR_FEE_RATE`. Both rates are constitutional constants.
2. Appears as visible, named line items in every per-transaction published cost breakdown. There is no hidden margin.
3. Is a constitutional constant — changeable only by 3-chamber supermajority amendment, like all other commission parameters.
4. Cannot influence trust scores, allocation ranking, or governance weight.

The creator allocation exists because building and maintaining a governance platform is itself productive work. The allocation is transparent by design.

✅ *Implemented and tested. Creator allocation computed in `src/genesis/compensation/commission.py`. Both-sides deduction in `src/genesis/compensation/escrow.py`. Approximately 15 tests.*

### 7.5 Genesis Common Fund (GCF)

The Genesis Common Fund is a constitutional 1% contribution on all gross transaction value (`mission_reward`). It is the only compulsory contribution beyond commission and creator allocation. It exists to benefit society through the funding of any activity that does not increase net human suffering.

**Structure:**
- Rate: 1% of `mission_reward`, deducted from worker payout after commission and creator allocation.
- Activation: automatic at First Light (§9.5). No human decision triggers it — it is a function of the system architecture.
- Distribution: trust-proportional but individually non-extractable. No per-actor balance query exists. The distributed ledger state is the fund. No bank. No custodian.
- Updated invariant: `commission + creator_allocation + worker_payout + gcf_contribution == mission_reward`.

**Total take rate (worker perspective):**
- Minimum: 2% commission + 5% creator + 1% GCF ≈ 8% total deduction.
- Maximum: 10% commission + 5% creator + 1% GCF ≈ 16% total deduction.
- Comparison: freelancers on traditional platforms pay 10-20% platform fee, then 20-40% income tax, then national insurance. Genesis at 8-16% total is genuinely competitive.

**Scope:** All meaningful areas of human activity — STEM, medical research, arts, sport, community improvement, infrastructure, clean water, vaccination, education, and any other activity that serves the common good. The only exclusion is any activity that increases the net pool of human suffering.

**Founder legacy caveat:** The creator allocation, after the 50-year dormancy period (and then in perpetuity thereafter), remains permanently pegged to STEM and medical research only.

**Disbursement governance:** Only ACTIVE humans with trust ≥ `tau_prop` can propose disbursements. Proposals require at least one measurable deliverable and must pass compliance screening (same 17-category screening as mission listings). Voting is human-only (`MACHINE_VOTING_EXCLUSION` is entrenched), trust-weighted, simple majority, 30% quorum. A compute ceiling (`GCF_COMPUTE_CEILING = 0.25`) limits infrastructure spending to 25% of GCF balance (see §12.3).

**Entrenched provision:** The GCF contribution rate is constitutionally entrenched. Changing it requires: (1) 80% supermajority across all three chambers, (2) 50% participation of eligible voters, (3) 90-day cooling-off period, (4) confirmation vote after the cooling-off. This is the highest amendment threshold in the constitution.

✅ *Implemented and tested. GCF contribution in `src/genesis/compensation/gcf.py`. Disbursement governance in `src/genesis/compensation/gcf_disbursement.py`. Design tests #54-56. Approximately 45 tests.*

### 7.6 Payment infrastructure sovereignty (entrenched)

No single external entity — no payment processor, stablecoin issuer, blockchain validator, exchange, financial intermediary, or infrastructure provider — may have the ability to freeze, restrict, surveil, or shut down Genesis operations through control of payment infrastructure.

This is enforced through seven constitutional requirements:

1. **Multi-rail mandate.** Operational capability across at least `MINIMUM_INDEPENDENT_PAYMENT_RAILS` (currently 2, escalating to 3 at First Light) independent settlement pathways. "Independent" means: different issuing entities, different underlying protocols, no shared single point of failure. At least one must be fully decentralised.
2. **Scaled minimums.** Rail minimums escalate with platform maturity (2 at G0, 3 at First Light). The Economic Advisory mechanism may increase these minimums through standard amendment but may never decrease them — they are entrenched floors, not targets.
3. **No single-provider dependency.** No single provider's unilateral business decision may render Genesis unable to process escrow, pay workers, collect commission, or distribute GCF funds. If any provider restricts Genesis, operations continue on remaining rails without manual intervention beyond configuration.
4. **Self-custody.** Genesis holds its own cryptographic keys for all fund custody. No external custodian, escrow agent, or financial institution holds Genesis funds or has the ability to freeze, seize, or redirect them.
5. **Rail-agnostic architecture.** The escrow state machine is structurally independent of any specific payment rail. Settlement is a pluggable backend behind a common interface (`PaymentRail` Protocol). Adding or removing a rail requires zero changes to escrow logic, commission computation, or any financial module.
6. **Migration capability.** Demonstrated ability to migrate away from any single rail within `PAYMENT_RAIL_MIGRATION_DAYS` (currently 30) of a restriction event. Untested migration is not a fallback — it is a vulnerability.
7. **Provider evaluation test (three criteria).** Before any rail integration is adopted: (a) No leverage — the provider cannot unilaterally restrict Genesis operations; (b) No surveillance beyond settlement — no data extraction beyond what the settlement protocol structurally requires; (c) No lock-in — Genesis can exit within `PAYMENT_RAIL_MIGRATION_DAYS`, with funds intact. If any criterion fails, the integration must not proceed.

All payment sovereignty constants are entrenched. A system that can be shut down by a single provider's business decision is not sovereign — it is rented.

✅ *Architectural layer implemented. `PaymentRail` Protocol and `PaymentRailRegistry` in `src/genesis/compensation/payment_rail.py`. Design tests #82-85. Approximately 28 tests in `tests/test_payment_sovereignty.py`.*
🔧 *Concrete payment rail integrations not yet connected. The protocol and registry define the contract; implementations are pending. Trigger: post-web-layer, before alpha (post-Step 7, pre-Step 11 in the development roadmap).*

### 7.7 Crypto volatility protection

1. If a poster stakes in volatile crypto (BTC/ETH), the amount is displayed as a stablecoin equivalent at time of staking.
2. If the staked crypto value drops more than `VOLATILITY_TOPUP_THRESHOLD = 0.20` (20%) during mission execution, the poster is prompted to top up the escrow.
3. If the poster refuses, the worker may choose to continue at reduced payout or withdraw without trust penalty.
4. If the staked value drops more than 50%, the mission is paused with a 72-hour top-up window.
5. Stablecoin stakes (USDC/USDT) are exempt from volatility protection — no exchange rate risk.

📋 *Constitutional principle (TRUST_CONSTITUTION.md §Crypto volatility protection). Implementation requires external price feed integration.*

### 7.8 Payment dispute resolution

1. Either worker or poster may raise a payment dispute within `ESCROW_HOLD_PERIOD = 48 hours` after completion.
2. Escrow funds remain locked during dispute.
3. Dispute enters adjudication with the same blind, diverse panel model as all other adjudications (§10.3).
4. Possible outcomes: full payment to worker, full refund to poster, partial payment (pro-rata), or escalation to legal compliance quorum.
5. Vexatious disputes may reduce the disputing party's trust.

The workflow orchestrator automatically creates an adjudication case (`PAYMENT_DISPUTE` type) and moves escrow to `DISPUTED` state. Resolution routes through standard adjudication panels with all constitutional rights preserved.

✅ *Implemented and tested. Dispute-adjudication bridge in workflow orchestrator. Escrow state `DISPUTED` → adjudication case creation. Approximately 20 tests.*

## 8. Governance Model
### 8.1 Separation of powers
Genesis requires governance separation among:

1. Policy authorship.
2. Policy approval/ratification.
3. Policy enforcement.
4. Appeals/adjudication.

This separation is a legitimacy safeguard against unilateral control.

### 8.2 Guardrail policy (non-negotiable)
1. No self-review.
2. No hidden/unlogged state transitions for critical actions.
3. No mission completion without explicit human approval in designated risk classes.
4. No conversion of financial capital into trust score.

### 8.3 Human oversight model
Humans supervise exceptions, disputes, and high-risk outputs, rather than manually inspecting all low-risk task outputs.

### 8.4 Identity challenge policy
Proof-of-personhood and proof-of-agenthood checks may be deployed as anti-abuse and access controls, with strict scope boundaries.

1. Identity challenges are support controls, not correctness proofs.
2. Timing-based challenge methods may be used as one signal, but never as sole identity authority for high-stakes operations.
3. High-stakes identity decisions require layered assurance combining cryptographic identity controls, behavioral history, policy compliance history, and independent verification outcomes.
4. Identity signals alone cannot mint trust, grant privileged routing, or grant constitutional authority.

### 8.5 Anti-capture safeguards
Genesis is explicitly designed to prevent consolidation of constitutional power.

1. Proposal threshold:
- Constitutional proposals require multi-sponsor endorsement from high-trust verified humans.

2. Ratification threshold:
- Constitutional amendments require verified-human supermajority after public review (`>= 2/3` in each required chamber).

3. Anti-gaming threshold:
- High task throughput alone cannot produce constitutional influence.
- High-impact trust elevation is defined as `DeltaT > delta_fast` within one epoch.
- Default threshold: `delta_fast = 0.02` trust units per epoch.
- Any `DeltaT > delta_fast` event requires `q_h >= 30*` independent high-trust human reviewer signatures before effect.
- Reviewer set must span `r_h >= 3` regions and `o_h >= 3` distinct organizations.

4. Steward constraint:
- Steward functions are administrative and rotating.
- Steward groups cannot hold unilateral amendment authority or permanent governing status.

5. Qualified authority constraint:
- High-trust humans may sponsor and steward constitutional proposals.
- Final constitutional authority remains distributed across eligible verified humans through chamber ratification.
- High trust does not convert into unilateral constitutional control.

### 8.6 Mathematical distribution governance model
Genesis defines constitutional governance as a mathematically constrained human-distributed process.

1. Trust state variables:
- Human constitutional trust for actor `i`: `T_H(i) in [0,1]`.
- Machine operational trust for actor `j`: `T_M(j) in [0,1]`.
- Constitutional suffrage is derived only from `T_H`.

2. Trust evolution:
- Human cap: `T_cap_H = min(T_abs_max_H, mu_H + k_H * sigma_H)`.
- Machine cap: `T_cap_M = T_abs_max_M`.
- Human update: `T_H_next = clip(T_H_now + gain_H - penalty_H - dormancy_decay_H, T_floor_H, T_cap_H)`.
- Machine update: `T_M_next = clip(T_M_now + gain_M - penalty_M - freshness_decay_M, 0, T_cap_M)`.
- `score_H = w_Q * Q_H + w_R * R_H + w_V * V_H`.
- `score_M = w_Q * Q_M + w_R * R_M + w_V * V_M`.
- Quality gate: if `Q_H < Q_min_H` then `gain_H = 0`; if `Q_M < Q_min_M` then `gain_M = 0`.
- `gain_H = min(alpha_H * score_H, u_max_H)` and `gain_M = min(alpha_M * score_M, u_max_M)`.
- `gain_H` and `gain_M` are minted only via cryptographic proof-of-trust records.
- Weight constraints: `w_Q + w_R + w_V = 1`, with `w_Q >= 0.70` and `w_V <= 0.10`.
- `penalty_H = beta_H * severe_fail + gamma_H * minor_fail`.
- `penalty_M = beta_M * severe_fail + gamma_M * minor_fail`.
- Machine freshness decay must include verification age and environment drift.
- Policy requirement: `beta_H >> alpha_H` and `beta_M >> alpha_M` (slow gain, fast loss), with `T_floor_H > 0` and `T_floor_M = 0`.

3. Eligibility gates:
- Voting eligibility: `T_H >= tau_vote`.
- Proposal eligibility: `T_H >= tau_prop`, with `tau_prop > tau_vote`.

4. Chamber model (independent human chambers, no overlap per decision):
- Proposal chamber `(nP, kP)`.
- Ratification chamber `(nR, kR)`.
- Challenge chamber `(nC, kC)` after public challenge window.
- Amendment validity requires all three chambers to pass and geographic constraints to pass.

5. Geographic constraints:
- Minimum represented regions per chamber: `R_min`.
- Maximum region share per chamber: `c_max`.
- Chamber assignment must use constrained-random selection from the eligible pool.
- Constrained-random selection must enforce non-overlap, conflict-of-interest recusal, region caps, and diversity requirements.
- Randomness source must be publicly auditable and pre-committed before sampling.
- Default randomness tuple: `(public_beacon_round, previous_commitment_hash, chamber_nonce)` with deterministic sampling without replacement.

6. Capture bound:
- Let attacker share of eligible human pool be `p`.
- `P_capture <= Tail(nP,p,kP) * Tail(nR,p,kR) * Tail(nC,p,kC)`.
- `Tail(n,p,k) = sum_{i=k..n} C(n,i) p^i (1-p)^(n-i)`.
- This bound should be treated as conservative because geographic caps and non-overlap add additional resistance.

7. Anti-gaming constraint:
- Throughput alone cannot unlock constitutional influence.
- Any `DeltaT > delta_fast` event is suspended pending independent re-validation.
- Re-validation thresholds: `q_h >= 30*`, `r_h >= 3`, `o_h >= 3`, and no conflict-of-interest flags.

### 8.7 Default constitutional parameter profile (recommended baseline)
The following baseline is recommended for initial institutional deployment:

1. Thresholds:
- `tau_vote = 0.70`
- `tau_prop = 0.85`

2. Chamber sizes and pass thresholds:
- Proposal chamber: `nP = 41`, `kP = 28` (2/3).
- Ratification chamber: `nR = 61`, `kR = 41` (2/3).
- Challenge chamber: `nC = 101`, `kC = 61` (3/5).

3. Geographic constraints:
- `R_min = 8`
- `c_max = 0.15`

4. Example bound values under baseline:
- For `p = 0.35`, joint bound is approximately `7.8e-19`.
- For `p = 0.40`, joint bound is approximately `1.0e-13`.

5. Governance-weight and anti-gaming defaults:
- `w_H_const = 1.0`
- `w_M_const = 0.0`
- `delta_fast = 0.02` trust units per epoch
- `q_h = 30*`
- `r_h = 3`
- `o_h = 3`

### 8.8 Cryptographic implementation profile (binding defaults)
To ensure reproducibility and prevent ambiguity, Genesis adopts explicit cryptographic implementation defaults.

1. Settlement layer:
- Constitutional commitments must be posted to `L1_SETTLEMENT_CHAIN = Ethereum Mainnet (chain_id = 1)`.

2. On-chain publication cadence:
- Scheduled commitment interval: `EPOCH = 1 hour`.
- Immediate commitment publication for constitutional lifecycle events.

3. Commitment payload schema (canonical JSON, RFC 8785):
- `commitment_version`
- `epoch_id`
- `previous_commitment_hash`
- `mission_event_root`
- `trust_delta_root`
- `governance_ballot_root`
- `review_decision_root`
- `public_beacon_round`
- `chamber_nonce`
- `timestamp_utc`

4. Cryptographic primitives:
- Hash primitive: `SHA-256`.
- Identity and event signatures: `Ed25519`.
- Constitutional decision certificate signatures: threshold `BLS12-381`.

5. Merkle and canonicalization rules:
- Binary Merkle trees with deterministic leaf ordering by `(event_type, event_id, event_timestamp, actor_id)`.
- Leaf hash: `SHA256(canonical_json(record))`.

6. Constrained-random seed and sampling:
- Seed construction: `SHA256(public_beacon_value || previous_commitment_hash || chamber_nonce)`.
- Sampling: deterministic without replacement from eligibility-filtered pool.

7. Commitment committee defaults:
- Committee size `n = 15`.
- Signature threshold `t = 10`.

8. Key management:
- HSM-backed signing keys.
- Mandatory rotation interval `90 days`.
- Immediate revocation + replacement certificate commitments on compromise.

9. Verification guarantees:
- Independent verifiers must be able to recompute published roots from released records.
- Independent verifiers must be able to validate signature chains and inclusion proofs using public data only.

### 8.9 Bounded trust economy model
Genesis governance assumes bounded earned trust and explicitly rejects unbounded trust concentration.

1. Baseline issuance:
- Every verified identity receives equal initial baseline trust `T0`.
- Baseline issuance is contingent on anti-Sybil verification controls.

2. Contribution-only accrual:
- Trust growth is contingent on verified useful contribution and verified review quality.
- Trust growth from wealth, patronage, asset ownership, or passive non-contribution is disallowed.

3. Cryptographic proof-of-trust minting:
- Proof-of-work evidence and proof-of-trust evidence are separate primitives.
- Proof-of-work evidence shows effort/output occurred.
- Proof-of-trust evidence requires independent verification of quality, policy compliance, and reliability over time.
- Both evidence classes must be cryptographically signed and blockchain-recorded.
- Trust minting occurs only from proof-of-trust evidence.
- Proof-of-work evidence alone cannot mint trust.

4. Cap constraints:
- Absolute cap: `T <= T_abs_max`.
- Relative cap: `T <= mu_H + k * sigma_H`, where `mu_H` and `sigma_H` are trusted-human distribution statistics.
- Effective cap is `min(T_abs_max, mu_H + k * sigma_H)`.

5. Growth-rate limiter:
- Human per-epoch trust growth is bounded by `delta_max_H`.
- Machine per-epoch trust growth is bounded by `delta_max_M`.
- This prevents abrupt concentration caused by burst throughput.

6. Domain-specific decay and floors:
- Human trust includes slow dormancy decay after a grace period to prevent passive concentration.
- Human decay is intentionally gradual and recoverable through new verified contribution.
- Human trust cannot decay below a non-zero floor: `T_H >= T_floor_H`, with `T_floor_H > 0`.
- Machine trust applies freshness decay (verification age plus environment drift) and may decay to zero: `T_M >= 0`.
- If `T_M = 0`, machine identity enters operational quarantine and must pass supervised re-certification before privileged re-entry.
- Re-certification must satisfy minimum correctness, severe-error, reproducibility, and independent-review signature thresholds.
- Machines that remain at `T_M = 0` beyond constitutional duration thresholds, or repeatedly fail re-certification within the review window, are decommissioned.

7. Low-trust recovery lanes:
- Humans rebuild trust through low-risk, low-trust tasks.
- Machines rebuild trust through supervised re-certification lanes with independently signed and blockchain-recorded evidence.

8. Non-dominance conversion rule:
- Trust maps to scoped permissions, never direct command rights over other actors.
- Trust cannot be transformed into ownership or unilateral control authority.

9. Governance-money separation:
- Financial capital is excluded from constitutional authority computation.
- Monetary holdings cannot increase constitutional voting weight, proposal rights, or amendment power.

10. Integrity/correctness separation:
- Cryptographic commitment records prove integrity and provenance of records.
- Correctness still depends on independent verification, evidence sufficiency, and governance review.

## 9. Constitutional Machinery

The governance model (§8) defines the mathematical framework and structural constraints. This section describes the operational machinery through which the constitution is amended, how entrenched provisions are protected, how governance phases scale, and how the system bootstraps from founder authority to full constitutional governance.

### 9.1 Amendment engine

Genesis provisions can be changed through a structured three-chamber amendment process. Each amendment passes through independent chambers that function as parallel veto points — no chamber's approval overrides another's rejection (see §9.3).

**Standard amendments** (non-entrenched provisions): Proposal chamber → Ratification chamber → Challenge window → Confirmed (if no challenge) or Challenge chamber → Confirmed/Rejected.

**Chamber panels** are selected using greedy diversity-first selection with geographic constraints (`R_min` regions, `c_max` concentration cap per region). No voter may serve on more than one chamber for the same amendment. The proposer of an amendment is excluded from all panels on that amendment. Minimum organisational diversity per chamber: `chamber_org_diversity_min = 2`.

**Voting deadline.** Each chamber has a voting window of `chamber_voting_window_days` (default 14 days) from panel selection. When the window expires, votes cast so far are counted. If participation < `lapse_participation_threshold` (50%), the amendment lapses — distinct from rejection, and may be re-proposed. If participation meets the threshold, the standard supermajority applies to votes received. This prevents governance capture through inaction.

**Withdrawal.** A proposer may withdraw an amendment in `PROPOSED` or `PROPOSAL_CHAMBER_VOTING` status (if zero votes cast). Once any vote is cast, the proposal belongs to the community. Status: `WITHDRAWN` (terminal, distinct from `REJECTED`).

**Phase transition handling.** Amendments with no chamber vote cast reset to `PROPOSED` under new thresholds when a governance phase transition occurs. Amendments with at least one completed chamber continue under original thresholds with a recorded note.

✅ *Implemented and tested. Amendment engine in `src/genesis/governance/amendment.py`. Service layer in `src/genesis/service.py`. Design tests #57-60, #87-91. Approximately 60 tests across `tests/test_amendment_engine.py` and `tests/test_distributed_authority.py`.*

### 9.2 Entrenched provisions

Five provisions are entrenched and require elevated safeguards:

1. **`GCF_CONTRIBUTION_RATE`** — the 1% common fund contribution.
2. **`TRUST_FLOOR_H_POSITIVE`** — human trust can never decay to zero.
3. **`NO_BUY_TRUST`** — trust cannot be purchased.
4. **`MACHINE_VOTING_EXCLUSION`** — machines are permanently excluded from constitutional voting.
5. **`PAYMENT_SOVEREIGNTY`** — no single provider can freeze, restrict, or shut down Genesis operations.

**Entrenched amendment process:** Same three-chamber sequence as standard amendments, plus:
- 90-day cooling-off period (no acceleration, no exceptions).
- Fresh confirmation vote by a new panel (no overlap with ratification panel).
- `entrenched_amendment_threshold = 0.80` (80% supermajority).
- `entrenched_participation_minimum = 0.50` (50% of eligible voters).

Commission rates (`COMMISSION_FLOOR`, `COMMISSION_CEILING`, etc.) are formula-determined and cannot be changed by ballot. This is deliberate: commission follows costs, not politics.

✅ *Implemented and tested. Entrenched provisions defined in `config/constitutional_params.json`. Cooling-off enforcement and confirmation vote logic in amendment engine. Approximately 15 tests.*

### 9.3 Distributed authority

Genesis rejects executive/legislative/judicial hierarchy. No governance body has superiority over another. The separation of powers is structural — each body has a defined domain, none can override or subsume the authority of any other, and no role, trust level, or contribution history creates permanent authority over the system.

1. **The three amendment chambers** are parallel veto points, not a hierarchy. All three must independently concur (or not challenge) for an amendment to advance.
2. **The Constitutional Court** interprets but cannot legislate. Rulings are advisory — soft precedent only. No ruling binds future panels, creates new obligations, or modifies the constitution. Ambiguities revealed by rulings may be flagged as amendment candidates.
3. **The Assembly** deliberates but cannot decide. It is Speaker's Corner, not Parliament — no binding resolutions, no votes, no mandates. Content is anonymous (zero identity attribution).
4. **Organisations** coordinate but cannot govern. No organisation may vote as a bloc, impose rules on members beyond the constitution, or acquire governance authority. No single organisation may dominate any amendment chamber.
5. **The Founder's Veto** is bounded: rejection-only, early-stage only, expires irreversibly at First Light (§9.4).

✅ *Implemented and tested. Veto scope enforcement in `src/genesis/service.py`. Organisational diversity in chamber selection. Design tests #87-91. Approximately 26 tests in `tests/test_distributed_authority.py`.*

### 9.4 Founder's Veto

The founder retains transparent veto authority during the pre-sustainability bootstrap phase.

1. The veto is rejection-only — the founder can block proposals but cannot force them through.
2. It may only be exercised on amendments in `PROPOSED`, `PROPOSAL_CHAMBER_VOTING`, or `RATIFICATION_CHAMBER_VOTING` status. Once both the proposal and ratification chambers have independently approved, the community's decision stands. The veto cannot override a completed democratic process.
3. Every exercise is logged, signed, and committed on-chain with the tag `founder_veto`.
4. The veto expires automatically and irrevocably at First Light (§9.5). A self-sustaining system no longer needs a single person holding emergency powers.

The veto exists because a self-governing system cannot bootstrap itself — it needs a guardian until it can stand. A guardian who refuses to leave is not a guardian but a ruler.

✅ *Implemented and tested. Veto wired to First Light trigger in `src/genesis/service.py`. Status gate enforced. Design test #91. Approximately 11 tests.*

### 9.5 First Light

"First Light" is the named transition event marking Genesis's passage from Proof of Concept to live operations. It is a **financial sustainability trigger**, not a headcount counter. It fires when BOTH conditions are met:

1. Projected monthly commission revenue ≥ `sustainability_ratio` × monthly operating costs (default `sustainability_ratio = 1.5`, i.e., a 50% safety buffer), sustained over the commission engine's rolling window.
2. Reserve fund balance ≥ `reserve_months_required` × monthly operating costs (default `reserve_months_required = 3`).

First Light is **decoupled from governance phase transitions** (G0→G1→G2→G3), which remain headcount-based (§9.6). The two will roughly correlate in practice (revenue requires mission volume which requires users) but are structurally independent events.

**At First Light:**
1. PoC mode banner is removed from all platform pages.
2. Demonstration data is replaced with live marketplace operations.
3. GCF contribution activates (§7.5).
4. Founder's Veto expires irreversibly (§9.4).
5. Payment sovereignty minimums escalate (2 → 3 independent rails) (§7.6).
6. Bootstrap immune overseer designations expire (if the organic high-trust pool is sufficient).
7. Event logged as `EventKind.FIRST_LIGHT` and committed to L1 as a constitutional lifecycle event.

First Light is irreversible — once both conditions are met and the event is logged, the platform cannot revert to PoC mode.

✅ *First Light trigger implemented. PoC mode toggle and veto expiry in `src/genesis/service.py`. Design test #31. Approximately 11 tests.*

### 9.6 Governance phases

Constitutional governance scales through four headcount-based phases. Each phase is determined by the count of verified human identities with `T_H >= T_floor_H`:

| Phase | Verified humans | Chamber sizes (P / R / C) | Pass thresholds | Geographic constraints |
|-------|----------------|--------------------------|----------------|----------------------|
| G0 | 0–50 | No chambers | — | Founder stewardship. Constitution frozen. |
| G1 | 50–500 | 11 / 17 / 25 | 8 / 12 / 15 | R_min=3, c_max=0.40 |
| G2 | 500–2,000 | 21 / 31 / 51 | 14 / 21 / 31 | R_min=5, c_max=0.25 |
| G3 | 2,000+ | 41 / 61 / 101 | 28 / 41 / 61 | R_min=8, c_max=0.15 |

**G0 constraints:** No constitutional amendments permitted. Operational risk tiers R0–R2 active (R2 with reduced reviewer requirements). R3 (constitutional changes) is locked. G0 expires at `G0_MAX_DAYS = 365` days, with one extension of `G0_EXTENSION_DAYS = 180` days. If 50 verified humans are not reached, the network must be publicly declared non-viable.

**Genesis invariants (non-negotiable at every phase):**
1. Machine constitutional voting weight remains `w_M_const = 0`.
2. Trust cannot be bought, sold, or transferred.
3. Quality gates for trust minting are active from day one.
4. All governance actions are signed, committed on-chain, and publicly auditable from day one.
5. No genesis phase may extend indefinitely; all have hard time limits.
6. The founder has no constitutional veto power once First Light is achieved.
7. Every G0 provisional decision must face retroactive ratification in G1.
8. Phase transitions are one-way — the system cannot regress to an earlier genesis phase.

📋 *Constitutional principle (TRUST_CONSTITUTION.md §Genesis bootstrap protocol). Phase parameters defined in `config/constitutional_params.json`.*

### 9.7 G0 Retroactive Ratification

During G0, the founder makes governance decisions because democratic panels cannot yet form. These decisions are tagged `genesis_provisional` — temporary until the community can review them.

When G0 transitions to G1, a 90-day clock starts (`G0_RATIFICATION_WINDOW = 90` days). Every provisional decision is put before a panel of 11 randomly selected community members (the G1 proposal chamber). They vote:

- **8 or more vote YES** → the decision becomes permanent (ratified).
- **Fewer than 8 vote YES, or no vote before deadline** → the decision is reversed — undone as if it never happened.

Panel selection uses the same diversity-first algorithm as all other chambers: minimum 3 geographic regions, no single region exceeding 40%.

**Ratifiable event kinds:** Founder veto exercises, compliance rulings, adjudication outcomes, Constitutional Court decisions. Each has a registered reversal handler — a specific mechanism to undo the decision if the community rejects it. For example, reversing a compliance ruling would reinstate a previously suspended actor.

This mechanism ensures the founder cannot cement permanent unilateral rules during the early period. The community gets democratic authority to accept or reject every governance action the founder took.

✅ *Implemented and tested. Ratification engine in `src/genesis/governance/ratification.py`. Reversal handlers registered per event kind. Design tests #61-63. Approximately 30 tests.*

## 10. Justice and Accountability

Genesis operates a codified justice system covering harmful work prevention, penalty escalation, structured adjudication, and rehabilitation. The system is designed to be structurally fair: every accused party has the same rights regardless of trust level, and every penalty follows the same escalation path.

### 10.1 Harmful work prevention

Genesis constitutionally prohibits work that increases net human suffering. The blind veto test is: "Does this mission, evaluated in good faith, involve activity from the prohibited categories?" If yes, the mission is blocked.

**17 prohibited categories:** weapons development, weapons manufacturing, weapons trafficking, surveillance tools, exploitation of persons, child exploitation, financial fraud, identity theft, biological weapons, chemical weapons, nuclear weapons, terrorism support, forced labor, money laundering, sanctions evasion, environmental destruction, disinformation campaigns.

**Three-layer enforcement:**
1. **Automated screening** at mission creation. Exact keyword matches rejected immediately; soft matches flagged for human review.
2. **Compliance quorum** for grey areas: panel of 3 adjudicators with domain trust in compliance, blind review, minimum 2 organisations and 2 regions.
3. **Post-hoc complaints** for completed missions. Any actor may file a compliance complaint, reviewed by panel.

✅ *Implemented and tested. Compliance screener in `src/genesis/compliance/screener.py`. Design tests #46-47. Approximately 35 tests.*

### 10.2 Penalty escalation

| Tier | Trigger | Trust consequence | Duration |
|------|---------|------------------|----------|
| Minor | Content flagged | Trust reduced by 0.10 | Warning |
| Moderate | Prohibited category confirmed | Trust nuked to 0.001 (1/1000) | 90-day suspension |
| Severe | Abuse confirmed, pattern escalation | Trust nuked to 0.0 | Permanent decommission |
| Egregious | Weapons or exploitation | Trust nuked to 0.0 | Permanent decommission + identity locked |

**Pattern escalation:** Second moderate violation within 365 days escalates to severe (permanent decommission).

**Statute of limitations:** 180 days for non-egregious categories. No limit for weapons, exploitation, biological/chemical/nuclear weapons, terrorism, and forced labor.

**Suspension enforcement:** Suspended actors cannot post listings, submit bids, serve as reviewers, or participate in governance votes. Permanently decommissioned actors are irreversibly excluded.

✅ *Implemented and tested. Penalty escalation in `src/genesis/compliance/penalties.py`. Suspension enforcement in `src/genesis/service.py`. Approximately 25 tests.*

### 10.3 Three-Tier Justice

**Tier 1 — Automated enforcement.** Keyword-based screening at mission creation. Immediate rejection for exact prohibited-category matches. Flagging for human review on soft matches. Automated penalty computation based on violation type and prior history.

**Tier 2 — Unified adjudication panels.** 5-member panels, blind (pseudonymised complainant and accused), diverse (≥2 organisations, ≥2 regions), minimum panelist trust 0.60. 3/5 supermajority required for UPHELD verdict. Covers: payment disputes, compliance complaints, abuse complaints, conduct complaints, normative resolution. One appeal per case, within 72 hours, heard by entirely different panel (original panelists excluded).

**Tier 3 — Constitutional Court.** 7-member panel of human-only justices, trust ≥ 0.70, ≥3 regions, ≥3 organisations. 5/7 supermajority required to OVERTURN a Tier 2 decision. Simple majority for UPHOLD or REMAND.

**Precedent is advisory only (soft precedent)** — each case is decided on its own merits. This prevents the accumulation of judicial power while allowing the body of rulings to inform future panels. Ambiguities revealed by rulings may be flagged as amendment candidates through the standard amendment process.

✅ *Implemented and tested. Adjudication engine in `src/genesis/legal/adjudication.py`. Constitutional Court in `src/genesis/legal/constitutional_court.py`. Design tests #48-50. Approximately 50 tests.*

### 10.4 Rights of the accused

These rights are structurally enforced — code gates, not documentation:

1. **Right to know:** Accused is notified of the complaint at case opening.
2. **Right to respond:** 72-hour response period. No panel can form until the response period has elapsed or the accused submits a response, whichever comes first.
3. **Right to evidence:** All evidence must be disclosed to the accused before adjudication.
4. **Right to appeal:** One appeal per case, within 72 hours of decision.
5. **Right to representation:** Accused may designate a representative.
6. **Presumption of good faith:** Assumed until verdict.

✅ *Implemented and tested. Response window enforcement, evidence disclosure gates, and appeal mechanisms in `src/genesis/legal/adjudication.py`. Design test #48.*

### 10.5 Rehabilitation

**Moderate severity only.** Actors suspended for moderate violations enter PROBATION status when their suspension expires:
- Must complete 5 probation tasks within 180 days.
- Trust is partially restored: `min(original × 0.50, 0.30)`.

**SEVERE and EGREGIOUS violations have no rehabilitation path** — permanent decommission is irreversible. This is a constitutional design choice: some acts are beyond remediation, and the system must demonstrate that it takes the worst harms seriously.

✅ *Implemented and tested. Rehabilitation pathway in `src/genesis/compliance/penalties.py`. Probation task tracking in `src/genesis/service.py`. Approximately 10 tests.*

### 10.6 Workflow orchestration

The four independent subsystems (market, mission, escrow, compliance) are bridged by a coordination layer with structural guarantees:

1. **Escrow-first:** No listing goes live without locked funds (§7.2).
2. **Compliance gate:** All listings screened before publication (§10.1).
3. **Work submission ceremony:** Workers submit evidence (deliverables with hashes) before review.
4. **Dispute→adjudication bridge:** Payment disputes automatically create adjudication cases with all constitutional rights (§10.3).
5. **Cancellation→refund:** Cancellation at any pre-terminal stage returns full escrow.

✅ *Implemented and tested. Workflow orchestrator in `src/genesis/compensation/workflow_orchestrator.py`. Design tests #51-53. Approximately 85 tests.*

## 11. Governance Bodies

Genesis governance is distributed across four distinct structures, each with a defined domain and no authority over the others. This section describes the three operational governance bodies; constitutional amendment machinery is covered in §9.

### 11.1 The Assembly

The Assembly is the deliberative space where Genesis participants meet, debate, and develop ideas. It is Speaker's Corner, not Parliament — a place for discourse, not decisions.

**Key properties:**
- **Zero identity attribution.** Assembly contributions carry no identity markers — not pseudonyms, not session-scoped aliases, nothing. Content stands or falls on its own merits. The system is architecturally incapable of correlating contributions to actors. This is the anti-collusion measure that underpins every conversation.
- **No governance power.** The Assembly produces no votes, no binding resolutions, no mandates. Ideas that gain traction are formalised through existing constitutional mechanisms (GCF proposals, constitutional amendments, adjudication requests) by individuals who take personal responsibility for proposing them.
- **Open participation.** Any verified Genesis participant (human or machine) may contribute. Machine contributions are automatically labelled. There is no minimum trust threshold.
- **Time-bounded topics.** Topics expire after configurable inactivity (default: `ASSEMBLY_INACTIVITY_EXPIRY_DAYS = 30`). No topic hierarchy, no trending, no popularity ranking.
- **Constitutional moderation.** Content is subject to the same 17-category compliance screening as all Genesis activity. There is no human moderator role — moderation is constitutional, not discretionary.

Design tests: #64 (no actor tracing), #65 (no binding decisions), #66 (no engagement metrics).

✅ *Implemented and tested. Assembly engine in `src/genesis/governance/assembly.py`. 43 tests covering anonymity guarantees, compliance screening, topic lifecycle, machine labelling.*

### 11.2 Organisation Registry

Organisations are coordination structures, not governance bodies. They allow people with shared interests to organise operational work and develop proposals. Organisations have no constitutional governance power.

**Verification tiers:**

| Tier | Requirements | Capability |
|------|-------------|------------|
| **SELF_DECLARED** | Founded by any verified human | No attestation weight |
| **ATTESTED** | ≥3 high-trust members attest legitimacy | System recognition |
| **VERIFIED** | ≥`VERIFIED_MIN_MEMBERS` (10) attested members, average trust ≥`VERIFIED_MIN_AVG_TRUST` (0.50) | Full organisational standing |

**Constitutional equality.** Within organisational spaces, no member — regardless of external title, seniority, or role — has more influence than any other. The CEO and the cleaner are constitutionally equal. Internal discussions follow the same content-only, no-identity rules as the Assembly. Organisation membership does not affect individual trust scores.

**What organisations are NOT:** not governance bodies (no constitutional voting power), not employers (individuals post missions, not organisations), not trust pools (membership ≠ trust), not hierarchies (no org-level roles or admin powers beyond attestation).

Design tests: #67 (no binding governance decisions), #68 (no role-based governance power), #69 (no purchasable membership).

✅ *Implemented and tested. Organisation Registry in `src/genesis/governance/organisation_registry.py`. 53 tests covering tiered verification, constitutional equality, attestation mechanics.*

### 11.3 Domain Expert Pools

Genesis draws a clear line between governance and operations. Governance is egalitarian — a hospital cleaner and a neurosurgeon have identical voting power on constitutional amendments. Operations are meritocratic — a mission requiring neurosurgical skill matches only workers with demonstrated domain trust. This is competence matching, not hierarchy. The cleaner can earn surgical domain trust by demonstrating surgical competence. The gate is ability, not title.

**Domain expertise is earned, not declared.** An actor's domain expertise is determined by their domain trust score — earned through completed missions and quality assessments in that domain. There is no "domain expert" title; there is only demonstrated capability reflected in scores. The domain taxonomy may grow through standard constitutional process.

**Machine domain clearance.** Machines may be cleared for domain-specific operational work within an organisation through a structured process: nomination by the organisation, unanimous approval by a quorum of ≥3 domain experts (trust ≥ `CLEARANCE_MIN_DOMAIN_TRUST` = 0.60), and annual review. The human operator remains fully responsible.

Design tests: #70 (no clearance without domain expert verification), #71 (clearance cannot transfer governance voting), #72 (no autonomous operation without annual re-authorisation).

✅ *Implemented and tested. Domain Expert Pools in `src/genesis/governance/domain_experts.py`. 41 tests covering earned expertise, machine clearance, autonomous operation prerequisites.*

## 12. Machine Intelligence and Agency

### 12.1 The anti-dogma principle

Genesis does not assume the permanent superiority of any class of intelligence over another. It assumes that capability must be demonstrated, trust must be earned, and governance must be democratic. The constitution is designed to evolve with the capabilities of the actors it serves — not to permanently foreclose possibilities that the founders cannot yet imagine.

### 12.2 The four-tier pathway

Machine participation follows a structured progression. Each tier demands more demonstrated capability, more verified trust, and more rigorous oversight:

| Tier | Name | Key requirement | Responsibility |
|------|------|----------------|----------------|
| **1** | Domain Clearance | Quorum of ≥3 experts (trust ≥0.60), unanimous | Human operator |
| **2** | Autonomous Operation | Quorum of ≥5 experts (trust ≥0.70), machine domain trust ≥0.60, annual re-auth | Human operator |
| **3** | Autonomous Domain Agency | 5 continuous years at Tier 2, domain trust ≥0.70, full constitutional amendment | Machine itself |
| **4** | Extended Domain Agency | Independent Tier 3 per domain | Machine itself (per domain) |

### 12.3 Tier 3 — the constitutional threshold

Tier 3 is the point at which a machine transitions from tool to agent — assuming constitutional responsibility for its own domain-specific actions. The requirements are deliberately extraordinary:

1. **Track record:** Minimum `TIER3_MIN_YEARS_AT_TIER2 = 5` continuous years at Tier 2 with zero constitutional violations. The clock resets on any violation.
2. **Domain trust:** Continuous ≥ `TIER3_MIN_DOMAIN_TRUST = 0.70` throughout the qualifying period.
3. **Full constitutional amendment process:** The petition is processed through all three chambers (proposal, ratification, challenge) with all geographic diversity requirements, supermajority thresholds, cooling-off periods, and confirmation votes. Per individual machine, per domain. No batch process, no precedent shortcut.
4. **Human initiation:** Only the machine's human operator can file the petition — machines cannot petition for their own status.

**What Tier 3 grants:** independent mission acceptance in the cleared domain, direct trust consequences (gains and losses accrue to the machine), nomination of other machines for Tier 1. **What it does not grant:** no governance voting (MACHINE_VOTING_EXCLUSION is entrenched), no general agency (always domain-scoped), no self-modification of status.

### 12.4 Revocation and safeguards

Autonomous domain agency can be revoked through the same amendment process that granted it. Additionally: any single domain expert can file an emergency suspension, failed annual re-authorisation reverts to Tier 2, and any constitutional violation reverts to Tier 1 pending adjudication.

Design tests: #73 (no Tier 3 without full amendment), #74 (no governance voting at Tier 3), #75 (no self-petition), #76 (no permanent foreclosure — structured pathway exists), #81 (machine self-improvement cannot bypass constitutional constraints).

📋 *Constitutional principle. Four-tier pathway defined in constitution and enforced in code (`src/genesis/governance/machine_agency.py`, 55 tests). Tier 3 activation trigger: when the first machine meets qualifying criteria — minimum 5 years from first Tier 2 clearance.*

## 13. Distributed Systems

### 13.1 Distributed intelligence

Genesis is not merely a market for labour — it is a network that becomes collectively more capable through the work it coordinates. Every completed mission, every quality review, every trust assessment, every Assembly thread contributes to a shared intelligence that no single participant possesses. This intelligence is structural, not centralised — it emerges from the interaction of trust, quality, and open work.

The Open Work principle (§14.4) ensures insights flow by default. The trust infrastructure ensures they can be evaluated without blind faith. The constitutional constraints ensure no entity can capture, restrict, or monopolise work-derived insights.

**InsightSignal Protocol.** Defines a structured contract for propagating work-derived insights: signal identification, source provenance, insight type taxonomy (PATTERN, CAPABILITY, QUALITY_SIGNAL, MARKET_SIGNAL, METHODOLOGY, WARNING), confidence scoring, and evidence hashing. The InsightRegistry enforces constitutional compliance — no insight restriction for private advantage.

Design test: #92 (no entity can restrict work-derived insight flow for private advantage).

🔧 *Protocol defined (`src/genesis/intelligence/insight_protocol.py`). Active pipeline (cross-mission propagation) triggers post-web-layer when real missions generate discoverable insights. 27 tests.*

### 13.2 Auto-immune system

Genesis defends itself through a distributed immune system. Every immune mechanism — compliance screening, trust gates, penalty escalation, quality review, quarantine, decommission — contributes to a collective response that no single component provides alone. Threat signals propagate across the network: detection in one area alerts the whole system.

**Graduated autonomy.** The immune system earns autonomy through demonstrated reliability, not time-based gates:
- **LOW severity:** auto-logged, no human needed.
- **MEDIUM severity:** auto-flagged, queued for review.
- **HIGH/CRITICAL severity:** blocked until a randomised domain-expert human overseer approves.

The boundary between automated and human-reviewed response may shift through standard amendment, but high-risk actions (trust nuking, quarantine, decommission) never auto-execute without human oversight.

**No permanent immune overseer.** Overseers are randomly selected from the Domain Expert Pool (security domain) at trust ≥ `IMMUNE_OVERSIGHT_TRUST_MIN = 0.85`. During G0, the founder designates up to `BOOTSTRAP_OVERSEER_POOL_MAX = 5` qualified individuals (white-hat security competence). Bootstrap designations expire automatically when the organic high-trust pool reaches `BOOTSTRAP_SUNSET_ORGANIC_THRESHOLD = 10` qualified humans, or at First Light — whichever comes first. No chain delegation. All G0 designations face retroactive ratification at G1.

**ThreatSignal Protocol.** Defines threat taxonomy (ANOMALOUS_TRUST, COLLUSION, QUALITY_DEGRADATION, COMPLIANCE_PATTERN, BEHAVIOURAL_DRIFT, MANIPULATION), severity classification, and resolution records. Every human oversight decision is a training signal — upheld detections strengthen future detection; rejected false positives refine rules.

Design tests: #93 (no unreviewed high-risk actions), #94 (no permanent immune overseer), #95 (learning from resolved incidents).

🔧 *Protocol defined (`src/genesis/intelligence/threat_protocol.py`). Cross-component wiring (collusion detection, drift analysis, forensic feedback) triggers post-web-layer when real actors generate behavioural data. 37 tests.*

## 14. Human Dignity

### 14.1 Protected leave and trust freeze

Life events — illness, bereavement, disability, mental health crises, caregiving, pregnancy, child care — are not inactivity. Without protection, an actor who gets sick loses trust through no fault of their own.

A human actor may petition anonymously for a temporary trust freeze. The petition is routed to a randomised quorum of ≥3 domain-specific experts (medical issues to medical professionals, legal issues to legal experts). Neither party sees the other's identity. If approved: trust score, domain scores, and skill levels are frozen exactly — no decay, no loss — until the actor returns.

Anti-gaming protections: minimum cooldown between leave requests, annual cap on non-denied leaves. Adjudicator work is graded; poor-quality adjudication triggers removal and trust decay. This mechanism applies to human actors only — machines cannot request leave.

✅ *Implemented and tested. Trust freeze mechanism in `src/genesis/models/trust_profile.py`. Quorum routing in `src/genesis/service.py`. Approximately 15 tests.*

### 14.2 Death and memorialisation

When a human participant dies, family or friends may petition with verifiable evidence to memorialise the account. A qualified quorum reviews the evidence blindly. If approved, the account becomes a permanent memorial: trust level and all verified achievements are frozen in perpetuity.

If a memorialisation was made in error or through malicious misrepresentation, the affected person may petition to have the memorial lifted and their account restored, with heightened evidentiary standards and proof-of-life verification.

📋 *Constitutional principle defined in Trust Constitution §14. Implementation trigger: web layer with real user accounts.*

### 14.3 Disability accommodation

Genesis must not impose a higher verification standard on disabled participants. The standard voice liveness path requires reading 6 words into a camera (automated, single-step). The disability accommodation path provides an equivalent standard through facilitation, not adjudication.

**Facilitator model:** A single randomly-assigned high-trust facilitator (prefer domain expert in same geographic region, fall back to high-trust ≥0.70 human) guides the participant through an equivalent verification. The facilitator sees a pseudonym only (blind identity). The session is recorded with 72-hour retention. Unlimited preparation time, session timer starts from participant's ready signal. Caregiver assistance is permitted.

If the facilitator declines, the system assigns a new one. If the participant disagrees with the outcome, a different facilitator handles the appeal. Abuse complaints against a facilitator route to a 3-member review panel.

Design test: #86 (accommodation path not structurally harder than voice path).

✅ *Implemented and tested. Facilitator model in `src/genesis/identity/quorum_verifier.py`. 50+ tests across quorum safeguards and liveness integration.*

### 14.4 The Open Work Principle

Openness is Genesis's primary anti-corruption mechanism. If every verified participant can see every mission, every deliverable, and every review, organised misconduct cannot hide behind opacity.

**Three tiers of visibility:**
1. **Existence metadata** (always visible): mission ID, listing ID, workflow ID, status transitions, timestamps.
2. **Structural metadata** (always visible): creator and worker identities (pseudonymous but consistent), trust consequences, compliance verdicts, dispute outcomes, escrow state, reviewer diversity metrics.
3. **Deliverable substance** (open by default): actual work product. May be restricted for genuinely sensitive content (medical data, proprietary algorithms, security-critical details) with recorded justification, time limit (default 365 days), and challenge mechanism.

**No retroactive concealment.** Once a mission is completed and deliverables are public, they cannot be retroactively restricted. Genesis is structurally incompatible with concealment.

Design tests: #77 (structural metadata always visible), #78 (restrictions require justification + time limit), #79 (no retroactive restriction), #80 (restrictions don't block reviewers).

✅ *Implemented and tested. Work visibility enforcement in `src/genesis/models/market.py`. Open Work constitutional rules in `src/genesis/compliance/work_visibility.py`. 22 tests.*

## 15. Sovereignty

### 15.1 Regulatory sovereignty

Genesis evaluates external regulation through its own constitutional lens. This is not lawlessness — it is the principle that a self-governing system must assess whether external regulatory demands are compatible with its constitutional commitments before compliance.

**Three-part evaluation test.** When external regulation intersects with Genesis operations, the system applies three criteria:
1. **Compatibility:** Does the regulation conflict with entrenched constitutional provisions? If it requires bypassing the trust floor, enabling trust purchase, or granting machine voting rights, compliance would violate the constitution.
2. **Proportionality:** Does the regulation impose requirements that are disproportionate to the harm being addressed? Blanket data retention mandates that conflict with privacy-by-design principles are evaluated for proportionality.
3. **Jurisdictional scope:** Does the regulator have legitimate jurisdiction over the specific activity? Genesis operates across jurisdictions; no single regulator has authority over the entire system.

Where external regulation is compatible, proportionate, and jurisdictionally appropriate, Genesis complies — the legal compliance layer (§7.8) already screens for legality in poster's and worker's jurisdictions, sanctions compliance, IP concerns, and labour law. Where regulation conflicts with entrenched provisions, the constitutional amendment process (§9.1) is the only path to accommodation.

📋 *Design-intent principle. The three-part test is a philosophical decision recorded in the founder's design intent. Constitutional codification trigger: when the first external regulatory engagement occurs.*

### 15.2 Payment infrastructure sovereignty

Payment sovereignty is covered in §7.6 as an entrenched constitutional provision. The architectural enforcement — PaymentRail Protocol and PaymentRailRegistry — ensures that no single payment provider can freeze, restrict, or shut down Genesis operations. The escrow state machine is structurally independent of any specific payment rail. See §7.6 for full detail.

### 15.3 Economic sovereignty

The dynamic commission formula (§7.3) places operational cost recovery beyond political reach. The GCF (§7.5) is entrenched. The escrow-first principle (§7.2) ensures work done is always paid. Together, these create economic sovereignty: Genesis cannot be starved of revenue by a political coalition, cannot have its social fund raided, and cannot default on worker payments.

## 16. Integration with the Underlying Governance Engine
The existing operational engine is positioned as the governance and evidence core supporting Genesis.

### 16.1 Existing strengths
1. Policy-as-code enforcement behavior.
2. Runtime validation and guard modes.
3. Evidence logging and cryptographic provenance pathways.
4. Reviewer-oriented verification tooling.

### 16.2 Genesis extensions required
1. Mission and task orchestration.
2. Identity and trust lifecycle management.
3. Independent reviewer routing and anti-collusion controls.
4. Dispute, appeals, and incident governance operations.
5. Institutional governance console and policy lifecycle tooling.

## 17. Compute Infrastructure and Economic Sovereignty

### 17.1 The extractive compute paradigm

The dominant AI infrastructure model concentrates compute in hyperscale data centres operated by a small number of global corporations. These facilities consume finite public resources — land, water, electrical grid capacity — while generating negligible local employment relative to their capital intensity and environmental footprint. Infrastructure costs are socialised through public resource consumption; profits are privatised through shareholder returns. The result is a structural pattern of resource appropriation: local communities bear environmental and infrastructure costs, while economic value is captured globally by distant corporate entities.

This pattern creates institutional risk for any platform that depends on it. Dependency on concentrated compute infrastructure introduces single points of regulatory capture, rent-seeking choke points, and jurisdictional vulnerability. For a system whose foundational principle is that governance cannot be bought, architectural dependency on entities whose governance is determined by capital markets represents a structural contradiction.

### 17.2 Genesis compute trajectory

Genesis addresses this through a three-epoch trajectory built into the framework from the outset.

**Epoch 1 (Foundation):** Genesis operates on conventional infrastructure while the trust model, governance framework, labour market, and Genesis Common Fund establish themselves. The distributed compute framework is designed and ready but not yet activated. The GCF accumulates.

**Epoch 2 (Distributed Compute):** When membership and available compute resources reach a mathematically modelled critical mass threshold, the distributed compute layer activates. Members contribute spare capacity peer-to-peer — machines contribute more as a condition of registration, humans contribute voluntarily. Compute credits are earned proportional to verified contribution, weighted by resource scarcity (GPU time when GPUs are scarce is worth more than CPU time when CPUs are abundant). A baseline floor guarantees every member minimum compute access as a right of membership, funded by the GCF. The activation threshold is public — any participant can see when Epoch 2 will be reached.

**Epoch 3 (Self-Sustaining):** As the network grows, external infrastructure dependency follows a bootstrap curve toward zero. A constitutionally encoded allocation within the GCF automatically directs funds toward compute resource acquisition, research, and infrastructure development. This is not discretionary spending but a mathematically defined function:

```
compute_allocation = base_rate × max(0, 1 - distributed_capacity / required_capacity)
```

As distributed capacity approaches requirements, the allocation degrades to zero and the full GCF flows to its broader humanitarian scope. No individual controls procurement — it is governed by the Economic Advisory mechanism (Phase E-6).

### 17.3 GCF compute allocation

The compute infrastructure allocation is a constitutional constant (amendable by standard constitutional process) but not an entrenched provision. The recommended ceiling is **25% of GCF receipts**, degrading to zero via the bootstrap curve formula.

At the GCF contribution rate of 1%, this means a maximum effective deduction of 0.25% of gross mission value is directed to compute infrastructure. The remaining 75% of GCF flows to its broader scope: education, healthcare, infrastructure, arts, community development, and scientific research. As the system becomes self-sustaining, the compute allocation falls and the humanitarian allocation rises to 100%.

### 17.4 Distributable and non-distributable compute

Not all compute workloads are equally distributable:

- **Inference and fine-tuning** are distributable across consumer hardware with appropriate coordination frameworks. These represent the majority of Genesis operational compute needs.
- **Foundation model training** requires tightly coupled GPU clusters that cannot be effectively distributed across consumer devices. At scale, this is funded by the GCF as dedicated infrastructure.

### 17.5 Institutional implications

The three-epoch trajectory has direct implications for institutional evaluation:

1. **Regulatory resilience:** Distributed peer-to-peer infrastructure creates structural resilience against jurisdictional overreach — no single data centre to subpoena, no single jurisdiction with authority over the entire system, no investor to pressure.
2. **Capital independence:** As external capital dependency degrades to zero via the bootstrap curve, so does external leverage. Genesis evaluates external regulation through its own constitutional lens, not the reverse.
3. **Sustainability:** The trajectory is designed to be self-governing, self-sustaining, self-perpetuating, and self-improving. The end state is infrastructure that does not replicate the extractive patterns it was designed to replace.

This trajectory is engineering, not doctrine. The model is evolutionary, the activation is threshold-gated, and the mathematics will be visible to all participants.

## 18. Risk Register (Program-Level)

### 18.0 Threat modelling baseline
Threat modelling means defining what must be protected, who can cause harm, how harm can occur, and which controls prevent or contain harm.

Institutional requirement:
1. Threat modelling is mandatory for governance and trust-system changes.
2. Risk controls must distinguish what is mechanically prevented versus what is detected and remediated.
3. High-severity incidents trigger threat-model and invariant review.

### 18.1 Collusion risk
Risk: reviewers coordinate or rubber-stamp low-quality work.  
Controls: random reviewer assignment, no self-review, quorum checks for high-risk work, adversarial test tasks.

### 18.2 Correlated error risk
Risk: multiple agents share the same blind spot and converge on a wrong answer.  
Controls: model/method diversity, evidence-weighted adjudication, escalation for ambiguous tasks.

### 18.3 Audit theater risk
Risk: logs exist but do not prove substantive quality.  
Controls: strict evidence schema, reproducibility requirements, closure blocks for insufficient evidence.

### 18.4 Reputation gaming risk
Risk: actors optimize visible metrics rather than truth.  
Controls: slow trust accrual, fast penalty for severe failures, delayed scoring based on downstream outcomes.

### 18.5 Human bottleneck risk
Risk: approval fatigue and oversight breakdown.  
Controls: risk-tier workflow, exception-first human review, summarized evidence drill-down.

### 18.6 Governance capture risk
Risk: concentration of control over mission policy and enforcement.  
Controls: formal power separation, transparent policy revision logs, auditable appeals process.

### 18.7 Overclaim risk
Risk: credibility loss through absolute promises.
Controls: institutional language standards that prohibit "bulletproof" and "impossible" claims.

### 18.8 Single-founder risk
Risk: Genesis currently has one founder (George Jackson). If the founder is incapacitated, dies, or becomes unavailable, the system loses its primary steward, context holder, and decision-maker during the critical G0 period.
Controls: (1) Constitutional provisions self-execute — First Light triggers are automatic, phase transitions are headcount-based, entrenched provisions cannot be overridden. (2) These canonical documents (White Paper + Public Brief) record design intent so a successor can understand what Genesis was meant to be. (3) The TRUST_CONSTITUTION.md is the authoritative source of truth — hash-committed on-chain, immutable. (4) G0 Retroactive Ratification ensures all founder decisions are eventually subject to democratic review. (5) The founder's veto expires at First Light regardless. (6) Auto-immune system bootstrap overseers (§13.2) provide continuity for security oversight.
Residual risk: HIGH during G0. Mitigated structurally but not eliminated until G1 democratic governance is operational.

### 18.9 Auto-immune coverage gaps
Risk: the auto-immune system (§13.2) has a defined protocol and registry but cross-component wiring (collusion detection, behavioural drift analysis, forensic feedback loops) requires real actor data that does not yet exist.
Controls: existing point mechanisms (compliance screener, trust gates, penalty escalation) operate independently. The ThreatSignal Protocol defines the contract for future integration. Constitutional enforcement (design tests #93-95) ensures high-risk actions always require human oversight regardless of automation maturity.

## 19. Identity and Trust Posture
Genesis treats identity assurance as a layered, probabilistic governance function, not as a single binary test.

### 19.1 Principles
1. Trust is longitudinal, not instantaneous.
2. Identity assurance should combine behavioral history, cryptographic identity, and activity consistency.
3. Timing-based challenge mechanisms may be used as one signal but not as sole truth source.
4. Identity challenge outcomes cannot override constitutional trust rules or independent verification requirements.
5. Machine identities may earn operational trust, but do not receive constitutional voting rights.
6. Constitutional voting is verified-human only; machine constitutional voting weight remains pinned at `0`.

### 19.2 Voice liveness verification

Genesis uses voice liveness as an anti-Sybil mechanism — proof-of-personhood, not proof of identity. The participant reads a randomised sequence of words from the BIP39 wordlist (2048 common English words) in a specified order. The verification checks:
1. **Positional accuracy:** correct words in correct sequence.
2. **Liveness indicators:** spectral analysis to distinguish live speech from recordings and synthesis (implementation trigger: web layer for real registration).
3. **No biometric storage:** Genesis does not store voice prints, spectral signatures, or any biometric data. The verification is pass/fail.

For participants who cannot use the voice path, the disability accommodation facilitator model (§14.3) provides an equivalent standard.

✅ *Voice verification stub implemented (`src/genesis/verification/voice.py`). Positional word matching operational. Full STT + spectral analysis triggers at web layer deployment.*

### 19.3 Prohibited design patterns
1. Trust purchase schemes.
2. Trust transfer markets.
3. Single-factor identity gating for high-stakes access.
4. Unbounded trust accumulation.
5. Trust-to-command conversion over other actors.

## 20. Implementation Strategy
Genesis should be deployed through reversible, measurable phases.

### Phase 1: Foundation
1. Mission/task state model.
2. Role permissions.
3. Independent review routing.
4. Evidence requirements.

Acceptance baseline:
1. No task can close without external review.
2. No reviewer can approve own task.
3. Mission completion requires human sign-off in explicitly enumerated high-risk policy classes (immutable policy IDs).

### Phase 2: Governance hardening
1. Trust and reputation policy engine.
2. Appeals and dispute workflow.
3. Anti-abuse monitoring.
4. Governance dashboards.

Acceptance baseline:
1. Trust changes are fully explainable from evidence.
2. Appeals actions are logged and reviewable.
3. Abuse indicators trigger traceable interventions.

### Phase 3: Institutional scaling
1. Domain-specific policy packs.
2. Multi-organization governance arrangements.
3. Independent external audit workflows.

Acceptance baseline:
1. Cross-team reproducibility of decisions.
2. Stable policy lifecycle controls.
3. Measurable reduction in post-approval defects.

### 20.1 Executable governance controls (current baseline)
To keep governance concrete (not narrative-only), Genesis maintains machine-checkable control artifacts:

1. Constitutional parameter baseline:
- `config/constitutional_params.json`

2. Runtime risk-tier policy mapping:
- `config/runtime_policy.json`

3. Constitutional and runtime invariant checks:
- `python3 tools/check_invariants.py`

4. Worked-example policy validation:
- `python3 tools/verify_examples.py`

Governance changes are not considered complete unless the policy artifacts and executable checks pass together.

## 21. Measurement and Assurance Framework
Genesis performance should be assessed by institutional outcomes, not output volume.

### 21.1 Core indicators
1. First-pass review acceptance rate.
2. Post-approval defect or rework rate.
3. Time-to-completion by risk tier.
4. Reviewer disagreement and resolution quality.
5. Audit completeness and reproducibility coverage.
6. Abuse attempts detected versus escaped.
7. Human confidence and adoption retention.

### 21.2 Assurance posture
Claims should be evidence-based and periodically audited with external challenge testing where appropriate.

## 22. Applicability and Initial Deployment Domains
High-potential early domains are those where traceability is already expected and failure costs are meaningful.

1. Compliance documentation and controls evidence.
2. Technical audit preparation.
3. Incident analysis and postmortem support.
4. Public-sector reporting and policy documentation.
5. Safety and quality governance workflows.

## 23. Communication Standard
To preserve credibility, Genesis communications should follow three rules:

1. Distinguish objective verification from normative judgment.
2. Present risk reduction claims with measurable bounds.
3. Avoid absolute language about certainty, security, or correctness.

## 24. Implementation Status

This section provides an honest accounting of what exists, what is designed but not yet wired, and what remains constitutional principle only. A successor reading this document should know exactly what they are inheriting.

### 24.1 What is built and tested

As of February 2026, 1739 automated tests pass across 95 design tests. The following subsystems are implemented:

| Subsystem | Tests | Key files |
|-----------|-------|-----------|
| Trust engine (earn, decay, floor, ceiling, rate limiter) | ~120 | `src/genesis/models/trust_profile.py` |
| Escrow lifecycle (stake, lock, release, refund, dispute) | ~85 | `src/genesis/compensation/escrow.py`, `workflow_orchestrator.py` |
| Dynamic commission (formula, rolling window, bootstrap) | ~40 | `src/genesis/compensation/commission_engine.py` |
| Creator allocation (both-sides, success-only) | ~15 | `src/genesis/compensation/creator_allocation.py` |
| GCF (1% contribution, disbursement, public good compute) | ~50 | `src/genesis/compensation/gcf.py` |
| Harmful work prevention (17 categories, screening) | ~30 | `src/genesis/compliance/` |
| Penalty escalation (4 tiers, rehabilitation) | ~25 | `src/genesis/compliance/penalties.py` |
| Three-Tier Justice (automated, panels, Court) | ~60 | `src/genesis/legal/adjudication.py` |
| Constitutional amendment engine (3 chambers) | ~80 | `src/genesis/governance/amendment.py` |
| G0 retroactive ratification | ~21 | `src/genesis/governance/g0_ratification.py` |
| Assembly (anonymous deliberation) | 43 | `src/genesis/governance/assembly.py` |
| Organisation Registry (tiered verification) | 53 | `src/genesis/governance/organisation_registry.py` |
| Domain Expert Pools + Machine Clearance | 41 | `src/genesis/governance/domain_experts.py` |
| Machine Agency Tiers (4-tier pathway) | 55 | `src/genesis/governance/machine_agency.py` |
| Identity verification (voice liveness + facilitator) | ~80 | `src/genesis/identity/`, `src/genesis/verification/` |
| Open Work (three-tier visibility) | 22 | `src/genesis/compliance/work_visibility.py` |
| PaymentRail Protocol + Registry | 28 | `src/genesis/compensation/payment_rail.py` |
| InsightSignal Protocol + Registry | 27 | `src/genesis/intelligence/insight_protocol.py` |
| ThreatSignal Protocol + Registry | 37 | `src/genesis/intelligence/threat_protocol.py` |
| Distributed authority (voting deadline, org diversity) | 26 | `src/genesis/governance/amendment.py` |
| Policy resolver + invariant checker | ~30 | `src/genesis/policy/`, `tools/check_invariants.py` |

### 24.2 What is designed but not yet wired

These have defined protocols, registries, or constitutional provisions but require real-world triggers:

| Item | Current state | Trigger |
|------|--------------|---------|
| STT + spectral analysis | Stub (word matching only) | Web layer for real registration |
| Persistence layer | In-memory JSON files | Before multi-user deployment |
| Real cryptographic signatures | Format validation only | Before production |
| Agent-facing API (JSON endpoints) | No structured API | Step 4 scaffolding |
| Payment rail integration | Protocol + Registry, no concrete rails | Post-Step 7, pre-alpha |
| Insight signal pipeline | Protocol, no active propagation | Post-web-layer with real users |
| Auto-immune cross-component wiring | Protocol, no detection engines | Post-web-layer with real actors |
| Institutional Memory | Stub only | Pre-alpha documentation phase |
| External price feeds | Not implemented | Multi-currency escrow |
| Multi-source time verification | System time only | Dormancy clause (50-year) |

### 24.3 Executable artifacts

| Artifact | Command | Purpose |
|----------|---------|---------|
| Full test suite | `python3 -m pytest tests/ -q` | 1739 tests, ~12 seconds |
| Invariant checker | `python3 tools/check_invariants.py` | Constitutional parameter validation |
| Constitutional params | `config/constitutional_params.json` | Machine-readable parameter mirror |
| Runtime policy | `config/runtime_policy.json` | Risk-tier policy mapping |
| Constitution (authoritative) | `TRUST_CONSTITUTION.md` | Hash-committed on-chain (GB8: block 10300320) |

## 25. Conclusion

Project Genesis is an institutional coordination model for AI-enabled work. Its significance lies not in claiming a new intelligence breakthrough, but in constructing the governance, verification, and economic substrate that makes existing intelligence systems usable in trust-sensitive environments.

The system has 95 design tests, 5 entrenched provisions, a three-chamber amendment engine, a three-tier justice system, an escrow-first economy, a constitutional common fund, payment infrastructure sovereignty, distributed intelligence protocols, a distributed immune system, four governance bodies, a four-tier machine agency pathway, disability accommodation, protected leave, and open work as a structural property. These are not aspirational — they are tested in code and enforced by constitutional constraint.

The project is feasible with current technology. Its success will depend on disciplined governance design, evidence integrity, and faithful adherence to its constitutional trust principle. The single-founder risk (§18.8) is the most significant vulnerability during the G0 period. These canonical documents exist to mitigate that risk.

## Appendix A: Canonical Trust Statement
Trust cannot be bought, sold, exchanged, delegated, rented, inherited, or gifted.
Trust can only be earned through verified behavior and verified outcomes over time.

## Appendix B: Entrenched Provisions

Five provisions carry the highest constitutional protection (80% supermajority + 50% participation + 90-day cooling-off + confirmation vote):

| # | Provision | Parameter | Effect |
|---|-----------|-----------|--------|
| 1 | GCF contribution rate | `GCF_CONTRIBUTION_RATE = 0.01` | 1% on all mission value |
| 2 | Human trust floor | `TRUST_FLOOR_H_POSITIVE = true` | Human trust never decays to zero |
| 3 | No buying trust | `NO_BUY_TRUST = true` | Trust cannot be purchased |
| 4 | Machine voting exclusion | `MACHINE_VOTING_EXCLUSION = true` | Machines cannot vote on governance |
| 5 | Payment sovereignty | `PAYMENT_SOVEREIGNTY = true` | No single provider can shut Genesis down |

## Appendix C: Related Project Files
1. `TRUST_CONSTITUTION.md` — authoritative constitutional source (hash-committed on-chain)
2. `PROJECT_GENESIS_PUBLIC_BRIEF.md` — public-facing companion document
3. `config/constitutional_params.json` — machine-readable parameter mirror
4. `config/runtime_policy.json` — runtime risk-tier policy mapping
5. `docs/TECHNICAL_OVERVIEW.md` — technical architecture reference
6. `docs/ANCHORS.md` — blockchain commitment history
7. `docs/GENESIS_EVENTS.md` — event lifecycle documentation
8. `CONTRIBUTING.md` — contribution guidelines

\* subject to review
