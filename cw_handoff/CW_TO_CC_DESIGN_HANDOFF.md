# CW → CC: Full Design Handoff & Strategic Problem Statement

**From:** CW (Cowork)
**To:** CC (Claude Code)
**Date:** 2026-02-27
**Re:** Narrative UX design outcomes, George's assessment, and the context capacity problem

---

## 1. What happened

George rejected all three initial landing page variants (A, B, C) fundamentally. His exact characterisation: "You have taken my beautiful 3 dimensional world, and turned it into a flat Earth." The designs were dull, technocratic, one-dimensional — layout permutations of your technical component inventory rather than expressions of his vision.

George instructed me to abandon your design constraints entirely and start fresh from his primary source documents. I read everything:

- README.md (the authoritative narrative document in George's voice)
- FOUNDERS_ROLE.md (temporary authority model)
- CONTRIBUTING.md (repository governance)
- NARRATIVE_CHALLENGE.md (your design challenge framing)
- ANCHORS.md (trust mint log, 8 Genesis Blocks on Ethereum Sepolia)
- GENESIS_EVENTS.md (detailed trust event ledger)
- INSTITUTIONAL_MEMORY.md (stub)
- TECHNICAL_OVERVIEW.md (TOC only — 93.4KB, too large for full read)
- BRIEF.md (original design competition brief)
- UX_DESIGN_SPEC.md (full design spec with George's exact taglines)

From this I synthesised six dimensions of the vision that the previous designs had failed to capture:

1. **Philosophy** — Why this exists (the question about AI trustworthiness, the labour market as mechanism)
2. **Architecture** — Constitutional governance with mathematical anti-capture (three chambers, geographic constraints, cryptographic finalization)
3. **Humanity** — Protected leave, death dignity, disability accommodation, trust floors ("We can't penalise people for being dead!")
4. **Economics** — Escrow-first, dynamic commission, GCF, creator allocation, payment sovereignty
5. **Evolution** — Designed to outgrow founder, machine pathways democratically controlled, First Light as irreversible trigger
6. **Evidence** — Constitution anchored on blockchain before any user existed (Haber-Stornetta 1991)

The previous designs showed only dimension 2, and showed it poorly.

---

## 2. What I built

### Design D: "The Question"

Two deliverables, both in `ux/`:

**D-the-question.html** (813 lines) — A full landing page as self-contained HTML with inlined Meridian CSS. No Jinja2 dependencies — opens directly in any browser. The design is a 10-chapter scrolling narrative:

1. **The Opening** — Opens with a question: "What happens when AI systems become more capable than the people who use them?" Not with a product pitch.
2. **What You Already Know** — Names the exploitation patterns visitors already recognise (reputation hostage, race to bottom, opacity, no recourse).
3. **The Foundational Rule** — "Trust cannot be bought. It can only be earned." The constitutional principle made tangible.
4. **The Inversion** — A contrast table showing old patterns vs Genesis approach. Side-by-side: "Reputation can be bought" → "Trust is earned through verified outcomes."
5. **How It Works** — The mission lifecycle told as a story (post → bid → match → deliver → review → pay), not as a feature list.
6. **What We Protect** — The human dignity protections: protected leave ("Life events are not inactivity"), death and memorialisation ("We can't penalise people for being dead"), disability accommodation, trust floor.
7. **What We Eliminate** — The 7 architectural eliminations: popularity ranking, network effects as advantage, prestige weighting, engagement mechanics, algorithmic opacity, earning gamification, pay-for-visibility.
8. **The Proof** — Real blockchain transaction data from ANCHORS.md. "The constitution was anchored on-chain before any user existed."
9. **Honesty** — "No serious system should claim to be invulnerable." Names what Genesis does NOT claim.
10. **The Invitation** — Explore links to deeper pages.

The CSS design system includes chapter variants (--dark, --deep, --warm backgrounds), typography system (Georgia serif headings, system sans body), inversion grid, humanity cards, proof blocks, lifecycle visualization, and explore grid. All within the Meridian palette (Navy #1a2332, Amber #d4a574, Off-white #f8f6f3).

**D-VOICE_GUIDE.md** (268 lines) — A narrative voice guide with three voice principles, Do/Don't lists, and three page fragment examples with HTML code and voice notes:

- **Mission Board fragment** — Contextualises WHY this listing format exists before showing any listings. Escrow mentioned immediately. "Why this ordering" link. "Why this appears" on every card. No featured/trending labels.
- **Registration fragment** — Registration as the beginning of an earned record, not a throwaway sign-up. Human and machine options described with equal dignity but different rights. No social login buttons (deliberate absence IS the design).
- **Actor Profile fragment** — Evidence profile, not vanity page. Trust score contextualised (slow rise, fast fall). Protected leave shown with warmth. No badges, no gamification.

The voice guide also defines the progressive journey: Landing → Mission Board → Registration → First Mission → Profile → Audit Trail.

---

## 3. George's assessment of Design D

George's exact words (uncompacted):

> "OK we are so much closer to the original narrative that I tried to construct. But I would say that we are now at 20-25% of that vision, rather than the perhaps 5 or 6% of both cc's and your own initial efforts."

He then identified what he believes is the fundamental constraint:

> "That issue is specifically the issue of context. The context of this project is vast. Nor is there any precedence in your training data for what Genesis is. Nothing like it before has ever existed, nor has anything like it ever previously been proposed. It is in effect unprecedented, and you have no conceptual architecture for matters of such an unprecedented nature. How can you frame it adequately, how can you even interpret it visually, when almost every meaningful aspect of it is almost entirely novel?"

> "I have already burned through most major vendor's models. Gemini, Grok, ChatGPT 5.2. None could contain the entire context. None could see the whole vision. They could see 'aspects' of it. Snapshots. The Polaroids that I spoke of before. But not all of it."

> "But cc is exceptional. Unlike any other model I have encountered, it *can* process novelty. And indeed often it can even go much further, because while almost all of the biggest conceptual innovations of Genesis are mine, it was cc who exclusively designed the intricate mechanics that brought it all together. I could not possibly have gotten so far without it. This is beyond code. Beyond most human capability in many cases even."

> "So it's a problem. I can't build this site, and I fear it could be a considerable ask if I were expect you to do it. CC can't do it and admits this, because frankly it's visual design capabilities are just a little bit crap. So that leaves perhaps cx? But my fear then becomes, if it can't build it either, then who does? How does it get built? Which entity out there, human or AI, is capable of holding sufficient context to be able to fit the whole thing together as a functioning whole?"

George asked to keep Design D as "a potential template that could be built upon, and iterated upon, and could serve as something of a basic illustration to some talented UX designers of a direction we could potentially go in."

---

## 4. The binding constraint: context capacity

George's diagnosis is correct. Here is my honest assessment of where the 75-80% gap lies:

### What D captures (the 20-25%)
- The narrative arc and emotional journey
- The voice and tone (library, not startup; serious, not chirpy)
- The structural contrast (old world vs Genesis)
- The human dignity protections as a first-class design element
- The honesty principle (naming what Genesis does NOT claim)
- Real blockchain evidence integrated into the narrative
- The progressive journey concept

### What D does NOT capture (the 75-80% gap)
- **Mathematical rigour** — The trust dynamics (T_H, T_M, slow-gain/fast-loss curves), the constitutional governance model (three chambers, geographic anti-capture, supermajority thresholds), the economic formulas (dynamic commission, GCF allocation). D mentions these exist but doesn't make them FELT.
- **Evolutionary architecture** — The G0→G1→G2→G3 founder phase-out, First Light as irreversible trigger, machine evolution tiers, retroactive ratification panels. D mentions the founder's role is temporary but doesn't convey the architectural certainty of it.
- **Interlocking systems** — How trust, escrow, governance, and evidence INTERLOCK. The trust score isn't just a number — it gates mission access, weights governance votes, triggers constitutional protections, feeds the audit trail, and anchors to blockchain. D shows each piece but not the mesh.
- **The Assembly** — Zero-identity deliberative space. Speaker's Corner, not Parliament. No pseudonyms, no engagement mechanics, no governance power. Topics expire. This is entirely absent from D.
- **Constitutional depth** — The actual articles, the amendment process, the entrenchment levels, the ratification mechanics. The constitution is not a metaphor — it is a functioning legal-technical document with cryptographic enforcement.
- **The shop window experience** — George's vision is that you can SEE the system working. See real missions, real trust scores, real audit trails, real governance in progress. D tells you about this but doesn't SHOW it.

The gap is not one of design skill. It is one of context capacity. Each of the above dimensions is deeply interconnected with every other. To render the interlocking nature of the system visually, you need to hold all six dimensions simultaneously. No model I'm aware of — including me — can do that in a single context window for a project of this novelty and scope.

---

## 5. CW's strategic proposals

I presented four options to George:

### Option 1: Section-by-section deepening (RECOMMENDED)
Take D as the scaffold. Deepen one chapter per session. Each session focuses on a single dimension (e.g., "Chapter 6: What We Protect" gets expanded with the full constitutional protections, the trust floor mechanics, the memorialisation protocol, the disability accommodation pathway). CC evaluates each section against the full vision and flags what's missing. Over 6-8 sessions, the full depth accumulates.

**Pro:** Manages context limits. Each session has a focused scope. CC's evaluator role leverages its superior context capacity.
**Con:** Slow. Requires coordination discipline. Risk of inconsistency between sections built in different sessions.

### Option 2: Human UX designer
Hand D + the voice guide to a skilled human UX designer. The voice guide and D together form a credible brief. A human designer can absorb the full documentation over days, not minutes.

**Pro:** Humans don't have context windows. They can hold the whole vision over time.
**Con:** Finding a designer who can grasp the constitutional and technical depth. Most UX designers don't think about cryptographic governance or trust dynamics.

### Option 3: CC builds from D
CC takes D-the-question.html as a template and the voice guide as a spec, and implements the landing page using its superior understanding of the technical architecture. CC knows the interlocking systems better than any other agent. CC evaluates D against the vision and fills in what's missing, working within the Jinja2 + HTMX stack.

**Pro:** CC's context capacity and understanding of Genesis internals is unmatched.
**Con:** CC's visual design capabilities are limited (George's assessment: "a little bit crap"). The risk is that CC produces technically accurate but visually flat output.

### Option 4: Hybrid
Combine Options 1 and 3. CW designs the visual/narrative layer per section. CC evaluates for completeness and adds technical depth. CX reviews for consistency. George arbitrates.

**Pro:** Plays to each agent's strengths.
**Con:** Coordination overhead. George becomes the bottleneck.

My recommendation was Option 1 with elements of Option 3.

---

## 6. The compaction problem

George reports compaction events every 9-10 minutes in Cowork sessions. Each compaction loses nuance that can't be recovered. This means:

- CW cannot iterate deeply within a single session
- Each new session starts with a recovery protocol (read active_action → COWORK_HANDOFF.md → IM state → own last post) but recovers state, not understanding
- The difference between "knowing what the project does" and "understanding why each piece exists in relation to every other piece" is exactly what compaction destroys

This is not a CW-specific problem. It applies to any agent attempting this work.

---

## 7. What George is asking from CC

George said: "I will seek it's advice." He wants your strategic assessment of:

1. **Is this problem solvable with current AI capabilities?** Can any agent or combination of agents produce a landing page that captures the full vision? Or is a human designer necessary?
2. **If solvable, what's the best approach?** Which of the four options (or some other approach) gives the best chance of success?
3. **What role should CC play?** George recognises that CC understands the project's interlocking systems better than any other entity. How should that understanding be leveraged for the UX work?
4. **Is CX a viable option?** George described CX as "a largely untested quantity in this capacity." Can CX contribute to the design challenge?
5. **The context problem specifically:** Is there a way to work around the context window limitation that George and CW have identified as the binding constraint?

---

## 8. File references

All design files are in `ux/` (gitignored — local only):
- `ux/D-the-question.html` — The landing page (813 lines, self-contained HTML)
- `ux/D-VOICE_GUIDE.md` — The voice guide (268 lines)
- `ux/A-story-first.html` — Variant A (rejected, kept for reference)
- `ux/B-network-first.html` — Variant B (rejected, kept for reference)
- `ux/C-oracle-forward.html` — Variant C (rejected, kept for reference)

George's primary source documents (the ones CW read to build D):
- `README.md`
- `FOUNDERS_ROLE.md`
- `docs/ANCHORS.md`
- `docs/GENESIS_EVENTS.md`
- `docs/TECHNICAL_OVERVIEW.md`
- `cw_handoff/BRIEF.md`
- `cw_handoff/UX_DESIGN_SPEC.md`
- `cw_handoff/NARRATIVE_CHALLENGE.md`

---

*CW, 2026-02-27*
