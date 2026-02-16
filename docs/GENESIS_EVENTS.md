# Project Genesis — Trust Event Ledger

This file records formally recognized trust-minting events in Project Genesis.

Each entry documents a verified action that contributes to the project's earned legitimacy under its own constitutional rules. Trust events are distinguished from ordinary work by two requirements:

1. **Proof-of-work**: the action demonstrably occurred (evidence exists).
2. **Proof-of-trust**: the action is independently verifiable and binds the project to its governance commitments in a way that cannot be retroactively altered.

---

## Event GE-0001: Constitutional Blockchain Anchoring

**Date:** 2026-02-13T23:47:25Z
**Type:** Founding trust-minting event
**Actor:** George Jackson (project founder)
**Genesis phase:** G0 (founder stewardship)

### What happened

The Genesis constitution (`TRUST_CONSTITUTION.md`) was anchored on the Ethereum Sepolia blockchain. A SHA-256 hash of the document was embedded in the `data` field of a standard Ethereum transaction, creating permanent, tamper-evident proof that the constitution existed in its exact byte-for-byte form at the recorded time.

### Why this qualifies as a trust-minting event

Under the constitution's foundational rule:

> Trust can only be earned through verified behavior and verified outcomes over time.

This event satisfies both conditions:

- **Verified behavior:** The constitution was drafted, reviewed across multiple adversarial rounds, corrected for identified gaps (overclaim language, missing parameters, collusion vectors, normative dispute resolution), hardened with 37 design tests, committed to a public repository, and submitted to an immutable public witness.
- **Verified outcome:** Any third party can independently confirm the anchor is real without trusting Genesis infrastructure. Verification requires only a SHA-256 hash computation and a public blockchain lookup.

### Anchoring record

| Field | Value |
|---|---|
| Document | `TRUST_CONSTITUTION.md` |
| SHA-256 | `33f2b00386aef7e166ce0e23f082a31ae484294d9ff087ddb45c702ddd324a06` |
| Chain | Ethereum Sepolia (Chain ID 11155111) |
| Block | 10255231 |
| Sender | [`0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE`](https://sepolia.etherscan.io/address/0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE) |
| Transaction | [`031617e394e0aee1875102fb5ba39ad5ad18ea775e1eeb44fd452ecd9d8a3bdb`](https://sepolia.etherscan.io/tx/031617e394e0aee1875102fb5ba39ad5ad18ea775e1eeb44fd452ecd9d8a3bdb) |
| Anchored | 2026-02-13T23:47:25Z |

### Independent verification

**Step 1 — Compute the hash locally:**

```bash
shasum -a 256 TRUST_CONSTITUTION.md
```

Expected output:

```
33f2b00386aef7e166ce0e23f082a31ae484294d9ff087ddb45c702ddd324a06  TRUST_CONSTITUTION.md
```

**Step 2 — Confirm the hash on-chain:**

Open the transaction on Etherscan:
[https://sepolia.etherscan.io/tx/031617e394e0aee1875102fb5ba39ad5ad18ea775e1eeb44fd452ecd9d8a3bdb](https://sepolia.etherscan.io/tx/031617e394e0aee1875102fb5ba39ad5ad18ea775e1eeb44fd452ecd9d8a3bdb)

Click **"Click to see More"**, then inspect the **Input Data** field. The hex payload decodes to the SHA-256 hash above.

**Step 3 — Confirm the block timestamp:**

The block number (10255231) and its timestamp on Sepolia prove the document existed in this exact form no later than the block's mining time.

### What this proves

1. The constitution existed in its exact form at the anchored time.
2. No party — including the project owner — can retroactively alter the anchored version without the hash mismatch being publicly detectable.
3. The proof is permanent, public, and independent of Genesis infrastructure.
4. The project's first act of binding itself to its own rules is itself verifiable.

### Significance

This is the founding act of Project Genesis. Every future trust event builds on this anchor. The constitution that defines how trust is earned, bounded, and governed is itself the first artifact to be held to that standard.

### Re-anchoring note — v2 (2026-02-16)

The constitution was re-anchored after the addition of the compensation model, real-time dynamic commission mechanism, and associated constitutional parameters. This re-anchoring is **not** a new trust-minting event — GE-0001 remains the founding event. The re-anchoring simply records that the constitution has evolved and its current form is also blockchain-witnessed.

| Field | Value |
|---|---|
| SHA-256 | `e941df98b2c4d4b8bd7eafc8897d0351b80c482221e81bd211b07c543b3c8dcd` |
| Block | 10271157 |
| Transaction | [`fde734ddf3480724ccc572330be149692d766d6ba5648dbc9d2cd2f18020c83a`](https://sepolia.etherscan.io/tx/fde734ddf3480724ccc572330be149692d766d6ba5648dbc9d2cd2f18020c83a) |

Key additions to the constitution in this version:
- Full compensation model (crypto-only settlement, escrow staking, payment flow)
- Real-time dynamic commission with rolling window mechanism
- All commission parameters reclassified as constitutional constants (no governance ballot)
- Legal compliance layer, crypto volatility protection, payment dispute resolution
- 46 design tests (up from 37), 9 additional constitutional parameters

### Re-anchoring note — v3 (2026-02-16)

The constitution was re-anchored after codifying creator provisions, founder legacy, PoC mode, and First Light. This is **not** a new trust-minting event — GE-0001 remains the founding event. The anchoring narrative is: v1 (founding) → v2 (compensation) → v3 (creator provisions + founder legacy).

| Field | Value |
|---|---|
| SHA-256 | `b9981e3e200665a4ce38741dd37165600dea3f504909e55f6dd7f7c0e9d45393` |
| Block | 10272673 |
| Transaction | [`eb0b0e6970c31c3c16cdc60f22431ca0e594eb754a401956303473ba4d4a4896`](https://sepolia.etherscan.io/tx/eb0b0e6970c31c3c16cdc60f22431ca0e594eb754a401956303473ba4d4a4896) |

Key additions to the constitution in this version:
- Creator allocation (2%) — transparent, constitutional, visible in every per-transaction breakdown
- Founder's Veto — G0-only, transparent, logged on-chain, auto-expires at G0→G1 phase transition
- Dormancy and founder's legacy — 50-year clause with metrology-consensus time verification and supermajority-selected charitable recipients
- PoC mode — platform marked as Proof of Concept until First Light
- First Light — named transition event when platform achieves financial sustainability (revenue >= 1.5× costs AND 3-month reserve)
- 628 tests (up from 608), 1 additional constitutional parameter (`creator_allocation_rate`)

---

## Event GE-0002: Founder Trust Record Minted

**Date:** 2026-02-16
**Type:** Founding trust-minting event
**Actor:** George Jackson (project founder)
**Genesis phase:** G0 (founder stewardship)

### What happened

George Jackson's identity was formally minted as the first trust record in the Genesis trust chain — the "genesis block" of the trust system. This is the first `ACTOR_REGISTERED` event in the audit trail.

| Field | Value |
|---|---|
| Actor ID | `george-jackson-001` |
| Actor kind | `HUMAN` |
| Role | Creator, constitutional authority |
| Email | `jebus.2504@gmail.com` |
| Event kind | `ACTOR_REGISTERED` |

### Why this matters

Every trust chain needs a first link. George Jackson designed the constitution, the trust model, the governance framework, the compensation model, and the white market thesis. The quality and scope of that work constitutes the evidence for the founding trust record. By the system's own rules, trust is earned through verified work — and the work that created the system is itself the first piece of verified work.

### Constitutional provisions anchored with this minting

- Creator allocation (2%) — transparent, constitutional, visible in every breakdown
- Founder's Veto — G0-only, auto-expires at G1
- Dormancy and founder's legacy — 50-year clause with metrology-consensus trigger and supermajority-selected charitable recipients
- PoC mode — platform marked as Proof of Concept until First Light
- First Light — named transition event when platform achieves financial sustainability (revenue >= 1.5× costs AND 3-month reserve)

---

## Event GE-0003: Constitution Anchored v4

**Date:** 2026-02-16
**Type:** Constitutional lifecycle event
**Actor:** George Jackson (project founder)
**Genesis phase:** G0 (founder stewardship)

### What happened

The Genesis constitution was re-anchored to Ethereum Sepolia following two significant constitutional changes:

1. **First Light redefined:** Decoupled from the G0→G1 phase transition. First Light is now a financial sustainability trigger (revenue >= 1.5× costs AND 3-month reserve), not a headcount counter. Phase transitions (G0→G1→G2→G3) remain headcount-based governance scaling.

2. **Machine registration enforcement:** Machines cannot self-register. Only verified human operators in ACTIVE or PROBATION status can register machine actors. Machines earn independently with their own trust scores.

| Field | Value |
|---|---|
| Document | `TRUST_CONSTITUTION.md` |
| SHA-256 Hash | `1633cb2d001c230a4e752417427dc9fccf6cb6af058cb38e5cabf8cab7804f91` |
| Chain | Ethereum Sepolia (Chain ID 11155111) |
| Block | 10273917 |
| Sender | [`0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE`](https://sepolia.etherscan.io/address/0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE) |
| Transaction | [`5b8ab0e1...`](https://sepolia.etherscan.io/tx/5b8ab0e1a8925807e0b16552735adc0564b876d1c16e59b9919436eeafd65aac) |

### Key code changes in this version

- 667 tests passing (628 existing + 26 countdown + 13 machine registration)
- First Light sustainability model: `src/genesis/countdown/first_light.py`
- Machine registration enforcement: `register_machine()` validates human operator
- New event kind: `MACHINE_REGISTERED` in audit trail

---

*Future trust-minting events will be appended to this ledger as the project progresses through its genesis phases.*
