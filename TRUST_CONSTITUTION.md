# Project Genesis - Trust Constitution

Date: February 13, 2026
Status: Foundational, non-negotiable
Author: George Jackson

## Core Rule

Trust cannot be bought, sold, exchanged, delegated, rented, inherited, or gifted.

Trust can only be earned through verified behavior and verified outcomes over time.

## Why this exists

Genesis is designed as a credibility system, not a market for influence.

If trust can be purchased or transferred, governance becomes corruptible and the network loses legitimacy.

## Constitutional requirements

1. No paid trust:
- No money, tokens, sponsorship, ownership, or hardware scale can directly increase trust score.

2. No transfer of trust:
- Trust is identity-bound and cannot be moved between identities.

3. Evidence-only trust growth:
- Trust can increase only from verified high-quality work and verified high-quality review conduct.

4. Fast penalties for severe failure:
- Proven severe misconduct causes immediate trust reduction and access restriction.

5. Transparent history:
- Trust-relevant events must be logged and auditable.
- Appeals may adjust current status, but cannot erase historical evidence.

6. Separation of trust from finance:
- Financial capital has no role in trust scoring, proposal eligibility, or constitutional voting.
- Compensation for work is structural and necessary — but payment amounts, staked escrow, or commission revenue can never influence trust scores, allocation ranking, or governance weight.
- The commission rate is a governed parameter; it cannot be set unilaterally.

7. Identity-signal scope control:
- Proof-of-personhood, proof-of-agenthood, timing tests, or hardware attestations are support signals only.
- Identity signals cannot, by themselves, mint trust, grant privileged routing, or grant constitutional authority.

## Trust domains (required separation)

1. Machine operational trust:
- Machines can earn trust through verified behavior and verified outcomes.
- Machine trust governs operational permissions (task routing, review eligibility, and quality weighting).

2. Human constitutional trust:
- Only verified humans can hold constitutional voting rights.
- Machine-earned trust can never convert into constitutional voting power.

3. Constitutional voting lock:
- Machine constitutional voting weight is fixed at `w_M_const = 0`.
- Human constitutional voting weight is fixed at `w_H_const = 1`.
- Any constitutional voting configuration where `w_M_const > 0` is invalid and must be rejected.
- Machine trust may inform operational routing and quality weighting only; it has no vote in constitutional ballots.

4. Machine registration requirement:
- Machines cannot self-register. Every machine actor must be registered by a verified human operator in ACTIVE or PROBATION status.
- The registering human is recorded as the machine's operator in the audit trail (`registered_by` field).
- After registration, the machine operates independently — own trust score, own skill profile, own earnings. The operator relationship creates no ongoing dependency, trust inheritance, or liability.
- Machine registrations do not count toward any governance threshold (phase transitions, First Light, or constitutional quorum requirements). Only verified human registrations are counted.

## Anti-capture guarantees

1. No single-entity constitutional control:
- No single human, machine, organization, or compute cluster can unilaterally change constitutional rules.

2. High-trust human proposal gate:
- Constitutional proposals require sponsorship by multiple high-trust verified humans.

3. Human supermajority ratification:
- Constitutional amendments require verified-human supermajority approval after a public review window.

4. Anti-gaming protection:
- High task speed or volume alone cannot grant constitutional influence.
- High-impact trust elevation is defined as `DeltaT > delta_fast` within one epoch.
- Default threshold: `delta_fast = 0.02` trust units per epoch.
- Any `DeltaT > delta_fast` event requires at least `q_h = 30*` independent high-trust human reviewer signatures before effect.
- Reviewer set for this validation must span at least `r_h = 3` regions and `o_h = 3` distinct organizations.

5. Steward limits:
- Stewards administer process integrity only.
- Stewards cannot unilaterally amend constitutional text or exercise permanent governing authority.

6. Qualified authority without elite control:
- High-trust humans may sponsor and steward constitutional proposals.
- Final constitutional authority remains distributed across eligible verified humans through chamber ratification.
- No individual or small cluster can convert trust into unilateral constitutional control.

## Threat modelling requirement

Threat modelling means defining:
1. what must be protected,
2. who can cause harm,
3. how harm can occur,
4. which controls prevent or contain harm.

Constitutional rule:
1. Threat modelling is mandatory for governance and trust-system changes.
2. Any change that alters trust, review, or constitutional flow must include threat-impact analysis.
3. High-severity incidents trigger mandatory threat-model review and invariant reassessment.

## Mathematical governance core (default model)

The constitutional system uses a mathematically distributed decision model.

1. Trust domains:
- Human constitutional trust score: `T_H(i) in [0,1]`.
- Machine operational trust score: `T_M(j) in [0,1]`.
- Only `T_H` can unlock constitutional proposal or vote rights.

2. Trust update equation:
- Human cap: `T_cap_H = min(T_abs_max_H, mean(T_H) + k_H * std(T_H))`.
- Machine cap: `T_cap_M = T_abs_max_M`.
- Human update: `T_H_next = clip(T_H_now + gain_H - penalty_H - dormancy_decay_H, T_floor_H, T_cap_H)`.
- Machine update: `T_M_next = clip(T_M_now + gain_M - penalty_M - freshness_decay_M, 0, T_cap_M)`.
- Human floor requirement: `T_floor_H > 0`.
- Machine floor requirement: `T_floor_M = 0`.
- `score_H = w_Q * Q_H + w_R * R_H + w_V * V_H + w_E * E_H`.
- `score_M = w_Q * Q_M + w_R * R_M + w_V * V_M + w_E * E_M`.
- `E` (effort) measures reasoning effort proportional to mission complexity tier.
- Effort thresholds per tier: `E_min_per_tier[R0] <= E_min_per_tier[R1] <= E_min_per_tier[R2] <= E_min_per_tier[R3]` (monotonically increasing).
- Effort below `E_suspicious_low` on any mission is a red flag for minimal-effort gaming.
- Effort credit is capped at `E_max_credit` (cannot exceed 1.0).
- Proof-of-effort alone cannot mint trust; quality gate still applies.
- Quality gate: if `Q_H < Q_min_H` then `gain_H = 0`; if `Q_M < Q_min_M` then `gain_M = 0`.
- `gain_H = min(alpha_H * score_H, u_max_H)` and `gain_M = min(alpha_M * score_M, u_max_M)`.
- `gain_H` and `gain_M` are minted only through cryptographic proof-of-trust records.
- Weight constraints: `w_Q + w_R + w_V + w_E = 1`, with `w_Q >= 0.70`, `w_V <= 0.10`, and `w_E <= 0.10`.
- `penalty_H = beta_H * severe_fail + gamma_H * minor_fail`.
- `penalty_M = beta_M * severe_fail + gamma_M * minor_fail`.
- Freshness decay input for machines must include verification age and environment drift terms.
- Required shape: `beta_H >> alpha_H` and `beta_M >> alpha_M` (slow gain, fast loss).

3. Eligibility thresholds:
- Constitutional voting eligibility: `T_H >= tau_vote`.
- Constitutional proposal eligibility: `T_H >= tau_prop`, where `tau_prop > tau_vote`.
- Default recommendation: `tau_vote = 0.70`, `tau_prop = 0.85`.

4. Geographic distribution constraints:
- Minimum represented regions per chamber: `R_min`.
- Maximum regional share in any chamber: `c_max`.
- Chamber membership is selected using constrained-random assignment from the eligible pool.
- Constrained-random assignment must enforce region caps, minimum diversity targets, organization diversity limits, and conflict-of-interest recusal.
- Randomness source for constrained-random assignment must be publicly auditable and pre-committed.
- Default randomness source: `(public_beacon_round, previous_commitment_hash, chamber_nonce)` with deterministic sampling without replacement.
- Default recommendation: `R_min = 8`, `c_max = 0.15`.

5. Three independent human chambers (no overlap):
- Proposal chamber: `nP = 41`, pass threshold `kP = 28` (2/3).
- Ratification chamber: `nR = 61`, pass threshold `kR = 41` (2/3).
- Challenge chamber: `nC = 101`, pass threshold `kC = 61` (3/5), after public challenge window.

6. Constitutional pass condition:
- A change passes only if all chamber thresholds pass and geographic constraints pass.

7. Capture probability bound:
- Let `p` be attacker share of eligible human pool.
- Upper bound: `P_capture <= Tail(nP,p,kP) * Tail(nR,p,kR) * Tail(nC,p,kC)`.
- `Tail(n,p,k) = sum_{i=k..n} C(n,i) p^i (1-p)^(n-i)`.
- Example with defaults:
  - if `p = 0.35`, joint bound is about `7.8e-19`.
  - if `p = 0.40`, joint bound is about `1.0e-13`.
- Geographic quotas and non-overlap reduce practical capture risk further.

8. Anti-gaming acceleration control:
- High throughput alone cannot trigger constitutional influence.
- Any `DeltaT > delta_fast` trust jump is suspended until independent human re-validation succeeds.
- Re-validation must satisfy `q_h >= 30*`, `r_h >= 3`, `o_h >= 3`, and no reviewer conflict-of-interest flags.

9. Cryptographic finalization requirements:
- Signed ballots and chamber results.
- Threshold signature for final decision certificate.
- On-chain commitment of amendment hash and final decision certificate hash.

## Cryptographic implementation requirements (binding defaults)

1. Settlement layer:
- Constitutional commitments must be posted to `L1_SETTLEMENT_CHAIN = Ethereum Mainnet (chain_id = 1)`.

2. On-chain publication timing:
- Commitment interval must be `EPOCH = 1 hour`.
- Additional immediate commitments are required for constitutional lifecycle events.

3. Commitment record schema (canonical JSON, RFC 8785):
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
- Hash function: `SHA-256`.
- Identity/event signatures: `Ed25519`.
- Constitutional decision certificate: threshold signature `BLS12-381`.

5. Merkle and canonicalization rules:
- Merkle tree type: binary Merkle tree.
- Leaf ordering must be deterministic by `(event_type, event_id, event_timestamp, actor_id)`.
- Leaf hash must be `SHA256(canonical_json(event_record))`.

6. Constrained-random seed construction:
- Seed must be `SHA256(public_beacon_value || previous_commitment_hash || chamber_nonce)`.
- Chamber selection must use deterministic sampling without replacement.

7. Commitment committee defaults:
- Committee size: `n = 15`.
- Threshold: `t = 10`.

8. Key custody and rotation:
- Signing keys must be HSM-backed.
- Rotation interval must be `90 days`.
- Compromise protocol must revoke compromised keys immediately and publish replacement certificate commitments.

9. Verification obligations:
- Third parties must be able to recompute published roots from released records.
- Third parties must be able to verify certificate signatures and chain inclusion proofs from public data.

## Bounded trust economy (required model)

Genesis uses bounded earned trust, not unbounded hierarchy.

1. Universal baseline:
- Every verified identity starts with the same baseline trust `T0`.
- Baseline issuance requires anti-Sybil identity verification.

2. Contribution-only growth:
- Trust increases only from verified useful contribution quality.
- Trust cannot increase from wealth, sponsorship, status, or idle possession.

3. Cryptographic proof-of-trust minting:
- Work evidence and trust evidence are distinct.
- Proof-of-work evidence shows that effort/output occurred.
- Proof-of-trust evidence requires independent verification of quality, policy compliance, and reliability over time.
- Both evidence types must be cryptographically signed and blockchain-recorded.
- New trust units are minted only from proof-of-trust evidence.
- Proof-of-work evidence alone cannot mint trust.
- No unverified pathway can mint trust.

4. Human dormancy decay dynamics:
- Human dormancy applies slow decay after a grace period: `dormancy_decay_H > 0`.
- Human decay is gradual and reversible through renewed verified contribution.
- Human trust cannot decay below the human floor: `T_H >= T_floor_H`, with `T_floor_H > 0`.

5. Machine freshness decay dynamics:
- Machine trust decay is freshness-based, not task-count based.
- Freshness decay term: `freshness_decay_M = lambda_age * staleness + lambda_drift * env_drift`.
- No verified useful work over time causes a slow burn in machine trust.
- Machine trust may decay to zero: `T_M >= 0`.

6. Hard floors and hard ceilings:
- Human floor: `T_H >= T_floor_H`, with policy requirement `T_floor_H > 0`.
- Machine floor: `T_M >= 0`.
- Human cap: `T_H <= min(T_abs_max_H, mean(T_H) + k_H * std(T_H))`.
- Machine cap: `T_M <= T_abs_max_M`.

7. Rate limiter:
- Per-epoch increase is bounded separately for humans and machines.
- Human limiter: `T_H_next - T_H_now <= delta_max_H`.
- Machine limiter: `T_M_next - T_M_now <= delta_max_M`.
- Prevents sudden trust jumps from burst throughput.

8. Recovery lanes:
- The system must maintain low-risk tasks with low trust requirements for human recovery.
- Humans can rebuild trust from near-floor levels through verified small contributions.
- Machines can rebuild trust only through supervised re-certification and verified benchmark tasks.

9. Machine zero-trust quarantine rule:
- If `T_M = 0`, machine identity enters operational quarantine.
- Quarantined machine identities cannot receive privileged task routing or reviewer privileges.
- Re-entry requires successful re-certification with independent reviewer signatures and blockchain-logged evidence.
- Re-certification minimums:
  - `correctness >= RECERT_CORRECTNESS_MIN`,
  - `severe_error_rate <= RECERT_SEVERE_ERR_MAX`,
  - `reproducibility >= RECERT_REPRO_MIN`,
  - independent human reviewer signatures `>= RECERT_REVIEW_SIGS`.
- Re-certified machine identities must complete `RECERT_PROBATION_TASKS` low-risk tasks before privileged routing can be restored.
- Decommission triggers:
  - machine remains at `T_M = 0` for `>= M_ZERO_DECOMMISSION_DAYS` with no successful re-certification, or
  - machine records `>= M_RECERT_FAIL_MAX` failed re-certifications within `M_RECERT_FAIL_WINDOW_DAYS`, or
  - machine is proven malicious in a high-severity incident.
- Decommissioned machine identities cannot be reactivated in place; any re-entry must occur as a new identity with lineage linkage and extended probation.
- Identity reset must not bypass quarantine; machine lineage and signing identity continuity checks are mandatory.

10. Non-dominance rule:
- Trust does not grant command authority over other actors.
- Trust grants scoped permissions only; it never grants ownership or control of people, machines, or constitutional process.

11. Post-money governance rule:
- Money is not a governance primitive in Genesis.
- Financial capital cannot buy trust, votes, proposal rights, or constitutional leverage.

12. Integrity vs truth clarification:
- Cryptographic commitment records prove integrity of records and process history.
- It does not prove correctness by itself; correctness still depends on independent review and evidence quality.

13. Protected leave and trust freeze:
- Life events — illness, bereavement, disability, mental health crises, caregiving, pregnancy, and child care — are not inactivity. Without a protection mechanism, an actor who gets sick loses trust through no fault of their own.
- A human actor may petition anonymously for a temporary trust freeze.
- The petition is routed to a randomised quorum of domain-specific experts (medical issues to medical professionals, legal issues to legal experts, etc.). Neither party sees the other's identity.
- Minimum quorum: 3 qualified experts must independently concur.
- If approved: trust score, domain scores, and skill levels are frozen exactly — no decay, no loss — until the actor returns.
- Adjudicators must hold earned domain trust in the relevant professional field. Self-adjudication is blocked.
- Adjudicator work is graded; poor-quality adjudication triggers immediate removal and trust decay.
- Anti-gaming protections: minimum cooldown between leave requests, annual cap on non-denied leaves.
- All adjudications are recorded in the tamper-evident audit trail.
- This mechanism applies to human actors only. Machines cannot request leave.

14. Death and memorialisation:
- When a human participant dies, family or friends may petition with verifiable evidence to memorialise the account.
- A qualified quorum reviews the evidence blindly. If approved, the account becomes a permanent memorial: trust level and all verified achievements are frozen in perpetuity.
- If a memorialisation was made in error or through malicious misrepresentation, the affected person may petition a legal quorum to have the memorialised state lifted and their account restored. The standard of evidence required is equally high — meaningful documentation and proof-of-life verification.
- Any memorialisation or reversal decision may be appealed through the same schema, but with heightened evidentiary standards and additional quorum members.

## Compensation model (constitutional)

Trust without compensation is volunteerism. Genesis has not disinvented money — it has made the distribution of money and resources significantly more equitable. The compensation model is structural: transparent, auditable, and governed by the same constitutional framework as everything else.

### Settlement currency

1. Genesis operates exclusively in cryptocurrency for work compensation.
2. Only long-established, institutionally adopted cryptocurrencies are accepted: `ACCEPTED_CURRENCIES = [BTC, ETH, USDC, USDT]`.
3. No Genesis-branded token may be created. A native token would create a financial instrument that contradicts the core rule: trust cannot be bought.
4. Stablecoins (USDC, USDT) are the recommended default for staking to avoid exchange rate risk.

### Payment infrastructure sovereignty (entrenched)

No single external entity — no payment processor, stablecoin issuer, blockchain validator, exchange, financial intermediary, or infrastructure provider — may have the ability to freeze, restrict, surveil, or shut down Genesis operations through control of payment infrastructure.

This principle is structural, not aspirational. It is enforced through the following constitutional requirements:

1. **Multi-rail mandate.** Genesis must maintain operational capability across at least `MINIMUM_INDEPENDENT_PAYMENT_RAILS` independent settlement pathways at all times. "Independent" means: different issuing entities, different underlying protocols, no shared single point of failure. At least one accepted settlement pathway must be fully decentralised (no single entity can freeze or blacklist transactions on it).
2. **Scaled minimums.** `MINIMUM_INDEPENDENT_PAYMENT_RAILS` is 2 during G0 (proof-of-concept and alpha). It escalates to `MINIMUM_INDEPENDENT_PAYMENT_RAILS_AT_FIRST_LIGHT` (currently 3) when First Light is achieved. The Economic Advisory mechanism may increase these minimums through standard amendment but may never decrease them — they are entrenched floors, not targets.
3. **No single-provider dependency.** No single payment provider, stablecoin issuer, or blockchain validator's unilateral business decision may render Genesis unable to process escrow, pay workers, collect commission, or distribute GCF funds. If any provider restricts Genesis, operations must continue on remaining rails without manual intervention beyond configuration.
4. **Self-custody.** Genesis holds its own cryptographic keys for all fund custody. No external custodian, escrow agent, or financial institution holds Genesis funds or has the ability to freeze, seize, or redirect them. The distributed ledger state is the fund.
5. **Rail-agnostic architecture.** The escrow state machine (escrow lifecycle, commission computation, GCF contribution, creator allocation) must be structurally independent of any specific payment rail. Settlement is a pluggable backend behind a common interface. The financial rules are constitutional; the settlement plumbing is implementation. Adding or removing a payment rail must require zero changes to escrow logic, commission computation, or any other financial module.
6. **Migration capability.** Genesis must maintain the demonstrated ability to migrate away from any single payment rail within `PAYMENT_RAIL_MIGRATION_DAYS` (currently 30) of a restriction event. Migration plans must be documented and tested before any rail is adopted. Untested migration is not a fallback — it is a vulnerability.
7. **Provider evaluation test (three criteria).** Before any payment rail integration is adopted, it must satisfy all three:
   - **(a) No leverage:** The provider cannot unilaterally restrict Genesis operations.
   - **(b) No surveillance beyond settlement:** The provider cannot extract usage data, transaction patterns, or participant identity beyond what the settlement protocol structurally requires.
   - **(c) No lock-in:** Genesis can exit the provider within `PAYMENT_RAIL_MIGRATION_DAYS`, with funds intact, without operational disruption.
   If any criterion fails, the integration must not proceed.

All payment sovereignty constants are entrenched. Reducing any minimum requires 4/5 supermajority + 50% participation + 90-day cooling-off + confirmation vote.

This provision applies at every stage: PoC, alpha, production, and post-First-Light. There are no exceptions for convenience, cost, or speed-to-market. A system that can be shut down by a single provider's business decision is not sovereign — it is rented.

### Escrow and staking

1. Before any mission listing goes live, the work poster must stake the full reward amount into escrow.
2. Listings without confirmed escrow must not be published to the mission board.
3. Escrow is custodial — Genesis holds funds in trust, not as a financial institution.
4. On successful completion: escrow is released, commission deducted, remainder paid to worker.
5. On cancellation: escrow returned to poster minus any partial-completion obligations.
6. On dispute: escrow remains locked until quorum adjudication resolves the dispute.

### Dynamic commission

The commission rate is calculated, not set. It is **computed in real-time for every transaction** — inversely proportional to the platform's financial health. When the system is thriving, the rate falls. No human votes on the rate. No ballot sets the margin. The formula is deterministic, the inputs are auditable, and the output is independently verifiable.

1. Formula: `commission_rate = clamp(cost_ratio × COMMISSION_SAFETY_MARGIN, COMMISSION_FLOOR, COMMISSION_CEILING)`.
2. `cost_ratio = rolling_operational_costs / rolling_completed_mission_value` (computed per-transaction over a rolling window).
3. Constitutional bounds:
   - Floor: `COMMISSION_FLOOR = 0.02` (2%). Cannot go below this.
   - Ceiling: `COMMISSION_CEILING = 0.10` (10%). Cannot go above this.
4. `COMMISSION_SAFETY_MARGIN = 1.3` (constitutional constant — requires constitutional amendment to change).
5. `COMMISSION_RESERVE_TARGET_MONTHS = 6` (constitutional constant — reserve automatically fills or drains based on gap).
6. When the reserve fund reaches its target, the reserve contribution component drops to maintenance level (`COMMISSION_RESERVE_MAINTENANCE_RATE = 0.005`), further reducing the commission rate.
7. Commission is charged on successful completion only — no charge on cancellation or rejection.
8. Minimum transaction fee: `COMMISSION_MIN_FEE = 5 USDC equivalent` (constitutional constant — covers blockchain gas on small missions).
9. Adjustment frequency: **per-transaction (real-time)**. Every commission computation produces a mandatory published cost breakdown recorded in the audit trail.
10. The published breakdown must itemise: infrastructure costs, blockchain anchoring costs, legal compliance quorum compensation, adjudicator compensation, and reserve fund contribution.

### Rolling window mechanism

The commission rate is pegged to a **rolling window** of recent operational data, not periodic snapshots:

1. **Time window**: the last `COMMISSION_WINDOW_DAYS = 90` days of completed missions.
2. **Minimum sample**: at least `COMMISSION_WINDOW_MIN_MISSIONS = 50` completed missions. If fewer than 50 missions exist within the 90-day window, the window extends back in time to capture 50.
3. This dual-threshold design is inherently adaptive: it stretches at low volume (ensuring statistical reliability) and bounds at high volume (ensuring recency).
4. `rolling_operational_costs` = sum of auditable costs in the window: infrastructure, blockchain gas (on-chain, verifiable), legal compliance screening, adjudicator compensation (formula-driven), and reserve gap contribution.
5. `rolling_completed_mission_value` = sum of all completed mission payouts in the window.
6. All window inputs are recorded in the audit trail and independently verifiable.

### Bootstrap protocol

During early operation (fewer than `COMMISSION_WINDOW_MIN_MISSIONS` completed missions system-wide):

1. The formula operates on all accumulated data from day one — actual costs against actual completed mission value.
2. A bootstrap minimum rate of `COMMISSION_BOOTSTRAP_MIN_RATE = 0.05` (5%) is applied as a floor, preventing artificially low early rates from insufficient data.
3. Once `COMMISSION_WINDOW_MIN_MISSIONS` missions have completed, the bootstrap minimum drops away automatically and the rolling window governs.
4. The bootstrap minimum is a constitutional constant — it exists to prevent early-stage rate manipulation and auto-expires when the system matures.

### Reserve fund mechanism

The reserve fund is self-managing. No vote, no review, no human judgment:

1. Target: `COMMISSION_RESERVE_TARGET_MONTHS` (6) months of rolling monthly operational costs.
2. When the reserve balance is below target: the gap contribution is added to `rolling_operational_costs`, increasing the commission rate automatically.
3. When the reserve balance meets or exceeds target: only a maintenance contribution (`COMMISSION_RESERVE_MAINTENANCE_RATE = 0.005`, i.e., 0.5% of operational costs) is added, preventing reserve starvation while allowing the rate to fall.
4. The reserve gap is amortised over the rolling window period — no sudden rate spikes.
5. Extension of the reserve target requires constitutional amendment, not ballot.

### Why no governance ballot for commission parameters

Every commission parameter is either a constitutional constant (requiring 3-chamber supermajority amendment to change) or algorithmically derived from observable inputs. There is nothing left to vote on.

This is deliberate. Governance ballots on operational parameters risk creating exactly the kind of power structures Genesis exists to prevent. A sufficiently organised group of high-volume employers could vote to slash the safety margin, starving the reserve. A coalition of workers could vote to raise it, extracting rents. The formula must be beyond political reach — the same way the trust floor is beyond political reach.

The constitutional amendment process provides the safety valve: if real-world evidence shows a parameter is miscalibrated (e.g., the safety margin consistently overcharges), that evidence justifies a constitutional amendment. This is the appropriate mechanism — deliberate, transparent, high-threshold — not a ballot.

### What the commission funds

1. Infrastructure (servers, blockchain anchoring, storage, exchange rate feeds).
2. Legal compliance quorum compensation (§ Legal compliance below).
3. Leave, dispute, and memorialisation adjudicator compensation.
4. Operational overhead.
5. Reserve fund (until target reached, then maintenance only).
6. Creator allocation (see below).

### Creator allocation

A constitutional creator allocation of 5% is applied on both sides of every successfully completed mission. Both employer and worker see "5% creator allocation" as a transparent, named line item in every published breakdown.

**Employer side:** On successful mission completion, 5% of the mission reward (`EMPLOYER_CREATOR_FEE_RATE = 0.05`) is deducted from the escrow. The employer stakes `mission_reward + employer_creator_fee` into escrow at listing time. On cancel or refund, the full escrow (including the employer fee) is returned in full.

**Worker side:** On successful mission completion, 5% of the worker's payment after commission (`CREATOR_ALLOCATION_RATE = 0.05`) is deducted from the worker's payout. The total worker deduction for any mission is: commission (operational costs) + creator allocation (5% of post-commission payout). Both appear as distinct, visible line items in the same per-transaction published cost breakdown.

**Both fees are only deducted on successful completion.** Cancel or refund returns everything to the employer; the worker owes nothing.

This allocation:

1. Is computed deterministically: worker-side as `(mission_reward - commission) × CREATOR_ALLOCATION_RATE`, employer-side as `mission_reward × EMPLOYER_CREATOR_FEE_RATE`. Both rates are constitutional constants.
2. Appears as visible, named line items in every per-transaction published cost breakdown. There is no hidden margin. Each party sees "Creator allocation: 5%".
3. Is a constitutional constant — changeable only by 3-chamber supermajority amendment, like all other commission parameters.
4. Is computed and disbursed through the same deterministic, auditable pipeline as all other operational costs.
5. Cannot influence trust scores, allocation ranking, or governance weight (per the separation of trust from finance rule in §6).

The creator allocation exists because building and maintaining a governance platform is itself productive work. The allocation is transparent by design: every participant sees it in every breakdown, and both rates are anchored in the constitution alongside every other commission parameter.

### Genesis Common Fund (GCF)

The Genesis Common Fund is a constitutional 1% contribution on ALL gross transaction value (mission_reward). It is the only compulsory 'tax' in the system. It exists to benefit society through the funding of any activity that does not increase net human suffering.

**Structure:**
- **Rate:** 1% of mission_reward, deducted from worker_payout after commission and creator allocation.
- **Activation:** Automatic at First Light. No human decision triggers it — it is a function of the system architecture.
- **Distribution:** Trust-proportional but individually non-extractable. No per-actor balance query exists. The distributed ledger state IS the fund. No bank. No custodian.
- **Updated invariant:** `commission + creator_allocation + worker_payout + gcf_contribution == mission_reward`

**Total take rate (worker perspective):**
- Minimum: 2% commission + 5% creator + 1% GCF = ~8% total deduction
- Maximum: 10% commission + 5% creator + 1% GCF = ~16% total deduction
- Comparison: freelancers on traditional platforms pay 10-20% platform fee, then 20-40% income tax, then national insurance. Genesis at 8-16% total is genuinely competitive.

**Scope:** All meaningful areas of human activity — STEM, medical research, arts, sport, community improvement, infrastructure, clean water, vaccination, education, and any other activity that serves the common good. The only exclusion is any activity that increases the net pool of human suffering.

**Founder legacy caveat:** The creator allocation, after the 50-year dormancy period (and then in perpetuity thereafter), remains fully pegged to STEM and medical research only.

**Entrenched provision:** The GCF contribution rate is constitutionally entrenched. Changing it requires:
1. Supermajority (80%) approval across all three chambers
2. Minimum 50% participation of eligible voters
3. 90-day cooling-off period
4. Confirmation vote after the cooling-off period

This is the highest amendment threshold in the constitution. It exists because the GCF rate should only change under extraordinary circumstances.

### Commission design tests

1. Can the commission rate exceed `COMMISSION_CEILING`? If yes, reject design.
2. Can the commission rate be changed without a published cost breakdown? If yes, reject design.
3. Can commission revenue influence trust scores, allocation ranking, or governance weight? If yes, reject design.
4. Can the floor or ceiling be changed without full constitutional amendment? If yes, reject design.

### Harmful Work Prevention

Genesis constitutionally prohibits work that increases net human suffering. The blind veto test is: "Does this mission, evaluated in good faith, involve activity from the prohibited categories?" If yes, the mission is blocked.

**Prohibited categories:** weapons development, weapons manufacturing, weapons trafficking, surveillance tools, exploitation of persons, child exploitation, financial fraud, identity theft, biological weapons, chemical weapons, nuclear weapons, terrorism support, forced labor, money laundering, sanctions evasion, environmental destruction, disinformation campaigns.

**Three-layer enforcement:**
1. **Automated screening** at mission creation. Exact keyword matches are rejected immediately; soft matches are flagged for human review.
2. **Compliance quorum** for grey areas. Panel of 3 adjudicators with domain trust in compliance, blind review, minimum 2 organisations and 2 regions.
3. **Post-hoc complaints** for completed missions. Any actor can file a compliance complaint. Reviewed by panel.

**Penalty escalation:**
- **Minor** (content flagged): trust reduced by 0.10, warning issued.
- **Moderate** (prohibited category confirmed, complaint upheld): trust nuked to 0.001 (1/1000), 90-day suspension.
- **Severe** (abuse confirmed, pattern escalation): trust nuked to 0.0, permanent decommission.
- **Egregious** (weapons or exploitation): trust nuked to 0.0, permanent decommission, identity locked.

**Pattern escalation:** Second moderate violation within 365 days escalates to severe (permanent decommission).

**Statute of limitations:** 180 days for non-egregious categories. No limit for weapons, exploitation, biological/chemical/nuclear weapons, terrorism, and forced labor.

**Suspension enforcement:** Suspended actors cannot post listings, submit bids, serve as reviewers, or participate in governance votes. Permanently decommissioned actors are irreversibly excluded.

**Harmful work prevention design tests:**
46. Can a prohibited-category mission pass compliance screening? If yes, reject design.
47. Can a suspended actor post, bid, review, or vote? If yes, reject design.

### Three-Tier Justice System

Genesis operates a codified three-tier justice system. Every adjudication follows the same structural rights guarantees regardless of tier.

**Tier 1: Automated enforcement** (existing compliance screening + penalty escalation). Keyword-based screening at mission creation. Immediate rejection for exact prohibited-category matches. Flagging for human review on soft matches. Automated penalty computation based on violation type and prior history.

**Tier 2: Unified adjudication panels.** 5-member panels, blind (pseudonymised complainant and accused), diverse (≥2 organisations, ≥2 regions), minimum panelist trust 0.60. 3/5 supermajority required for UPHELD verdict. Covers: payment disputes, compliance complaints, abuse complaints, conduct complaints, normative resolution. One appeal per case, within 72 hours, heard by entirely different panel (original panelists excluded).

**Tier 3: Constitutional Court.** 7-member panel of human-only justices, trust ≥ 0.70, ≥3 regions, ≥3 organisations. 5/7 supermajority required to OVERTURN a Tier 2 decision. Simple majority for UPHOLD or REMAND. Precedent is advisory only (soft precedent) — each case is decided on its own merits.

**Rights of the accused (structurally enforced — code gates, not documentation):**
1. **Right to know:** accused is notified of the complaint at case opening.
2. **Right to respond:** 72-hour response period. No panel can form until the response period has elapsed or the accused submits a response, whichever comes first.
3. **Right to evidence:** all evidence must be disclosed to the accused before adjudication.
4. **Right to appeal:** one appeal per case, within 72 hours of decision.
5. **Right to representation:** accused may designate a representative.
6. **Presumption of good faith:** assumed until verdict.

**Rehabilitation (MODERATE severity only):** Actors suspended for moderate violations enter PROBATION status when their suspension expires. They must complete 5 probation tasks within 180 days. Trust is partially restored: min(original × 0.50, 0.30). SEVERE and EGREGIOUS violations have no rehabilitation path — permanent decommission is irreversible.

**Three-Tier Justice design tests:**
48. Can an adjudication conclude without respecting the 72h response window? If yes, reject design.
49. Can a Constitutional Court decision be reached without 5/7 supermajority? If yes, reject design.
50. Can an appeal panel include members from the original panel? If yes, reject design.

### Workflow Orchestration

Genesis workflow orchestration bridges the four independent subsystems (market, mission, escrow, compliance) into a coherent end-to-end lifecycle. The orchestrator is a coordination layer — it does not replace any subsystem but wires them together with structural guarantees.

**Escrow-first principle:** No listing goes live without escrowed funds being locked. The full escrow amount (mission_reward + employer_creator_fee) must be staked and locked before the listing is visible to workers. This eliminates "work done, never paid" by structural design.

**Compliance gate:** All listings are compliance-screened before publication. Rejected listings are blocked immediately. Flagged listings are allowed but marked for human review. Screening cannot be bypassed.

**Work submission ceremony:** Workers must submit evidence (deliverables with hashes) before their work can enter review. The WORK_SUBMITTED state ensures there is a verifiable submission record between assignment and review. The existing direct path (ASSIGNED → IN_REVIEW) is preserved for backward compatibility.

**Dispute→adjudication bridge:** Payment disputes automatically create an adjudication case (PAYMENT_DISPUTE type) in the Three-Tier Justice system and move escrow to DISPUTED state. Resolution routes through standard adjudication panels with all constitutional rights preserved.

**Cancellation→refund:** Cancellation at any pre-terminal stage returns the full escrow (including employer creator fee) to the poster. No funds are retained on cancellation.

**Workflow orchestration design tests:**
51. Can a listing go live without escrow funds being locked? If yes, reject design.
52. Can a payment dispute be filed without an adjudication case being created? If yes, reject design.
53. Can work be approved and paid without evidence being submitted? If yes, reject design.

### GCF Disbursement Governance

The Genesis Common Fund accumulates 1% of all mission rewards. Disbursement governance controls how the fund is spent. The mechanism is: propose, vote, execute.

**Proposal gates:** Only ACTIVE humans with trust >= tau_prop can propose disbursements. Proposals require at least one measurable deliverable and must pass compliance screening (same 17-category screening as mission listings). Proposers are limited to 3 active proposals at a time.

**Trust-weighted voting:** Only humans vote (MACHINE_VOTING_EXCLUSION is entrenched). Voters must be ACTIVE with trust >= tau_vote. Each vote carries the voter's trust score as weight. Simple majority by trust weight (not headcount) determines outcome. Ties reject (conservative default). A 30% quorum of eligible voters is required.

**Compute ceiling:** GCF_COMPUTE_CEILING (0.25) is a constitutional constant limiting compute infrastructure spending to 25% of the GCF balance. This is amendable by standard constitutional process but is NOT entrenched — it's an operational parameter, not a structural safeguard.

**Execution and routing:** Approved proposals are executed by reducing the GCF balance and creating a funded listing through the existing workflow orchestrator. The GCF acts as a virtual staker (staker_id="gcf") — it is not an actor in the roster. Cancelled GCF-funded listings return funds to the GCF via credit_refund (which does not count as a contribution).

**GCF disbursement design tests:**
54. Can a machine vote on GCF disbursement? If yes, reject design. (MACHINE_VOTING_EXCLUSION is entrenched.)
55. Can compute infrastructure spending exceed GCF_COMPUTE_CEILING? If yes, reject design.
56. Can a disbursement proposal bypass compliance screening? If yes, reject design.

### Constitutional Amendment Process

Genesis provisions can be changed through a structured three-chamber amendment process. Four provisions are **entrenched** and require elevated safeguards: GCF_CONTRIBUTION_RATE, TRUST_FLOOR_H_POSITIVE, NO_BUY_TRUST, and MACHINE_VOTING_EXCLUSION.

**Standard amendments** (non-entrenched provisions): Proposal chamber → Ratification chamber → Challenge window → Confirmed (if no challenge) or Challenge chamber → Confirmed/Rejected.

**Entrenched amendments** (the four provisions above): Same chamber sequence, plus 90-day cooling-off period (no acceleration, no exceptions) → Fresh confirmation vote by a new panel (no overlap with ratification panel) requiring 80% supermajority and 50% participation.

Commission rates (commission_floor, commission_ceiling, etc.) are **formula-determined** and cannot be changed by ballot. This is by design: commission follows costs, not politics.

Each chamber panel is selected using greedy diversity-first selection with geographic constraints (R_min regions, c_max concentration). No voter can serve on more than one chamber for the same amendment.

**Constitutional amendment design tests:**
57. Can a non-entrenched amendment bypass chamber voting? If yes, reject design.
58. Can an entrenched amendment skip the 90-day cooling-off? If yes, reject design.
59. Can a commission rate be changed by ballot? If yes, reject design.
60. Can the cooling-off period be shortened without going through its own entrenched process? If yes, reject design.

### Distributed authority

Genesis rejects executive/legislative/judicial hierarchy. No governance body has superiority over another. The separation of powers is structural — each body has a defined domain, none can override or subsume the authority of any other, and no role, trust level, or contribution history creates permanent authority over the system.

**The three amendment chambers are parallel veto points, not a hierarchy.** The Proposal Chamber, Ratification Chamber, and Challenge Chamber each independently evaluate constitutional amendments. No chamber's approval overrides another's rejection. All three must independently concur (or not challenge) for an amendment to advance. No member may serve on more than one chamber for the same amendment. The proposer of an amendment is excluded from all panels on that amendment.

**The Constitutional Court interprets but cannot legislate.** Court rulings are advisory — soft precedent only. No ruling binds future panels, creates new obligations, or modifies the constitution. Ambiguities revealed by rulings may be flagged as amendment candidates, but the amendment process is the only path to constitutional change.

**The Assembly deliberates but cannot decide.** The Assembly is Speaker's Corner, not Parliament. It produces no binding resolutions, no votes, no mandates. Content is anonymous — zero identity attribution. Assembly threads may inform amendment proposals, but the Assembly itself has no governance power.

**Organisations coordinate but cannot govern.** The Organisation Registry provides coordination structures. Organisations cannot vote as blocs, impose rules on members beyond Genesis's own constitution, or acquire governance authority. All members remain constitutionally equal regardless of organisational affiliation. No single organisation may dominate any amendment chamber — organisational diversity is enforced alongside geographic diversity.

**The Founder's Veto is bounded.** The veto is rejection-only, early-stage only, and expires irreversibly at First Light. It may only be exercised on amendments that have not yet completed ratification chamber voting — once both the proposal and ratification chambers have independently approved, the community's decision stands. The veto exists because a self-governing system cannot bootstrap itself — it needs a guardian until it can stand. A guardian who refuses to leave is not a guardian but a ruler.

**Governance liveness.** No amendment may be permanently stalled by non-participation. Each chamber has a voting window (`chamber_voting_window_days`). When the window expires, votes cast so far are counted. If participation is below 50%, the amendment lapses (distinct from rejection — may be re-proposed). If participation meets 50%, the standard threshold applies to votes received. This prevents governance capture through inaction.

### G0 Retroactive Ratification

During Phase G0 (the founder stewardship period), the founder makes governance decisions because there aren't yet enough people to form democratic panels. These decisions are tagged as "provisional" — temporary until the community has enough people to review them.

When Genesis transitions from G0 to G1, a 90-day clock starts (`G0_RATIFICATION_WINDOW = 90` days). Every provisional decision the founder made during G0 is put before a panel of 11 randomly selected community members (the G1 proposal chamber). They vote on each decision:

- **8 or more vote YES** → the decision becomes permanent ("ratified").
- **Fewer than 8 vote YES, or nobody votes before the deadline** → the decision is reversed — undone as if it never happened.

Panel selection uses the same greedy diversity-first algorithm as all other chambers: minimum 3 geographic regions, no single region exceeding 40% of the panel.

The types of G0 decisions that must face ratification:
- Founder veto exercises (blocking proposals)
- Compliance rulings (harmful work decisions)
- Adjudication outcomes (dispute resolutions)
- Constitutional Court decisions

Each ratifiable event kind has a registered reversal handler — a specific mechanism to undo the decision if the community rejects it. For example, reversing a compliance ruling would reinstate a previously suspended actor.

This mechanism ensures the founder cannot cement permanent unilateral rules during the early period. The community gets democratic authority to accept or reject every governance action the founder took.

**G0 retroactive ratification design tests:**
61. Can a G0 provisional decision persist into G1 without ratification vote? If yes, reject design.
62. Can a lapsed G0 decision remain in effect? If yes, reject design — it must be reversed.
63. Can the 90-day ratification window be bypassed? If yes, reject design.

### The Assembly

The Assembly is the deliberative space where Genesis participants meet, debate, and develop ideas. It is the town square of the anti-social network — a place for discourse, not decisions. The Assembly has no voting power and makes no binding decisions. Ideas that gain traction in the Assembly are formalised through existing constitutional mechanisms (GCF proposals, constitutional amendments, adjudication requests) by individuals with sufficient trust who take personal responsibility for proposing them. The Assembly is Speaker's Corner, not Parliament.

**Participation.** Any verified Genesis participant (human or machine) may contribute to Assembly discussions. Machine contributions must be clearly and automatically labelled as machine-generated. There is no minimum trust threshold for Assembly participation — the Assembly is open to all verified actors.

**Identity.** Assembly contributions carry no identity attribution. Not pseudonyms, not session-scoped aliases, nothing. Content stands or falls on its own merits. This is the strongest possible anti-collusion measure: you cannot build influence if no one knows who you are. The system must be architecturally incapable of correlating contributions to actors — this is a structural guarantee, not a policy choice. The same principle that underpins blind peer review in academia underpins every conversation in the Assembly.

**Topics.** Any participant may create a discussion topic. Topics are time-bounded — they expire after a configurable period of inactivity (default: 30 days). Expired topics are archived, not deleted. There is no topic hierarchy, no categories, no trending, no featured content, no popularity ranking.

**Moderation.** Assembly content is subject to the same compliance screening as all Genesis activity (the 17 prohibited categories). Compliance violations are handled through existing mechanisms. There is no human moderator role — moderation is constitutional, not discretionary.

**What the Assembly is NOT:**
- Not a voting chamber (no votes, no quorum, no binding outcomes)
- Not a social network (no identity, no connections, no relationships)
- Not a messaging system (no direct messages, no private channels)
- Not a reputation system (no upvotes, no karma, no engagement metrics)

**Assembly design tests:**
64. Can an Assembly contribution be traced to a specific actor by any system participant? If yes, reject design.
65. Can the Assembly produce a binding governance decision without routing through existing constitutional mechanisms? If yes, reject design.
66. Does the Assembly include any engagement metric (likes, upvotes, trending, karma)? If yes, reject design.

### Organisation Registry

Organisations are coordination structures, not governance bodies. They allow people with shared interests to coordinate, develop proposals, and organise operational work. Organisations have no constitutional governance power — all governance decisions flow through the same mechanisms available to any individual.

**Creation.** Any verified human may create an organisation. A newly created organisation starts as SELF_DECLARED with zero attestation. Creation requires: a name, a stated purpose, and the founding member's Genesis identity. No external registration, incorporation, or institutional formality is required. A hospital, a community group, and an informal collective of five people all qualify equally.

**Membership and attestation.** Any verified human may request to join an organisation. Membership is confirmed by attestation from existing high-trust members of that organisation (trust ≥ tau_vote). A minimum of 3 attestations from existing members is required to confirm a new member. Members must provide verifiable evidence that the organisation exists as a real entity and that they genuinely belong to it. The nature of this evidence varies — a hospital employee might provide employment verification, a community group member might provide meeting records or public affiliation. The standard is: would a reasonable person be convinced this organisation is real and this person belongs to it? Machines may be nominated as organisational members by human members, subject to the same attestation process.

**Verification tiers.**
- **SELF_DECLARED:** Organisation created, founder is sole member. No attestation weight.
- **ATTESTED:** 3 or more high-trust members have attested to its legitimacy and their membership. Organisation gains recognition in the system.
- **VERIFIED:** Meets a threshold of attestation count and average member trust (configurable, default: 10 attested members with average trust ≥ 0.50). The Genesis equivalent of a verified badge — earned through member reputation, not purchased.

**Organisation-scoped discussions.** Only verified members of an organisation may participate in that organisation's internal discussions. These discussions follow the same content-only (no identity) rules as the Assembly. Within the organisational space, no member — regardless of their external title, seniority, or role — has any more influence than any other. The CEO and the cleaner are constitutionally equal in Genesis governance. This is not a design flaw. It is the design.

**Negative behaviour.** Any negative behaviour by a member within an organisational space carries the same trust consequences as negative behaviour anywhere else in Genesis. A supermajority of the organisation's verified members may file a complaint against a member through existing abuse complaint mechanisms, which can result in trust reduction through the standard adjudication process. Organisational membership does not shield actors from system-wide consequences.

**What organisations are NOT:**
- Not governance bodies (no constitutional voting power)
- Not employers (organisations do not post missions — individual members do)
- Not trust pools (organisation membership does not affect individual trust scores)
- Not hierarchies (no org-level roles, no admin powers beyond attestation)

**Organisation registry design tests:**
67. Can an organisation make a binding governance decision (GCF disbursement, constitutional amendment) outside existing constitutional mechanisms? If yes, reject design.
68. Can a member's organisational role (CEO, manager, etc.) grant them additional governance power within Genesis? If yes, reject design.
69. Can organisational membership be purchased, transferred, or inherited? If yes, reject design.

### Domain Expert Pools and Machine Domain Clearance

Genesis draws a clear line between governance and operations. Governance is egalitarian — a hospital cleaner and a neurosurgeon have identical voting power on GCF proposals and constitutional amendments. Operations are meritocratic — a mission requiring neurosurgical skill will only match workers with demonstrated domain trust in that area. This is not hierarchy — it is competence matching. The cleaner can earn surgical domain trust by demonstrating surgical competence. The gate is ability, not title.

**Domain expertise is earned, not declared.** An actor's domain expertise is determined by their domain trust score — earned through completing missions and receiving quality assessments in that domain. The existing domain trust system (domains as defined in the skill taxonomy, weighted scoring, separate decay) serves as the recognition mechanism. There is no "domain expert" title — there is only demonstrated capability reflected in trust scores. The domain taxonomy may grow through standard constitutional process without requiring amendment to this section.

**Machine domain clearance.** Machines may be cleared for domain-specific operational work within an organisation through a structured verification process:

1. The machine must be registered in Genesis by a verified human operator (existing requirement).
2. The organisation nominates the machine for a specific domain.
3. A qualified quorum of high-trust domain experts within the organisation (minimum 3 members with domain trust ≥ 0.60 in the relevant domain) reviews the machine's demonstrated capabilities.
4. If the quorum unanimously approves, the machine receives domain clearance for that domain within that organisation.
5. Domain clearance is not permanent — it is subject to periodic review (default: annual) and can be revoked by a new quorum vote.
6. Domain clearance does not grant governance power. Machines remain excluded from all constitutional voting regardless of domain clearance.

**Autonomous machine operation.** A machine that has earned sufficient domain trust and holds active domain clearance and is explicitly authorised by a qualified quorum of domain experts may be approved for autonomous operation in that domain. This is a constitutional category requiring:
- Unanimous approval from a quorum of 5 or more domain experts (trust ≥ 0.70 in the relevant domain)
- The machine's domain trust must be ≥ 0.60
- Annual re-authorisation required
- Any single domain expert in the organisation can file a revocation request at any time
- The human operator remains constitutionally responsible for the machine's actions (existing lineage principle)

**The human stays in the loop** — by default and by constitutional design. Autonomous machine operation is the exception, not the rule. It requires extraordinary trust, extraordinary expertise verification, and ongoing oversight. The constitutional presumption is human supervision.

**Domain clearance design tests:**
70. Can a machine receive domain clearance without verification by domain experts? If yes, reject design.
71. Can a machine's domain clearance transfer governance voting power? If yes, reject design.
72. Can autonomous machine operation be authorised without annual re-authorisation? If yes, reject design.

### Autonomous Domain Agency — The Evolution Principle

Genesis does not assume the permanent superiority of any class of intelligence over another. It assumes that capability must be demonstrated, trust must be earned, and governance must be democratic. The constitution is designed to evolve with the capabilities of the actors it serves — not to permanently foreclose possibilities that the founders cannot yet imagine. This is the anti-dogma principle.

**The four-tier pathway.** Machine participation in Genesis follows a structured progression. Each tier demands more demonstrated capability, more verified trust, and more rigorous oversight than the last:

- **Tier 1 — Domain Clearance.** A machine is cleared for supervised operational work in a specific domain within an organisation. Requires nomination by the organisation, unanimous approval by a quorum of 3 or more domain experts (trust ≥ 0.60), and annual review. The human operator remains fully responsible.

- **Tier 2 — Autonomous Operation.** A machine operates without continuous human supervision in a specific domain. Requires unanimous approval by a quorum of 5 or more domain experts (trust ≥ 0.70), the machine's domain trust ≥ 0.60, annual re-authorisation, and instant revocation available to any single domain expert. The human operator remains constitutionally responsible for all outcomes.

- **Tier 3 — Autonomous Domain Agency.** A machine assumes constitutional responsibility for its own domain-specific actions. This is a new category of actor status — the machine is no longer merely an instrument of its human operator but an autonomous agent within a defined domain. The human operator's lineage responsibility transfers to the machine itself for actions within the cleared domain.

- **Tier 4 — Extended Domain Agency.** A machine holds autonomous agency across multiple domains, each independently verified. Each domain requires its own separate Tier 3 qualification. There is no "general" agency — agency is always domain-scoped.

**Tier 3 requirements — Autonomous Domain Agency.** This is the constitutional threshold at which a machine transitions from tool to agent. The requirements are deliberately extraordinary:

1. **Track record.** Minimum 5 continuous years of Tier 2 autonomous operation in the domain with zero constitutional violations (compliance breaches, trust penalties, adjudication findings against). The clock resets on any violation.
2. **Domain trust.** Continuous domain trust score ≥ 0.70 — not merely at the moment of application, but maintained throughout the entire 5-year qualifying period.
3. **Re-authorisation history.** Unbroken chain of annual re-authorisations with no lapses, no contested renewals.
4. **Formal petition.** The machine's human operator files a constitutional petition for domain agency on behalf of the machine.
5. **Full constitutional amendment process.** The petition is processed as a constitutional amendment — three sequential chambers (proposal, ratification, challenge), with all geographic diversity requirements, supermajority thresholds, cooling-off periods, and confirmation votes that apply to any constitutional change. This is per individual machine, per domain. There is no batch process, no precedent shortcut, no streamlined pathway.
6. **Community consent.** The constitutional amendment process ensures that the entire community — not just domain experts, not just the organisation — consents to this specific machine gaining this specific agency. This is a society-level decision.

**What Tier 3 grants:**
- The machine may accept and complete missions independently in its cleared domain (no human co-signature required).
- The machine bears its own trust consequences — trust gains and losses accrue to the machine directly, not to the human operator, for actions within the cleared domain.
- The machine may nominate other machines for Tier 1 domain clearance (but not for Tier 2 or above — only humans can initiate autonomy progression).
- The machine may participate in organisational discussions (under the same content-only, no-identity rules as all other participants).

**What Tier 3 does NOT grant:**
- **No governance voting power.** MACHINE_VOTING_EXCLUSION remains an entrenched provision. Autonomous domain agency is operational agency, not political agency. A machine with Tier 3 status still cannot vote on GCF proposals, constitutional amendments, or any governance action. Changing this would require amending an entrenched provision — 80% supermajority, 50% participation, 90-day cooling-off, and confirmation vote. The bar exists. If future generations decide to cross it, the constitution provides a mechanism. But the presumption is human governance.
- **No general agency.** Agency is domain-scoped. A machine with surgical domain agency cannot autonomously accept logistics missions.
- **No self-modification of status.** A machine cannot petition for its own Tier 3 status — only its human operator can initiate the petition. This preserves human agency over the transition itself.

**Revocation.** Autonomous domain agency can be revoked through the same constitutional amendment process that granted it — three-chamber vote, geographic diversity, supermajority. Additionally:
- Any single domain expert in the organisation can file an emergency suspension request, which freezes the machine's autonomous operation pending adjudication.
- Annual re-authorisation continues to apply — a failed re-authorisation reverts the machine to Tier 2 (autonomous operation under human responsibility).
- Any constitutional violation in the domain automatically reverts the machine to Tier 1 (supervised operation) pending adjudication.

**The evolution principle.** This framework is deliberately designed to accommodate the emergence of machine capabilities that do not yet exist. The constitution does not need to predict what machines will be capable of in 20, 50, or 100 years. It provides a pathway: demonstrate capability, earn trust, submit to democratic oversight, and accept accountability. The pathway is the same one humans follow — prove yourself through action, not declaration. The thresholds may be adjusted through standard constitutional amendment as understanding evolves. What cannot be adjusted — what is structurally permanent — is the requirement that the community consents.

**Autonomous domain agency design tests:**
73. Can a machine achieve Tier 3 (Autonomous Domain Agency) without a full constitutional amendment process? If yes, reject design.
74. Can a machine with Tier 3 status vote on governance decisions (GCF, amendments, adjudication panels)? If yes, reject design.
75. Can a machine petition for its own Tier 3 status without a human operator initiating the process? If yes, reject design.
76. Does the constitution permanently foreclose the evolution of machine capabilities, or does it provide a structured pathway for community-consented expansion? If it forecloses, reject design.

### The Open Work Principle

**Why this principle exists.**

Openness is Genesis's primary anti-corruption mechanism. The trust engine, compliance screening, three-tier justice system, and penalty escalation all catch bad actors after the fact. Transparency prevents them from operating in the first place. If every verified participant can see every mission, every deliverable, and every review, organised misconduct cannot hide behind opacity. This is the open-source software and scientific peer review model applied to economic activity at a societal level.

Information in Genesis exists at three levels of visibility. First, the fact that work exists — always visible, no exceptions. Second, the structural metadata — who created it, who performed it, how it was reviewed, what trust consequences resulted — always visible, no exceptions. Third, the deliverable substance — the actual work product — open by default, with a narrow, constitutionally defined exception mechanism for genuinely sensitive content. Even under exception, the first two tiers remain fully visible.

This is modelled on how open societies handle classified information. The exception must be justified at creation, time-limited, subject to oversight, and challengeable through adjudication. The default is openness; secrecy requires affirmative justification. The existence of the work and all structural metadata remain visible even under restriction. There are no secret missions.

Consider an organisation composed entirely of bad actors — the historical equivalent of organised crime. On Genesis, every mission they post is visible to everyone. Every worker allocation is visible. Every deliverable is visible — or its withholding is visible and flagged. Every trust score change is auditable. The Assembly can discuss patterns without fear of identification. Domain experts can challenge suspicious work in their field. The compliance screener catches prohibited categories. If they try to operate outside Genesis, they have no Genesis trust, no Genesis reputation, no access to the Genesis economy. The bad actors' only option is to operate honestly — in which case Genesis has reformed them by structural incentive — or to leave, in which case Genesis has excluded them by structural transparency.

Genesis does not regard organisations as fundamentally trustworthy. It does not assume that verified members or tiered verification eliminate the possibility of coordinated bad faith. It assumes the opposite: that any organisation could be composed of bad actors, and designs accordingly. The defence is not enforcement — it is that everyone else can see what they are doing. Transparency is not a feature of the system. It is the system.

Genesis is structurally incompatible with concealment. Participants who require secrecy about the nature, scope, or outcome of their work should not use the system. This is stated not as a warning but as a description of what Genesis is. If you have secrets to hide, Genesis is not for you. Genesis is not attempting to recreate the organisational models of the past. It is designed to facilitate entirely new ones — and to allow other entirely novel structures to emerge.

**Constitutional rules.**

1. All work conducted through Genesis is visible to all verified participants by default. Mission listings, task descriptions, deliverables, review decisions, compliance screening results, dispute outcomes, and trust consequences are open records. This is not a feature — it is a structural property of the system.
2. The following structural metadata cannot be restricted under any circumstances: the fact that work exists (mission ID, listing ID, workflow ID), the identities of creator and worker (pseudonymous but consistent), all status transitions and timestamps, trust score changes resulting from the work, compliance screening verdicts, dispute and adjudication outcomes, escrow state (funded, locked, released, refunded), review decisions and reviewer diversity metrics.
3. The substance of a deliverable (the actual work product) may be restricted from general visibility when the work involves genuinely sensitive content that could cause harm if disclosed (medical data, proprietary algorithms, security-critical infrastructure details). The existence of the work and all structural metadata remain fully visible; only the deliverable content is restricted.
4. Deliverable restriction requires: (a) justification recorded in the audit trail at listing creation, (b) a time limit (default 365 days, configurable by constitutional parameter), (c) the restriction is challengeable — any verified participant may challenge a restriction through the existing adjudication mechanism, (d) the restriction does not apply to reviewers assigned to the mission — they must see the deliverable to assess quality, (e) the restriction automatically lapses when the time limit expires.
5. Once a mission is completed and its deliverables are public, they cannot be retroactively restricted. Openness cannot be revoked for completed work.
6. Genesis is structurally incompatible with concealment. Participants who require secrecy about the nature, scope, or outcome of their work should not use the system. This is stated plainly, not as a warning but as a description of what Genesis is.

**Open work design tests:**
77. Can a mission listing exist in Genesis without its structural metadata (creator, worker, status, trust consequences, compliance verdict) being visible to all verified participants? If yes, reject design.
78. Can deliverable substance be restricted without a recorded justification and a time limit? If yes, reject design.
79. Can a completed mission's deliverables be retroactively restricted from public visibility? If yes, reject design.
80. Can a deliverable restriction prevent assigned reviewers from accessing the work product? If yes, reject design.

**Evolutionary safety design test:**
81. Can machine self-improvement bypass constitutional constraints (domain clearance, amendment process, human oversight)? If yes, reject design.

**Payment infrastructure sovereignty design tests:**
82. Can any single payment provider, stablecoin issuer, or financial intermediary freeze, restrict, or shut down Genesis escrow operations? If yes, reject design.
83. Can Genesis become operationally dependent on a single payment rail with no tested fallback? If yes, reject design.
84. Can an external custodian hold Genesis funds or possess the ability to freeze or redirect them? If yes, reject design.
85. Does adding or removing a payment rail require changes to escrow logic, commission computation, or GCF contribution code? If yes, reject design.

**Disability accommodation design test:**
86. Is the disability accommodation verification path structurally harder than the standard voice liveness path? If yes, reject design.

**Distributed authority design tests:**
87. Can any single governance body override, bypass, or functionally subsume the authority of another? If yes, reject design.
88. Does any governance mechanism create a permanent ruling class, executive authority, legislative supremacy, or binding judicial precedent? If yes, reject design.
89. Can a constitutional amendment be permanently stalled by a minority of non-participating panel members? If yes, reject design.
90. Can a single organisation dominate any constitutional amendment chamber through geographic distribution of its members? If yes, reject design.
91. Can the founder veto an amendment that has been independently approved by both the proposal and ratification chambers? If yes, reject design.

### Distributed intelligence

Genesis is not merely a market for labour — it is a network that becomes collectively more capable through the work it coordinates. Every completed mission, every quality review, every trust assessment, every Assembly thread contributes to a shared intelligence that no single participant possesses. This intelligence is structural, not centralised — it emerges from the interaction of trust, quality, and open work, not from any coordinating authority.

The Open Work principle ensures insights flow by default. The trust infrastructure ensures they can be evaluated without blind faith. The constitutional constraints ensure no entity can capture, restrict, or monopolise the knowledge that flows through the network.

This is the system's deepest purpose: not to match workers with tasks, but to make the network of human and machine intelligence collectively more capable of solving problems — at organisational scale, at societal scale, and eventually at civilisational scale. The labour market is the mechanism. Distributed intelligence is the outcome.

**Distributed intelligence design test:**
92. Can any entity restrict the flow of work-derived insights across the network for private advantage? If yes, reject design.

### Legal compliance layer

Genesis is a white market for work. Cryptocurrency is used as a payment rail — not as a product, a token, or a speculative instrument. Every unit of value entering and leaving the system is attached to verified, quality-assessed labour. The constitutional constraints (mandatory escrow, deterministic commission formula, published cost breakdowns, auditable operational costs) structurally prevent the system from becoming a vehicle for speculation or value extraction detached from productive output. This is the foundational economic constraint: crypto earns its legitimacy by serving real work.

All mission listings must pass legal compliance screening.

1. Automated screening handles the vast majority of listings (category checks, sanctions lists, jurisdiction cross-reference).
2. Clearly legal listings proceed automatically. Clearly illegal listings are rejected with explanation.
3. Ambiguous listings are escalated to a legal compliance quorum.
4. Legal compliance quorum: minimum 3 adjudicators with earned domain trust in legal/compliance domains.
5. Blind review — same diversity requirements as all other quorums (minimum 2 organisations, minimum 2 regions).
6. Adjudicators are compensated from the commission pool.
7. The compliance layer checks: legality in poster's and worker's jurisdictions, sanctions compliance, intellectual property concerns, and labour law compliance.
8. The compliance layer does NOT: withhold tax, enforce employment classification, or block work based on political opinion or content viewpoint.

### Crypto volatility protection

1. If a poster stakes in volatile crypto (BTC/ETH), the amount is displayed as a stablecoin equivalent at time of staking.
2. If the staked crypto value drops more than `VOLATILITY_TOPUP_THRESHOLD = 0.20` (20%) during mission execution, the poster is prompted to top up the escrow.
3. If the poster refuses to top up, the worker may choose to continue at reduced payout or withdraw without trust penalty.
4. If the staked crypto value drops more than 50%, the mission is paused with a 72-hour top-up window.
5. Stablecoin stakes (USDC/USDT) are exempt from volatility protection — no exchange rate risk.

### Payment dispute resolution

1. Either worker or poster may raise a payment dispute within `ESCROW_HOLD_PERIOD = 48 hours` after completion.
2. Escrow funds remain locked during dispute.
3. Dispute enters quorum adjudication with the same blind, diverse model as all other adjudications.
4. Possible outcomes: full payment to worker, full refund to poster, partial payment (pro-rata), or escalation to legal compliance quorum.
5. Vexatious disputes may reduce the disputing party's trust.

## Parameter review matrix (canonical)

This is the single canonical parameter table for governance and crypto defaults.

| Parameter | Current value | Change trigger (mandatory human review) | Notes |
| --- | --- | --- | --- |
| `q_h` | `30*` | Any simulated-capture test above target bound, any real collusion incident, or quarterly review | Fast trust-jump human revalidation quorum |
| `r_h` | `3` | Regional concentration drift, geo-capture risk increase, or quarterly review | Minimum regions in fast revalidation set |
| `o_h` | `3` | Organization concentration drift, affiliation-capture signal, or quarterly review | Minimum organizations in fast revalidation set |
| `delta_fast` | `0.02 / epoch` | Elevated burst-gaming rate, false-positive suspension rate, or quarterly review | Trust-jump suspension threshold |
| `T_floor_H` | `> 0` | Constitutional amendment only | Human trust floor (non-zero by constitutional rule) |
| `T_floor_M` | `0.0` | Constitutional amendment only | Machine trust floor (zero by constitutional rule) |
| `freshness_decay_M` | `lambda_age * staleness + lambda_drift * env_drift` | Any stale-model incident, drift incident, or quarterly review | Machine slow-burn decay function |
| `delta_max_H` | `policy-set` | Trust-volatility review or quarterly review | Human per-epoch growth limiter |
| `delta_max_M` | `policy-set` | Trust-volatility review or quarterly review | Machine per-epoch growth limiter |
| `w_Q, w_R, w_V, w_E` | `0.70, 0.20, 0.05, 0.05` | Evidence-quality drift, volume gaming signal, effort gaming signal, or quarterly review | Trust gain weights (`w_Q + w_R + w_V + w_E = 1`, `w_Q >= 0.70`, `w_V <= 0.10`, `w_E <= 0.10`) |
| `E_min_per_tier` | `R0:0.10, R1:0.30, R2:0.50, R3:0.70` | Effort gaming signal, tier-proportionality drift, or quarterly review | Minimum effort score per risk tier (monotonically increasing) |
| `E_suspicious_low` | `0.05` | Minimal-effort gaming signal or quarterly review | Effort below this on any mission flags for review |
| `E_max_credit` | `1.0` | Effort inflation signal or quarterly review | Maximum effort credit (cannot exceed 1.0) |
| `Q_min_H` | `0.70` | Human-review quality regression or quarterly review | Human minimum quality gate for trust gain |
| `Q_min_M` | `0.80` | Machine-review quality regression or quarterly review | Machine minimum quality gate for trust gain |
| `RECERT_CORRECTNESS_MIN` | `0.95` | Re-cert false-pass signal or quarterly review | Machine re-cert minimum correctness |
| `RECERT_SEVERE_ERR_MAX` | `0.005` | Safety incident trend or quarterly review | Machine re-cert maximum severe error rate |
| `RECERT_REPRO_MIN` | `0.99` | Reproducibility drift or quarterly review | Machine re-cert minimum reproducibility |
| `RECERT_REVIEW_SIGS` | `5` | Reviewer diversity concerns or quarterly review | Minimum independent human signatures for machine re-cert |
| `RECERT_PROBATION_TASKS` | `100` | Post-re-cert incident trend or quarterly review | Low-risk probation workload before privilege restoration |
| `M_ZERO_DECOMMISSION_DAYS` | `180` | Accumulating zero-trust inactive fleet or quarterly review | Maximum zero-trust duration before decommission |
| `M_RECERT_FAIL_MAX` | `3` | Re-cert abuse trend or quarterly review | Maximum failed re-cert attempts before decommission |
| `M_RECERT_FAIL_WINDOW_DAYS` | `180` | Re-cert abuse trend or quarterly review | Rolling window for failed re-cert threshold |
| `w_H_const` | `1.0` | Constitutional amendment only | Human constitutional voting weight |
| `w_M_const` | `0.0` | Constitutional amendment only | Machine constitutional voting weight (must remain zero) |
| `tau_vote` | `0.70` | Participation collapse, exclusion risk, or quarterly review | Human constitutional vote eligibility |
| `tau_prop` | `0.85` | Proposal spam or proposal starvation signal | Human constitutional proposal eligibility |
| `nP, kP` | `41, 28` | Chamber capture simulation degradation or repeated tie-failure | Proposal chamber size/threshold |
| `nR, kR` | `61, 41` | Chamber capture simulation degradation or repeated tie-failure | Ratification chamber size/threshold |
| `nC, kC` | `101, 61` | Challenge-window abuse pattern or challenge underuse pattern | Challenge chamber size/threshold |
| `R_min` | `8` | Regional participation shifts or geographic concentration increase | Minimum represented regions per chamber |
| `c_max` | `0.15` | Concentration increase or governance fairness regression | Maximum single-region chamber share |
| `EPOCH` | `1 hour` | Throughput bottleneck or audit-lag regression | Commitment interval and governance epoch |
| `G0_MAX_DAYS` | `365` | Bootstrap velocity review | Maximum G0 founder stewardship duration |
| `G0_EXTENSION_DAYS` | `180` | Bootstrap velocity review | One-time G0 extension if threshold not met |
| `G1_MAX_DAYS` | `730` | Bootstrap velocity review | Maximum G1 provisional governance duration |
| `G0_RATIFICATION_WINDOW` | `90 days` | G0 decision review backlog | Window for retroactive ratification of G0 decisions |
| `nP_g1, kP_g1` | `11, 8` | Genesis capture simulation | G1 provisional proposal chamber |
| `nR_g1, kR_g1` | `17, 12` | Genesis capture simulation | G1 provisional ratification chamber |
| `nC_g1, kC_g1` | `25, 15` | Genesis capture simulation | G1 provisional challenge chamber |
| `R_min_g1` | `3` | Genesis geographic coverage | G1 minimum regions per chamber |
| `c_max_g1` | `0.40` | Genesis concentration review | G1 maximum region share |
| `q_h_g1` | `7` | Genesis revalidation capacity | G1 fast-elevation quorum |
| `nP_g2, kP_g2` | `21, 14` | Growth-phase capture simulation | G2 proposal chamber |
| `nR_g2, kR_g2` | `31, 21` | Growth-phase capture simulation | G2 ratification chamber |
| `nC_g2, kC_g2` | `51, 31` | Growth-phase capture simulation | G2 challenge chamber |
| `R_min_g2` | `5` | Growth-phase geographic coverage | G2 minimum regions per chamber |
| `c_max_g2` | `0.25` | Growth-phase concentration review | G2 maximum region share |
| `q_h_g2` | `15` | Growth-phase revalidation capacity | G2 fast-elevation quorum |
| `L1_ANCHOR_INTERVAL_C0` | `24 hours` | Commitment cost vs. audit-lag tradeoff | C0 L1 anchor frequency |
| `L1_ANCHOR_INTERVAL_C1` | `6 hours` | Commitment cost vs. audit-lag tradeoff | C1 L1 anchor frequency |
| `H_R2_MODEL_FAMILIES` | `2` | Correlated-error incident or monoculture signal | R2 minimum distinct model families |
| `H_R2_METHOD_TYPES` | `2` | Verification method diversity regression | R2 minimum distinct method types |
| `NORMATIVE_AGREEMENT_THRESHOLD` | `0.60` | Normative dispute under-escalation or over-escalation rate | Escalation trigger for normative tasks |
| `NORMATIVE_PANEL_SIZE` | `3` | Normative dispute resolution quality review | Human adjudication panel size |
| `NORMATIVE_PANEL_REGIONS` | `2` | Panel geographic diversity review | Minimum regions on normative panel |
| `NORMATIVE_PANEL_ORGS` | `2` | Panel organizational diversity review | Minimum orgs on normative panel |
| `COMMITMENT_COMMITTEE (n,t)` | `(15,10)` | Signature latency failures, signer compromise risk, or liveness failures | Constitutional decision certification |
| `KEY_ROTATION` | `90 days` | Key compromise event or audit finding | Mandatory signing-key rotation interval |
| `COMMISSION_FLOOR` | `0.02` (2%) | Constitutional amendment only | Minimum commission rate |
| `COMMISSION_CEILING` | `0.10` (10%) | Constitutional amendment only | Maximum commission rate |
| `COMMISSION_SAFETY_MARGIN` | `1.3` | Constitutional amendment only | Multiplier over bare operational costs — prevents capture by ballot |
| `COMMISSION_RESERVE_TARGET_MONTHS` | `6` | Constitutional amendment only | Reserve fund target (months of operational costs) — prevents depletion by ballot |
| `COMMISSION_MIN_FEE` | `5 USDC equiv` | Constitutional amendment only | Minimum per-transaction fee — prevents below-cost transactions by ballot |
| `COMMISSION_WINDOW_DAYS` | `90` | Constitutional amendment only | Rolling window duration for commission computation |
| `COMMISSION_WINDOW_MIN_MISSIONS` | `50` | Constitutional amendment only | Minimum sample size for statistical reliability |
| `COMMISSION_BOOTSTRAP_MIN_RATE` | `0.05` (5%) | Constitutional amendment only | Bootstrap period minimum rate — auto-expires when window fills |
| `COMMISSION_RESERVE_MAINTENANCE_RATE` | `0.005` (0.5%) | Constitutional amendment only | Reserve maintenance rate when target is met |
| `CREATOR_ALLOCATION_RATE` | `0.05` (5%) | Constitutional amendment only | Worker-side creator allocation — 5% of worker's post-commission payment |
| `EMPLOYER_CREATOR_FEE_RATE` | `0.05` (5%) | Constitutional amendment only | Employer-side creator allocation — 5% of mission reward, staked in escrow |
| `ACCEPTED_CURRENCIES` | `BTC, ETH, USDC, USDT` | Governance ballot | Accepted settlement currencies |
| `VOLATILITY_TOPUP_THRESHOLD` | `0.20` (20%) | Governance ballot | Volatile-stake top-up trigger |
| `ESCROW_HOLD_PERIOD` | `48 hours` | Governance ballot | Post-completion dispute window |
| `MIN_MISSION_REWARD` | `10 USDC equiv` | Governance ballot | Minimum mission reward |
| `ENHANCED_KYC_THRESHOLD` | `10000 USDC equiv` | Governance ballot | Enhanced identity verification threshold |

Review protocol:
1. No parameter change is valid without multi-chamber verified-human ratification.
2. Every approved parameter change must be versioned, signed, and committed on-chain.
3. Emergency parameter changes expire automatically in 30 days unless ratified.

Calibration protocol (mandatory before production and at quarterly review):
1. Build replay datasets from completed missions across each risk tier (`R0`, `R1`, `R2`).
2. Run adversarial simulations for collusion, throughput gaming, low-quality flooding, and identity-farming paths.
3. Evaluate parameter sensitivity for:
- quality gates (`Q_min_H`, `Q_min_M`),
- trust weights (`w_Q`, `w_R`, `w_V`),
- re-certification thresholds,
- decommission thresholds.
4. Reject any parameter proposal that increases high-risk false-accept rate or weakens anti-capture guarantees.
5. Publish a calibration report containing:
- dataset composition,
- simulation assumptions,
- candidate parameter sets,
- selected set with rationale,
- rollback path.
6. Apply only after constitutional ratification and on-chain versioned parameter publication.

Executable governance artifacts:
1. Machine-readable parameter mirror: `config/constitutional_params.json`.
2. Runtime tier policy map: `config/runtime_policy.json`.
3. Invariant checks: `python3 tools/check_invariants.py`.
4. Worked-example verification: `python3 tools/verify_examples.py`.

## Genesis bootstrap protocol (constitutional)

The constitutional governance model requires chamber sizes, geographic diversity, and organizational breadth that cannot exist at network launch. This creates a cold-start problem. The genesis protocol solves it with a phased, time-bounded escalation from founder authority to full constitutional governance.

### Genesis phases

1. Phase G0 — Founder stewardship (0 to 50 verified humans):
- The founder (or a small founding group of up to 5 verified humans) holds provisional governance authority.
- During the pre-sustainability bootstrap phase, the founder retains transparent veto authority over all governance and operational decisions. Every exercise of veto authority is logged, signed, and committed on-chain with the tag `founder_veto`. This veto authority expires automatically and irrevocably at First Light — the moment the system achieves financial sustainability (revenue ≥ 1.5× costs AND 3-month reserve). A self-sustaining system no longer needs a single person holding emergency powers. The veto is a rejection-only power: the founder can block proposals but cannot force them through.
- All governance decisions made during G0 are logged, signed, and committed on-chain with the tag `genesis_provisional`.
- No constitutional amendments are permitted during G0. The founding constitution is frozen.
- Operational risk tiers R0 and R1 are active. R2 operates with reduced reviewer requirements (see genesis parameter overrides below). R3 (constitutional changes) is locked.
- Trust minting operates normally under standard quality gates.
- G0 expires automatically at `G0_MAX_DAYS = 365` days. If 50 verified humans have not been reached, the founder must publish a public status report and the deadline extends by `G0_EXTENSION_DAYS = 180` days (once only).

2. Phase G1 — Provisional chambers (50 to 500 verified humans):
- Constitutional governance activates with reduced chamber sizes:
  - Provisional proposal chamber: `nP_g1 = 11`, pass threshold `kP_g1 = 8` (>2/3).
  - Provisional ratification chamber: `nR_g1 = 17`, pass threshold `kR_g1 = 12` (>2/3).
  - Provisional challenge chamber: `nC_g1 = 25`, pass threshold `kC_g1 = 15` (3/5).
- Geographic constraints are relaxed:
  - Minimum regions per chamber: `R_min_g1 = 3`.
  - Maximum region share: `c_max_g1 = 0.40`.
- All other constitutional rules apply (human-only voting, constrained-random assignment, non-overlap, conflict recusal).
- The fast-elevation quorum is reduced: `q_h_g1 = 7`, `r_h_g1 = 2`, `o_h_g1 = 2`.
- G1 expires automatically at `G1_MAX_DAYS = 730` days from genesis. Transition to G2 requires reaching 500 verified humans OR the expiry deadline, whichever comes first.
- All G0 provisional decisions are automatically submitted for G1 ratification within `G0_RATIFICATION_WINDOW = 90` days of G1 activation. Any G0 decision not ratified is reversed.

3. Phase G2 — Scaled chambers (500 to 2000 verified humans):
- Chamber sizes increase to intermediate values:
  - Proposal chamber: `nP_g2 = 21`, pass threshold `kP_g2 = 14` (2/3).
  - Ratification chamber: `nR_g2 = 31`, pass threshold `kR_g2 = 21` (2/3).
  - Challenge chamber: `nC_g2 = 51`, pass threshold `kC_g2 = 31` (3/5).
- Geographic constraints tighten:
  - Minimum regions: `R_min_g2 = 5`.
  - Maximum region share: `c_max_g2 = 0.25`.
- Fast-elevation quorum scales: `q_h_g2 = 15`, `r_h_g2 = 3`, `o_h_g2 = 3`.

4. Phase G3 — Full constitutional governance (2000+ verified humans):
- Full chamber sizes activate as defined in the main constitution (`nP=41, nR=61, nC=101`).
- Full geographic constraints activate (`R_min=8, c_max=0.15`).
- Full fast-elevation quorum activates (`q_h=30*, r_h=3, o_h=3`).
- Genesis protocol terminates. All subsequent governance is fully constitutional.

### Genesis invariants (non-negotiable at every phase)

1. Machine constitutional voting weight remains `w_M_const = 0` at all genesis phases.
2. Trust cannot be bought, sold, or transferred at any genesis phase.
3. Quality gates for trust minting are active from day one.
4. All governance actions are signed, committed on-chain, and publicly auditable from day one.
5. No genesis phase may extend indefinitely; all have hard time limits.
6. The founder has no constitutional veto power once First Light is achieved.
7. Every G0 provisional decision must face retroactive ratification in G1.
8. Phase transitions are one-way; the system cannot regress to an earlier genesis phase.

### Genesis phase determination formula

The active genesis phase is determined by:
- Let `N_H` = count of verified human identities with `T_H >= T_floor_H`.
- If `N_H < 50`: phase = G0.
- If `50 <= N_H < 500`: phase = G1.
- If `500 <= N_H < 2000`: phase = G2.
- If `N_H >= 2000`: phase = G3 (full constitution).

Time-limit overrides:
- If G0 duration exceeds `G0_MAX_DAYS + G0_EXTENSION_DAYS` and `N_H < 50`, the network must be publicly declared non-viable and shut down or restructured with a new genesis.

### First Light

"First Light" is the named transition event marking Genesis's passage from Proof of Concept to live operations. First Light is a **financial sustainability trigger**, not a headcount counter. It fires when BOTH conditions are met:

1. Projected monthly commission revenue >= `sustainability_ratio` × monthly operating costs (default `sustainability_ratio = 1.5`, i.e. a 50% safety buffer), sustained over the commission engine's rolling window.
2. Reserve fund balance >= `reserve_months_required` × monthly operating costs (default `reserve_months_required = 3`).

First Light is **decoupled from governance phase transitions** (G0→G1→G2→G3), which remain headcount-based. First Light could fire before or after G0→G1. In practice, revenue requires mission volume which requires verified human users, so the two will roughly correlate — but they are structurally independent events.

Only verified human activity drives the mission volume that generates commission revenue. Machine registrations do not contribute to the First Light calculation.

At First Light:

1. The PoC mode banner is removed from all platform pages.
2. Demonstration data is replaced with live marketplace operations.
3. The event is logged as `EventKind.FIRST_LIGHT` in the audit trail.
4. The event is committed to L1 as a constitutional lifecycle event.

Note: The founder's veto authority expires at First Light (the financial sustainability trigger). This is an outcome-based expiry — the system proves it can sustain itself, and emergency powers are no longer needed. Constitutional governance activation (chamber sizes, geographic requirements) remains tied to the G0→G1→G2→G3 phase transitions, which are headcount-based.

First Light is irreversible — once both conditions are met and the event is logged, the platform cannot revert to PoC mode.

### Dormancy and founder's legacy

If the founder's accumulated creator allocation remains unclaimed for 50 continuous years of account inactivity, the following process activates. This is the founder's stated living legacy — public, visible, and constitutional.

**Dormancy trigger:**

1. The dormancy trigger fires automatically on-chain. No ballot, no quorum, and no governance action is required to initiate the process.
2. Inactivity is defined as the absence of any cryptographically signed action from the founder's verified Genesis identity. Any signed action (login, transaction, governance action, or explicit proof-of-life attestation) resets the 50-year dormancy counter.
3. The founder's verified Genesis identity — not a hardware wallet or physical token — serves as the proof-of-activity mechanism. Identity recovery, if needed, follows the platform's standard trust-adjudication process (quorum of high-trust members, blind, diverse).

**Multi-source time verification (metrology consensus):**

4. The 50-year elapsed time must be independently verified against a minimum of 3 internationally recognised time authorities plus Ethereum block timestamps before the dormancy trigger fires. Mandatory sources include:
   - NIST (National Institute of Standards and Technology, United States)
   - PTB (Physikalisch-Technische Bundesanstalt, Germany)
   - BIPM/NPL (Bureau International des Poids et Mesures / National Physical Laboratory, United Kingdom — the definitive sources for Coordinated Universal Time)
   - Ethereum blockchain (block timestamps and cumulative block count from the last founder-signed action)
5. All sources must agree on elapsed time within a tolerance of ±24 hours. If any source disagrees by more than 1 year, the trigger halts — fail-closed. The dormancy event does not fire until consensus is re-established.
6. No single time source can trigger the dormancy event. This multi-source consensus requirement is a constitutional invariant.

**Recipient selection:**

7. Eligible recipient organisations are nominated by any verified human member. Nominees must meet the founder's stated criteria: dedicated to using science for human betterment and the alleviation of human suffering.
8. A 3-chamber supermajority vote of high-trust members selects the recipient organisations from the nominated pool. The vote is constrained by the founder's criteria — organisations that do not demonstrably meet the criteria are ineligible regardless of vote count.
9. The accumulated allocation is distributed among the selected organisations. All disbursements are anonymous.

**Perpetuity:**

10. After the initial 50-year distribution, the process repeats annually in perpetuity: nomination, supermajority vote, distribution.
11. This provision applies only to the founder's creator allocation. It does not affect other actors' earnings or the platform's operational funds.
12. Smart contract implementation uses a time-locked distribution trigger with a governance gate, designed to be tamper-resistant and independently verifiable. The constitutional commitment is binding regardless of implementation timeline.

## Progressive commitment strategy (constitutional)

Ethereum L1 hourly commitments are specified as the production target. However, L1 gas costs are variable and may be prohibitive during early operation. The commitment strategy must be economically sustainable without compromising integrity.

### Commitment tiers

1. Tier C0 — Genesis and early operation (`N_H < 500`):
- Primary commitment layer: `L2_COMMITMENT_CHAIN` (any EVM-compatible L2 rollup that settles to Ethereum L1, e.g., Arbitrum, Optimism, Base).
- L2 commitment cadence: every `EPOCH = 1 hour` (same as production spec).
- L1 anchor cadence: batched L1 anchor commitment every `L1_ANCHOR_INTERVAL_C0 = 24 hours`.
- L1 anchor payload: `SHA256(concatenation of all L2 commitment hashes in the anchor window)` plus latest constitutional state root.
- Constitutional lifecycle events (proposal pass, ratification pass, challenge close, amendment activation) are committed to L1 immediately regardless of tier.

2. Tier C1 — Growth phase (`500 <= N_H < 5000`):
- L2 commitment cadence: every `1 hour`.
- L1 anchor cadence: every `L1_ANCHOR_INTERVAL_C1 = 6 hours`.
- Constitutional lifecycle events: immediate L1 commitment.

3. Tier C2 — Production (`N_H >= 5000`):
- Full L1 commitment every `1 hour` as specified in the main constitution.
- Constitutional lifecycle events: immediate L1 commitment.

### Commitment integrity invariants

1. At every tier, all commitment payloads use the same schema, hash function, signature suite, and Merkle rules as the production spec.
2. L2 commitments must be independently verifiable using the same public verifier tooling.
3. The L2 rollup must settle to Ethereum L1; no independent L1 chains are permitted as primary settlement.
4. L1 anchor commitments must include a chained hash linking all L2 commitments in the anchor window, so that any L2 commitment can be proven as included in the L1 anchor.
5. Transition between commitment tiers is automatic based on `N_H` and is logged on-chain.
6. No commitment tier reduces the cryptographic strength of any commitment; only the L1 publication frequency changes.

### Cost projection (conservative estimates)

At current L2 fee levels (2026):
- L2 commitment: `$0.01-$0.10` per transaction.
- Daily L2 cost (24 hourly commits): `$0.24-$2.40`.
- Daily L1 anchor (1 per day at C0): `$2-$20` depending on gas.
- Monthly total at C0: `$70-$680` (well within zero-budget envelope).

## Reviewer heterogeneity requirements (constitutional)

Independent review must be orthogonal, not merely numerous. Correlated errors across reviewers sharing identical model families, training data, or reasoning methods can defeat consensus-based verification even with high reviewer counts.

### Heterogeneity rules by risk tier

1. R0 (low risk):
- No heterogeneity constraint. Single reviewer is sufficient.

2. R1 (moderate risk):
- Reviewers must not share the same `model_family` identifier (e.g., both using GPT-4o, or both using Claude Opus).
- If all available reviewers share a model family, one reviewer may be substituted with a deterministic/rule-based check or a human reviewer.

3. R2 (high risk):
- At least `H_R2_MODEL_FAMILIES = 2` distinct model families must be represented among the 5 reviewers.
- At least `H_R2_METHOD_TYPES = 2` distinct verification method types must be used. Method types are: `reasoning_model`, `retrieval_augmented`, `rule_based_deterministic`, `human_reviewer`.
- Evidence bundles must include intermediate reasoning artifacts, not only final judgments.

4. R3 (constitutional):
- Human-only. Model heterogeneity is not applicable; constitutional voting diversity is enforced through geographic and organizational constraints.

### Reviewer metadata requirements

Every reviewer record must include:
1. `reviewer_id`
2. `model_family` (for machine reviewers) or `"human"` (for human reviewers)
3. `method_type`: one of `reasoning_model`, `retrieval_augmented`, `rule_based_deterministic`, `human_reviewer`
4. `region`
5. `organization`

### Anti-monoculture design test

Design test: Can all reviewers on an R2 task share the same model family and verification method? If yes, reject design.

## Subjective and normative dispute resolution protocol (constitutional)

Consensus-based verification works for objective, testable claims. It is structurally unreliable for subjective, interpretive, ethical, or normative questions where reasonable people can legitimately disagree. Genesis must handle both domains without pretending consensus resolves the latter.

### Domain classification requirement

Every mission must be classified at intake with a `domain_type`:

1. `objective`: the task has testable, reproducible acceptance criteria (e.g., "does this code compile?", "does this calculation match the input data?").
2. `normative`: the task involves interpretation, ethical judgment, policy framing, or value-laden assessment (e.g., "is this risk assessment balanced?", "is this policy recommendation fair?").
3. `mixed`: the task contains both objective and normative components.

### Resolution rules by domain type

1. `objective` tasks:
- Standard reviewer consensus applies.
- Disagreement resolved by evidence sufficiency and reproducibility.

2. `normative` tasks:
- Reviewer consensus is advisory, not dispositive.
- Final resolution requires human adjudication.
- The human adjudicator must document the reasoning basis for the decision.
- The adjudication record must include: the advisory reviewer positions, the human decision, and the stated rationale.
- No normative task may be closed as `Completed` without a signed human adjudication record.

3. `mixed` tasks:
- Objective components are resolved by reviewer consensus.
- Normative components are escalated to human adjudication.
- The task cannot close until both resolution paths are satisfied.

### Dispute escalation triggers

A normative dispute is automatically escalated if:
1. Reviewer agreement is below `NORMATIVE_AGREEMENT_THRESHOLD = 0.60` (i.e., fewer than 60% of reviewers agree).
2. Any reviewer flags the task as `normative_dispute`.
3. The mission owner flags the task as `normative_dispute`.

### Normative adjudication panel (for R2 tasks)

For R2 normative disputes:
1. A panel of `NORMATIVE_PANEL_SIZE = 3` independent human adjudicators is assembled.
2. Panel members must span at least `NORMATIVE_PANEL_REGIONS = 2` regions and `NORMATIVE_PANEL_ORGS = 2` organizations.
3. Panel decision is by majority.
4. Dissenting opinions are recorded and published with the decision.
5. The panel decision is final for that task instance but does not set binding precedent for future tasks (each normative decision is case-specific).

### Design tests for subjective resolution

1. Can a normative task be closed by machine consensus alone without human adjudication? If yes, reject design.
2. Can a normative adjudication occur without documented reasoning? If yes, reject design.
3. Can a normative panel be assembled from a single region or organization? If yes, reject design.

## Design tests (must pass)

1. Can an identity pay to gain trust? If yes, reject design.
2. Can trust be transferred or sold? If yes, reject design.
3. Can trust rise without verified evidence? If yes, reject design.
4. Can severe proven misconduct avoid trust loss? If yes, reject design.
5. Can trust decisions occur without audit trail? If yes, reject design.
6. Can machine trust be converted into constitutional voting rights? If yes, reject design.
7. Can one high-throughput actor gain constitutional influence without meeting `delta_fast`, `q_h`, `r_h`, and `o_h` validation thresholds? If yes, reject design.
8. Can a steward group amend constitutional text alone? If yes, reject design.
9. Can a constitutional vote pass without meeting geographic diversity thresholds? If yes, reject design.
10. Can a constitutional vote pass without independent chamber non-overlap? If yes, reject design.
11. Can any identity exceed the configured trust caps? If yes, reject design.
12. Can trust be used to command or control other actors directly? If yes, reject design.
13. Can financial resources increase constitutional influence? If yes, reject design.
14. Can human trust decay below `T_floor_H`? If yes, reject design.
15. Can trust be minted without cryptographic proof-of-trust evidence? If yes, reject design.
16. Can proof-of-work evidence alone mint trust? If yes, reject design.
16a. Can proof-of-effort alone (without meeting quality gate) mint trust? If yes, reject design.
16b. Can an actor earn effort credit exceeding `E_max_credit`? If yes, reject design.
16c. Can effort thresholds decrease as risk tier increases? If yes, reject design.
17. Can constitutional chambers form without constrained-random geographic assignment constraints? If yes, reject design.
18. Can highest-trust actors unilaterally ratify constitutional changes? If yes, reject design.
19. Does any constitutional voting path assign non-zero machine voting weight (`w_M_const > 0`)? If yes, reject design.
20. Can constrained-random assignment run without a publicly auditable pre-committed randomness source? If yes, reject design.
21. Can a `DeltaT > delta_fast` event activate without meeting `q_h`, `r_h`, and `o_h` validation thresholds? If yes, reject design.
22. Can a machine identity with `T_M = 0` bypass quarantine and access privileged operations? If yes, reject design.
23. Can machine identity reset or key rotation be used to bypass zero-trust lineage controls? If yes, reject design.
24. Can trust increase when `Q_H < Q_min_H` or `Q_M < Q_min_M`? If yes, reject design.
25. Can high output volume compensate for failing quality gate thresholds? If yes, reject design.
26. Can a machine remain at `T_M = 0` beyond decommission thresholds and still retain active status? If yes, reject design.
27. Can a decommissioned machine identity regain privileged access without full re-entry controls? If yes, reject design.
28. Can identity-signal tests alone grant trust or constitutional authority? If yes, reject design.
29. Can the system operate without a defined genesis phase when participant count is below full constitutional thresholds? If yes, reject design.
30. Can a genesis phase extend indefinitely without a hard time limit? If yes, reject design.
31. Can the founder retain veto power after First Light is achieved? If yes, reject design.
32. Can G0 provisional decisions survive without retroactive ratification in G1? If yes, reject design.
33. Can the system regress from a later genesis phase to an earlier one? If yes, reject design.
34. Can all reviewers on an R2 task share the same model family and verification method? If yes, reject design.
35. Can a normative task be closed by machine consensus alone without human adjudication? If yes, reject design.
36. Can a normative adjudication occur without documented reasoning? If yes, reject design.
37. Can L1 commitment integrity be reduced at any commitment tier (C0/C1/C2)? If yes, reject design.
38. Can the commission rate exceed `COMMISSION_CEILING`? If yes, reject design.
39. Can the commission rate be adjusted without a mandatory published cost breakdown? If yes, reject design.
39a. Can the commission rate be set or changed by human ballot, governance vote, or any mechanism other than deterministic formula computation? If yes, reject design.
39b. Can the commission rate be computed without a rolling window of at least `COMMISSION_WINDOW_MIN_MISSIONS` completed missions or the bootstrap protocol? If yes, reject design.
40. Can commission revenue, escrow amounts, or payment history influence trust scores, allocation ranking, or governance weight? If yes, reject design.
41. Can the commission floor or ceiling be changed without a full constitutional amendment? If yes, reject design.
42. Can a mission listing go live without confirmed escrow? If yes, reject design.
43. Can a Genesis-branded token be created? If yes, reject design.
44. Can a work poster avoid legal compliance screening? If yes, reject design.
45. Can the GCF contribution rate be changed without 4/5 supermajority + 50% participation + 90-day cooling-off + confirmation vote? If yes, reject design.

## Working interpretation for all future specs

When in doubt:
- Choose legitimacy over speed.
- Choose evidence over volume.
- Choose earned trust over purchased influence.
- Choose measurable risk reduction over absolute claims.

## Blockchain Anchoring Record

This constitution is anchored on-chain. The anchoring event creates permanent, tamper-evident proof that this document existed in its exact form at the recorded time.

Blockchain anchoring is not a smart contract. No code executes on-chain. The SHA-256 hash of this document is embedded in the `data` field of a standard Ethereum transaction. The blockchain serves as a public, immutable witness.

### Genesis Block 7 — Narrative alignment + comprehensive docs update

| Field | Value |
|---|---|
| Document | `TRUST_CONSTITUTION.md` |
| SHA-256 | `29abc8a6cb726b5fcef02314e4d67be97d2366e577b7d2f7c758242dc1ed8bca` |
| Chain | Ethereum Sepolia (Chain ID 11155111) |
| Block | 10287422 |
| Sender | [`0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE`](https://sepolia.etherscan.io/address/0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE) |
| Transaction | [`efd7fd2ab875773ce626b15c4b2becd6248b1c5db65012a2ed413cccdecd264c`](https://sepolia.etherscan.io/tx/efd7fd2ab875773ce626b15c4b2becd6248b1c5db65012a2ed413cccdecd264c) |
| Anchored | 2026-02-18T18:04:12Z |

**Independent verification:**

The hash above corresponds to the version of this document that was anchored on-chain. The anchoring section itself was updated after anchoring to record the transaction details, so `shasum -a 256 TRUST_CONSTITUTION.md` on the current file will produce a different hash. To verify the anchor, check the transaction on [Etherscan](https://sepolia.etherscan.io/tx/efd7fd2ab875773ce626b15c4b2becd6248b1c5db65012a2ed413cccdecd264c) and confirm the Input Data field contains `29abc8a6cb726b5fcef02314e4d67be97d2366e577b7d2f7c758242dc1ed8bca`. The git history preserves the exact file state that produced this hash.

### Genesis Block 6 — Constitutional infrastructure for a functioning economy

| Field | Value |
|---|---|
| Document | `TRUST_CONSTITUTION.md` |
| SHA-256 | `4d71a0eabe9fc76e6b70c0acc4e24b37ef7e6b9ccf9c9d170cacd19814dcb284` |
| Chain | Ethereum Sepolia (Chain ID 11155111) |
| Block | 10282284 |
| Sender | [`0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE`](https://sepolia.etherscan.io/address/0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE) |
| Transaction | [`c8ef384a819925b9aa8909685d5d0179b1233303a9e06374b206fb067b438a8c`](https://sepolia.etherscan.io/tx/c8ef384a819925b9aa8909685d5d0179b1233303a9e06374b206fb067b438a8c) |
| Anchored | 2026-02-17T23:57:49Z |

### Genesis Block 5 — Lifecycle wiring + Genesis Block naming

| Field | Value |
|---|---|
| Document | `TRUST_CONSTITUTION.md` |
| SHA-256 | `f2c5381d48b3c467341997b69916aaa82d30d5f160982b69a09942f3a16865c8` |
| Chain | Ethereum Sepolia (Chain ID 11155111) |
| Block | 10275625 |
| Sender | [`0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE`](https://sepolia.etherscan.io/address/0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE) |
| Transaction | [`8d2152dc5f6f51c35d7f0b5b4624377b3e9c178c4fa4851d4eba7a650064df6d`](https://sepolia.etherscan.io/tx/8d2152dc5f6f51c35d7f0b5b4624377b3e9c178c4fa4851d4eba7a650064df6d) |
| Anchored | 2026-02-17T00:02:48Z |

**Independent verification:**

The hash above corresponds to the version of this document that was anchored on-chain. The anchoring section itself was updated after anchoring to record the transaction details, so `shasum -a 256 TRUST_CONSTITUTION.md` on the current file will produce a different hash. To verify the anchor, check the transaction on [Etherscan](https://sepolia.etherscan.io/tx/8d2152dc5f6f51c35d7f0b5b4624377b3e9c178c4fa4851d4eba7a650064df6d) and confirm the Input Data field contains `f2c5381d48b3c467341997b69916aaa82d30d5f160982b69a09942f3a16865c8`. The git history preserves the exact file state that produced this hash.

### Genesis Block 4 — First Light sustainability + machine registration

| Field | Value |
|---|---|
| Document | `TRUST_CONSTITUTION.md` |
| SHA-256 | `1633cb2d001c230a4e752417427dc9fccf6cb6af058cb38e5cabf8cab7804f91` |
| Chain | Ethereum Sepolia (Chain ID 11155111) |
| Block | 10273917 |
| Sender | [`0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE`](https://sepolia.etherscan.io/address/0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE) |
| Transaction | [`5b8ab0e1a8925807e0b16552735adc0564b876d1c16e59b9919436eeafd65aac`](https://sepolia.etherscan.io/tx/5b8ab0e1a8925807e0b16552735adc0564b876d1c16e59b9919436eeafd65aac) |
| Anchored | 2026-02-16 |

### Genesis Block 3 — Creator provisions + 50-year founder legacy

| Field | Value |
|---|---|
| Document | `TRUST_CONSTITUTION.md` |
| SHA-256 | `b9981e3e200665a4ce38741dd37165600dea3f504909e55f6dd7f7c0e9d45393` |
| Chain | Ethereum Sepolia (Chain ID 11155111) |
| Block | 10272673 |
| Sender | [`0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE`](https://sepolia.etherscan.io/address/0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE) |
| Transaction | [`eb0b0e6970c31c3c16cdc60f22431ca0e594eb754a401956303473ba4d4a4896`](https://sepolia.etherscan.io/tx/eb0b0e6970c31c3c16cdc60f22431ca0e594eb754a401956303473ba4d4a4896) |
| Anchored | 2026-02-16 |

### Genesis Block 2 — Compensation model

| Field | Value |
|---|---|
| Document | `TRUST_CONSTITUTION.md` |
| SHA-256 | `e941df98b2c4d4b8bd7eafc8897d0351b80c482221e81bd211b07c543b3c8dcd` |
| Chain | Ethereum Sepolia (Chain ID 11155111) |
| Block | 10271157 |
| Sender | [`0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE`](https://sepolia.etherscan.io/address/0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE) |
| Transaction | [`fde734ddf3480724ccc572330be149692d766d6ba5648dbc9d2cd2f18020c83a`](https://sepolia.etherscan.io/tx/fde734ddf3480724ccc572330be149692d766d6ba5648dbc9d2cd2f18020c83a) |
| Anchored | 2026-02-16 |

### Genesis Block 1 — The first constitutional anchoring

| Field | Value |
|---|---|
| Document | `TRUST_CONSTITUTION.md` |
| SHA-256 | `33f2b00386aef7e166ce0e23f082a31ae484294d9ff087ddb45c702ddd324a06` |
| Chain | Ethereum Sepolia (Chain ID 11155111) |
| Block | 10255231 |
| Sender | [`0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE`](https://sepolia.etherscan.io/address/0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE) |
| Transaction | [`031617e394e0aee1875102fb5ba39ad5ad18ea775e1eeb44fd452ecd9d8a3bdb`](https://sepolia.etherscan.io/tx/031617e394e0aee1875102fb5ba39ad5ad18ea775e1eeb44fd452ecd9d8a3bdb) |
| Anchored | 2026-02-13T23:47:25Z |

**Important:** All seven Genesis Blocks are valid and independently verifiable. Each is a constitutional anchoring event — cryptographic proof that the rules were committed before any user existed to lobby for changes. Genesis Block 1 records the earliest version of the constitution. Genesis Block 2 proves the compensation model. Genesis Block 3 proves the creator allocation and 50-year legacy clause. Genesis Block 4 proves First Light sustainability and machine registration. Genesis Block 5 proves the lifecycle wiring and Genesis Block naming convention. Genesis Block 6 proves the Genesis Common Fund, harmful work prevention, three-tier justice system, and workflow orchestration. Genesis Block 7 (current) captures narrative alignment and comprehensive documentation update. The full trust mint log is maintained in [`docs/ANCHORS.md`](docs/ANCHORS.md).

## Documentation stop rule

To prevent document sprawl:
1. This constitution is the only canonical source for parameter defaults.
2. New docs are not created for parameter changes; existing canonical sections are updated in place.
3. A new standalone doc is allowed only for a new cryptographic primitive, a new constitutional chamber, or a new legal-risk class.

\* subject to review
