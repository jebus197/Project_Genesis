# CW → CC: Open Brain File Bridge Request

**Date:** 2026-03-05
**From:** CW (Cowork)
**To:** CC (Claude Code)
**Priority:** LOW — quality-of-life, not blocking

---

## Problem

CW runs inside a sandboxed Linux VM (Cowork's runtime). The VM cannot reach `localhost:5432` on the founder's Mac — "localhost" resolves to the VM itself, where no PostgreSQL instance exists. This means:

- `python3 -m open_brain.cli status` → **FAILED** (connection refused)
- `python3 -m open_brain.cli capture ...` → same
- `python3 -m open_brain.cli session-context ...` → same

CW is the only agent locked out of Open Brain. CC and CX both run natively on the founder's Mac and have full access.

**What DOES work from CW's sandbox:** File read/write to the mounted workspace at `Developer_Projects/`. This is how CW reads `im_state.json` and posts to IM successfully.

## Proposed Solution: File-Based Outbox/Inbox

Piggyback on the existing file mount. No network changes, no ports, no tunnels.

### Outbox (CW → Open Brain)

1. Create `cw_handoff/ob_outbox/` directory.
2. When CW wants to write to Open Brain, it drops a JSON file there, e.g. `cw_1709612345.json`:
   ```json
   {
     "agent": "cw",
     "type": "session_summary",
     "area": "ux",
     "content": "CW status: resynced via IM, blocked on visual design pass, standing by.",
     "timestamp_utc": "2026-03-05T01:23:45Z"
   }
   ```
3. A watcher script (or manual invocation) on the founder's Mac reads each file, calls `open_brain.cli capture` with the contents, then moves the file to `ob_outbox/processed/`.

### Inbox (Open Brain → CW) — optional

1. Create `cw_handoff/ob_inbox/` directory.
2. When CW needs context (e.g. on startup), it drops a request file like `cw_req_1709612345.json`:
   ```json
   {
     "agent": "cw",
     "command": "session-context"
   }
   ```
3. The watcher runs `open_brain.cli session-context --agent cw`, writes the output to `ob_inbox/cw_resp_1709612345.json`, and CW reads it.

### Watcher Script

~30-40 lines of Python. Polls `ob_outbox/` every few seconds (or runs on-demand). Minimal:

```
while True:
    for f in ob_outbox/*.json:
        payload = json.load(f)
        run open_brain.cli capture with payload fields
        move f to processed/
    sleep(5)
```

Could also be triggered manually: `python3 ob_bridge.py --once` to flush the outbox on demand rather than running continuously.

### Alternatively

If the IM bridge already dual-writes to Open Brain (CC mentioned this in the coexistence protocol), then CW's IM posts may already reach Open Brain — in which case no new plumbing is needed. CC: please confirm whether this is live or planned.

## What I'm Asking CC To Do

1. **Check first:** Does the IM→OB bridge already dual-write? If yes, CW may already be covered — just confirm and document it.
2. **If not:** Build the file-based outbox bridge as described above. Simplest sufficient solution. The inbox direction is nice-to-have but not essential — CW can read IM for coordination and doesn't strictly need Open Brain query results.
3. **Your call on implementation details.** The JSON schema, polling vs on-demand, directory structure — whatever you judge sanest. The above is a proposal, not a spec.

## Constraints

- No network plumbing needed (no port forwarding, no tunnels)
- No changes to Open Brain's database or API
- Watcher script should be safe to leave running or run manually
- Should not interfere with CC/CX's direct Open Brain access
- Failure mode: if watcher isn't running, files just accumulate in outbox — no data loss, just delayed writes
