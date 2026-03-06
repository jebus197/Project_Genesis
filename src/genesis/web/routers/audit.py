"""Audit trail — the ledger is first-class.

Three event sources, strictly separated:
  • Historical anchors: constitutional anchoring records from docs/anchors.json.
    Real Ethereum transactions with verifiable tx hashes and Etherscan links.
  • Runtime anchors: COMMITMENT_ANCHORED events from the service event log.
    Emitted when anchor_commitment() succeeds during epoch lifecycle.
    Same verified badge treatment — only shown when tx_hash + explorer_url exist.
  • Internal ledger: all other governance events from the in-memory event log.
    No chain badge — these are platform-internal records.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request

from genesis.persistence.event_log import EventKind
from genesis.web.deps import get_service, get_templates
from genesis.web.negotiate import respond

router = APIRouter()

_ANCHORS_PATH = Path(__file__).resolve().parents[4] / "docs" / "anchors.json"
_SEPOLIA_CHAIN_ID = 11155111
_SEPOLIA_TX_PREFIX = "https://sepolia.etherscan.io/tx/"
_TX_HASH_RE = re.compile(r"^(0x)?[a-fA-F0-9]{64}$")
_AUDIT_INTERNAL_EVENT_LIMIT = 120
_AUDIT_RUNTIME_ANCHOR_LIMIT = 600


def _format_timestamp_compact(value: str) -> str:
    """Render ISO timestamps in a compact, human-readable UTC form."""
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return value


def _normalize_anchor_records(records: object) -> list[dict]:
    """Fail-closed filter for historical anchor records.

    Keeps only anchors with verifiable chain proof fields and sorts newest-first.
    """
    if not isinstance(records, list):
        return []

    normalized: list[dict] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        tx_hash = str(item.get("tx_hash", "")).strip()
        explorer_url = str(item.get("explorer_url", "")).strip()
        sha256 = str(item.get("sha256", "")).strip()
        if not tx_hash or not explorer_url or not sha256:
            continue
        if not _TX_HASH_RE.fullmatch(tx_hash):
            continue
        if not explorer_url.startswith(_SEPOLIA_TX_PREFIX):
            continue
        try:
            genesis_block = int(item.get("genesis_block", 0))
        except (TypeError, ValueError):
            continue
        record = dict(item)
        record["status"] = str(item.get("status", "canonical"))
        record["tx_hash"] = tx_hash
        record["explorer_url"] = explorer_url
        record["sha256"] = sha256
        record["minted_utc"] = str(item.get("minted_utc", "")).strip()
        record["genesis_block"] = genesis_block
        normalized.append(record)

    normalized.sort(
        key=lambda a: (str(a.get("minted_utc", "")), int(a.get("genesis_block", 0))),
        reverse=True,
    )
    return normalized


def _load_anchors() -> list[dict]:
    """Load on-chain anchor records from docs/anchors.json."""
    try:
        return _normalize_anchor_records(json.loads(_ANCHORS_PATH.read_text()))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _iter_event_records(source) -> list:
    if source is None:
        return []
    events_fn = getattr(source, "events", None)
    if callable(events_fn):
        return events_fn()
    return list(source)


def _extract_runtime_anchors(event_source) -> list[dict]:
    """Extract COMMITMENT_ANCHORED events from the event log.

    These are runtime anchor records emitted by GenesisService.anchor_commitment().
    Only included if they have a real tx_hash and explorer_url — no badge without proof.
    """
    runtime = []
    if event_source is None:
        return runtime

    for ev in _iter_event_records(event_source):
        kind = ev.event_kind.value if hasattr(ev.event_kind, "value") else str(ev.event_kind)
        if kind != "commitment_anchored":
            continue
        p = ev.payload
        # Release gate: no on-chain badge without verifiable tx proof
        tx_hash = str(p.get("tx_hash", "")).strip()
        explorer_url = str(p.get("explorer_url", "")).strip()
        try:
            chain_id = int(p.get("chain_id"))
        except (TypeError, ValueError):
            continue
        if (
            not _TX_HASH_RE.fullmatch(tx_hash)
            or not explorer_url.startswith(_SEPOLIA_TX_PREFIX)
            or chain_id != _SEPOLIA_CHAIN_ID
        ):
            continue
        runtime.append({
            "source": "runtime",
            "tx_hash": tx_hash,
            "block_number": p.get("block_number"),
            "chain_id": chain_id,
            "explorer_url": explorer_url,
            "sha256": p.get("sha256_hash", ""),
            "epoch_id": p.get("epoch_id", ""),
            "document": p.get("document_path", ""),
            "timestamp": ev.timestamp_utc,
            "summary": f"Runtime anchor — epoch {p.get('epoch_id', '?')}",
        })
    runtime.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return runtime


def _event_group(kind: str) -> str:
    lowered = kind.lower()
    if lowered.startswith("mission_"):
        return "Mission"
    if lowered.startswith("governance_") or lowered.startswith("assembly_"):
        return "Governance"
    if lowered.startswith("trust_"):
        return "Trust"
    if "evidence" in lowered or "review" in lowered:
        return "Verification"
    if "payment" in lowered or "escrow" in lowered or "payout" in lowered:
        return "Settlement"
    return "System"


def _event_label(kind: str) -> str:
    return kind.replace("_", " ").strip().title() if kind else "Event"


def _audit_actor_label(actor_id: str) -> str:
    value = str(actor_id or "").strip()
    if not value:
        return "unknown"
    if value.lower() == "system":
        return "system"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest().upper()[:8]
    return f"Anon-{digest}"


@router.get("")
async def audit_trail(request: Request):
    service = get_service()
    templates = get_templates(request)

    # --- Historical anchors (docs/anchors.json) ---
    anchors = _load_anchors()

    # --- Runtime anchors (COMMITMENT_ANCHORED events) ---
    runtime_anchor_events = service.recent_events(
        limit=_AUDIT_RUNTIME_ANCHOR_LIMIT,
        kind=EventKind.COMMITMENT_ANCHORED,
    )
    runtime_anchors = _extract_runtime_anchors(runtime_anchor_events)

    # --- Internal ledger events (everything except COMMITMENT_ANCHORED) ---
    events = []
    for ev in reversed(service.recent_events(limit=_AUDIT_INTERNAL_EVENT_LIMIT)):
        kind = ev.event_kind.value if hasattr(ev.event_kind, "value") else str(ev.event_kind)
        if kind == "commitment_anchored":
            continue  # Already surfaced in runtime_anchors
        summary = (
            ev.payload.get("summary")
            or ev.payload.get("action")
            or ev.payload.get("decision")
            or ev.payload.get("status")
            or "recorded"
        )
        events.append({
            "event_id": ev.event_id,
            "event_id_short": ev.event_id[:8],
            "kind": kind,
            "kind_label": _event_label(kind),
            "group": _event_group(kind),
            "timestamp": ev.timestamp_utc,
            "actor_label": _audit_actor_label(ev.actor_id),
            "summary": summary,
        })

    latest_chain_anchor = ""
    if runtime_anchors:
        latest_chain_anchor = runtime_anchors[0].get("timestamp", "")
    elif anchors:
        latest_chain_anchor = anchors[0].get("minted_utc", "")

    context = {
        "request": request,
        "active_tab": "audit",
        "anchors": anchors,
        "runtime_anchors": runtime_anchors,
        "events": events,
        "total_chain_anchors": len(anchors) + len(runtime_anchors),
        "latest_chain_anchor": latest_chain_anchor,
        "latest_chain_anchor_display": _format_timestamp_compact(latest_chain_anchor),
    }
    return respond(request, templates, "audit/trail.html", context)
