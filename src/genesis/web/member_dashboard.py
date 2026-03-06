"""Member dashboard shaping from live service data.

Builds the /members payload from the backend service so the UI reflects
actual roster, trust, bidding, mission, and GCF state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from genesis.models.market import Bid, BidState, ListingState, MarketListing
from genesis.models.mission import MissionState
from genesis.service import GenesisService


SCAN_LIMIT = 1000


def build_member_dashboard(
    service: GenesisService,
    actor_id: str,
    display_name: str | None = None,
) -> dict[str, Any]:
    """Return a members dashboard payload for a single actor."""
    actor = service.get_actor(actor_id)
    if actor is None:
        raise ValueError(f"Unknown actor_id: {actor_id}")

    trust = service.get_trust(actor_id)
    trust_score = int(round((trust.score if trust else 0.0) * 1000))

    listings = _fetch_all_listings(service)
    bid_rows: list[dict[str, Any]] = []
    completed_rows: list[dict[str, Any]] = []
    completed_ids: set[str] = set()
    circles_joined: set[str] = set()

    submitted_count = 0
    accepted_count = 0

    for listing in listings:
        actor_bids = [bid for bid in service.get_bids(listing.listing_id) if bid.worker_id == actor_id]
        if not actor_bids:
            continue

        latest_bid = _latest_bid(actor_bids)
        circle_name = _circle_name_from_tags(listing.domain_tags)
        circles_joined.add(circle_name)

        submitted_count += 1
        if latest_bid.state == BidState.ACCEPTED:
            accepted_count += 1

        bid_rows.append({
            "mission_id": listing.listing_id,
            "mission_title": listing.title,
            "circle_name": circle_name,
            "bid_status": _bid_status_label(latest_bid.state, listing.state),
            "next_gate": _next_gate(latest_bid.state, listing.state),
        })

        completed = _completed_row_for_listing(service, listing, actor_id)
        if completed is not None and completed["mission_id"] not in completed_ids:
            completed_rows.append(completed)
            completed_ids.add(completed["mission_id"])

    # Stable ordering keeps JSON/HTML deterministic for tests and UX
    bid_rows.sort(key=lambda row: (row["mission_title"].lower(), row["mission_id"]))
    completed_rows.sort(key=lambda row: row["mission_title"].lower())

    active_bids = sum(
        1 for row in bid_rows
        if row["bid_status"] in {"Submitted", "Under listing review", "Shortlisted"}
    )

    reward_flow = _build_reward_flow(
        submitted=submitted_count,
        accepted=accepted_count,
        completed=len(completed_rows),
    )
    trust_history = _build_trust_history(trust)

    gcf = service.get_gcf_snapshot()
    gcf_allocation = gcf.get("allocation_channels", [])

    return {
        "member_id": actor_id,
        "display_name": display_name or actor_id.replace("-", " ").title(),
        "trust_score": trust_score,
        "missions_completed": len(completed_rows),
        "active_bids": active_bids,
        "circles_joined": sorted(circles_joined),
        "bid_rows": bid_rows,
        "completed_rows": completed_rows,
        "trust_history": trust_history,
        "reward_flow": reward_flow,
        "gcf_allocation": gcf_allocation,
        "gcf_epoch": gcf.get("epoch_label", _epoch_label(datetime.now(timezone.utc))),
        "gcf_allocation_index": int(gcf.get("allocation_index", 0)),
    }


def _fetch_all_listings(service: GenesisService) -> list[MarketListing]:
    result = service.search_listings(limit=SCAN_LIMIT)
    if not result.success:
        return []
    listings: list[MarketListing] = []
    for item in result.data.get("listings", []):
        listing_id = str(item.get("listing_id", "")).strip()
        if not listing_id:
            continue
        listing = service.get_listing(listing_id)
        if listing is not None:
            listings.append(listing)
    return listings


def _latest_bid(bids: list[Bid]) -> Bid:
    def _stamp(bid: Bid) -> datetime:
        return bid.submitted_utc or datetime.min.replace(tzinfo=timezone.utc)

    return sorted(bids, key=_stamp, reverse=True)[0]


def _completed_row_for_listing(
    service: GenesisService,
    listing: MarketListing,
    actor_id: str,
) -> dict[str, Any] | None:
    if listing.allocated_worker_id != actor_id:
        return None
    if not listing.allocated_mission_id:
        return None
    mission = service.get_mission(listing.allocated_mission_id)
    if mission is None:
        return None
    if mission.state not in {MissionState.REVIEW_COMPLETE, MissionState.APPROVED}:
        return None
    return {
        "mission_id": mission.mission_id,
        "mission_title": mission.mission_title,
        "circle_name": _circle_name_from_tags(listing.domain_tags),
        "completion_note": _completion_note(mission.state),
        "evidence_ref": f"audit-{mission.mission_id[:20]}",
    }


def _completion_note(state: MissionState) -> str:
    if state == MissionState.APPROVED:
        return "Approved after independent review; settlement path unlocked."
    return "Review complete; awaiting final mission closure step."


def _circle_name_from_tags(domain_tags: list[str]) -> str:
    tags = [str(tag).strip().lower() for tag in domain_tags if str(tag).strip()]
    if not tags:
        return "General Operations Circle"
    if "healthcare" in tags:
        return "Public Health Circle"
    if "transport" in tags or "data-analysis" in tags:
        return "Civic QA Lab"
    if "environment" in tags:
        return "Water Infrastructure Circle"
    if "education" in tags:
        return "Education and Skills Circle"
    if "audit" in tags:
        return "Governance and Justice Circle"
    return "Cross-Domain Circle"


def _bid_status_label(bid_state: BidState, listing_state: ListingState) -> str:
    if bid_state == BidState.ACCEPTED:
        if listing_state in {ListingState.ALLOCATED, ListingState.CLOSED}:
            return "Allocated"
        return "Shortlisted"
    if bid_state == BidState.REJECTED:
        return "Not selected"
    if bid_state == BidState.WITHDRAWN:
        return "Withdrawn"
    if listing_state in {ListingState.EVALUATING, ListingState.ALLOCATED}:
        return "Under listing review"
    return "Submitted"


def _next_gate(bid_state: BidState, listing_state: ListingState) -> str:
    if bid_state == BidState.REJECTED:
        return "Bid closed for this cycle."
    if bid_state == BidState.WITHDRAWN:
        return "Re-apply to another open mission."
    if bid_state == BidState.ACCEPTED and listing_state in {ListingState.ALLOCATED, ListingState.CLOSED}:
        return "Mission workflow in progress or settled."
    if bid_state == BidState.ACCEPTED:
        return "Awaiting allocation lock and escrow checks."
    if listing_state == ListingState.EVALUATING:
        return "Composite scoring and conflict checks running."
    if listing_state == ListingState.ACCEPTING_BIDS:
        return "Shortlisting window remains open."
    return "Waiting for listing progression."


def _build_reward_flow(submitted: int, accepted: int, completed: int) -> list[dict[str, Any]]:
    signals = [
        ("Mission bid participation", submitted, "Bids submitted into active mission lanes."),
        ("Selection and allocation", accepted, "Bids accepted into allocation pathways."),
        ("Completed outcomes", completed, "Work that reached review-complete or approved state."),
    ]
    total = sum(weight for _, weight, _ in signals)
    if total <= 0:
        return [{
            "channel": "Mission participation",
            "share": None,
            "measurable": False,
            "note": "No mission bids recorded for this member yet. Flow percentages appear after first measurable activity.",
        }]

    rows: list[dict[str, Any]] = []
    running = 0
    for idx, (name, weight, note) in enumerate(signals):
        if weight <= 0:
            continue
        if idx == len(signals) - 1:
            share = max(0, 100 - running)
        else:
            share = int((Decimal(weight) * Decimal(100) / Decimal(total)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP,
            ))
            running += share
        rows.append({
            "channel": name,
            "share": share,
            "measurable": True,
            "note": note,
        })

    # Guard against edge-case rounding gaps when earlier zero-weight rows are skipped.
    if rows:
        remainder = 100 - sum(int(row["share"]) for row in rows)
        rows[-1]["share"] = int(rows[-1]["share"]) + remainder
    return rows


def _build_trust_history(trust) -> list[dict[str, Any]]:
    if trust is None:
        return []
    score = int(round(float(trust.score) * 1000))
    quality = int(round(float(trust.quality) * 100))
    reliability = int(round(float(trust.reliability) * 100))
    volume = int(round(float(trust.volume) * 100))
    effort = int(round(float(trust.effort) * 100))
    return [
        {
            "period": "Current",
            "score": score,
            "reason": (
                "Live score from service state "
                f"(quality {quality}%, reliability {reliability}%, volume {volume}%, effort {effort}%)."
            ),
        },
    ]


def _epoch_label(now: datetime) -> str:
    quarter = ((now.month - 1) // 3) + 1
    return f"{now.year}-Q{quarter}"
