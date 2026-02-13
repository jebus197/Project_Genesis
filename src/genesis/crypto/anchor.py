"""Blockchain anchoring — embeds cryptographic hashes on Ethereum as tamper-evident proof.

Blockchain anchoring is the act of embedding a hash of important data
into a blockchain transaction, creating an immutable, timestamped,
publicly verifiable proof that the data existed in that exact form
at that exact moment.

This is NOT a smart contract. No code executes on-chain. The blockchain
serves as a witness — a notary stamp that cannot be forged, altered,
or retroactively changed.

Genesis uses blockchain anchoring to prove:
1. The constitution existed in a specific form at a specific time.
2. Epoch commitment payloads were produced and recorded.
3. Governance decisions were logged before outcomes were known.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class AnchorRecord:
    """A record of a successful blockchain anchor."""
    document_path: str
    sha256_hash: str
    tx_hash: str
    block_number: int
    chain_id: int
    timestamp_utc: str
    explorer_url: str


def canonical_hash(document_path: Path) -> str:
    """Compute the canonical SHA-256 hash of a JSON document.

    Canonical form: sorted keys, Unicode preserved, UTF-8 encoded.
    This ensures the same document always produces the same hash,
    regardless of key ordering or whitespace.
    """
    raw = document_path.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    canonical = json.dumps(parsed, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def canonical_hash_text(document_path: Path) -> str:
    """Compute the SHA-256 hash of a plain text document (e.g. Markdown).

    For non-JSON documents, we hash the raw UTF-8 bytes directly.
    No canonicalization needed — the file is its own canonical form.
    """
    raw = document_path.read_bytes()
    return hashlib.sha256(raw).hexdigest()


def anchor_to_chain(
    digest: str,
    rpc_url: str,
    private_key: str,
    chain_id: int = 11155111,  # Sepolia
    gas: int = 30_000,
    gas_price_gwei: str = "2",
) -> AnchorRecord:
    """Anchor a SHA-256 hash to Ethereum by embedding it in a transaction.

    Sends a 0-ETH self-send transaction with the hash in the data field.
    Waits for 1 confirmation. Returns a complete AnchorRecord.

    Args:
        digest: The SHA-256 hex string to anchor.
        rpc_url: Ethereum RPC endpoint URL.
        private_key: Hex-encoded private key for signing.
        chain_id: Network chain ID (default: 11155111 = Sepolia).
        gas: Gas limit for the transaction.
        gas_price_gwei: Gas price in gwei.

    Returns:
        AnchorRecord with transaction details.
    """
    from web3 import Web3, HTTPProvider
    from eth_account import Account

    w3 = Web3(HTTPProvider(rpc_url))
    acct = Account.from_key(private_key)

    nonce = w3.eth.get_transaction_count(acct.address)
    tx = {
        "to": acct.address,  # self-send, 0 ETH
        "value": 0,
        "gas": gas,
        "gasPrice": w3.to_wei(gas_price_gwei, "gwei"),
        "nonce": nonce,
        "chainId": chain_id,
        "data": bytes.fromhex(digest),
    }

    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

    print(f"  Sent tx: {tx_hash.hex()}")
    print(f"  Waiting for confirmation ...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

    explorer_url = f"https://sepolia.etherscan.io/tx/{tx_hash.hex()}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"  Confirmed in block {receipt.blockNumber}")
    print(f"  Explorer: {explorer_url}")

    return AnchorRecord(
        document_path="",
        sha256_hash=digest,
        tx_hash=tx_hash.hex(),
        block_number=receipt.blockNumber,
        chain_id=chain_id,
        timestamp_utc=now,
        explorer_url=explorer_url,
    )
