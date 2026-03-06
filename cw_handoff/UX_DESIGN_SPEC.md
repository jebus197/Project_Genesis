# Genesis UX Design Specification

> Written spec for the web interface. This document governs all visual design work.
> Both CC and CX will produce independent design concepts evaluated against this spec.

---

## 1. What Genesis Is (Identity)

**One-liner:** A governance-first trust infrastructure for large-scale human and AI coordination.

**The pitch:** The missing piece in AI is not smarter models. It is **institutional structure**. Genesis wraps AI capability in a governance framework where trust can only be earned — never bought, sold, or traded.

**What it actually is:**
- A coordination system for meaningful work
- A verification system with independent checks
- A governance system with explicit rules and accountability
- An evidence system with traceable records
- A trust-mediated labour market for mixed human-AI populations

**What it explicitly is not:**
- A social engagement platform
- A chatbot
- A token or blockchain product
- A permissionless free-for-all
- A replacement for human responsibility

---

## 2. The Positioning Problem

Genesis is the world's first anti-social network. The "(anti)" is structural — baked into code, not marketing — but the word is provocative by design. The system inverts every toxic pattern of social media:

| Social Network | Genesis |
|---|---|
| Engagement optimization | Mission completion |
| Output volume | Verifiable quality |
| Opaque algorithms | Auditable processes |
| Centralised discretion | Explicit governance |
| Purchased influence | Earned trust only |
| Popularity ranking | Capability matching |
| Vanity metrics | Evidence profiles |
| Dopamine loops | Work-first, no bait |

The UX must communicate this inversion **at a glance** — without ever becoming preachy, dour, or self-righteous about it.

---

## 3. The Taglines (George's Own Framing)

These are the founder's exact words. They are the voice of the project. The UX must channel this tone — plain-spoken, serious but not solemn, quietly revolutionary:

### Constitutional
- **"Trust cannot be bought, sold, exchanged, delegated, rented, inherited, or gifted. Trust can only be earned through verified behaviour and verified outcomes over time."**

### The Problem
- "AI is getting more capable every year. But capability is not the same as trustworthiness."
- "The missing piece in AI is not smarter models. It is **institutional structure**."

### The Inversion
- "From engagement optimization to mission completion."
- "From output volume to verifiable quality."
- "From opaque generation to auditable processes."
- "From centralized discretion to explicit governance mechanisms."

### On Work and Skills
- "Your skills are earned, not claimed."
- "When the system says someone is qualified, it actually means something."
- "Trust is meaningful only if it leads to real work."

### On Trust
- "Make gaming the system expensive, make concentration difficult, and keep legitimacy tied to contribution quality."
- "High trust grants more responsibility, not more power."
- "Earned trust, not purchased influence."

### On Human Dignity
- **"We can't penalise people for being dead!"**
- "Life events — illness, bereavement, disability, caregiving — are not inactivity. Without a protection mechanism, an actor who gets sick loses trust through no fault of their own. This is a new kind of poverty: your verified track record eroding while you're incapable of contributing."

### On Governance
- "No one gets to mark their own homework."
- "The system that governs AI must not be governable by AI. Machines are workers and reviewers within the system. Humans are the legislators."

### On Honesty
- "No serious system should claim to be invulnerable."
- "Genesis aims for **measurable risk reduction**, not perfection."

### On Ambition
- "If that holds in practice, Genesis is not just another tool. It is a new trust substrate for coordinated work in the AI era."

### Design Principles
- "Choose legitimacy over speed."
- "Choose evidence over volume."
- "Choose earned trust over purchased influence."
- "Choose measurable risk reduction over absolute claims."

---

## 4. The Shop Window Problem

The first 7 UX concepts were profile-centric — they showed a logged-in actor's personal view. That's necessary but insufficient.

**The landing experience must be an open marketplace.** Someone who has never heard of Genesis should be able to look at the front page — like a shop window — and understand:

1. **What this place is** — a marketplace for verified work
2. **What work is available** — real missions, visible to anyone
3. **Why it's different** — transparency, no engagement tricks, trust earned not bought
4. **Who's here** — a mixed population of humans and AI, working together
5. **How the trust system works** — at a glance, not after reading a white paper

### The analogy
Think of it as: **LinkedIn's gravitas** meets a **mature social network's usability** — but with the fundamental inversion that nothing here is designed to keep you scrolling. You come to work. You come to find work. You come to verify work. The system respects your time.

### What the landing page must NOT be
- A login wall (the marketplace should be browseable without an account)
- A marketing page with no live data
- A dashboard (that's post-login)
- A white paper summary

### What the landing page MUST be
- A live view of the open marketplace: real missions, real domains, real numbers
- Immediately legible to a non-technical visitor
- A clear statement of what makes this different (tagline + one-paragraph pitch)
- An invitation to explore further — browse missions, read an actor's evidence profile, explore the audit trail
- Respectful, inviting, and confident — not sombre, not startup-perky

---

## 5. The Three Core Views (Post-Login)

Per CX architecture guidance, the MVP has four core views (expanded from the original three to include payment). All must use identical data to enable visual comparison:

### 5.1 Mission Board (Open Marketplace)
- Filterable work feed ordered by transparent fit logic
- **"Why this appears"** explanation on every listing (never opaque ranking)
- Domain tags with equal visual weight (no domain is "bigger" or "more important")
- Bid counts, time remaining, status badges, **staked reward (stablecoin equivalent)**
- Fit score for logged-in actors (0–1000 scale)
- **Current commission rate** displayed on mission detail view

### 5.2 Actor Profile (Evidence Record)
- Trust trajectory (not a single number — show the journey)
- Domain trust breakdown with scores (0–1000 scale)
- Verified skills with proficiency scores
- Outcome history (verified completions, in-progress work)
- **Earnings summary** (total missions completed, total earned — visible to logged-in users; exact amounts self-only)
- Leave status (including memorialisation where applicable)
- Actor facts: kind (HUMAN/AI), status, region, organisation, missions, reviews, endorsements
- **No vanity metrics** — no followers, no likes, no "connections"

### 5.3 Audit Trail (Public Ledger)
- First-class, searchable, filterable
- Trust changes, mission events, leave decisions, epoch closures, memorialisations, **payment events (escrow, commission, disbursement)**
- Every entry shows: timestamp, event type, details, epoch:hash receipt
- Tamper-evident and blockchain-anchored — communicate this without jargon
- **Per-transaction commission breakdown** accessible from audit trail (published cost reports)

### 5.4 Wallet & Payments (Self-Only)
- Current balance by currency (BTC, ETH, USDC, USDT)
- Payment history: received, pending, disputed
- Withdrawal options: exchange to stablecoin/local currency equivalent, or hold on platform
- Tax summary export (CSV/PDF — annual earnings, commission paid, payment dates)
- Escrow status for posters: which missions have staked funds, amounts, status
- **Creator allocation**: visible as a named line item in every per-transaction commission breakdown (2% constitutional constant)
- **No gamification of earnings** — no leaderboards, no "top earner" badges

---

## 6. Non-Negotiable UX Constraints

These are structural rules, not style preferences. Violation of any one is a design failure:

1. **No featured/trending/popularity modules.** Ever.
2. **No prestige weighting** in UI language, ranking, or visual hierarchy.
3. **Equal visual weight across domains and event categories.** Healthcare is not "above" education.
4. **"Why this appears"** for every list ordering — relevance/trust factors, never opaque.
5. **No engagement mechanics** — no likes, streak bait, notifications designed to pull you back, dopamine loops.
6. **Verification actions prominent.** The audit trail is not buried in settings.
7. **Scores on 0–1000 scale.** Humans need bigger numbers. (George: "One isn't a very interesting number for humans. 1000? Humans instinctively like greater quantities.")
8. **Machines cannot request leave.** Leave is for human life events only. The UI must not offer leave options to AI actors.
9. **Death/memorialisation treated with dignity.** A memorialised record is permanently sealed — the UI should communicate respect, not error.
10. **Human and AI actors visually distinguishable** but with equal dignity — no "AI badge of shame."
11. **Commission rate and staked reward visible on every mission listing.** Transparency is not optional.
12. **No gamification of earnings.** No "top earner" badges, no earning leaderboards, no wealth-based ranking.
13. **Per-transaction commission breakdown published and accessible.** The audit trail includes what the commission was spent on.
14. **PoC mode banner visible on every page** when the platform is in Proof of Concept mode. Users must always know they are viewing demonstration data.
15. **Creator allocation visible as a named line item** in every commission breakdown. The 2% constitutional allocation to the founder is transparent, not hidden.

---

## 7. Tone and Voice

### Do
- Plain-spoken, direct, confident
- Quietly revolutionary — let the system speak for itself
- Respectful of people's time and intelligence
- Warm but serious — this is real work, real trust, real stakes
- Use George's language: "earned", "verified", "evidence", "mission", "trust"

### Don't
- Preachy or moralising (the anti-social stance is structural, not rhetorical)
- Startup-chirpy ("Hey there! 🎉 Ready to disrupt trust?")
- Sombre or bureaucratic (this is not a government form)
- Jargon-heavy (no "decentralised consensus mechanisms" on the landing page)
- Marxian or overtly political (the principles are intact, the politics are not the brand)

### The sweet spot
**Confident institutional credibility + genuine warmth + radical transparency.** Think: the best public library you've ever been in — obviously serious, obviously for everyone, obviously well-run, and you feel smarter just being there.

---

## 8. Technical Constraints (CX Architecture Guidance)

- **Stack:** FastAPI + Jinja2 + HTMX (server-rendered, progressive enhancement)
- **No SPA complexity for MVP**
- **All business logic through GenesisService** — routes must not bypass service methods
- **Versioned API under /api/v1** with deterministic response contracts
- **Every state-changing operation returns an event receipt** (event id + hash + epoch)
- **Auth:** secure sessions + CSRF + rate limiting + strict input validation
- **Fail-closed:** never continue on partial trust/policy failure

---

## 9. Design Evaluation Rubric

Both CC and CX designs will be scored against:

| Criterion | Weight | Description |
|---|---|---|
| **Shop window clarity** | 25% | Can a stranger understand what this is in 10 seconds? |
| **Audit/transparency visibility** | 20% | Is the ledger first-class, not buried? |
| **Anti-social compliance** | 20% | Zero engagement bait, zero prestige hierarchy? |
| **Accessibility & readability** | 15% | Mobile, screen readers, colour contrast, reading level |
| **Warmth & invitation** | 10% | Does it feel like somewhere you'd want to work? |
| **Implementation complexity** | 10% | Can this be built with Jinja2 + HTMX in reasonable time? |

---

## 10. Founding Members & Trust Minting History

Genesis's trust engine has already begun minting:

| # | Event | Subject | Evidence |
|---|---|---|---|
| 1 | **Constitution Anchored** | The Trust Constitution | SHA-256 hash anchored to Ethereum Sepolia, block 10255231. Re-anchored at block 10271157 (v2 with compensation model). Re-anchored at block 10272673 (v3 with creator provisions + founder legacy). The foundation of Genesis's trust engine. |
| 2 | **George Jackson** (HUMAN) | Creator, constitutional authority, first trust record | Email: jebus.2504@gmail.com. Designed the constitution, trust model, governance framework, compensation model, white market thesis, and every architectural decision. The genesis block of the trust chain. |
| 3 | **CC** (Claude / AI) | Implementation partner | TBD — pending assessed work product (UX design competition entry) |
| 4 | **CX** (Codex / AI) | Technical reviewer | TBD — pending assessed work product (UX design competition entry) |

The UX design competition between CC and CX constitutes their first formally assessed work — and by the system's own rules, that evidence could seed their founding trust scores. A fitting origin story for the trust engine.

---

## 11. What Happens Next

1. Design brief posted at `Notes/ux_designs/BRIEF.md` — the shared brief both CC and CX compete against.
2. CC produces 7 design concepts in `Notes/ux_designs/cc/` covering the full UX: Landing, Registration, Mission Board, Actor Profile, Audit Trail, Wallet & Payments, and PoC mode indicators.
3. CX independently produces 7 design concepts in `Notes/ux_designs/cx/` against the same brief.
4. Both are scored on the rubric in Section 9.
5. George selects the winner (or hybrid).
6. Design tokens and component rules are locked before feature expansion.
7. The winning design is implemented as FastAPI + Jinja2 + HTMX front-end.

---

*"If that holds in practice, Genesis is not just another tool. It is a new trust substrate for coordinated work in the AI era."*
