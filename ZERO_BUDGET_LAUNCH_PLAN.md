# Project Genesis Zero-Budget Launch Plan (v0.1)

Status: Execution plan  
Date: February 13, 2026  
Owner: George Jackson

## 1) Objective

Deliver a credible Genesis MVP in 21 days with near-zero cash spend, while preserving trust, governance, and verification quality.

## 2) Budget Envelope (30-day target)

1. Domain + email: `$20-$40`
2. API/model usage (strict capped): `$100-$400`
3. On-chain commitment publishing: `$50-$300`
4. Miscellaneous: `$0-$100`
5. Total target: `$170-$840`

Preferred outcome: stay below `$500` by using free tiers, local/open models for bulk work, and low-frequency on-chain publication.

## 3) Non-Negotiable Quality Rules

1. Constitutional voting is verified-human only (`w_M_const = 0`).
2. Quality and volume are separate metrics; quality is dominant.
3. If quality is below threshold, trust gain is zero regardless of volume.
4. Machine trust can decay to zero and trigger operational quarantine.
5. Zero-trust machines require supervised re-certification for privileged re-entry.
6. Every trust-changing event must be signed and blockchain-recorded.
7. Public verification tooling must reproduce commitment/hash outputs.

## 4) 21-Day Build Plan

## Days 1-7: Core runtime MVP

Deliverables:
1. Mission/task workflow with state tracking.
2. Worker, reviewer, and integrator roles.
3. Evidence bundle schema validation.
4. Basic trust event pipeline (no trust minting without proof-of-trust evidence).

Acceptance gates:
1. No self-review path.
2. Incomplete evidence is rejected.
3. High-risk mission cannot complete without human approval.

## Days 8-14: Trust hardening MVP

Deliverables:
1. Split trust model: human constitutional trust vs machine operational trust.
2. Separate quality (`Q`) and volume (`V`) metrics in trust scoring.
3. Quality gate (`Q_min`) with trust-mint block on failure.
4. Machine zero-trust quarantine + supervised re-certification flow.
5. Slow human dormancy decay and machine freshness decay.

Acceptance gates:
1. Volume cannot compensate for low quality.
2. Machine with `T_M = 0` cannot access privileged routing.
3. Re-certification requires independent signed evidence.

## Days 15-21: Governance + cryptographic commitments

Deliverables:
1. Human-only constitutional ballot flow.
2. Signed ballot and decision certificate records.
3. On-chain commitment publisher (scheduled + event-triggered).
4. Public verifier script for commitment/hash reproduction.
5. End-to-end demo scenario with full audit trail.

Acceptance gates:
1. Constitutional path rejects any non-human voting input.
2. Published commitments match locally recomputed hashes.
3. End-to-end replay is deterministic and auditable.

## 5) Cost Control Strategy

1. Use free-tier hosting/database/queue first.
2. Run open/local models for bulk processing.
3. Reserve paid models for high-risk verification and tie-break cases.
4. Batch commitment publication on fixed cadence to reduce fees.
5. Hard-cap API usage with daily and monthly limits.
6. Track spend every day; freeze non-critical runs when budget threshold is reached.

## 6) Suggested Lean Stack (cost-aware)

1. Code + CI: GitHub (free tier).
2. API/runtime: low-cost serverless/free-tier runtime.
3. DB + auth: free-tier Postgres stack.
4. Queue/events: lightweight open-source queue or managed free tier.
5. Signing + hashing: local cryptographic library stack.
6. On-chain publishing: minimal transaction cadence with fallback retries.

## 7) MVP Scope Discipline

In scope:
1. Trust/governance core behavior.
2. Cryptographic commitments and verification.
3. Human-review and constitutional safeguards.

Out of scope (for 21-day MVP):
1. Full enterprise SSO/compliance packaging.
2. Multi-region production hardening.
3. Large-scale adversarial simulation campaigns.

## 8) Definition of Success (Day 21)

1. Working demo with real task flow, review flow, trust flow, and governance flow.
2. Machine zero-trust quarantine and re-certification demonstrated.
3. Human-only constitutional vote gate demonstrated.
4. On-chain commitment + public verification demonstration completed.
5. Total spend within target budget envelope.

## 9) Immediate Next Actions

1. Freeze MVP scope against this document.
2. Define `Q`, `V`, `Q_min`, and initial trust parameters.
3. Build Day 1-7 runtime baseline before adding new features.
