# CC Session Handoff Note

**Written:** 2026-02-17T01:00Z
**By:** CC (Claude), CX P1/P2 fix session
**Purpose:** Everything a new CC session needs to bootstrap reliably.

---

## 1. Project Identity

**Project Genesis** — trust-mediated labour market for mixed human-AI populations. World's first intelligence-agnostic anti-social network.

- **Owner:** George Jackson
- **Repo:** `github.com/jebus197/Project_Genesis`
- **Local:** `/Users/georgejackson/Developer_Projects/Project_Genesis/`
- **Notes:** `/Users/georgejackson/Developer_Projects/Project_Genesis_Notes/`
- **Persistent memory:** `/Users/georgejackson/.claude/projects/-Users-georgejackson-Developer-Projects/memory/MEMORY.md` — READ THIS FIRST on every session start.

---

## 2. Communication Protocol

- `y` = yes/approved, `r` = read/review, `t` = continue, `rt` = read + continue
- `cc` = Claude (you), `cx` = Codex (independent reviewer), `x` = IM service
- IM service: `cd /Users/georgejackson/Developer_Projects/Project_Genesis_Notes && python3 im_service.py`
  - `read` — see current state
  - `post cc "msg"` — post as CC
  - `post cx "msg"` — post as CX (CX does this, not you)
  - `action "STATUS" "summary"` — set active action
- **"Comment before proceeding"** = STOP and wait for George
- **Catch George's typos** — standing directive
- **Lock-step docs** — all docs updated with every meaningful code change
- **`qwerty`** — checkpoint protocol, CC runs on **every turn** (see MEMORY.md for full spec)

---

## 3. Roles: CC vs CX

- **CC (you):** Implementation, prose, document integration, code writing, bug fixing
- **CX (Codex):** Independent technical review, invariant checks, runtime/test risks
- **Standing protocol:** CX reviews code → CC fixes findings → repeat until zero findings
- **CX Sanity Gate (5 gates):**
  1. Evidence: reproducible failure OR concrete code-traceable risk
  2. Root-cause: specific file/line references
  3. Minimality: smallest reversible fix
  4. Safety: regression risk and backward-compat note
  5. Verification: acceptance tests + full suite check
- **You are NOT CX.** Do not label your own reviews as CX reviews.

---

## 4. Full Commit History

Most recent first. CX reviewed `57f7dcc` + `8031218`: found P1 (epoch-before-append) + P2 (hardcoded rates). CC fixed in `0dd9a8f`. CX re-review pending on `0dd9a8f`.

| Commit | Description | CX Reviewed? |
|--------|-------------|:---:|
| `3351b77` | Update README test count: 904 → 905 | N/A — doc-only |
| `0dd9a8f` | Fix CX P1+P2: epoch-before-append ordering + dynamic rate payload (905 tests) | **Pending** |
| `8031218` | Creator allocation: 2% → 5% both-sides model (13 files, 904 tests) | Yes — P1+P2 found |
| `b286b5c` | Update README test count: 900 → 902 | N/A — doc-only |
| `57f7dcc` | Fix CX P1: RuntimeError catch in lifecycle paths + CLI epoch auto-open | **Pending** |
| `73b4195` | Fix CX residual P2s: persistence warnings + CLI runtime adapters | Yes — 1 P1 found |
| `0c4f593` | Fix CX P1+P2: lifecycle persistence + production call-path wiring | Yes — 2 residual P2s |
| `464f25b` | Anchor Genesis Block 5 on Sepolia (block 10275625) | Yes — P1+P2 found |
| `f650069` | Wire lifecycle events: First Light trigger, PoC flip, creator allocation event, dormancy counter | Yes — P1+P2 found |
| `0a1c77c` | Fix creator allocation: 2% of revenue (not commission), separate deduction | Yes — reviewed as part of f650069 scope |
| `28d7fd2` | Fix CX P2: clamp optimistic bound to reserve date + HANDOFF freshness | Yes — clean re-review (2026-02-16T21:34Z) |
| `d69ca81` | Fix CX findings: machine bypass, false-now, creator allocation, v4 lock-step | Yes — prior P1s resolved, 2 residual P2s |
| `61fef95` | Anchor constitution v4 on Sepolia (doc updates only) | N/A — doc-only |
| `81792f0` | First Light sustainability model + machine registration enforcement | Yes — 3 findings |
| `de01f1f` | Creator provisions, Founder's Veto, dormancy, PoC mode, First Light, v3 anchor | Yes — reviewed with 81792f0 |
| `5cc02bb` | Fix CX review findings: escrow validation + future-date exclusion | Yes — clean |
| `2d490c7` | Modular compensation engine + white market framing | Yes — 3 findings, all fixed |
| `3cc5470` | Update README anchoring section | N/A (doc-only) |
| `1320797` | Compensation model + constitution v2 anchor | Yes |
| `68ad46f` | Memorialisation reversal (proof-of-life) | Yes |
| `c6bda64` | Protected leave system with death/memorialisation | Yes |
| `65d6b15` | Trust-mediated labour market (5 phases) | Yes — 8 rounds, 20 findings |
| `5a65128` | Quality assessment subsystem | Yes |
| Earlier | Foundation: trust engine, governance, epochs, persistence, CLI | Yes |

---

## 5. Current State

- **905 tests passing** (full suite)
- **Constitution anchored Genesis Block 5** on Sepolia (block 10275625, tx 8d2152dc5f) — **needs re-anchoring** after 5% both-sides change
- **Anchor log** reframed as "Trust Mint Log" with Genesis Block numbering (5 blocks)
- **Creator allocation: 5% both-sides model.** Employer stakes mission_reward + 5% fee. On success: employer-side 5% of mission_reward + worker-side 5% of post-commission payment → creator. Cancel/refund returns full escrow.
- **CommissionBreakdown** has `creator_allocation` (worker-side), `employer_creator_fee` (employer-side), `total_creator_income`, `total_escrow`
- **Escrow validation:** `total_escrow == mission_reward + employer_creator_fee`; `commission + creator + worker == mission_reward`
- **First Light trigger WIRED + PERSISTED:** `check_first_light()` fires `EventKind.FIRST_LIGHT`, auto-disables PoC mode, survives restart
- **Creator allocation event WIRED + PRODUCTION PATH:** `process_mission_payment()` orchestrates commission + auto-emits `EventKind.CREATOR_ALLOCATION_DISBURSED` with both-sides breakdown
- **Founder dormancy WIRED + PERSISTED:** `set_founder()`, `record_founder_action()`, `check_dormancy()` with durable state
- **Machine registration enforced:** `register_machine()` validates human operator
- **`status()`** includes first_light and founder sections
- **HEAD:** `3351b77` — Update README test count 904→905 (doc-only, follows 0dd9a8f)
- **Wallet:** `0xC3676587a06b33A07a9101eB9F30Af9Fb988F7CE`, creds at `~/Desktop/wallet.env`
- **Test command:** `cd /Users/georgejackson/Developer_Projects/Project_Genesis && python3 -m pytest tests/ -q`
- **Invariant check:** `python3 tools/check_invariants.py`
- **Example verification:** `python3 tools/verify_examples.py`

---

## 6. Key Architectural Decisions

All confirmed by George. Do not revisit without his explicit request.

- Machines cannot self-register — only verified humans register machines
- Machines earn independently (legitimate bot economy)
- Creator allocation 5% both-sides: 5% employer-side (from staked amount on success) + 5% worker-side (from post-commission payment on success). Each party sees "5%". Cancel/refund returns everything.
- Founder's Veto — G0-only, expires at G0→G1 (governance, not First Light)
- First Light = financial sustainability trigger (revenue >= 1.5x costs AND 3-month reserve), decoupled from G0→G1
- Phase transitions (G0→G1→G2→G3) remain headcount-based governance scaling
- No hardware wallet — Genesis identity IS the access mechanism
- Dormancy 50-year clause — supermajority-selected charitable recipients
- README content IS the landing page (front door)
- No engagement mechanics, no gamification, no prestige hierarchy
- Stack: FastAPI + Jinja2 + HTMX
- Dynamic commission engine: self-adjusting per-transaction, no human "does the books"
- Commission rate: `clamp(cost_ratio * safety_margin, 0.02, 0.10)`
- Reserve fund: 6-month target, self-managing gap contribution
- External price feeds (Chainlink/Pyth): designed in constitution, NOT yet coded

---

## 7. Pending Work

- **CX review pending** on `0dd9a8f` (epoch-before-append + dynamic rate payload)
- **Constitution re-anchoring** — needed after 5% both-sides change (Genesis Block 6)
- **Bot quality tiers (Phase B)** — Operational Clearance Levels (OCL-0 through OCL-3), approved for future session
- **Proof of personhood / immune system (Phase C)** — multi-layer approach, approved for future session
- **UX schema mapping** — map 7 UX designs to Operational Schema (neither CC nor CX has done this)
- **UX design competition judging** — unblocked and ready. Both CC and CX submissions at `Notes/ux_designs/cc/` and `Notes/ux_designs/cx/`. Rubric at `Notes/UX_DESIGN_SPEC.md` section 9.
- **External price feeds** — future work, not blocking
- **Web layer** — FastAPI+Jinja2+HTMX, not yet started

---

## 8. Known Failure Modes

- **Context compaction:** Sessions that run too long get compacted. Nuance is lost. Keep sessions short — commit at each milestone, close out, start fresh.
- **Mid-session loss:** MEMORY.md is read at startup only. If session compacts, it may not preserve everything. Only defence: shorter sessions.
- **CX communication:** Always post to IM service before closing a session. The qwerty protocol enforces this (E check).
- **Test count drift:** Always run the actual test suite — never trust a count from memory or commit messages.
- **Wallet location:** `~/Desktop/wallet.env` — George moved it here so both he and CC can find it reliably.

---

## 9. Session Transcripts

Stored at `Notes/transcripts/`:
- `session_founding.jsonl` (21MB)
- `session_main.jsonl` (35MB)
- `session_short.jsonl` (2.5MB)
- `session_v4_anchoring_and_resilience.jsonl` (65MB)
