# Project Genesis — Project-Level Instructions

These instructions override or supplement the global `~/.claude/CLAUDE.md`
when the working directory is within this repository.

## Identity

Trust-mediated labour market for mixed human-AI populations. World's first
intelligence-agnostic anti-social network. Stack: FastAPI + Jinja2 + HTMX.

Agents: cc (Claude Code), cx (Codex), cw (Claude Web).

## Recovery (project-specific)

After compaction, in addition to the universal checks (git state + OB
session-context), run:
  (c) python3 cw_handoff/im_service.py read --recent 3

On session start (alongside recovery), verify coordination file integrity:
  python3 cw_handoff/file_integrity.py verify-chain
If broken_chain or broken_sig is non-empty, STOP and alert the user.

## Coordination File Integrity

MEMORY.md, ACTION_QUEUE.md, and QWERTY_CHECKPOINT.md are signed with
Ed25519 + hash-chained via cw_handoff/file_integrity.py. After any write
to these files, re-sign:
  python3 cw_handoff/file_integrity.py sign <file> --agent cc
Periodic Merkle rollups anchor the chain state into OB (and on-chain):
  python3 cw_handoff/file_integrity.py rollup --anchor

## Checkpoint Protocol (qwerty)

CC MUST run qwerty on every turn:
  q — Quality: tests passing (run suite, report count)
  w — Written: committed and pushed (git status clean, origin up to date)
  e — Exchanged: CX notified via IM service (post with commit hash)
  r — Recorded: MEMORY.md updated (current state, test count, pending items)
  ty — Tidy: docs lock-stepped (README, constitution, events, anchors)

CC writes every checkpoint to cw_handoff/QWERTY_CHECKPOINT.md.
IM service is updated on every turn, not just milestones.

## IM Service

Post: python3 cw_handoff/im_service.py post cc "<message>"
Read: python3 cw_handoff/im_service.py read
Read recent: python3 cw_handoff/im_service.py read --recent N

## Session Boundary Rules

Before closing ANY session:
1. Post to IM service summarising what was done (commit hashes, changes)
2. Update MEMORY.md with current state
3. Verify tests pass and record count
4. Ensure all docs are lock-stepped

## Key Paths

- Constitution: TRUST_CONSTITUTION.md
- Constitutional params: src/genesis/governance/constitutional_params.json
- Coordination: cw_handoff/ (IM, checkpoints, action queue, file integrity)
- Notes: /Users/georgejackson/Developer_Projects/Project_Genesis_Notes/
- Development roadmap: Notes dir / DEVELOPMENT_ROADMAP.md
- Wallet: ~/Desktop/wallet.env (0xC367...7CE on Sepolia)

## Boundary

Do NOT read Genesis files when CWD is a different project. Genesis-specific
recovery commands must not execute from non-Genesis working directories.
