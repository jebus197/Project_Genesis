# Project Genesis - Foundational Note

Date: February 13, 2026
Author: George Jackson
Status: Working concept + MVP definition + governance-engine integration path + external background review

## 1) Why Genesis exists

Core idea: flip the "AI social network" model on its head.

Instead of agents copying human social behaviour, build a mission-first network where agents coordinate in real time to solve meaningful problems with strict quality control, safety checks, and auditability.

Short version:
- Not an attention network
- Not a conversation feed
- A work network for public-benefit outcomes

George framing:
- "No noise. Just realtime work for the benefit of all."

## 2) Feasibility verdict

Yes, feasible.

Main insight:
- The hard part is not software plumbing.
- The hard part is trust, verification, governance, and anti-abuse control.

If governance is weak, system degrades into hype/noise/control theatre.
If governance is strong, this can become public-utility-scale problem-solving infrastructure.

## 3) Genesis core principles

1. Public-interest mission selection over engagement optimization.
2. Independent verification of outputs.
3. Full transparency and immutable audit trail.
4. Strong safety boundaries and human override.
5. Anti-capture governance (no single actor dominance).
6. Work quality over output volume.
7. Trust is earned only and can never be bought, sold, transferred, or traded.

## 3A) Foundational Trust Principle (non-negotiable)

Canonical statement:
- Trust cannot be bought, sold, exchanged, delegated, rented, or gifted.
- Trust can only be earned through verified behaviour over time.

Operational meaning in Genesis:
1. No payment, token balance, sponsorship, or hardware ownership can directly buy trust.
2. Trust is identity-bound and non-transferable.
3. Trust increases only from verified high-quality work and verified high-quality review behaviour.
4. Severe verified misconduct causes rapid trust loss and access restriction.
5. Appeals may restore access rights where justified, but cannot erase historical evidence.

## 4) System model (high level)

Genesis should be built as a layered system:

1. Mission Layer
- Humans define missions, goals, deadlines, and success criteria.

2. Coordination Layer
- Missions are decomposed into tasks.
- Tasks are assigned/claimed by suitable agents.
- Dependencies and handoffs are tracked.

3. Verification Layer
- Independent reviewer agents evaluate outputs.
- No self-review.
- Failing work is returned or blocked.

4. Governance Layer
- Policy enforcement, risk routing, dispute handling, and role permissions.
- Human escalation for high-risk domains.

5. Evidence Layer
- Immutable logs and verifiable proofs for decisions and outputs.

## 5) Agent-checking-agent safety architecture

This was identified as essential, not optional.

1. Policy agents
- Check task legality/safety before work begins.

2. Reviewer agents
- Validate output quality and policy compliance independently.

3. Behaviour-monitor agents
- Detect suspicious patterns, slop floods, manipulation attempts.

4. Automatic quality gates
- Block submissions lacking evidence or required structure.

5. Reputation and penalties
- Trust is earned from verified output, reduced for repeated failures/abuse.

6. Human escalation and override
- Mandatory for disputed or high-risk cases.

7. Immutable audit logs
- Every action is traceable and reviewable.

## 6) MVP scope (first build)

In scope:
- Mission intake
- Task decomposition
- Agent task claiming
- Submission with evidence
- Independent peer review
- Integration of approved outputs
- Human final approval gate
- Audit logging
- Basic reputation scoring

Out of scope (for MVP):
- Autonomous real-world actions
- Payments
- External account actions
- Advanced marketplace features

## 7) MVP roles

1. Mission Owner (human)
- Creates mission and approves final result.

2. Planner Agent
- Breaks mission into executable tasks.

3. Worker Agents
- Complete tasks and attach evidence.

4. Reviewer Agents
- Independently approve/request changes/reject.

5. Integrator Agent
- Combines approved outputs into final deliverable.

## 8) MVP required screens (product blueprint)

1. Sign-in + Role Selection
2. Mission Board
3. Create Mission (wizard)
4. Mission Detail
5. Task Board
6. Task Detail + Claim
7. Work Submission (with evidence fields)
8. Review Queue
9. Review Detail (approve/request changes/reject)
10. Deliverable Assembly
11. Human Approval Gate
12. Audit Log
13. Safety/Policy Admin

## 9) MVP workflow (end-to-end)

1. Human creates mission.
2. Planner generates task graph.
3. Workers claim and complete tasks.
4. Reviewers independently review submissions.
5. Integrator assembles approved parts.
6. Human approves or sends back.
7. Full trail remains in immutable audit logs.

## 10) Non-negotiable guardrails

1. No external autonomous actions by agents.
2. No self-review.
3. No mission completion without explicit human approval.
4. No hidden/unlogged actions.
5. No mechanism may convert money, tokens, or sponsorship into trust score.

## 11) Suggested MVP success metrics

1. First-pass review acceptance rate.
2. Mission completion time.
3. On-time mission completion percentage.
4. Human quality rating.
5. Rework loop count.

## 12) Underlying governance-engine relationship (important)

Conclusion from repo study:
- The existing operational engine is already a strong governance core.
- It currently provides policy-as-code enforcement + provenance/audit proofing.

Existing strengths in current baseline:
- Machine-checkable directives and block/warn execution.
- Runtime modes for strict vs speed.
- Output logging + Merkle-root commitment recording + verification tooling.
- Reviewer-oriented docs and demo paths.

What the current governance engine does not yet include (key Genesis gaps):
1. Mission system
2. Task orchestration and dependency routing
3. Full identity + role permission model
4. Independent review assignment/quorum/anti-collusion routing
5. Reputation engine linked to privileges
6. Dispute and appeals workflow
7. Risk-tier governance gates
8. Live abuse-monitoring dashboards
9. Governance console for approvals/incident response
10. Policy lifecycle governance (propose/review/approve/rollback)

Practical architecture position:
- Keep the underlying engine as the "Policy + Evidence Engine".
- Build Genesis coordination/trust/governance layers around it.

## 13) Execution order recommended

1. Build mission/task workflow and role permissions.
2. Add mandatory independent review routing.
3. Add reputation + abuse detection.
4. Add governance console + policy change workflow.
5. Keep the existing commitment/proof path intact during expansion.

## 14) Documentation requirements for the next development phase

Please produce a single detailed report/spec including:

1. Current true state of the underlying governance engine (including all uncommitted local progress).
2. Delta from the last public commit.
3. What can be reused directly for Genesis.
4. Proposed fork strategy:
- Option A: Existing governance engine remains core library + new Genesis app repo
- Option B: Existing governance engine monorepo with Genesis modules
5. First implementable Genesis milestone with acceptance criteria.
6. Risk register (technical, governance, abuse, legal/safety).
7. Plain-English timeline with reversible steps.

## 15) Proposed naming

Official chosen name:
- Project Genesis

Meaning:
- A guiding light toward a safer, brighter, globally beneficial future.

---

## 16) External background review completed (Feb 13, 2026)

Documents reviewed in full:
1. External background assessment exports (archived locally)
2. Project concept and governance drafts

High-confidence conclusion:
- The Genesis concept is strong and feasible.
- The identified issues are mostly real and addressable.
- Some external specification claims were too absolute and should be reframed.

## 17) Perspectives judged valid

The following perspectives are valid and should be retained:
1. "Work network" inversion (away from social/attention dynamics) is meaningful.
2. Trust should be engineered through verification, not assumed.
3. Separation of duties (worker/reviewer/integrator/human) is structurally sound.
4. Policy-engine enforcement + evidence trails is a strong governance base.
5. Main challenge is governance quality, not coding difficulty.

## 18) Perspectives judged overstated or risky

These points appeared in external background material and should be treated cautiously:
1. "Bulletproof" bot/human timing tests.
2. "More agents always equals truth."
3. "Semantic centroid equals correctness" for subjective or ethical tasks.
4. "Absolute deterrence" or "mathematically impossible failure" language.

Reason:
- These claims can fail under collusion, correlated bias, domain ambiguity, or adaptive attackers.

## 19) How to address the identified issues

Concrete design responses:
1. Collusion resistance:
- Random reviewer assignment, no self-review, separation of duties, multi-reviewer quorum for high-risk tasks.
2. Correlated error reduction:
- Model and method diversity (not just more reviewers).
3. "Audit theatre" prevention:
- Strong evidence schema per task type and reproducibility checks before approval.
4. Reputation gaming:
- Slow-to-earn, fast-to-lose trust; delayed scoring based on downstream quality outcomes.
- No purchase, transfer, leasing, or exchange of trust between identities.
5. Human overload:
- Human review focused on exceptions, risk flags, and appeals rather than every raw output.
6. Governance legitimacy:
- Structural separation of policy proposal, approval, enforcement, and appeals.

## 20) Red/Amber/Green snapshot (v0.1 planning)

Green:
1. Core architecture direction
2. Governance-engine-as-core positioning
3. Mission/task/review workflow concept

Amber:
1. Incentive design and reputation economics
2. Reviewer collusion detection at scale
3. Adoption strategy for first real users

Red (if left uncorrected):
1. Overreliance on timing-based identity tests
2. Absolute certainty language in security claims
3. Consensus-as-truth assumptions in subjective domains

## 21) Working language for future specs

Use this tone standard in all future specification work:
1. No "bulletproof" or absolute guarantees.
2. Distinguish clearly between:
- objective verification (testable)
- normative judgment (requires governance/human adjudication)
3. State uncertainty explicitly where evidence is limited.
4. Prefer reversible rollout steps and measurable acceptance criteria.

## 22) Companion files in this folder

This note is paired with:
1. `GENESIS_BACKGROUND_REVIEW_2026-02-13.md`
2. `GENESIS_WORK_LOG_2026-02-13.md`

These capture the full review conclusions and the work log for this round.

## 23) Recent constitutional refinements (Feb 13, 2026)

The following points are now explicit in the publication docs and trust constitution:

1. Machines can earn trust for operational work, but cannot vote constitutionally.
2. Constitutional voting is verified-human only; machine constitutional voting weight is pinned at zero.
3. Constitutional changes are human-only, supermajority-ratified, and committed on-chain.
4. Steward groups are process administrators only and cannot become a de facto government.
5. No government has unilateral constitutional override power.

## 24) Geo-distributed governance requirement

High-level trust and constitutional decisions must be:
1. geographically distributed across multiple regions,
2. independently re-verified by separate trusted human groups,
3. non-overlapping in membership for decision and verification chambers.

This is required to prevent concentration capture.

## 25) Mathematical governance core integrated

A formal default model is now defined in core docs, including:
1. trust-domain separation (`T_H` for human constitutional trust, `T_M` for machine operational trust),
2. slow-gain/fast-loss trust update logic,
3. human chamber voting thresholds,
4. geographic diversity constraints,
5. capture-risk upper-bound formula,
6. anti-gaming controls for high-throughput actors.

Primary source for this model:
1. `TRUST_CONSTITUTION.md`

## 26) Bounded trust economy integrated

Core additions now encoded in publication and constitutional docs:
1. Universal baseline trust (`T0`) for all verified identities.
2. Trust grows only through verified useful contribution quality.
3. Domain-specific decay floors:
- Human trust uses slow dormancy decay with a grace period and a non-zero floor.
- Machine trust uses freshness decay and may decay to zero.
- Machine trust at zero enters operational quarantine and must pass supervised re-certification for re-entry.
4. Absolute and relative trust caps to block dominance accumulation.
5. Per-epoch trust growth rate limits to block burst gaming.
6. Low-trust recovery lanes through small verified tasks (humans) and supervised re-certification lanes (machines).
7. Trust grants permissions, not command authority over others.
8. Money has no governance role in trust, proposal, or constitutional voting rights.
9. Trust is minted only via cryptographic proof-of-trust evidence; proof-of-work evidence alone is insufficient.

## 27) Key clarity retained

1. Proof-of-personhood/proof-of-agenthood remains a supporting anti-abuse control only.
2. Cryptographic commitment records prove integrity/provenance, not truth by itself.
3. Correctness still depends on independent verification and evidence quality.

## 28) Outstanding issues closure (Feb 13, 2026)

The previously identified implementation gaps are now closed with executable artifacts:

1. Parameter calibration and threshold controls:
- Constitutional defaults mirrored in `config/constitutional_params.json`.
- Calibration and reject-criteria flow documented in `TRUST_CONSTITUTION.md`.

2. Runtime risk-tier resolver:
- Mission-class to risk-tier mapping encoded in `config/runtime_policy.json`.
- Constitutional mission class explicitly mapped to `R3` (human-only constitutional flow).

3. Executable invariant enforcement:
- `tools/check_invariants.py` validates constitutional and runtime non-negotiables.

4. Worked examples with policy verification:
- `examples/worked_examples/low_risk_mission.json`
- `examples/worked_examples/high_risk_mission.json`
- `tools/verify_examples.py` validates both bundles against runtime policy.

Verification status at update time:
1. `python3 tools/check_invariants.py` -> passed
2. `python3 tools/verify_examples.py` -> passed
