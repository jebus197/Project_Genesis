#!/usr/bin/env python3
"""Anchor the Genesis constitution on Ethereum Sepolia.

This script computes the SHA-256 hash of TRUST_CONSTITUTION.md and
embeds it in a blockchain transaction, creating permanent, tamper-evident
proof that the constitution existed in this exact form at this exact time.

Each anchor is a trust-minting event — the founding act of committing
the rules before any user exists to lobby for changes.

Usage:
    python3 tools/anchor_constitution.py
    python3 tools/anchor_constitution.py "Description of what changed"

Requires:
    SEPOLIA_RPC_URL and PRIVATE_KEY in a .env file at the project root.
"""

import os
import re
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

# Optional description from command line
description = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""

# ------------------------------------------------------------------ #
# Determine next Genesis Block number                                  #
# ------------------------------------------------------------------ #

def next_genesis_block(anchors_path: Path) -> int:
    """Read the anchors file and find the highest Genesis Block number."""
    if not anchors_path.exists():
        return 1
    text = anchors_path.read_text(encoding="utf-8")
    numbers = [int(m) for m in re.findall(r"## Genesis Block (\d+)", text)]
    return max(numbers) + 1 if numbers else 1

block_number = next_genesis_block(ANCHORS_FILE)

# ------------------------------------------------------------------ #
# Compute hash                                                        #
# ------------------------------------------------------------------ #

print("=" * 60)
print("PROJECT GENESIS — TRUST MINT EVENT")
print("=" * 60)
print()
print(f"  Genesis Block:  {block_number}")
print(f"  Document:       {CONSTITUTION.name}")

digest = canonical_hash_text(CONSTITUTION)
print(f"  SHA-256:        {digest}")
if description:
    print(f"  Description:    {description}")
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
# Log the anchor in Genesis Block format                               #
# ------------------------------------------------------------------ #

ANCHORS_FILE.parent.mkdir(parents=True, exist_ok=True)

short_tx = record.tx_hash[:10] + "..."

entry_lines = [
    f"## Genesis Block {block_number}",
    "",
    f"- `{digest}` → [tx {short_tx}]({record.explorer_url})",
    f"  Document: `TRUST_CONSTITUTION.md` | Ethereum Block: {record.block_number} | Minted: {record.timestamp_utc}",
]
if description:
    entry_lines.append(f"  **{description}**")
entry_lines.append("")

entry = "\n".join(entry_lines)

if ANCHORS_FILE.exists():
    existing = ANCHORS_FILE.read_text(encoding="utf-8")
else:
    existing = ""

# Insert after the horizontal rule (---) but before the first Genesis Block
SEPARATOR = "---"
if SEPARATOR in existing:
    head, tail = existing.split(SEPARATOR, 1)
    new_content = head + SEPARATOR + "\n\n" + entry + tail.lstrip("\n")
    ANCHORS_FILE.write_text(new_content, encoding="utf-8")
else:
    # Fallback: append to end
    with ANCHORS_FILE.open("a", encoding="utf-8") as f:
        f.write("\n" + entry)

print()
print("=" * 60)
print("TRUST MINT COMPLETE")
print("=" * 60)
print(f"  Genesis Block:  {block_number}")
print(f"  Hash:           {digest}")
print(f"  Tx:             {record.tx_hash}")
print(f"  Eth Block:      {record.block_number}")
print(f"  Explorer:       {record.explorer_url}")
print(f"  Logged:         {ANCHORS_FILE}")
print()
