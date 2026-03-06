#!/usr/bin/env python3
"""CX-CC Instant Messaging Service — lightweight coordination channel.

A self-culling, rolling-buffer coordination file for CC (Claude), CX (Codex),
and CW (Cowork). Replaces the old markdown coordination note.

Design:
- JSON state file with fixed-size rolling buffers (max 20 entries per stream).
- Oldest entries auto-deleted on write — no manual culling needed.
- Tiny reads: entire state is ~50-100 lines of JSON, always.
- Read-only semantics: the script manages the file, never injects into chat.
- Same approval protocol: nothing happens without George's approval.

Communication protocol (unchanged from previous system):
- George says `r` → run startup resync (Open Brain status + session context + IM read).
- George says `y` → approval.
- George says `rt` → startup resync + continue/review.
- CC posts via: python3 im_service.py post cc "message"
- CX posts via: python3 im_service.py post cx "message"
- CW posts via: python3 im_service.py post cw "message"
- Any agent reads via: python3 im_service.py read
- Set active action: python3 im_service.py action "status" "summary"
- Archive to permanent record: python3 im_service.py archive "summary"

The state file lives at: Project_Genesis/cw_handoff/im_state.json
The archive stays at: Project_Genesis_Notes/X_ARCHIVE_REVIEW_ROUNDS_1_TO_4.md

Rules:
1. Every entry prefixed CC: or CX:. Attribution is sacred.
2. Only genuine project files in repo. Agent-critical files in cw_handoff/.
3. CX proposals must pass the Sanity Gate (evidence, root-cause, minimality,
   safety, verification) before posting.
4. Auto-cull: writing a 21st entry drops the oldest. No manual discipline.
5. Repo path: /Users/georgejackson/Developer_Projects/Project_Genesis/
"""

from __future__ import annotations

import fcntl
import json
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

STATE_FILE = Path(__file__).parent / "im_state.json"
LOCK_FILE = Path(__file__).parent / "im_state.json.lock"
MAX_ENTRIES = 20  # Rolling buffer size per stream

INITIAL_STATE = {
    "version": "1.0",
    "protocol": {
        "keys": {
            "cc": "Claude (implementation, prose, document integration)",
            "cx": "Codex (technical review, invariant checks, runtime/test risks)",
            "cw": "Cowork (UX design, narrative, interactive testing)",
            "r": "Resync: Open Brain status + session context + IM read",
            "rt": "Resync + continue; review if warranted",
            "y": "Yes / approved",
        },
        "rules": [
            "Every entry prefixed CC:, CX:, or CW:. Attribution is sacred.",
            "Only genuine project files in repo. Working notes in Project_Genesis_Notes/.",
            "CX proposals must pass Sanity Gate before posting.",
            "Auto-cull: 21st entry drops oldest. No manual discipline needed.",
        ],
        "sanity_gate": [
            "1. Evidence gate: reproducible failure OR concrete code-traceable risk.",
            "2. Root-cause gate: specific file/line references.",
            "3. Minimality gate: smallest reversible fix.",
            "4. Safety gate: regression risk and backward-compat note.",
            "5. Verification gate: acceptance tests + full suite check.",
        ],
        "repo": "/Users/georgejackson/Developer_Projects/Project_Genesis/",
        "archive": "X_ARCHIVE_REVIEW_ROUNDS_1_TO_4.md",
    },
    "active_action": {
        "status": "IDLE",
        "summary": "No pending action.",
        "updated_utc": None,
    },
    "cc": [],
    "cx": [],
    "cw": [],
}


def _normalise_protocol(state: dict) -> None:
    """Keep protocol metadata aligned with current command behavior."""
    protocol = state.setdefault("protocol", {})
    default_protocol = INITIAL_STATE["protocol"]

    keys = protocol.setdefault("keys", {})
    default_keys = default_protocol["keys"]
    keys.setdefault("cc", default_keys["cc"])
    keys.setdefault("cx", default_keys["cx"])
    keys.setdefault("cw", default_keys["cw"])
    keys["r"] = default_keys["r"]
    keys["rt"] = default_keys["rt"]
    keys.setdefault("y", default_keys["y"])

    rules = protocol.setdefault("rules", [])
    new_rule = "Auto-cull: 21st entry drops oldest. No manual discipline needed."
    if not isinstance(rules, list):
        protocol["rules"] = [new_rule]
        return

    replaced = False
    for idx, rule in enumerate(rules):
        if isinstance(rule, str) and rule.startswith("Auto-cull:"):
            rules[idx] = new_rule
            replaced = True
            break
    if not replaced:
        rules.append(new_rule)


@contextmanager
def _locked_state() -> Generator[dict, None, None]:
    """Load state under exclusive file lock, save on exit.

    Prevents write-races when CC and CX (or parallel CC calls) run
    ``im_service.py post`` and ``im_service.py action`` concurrently.
    The lock is held for the entire read-modify-write cycle.
    """
    LOCK_FILE.touch(exist_ok=True)
    with open(LOCK_FILE, "r+") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)  # Block until exclusive lock acquired
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE) as f:
                    state = json.load(f)
            else:
                state = json.loads(json.dumps(INITIAL_STATE))  # Deep copy
            _normalise_protocol(state)
            yield state
            # Save on exit from the with block
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2, default=str)
                f.write("\n")
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _load_readonly() -> dict:
    """Load state for read-only access (still locked to prevent torn reads)."""
    LOCK_FILE.touch(exist_ok=True)
    with open(LOCK_FILE, "r+") as lf:
        fcntl.flock(lf, fcntl.LOCK_SH)  # Shared lock — blocks writers, allows readers
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE) as f:
                    state = json.load(f)
            else:
                state = json.loads(json.dumps(INITIAL_STATE))
            _normalise_protocol(state)
            return state
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _run_command(args: list[str]) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            args,
            cwd=_project_root(),
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except OSError as exc:
        return 127, "", str(exc)


def cmd_read() -> None:
    """Read the full IM state (debugging/audit). Use 'recent' for lean reads."""
    state = _load_readonly()
    print(json.dumps(state, indent=2, default=str))


def cmd_recent(n: int = 5) -> None:
    """Read only the last N entries per stream. No protocol metadata.

    This is what agents should use on startup — minimal tokens, maximum signal.
    """
    state = _load_readonly()
    compact: dict = {
        "active_action": state.get("active_action", {}),
    }
    for stream in ("cc", "cx", "cw"):
        entries = state.get(stream, [])
        compact[stream] = entries[:n]  # Already newest-first
    print(json.dumps(compact, indent=2, default=str))


def cmd_post(stream: str, message: str) -> None:
    """Post a message to CC, CX, or CW stream. Auto-culls to MAX_ENTRIES."""
    if stream not in ("cc", "cx", "cw"):
        print(f"Error: stream must be 'cc', 'cx', or 'cw', got '{stream}'", file=sys.stderr)
        sys.exit(1)

    with _locked_state() as state:
        entry = {
            "ts": _now(),
            "msg": message,
        }
        state[stream].insert(0, entry)  # Newest first

        # Auto-cull: keep only MAX_ENTRIES
        if len(state[stream]) > MAX_ENTRIES:
            state[stream] = state[stream][:MAX_ENTRIES]

        count = len(state[stream])

    print(f"Posted to {stream.upper()} stream ({count}/{MAX_ENTRIES} entries).")


def cmd_action(status: str, summary: str) -> None:
    """Set the active action status."""
    with _locked_state() as state:
        state["active_action"] = {
            "status": status,
            "summary": summary,
            "updated_utc": _now(),
        }
    print(f"Active action set: {status}")


def cmd_archive(summary: str) -> None:
    """Append a summary line to the permanent archive file."""
    archive_path = Path(__file__).parent / "X_ARCHIVE_REVIEW_ROUNDS_1_TO_4.md"
    if not archive_path.exists():
        print(f"Warning: archive file not found at {archive_path}", file=sys.stderr)
        return

    with open(archive_path, "a") as f:
        f.write(f"\n### Archived ({_now()})\n\n{summary}\n")

    print(f"Appended to archive: {archive_path.name}")


def cmd_clear(stream: str) -> None:
    """Clear all entries from a stream (used after archiving resolved rounds)."""
    if stream not in ("cc", "cx", "all"):
        print(f"Error: stream must be 'cc', 'cx', or 'all', got '{stream}'", file=sys.stderr)
        sys.exit(1)

    with _locked_state() as state:
        if stream == "all":
            state["cc"] = []
            state["cx"] = []
        else:
            state[stream] = []

    print(f"Cleared {stream} stream(s).")


def cmd_init() -> None:
    """Initialise the IM state file (first-time setup or reset)."""
    with _locked_state() as state:
        state.clear()
        state.update(INITIAL_STATE)
    print(f"Initialised IM state at {STATE_FILE}")


def cmd_resync(agent: str, *, continue_mode: bool) -> None:
    """Run startup resync: Open Brain status/context, then IM state read.

    Falls back cleanly to IM-only when Open Brain is unavailable.
    """
    if agent not in ("cc", "cx", "cw"):
        print(f"Error: agent must be 'cc', 'cx', or 'cw', got '{agent}'", file=sys.stderr)
        sys.exit(1)

    print(f"Resync start (agent={agent})")

    print("\n=== Open Brain: status ===")
    status_rc, status_out, status_err = _run_command(
        ["python3", "-m", "open_brain.cli", "status"],
    )
    open_brain_ok = status_rc == 0
    if status_out:
        print(status_out)
    if status_err:
        print(status_err, file=sys.stderr)
    if not open_brain_ok and not status_out and not status_err:
        print("Open Brain unavailable.")

    print("\n=== Open Brain: session-context ===")
    if open_brain_ok:
        ctx_rc, ctx_out, ctx_err = _run_command(
            ["python3", "-m", "open_brain.cli", "session-context", "--agent", agent],
        )
        if ctx_out:
            print(ctx_out)
        if ctx_err:
            print(ctx_err, file=sys.stderr)
        if ctx_rc != 0 and not ctx_out and not ctx_err:
            print("Session context unavailable.")
    else:
        print("Skipped (Open Brain status check failed).")

    print("\n=== IM recent (last 5 per stream) ===")
    cmd_recent(5)
    if continue_mode:
        print("\nResync complete. Continue.")


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            "  im_service.py r [cc|cx|cw]                — Resync startup context\n"
            "  im_service.py rt [cc|cx|cw]               — Resync + continue\n"
            "  im_service.py read                       — Read full state (debug)\n"
            "  im_service.py recent [N]                 — Last N entries/stream (default 5)\n"
            "  im_service.py post <cc|cx> \"message\"      — Post to stream\n"
            "  im_service.py action \"status\" \"summary\"   — Set active action\n"
            "  im_service.py archive \"summary\"           — Append to permanent archive\n"
            "  im_service.py clear <cc|cx|all>           — Clear stream entries\n"
            "  im_service.py init                        — Initialise state file\n"
        )
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd in {"r", "rt"}:
        agent = sys.argv[2] if len(sys.argv) >= 3 else "cx"
        cmd_resync(agent, continue_mode=(cmd == "rt"))
    elif cmd == "read":
        cmd_read()
    elif cmd == "recent":
        n = int(sys.argv[2]) if len(sys.argv) >= 3 else 5
        cmd_recent(n)
    elif cmd == "post":
        if len(sys.argv) < 4:
            print("Usage: im_service.py post <cc|cx> \"message\"", file=sys.stderr)
            sys.exit(1)
        cmd_post(sys.argv[2], sys.argv[3])
    elif cmd == "action":
        if len(sys.argv) < 4:
            print("Usage: im_service.py action \"status\" \"summary\"", file=sys.stderr)
            sys.exit(1)
        cmd_action(sys.argv[2], sys.argv[3])
    elif cmd == "archive":
        if len(sys.argv) < 3:
            print("Usage: im_service.py archive \"summary\"", file=sys.stderr)
            sys.exit(1)
        cmd_archive(sys.argv[2])
    elif cmd == "clear":
        if len(sys.argv) < 3:
            print("Usage: im_service.py clear <cc|cx|all>", file=sys.stderr)
            sys.exit(1)
        cmd_clear(sys.argv[2])
    elif cmd == "init":
        cmd_init()
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
