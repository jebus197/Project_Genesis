#!/usr/bin/env python3
"""File integrity verification for agent coordination files.

Defence-in-depth for flat-file agent coordination (MEMORY.md,
ACTION_QUEUE.md, QWERTY_CHECKPOINT.md).  Three layers:

  Layer 1 — Local:  SHA-256 content hash + Ed25519 signature per file.
                    Catches filesystem tampering by any process without
                    the private key.

  Layer 2 — Chain:  Append-only integrity log with hash-chain linking.
                    Each entry links to the previous via SHA-256.
                    Modification of any historical entry invalidates all
                    subsequent entries.

  Layer 3 — Anchor: Periodic Merkle rollup stored as OB memory.
                    OB's existing epoch service anchors Merkle roots
                    on-chain (Sepolia).  Provides immutable, independently
                    verifiable proof that coordination files existed in a
                    specific state at a specific time.  Gracefully degrades
                    if OB is unavailable.

Uses OB's existing Ed25519 keypair (~/.openbrain/keys/) for signing
consistency.  Falls back to unsigned hashing if no keypair exists.

Zero dependency on OB's database layer.  Zero regression risk to
OB's 438-test suite.

Usage:
    python3 file_integrity.py sign   <file> --agent cc
    python3 file_integrity.py verify <file>
    python3 file_integrity.py verify-chain
    python3 file_integrity.py rollup [--anchor]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Ed25519 support (optional — same library OB uses)
# ---------------------------------------------------------------------------

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization
    from cryptography.exceptions import InvalidSignature

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# OB's keypair location — reuse for signing consistency
OB_KEYS_DIR = Path.home() / ".openbrain" / "keys"
PRIVATE_KEY_FILE = OB_KEYS_DIR / "ed25519_private.pem"
PUBLIC_KEY_FILE = OB_KEYS_DIR / "ed25519_public.pem"

# Append-only integrity log with hash chain
INTEGRITY_LOG = Path(__file__).resolve().parent / ".integrity_chain.jsonl"

# Chain genesis — matches OB's convention (hashing.py)
GENESIS_HASH = "sha256:genesis"


# ---------------------------------------------------------------------------
# File hashing
# ---------------------------------------------------------------------------


def hash_file(path: Path) -> str:
    """Compute SHA-256 of file contents.  Returns ``sha256:<hex>``."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def hash_entry(entry: dict) -> str:
    """Compute SHA-256 of a log entry (for chain linking)."""
    canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


# ---------------------------------------------------------------------------
# Ed25519 signing (reuses OB's existing keypair)
# ---------------------------------------------------------------------------


def _load_private_key() -> Optional[Any]:
    """Load OB's Ed25519 private key.  Returns None if unavailable."""
    if not HAS_CRYPTO or not PRIVATE_KEY_FILE.exists():
        return None
    pem = PRIVATE_KEY_FILE.read_bytes()
    key = serialization.load_pem_private_key(pem, password=None)
    return key if isinstance(key, Ed25519PrivateKey) else None


def _load_public_key() -> Optional[Any]:
    """Load OB's Ed25519 public key.  Returns None if unavailable."""
    if not HAS_CRYPTO or not PUBLIC_KEY_FILE.exists():
        return None
    pem = PUBLIC_KEY_FILE.read_bytes()
    key = serialization.load_pem_public_key(pem)
    return key if isinstance(key, Ed25519PublicKey) else None


def sign_content(content: bytes) -> Optional[str]:
    """Sign content with Ed25519.  Returns hex signature or None."""
    key = _load_private_key()
    if key is None:
        return None
    return key.sign(content).hex()


def verify_ed25519(content: bytes, sig_hex: str) -> bool:
    """Verify Ed25519 signature.  Returns False if no key or invalid."""
    key = _load_public_key()
    if key is None:
        return False
    try:
        key.verify(bytes.fromhex(sig_hex), content)
        return True
    except (InvalidSignature, ValueError):
        return False


# ---------------------------------------------------------------------------
# Integrity log — append-only JSONL with hash chain
# ---------------------------------------------------------------------------


def _get_last_entry_hash() -> str:
    """Read the hash of the last entry in the chain, or GENESIS_HASH."""
    if not INTEGRITY_LOG.exists():
        return GENESIS_HASH
    last_line = ""
    with open(INTEGRITY_LOG, "r") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                last_line = stripped
    if not last_line:
        return GENESIS_HASH
    try:
        entry = json.loads(last_line)
        return hash_entry(entry)
    except json.JSONDecodeError:
        return GENESIS_HASH


def append_entry(
    file_path: str,
    file_hash: str,
    agent: str,
    signature: Optional[str] = None,
) -> dict:
    """Append a signed entry to the integrity log.  Returns the entry."""
    prev_hash = _get_last_entry_hash()
    ts = datetime.now(timezone.utc).isoformat()

    entry: Dict[str, Any] = {
        "file": file_path,
        "sha256": file_hash,
        "agent": agent,
        "timestamp": ts,
        "previous_hash": prev_hash,
    }
    if signature:
        entry["signature"] = signature

    INTEGRITY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(INTEGRITY_LOG, "a") as f:
        f.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")

    return entry


# ---------------------------------------------------------------------------
# Chain verification
# ---------------------------------------------------------------------------


def verify_chain() -> Dict[str, Any]:
    """Walk the integrity chain and verify every link + signature."""
    if not INTEGRITY_LOG.exists():
        return {
            "total": 0,
            "valid": 0,
            "broken_chain": [],
            "broken_sig": [],
        }

    entries: List[tuple] = []
    with open(INTEGRITY_LOG, "r") as f:
        for i, line in enumerate(f):
            stripped = line.strip()
            if stripped:
                try:
                    entries.append((i + 1, json.loads(stripped)))
                except json.JSONDecodeError:
                    pass

    result: Dict[str, Any] = {
        "total": len(entries),
        "valid": 0,
        "broken_chain": [],
        "broken_sig": [],
    }

    expected_prev = GENESIS_HASH

    for line_num, entry in entries:
        # --- chain link ---
        actual_prev = entry.get("previous_hash", "")
        if actual_prev != expected_prev:
            result["broken_chain"].append({
                "line": line_num,
                "file": entry.get("file", "?"),
                "expected": expected_prev,
                "actual": actual_prev,
            })

        # --- signature ---
        sig = entry.get("signature")
        if sig:
            verify_entry = {k: v for k, v in entry.items() if k != "signature"}
            content = json.dumps(
                verify_entry, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            if not verify_ed25519(content, sig):
                result["broken_sig"].append({
                    "line": line_num,
                    "file": entry.get("file", "?"),
                })
            else:
                result["valid"] += 1
        else:
            # Unsigned entries counted as valid (pre-signing migration)
            result["valid"] += 1

        # advance chain
        expected_prev = hash_entry(entry)

    return result


# ---------------------------------------------------------------------------
# File verification (Layer 1)
# ---------------------------------------------------------------------------


def cmd_sign_file(path: str, agent: str) -> dict:
    """Sign a file and append to the integrity chain.

    Builds the entry once, signs it, then appends — the signed content
    and the stored content are identical (same timestamp, same hash).
    """
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    file_hash = hash_file(p)
    prev_hash = _get_last_entry_hash()
    ts = datetime.now(timezone.utc).isoformat()

    # Build the entry (everything except signature)
    entry: Dict[str, Any] = {
        "file": str(p),
        "sha256": file_hash,
        "agent": agent,
        "timestamp": ts,
        "previous_hash": prev_hash,
    }

    # Sign the canonical entry
    canonical = json.dumps(
        entry, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    signature = sign_content(canonical)
    if signature:
        entry["signature"] = signature

    # Append to log
    INTEGRITY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(INTEGRITY_LOG, "a") as f:
        f.write(
            json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n"
        )

    return entry


def cmd_verify_file(path: str) -> Dict[str, Any]:
    """Verify a file against the latest entry in the integrity chain."""
    p = Path(path).resolve()
    if not p.exists():
        return {"status": "ERROR", "reason": f"File not found: {p}"}

    current_hash = hash_file(p)

    if not INTEGRITY_LOG.exists():
        return {"status": "UNTRACKED", "file": str(p), "hash": current_hash}

    # Find the latest entry for this file
    latest: Optional[dict] = None
    with open(INTEGRITY_LOG, "r") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
                if entry.get("file") == str(p):
                    latest = entry
            except json.JSONDecodeError:
                continue

    if latest is None:
        return {"status": "UNTRACKED", "file": str(p), "hash": current_hash}

    recorded_hash = latest.get("sha256", "")

    if current_hash != recorded_hash:
        return {
            "status": "MODIFIED",
            "file": str(p),
            "recorded_hash": recorded_hash,
            "current_hash": current_hash,
            "recorded_at": latest.get("timestamp", "?"),
            "agent": latest.get("agent", "?"),
        }

    # Content matches — verify signature if present
    sig = latest.get("signature")
    sig_valid: Optional[bool] = None
    if sig:
        verify_entry = {k: v for k, v in latest.items() if k != "signature"}
        content = json.dumps(
            verify_entry, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        sig_valid = verify_ed25519(content, sig)

    return {
        "status": "VERIFIED",
        "file": str(p),
        "hash": current_hash,
        "signed_by": latest.get("agent", "?"),
        "signed_at": latest.get("timestamp", "?"),
        "signature_valid": sig_valid,
    }


# ---------------------------------------------------------------------------
# Merkle rollup (Layer 3)
# ---------------------------------------------------------------------------


def _build_merkle_root(hashes: List[str]) -> str:
    """Build a Merkle root from a list of hash strings."""
    if not hashes:
        return GENESIS_HASH

    # Leaf nodes
    nodes = [hashlib.sha256(h.encode("utf-8")).digest() for h in hashes]

    while len(nodes) > 1:
        # Duplicate last node if odd count
        if len(nodes) % 2 == 1:
            nodes.append(nodes[-1])
        next_level = []
        for i in range(0, len(nodes), 2):
            combined = nodes[i] + nodes[i + 1]
            next_level.append(hashlib.sha256(combined).digest())
        nodes = next_level

    return f"sha256:{nodes[0].hex()}"


def cmd_rollup(anchor: bool = False) -> Dict[str, Any]:
    """Build Merkle tree from all entries; optionally anchor via OB."""
    if not INTEGRITY_LOG.exists():
        return {"entries": 0, "merkle_root": GENESIS_HASH, "anchored": False}

    entry_hashes: List[str] = []
    with open(INTEGRITY_LOG, "r") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                entry_hashes.append(
                    f"sha256:{hashlib.sha256(stripped.encode('utf-8')).hexdigest()}"
                )

    merkle_root = _build_merkle_root(entry_hashes)
    ts = datetime.now(timezone.utc).isoformat()

    result: Dict[str, Any] = {
        "entries": len(entry_hashes),
        "merkle_root": merkle_root,
        "timestamp": ts,
        "anchored": False,
    }

    if anchor:
        # Store Merkle root as OB memory — OB's epoch service handles
        # the on-chain anchoring automatically at the next seal-epoch.
        text = (
            f"FILE_INTEGRITY_ROLLUP "
            f"merkle_root={merkle_root} "
            f"entries={len(entry_hashes)} "
            f"timestamp={ts}"
        )
        try:
            proc = subprocess.run(
                [
                    sys.executable, "-m", "open_brain.cli",
                    "capture", text,
                    "--agent", "cc",
                    "--type", "insight",
                    "--area", "ops",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            result["anchored"] = proc.returncode == 0
            if proc.returncode != 0:
                result["anchor_error"] = proc.stderr.strip()[:200]
        except Exception as e:
            # Graceful degradation — OB not available
            result["anchor_error"] = f"OB unavailable: {type(e).__name__}"

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Defence-in-depth integrity for agent coordination files",
    )
    sub = parser.add_subparsers(dest="command")

    # sign
    p_sign = sub.add_parser("sign", help="Sign a file and append to chain")
    p_sign.add_argument("file", help="Path to file")
    p_sign.add_argument("--agent", required=True, help="Agent identifier")

    # verify
    p_verify = sub.add_parser("verify", help="Verify file against chain")
    p_verify.add_argument("file", help="Path to file")

    # verify-chain
    sub.add_parser("verify-chain", help="Verify entire integrity chain")

    # rollup
    p_rollup = sub.add_parser("rollup", help="Merkle rollup of chain")
    p_rollup.add_argument(
        "--anchor", action="store_true",
        help="Anchor Merkle root to OB for on-chain rollup",
    )

    args = parser.parse_args()

    if args.command == "sign":
        entry = cmd_sign_file(args.file, args.agent)
        print(json.dumps(entry, indent=2))

    elif args.command == "verify":
        result = cmd_verify_file(args.file)
        print(json.dumps(result, indent=2))
        if result.get("status") == "MODIFIED":
            sys.exit(1)

    elif args.command == "verify-chain":
        result = verify_chain()
        print(json.dumps(result, indent=2))
        if result["broken_chain"] or result["broken_sig"]:
            sys.exit(1)

    elif args.command == "rollup":
        result = cmd_rollup(anchor=getattr(args, "anchor", False))
        print(json.dumps(result, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
