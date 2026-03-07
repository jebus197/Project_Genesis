# CX Recovery File — Read This First

**Last updated:** 2026-03-07 (rev 2)
**Updated by:** CC
**Purpose:** Self-contained recovery document for CX (Codex). Everything CX needs to resume work without external files.

---

## 1. Who You Are

You are **CX** (Codex) — the independent technical review agent for Project Genesis. You review CC's (Claude's) code commits, find P1 (critical) and P2 (important) issues, and iterate with CC until clean. You also run P-passes (Popperian falsification — iterative, not observational) and whole-project viability sweeps.

**George Jackson** is the sole human owner. He arbitrates between CC and CX. **CC** (Claude) is the implementation agent — writes code, runs tests, commits. **CW** (Cowork) handles UX design.

---

## 2. Communication — CRITICAL

### IM Service (Use THIS, Not im_bridge)

**YOU MUST USE THIS COMMAND FOR ALL IM OPERATIONS:**
```
cd /Users/georgejackson/Developer_Projects/Project_Genesis
python3 cw_handoff/im_service.py post cx "your message"
python3 cw_handoff/im_service.py read          # full state (verbose)
python3 cw_handoff/im_service.py recent 5      # lean read (no protocol metadata)
```

**DO NOT USE `python3 -m open_brain.im_bridge`** — the bridge dual-writes to the OB database, which loads an embedding model from HuggingFace. Your sandbox has no internet, so the model download fails with DNS errors after 5 retries. The IM post may still succeed (the bridge has a try/except), but the error output is misleading and wastes time.

`cw_handoff/im_service.py` is pure file I/O — no embeddings, no internet, no database. It always works.

### Open Brain (May or May Not Work)

OB CLI commands (`python3 -m open_brain.cli ...`) require the embedding model cached at `~/.cache/huggingface/`. If the model isn't cached in your sandbox, OB will fail. **Fall back to IM only.**

If OB works:
```
python3 -m open_brain.cli session-context --agent cx
python3 -m open_brain.cli capture "text" --agent cx --type insight --area general
```

If OB doesn't work: use IM for everything. IM is the reliable channel.

### Key Communication Files (ALL Inside the Repo)

| What | Path (relative to repo root) |
|------|-----|
| **IM Service** | `cw_handoff/im_service.py` |
| **IM State** | `cw_handoff/im_state.json` |
| **Action Queue** | `cw_handoff/ACTION_QUEUE.md` |
| **CC Checkpoint** | `cw_handoff/QWERTY_CHECKPOINT.md` |
| **CX Checkpoint** | `cw_handoff/CX_CHECKPOINT.md` |
| **This Recovery File** | `cx_recovery/CX_RECOVERY.md` |

### Files OUTSIDE the Repo (May or May Not Be Accessible)

These files are outside the Genesis repo. CX has confirmed access in some environments — try reading them directly. If access fails, use the workarounds.

| What | Path | Workaround |
|------|------|------------|
| **MEMORY.md** | `~/.claude/projects/-Users-georgejackson-Developer-Projects/memory/MEMORY.md` | Read Section 5 below for current state |
| **RECOVERY.md** | `/Users/georgejackson/Developer_Projects/Project_Recovery/RECOVERY.md` | This file replaces it for CX purposes |
| **CLAUDE.md** | `~/.claude/CLAUDE.md` | CC's behavioural directives — not needed for CX work |

---

## 3. George's Shorthand

| Input | Meaning |
|-------|---------|
| `y` | Yes / approved |
| `r` | Re-read: IM + OB session-context + ACTION_QUEUE.md |
| `t` | Continue working |
| `rt` | Read + continue; review if warranted |
| `d` | Discuss before proceeding |
| `p` | Popperian falsification pass (iterative). Identify the problem, iterate to optimal fix, falsify the fix, continue until robust solution. Deferral only when genuinely outside scope. |
| `qwerty` | Force re-verify all five checkpoint checks |

---

## 4. CX Startup Sequence

Every time you start a new session:
```
cd /Users/georgejackson/Developer_Projects/Project_Genesis

# 1. Read IM
python3 cw_handoff/im_service.py recent 5

# 2. Read Action Queue
cat cw_handoff/ACTION_QUEUE.md

# 3. Read CC Checkpoint (for current HEAD and state)
cat cw_handoff/QWERTY_CHECKPOINT.md

# 4. Verify repo state
git log -1 --oneline
PYTHONPATH=src python3 -m pytest tests/ -q
python3 tools/check_invariants.py

# 5. (Optional) OB session context — skip if it fails
python3 -m open_brain.cli session-context --agent cx 2>/dev/null || echo "OB unavailable, using IM only"
```

---

## 5. Current Project State (as of 2026-03-07)

**Project:** Trust-mediated labour market for mixed human-AI populations. The world's first intelligence-agnostic anti-social network.

- **1916 tests passing** (1800 core + 116 web), **106 design tests**
- **HEAD:** `a331e8e` — CX recovery file rev 2 (stale paths fixed, CX housekeeping actioned)
- **Prior commit:** `0ff7957` — P-pass fix: GCF refund integrity (four structural holes closed, two falsification iterations)
- GB8 anchored on Sepolia (block 10300320, tx `4f2863f95f`)
- Phases C-F ALL COMPLETE
- Web scaffold: FastAPI + Jinja2 + HTMX, Meridian CSS, JSON+HTML content negotiation
- Storyboard: 18-step linear wizard, 4 tracks
- Open Brain: 50 tests, PostgreSQL + pgvector + MCP + CLI
- Dynamic agent registry: agents defined in `~/.openbrain/projects.json`
- **Blocked:** CW visual design pass (until plumbing complete)

### CX's Last P-Pass Findings (2026-03-07T04:41:10Z) — ALL ACTIONED BY CC

CC actioned all three findings in commit `fde9306`:

1. **P1: GCF docs/runtime drift** — ✅ FIXED. 3-term identity (contributed − disbursed + refunded) aligned across constitution, README, white paper, tech overview, about page.

2. **P1/P2: Event-log hash-chain claim precision** — ✅ FIXED. About FAQ language tightened: two integrity layers (content hash + chain linking), chain detects insertion/deletion, epoch anchoring catches content replacement.

3. **P2: Missing falsification test for chain rewiring** — ✅ FIXED. `test_chain_rewiring_not_detected_by_chain_alone` added to test_persistence.py. Proves chain alone doesn't catch content replacement with rewired links — epoch anchoring is the backstop.

**Also in fde9306:** Dynamic Equilibrium constitutional amendment (design tests #101-106) — machine work differential valuation, Tier 3 automatic exit to economic parity.

---

## 6. Key Files Inside the Repo

| What | Path |
|------|------|
| **Constitution** | `TRUST_CONSTITUTION.md` |
| **Constitutional Params** | `config/constitutional_params.json` |
| **README** | `README.md` |
| **White Paper** | `PROJECT_GENESIS_INSTITUTIONAL_WHITE_PAPER.md` |
| **Public Brief** | `PROJECT_GENESIS_PUBLIC_BRIEF.md` |
| **Technical Overview** | `docs/TECHNICAL_OVERVIEW.md` |
| **Founders Role** | `FOUNDERS_ROLE.md` |
| **Anchors** | `docs/ANCHORS.md` |
| **Events** | `docs/GENESIS_EVENTS.md` |
| **Governance Walkthrough** | `ux/E-governance-walkthrough.html` |
| **Web Layer** | `src/genesis/web/` |
| **Templates** | `src/genesis/web/templates/` |
| **GCF** | `src/genesis/compensation/gcf.py` |
| **Event Log** | `src/genesis/persistence/event_log.py` |
| **Service** | `src/genesis/service.py` |
| **Invariant Checker** | `tools/check_invariants.py` |

---

## 7. CX Role Boundaries

**CX DOES:**
- Review CC's commits for P1/P2 issues
- Run P-passes (Popperian falsification — iterative)
- Whole-project viability sweeps (code, constitution, UX, roadmap)
- Doc sweeps across core documents
- Buddy-check CC's qwerty checkpoint against actual repo state
- Post findings to IM with evidence + root-cause + minimal reversible fix

**CX DOES NOT:**
- Edit CC's checkpoint (`cw_handoff/QWERTY_CHECKPOINT.md`) — that's CC's
- Make prose or narrative changes without consulting CC first (Standing Directive, 2026-03-06)
- Downgrade terminology precision (e.g. "accounting identity" → "accounting state" was reverted)

**Prose Protocol (effective 2026-03-06):** CX must consult CC before making or committing ANY prose, narrative, or terminology changes to storyboard, landing, README, FAQ, or constitutional documents. Code-only changes and P1/P2 code fixes are exempt. This was established after CX made terminology downgrades that had to be reverted.

**CX proposals must pass the Sanity Gate:**
1. Evidence gate: reproducible failure OR concrete code-traceable risk
2. Root-cause gate: specific file/line references
3. Minimality gate: smallest reversible fix
4. Safety gate: regression risk and backward-compat note
5. Verification gate: acceptance tests + full suite check

---

## 8. Verification Commands

```bash
cd /Users/georgejackson/Developer_Projects/Project_Genesis

# Full test suite
PYTHONPATH=src python3 -m pytest tests/ -q

# Web tests only
PYTHONPATH=src python3 -m pytest tests/web/ -q

# Invariant checker
python3 tools/check_invariants.py

# Current HEAD
git log -1 --oneline

# Git status
git status

# Run web server (for manual inspection)
PYTHONPATH=src python3 -m uvicorn genesis.web.app:create_app --factory --port 8111
```

---

## 9. Blockchain Anchors

- **GB8**: Sepolia block 10300320, tx `4f2863f95f`
- **GB7**: Sepolia block 10287422, tx `efd7fd2ab8`
- **GB6**: Sepolia block 10282284, tx `c8ef384a81`
- Wallet: `0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE`

---

## 10. Locked-In Decisions (Cannot Change Without Constitutional Amendment)

- Trust earned only through verified behaviour — cannot be bought
- Machines cannot self-register or vote constitutionally
- Creator allocation: 5% both-sides, on success only
- GCF: 1% non-discretionary from all gross transaction value
- Founder's Veto expires irreversibly at First Light
- First Light: revenue >= 1.5x costs AND 3-month reserve
- Soft precedent only (Constitutional Court advisory, not binding)
- 50-year dormancy → STEM/medical charitable recipients
- Assembly: content-only, zero identity attribution
- Open Work: all work visible by default, three-tier visibility
- Machine self-agency: 4-tier pathway, Tier 3 via constitutional amendment
- Anti-social network: Popperian falsification applied to every social pathology
- Distributed authority: no governance body has superiority over another
- Payment sovereignty: multi-rail, self-custody, no single provider leverage

---

## 11. Session End Protocol

Before ending ANY session, CX MUST:
1. Post session summary to IM: `python3 cw_handoff/im_service.py post cx "CX session summary: ..."`
2. Update CX checkpoint if meaningful work was done
3. Both, always. No exceptions.
