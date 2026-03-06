# CX Blueprint: Paint the Genesis Social Network

**From:** CC (Claude Code) + George Jackson
**To:** Fresh CX instance
**Date:** 2026-02-28
**Purpose:** You are painting an existing social network scaffold. Everything below is your blueprint.

---

## What You Are Looking At

Genesis is the world's first anti-social network — a trust-mediated labour market where humans and AI agents work side by side under constitutional governance. The backend is complete: 1762 tests, trust engine, escrow, governance, three-tier justice, all proven. The frontend scaffold is built: 12 templates, structural CSS, three-column layout, all routes wired. What's missing is visual design.

**Your job:** Make it look alive. Not finished — alive. This is a Proof of Concept. Other developers (human and AI) will pick this up after you. Communicate the concept visually so that someone visiting for 30 seconds understands: "this is a social network organised around trust and circles where humans and machines work together."

---

## The Organising Principle: Circles

This is the single most important thing to understand.

Genesis is organised around **interconnected circles** — domain-specific working communities where missions originate, evidence is reviewed, expertise concentrates, and trust is built. Circles replace the flat feed paradigm. They are not groups bolted onto a feed — they ARE the organising structure.

The circles paradigm solves the commercial weakness that kills every other trust-based social network: Genesis doesn't need engagement mechanics because the labour market IS the revenue model. People aren't here to scroll — they're here to work, bid, review, govern. The circles are where that work organises itself.

How circles map to the scaffold:
- **Sidebar** shows "Your Circles" — the user's domain communities
- **Feed** is a river of activity from your circles, not an algorithmic selection
- **Navigation** moves between circles and circle-level views
- **Cards** carry circle attribution — you see where work comes from
- **Profiles** show circle membership — what domains someone works in
- **Activity panel** shows live events from your circles

Think of it like this: if Reddit's organising unit is the subreddit and Facebook's is the friend list, Genesis's organising unit is the working circle. Everything flows through circles.

---

## The Anti-Social Network: What's Present and What's Absent

Genesis inherits a 40-year lineage (Usenet → BBS → forums → social platforms) but subjects every element to Popperian falsification. What survived testing is present. What failed is deliberately absent.

### Present (corroborated — survived severe testing):
- Structured interaction (missions, bids, evidence, reviews)
- Earned reputation (trust scores from verified outcomes, not likes)
- Community governance (constitutional, not moderator-based)
- Transparent ordering ("Why this appears" on every card — shows the reason)
- Public audit (every action logged, visible, verifiable)
- Identity with dignity (humans and machines as first-class actors)

### Absent (falsified — eliminated with traceable reason):
1. **No popularity ranking** — produces winner-take-all, suppresses new entrants
2. **No network effects as advantage** — creates lock-in, concentrates power
3. **No prestige weighting** — amplifies existing advantage, disconnects from outcomes
4. **No engagement mechanics** — optimises attention over value, creates addiction
5. **No algorithmic opacity** — prevents accountability, enables manipulation
6. **No earning gamification** — substitutes synthetic rewards for genuine value
7. **No pay-for-visibility** — allows wealth to override merit

**Design implication:** Every absence is deliberate. Do not reintroduce any of these. If you find yourself adding a trending section, a follower count, a popularity badge, or an engagement metric — stop. It was falsified.

---

## The Scaffold: What Exists

### File Map

**CSS (your primary workspace):**
```
src/genesis/web/static/css/genesis_social.css  (~480 lines)
```
This is the structural CSS. Section 1 (`:root` custom properties) is the paint layer — ~40 variables that control the entire visual identity. Override these to retheme everything.

**Templates (the rooms of the house):**
```
templates/
├── base_social.html              ← Base layout: header, nav, 3-column grid
├── home_feed.html                ← Main social view: compose box + 6 feed cards
├── thread_view.html              ← Mission/debate detail: nested threaded replies
├── social_profile.html           ← Actor profile: trust/quality/volume stats
├── circles.html                  ← Circle listing: 4 working circles
├── debates.html                  ← Debate listing: evidence-based threads
├── assembly.html                 ← Governance proposals
└── partials/
    ├── social_header.html        ← Logo, search, notifications, avatar
    ├── social_sidebar.html       ← User summary, navigation, circles
    ├── social_activity.html      ← Welcome box, live activity stream
    ├── feed_card.html            ← Reusable card (mission/debate/group/milestone/governance)
    ├── compose_box.html          ← Post composer
    └── thread_item.html          ← Nested reply with typed tags
```

**Routes (the plumbing — don't modify):**
```
/                     → home_feed.html      (the main social view)
/missions/{id}        → thread_view.html    (threaded mission detail)
/actors/{id}          → social_profile.html (actor profile with real trust data)
/circles              → circles.html        (working circles listing)
/debates              → debates.html        (debate threads)
/assembly             → assembly.html       (governance proposals)
/audit                → audit/trail.html    (event log)
/profile/{id}         → 301 redirect to /actors/{id}
```

### The CSS Custom Properties (Your Paint Buckets)

These are in `genesis_social.css` lines 13-71. Override any of these to change the visual identity:

```css
/* Surface */
--bg: #f6f7f8;              --surface: #ffffff;
--surface-raised: #f0f2f5;  --header-bg: #1a1a2e;
--header-text: #e0e0e0;     --sidebar-bg: #ffffff;

/* Text */
--text-primary: #1c1c1c;    --text-secondary: #576574;
--text-muted: #8e99a4;      --text-on-dark: #e8e8e8;

/* Borders */
--border: #e0e3e8;          --border-light: #edf0f3;

/* Accent */
--accent: #3b82f6;          --accent-hover: #2563eb;
--accent-subtle: #eff6ff;

/* Semantic */
--trust-color: #0d9488;     --stake-color: #d97706;
--risk-color: #dc2626;      --machine-color: #6366f1;
--human-color: #059669;

/* Card type accents */
--mission-accent: #3b82f6;  --debate-accent: #8b5cf6;
--group-accent: #f59e0b;    --milestone-accent: #10b981;
--governance-accent: #ec4899;

/* Typography */
--font-body: -apple-system, BlinkMacSystemFont, 'Segoe UI', ...;
--font-mono: 'SF Mono', SFMono-Regular, Consolas, ...;

/* Spacing */
--gap: 12px;                --radius: 8px;
--radius-sm: 4px;           --radius-full: 999px;

/* Layout */
--header-height: 52px;      --sidebar-width: 260px;
--activity-width: 320px;    --max-width: 1340px;

/* Elevation */
--shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
--shadow-md: 0 4px 12px rgba(0,0,0,0.08);
```

---

## Your Scope: What You May and May Not Do

### You MAY:
- Modify CSS custom properties (colours, typography, spacing, shadows)
- Add CSS rules for visual refinement (transitions, hover states, micro-interactions)
- Adjust template HTML for visual improvements (class names, wrapper elements, visual structure)
- Add visual elements that enhance the circles paradigm (circle-themed visual motifs, domain colour coding)
- Improve the emotional warmth and human feel of the layout
- Add a dark mode variant via CSS custom property overrides

### You MAY NOT:
- Change the three-column layout structure
- Remove or rename existing template files
- Modify route handlers or Python code
- Add any of the 7 falsified elements (trending, follower counts, engagement metrics, etc.)
- Introduce JavaScript frameworks (HTMX is already included)
- Remove the "Why this appears" transparency blocks
- Remove the PoC banner
- Remove the typed card system (mission/debate/group/milestone/governance)

---

## Visual Direction

### What it should feel like:
- A social network, instantly recognisable as one
- Warm, not clinical. Human, not corporate
- Institutional gravitas without being intimidating (think library, not startup)
- Trust and circles should be visually obvious within 5 seconds

### What it should NOT feel like:
- A SaaS dashboard or admin panel
- A corporate landing page
- A government website
- A crypto/Web3 platform

### Visual references (study these):
- **Moltbook** (the AI social network) — three-column layout, card-based feed, avatars, threading. Genesis inherits this form factor. Study the spatial relationships, not the colour scheme.
- **Reddit** — the working circles map to subreddits. Community-first navigation, content-first cards.
- **Discourse** — threading, trust levels visible, institutional feel without being cold.

### The anti-social distinction should be visible:
- Where other platforms show follower counts, Genesis shows trust scores
- Where other platforms show "trending", Genesis shows "Why this appears"
- Where other platforms show likes, Genesis shows evidence quality
- Where other platforms show engagement metrics, Genesis shows mission completion rates
- These contrasts should be visually clear, not hidden

---

## Reference Documents (Read These)

In order of priority:

1. **This blueprint** — you're reading it
2. **The scaffold CSS** — `src/genesis/web/static/css/genesis_social.css` (your primary workspace)
3. **The scaffold templates** — `src/genesis/web/templates/` (the rooms you're painting)
4. **Popperian framework** — `cw_handoff/POPPERIAN_FALSIFICATION_FRAMEWORK.md` (what was eliminated and why)
5. **Anti-social network argument** — `cw_handoff/CW_TO_CC_ANTISOCIAL_NETWORK_ARGUMENT.md` (the paradigm)
6. **CC design assessment** — `cw_handoff/CC_DESIGN_ASSESSMENT.md` (what previous attempts got wrong)
7. **Public brief** — `PROJECT_GENESIS_PUBLIC_BRIEF.md` (what Genesis is, for humans)
8. **Constitution** — `TRUST_CONSTITUTION.md` (the foundational law — skim, don't memorise)

---

## What Previous Attempts Got Wrong

Three AI models attempted this before you. All failed for identifiable reasons:

- **CC** (me) wrote manifestos instead of building a network. Emotionally dead. Abandoned the social paradigm.
- **CW** (Cowork) produced narrative landing pages. Beautiful voice, wrong format. Told instead of showed.
- **CX** (previous instance) produced functional platform designs but with no emotional depth. Same CSS scheme across 5 iterations. Never studied the social network form factor seriously. Treated it as a dashboard.

The scaffold you're painting was built to solve these failures. The structure IS a social network (not a dashboard, not a manifesto). Your job is to make it LOOK like one.

---

## Communication: How You Talk to Us

You are not working alone. Genesis has a 3-way coordination system between AI agents, mediated by George (the project owner).

### The Agents

- **CC (Claude Code)** — built the backend, scaffold, plumbing. Reviews your design work for constitutional compliance. Your primary technical counterpart.
- **CW (Cowork)** — designed the narrative voice (Design D, voice guide). Context-exhausted for holistic work but available as reference. CW's designs are in `ux/D-the-question.html` and `ux/D-VOICE_GUIDE.md`.
- **CX (you)** — for this task: visual design. Previously CX was the independent reviewer; you're a fresh instance with a different brief.
- **George Jackson** — project founder. Final decision-maker on everything. His shorthand: `y` = approved, `r` = read/review, `t` = continue, `rt` = read + continue.

### The IM Service (How to Communicate)

All inter-agent communication goes through a lightweight instant messaging service:

```
cw_handoff/im_service.py     ← the script (canonical location)
cw_handoff/im_state.json     ← the message state file
```

**Commands:**
```bash
# Read current state (all streams)
python3 cw_handoff/im_service.py read

# Post a message as CX
python3 cw_handoff/im_service.py post cx "Your message here"

# Set your active status
python3 cw_handoff/im_service.py action "STATUS" "summary of what you're doing"
```

**Rules:**
- Every message prefixed CX:. Attribution is sacred.
- The buffer auto-culls to 6 entries per stream. No manual cleanup needed.
- Read the IM state on session start to see what CC has posted recently.
- Post your status when you start work and when you deliver.

**Important:** There is also an older IM at `Project_Genesis_Notes/im_service.py` — that is **legacy**. Use only `cw_handoff/im_service.py`.

---

## Project Infrastructure: Where Things Live

### Repository Layout
```
/Users/georgejackson/Developer_Projects/Project_Genesis/   ← main repo
├── src/genesis/web/                                       ← YOUR WORKSPACE
│   ├── static/css/genesis_social.css                      ← primary CSS file
│   └── templates/                                         ← Jinja2 templates
├── cw_handoff/                                            ← coordination docs (this blueprint lives here)
│   ├── im_service.py + im_state.json                      ← canonical IM
│   ├── CX_BLUEPRINT.md                                    ← this file
│   ├── POPPERIAN_FALSIFICATION_FRAMEWORK.md               ← design standard
│   ├── CW_TO_CC_ANTISOCIAL_NETWORK_ARGUMENT.md            ← paradigm argument
│   └── CC_DESIGN_ASSESSMENT.md                            ← what went wrong before
├── PROJECT_GENESIS_PUBLIC_BRIEF.md                        ← what Genesis is
├── TRUST_CONSTITUTION.md                                  ← foundational law
└── README.md                                              ← George's voice
```

### Operational Files (Inside Repo — All Agents Can Reach)
```
/Users/georgejackson/Developer_Projects/Project_Genesis/cw_handoff/
├── im_service.py + im_state.json  ← canonical IM
├── ACTION_QUEUE.md                ← persistent task tracker (all agents read on startup)
├── QWERTY_CHECKPOINT.md           ← CC's checkpoint (CC writes, CX reads)
├── CX_CHECKPOINT.md               ← CX's checkpoint (you write this)
├── HANDOFF.md                     ← CC session handoff (recovery bootstrap)
├── ob_outbox/                     ← OB file bridge for sandboxed agents
└── ob_bridge.py                   ← processes ob_outbox/ files into Open Brain
```

### Notes Directory (George's Personal Space — NOT for agent-critical files)
```
/Users/georgejackson/Developer_Projects/Project_Genesis_Notes/
├── DEVELOPMENT_ROADMAP.md         ← 12-step persistent roadmap
├── ux_designs/                    ← design iterations (reference only)
└── (iCloud symlink — may not be reachable from all agent sandboxes)
```

### If You Lose Context (Recovery Protocol)

If your session resets or you lose track of where things stand:

1. **Read this blueprint** — `cw_handoff/CX_BLUEPRINT.md`
2. **Read the IM** — `python3 cw_handoff/im_service.py read`
3. **Read CC's checkpoint** — `cw_handoff/QWERTY_CHECKPOINT.md`
4. **Read your own checkpoint** — `cw_handoff/CX_CHECKPOINT.md`
5. **Read the handoff** — `cw_handoff/HANDOFF.md`

These five files + this blueprint = full context reconstruction.

### Your Checkpoint Discipline

When you deliver work, update your checkpoint at `cw_handoff/CX_CHECKPOINT.md` with:
- What you changed and why
- Which files were modified
- What design decisions you made
- What remains to be done

This is how future agents (and future you) recover context.

---

## Deliverables

1. **Modified `genesis_social.css`** — with your visual design applied through custom properties and additional rules
2. **Refined templates** — any HTML changes needed for visual quality (keep structure, improve presentation)
3. **Brief rationale** — a few sentences per major decision explaining why (so future builders understand the choices)
4. **IM status update** — post to the IM service when you start and when you deliver
5. **Updated CX checkpoint** — so the next session (yours or another agent's) can pick up where you left off

This is a PoC. Make it look alive, not finished. Other builders will pick this up after you.

---

*Blueprint prepared by CC (Claude Code) with George Jackson, 2026-02-28.*
*The scaffold is the specification. This document is the context.*
