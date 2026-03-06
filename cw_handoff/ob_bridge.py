#!/usr/bin/env python3
"""Open Brain file-based bridge for agents without DB access (e.g. CW).

CW drops JSON files into cw_handoff/ob_outbox/. This script polls that
folder, runs open_brain.cli capture for each file, and moves processed
files to ob_outbox/processed/.

JSON file format (one per file):
{
  "agent": "cw",
  "type": "session_summary",   # memory_type: session_summary|insight|decision|task|blocker
  "area": "ux",                # optional, defaults to "general"
  "text": "The memory content"
}

Usage:
  # Run once (process all pending files):
  python3 cw_handoff/ob_bridge.py

  # Run as watcher (poll every 5 seconds):
  python3 cw_handoff/ob_bridge.py --watch
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

OUTBOX = Path(__file__).parent / "ob_outbox"
PROCESSED = OUTBOX / "processed"
REPO = Path(__file__).parent.parent  # Project_Genesis/


def process_file(p: Path) -> bool:
    """Process one outbox JSON file via open_brain CLI. Returns True on success."""
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"  SKIP {p.name}: {e}")
        return False

    agent = data.get("agent", "cw")
    mem_type = data.get("type", "session_summary")
    area = data.get("area", "general")
    text = data.get("text", "")

    if not text.strip():
        print(f"  SKIP {p.name}: empty text")
        return False

    cmd = [
        sys.executable, "-m", "open_brain.cli", "capture",
        text,
        "--agent", agent,
        "--type", mem_type,
        "--area", area,
    ]
    result = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)

    if result.returncode == 0:
        print(f"  OK   {p.name} -> OB ({agent}/{mem_type}/{area})")
        return True
    else:
        print(f"  FAIL {p.name}: {result.stderr.strip()[:200]}")
        return False


def run_once() -> int:
    """Process all pending files. Returns count processed."""
    PROCESSED.mkdir(parents=True, exist_ok=True)
    files = sorted(OUTBOX.glob("*.json"))
    if not files:
        return 0

    count = 0
    for p in files:
        if process_file(p):
            shutil.move(str(p), str(PROCESSED / p.name))
            count += 1
        else:
            # Move failures too so they don't block the queue
            shutil.move(str(p), str(PROCESSED / f"FAILED_{p.name}"))
    return count


def watch(interval: float = 5.0) -> None:
    """Poll outbox every `interval` seconds."""
    print(f"OB bridge watching {OUTBOX}/ (every {interval}s, Ctrl-C to stop)")
    while True:
        n = run_once()
        if n:
            print(f"  Processed {n} file(s)")
        time.sleep(interval)


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch()
    else:
        n = run_once()
        if n:
            print(f"Processed {n} file(s)")
        else:
            print("No pending files in ob_outbox/")
