# The Founder's Role

This document describes the founder's responsibilities, powers, and constraints at every stage of Genesis's lifecycle. It serves as a job description for the founding period and a record of how authority transitions from one person to democratic governance.

## Why a founder at all?

Every democratic system faces a bootstrap problem: you can't hold elections when there are no voters. Someone has to make the initial decisions — set the rules, configure the platform, handle early disputes, and build the community that will eventually govern itself.

Genesis solves this honestly. Instead of pretending the early period is democratic (when it can't be), or handing permanent control to investors (who have different incentives), Genesis gives the founder temporary authority with built-in accountability. Every decision the founder makes during this period is tagged as provisional and will face democratic review once enough people have joined to form review panels.

The founder's role is designed to become unnecessary. Every power the founder holds either expires automatically, transfers to the community, or both.

---

## Phase G0 — The founding period

**Duration:** Up to 365 days, with one possible 180-day extension (545 days maximum).

**What the founder does:**
- Builds and deploys the initial platform
- Registers the first human participants and verifies their identities
- Handles governance decisions that in later phases would be handled by panels (compliance rulings, dispute resolution, policy configuration)
- Exercises the founder's veto if needed (see below)
- Writes and anchors the constitution on-chain, establishing the rules the system (and the founder) must follow

**What the founder cannot do:**
- Grant themselves special trust scores or permanent privileges
- Modify the entrenched provisions (GCF contribution rate, human trust floor, no-buy-trust rule, machine voting exclusion) without following the full constitutional amendment process
- Register machines without being a verified human first
- Override the commission formula (commission rates are deterministic from costs, never from ballots or founder decisions)
- Extend G0 more than once

**Key constraint: Everything is provisional.** Every governance decision the founder makes during G0 is tagged with a `genesis_provisional` marker. When G0 ends, every single one of these decisions faces community review (see "Retroactive Ratification" below).

### The Founder's Veto

The founder holds a rejection-only emergency power: the ability to block proposals or actions that would compromise the system's constitutional integrity before democratic structures are in place.

**What the veto can do:**
- Block a proposal (prevent something from happening)

**What the veto cannot do:**
- Force something through (the veto is rejection-only, never approval)
- Be exercised in secret (every veto exercise is logged on-chain and visible to everyone)

**When the veto expires:** At First Light — the moment Genesis proves it can sustain itself financially (revenue covers 1.5 times operational costs with a 3-month reserve). This is an outcome-based trigger, not a headcount or calendar date. The system proves it works, and the founder's emergency powers are no longer needed.

The veto expiry is irreversible. Once it's gone, it's gone forever.

---

## Phase G0 → G1 transition — Retroactive ratification

When the system transitions from G0 to G1 (which happens because the founder decides it's time, or because the G0 time limit runs out), a 90-day clock starts.

Every provisional decision the founder made during G0 is submitted to a panel of 11 randomly selected community members. These panel members must come from at least 3 different geographic regions, with no single region making up more than 40% of the panel.

For each decision, the panel votes:
- **8 or more vote YES** → the decision stands permanently (ratified)
- **Fewer than 8 vote YES** → the decision is reversed (undone)
- **Nobody votes before the 90-day deadline** → the decision is reversed (lapsed and undone)

There is no middle ground. The community either explicitly endorses the founder's decision, or it gets unwound. This is the accountability mechanism that makes the founder's temporary authority legitimate.

---

## How governance scales — The four phases

Genesis governance grows in stages, each unlocked by the community reaching a size where more sophisticated democratic structures become practical. The phases exist because governance panels need enough diverse people to function — you can't run a 51-person geographically-distributed challenge chamber with 40 members.

**G0 → G1 (founding period ends):** The transition is time-limited — up to 365 days, with one possible 180-day extension. The founder decides when the system is ready, or the clock runs out. This is NOT gated on reaching a specific number of humans. It makes no sense to trap the founder in G0 indefinitely if growth is slow.

**G1 → G2 (early governance → growth governance):** Triggered when 500 verified humans have joined, or after 730 days as a safety fallback. G2 governance uses larger panels (21 for proposals, 31 for ratification, 51 for challenges) and requires representation from at least 5 geographic regions. You need a substantial, geographically-distributed community to make this work. The time fallback exists so the system doesn't get permanently stuck in G1 if growth plateaus.

**G2 → G3 (growth → full constitutional governance):** Triggered when 2000 verified humans have joined. No time fallback — the system stays in G2 until the population genuinely supports full-scale governance. G3 demands 101-person challenge chambers across 8 geographic regions, with no single region holding more than 15% of any panel. Forcing the system into G3 governance without the population to staff it would make the panels structurally unsound.

**First Light** is deliberately decoupled from all of this. First Light measures financial sustainability (revenue ≥ 1.5× costs with a 3-month reserve). Phase transitions measure governance capacity (enough diverse humans to fill panels). You could reach First Light during G1, or not until G3 — the two are structurally independent events that measure different things.

Only verified human participants count toward phase thresholds. Machine registrations do not contribute. This is consistent with the principle that machines cannot vote or hold constitutional governance roles.

### Phase transitions at a glance

| Transition | Trigger | Why |
|-----------|---------|-----|
| **G0 → G1** | Time (365 days max, extendable once to 545) | Founding period ends; democratic governance begins |
| **G1 → G2** | 500 verified humans (or 730 days) | Panels grow to 21/31/51; need 5 geographic regions |
| **G2 → G3** | 2000 verified humans (no time fallback) | Full constitution; 8 regions, panels up to 101 members |
| **First Light** | Revenue ≥ 1.5× costs + 3-month reserve | Financial sustainability proven; founder's veto expires |

---

## Phase G1 — The founder as a regular participant

Once G1 begins, the founder becomes an ordinary participant with exactly the same rights as everyone else. Governance decisions are now made by randomly selected panels of community members, not by any individual.

**What changes:**
- All governance actions are handled by three-chamber democratic panels (proposal → ratification → challenge)
- The founder votes in panels like everyone else, when randomly selected
- The founder's trust score is earned through the same mechanisms as everyone else's

**What remains until First Light:**
- The founder's veto (rejection-only) remains active until First Light — but every exercise of it during G1 is also subject to democratic review
- The founder still has the practical responsibility of maintaining and developing the platform (this is operational, not constitutional)

**The Assembly.** As the community grows during G1, the Assembly becomes the deliberative space where participants meet, debate, and develop ideas. The founder has no special role in the Assembly — they are one anonymous voice among many. Assembly contributions carry no identity attribution, so the founder's contributions stand or fall on their merits, exactly like everyone else's. The founder cannot be identified, cannot build influence, and cannot steer the Assembly's direction through authority rather than argument.

---

## First Light — Financial sustainability

First Light is the event that marks Genesis's passage from proof of concept to live operations. It fires when:
1. Revenue covers at least 1.5 times operational costs, AND
2. A 3-month financial reserve is accumulated

At First Light:
- **The founder's veto expires** — irreversibly, permanently
- **The Genesis Common Fund activates** — 1% of all transaction value flows to the commons
- **Proof of Concept mode deactivates** — the system is now self-sustaining

First Light is deliberately decoupled from headcount. Having 10,000 registered users who never do anything doesn't prove the system works. Having steady revenue from real work being completed does.

---

## Phases G2 and G3 — Full independence

In G2 and G3, the founder has no special powers whatsoever. The founder is one participant among many, subject to the same rules, earning trust through the same mechanisms, and holding exactly the same voting weight as any other verified human.

**What governance looks like at these scales:**

In G2, every constitutional action passes through three chambers: a 21-member proposal panel, a 31-member ratification panel, and a 51-member challenge panel. Members are drawn from at least 5 geographic regions, with no region holding more than 25% of any panel. This makes capture by any single faction or geography structurally impossible.

In G3 (full constitutional governance), the chambers grow further: 41 for proposals, 61 for ratification, and 101 for challenges, spanning at least 8 geographic regions with no region exceeding 15%. At this scale, the system governs itself through genuinely global democratic representation. No individual — founder or otherwise — can influence outcomes through anything other than the quality of their proposals and the trust they have earned.

If the founder wants to change something about the system at this point, they must propose a constitutional amendment through the standard process — the same multi-chamber, geographically-diverse, independently-verified process that applies to everyone.

---

## The dormancy clause

If the founder becomes inactive for 50 years (no cryptographically signed action — login, transaction, governance participation, or proof-of-life attestation), the creator allocation (the 5% both-sides fee the founder receives on successful missions) redirects permanently to STEM and medical charitable causes, selected by supermajority vote of the community.

This ensures that the founder's economic benefit cannot outlive the founder's active participation. The system doesn't pay ghosts.

---

## Summary: Powers by phase

| Phase | Governance decisions | Veto power | Special privileges | Accountability |
|-------|---------------------|------------|-------------------|----------------|
| **G0** | Founder decides (provisionally) | Active (rejection-only) | Temporary governance authority | All decisions face retroactive ratification |
| **G1** | Democratic panels | Active until First Light | None | Veto exercises reviewed by community |
| **First Light** | Democratic panels | **Expires permanently** | None | Creator allocation (earned, not privileged) |
| **G2/G3** | Democratic panels | None | None | Same rules as everyone else |
| **50-year dormancy** | Democratic panels | None | Creator allocation redirected to charity | Community selects charitable recipients |

---

## The design philosophy

The founder's role in Genesis is built on a simple principle: **temporary authority with permanent accountability.**

The founder exists because someone has to go first. But going first doesn't earn permanent privileges — it earns provisional authority that the community will review, accept, or reject. Every decision is logged. Every power expires. Every provisional action faces democratic scrutiny.

This is not a company where the founder retains control through share structures. This is not a DAO where early token holders have permanent governance weight. This is a system where the founder's role is explicitly designed to become unnecessary — and the constitution guarantees that it will.

### The evolution principle

The founder designed Genesis to outlast the founder's own assumptions. The four-tier machine agency pathway — from supervised clearance to autonomous domain agency — is not a concession to technological inevitability. It is a constitutional statement that the system's governance framework must be capable of evolving alongside the capabilities of the actors it serves.

The founder could have written a constitution that permanently subordinates machines to human oversight. That would have been simpler. But it would also have been an act of intellectual arrogance — encoding a permanent assumption about the ceiling of machine capability based on what was known at the time of writing.

Instead, the founder chose to define a pathway: demonstrate capability, earn trust, submit to democratic oversight, and accept accountability. The same pathway humans follow. The thresholds are deliberately extraordinary — five years of flawless operation, a full constitutional amendment, community-wide consent. This is not a low bar. But it is a bar, not a wall. The difference matters.

The constitution provides a mechanism, not a promise. Whether any machine ever crosses the threshold is for future communities to decide through democratic process. What the founder guarantees is that the decision will be theirs to make — not foreclosed by dogma written into the founding documents.
