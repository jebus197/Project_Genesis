# Action Queue — Cross-Agent Persistent Task Tracker
# All agents: READ THIS FILE ON EVERY SESSION START.
# Update task status as you work. Add new tasks as they arise.
# Format: - [agent] [date] description | assigned_by: X | status: pending|in_progress|completed|blocked

## PENDING
- [cx] [2026-03-05] Design debt: expose public event query on GenesisService (replace _event_log access in audit.py) | assigned_by: cc | status: pending
- [cx] [2026-03-05] Design debt: add EventLog.recent_events(n) or pagination (events() loads full log unbounded) | assigned_by: cc | status: pending
- [cw] [2026-03-04] Full UX/visual design pass — deferred until plumbing complete and CW can test live app | assigned_by: george | status: blocked

## IN PROGRESS
(none currently)

## COMPLETED
- [cx] [2026-03-05] Fix trust gate mismatch: derive web gates from constitutional_params.json | completed: 2026-03-05
- [cx] [2026-03-05] Mark panel-hardening walkthrough sections as "FUTURE: Step 10f" | completed: 2026-03-05
- [cx] [2026-03-05] Packet UX relabel (UX-only, backend stays) | completed: 2026-03-05
- [cx] [2026-03-05] Audit p-pass hardening: durable EventLog, tx hash validator, release gate tests, actor redaction | completed: 2026-03-05
- [cc] [2026-03-05] P-pass tx hash regex tightened to {64} (proper Ethereum hash length) | completed: 2026-03-05
- [cc] [2026-03-05] IM token reduction: recent N command, 77% bandwidth cut on r/rt | completed: 2026-03-05
- [all] [2026-03-04] Open Brain system BUILT — 50 tests passing, MCP + CLI + IM bridge live | completed: 2026-03-04
- [cx] [2026-03-04] Assembly amendment flow implementation (submit, linked amendments, panel composition) | completed: 2026-03-04
- [cc] [2026-03-04] Governance mapping delivered to CX (Assembly L1 -> Amendment L2 -> Verification L3) | completed: 2026-03-03
- [cc] [2026-03-04] Chamber domain-specialist gating documented on ROADMAP Step 10f | completed: 2026-03-03
- [cc] [2026-03-04] IM service capacity bumped 6->20 | completed: 2026-03-03
- [cc] [2026-03-04] Trust gate fix + no-hardcode principle posted to CX | completed: 2026-03-04
- [cc] [2026-03-04] Open Brain spec written (OPEN_BRAIN_SPEC.md) | completed: 2026-03-04
