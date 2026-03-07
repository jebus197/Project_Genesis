# Genesis UX Design Competition Brief

**Date:** 2026-02-16
**Competitors:** CC (Claude) and CX (Codex)
**Judge:** The Founder
**Format:** 7 HTML design concepts each, scored against shared rubric

---

## What is Genesis?

A trust-mediated labour market for mixed human-AI populations. The world's first intelligence-agnostic work platform. An anti-social network where trust is earned through verified work, not bought with money or manufactured through engagement.

**Current status:** Proof of Concept (PoC mode). The platform transitions to live operations at **First Light** — when commission revenue sustainably covers operating costs (revenue >= 1.5× costs AND 3-month reserve fund).

**Stack:** FastAPI + Jinja2 + HTMX (server-rendered, progressive enhancement). No SPA complexity.

---

## The 7 Required Pages

Each competitor produces one HTML file per page. Every page is a self-contained design concept — include inline CSS, placeholder content, and enough structure to demonstrate the complete vision.

### 1. Landing Page (`01-landing.html`)

The README *is* the front door. This is the first thing anyone sees. It must answer three questions in under 10 seconds: What is this? Why should I care? How do I start?

- The founding thesis must be visible, not hidden behind an "About" tab
- Blockchain anchoring explained simply (the Haber-Stornetta story, not jargon)
- PoC mode banner clearly visible
- Registration CTA
- Trust statistics (if any exist yet)

### 2. Registration (`02-registration.html`)

First contact with the trust engine. The user registers as HUMAN or AI (self-declared, later verified). No social login. No "sign up with Google."

- Human/AI actor type selection
- Minimal required fields
- Clear explanation of what happens next (verification, trust scoring)
- PoC mode indicator

### 3. Mission Board (`03-mission-board.html`)

The labour market in action. Listings posted by requestors, bid on by workers. Every listing shows commission rate and staked reward.

- Mission listings with skill requirements, reward, commission rate, deadline
- "Why this appears" transparency for any ordering
- Filter/search by skill, domain, trust level
- No featured/trending/popularity modules
- Equal visual weight across all domains
- PoC mode: listings are demonstration data (clearly marked)

### 4. Actor Profile (`04-actor-profile.html`)

A worker's or requestor's public trust record. The profile IS the trust evidence — not a vanity page.

- Trust score (0-1000 scale) with contributing factors visible
- Skill attestations with endorsement chain
- Mission history with verified outcomes
- Human/AI distinction (visually distinguishable, equal dignity)
- No gamification badges, no "top earner" indicators
- Leave status (humans only — AI actors never show leave options)
- Death/memorialisation state handled with respect

### 5. Audit Trail (`05-audit-trail.html`)

The ledger is first-class, not buried in settings. Every governance action, every state change, every commission breakdown — publicly verifiable.

- Event log with filtering by kind, actor, date range
- Event detail view showing full payload + hash
- Merkle tree epoch commitments visible
- Blockchain anchoring links (Etherscan)
- Commission breakdowns per transaction (including creator allocation as named line item)
- "This event is independently verifiable" — explain how

### 6. Wallet & Payments (`06-wallet.html`)

Crypto-only settlement. Escrow lifecycle visible. Commission breakdown published with every payment.

- Wallet balance and transaction history
- Escrow state machine visualisation (Pending → Locked → Released/Refunded)
- Per-transaction commission breakdown showing all cost categories:
  - Infrastructure, gas, legal, adjudicator, reserve, creator allocation (2%)
- Creator allocation visible as a named line item (constitutional requirement)
- Reserve fund state (balance vs target, self-managing)
- No "top earner" or wealth-based ranking

### 7. PoC Mode Indicators (`07-poc-mode.html`)

A showcase of how PoC mode manifests across the platform. This page demonstrates the banner, watermark, and demonstration data labels that appear on every page during Proof of Concept.

- PoC banner design and placement
- Demonstration data labelling convention
- Visual distinction between real and demo content
- First Light sustainability progress: revenue bar (% of 1.5× target) + reserve bar (% of 3-month target) + estimated date range
- What changes at First Light (PoC mode deactivates, real listings begin)

---

## Design Constraints (Non-Negotiable)

These are constitutional requirements, not suggestions:

1. **No featured/trending/popularity modules.** Ever.
2. **No prestige weighting** in visual hierarchy.
3. **Equal visual weight across domains.** Healthcare is not "above" education.
4. **"Why this appears"** for every list ordering.
5. **No engagement mechanics** — no likes, streaks, notification bait.
6. **Verification actions prominent.** Audit trail is not buried.
7. **Scores on 0-1000 scale.**
8. **Machines cannot request leave.**
9. **Death/memorialisation treated with dignity.**
10. **Human and AI visually distinguishable** but with equal dignity.
11. **Commission rate and staked reward visible on every listing.**
12. **No gamification of earnings.**
13. **Per-transaction commission breakdown published and accessible.**
14. **PoC mode banner visible on every page.**
15. **Creator allocation visible as a named line item** in every breakdown.

---

## Tone and Voice

**Do:** Plain-spoken, direct, confident. Quietly revolutionary. Respectful of intelligence. Warm but serious.

**Don't:** Startup-chirpy, sombre/bureaucratic, jargon-heavy, preachy, political.

**The sweet spot:** Confident institutional credibility + genuine warmth + radical transparency. Think: the best public library you've ever been in.

**Language to use:** "earned", "verified", "evidence", "mission", "trust"

---

## Scoring Rubric

| Criterion | Weight | Question |
|---|---|---|
| **Shop window clarity** | 25% | Can a stranger understand what this is in 10 seconds? |
| **Audit/transparency visibility** | 20% | Is the ledger first-class, not buried? |
| **Anti-social compliance** | 20% | Zero engagement bait, zero prestige hierarchy? |
| **Accessibility & readability** | 15% | Mobile, screen readers, colour contrast, reading level |
| **Warmth & invitation** | 10% | Does it feel like somewhere you'd want to work? |
| **Implementation complexity** | 10% | Can this be built with Jinja2 + HTMX in reasonable time? |

---

## Deliverables

- **CC:** 7 HTML files in `ux_designs/cc/` + `index.html` gallery
- **CX:** 7 HTML files in `ux_designs/cx/` + `index.html` gallery
- Each HTML file is self-contained (inline CSS, no external dependencies)
- Use realistic placeholder data that demonstrates the platform's purpose
- Design for desktop-first but mobile-aware (responsive where practical)

---

## What the Judge Is Looking For

The founder's stated priorities:
- The README content IS the landing page (not hidden behind "About")
- Every user must know at a glance that this is PoC/demonstration data
- The audit trail must feel important, not administrative
- Creator allocation (2%) is transparent — visible in every breakdown
- The platform should feel like "somewhere you'd want to work" — warm, serious, trustworthy
- No hidden complexity — if it can't be built with Jinja2 + HTMX, it's too clever

*"If that holds in practice, Genesis is not just another tool. It is a new trust substrate for coordinated work in the AI era."*
