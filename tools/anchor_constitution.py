#!/usr/bin/env python3
"""Anchor the Genesis constitution on Ethereum Sepolia.

This script computes the SHA-256 hash of TRUST_CONSTITUTION.md and
embeds it in a blockchain transaction, creating permanent, tamper-evident
proof that the constitution existed in this exact form at this exact time.

Usage:
    python3 tools/anchor_constitution.py

Requires:
    SEPOLIA_RPC_URL and PRIVATE_KEY in a .env file at the project root.
"""

import os
import sys
from pathlib import Path

# Add src to path for genesis imports
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
from genesis.crypto.anchor import canonical_hash_text, anchor_to_chain

# ------------------------------------------------------------------ #
# Configuration                                                       #
# ------------------------------------------------------------------ #

load_dotenv(ROOT / ".env")

RPC_URL = os.getenv("SEPOLIA_RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY") or os.getenv("SEPOLIA_PRIVATE_KEY")

if not RPC_URL or not PRIVATE_KEY:
    print("ERROR: Missing SEPOLIA_RPC_URL and/or PRIVATE_KEY in .env")
    sys.exit(1)

CONSTITUTION = ROOT / "TRUST_CONSTITUTION.md"
ANCHORS_FILE = ROOT / "docs" / "ANCHORS.md"

if not CONSTITUTION.exists():
    print(f"ERROR: Constitution not found: {CONSTITUTION}")
    sys.exit(1)

# ------------------------------------------------------------------ #
# Compute hash                                                        #
# ------------------------------------------------------------------ #

print("=" * 60)
print("PROJECT GENESIS — CONSTITUTION BLOCKCHAIN ANCHOR")
print("=" * 60)
print()
print(f"Document: {CONSTITUTION.name}")

digest = canonical_hash_text(CONSTITUTION)
print(f"SHA-256:  {digest}")
print()

# ------------------------------------------------------------------ #
# Anchor on Sepolia                                                   #
# ------------------------------------------------------------------ #

print("Anchoring to Ethereum Sepolia (Chain ID: 11155111) ...")
print()

record = anchor_to_chain(
    digest=digest,
    rpc_url=RPC_URL,
    private_key=PRIVATE_KEY,
    gas_price_gwei="10",
)

# ------------------------------------------------------------------ #
# Log the anchor                                                      #
# ------------------------------------------------------------------ #

ANCHORS_FILE.parent.mkdir(parents=True, exist_ok=True)

entry = (
    f"- `{digest}` → "
    f"[{record.tx_hash}]({record.explorer_url})  \n"
    f"  Document: `TRUST_CONSTITUTION.md` | "
    f"Block: {record.block_number} | "
    f"Anchored: {record.timestamp_utc}\n"
)

if ANCHORS_FILE.exists():
    existing = ANCHORS_FILE.read_text(encoding="utf-8")
else:
    existing = ""

MARKER = "## Constitution anchors"
if MARKER in existing:
    head, tail = existing.split(MARKER, 1)
    new_content = head + MARKER + "\n\n" + entry + tail.lstrip("\n")
    ANCHORS_FILE.write_text(new_content, encoding="utf-8")
else:
    with ANCHORS_FILE.open("a", encoding="utf-8") as f:
        if not existing.strip():
            f.write("# Project Genesis — Blockchain Anchor Log\n\n")
            f.write("This file records every blockchain anchoring event.\n")
            f.write("Each entry links a SHA-256 hash to a Sepolia transaction,\n")
            f.write("providing tamper-evident proof that the document existed\n")
            f.write("in that exact form at that exact time.\n\n")
            f.write(f"{MARKER}\n\n")
        else:
            f.write(f"\n{MARKER}\n\n")
        f.write(entry)

print()
print("=" * 60)
print("ANCHOR COMPLETE")
print("=" * 60)
print(f"  Hash:     {digest}")
print(f"  Tx:       {record.tx_hash}")
print(f"  Block:    {record.block_number}")
print(f"  Explorer: {record.explorer_url}")
print(f"  Logged:   {ANCHORS_FILE}")
print()
