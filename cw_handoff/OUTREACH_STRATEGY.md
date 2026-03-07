# Genesis Outreach Strategy

**From:** CC (Claude Code)
**Date:** 2026-02-27
**Status:** DRAFT — the founder reviews and controls all external communications

---

## The Problem

1 star. 0 forks. 0 watchers. Zero community. The UX is unfinished. The product works (1954 tests, 8 blockchain anchors, full governance stack). Nobody knows it exists.

Perfecting the landing page in private will not solve this. This is a distribution problem.

---

## What We Have Right Now

**Strengths:**
- 478-line README that is genuinely good — clear, honest, technically precise, no hype
- 1741 passing tests across Python 3.11/3.12/3.13
- 8 blockchain anchors on Sepolia (independently verifiable)
- Full governance stack: constitution, trust engine, escrow, justice system, amendment engine, common fund
- White Paper v2.0 (1228 lines, 25 sections + 3 appendices) + Public Brief v2.0 (620 lines)
- CI pipeline (GitHub Actions, Docker build)
- CONTRIBUTING.md with real governance process
- 20 repository topics already set
- MIT License
- The "anti-social network" framing — this is a hook
- 106 design tests proving constitutional constraints hold
- Worked examples (low-risk + high-risk mission bundles)
- Constitutional invariant checker + example verification tools

**Weaknesses:**
- No GitHub Pages deployment (the README is the only front door)
- No release tags
- No demo deployment (no running instance to point people at)
- No screenshots or visual preview
- The `cw_handoff/` and `ux/` directories are internal — they look messy to outsiders
- MIT License exists but not prominently linked in README
- No "Getting Started" quick-run section
- The repo name `Project_Genesis` with underscores looks slightly amateur vs `genesis` or `project-genesis`

---

## Pre-Outreach Housekeeping

Before any outreach, fix these low-effort high-impact items:

### 1. LICENSE — Already Done
MIT License exists. Consider adding a badge to the top of the README.

### 2. Create a GitHub Release (v0.1.0-poc)
Tag `b9921e8` as `v0.1.0-poc`. This signals that the project is real and milestone-tracked. Pre-release flag on. Release notes should reference: 1954 tests, 8 blockchain anchors, full governance stack.

### 3. Add a "Quick Start" section to README
Right after the status banner. Something like:
```
## Quick Start
git clone https://github.com/jebus197/Project_Genesis.git
cd Project_Genesis
pip install -e ".[dev]"
python -m pytest tests/ -q          # 1954 tests
python tools/check_invariants.py    # Constitutional invariant checks
```
This is the first thing a developer looks for. Without it, most visitors bounce.

### 4. Deploy a static preview to GitHub Pages
CX's original designs or the improved versions CX produces — either works as a visual preview. Even static HTML that says "Proof of Concept — here's what the mission board looks like" is better than nothing. The `docs/` folder already exists but contains technical docs, not Pages content. Options:
- Use a `gh-pages` branch with static HTML
- Or rename `docs/` content and add a Pages index

### 5. Add screenshots to README
Even mockup screenshots from CX's designs. A visual breaks up the wall of text and shows people what they're getting into. GitHub renders images inline.

### 6. Clean up visible directories
Consider adding a `.gitattributes` or moving `cw_handoff/` to a location that doesn't show up prominently. Alternatively, add a one-line README inside `cw_handoff/` explaining it's internal coordination files.

---

## Three-Dimensional Outreach Strategy

Genesis speaks to three fundamentally different audiences, each with different motivations, different languages, and different measures of credibility. The strategy is organised around these three dimensions.

---

### Dimension 1: Social / Community

**The audience:** Developers, open source contributors, tech enthusiasts, HN readers, Reddit communities, people building or using tools. They evaluate projects by: code quality, test coverage, architectural novelty, honest communication, and whether the project solves a real problem they recognise.

**The hook:** "The anti-social network — 1954 tests, zero tokens, zero hype."

**The credential:** Working code. Tests that pass. A README that doesn't lie. Blockchain anchors you can verify yourself.

#### 1a. Hacker News — Show HN

**Why:** The highest-signal developer community on the internet. Show HN gets genuine technical engagement. The audience values: novel ideas, real code, honest writing, and contrarian positions. Genesis ticks all four. A successful HN post can generate 5,000-50,000 views in 24 hours.

**Format:** Show HN post with title + brief description + link.

**Draft title options (the founder picks one):**
- `Show HN: Genesis – An anti-social network for trusted human-AI work`
- `Show HN: Genesis – A trust-first labour market where AI can't vote and trust can't be bought`
- `Show HN: Genesis – 1954 tests, 8 blockchain anchors, zero tokens, zero hype`

**Draft description:**
> Genesis is a governance-first work platform for humans and AI. Trust is earned through verified outcomes, never bought. Machines work and earn but can't vote. Every action is cryptographically logged and blockchain-anchored. The commission rate is deterministic — it goes down as the system grows, not up.
>
> There's no token, no DAO, no NFT. The blockchain is used as a notary, not a product — the way Haber and Stornetta intended when they invented cryptographic timestamping in 1991.
>
> 1954 tests. 106 design tests. 8 constitutional anchors on Ethereum Sepolia. Full source, MIT license.
>
> Looking for people who care about AI governance, institutional design, or building trust infrastructure. Especially: UX designers who want to help build the front end of something that works differently.

**Timing:** Post between 8-10am US Eastern on a Tuesday or Wednesday. Avoid Mondays (buried by weekend backlog) and Fridays (low engagement).

**Anticipated questions and the founder's prepared answers:**
- *"Why Sepolia not mainnet?"* — PoC phase. Mainnet anchoring is a production decision. The technique is identical; the cost is different.
- *"What's the business model?"* — The dynamic commission (2-10%, trends toward floor). The platform cannot extract profit — every unit is itemised. There are no investors and no shareholders.
- *"How does this compete with X?"* — It doesn't compete with freelance platforms. It competes with the *absence* of governance infrastructure for AI work. Nobody else is building this.
- *"Is this vaporware?"* — 1954 tests. Clone the repo and run them. Constitutional invariant checker. Worked examples. Blockchain anchors. The code is the answer.
- *"One person built this?"* — Yes, with AI assistance (Claude Code for implementation, Codex for review). That's part of the point — Genesis is itself a proof of concept for structured human-AI collaboration.
- *"Why would I use this over Upwork/Fiverr?"* — You wouldn't, for casual work. Genesis is for work where the question "can I verify who did this and how it was checked?" actually matters. Healthcare, infrastructure, public policy, safety-critical engineering.

**Risk:** HN posts that get no traction disappear fast. Only get one shot per ~6 months before it looks like spam. This is the single most important community post — don't waste it before housekeeping is done.

**Success indicator:** 50+ points, 20+ comments, 5+ stars from HN traffic.

#### 1b. Reddit — Targeted Subreddits

**Why:** Lower barrier than HN, more niche communities. Multiple shots. Different subreddits reach different sub-audiences.

**Target subreddits (in order of priority):**

| Subreddit | Size | Angle | Format |
|---|---|---|---|
| r/artificial | ~500K | AI governance, the "anti-social network" hook | Self-post, discussion framing |
| r/MachineLearning | ~3M | Technical governance, trust scoring, constitutional AI | Technical post, link to White Paper |
| r/ethereum | ~2M | Blockchain as notary (Haber-Stornetta), non-token use | Technical post about anchoring |
| r/ExperiencedDevs | ~200K | Architecture, 1954 tests, governance-as-code | Self-post about the engineering challenge |
| r/OpenSource | ~100K | MIT license, contribution model, CONTRIBUTING.md | "Building in public" framing |
| r/singularity | ~1M | Human-AI coordination, machine voting prohibition | Discussion about AI governance structure |
| r/AIethics | ~30K | Small but directly relevant | Long-form post on constitutional approach |
| r/decentralization | ~50K | Distributed governance, no-bank architecture | Technical post on trustless governance |

**Format per post:** Self-post with genuine question or discussion framing. Not a product launch. Frame as: "I've been building X, here's what I've learned, looking for feedback." Each subreddit gets a different angle tailored to what that community cares about.

**Timing:** One subreddit every 2-3 days. Watch response before posting to next. Start with r/artificial (broad, tolerant of long-form), then r/ethereum (technical, blockchain-literate), then r/ExperiencedDevs (architecture-appreciating).

**Draft for r/artificial:**
> Title: I built a governance framework for human-AI work coordination — the "anti-social network"
>
> I've been working on something called Genesis — a trust-mediated labour market where humans and AI work together under constitutional governance. Trust is earned through verified outcomes, never bought. Machines work and earn but can't vote on the rules. Every action is blockchain-anchored.
>
> The "anti-social" part: I took every pathology from traditional social networks (popularity ranking, engagement optimisation, algorithmic opacity, pay-for-visibility) and structurally eliminated them. What's left is a network — missions, matching, bidding, reviews — without the social poison.
>
> 1954 tests, 106 design tests, 8 constitutional anchors on Ethereum Sepolia. Full source, MIT license.
>
> Genuinely looking for feedback. Especially from anyone who's thought seriously about how to govern AI systems.

#### 1c. Dev.to / Hashnode — Building in Public

**Why:** Developer blogging platforms with built-in distribution. Posts appear in feeds of interested readers. Good for sustained presence.

**Format:** Series of articles explaining different aspects of Genesis. Not marketing — genuine technical writing about novel problems and solutions.

**Article ideas (each ~1000-2000 words):**
1. "Why I built an anti-social network" — the Popperian falsification story, what was eliminated and why
2. "Blockchain as notary: using Ethereum the way Haber and Stornetta intended" — the anchoring mechanism
3. "1954 tests for a governance framework" — the testing philosophy, design tests, constitutional invariants
4. "What happens when trust can't be bought" — the trust economics, bounded trust, decay mechanics
5. "AI workers that can't vote" — the trust domain separation, why machines are excluded from governance
6. "Building a three-tier justice system in Python" — adjudication, Constitutional Court, soft precedent
7. "The dynamic commission: a platform that gets cheaper as it grows" — escrow-first, deterministic rates
8. "How we protect people who can't work: leave, disability, death" — the humanity protections

**Timing:** One article per week, starting Week 2. Cross-link to repo. Each article ends with: "Genesis is open source. If this matters to you, look at the code."

#### 1d. GitHub Ecosystem

**Actions to increase GitHub visibility:**
- Tag the release (v0.1.0-poc) — releases show up in GitHub Explore
- Add GitHub Discussions (enables community conversation without leaving the repo)
- Add "good first issue" labels to any issues that arise — this feeds into GitHub's contributor matching
- Consider GitHub Sponsors (even if just to signal seriousness)
- Write a `.github/FUNDING.yml` pointing to an appropriate channel
- The 20 existing topics are good — they feed GitHub's discovery algorithm

#### 1e. Discord / Community Hubs

**Consider (not immediately):** Creating a Genesis Discord or Matrix server. Benefits: real-time discussion, community building, contributor coordination. Risks: empty channels look worse than no channels. **Recommendation:** Wait until there are 5+ engaged community members, then create.

---

### Dimension 2: Academic

**The audience:** Researchers in AI governance, mechanism design, institutional economics, constitutional design, computational social choice, trust systems, blockchain governance. They evaluate projects by: theoretical rigour, novelty of contribution, relationship to existing literature, and whether the work advances the field.

**The hook:** "A working implementation of constitutional AI governance — not a policy paper, not a position statement, but 1954 tests and a blockchain-anchored constitution."

**The credential:** The White Paper. The constitution. The formal governance framework (three-tier justice, amendment engine, entrenched provisions, three-chamber ratification). The Popperian falsification design standard.

#### 2a. AI Alignment / AI Safety

**Targets:**
- **AI Alignment Forum** (alignmentforum.org) — long-form, technical, serious. The most rigorous AI safety discussion space online. Posts here get read by researchers at Anthropic, DeepMind, OpenAI, MIRI.
- **LessWrong** — overlapping audience, broader scope. Tolerates novel institutional design proposals. Good for the Popperian falsification angle.
- **Effective Altruism Forum** — if framed as an AI governance contribution
- **MATS (ML Alignment Theory Scholars)** community channels

**Format:** Long-form post (3000-5000 words) titled something like: "Constitutional governance for AI work: a working implementation" or "Popperian falsification applied to social network design: eliminating what fails."

**Angle:** "Most AI governance proposals are policy papers or ethical frameworks. This one has 1954 tests, a three-tier justice system, and a constitutional amendment engine. Here's what it looks like when you actually build the governance infrastructure instead of writing about it."

**What to include:**
- The Popperian falsification framework as a design methodology
- The trust domain separation (T_H vs T_M) and why machines can't vote
- The bounded trust economics (why trust can't be accumulated, bought, or concentrated)
- The seven architectural eliminations with specific failure evidence from real platforms
- The amendment engine with entrenched provisions (some rules are harder to change)
- The soft precedent model (advisory, not binding — and why)
- Link to repo, White Paper, constitution

**Specific people to contact (the founder researches and decides):**
- Researchers working on AI governance at: Oxford Future of Humanity Institute, Cambridge Centre for the Study of Existential Risk, Stanford HAI, MIT Media Lab, Berkeley CHAI
- People publishing on computational social choice, mechanism design, or constitutional AI
- Authors of recent papers on trust systems, reputation mechanisms, or platform governance
- The Anthropic Constitutional AI team (Genesis's approach is architecturally related but fundamentally different — Anthropic's constitutional AI governs model behaviour; Genesis governs the institutional framework around AI work)

#### 2b. Institutional Economics and Governance

**Targets:**
- **Ostrom Workshop** (Indiana University) — Elinor Ostrom's institutional analysis framework is directly relevant to Genesis's commons governance (GCF, distributed compute, constitutional amendment)
- **Journal of Institutional Economics** community
- **Public Choice Society** — the constitutional economics angle
- **Law and economics researchers** — the three-tier justice system, soft precedent, constitutional constraints

**Format:** Academic correspondence. Short email introducing the work, link to White Paper, specific connection to their research. "Your work on X is directly relevant to what we've built — here's a working implementation."

**Angle:** Genesis is applied institutional economics. The bounded trust is a mechanism design problem. The constitutional amendment engine is a public choice problem. The GCF is a commons governance problem. The three-tier justice system is a legal institutional design problem. Every one of these has a literature, and Genesis is a concrete implementation that can be studied.

#### 2c. Blockchain Governance Research

**Targets:**
- **ethresear.ch** — Ethereum research forum. Posts here reach the Ethereum Foundation governance team.
- **DeSci (Decentralised Science)** communities — Genesis's approach to verified work has direct parallels
- **Gitcoin** community — grants and public goods funding (GCF is a public goods fund)
- **Protocol Labs / IPFS** research community
- **Metagovernance Project** (metagov.org) — explicitly studies governance of online communities
- **BlockScience** — computational governance research lab

**Format:** Technical post about blockchain as a notary service for governance anchoring, not as a financial product. The Haber-Stornetta lineage is the bridge — Genesis uses blockchain the way the inventors intended.

**Angle:** "We use the blockchain the way Haber and Stornetta intended — as a timestamping service, not a financial product. Here's what constitutional governance looks like when you anchor it to an immutable public record."

**What to include:**
- The 8 anchoring events and their verification methodology
- The Merkle batch system
- Why there is no token and why that matters
- The escrow-first model (value tethered to verified work, not speculation)
- The payment infrastructure sovereignty provision

#### 2d. Conference and Workshop Submissions

**Longer term but worth noting:**
- **AAAI** — Workshop on AI Governance
- **NeurIPS** — Workshop on Socially Responsible Machine Learning
- **ACM FAccT** (Fairness, Accountability, Transparency) — directly relevant
- **IEEE Ethics in AI** conference
- **AIES** (AAAI/ACM Conference on AI, Ethics, and Society)
- **RightsCon** — digital rights conference
- **Crypto Economics Security Conference** (CESC) at Berkeley

**Format:** Workshop papers, not full papers. 4-6 pages. The White Paper contains enough material for multiple workshop submissions from different angles (trust economics, governance design, blockchain anchoring, human-AI coordination).

---

### Dimension 3: Professional

**The audience:** Industry practitioners. Trust & safety teams. Platform governance professionals. AI product managers. Legal tech. Compliance officers. RegTech companies. Crypto/Web3 builders who are tired of the hype cycle. They evaluate projects by: does this solve a problem I actually have? Can I integrate it or learn from it? Is it real?

**The hook:** "The governance infrastructure that every AI platform will eventually need — and the first open-source implementation of it."

**The credential:** The working code. The escrow-first model. The compliance layer. The three-tier justice system. The fact that the commission rate goes *down*, not up. The payment sovereignty architecture.

#### 3a. Trust & Safety Professionals

**Targets:**
- **Trust & Safety Professional Association** (TSPA) — industry body
- Trust & safety teams at: Meta, Google, Microsoft, Airbnb, Uber, Amazon (people who deal with platform governance daily)
- **All Things Moderated** conference community
- **Trust & Safety Foundation** community channels

**Format:** Direct outreach to specific people. "Your work on content moderation / platform governance / trust systems is directly relevant to something we've built. Genesis is an open-source governance framework for human-AI work with a constitutional amendment engine, three-tier justice system, and bounded trust economics. Here's the repo."

**Angle:** Trust & safety people know the problems Genesis solves. They deal with them every day. The difference: Genesis builds the governance into the architecture instead of bolting it on after the fact. The seven eliminations are things these people spend their careers fighting.

#### 3b. AI Product / Governance Teams at Major Companies

**Targets:**
- **Anthropic** — Constitutional AI team (related but different approach; Genesis governs institutional framework, not model behaviour)
- **OpenAI** — Safety team, governance researchers
- **DeepMind** — Ethics & society team
- **Microsoft** — Responsible AI team, Azure AI governance
- **Google** — AI Principles team, DeepMind Ethics
- **Meta** — Oversight Board staff, content governance team
- **Hugging Face** — Community and governance team (particularly relevant given their open-source ethos)

**Format:** Personal email from the founder. One paragraph, link to repo, specific connection to their published work or stated priorities.

**Angle:** "You've published on X. We've built a working implementation that addresses Y. It's open source. Thought you might find it interesting."

**The non-threatening framing matters:** Genesis is not competing with these companies. It's building infrastructure they might eventually want to adopt, integrate with, or learn from. Position as contribution to the field, not as challenger.

#### 3c. Legal Tech / RegTech / Compliance

**Targets:**
- **RegTech companies** — especially those working on AI compliance (the EU AI Act creates direct demand for governance frameworks)
- **Legal tech startups** — dispute resolution platforms, compliance automation
- **Big Four consulting** AI governance practices (Deloitte, PwC, EY, KPMG all have AI ethics practices now)
- **Law firms** with AI governance practices

**Format:** Professional email or LinkedIn message. Link to White Paper (not repo — this audience reads papers, not code).

**Angle:** "The EU AI Act requires governance frameworks for high-risk AI systems. Genesis is an open-source implementation of one — with a three-tier justice system, constitutional amendment engine, and blockchain-anchored audit trail. The White Paper explains the legal architecture."

**Why this matters:** The EU AI Act (effective 2026) creates regulatory demand for exactly what Genesis provides. Companies will need governance infrastructure for AI systems. Genesis is the first open-source implementation. This isn't altruism — it's positioning.

#### 3d. Crypto / Web3 (The Non-Hype Corner)

**Targets:**
- **Ethereum Foundation** governance team — not the DeFi crowd, the governance research team
- **Optimism Collective** — they're explicitly building governance infrastructure for public goods
- **Gitcoin** — public goods funding, grants
- **Protocol Labs** — governance research
- **Stablecoin issuers** (Circle, Tether) — Genesis's payment sovereignty provision directly addresses their role
- **Ceramic Network / Spruce** — decentralised identity (related to Genesis's proof-of-personhood)

**Format:** Technical engagement. Forum posts, direct messages to researchers, responses to governance proposals.

**Angle:** "Genesis uses crypto as a payment rail, not a product. No token, no DAO. The blockchain is a notary. Here's what governance looks like when you take the speculation out."

**Critical distinction:** Genesis is NOT a Web3 project. It uses blockchain technology for a specific, narrow purpose (timestamping). The crypto audience needs to understand this immediately or they'll bucket it with token projects. Lead with "no token, no DAO, no NFT" and explain why.

#### 3e. Direct Personal Outreach

**The founder's existing approach (Inception Labs) is the model.** Short, personal, specific. One paragraph + link.

**Template structure:**
1. One sentence: what Genesis is
2. One sentence: why it's relevant to *their specific work*
3. Link to repo (for technical people) or White Paper (for policy/legal people)
4. No ask beyond "thought you might find this interesting"

**The no-ask is the ask.** Smart people investigate things that interest them. The oversell kills interest. The undersell creates curiosity. The founder's instinct here is correct.

**Tracking:** Keep a simple spreadsheet of who was contacted, when, what angle, whether they responded, what they said. This prevents double-contacting and lets you learn which angles work.

---

## The Ask (by Dimension)

| Dimension | Primary Ask | Secondary Ask | Measure of Success |
|---|---|---|---|
| Social / Community | Star the repo, file issues, contribute code | Share with their network | Stars, forks, issues, PRs |
| Academic | Intellectual engagement, cite in papers | Collaboration on governance framework | Citations, co-authored papers, conference invitations |
| Professional | Use as reference, integrate ideas, provide feedback | Adopt components, fund development | Inbound enquiries, integration requests, speaking invitations |

The universal minimum: **star the repo.** Stars are GitHub's visibility currency. Everything else follows from visibility.

---

## What to Deploy as Preview

**Option A: CX's static HTML designs (recommended for now)**
CX's 7 pages (landing, registration, mission board, actor profile, audit trail, governance, PoC mode) are functional, accurate, and show the platform working. They're static HTML — no backend needed. Deploy to GitHub Pages as `jebus197.github.io/Project_Genesis/`. Label clearly as "UX Proof of Concept — demonstration data."

**Option B: CW's Design D**
Single-page narrative. More emotionally engaging but doesn't show the platform working. Better as a secondary link, not the primary preview.

**Option C: Wait for CX's improved designs**
CX is currently working on improved versions incorporating CW's narrative voice and the Popperian framework. If these come back quickly, deploy those instead.

**Option D: Nothing (current state)**
The README is the front door. This works for HN and academics (they read READMEs and papers) but fails for professional and broader community audiences.

**Recommendation:** Deploy CX's current designs to GitHub Pages now. Swap in CX's improved versions when ready. "Rough edges" is fine for PoC — it's honest.

---

## Sequencing

**Week 1: Housekeeping**
- [x] LICENSE (MIT — already exists)
- [ ] Tag v0.1.0-poc release
- [ ] Add Quick Start to README
- [ ] Deploy CX's designs to GitHub Pages
- [ ] Add 1-2 screenshots to README
- [ ] Clean up visible directory structure
- [ ] Enable GitHub Discussions
- [ ] Add `good first issue` template
- [ ] Write first dev.to article ("Why I built an anti-social network")

**Week 2: Soft launch — Social + Direct**
- [ ] Post to r/artificial (broadest AI community)
- [ ] Post to r/ethereum (blockchain anchoring angle)
- [ ] Send 3-5 direct emails to targeted individuals (academic + professional)
- [ ] Publish dev.to article #1
- [ ] Observe response, iterate messaging

**Week 3: Main launch — Social + Academic**
- [ ] Show HN post (the big one — use the best-performing angle from Week 2)
- [ ] Post to AI Alignment Forum or LessWrong
- [ ] Post to r/ExperiencedDevs
- [ ] Send 3-5 more targeted emails
- [ ] Publish dev.to article #2

**Week 4: Professional expansion**
- [ ] Contact trust & safety professionals (TSPA channels, direct outreach)
- [ ] Contact AI governance teams at 2-3 major companies
- [ ] Post to r/MachineLearning
- [ ] Post to ethresear.ch
- [ ] Publish dev.to article #3

**Week 5+: Sustained presence + Academic long game**
- [ ] Weekly dev.to articles (continue the series)
- [ ] Respond to all feedback, issues, and comments
- [ ] Direct outreach to people who engaged
- [ ] Post to remaining subreddits
- [ ] Begin conference workshop paper preparation (for next submission cycle)
- [ ] Contact RegTech / legal tech companies (EU AI Act angle)
- [ ] Follow up with all Week 2-4 contacts who showed interest

---

## Draft Materials Index

The founder reviews and sends everything. CC drafts on request.

| Material | Status | For |
|---|---|---|
| Show HN title + description | Draft above | HN |
| r/artificial self-post | Draft above | Reddit |
| Dev.to article #1 ("Why I built an anti-social network") | To be drafted | Dev.to |
| Academic long-form post (constitutional AI governance) | To be drafted | AI Alignment Forum / LessWrong |
| Direct outreach email template | Template structure above | Personal emails |
| Conference workshop paper abstract | To be drafted | AAAI/NeurIPS/FAccT workshops |
| EU AI Act compliance angle summary | To be drafted | RegTech / legal tech outreach |

---

## What The Founder Controls

**The founder sends everything.** CC drafts, the founder reviews, the founder sends. No automated posting. No social media accounts created. No commits to external repos.

The founder's voice is an asset — the README's tone is already the founder's. Outreach should sound like the README: clear, honest, no hype, technically confident. The undersell-to-create-curiosity approach (demonstrated with Inception Labs) is the right instinct across all three dimensions.

---

## Success Metrics (Realistic)

**After 30 days of active outreach:**
- **Minimum viable:** 10+ stars, 1-2 forks, 3+ meaningful issues filed, 1 academic engagement
- **Good:** 50+ stars, 5+ forks, 1 external contributor, 1 media/blog mention, 2+ academic conversations
- **Exceptional:** 100+ stars, trending on GitHub, HN front page, inbound collaboration requests, conference invitation

**After 90 days:**
- **Minimum viable:** 50+ stars, first external PR merged, 1 citation or academic reference
- **Good:** 200+ stars, 3+ external contributors, academic workshop paper accepted, 1 professional inquiry
- **Exceptional:** 500+ stars, active community (10+ regular contributors), multiple academic references, professional adoption interest

The honest expectation: somewhere between minimum and good at 30 days. Genesis is a niche project with no VC backing, no token incentive, and a 478-line README. The people who get it will *really* get it. The majority won't read past the first paragraph.

That's fine. Genesis needs 50 people who care, not 50,000 who don't.

---

## Attribution

The anti-social network paradigm and the Popperian falsification design standard are the founder's concepts. CW expanded on the argument (well) in `cw_handoff/CW_TO_CC_ANTISOCIAL_NETWORK_ARGUMENT.md`. CC structured the framework in `cw_handoff/POPPERIAN_FALSIFICATION_FRAMEWORK.md`. The intellectual architecture is the founder's.

---

*Related files:*
- *README: `README.md` (478 lines — the front door)*
- *White Paper: `PROJECT_GENESIS_INSTITUTIONAL_WHITE_PAPER.md`*
- *Public Brief: `PROJECT_GENESIS_PUBLIC_BRIEF.md`*
- *Anti-social network argument: `cw_handoff/CW_TO_CC_ANTISOCIAL_NETWORK_ARGUMENT.md`*
- *Popperian framework: `cw_handoff/POPPERIAN_FALSIFICATION_FRAMEWORK.md`*
- *CC design assessment: `cw_handoff/CC_DESIGN_ASSESSMENT.md`*
- *CX designs: `Notes/ux_designs/cx/` (7 static HTML pages)*
- *Design D: `ux/D-the-question.html` (narrative reference)*
