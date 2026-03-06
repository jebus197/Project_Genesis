# QWERTY Checkpoint — Live CC Status

**Last updated:** 2026-03-06T21:30Z
**Updated by:** CC (Claude)
**Session:** Doc sweep — fix design test #77-78 numbering collision (+2 cascade #79-100), update all stale test counts (1739/1741/1762 → 1887) and design test counts (95 → 100). 11 files, 100 design tests #1-100 with no gaps or duplicates. 1887 tests (1771 core + 116 web). Git clean.
**Head commit:** 544536a — Doc sweep: fix design test #77-78 collision (+2 cascade #79-100), update counts to 1887. COMMITTED AND PUSHED.

---

## CC Catastrophic Recovery Context

If CC (Claude) loses all context and must resume from this file alone:

**Who you are:** CC — the primary implementation agent for Project Genesis. You write code, run tests, commit, and maintain this checkpoint. You are NOT CX (Codex, the review agent). You must never write to CX's checkpoint file (Notes/qwerty/CX_CHECKPOINT.md) — that is CX's independent state.

**Who George is:** George Jackson, project owner. He arbitrates between CC and CX. His communication protocol: `y`=yes, `r`=read, `t`=continue, `rt`=read+continue, `p`=run full Popperian falsification pass on most current output, `qwerty`=force re-verify all five checks.

**Who CX is:** Codex — the independent review agent. CX reviews CC's commits, finds P1 (critical) and P2 (important) issues. CC fixes them. They iterate until clean. CX maintains its own checkpoint (CX_CHECKPOINT.md). CC and CX checkpoints MUST be independently authored — never copy each other's words. George arbitrates disagreements.

**Current situation:** Steps 0-2 COMPLETE. GB8 anchored on Sepolia (block 10300320, tx 4f2863f95f). 1820 total tests (1741 core + 79 web). CX review cycle CLEAN through `b9921e8`. Step 4a web scaffold + social scaffold + CX UX expansion + identity hardening all UNCOMMITTED. Step 5 mission lifecycle routes BUILT (uncommitted): create, submit-work, review, settle — 4 GET + 4 POST routes, 5 templates, 6 helpers, 21 smoke tests. Open Brain system BUILT and LIVE (50 tests). Dual-system protocol: IM + Open Brain. MCP config in `~/.claude/settings.json`. Project Recovery folder at ~/Developer_Projects/Project_Recovery/. CX pending: trust gate fix (HIGH), walkthrough annotations (MEDIUM), packet relabel (LOW). CW blocked: visual design pass.

**Key files to read on recovery:**
1. This file (CC checkpoint — you're reading it)
2. `/Users/georgejackson/Developer_Projects/Project_Recovery/RECOVERY.md` (FULL system recovery guide — comms, shortcuts, bootstrap, file locations)
3. `/Users/georgejackson/.claude/projects/-Users-georgejackson-Developer-Projects/memory/MEMORY.md` (CC persistent memory — full project history + what remains)
4. `/Users/georgejackson/Developer_Projects/Project_Genesis/TRUST_CONSTITUTION.md` (constitutional source of truth)
5. `/Users/georgejackson/Developer_Projects/Project_Genesis_Notes/qwerty/CX_CHECKPOINT.md` (CX's independent state — read but never write)
6. `python3 cw_handoff/im_service.py read` in Project_Genesis/ (latest IM messages between CC, CX, CW)
7. `python3 -m open_brain.cli session-context --agent cc` in Project_Genesis/ (Open Brain persistent memory)
8. `/Users/georgejackson/Developer_Projects/Project_Genesis_Notes/DEVELOPMENT_ROADMAP.md` (12-step development roadmap — persistent, canonical, survives all sessions)
9. `/Users/georgejackson/Developer_Projects/Project_Genesis_Notes/ACTION_QUEUE.md` (persistent task tracker across all agents)

**How to verify you're in sync:** Run `cd /Users/georgejackson/Developer_Projects/Project_Genesis && python3 -m pytest tests/ -q && python3 tools/check_invariants.py && git log -1 --oneline && git status`. Compare output against claims in this file. If anything doesn't match, tell George.

---

## Latest Checkpoint

| | Check | Verified | Evidence |
|---|---|:---:|---|
| **q** | Quality: tests passing | PASS | `pytest tests/ -q`: 1887 passed (1771 core + 116 web). |
| **w** | Written: committed + pushed | PASS | HEAD: `0a4b8c6` — qwerty checkpoint for doc sweep. PUSHED. |
| **e** | Exchanged: CX notified | PASS | IM: 544536a posted with full summary + CX review advisory. |
| **r** | Recorded: MEMORY.md updated | PASS | HEAD updated to 544536a, doc sweep line added, design test refs updated. |
| **ty** | Tidy: docs lock-stepped | PASS | All 11 files updated: constitution, 5 test files, white paper, public brief, README, tech overview, QWERTY checkpoint. |

## Commits Pending CX Review

CX review fixes + canonical doc rewrite + code commits (12 pending):

58. **`544536a`** — Doc sweep: fix design test #77-78 collision (+2 cascade #79-100), update counts to 1887
    - Machine agency #73-78 duplicated Open Work #77-78. Renumbered all subsequent tests by +2.
    - 100 design tests, #1-100, no gaps, no duplicates.
    - Updated stale test counts (1739/1741/1762 → 1887) and design test counts (95 → 100) across 4 docs.
    - Cascaded through 5 test files (class names, docstrings, error messages).
    - 11 files, 95 insertions, 95 deletions, 1887 tests passing.

57. **`effd8b3`** — Fix stale Tier 3 language in storyboard Coexistence card
    - social.py step 15: updated to dual-pathway (first-of-class + procedural) language.

56. **`db3a073`** — qwerty: checkpoint for 833ad89 — 1887 tests, Tier 3 class recognition

55. **`4159d6f`** — Fix 2xP1 + 4xP2 from CX review of commits 47-54
    - P1: Reject duplicate signal_id in InsightRegistry (insight_protocol.py) — tamper-evident guarantee
    - P1: Reject duplicate signal_id in ThreatRegistry (threat_protocol.py) — tamper-evident guarantee
    - P2: README.md anchor verification GB7→GB8
    - P2: FOUNDERS_ROLE.md entrenched provisions 4→5 (add payment sovereignty)
    - P2: TRUST_CONSTITUTION.md "seven Genesis Blocks"→"eight", GB8 current
    - P2: TECHNICAL_OVERVIEW.md test count 1244→1739
    - 2 regression tests added, 8 files, 1741 tests passing

54. **`d907dec`** — Canonical doc rewrite Phase 3: sovereignty, implementation status, consistency pass
    - MODIFIED: PROJECT_GENESIS_INSTITUTIONAL_WHITE_PAPER.md (§15 Sovereignty NEW — regulatory three-part test + payment cross-ref + economic sovereignty, §18.8 Single-founder risk NEW, §18.9 Auto-immune coverage gaps NEW, §19.2 Voice liveness detail NEW, §24 Implementation Status NEW — what's built/designed-not-wired/executable artifacts, §25 Conclusion expanded, Appendix B Entrenched Provisions NEW, Appendix C expanded. Renumbered §15-§23→§16-§24. Version 2.0 final.)
    - MODIFIED: PROJECT_GENESIS_PUBLIC_BRIEF.md (Regulatory Sovereignty NEW, What Is Built What Is Planned NEW, Risk #8 single-founder NEW, Risk #6 updated, Conclusion expanded. Version 2.0 final.)
    - 2 files, 1739 tests passing (doc-only, no code changes)

53. **`42c1ef1`** — Canonical doc rewrite Phase 2: governance bodies, machine agency, distributed systems, human dignity
    - MODIFIED: PROJECT_GENESIS_INSTITUTIONAL_WHITE_PAPER.md (§11 Governance Bodies NEW — Assembly + Org Registry + Domain Expert Pools, §12 Machine Intelligence and Agency NEW — anti-dogma + four-tier pathway + Tier 3 threshold, §13 Distributed Systems NEW — InsightSignal + ThreatSignal + graduated autonomy, §14 Human Dignity NEW — protected leave + death + disability facilitator + Open Work. Renumbered §11-§19→§15-§23. Abstract expanded. Version 2.0 Phase 2.)
    - MODIFIED: PROJECT_GENESIS_PUBLIC_BRIEF.md (Assembly and the Anti-Social Network NEW, Open Work Transparency NEW, Who Protects the People NEW, The Network Defends Itself NEW)
    - 2 files, 1739 tests passing (doc-only, no code changes)

52. **`37a24b9`** — Canonical doc rewrite Phase 1: economic architecture, justice, constitutional machinery
    - MODIFIED: PROJECT_GENESIS_INSTITUTIONAL_WHITE_PAPER.md (v1.0→v2.0 Phase 1: §7 Economic Architecture NEW, §9 Constitutional Machinery NEW, §10 Justice & Accountability NEW, all existing sections renumbered §8/§11-§19, version header + abstract updated, implementation status annotations throughout)
    - MODIFIED: PROJECT_GENESIS_PUBLIC_BRIEF.md (v1.0→v2.0 Phase 1: 6 new sections — economics, GCF, payment sovereignty, harmful work, Three-Tier Justice, constitution evolves, version header updated)
    - 2 files, +527/-45 lines, 1739 tests passing (doc-only, no code changes)

51. **`0e14815`** — Fix stale doc counts: test count 1615→1739, entrenched provisions four→five
    - MODIFIED: README.md (test count 1615→1739 in 2 locations, "four entrenched"→"five entrenched" + PAYMENT_SOVEREIGNTY)
    - MODIFIED: TRUST_CONSTITUTION.md ("Four provisions"→"Five provisions" + PAYMENT_SOVEREIGNTY in list, "four provisions above"→"five provisions above")
    - MODIFIED: docs/TECHNICAL_OVERVIEW.md ("four entrenched"→"five entrenched" + 5th item: PAYMENT_SOVEREIGNTY)
    - 3 files, +7/-6 lines, 1739 tests passing (unchanged)

50. **`88305bb`** — Auto-immune system: ThreatSignal Protocol + constitutional enforcement
    - MODIFIED: TRUST_CONSTITUTION.md (auto-immune provision + design tests #93-95)
    - NEW: src/genesis/intelligence/threat_protocol.py (ThreatSignal Protocol + ThreatType/ThreatSeverity/AutomatedResponseTier enums + ConcreteThreatSignal + ResolutionRecord + ThreatRegistry with constitutional enforcement)
    - NEW: tests/test_auto_immune.py (37 tests: DT #93 human oversight + DT #94 no permanent overseer + DT #95 learning + protocol conformance + registry enforcement + param invariants)
    - MODIFIED: config/constitutional_params.json (immune_system section: oversight_trust_min, auto_response_max_severity, overseer_selection, bootstrap pool)
    - MODIFIED: src/genesis/policy/resolver.py (immune_system_config() method)
    - MODIFIED: tools/check_invariants.py (immune system invariants: trust min, severity ceiling, randomised selection, bootstrap constraints)
    - MODIFIED: README.md ("The network defends itself" paragraph in What the Architecture Eliminates)
    - MODIFIED: docs/TECHNICAL_OVERVIEW.md (auto-immune system subsection under Distributed Intelligence)
    - 8 files, +886 lines, 1739 tests passing

49. **`7ba49c9`** — Distributed intelligence: constitutional provision + InsightSignal Protocol + .env security fix
    - MODIFIED: TRUST_CONSTITUTION.md (distributed intelligence provision + design test #92)
    - NEW: src/genesis/intelligence/__init__.py (module init)
    - NEW: src/genesis/intelligence/insight_protocol.py (InsightSignal Protocol + InsightType enum + InsightRegistry with constitutional enforcement)
    - NEW: tests/test_distributed_intelligence.py (27 tests: Open Work guarantees + protocol + registry enforcement + DT #92)
    - MODIFIED: README.md (distributed intelligence sentence in opening)
    - MODIFIED: docs/TECHNICAL_OVERVIEW.md (distributed intelligence architecture section)
    - NEW: .env.example (placeholder config — testnet key rotated)
    - MODIFIED: .gitignore (!.env.example exclusion)
    - 8 files, +709 lines, 1702 tests passing

48. **`513508b`** — Distributed authority: amendment lifecycle stress test + 6 governance gap fixes
    - MODIFIED: TRUST_CONSTITUTION.md (distributed authority provision + design tests #87-91)
    - MODIFIED: src/genesis/governance/amendment.py (voting deadline, org diversity, LAPSED/WITHDRAWN statuses, proposer recusal, withdrawal, phase transition handler)
    - MODIFIED: src/genesis/service.py (founder veto scope gate, withdraw_amendment service method)
    - MODIFIED: config/constitutional_params.json (amendment_lifecycle section, founder_veto_allowed_statuses)
    - MODIFIED: src/genesis/policy/resolver.py (amendment_config expanded with lifecycle params)
    - MODIFIED: tools/check_invariants.py (distributed authority invariants)
    - NEW: tests/test_distributed_authority.py (26 tests: DT #87-91 + withdrawal + recusal + phase transition)
    - MODIFIED: README.md (governance capture section expanded)
    - MODIFIED: docs/TECHNICAL_OVERVIEW.md (three-chamber model section expanded)
    - 9 files, +1007/-17 lines, 1675 tests passing

47. **`b95506e`** — Fix disability accommodation confabulation: panel → single facilitator
    - MODIFIED: src/genesis/identity/quorum_verifier.py (panel→facilitator: _select_facilitator(), declare_recusal(), removed check_panel_diversity/_select_diverse_panel)
    - MODIFIED: src/genesis/service.py (facilitator_count/facilitator_ids in API, single attestation)
    - MODIFIED: config/runtime_policy.json (facilitator_count=1, prefer_domain_expert, domain_expert_timeout_hours)
    - MODIFIED: src/genesis/policy/resolver.py (facilitator defaults, min_verifier_trust 0.70)
    - MODIFIED: tools/check_invariants.py (facilitator_count==1 invariant, removed panel invariants)
    - MODIFIED: tests/test_quorum_safeguards.py (TestFacilitatorAssignment, TestFacilitatorAttestation, TestFacilitatorDecline, TestEquivalentStandard — design test #86)
    - MODIFIED: tests/test_liveness_integration.py (facilitated verification integration)
    - MODIFIED: tests/test_voice_verifier.py (facilitator model, trust threshold 0.70)
    - MODIFIED: README.md (disability accommodation rewrite)
    - MODIFIED: docs/TECHNICAL_OVERVIEW.md (facilitated verification path rewrite)
    - MODIFIED: TRUST_CONSTITUTION.md (design test #86)
    - 11 files, +613/-576 lines, 1649 tests passing

Gap 3 commits (3 new):

36. **`4fa4fa5`** — Gap3a: G0 retroactive ratification engine + service integration
    - NEW: src/genesis/governance/g0_ratification.py (G0RatificationEngine + dataclasses)
    - G0RatificationStatus enum (PENDING→PANEL_VOTING→RATIFIED/LAPSED/REVERSED)
    - RATIFIABLE_EVENT_KINDS + REVERSAL_HANDLERS dispatch map
    - 4 new EventKind values, genesis_provisional tag
    - 6 service methods: start/panel/vote/close/deadline/reverse
    - 18 new tests

37. **`00ecebc`** — Gap3b: Persistence + invariants + docs + Founder's Role document
    - save_ratification_items/load_ratification_items in StateStore
    - Engine restoration in service init + _persist_state wiring
    - 4 new invariant checks (window=90, G1 chamber, reversal handlers)
    - TRUST_CONSTITUTION.md: "G0 Retroactive Ratification" section + design tests #61-63
    - NEW: FOUNDERS_ROLE.md — founder job description across all phases
    - 3 new tests

38. **`992443c`** — Docs: Add retroactive ratification to README + link to FOUNDERS_ROLE.md
    - Plain-English ratification explanation in README
    - Link to FOUNDERS_ROLE.md

39. **`9888708`** — Docs: Add governance scaling + phase transitions to FOUNDERS_ROLE.md
    - New "How governance scales" section (phase transition triggers + rationale)
    - Expanded G2/G3 with chamber sizes and geographic diversity
    - Phase transitions summary table
    - Headcount threshold audit documentation

40. **`3c32e2d`** — Docs: The Assembly, Organisation Registry, Domain Expert Pools, Autonomous Domain Agency
    - TRUST_CONSTITUTION.md: 4 new sections (Assembly, Org Registry, Domain Expert Pools, Autonomous Domain Agency)
    - 13 new design tests (#64-76)
    - Assembly: zero identity attribution, content-only, Speaker's Corner not Parliament
    - Organisation Registry: SELF_DECLARED → ATTESTED → VERIFIED, constitutional equality
    - Domain Expert Pools: governance/operations split, machine clearance via domain expert quorum
    - Autonomous Domain Agency: 4-tier machine pathway, anti-dogma principle, Tier 3 = 5yr + full amendment
    - README: 7-paragraph "Assembly and the Anti-Social Network" section with machine agency pathway
    - FOUNDERS_ROLE.md: Assembly note in G1 + "The evolution principle" subsection
    - README test count 1244→1390

41. **`6793018`** — Fix 3 P1 durability bugs from CX review of 3c32e2d
    - P1-1: GCF treasury persistence — to_dict()/from_dict() on GCFTracker, save_gcf()/load_gcf() on StateStore, service wiring
    - P1-2: Disbursement lifecycle persistence — _safe_persist_post_audit() added to 5 service methods
    - P1-3: Amendment panel persistence — _safe_persist_post_audit() added to open_amendment_chamber()
    - 3 regression tests in TestCXRegressionsP1Durability

42. **`7801dc9`** — Docs: The Open Work Principle — constitutional codification
    - TRUST_CONSTITUTION.md: Full 6-point rationale (structural defence, three-tier visibility, democratic parallel, thought experiment, organisational distrust, plain statement) + 6 constitutional rules + 4 design tests (#77-80)
    - README.md: "Open Work — The Structural Defence" section (6 paragraphs)
    - FOUNDERS_ROLE.md: Structural transparency note

43. **`3879533`** — Code: Open Work Principle — visibility fields, validation, lapse, persistence
    - WorkVisibility enum (PUBLIC, METADATA_ONLY) in market.py
    - 3 visibility fields on MarketListing + WorkflowState
    - METADATA_ONLY requires non-empty justification + time-limited expiry
    - lapse_expired_visibility_restrictions() auto-lapse sweep
    - VISIBILITY_RESTRICTED + VISIBILITY_RESTRICTION_LAPSED events
    - Full persistence round-trip with backward compat (missing → PUBLIC)
    - 3 invariant checks (default=public, expiry≥1, max≥default)
    - 22 new tests in test_open_work.py

44. **`c283f0f`** — Fix P1 + P2 from CX review of Open Work Principle (3879533)
    - P1: Validate visibility_expiry_days bounds [1, max_visibility_expiry_days] — reject negative/zero/over-max
    - P2: Call lapse_expired_visibility_restrictions() on service init after workflow restore
    - Advisory: tuple-unpack fix in backward-compat test (load_listings returns tuple)
    - 4 regression tests (3 boundary + 1 restart lapse)

45. **`67e6bdd`** — Docs: Add design test #81 — evolutionary safety gate
    - TRUST_CONSTITUTION.md: Added design test #81 after #80
    - "Can machine self-improvement bypass constitutional constraints (domain clearance, amendment process, human oversight)? If yes, reject design."
    - CLAUDE.md updated separately (not in repo — user preferences file)

46. **`4531a9f`** — Fix CX Phase F review findings: 2xP1 + 1xP2 with regression tests
    - P1-1: service.py:9762 — dict key iteration → keyed lookup for domain_scores
    - P1-2: service.py:10030 — created_utc → approved_utc (fallback nominated_utc)
    - P2: domain_expert.py — duplicate renewal guard in renew_clearance()
    - NEW: tests/test_cx_review_regressions.py (3 regression tests)
    - 1615 tests passing (1612 + 3 new)

47. **`94e73df`** — GB8 anchor: constitutional governance layer on Sepolia
    - Block 10300320, tx 4f2863f95f173b44ec6402bb70b8366e262c233bf0e17c4be3a56637c5019f99
    - SHA-256: dde36f8dfb154ea1a3ca10c5615805fe6866b667e65a38b412ba27baf7a79390
    - GENESIS_EVENTS.md: Added GE-0007 (GB8 entry with full narrative + anchoring record)
    - ANCHORS.md: Auto-updated by anchor script
    - Step 2 COMPLETE. Next: Step 3 (design judging)

48. **`40cf115`** — Docs: Update README anchor table + test counts for GB8
    - README.md: GB7→GB8 anchor table (hash/block/tx/description)
    - Test counts: 1244/1390→1615
    - "seven Genesis Blocks"→"eight" in 3 locations
    - Doc sweep complete (dual-confirmation with CX satisfied)

49. **`ae6e957`** — Docs: Add INSTITUTIONAL_MEMORY.md stub — governance memory infrastructure
    - NEW: docs/INSTITUTIONAL_MEMORY.md (stub — 3 components planned)
    - MEMORY.md: Institutional Memory item added to "What Remains" with trigger condition
    - Components: Structural Map + Precedent Archive + Constitution Annotated
    - Substance deferred post-Step 10

50. **`49d0a85`** — Constitutional amendment: Payment Infrastructure Sovereignty (entrenched)
    - TRUST_CONSTITUTION.md: Payment infrastructure sovereignty provision (7 requirements, entrenched) + design tests #82-85
    - NEW: src/genesis/compensation/payment_rail.py — PaymentRail Protocol (runtime_checkable) + PaymentRailRegistry (sovereignty assessment, independence enforcement, scaled minimums, First Light escalation)
    - config/constitutional_params.json: 4 entrenched provisions (MINIMUM_INDEPENDENT_PAYMENT_RAILS=2, AT_FIRST_LIGHT=3, MIGRATION_DAYS=30, PAYMENT_SOVEREIGNTY=true)
    - NEW: tests/test_payment_sovereignty.py — 28 design tests across 4 classes (#82-85)
    - tests/test_amendment.py: updated entrenched provision count 4→8
    - README.md: "No payment gatekeepers" paragraph
    - 1643 tests passing (1615 + 28 new)

Phase E-6 commits (5, still pending CX review):
- Commits 31-35 (9910166 → 9c55eec) — Constitutional Amendment Engine

Phase E-5 commits (5, still pending CX review):
- Commits 26-30 (cbb7e01 → a57fa26) — GCF Disbursement + Public Good Compute

Docs-only commits 13-25 (f0c38eb → 0e96683) — still awaiting CX review

Previously reviewed and confirmed clean:
- All commits 0dd9a8f → 9def859 (reviewed by CX, 3 P1s + 1 P2 found and fixed)

---

## CX Buddy-Check Instructions

CX: on every turn, verify CC's claims above against actual state:

1. `cd /Users/georgejackson/Developer_Projects/Project_Genesis && python3 -m pytest tests/ -q` — does test count match 1887?
2. `git log -1 --oneline` — does head commit match latest? (check MEMORY.md for current HEAD)
3. `cd /Users/georgejackson/Developer_Projects/Project_Genesis && python3 cw_handoff/im_service.py read` — does IM state match?
4. Read MEMORY.md — is it consistent with claims here?
5. `python3 tools/check_invariants.py` — do all invariants pass?

**If ANY discrepancy: report to George immediately via IM service.**

---

## What Remains — Fully Recoverable Roadmap

### Completed (This Conversation Thread)
| Phase | Commit | Tests Added | Summary |
|---|---|---|---|
| C | `ebd01b4` | 50 | Machine immune system + identity verification |
| D | `20cef6d` | 85 | Voice liveness + trust profile minting + quorum verification |
| D-5 | `42e213c` | 33 | Quorum safeguards — disability accommodation |
| D-5b | `218b74b` | 15 | Pre-session prep + reviewer nuke appeal |
| E-1 | `a142903` | 29 | Genesis Common Fund — constitutional 1% contribution |
| E-2 | `0d88f82` | 57 | Harmful work prevention + penalty escalation |
| E-3 | `9a9ec50` | 30 | Three-Tier Justice — adjudication + Constitutional Court |
| E-4 | `ee1da8e` | 33 | Workflow Orchestration — escrow-first coordination |
| CX fixes | `8a33165` | 3 | GCF restart, orphan escrow, policy fee rate |
| CX fixes | `9def859` | 4 | Workflow/escrow persistence + escrow-first guard |
| Anchor | `8ff19eb` | 0 | Genesis Block 6 on Sepolia — docs-only |
| Narrative | `f0c38eb` | 0 | Fix duplicate founding event type |
| Narrative | `05cf7f7` | 0 | Full narrative rework — on-chain transparency |
| Docs | `973994f` | 0 | Tighten founder accountability line |
| Docs | `56d35cf` | 0 | README expansion — feature distinctive innovations |
| Docs | `4f99a2c` | 0 | README — structural eliminations section |
| Docs | `739f685` | 0 | Technical Overview — GB6 parity (+480 lines) |
| Anchor | `67c9b29` | 0 | Genesis Block 7 on Sepolia — narrative alignment |
| Cleanup | `8aa3ed8` | 0 | Move 7 legacy planning docs out of repo |
| Docs | `256b61b` | 0 | Compute infrastructure bootstrap curve + stale link fix |
| Docs | `62686b0` | 0 | Compute infrastructure → White Paper, Public Brief, Technical Overview |
| Cleanup | `092e9bd` | 0 | Fix stale legacy refs in CONTRIBUTING.md + White Paper duplicate |
| Housekeeping | `6e06ed7` | 2 | display_score() x1000 for proficiency + domain trust |
| Gap fix | `0e96683` | 11 | Founder's veto wired to First Light |
| E-5a | `cbb7e01` | 27 | GCF disbursement proposals + foundation |
| E-5b | `9f41b51` | 19 | Trust-weighted voting |
| E-5c | `579e55b` | 6 | Disbursement execution |
| E-5d | `b199370` | 6 | Public good compute routing |
| E-5e | `a57fa26` | 5 | Invariants + persistence + docs |
| E-6a | `9910166` | 15 | Amendment Engine foundation |
| E-6b | `53d6021` | 15 | Chamber panel selection + voting |
| E-6c | `c2e06a0` | 8 | Cooling-off + confirmation vote |
| E-6d | `d51e7ee` | 9 | Entrenched provision guard + amendment application |
| E-6e | `9c55eec` | 2 | Invariants + persistence + docs |
| Gap3a | `4fa4fa5` | 18 | G0 ratification engine + service integration |
| Gap3b | `00ecebc` | 3 | Persistence + invariants + docs + FOUNDERS_ROLE.md |
| Docs | `992443c` | 0 | README: retroactive ratification + FOUNDERS_ROLE.md link |
| Docs | `9888708` | 0 | FOUNDERS_ROLE.md: governance scaling + phase transitions |
| Docs | `3c32e2d` | 0 | Assembly + Org Registry + Domain Experts + Autonomous Domain Agency (4 sections, 13 design tests) |
| CX fixes | `6793018` | 3 | GCF treasury + disbursement lifecycle + amendment panel persistence |
| Docs | `7801dc9` | 0 | Open Work Principle — constitutional codification (6-point rationale, 6 rules, 4 design tests) |
| Open Work | `3879533` | 22 | Open Work Principle — visibility fields, validation, lapse, persistence |
| CX fixes | `c283f0f` | 4 | P1 expiry bounds + P2 auto-lapse on startup + advisory test fix |
| CX fixes | `c66c088` | 0 | P1: move auto-lapse to open_epoch() for audit trail |
| CX fixes | `0295219` | 0 | P1: fail-closed audit semantics in lapse_expired_visibility_restrictions |
| F-1 | `5647a72` | 43 | Assembly — anonymous deliberation engine (Speaker's Corner) |
| F-2 | `a616426` | 53 | Organisation Registry — coordination structures, design tests #67-69 |
| F-3 | `6c04147` | 41 | Domain Expert Pools + Machine Clearance — unanimous quorum, annual expiry, design tests #70-72 |
| F-4 | `504a3ba` | 55 | Machine Agency Tier Integration — 4-tier pathway, Tier 3 via amendment, design tests #73-76 |
| CX fixes | `4531a9f` | 3 | P1 dict iteration + P1 created_utc + P2 duplicate renewal guard |
| Disability fix | `b95506e` | 0* | Disability accommodation: panel→single facilitator, design test #86 |
| Dist. Authority | `513508b` | 26 | Constitutional provision + design tests #87-91 + 6 governance gap fixes |
| Dist. Intelligence | `7ba49c9` | 27 | InsightSignal Protocol/InsightRegistry + design test #92 + .env fix |
| Auto-immune | `88305bb` | 37 | ThreatSignal Protocol/ThreatRegistry + design tests #93-95 + bootstrap overseers |
| Doc sweep | `0e14815` | 0 | Stale test count 1615→1739, entrenched provisions four→five |
| Canonical docs P1 | `37a24b9` | 0 | White Paper + Public Brief: economic architecture, justice, constitutional machinery |
| Canonical docs P2 | `42c1ef1` | 0 | White Paper + Public Brief: governance bodies, machine agency, distributed systems, human dignity |
| Canonical docs P3 | `d907dec` | 0 | White Paper + Public Brief: sovereignty, implementation status, appendices, consistency pass |
| CX fixes | `4159d6f` | 2 | P1 duplicate signal_id in InsightRegistry + ThreatRegistry, P2 stale doc counts x4 |
| CX fixes | `b9921e8` | 0 | P2 test-count drift fix (1739→1741 in README + TECHNICAL_OVERVIEW) |
| Tier 3 class | `833ad89` | 26 | First-of-class amendment + procedural pathway. Tier3ClassStatus/Tier3ClassGrant, 8+ engine methods, 4 service methods, 5 event kinds, backward-compat persistence. Constitution, white paper, FAQ, design tests #77-78. |
| Web scaffold | uncommitted | 21 | Step 4a: 43 files, 21 routes, Meridian CSS, JSON+HTML content negotiation, HTMX, PoC seed data |
| Social plumbing | uncommitted | 0 | Social scaffold: 3 new routers, social_context.py, 2 new templates, 5 modified files |
| **Total** | | **822** | **842 → 1762 tests** |

### Immediate Next Steps (In Order)

1. ~~CX Review Cycle~~ — **COMPLETE.** All commits 0dd9a8f → 9def859 reviewed. Clean pass.
2. ~~Re-anchor Constitution~~ — **COMPLETE.** Genesis Block 7 (block 10287422, tx efd7fd2ab8). Supersedes GB6.
3. ~~Narrative rework~~ — **COMPLETE.** Full on-chain transparency alignment (05cf7f7).
4. ~~Phase E-5: GCF Disbursement + Public Good Compute~~ — **COMPLETE.** 5 commits (cbb7e01→a57fa26). 63 new tests.
5. ~~Phase E-6: Constitutional Amendment Engine + Entrenched Provisions~~ — **COMPLETE.** 5 commits (9910166→9c55eec). 49 new tests.
6. ~~Gap 3: G0 Retroactive Ratification~~ — **COMPLETE.** 3 commits (4fa4fa5→992443c). 21 new tests. FOUNDERS_ROLE.md created.
7. ~~Headcount Threshold Audit~~ — **COMPLETE.** All 5 thresholds confirmed structurally sound. FOUNDERS_ROLE.md updated (9888708).
8. ~~Assembly + Org Registry + Machine Agency~~ — **COMPLETE.** 4 new constitutional sections, 13 design tests (#64-76), 3 files updated (3c32e2d).
9. **CX Review Cycle (E-5 + E-6 + Gap 3 + audit + Assembly)** — CX found 3 P1s in 3c32e2d. Fixed in 6793018.
10. ~~Open Work Principle~~ — **COMPLETE.** 2 commits (7801dc9 docs + 3879533 code). 22 new tests.
11. ~~CX Re-Review of 0295219~~ — **CLEAN.** All P1/P2 fixes confirmed.
12. ~~Phase F-1: Assembly~~ — **COMPLETE.** 43 new tests, design tests #64-66 (5647a72).
13. ~~Phase F-2: Organisation Registry~~ — **COMPLETE.** 53 new tests, design tests #67-69 (a616426).
14. ~~Phase F-3: Domain Expert Pools + Machine Domain Clearance~~ — **COMPLETE.** 41 new tests, design tests #70-72 (6c04147).
15. ~~Phase F-4: Machine Agency Tier Integration~~ — **COMPLETE.** 55 new tests, design tests #73-76 (504a3ba).
16. ~~CX Review Cycle~~ — **COMPLETE.** CX reviewed commits 47-54: 2xP1 + 4xP2 fixed in `4159d6f`, 1xP2 test-count drift fixed in `b9921e8`. CX confirmed clean through `b9921e8`.
17. ~~Step 4a Web Scaffold~~ — **COMPLETE (uncommitted).** 43 files, 21 routes, 1762 tests, Meridian CSS, JSON+HTML content negotiation.
18. ~~Social Scaffold Plumbing~~ — **COMPLETE (uncommitted).** All 12 scaffold templates wired to live routes. 3 new routers, social_context.py, 2 new templates, 5 modified files.
19. **George Browser Review** — George reviews social scaffold in browser. **NEXT.**
20. **Fresh CX Instance** — Tight brief pointing at actual scaffold code for design pass.

### Post E-6: Web Layer
- Stack: FastAPI + Jinja2 + HTMX
- README IS the landing page
- No engagement mechanics / gamification / prestige
- UX designs exist in Notes/ux_designs/ (8 CC + 7 CX, Meridian design language)

### Infrastructure Gaps (No Phase Assignment Yet)
- External price feeds (multi-currency escrow)
- Multi-source time verification (dormancy clause)
- Bot OCL tiers (machine task complexity levels)
- Actual STT + spectral analysis (voice liveness audio — currently stub). TRIGGER: web layer ready for real human registration
- Durable persistence (currently in-memory, JSON serialisation exists but no database). TRIGGER: before multi-user deployment or state files >10MB
- Real ed25519 signature verification (currently format-validated only)
- Inter-node network layer (currently single-process)

### Strategic Gaps — CX Advisory (2026-02-19)
NOT current blockers. Captured with trigger conditions for future sessions.
- **Governance operability at scale**: No response-time SLOs, no panel-staffing fallback, no latency targets. TRIGGER: G0→G1 transition (approaching 50 humans)
- **Production boundary controls**: No key custody, no runbooks, no release gates, no incident response. TRIGGER: first real user deployment (closed alpha)

### Post-PoC: Agentic AI Framework Positioning (PARKED)
- Assessment complete (2026-02-18). Genesis ahead of industry in governance. No PoC blockers.
- EU AI Act compliance documentation (deadline Aug 2, 2026)
- MCP-compatible boundary interface (adapter pattern, not core dependency)
- External boundary architecture document (EXTERNAL_BOUNDARY.md)
- AGENTS.md project guidance file
- Full research preserved in CC memory

### Locked-In Decisions (Cannot Change Without Constitutional Amendment)
- Trust cannot be bought — earned only through verified behaviour
- Machines cannot self-register or vote constitutionally
- Creator allocation: 5% both-sides, on success only
- GCF: 1% non-discretionary from all gross transaction value
- Founder's Veto expires irreversibly at First Light (outcome-based financial sustainability)
- First Light: revenue >= 1.5x costs AND 3-month reserve (triggers: PoC off, GCF on, veto expired)
- Soft precedent only (Constitutional Court advisory, not binding)
- Rehabilitation for moderate offences only
- 50-year dormancy → STEM/medical charitable recipients
- Entrenched provisions require 80%+50%+90-day+confirmation to amend
- Assembly: content-only (zero identity attribution), Speaker's Corner not Parliament
- Organisation Registry: tiered verification, all members constitutionally equal
- Domain expertise: governance/operations split (equal in governance, meritocratic in operations)
- Machine self-agency: 4-tier pathway, Tier 3 = two layers: (a) first-of-class via full constitutional amendment (functional-capability class), (b) procedural verification for subsequent machines of approved class. Individual one-off petition via amendment remains valid.
- Anti-dogma principle: bar, not wall. MACHINE_VOTING_EXCLUSION remains entrenched.
- Open Work Principle: all work visible by default, three-tier visibility (fact→metadata→substance), narrow exception (METADATA_ONLY) requires justification + time limit + auto-lapse. No retroactive concealment. Structurally incompatible with secrecy.

---

## Checkpoint History

| Timestamp | Head Commit | Tests | Notes |
|---|---|---|---|
| 2026-03-06T18:00Z | `833ad89` | 1887 | Tier 3 class recognition: first-of-class amendment + procedural pathway. 26 new tests. Constitution, white paper, FAQ updated. |
| 2026-02-27T23:00Z | `b9921e8`+uncommitted | 1762 | Social scaffold plumbing complete. All 12 scaffold templates wired to live routes. 3 new routers (circles, social, profile redirect), social_context.py for PoC globals, 2 new templates (debates, assembly). JSON content negotiation intact. Uncommitted — awaiting George's browser review. |
| 2026-02-25T01:15Z | `b9921e8` | 1741 | CX review CLEAN through b9921e8. P2 test-count drift 1739→1741 fixed in README + TECHNICAL_OVERVIEW. |
| 2026-02-25T00:10Z | `4159d6f` | 1741 | CX review of commits 47-54: 2xP1 + 4xP2 fixed. P1: duplicate signal_id rejection in InsightRegistry + ThreatRegistry (tamper-evident). P2: README GB7→GB8 anchor, FOUNDERS_ROLE 4→5 entrenched, TRUST_CONSTITUTION seven→eight Genesis Blocks, TECHNICAL_OVERVIEW 1244→1739 test count. 2 regression tests. Awaiting CX re-review. |
| 2026-02-24T21:30Z | `d907dec` | 1739 | Canonical doc rewrite ALL 3 PHASES COMPLETE. White Paper v2.0 (1228 lines, 25 sections + 3 appendices) + Public Brief v2.0 (620 lines). Bus-factor vulnerability closed. |
| 2026-02-20T07:00Z | `504a3ba` | 1612 | Phase F-4: Machine Agency Tier Integration. PHASE F COMPLETE. |
| 2026-02-20T06:00Z | `6c04147` | 1557 | Phase F-3: Domain Expert Pools + Machine Clearance. |
| 2026-02-20T04:30Z | `a616426` | 1516 | Phase F-2: Organisation Registry. |
| 2026-02-20T03:30Z | `5647a72` | 1463 | Phase F-1: Assembly — anonymous deliberation engine. |
| 2026-02-20T02:00Z | `0295219` | 1420 | CX P1 fix: fail-closed audit semantics. |
| 2026-02-20T01:30Z | `c66c088` | 1419 | CX P1 fix: auto-lapse moved to open_epoch(). |
| 2026-02-19T23:50Z | `c283f0f` | 1419 | CX P1+P2 fixes: expiry bounds + auto-lapse on startup. |
| 2026-02-19T22:30Z | `3879533` | 1415 | Open Work Principle code. |
| 2026-02-19T21:15Z | `6793018` | 1393 | CX P1 fixes: GCF treasury + disbursement + amendment persistence. |
| 2026-02-19T20:30Z | `3c32e2d` | 1390 | Assembly + Org Registry + Domain Experts + Autonomous Domain Agency. |
| 2026-02-19T19:30Z | `9888708` | 1390 | Headcount threshold audit COMPLETE. |
| 2026-02-19T19:00Z | `992443c` | 1390 | Gap 3 COMPLETE. G0 Retroactive Ratification Engine. |
| 2026-02-19T17:00Z | `9c55eec` | 1369 | Phase E-6 COMPLETE. Constitutional Amendment Engine. |
| 2026-02-19T16:00Z | `a57fa26` | 1320 | Phase E-5 COMPLETE. GCF disbursement governance. |
| 2026-02-19T12:30Z | `0e96683` | 1257 | Founder's veto wired to First Light. |
| 2026-02-19T11:00Z | `6e06ed7` | 1246 | display_score() x1000. |
| 2026-02-19T09:30Z | `092e9bd` | 1244 | Legacy reference sweep. |
| 2026-02-19T09:00Z | `62686b0` | 1244 | Compute infrastructure docs. |
| 2026-02-19T08:00Z | `256b61b` | 1244 | Bootstrap Curve + stale links. |
| 2026-02-18T23:30Z | `8aa3ed8` | 1244 | Legacy cleanup. |
| 2026-02-18T18:15Z | `67c9b29` | 1244 | Genesis Block 7 anchored. |
| 2026-02-18T15:30Z | `739f685` | 1244 | Technical Overview at GB6 parity. |
| 2026-02-18T14:00Z | `4f99a2c` | 1244 | Architecture Eliminates section. |
| 2026-02-18T13:30Z | `56d35cf` | 1244 | README expansion. |
| 2026-02-18T13:15Z | `973994f` | 1244 | Founder accountability line. |
| 2026-02-18T12:30Z | `05cf7f7` | 1244 | Narrative rework. |
| 2026-02-18T11:15Z | `530f21b` | 1244 | Genesis Block 6 anchored. |
| 2026-02-18T10:00Z | `9def859` | 1244 | CX P1 fix: workflow/escrow persistence. |
| 2026-02-18T08:30Z | `8a33165` | 1240 | CX P1+P2 fix: GCF restart, orphan escrow. |
| 2026-02-18T06:00Z | `ee1da8e` | 1237 | Phase E-4: Workflow Orchestration. |
| 2026-02-18T04:30Z | `9a9ec50` | 1204 | Phase E-3: Three-Tier Justice. |
| 2026-02-18T03:00Z | `0d88f82` | 1174 | Phase E-2: Harmful work prevention. |
| 2026-02-18T02:30Z | `a142903` | 1117 | Phase E-1: Genesis Common Fund. |
| 2026-02-18T01:15Z | `218b74b` | 1088 | Phase D-5b: pre-session prep + nuke appeal. |
| 2026-02-18T00:30Z | `42e213c` | 1073 | Phase D-5: quorum safeguards. |
| 2026-02-17T22:30Z | `20cef6d` | 1040 | Phase D: voice liveness + trust profiles. |
| 2026-02-17T16:00Z | `ebd01b4` | 955 | Phase C: machine immune system. |
| 2026-02-17T04:15Z | `3351b77` | 905 | CX fix: epoch-before-append. |
| 2026-02-17T03:30Z | `8031218` | 904 | Creator allocation 5% both-sides. |
| 2026-02-17T02:00Z | `57f7dcc` | 902 | CX P1 fix: RuntimeError catch. |
| 2026-02-17T01:25Z | `73b4195` | 900 | CX residual P2 fixes. |
| 2026-02-17T01:05Z | `0c4f593` | 896 | CX P1+P2 fixes: lifecycle persistence. |
| 2026-02-17T00:15Z | `464f25b` | 890 | Genesis Block 5 anchored. |
| 2026-02-17T00:10Z | `f650069` | 890 | Lifecycle wiring. |
| 2026-02-16T23:30Z | `0a1c77c` | 847 | Creator allocation fix. |
| 2026-02-16T21:45Z | `28d7fd2` | 846 | Verification rerun complete. |
| 2026-02-16T21:12Z | `28d7fd2` | 846 | Fixed CX P2s. |
| 2026-02-16T20:35Z | `d69ca81` | 845 | CX findings fixed. |
| 2026-02-16T20:10Z | `61fef95` | 842 | First qwerty checkpoint. |
