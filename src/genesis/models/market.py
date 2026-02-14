"""Labour market models — listings, bids, and allocation results.

The market layer sits before the mission lifecycle: creators post listings,
workers bid, the allocator selects the best match, and a mission is
auto-created from the listing.

Listing lifecycle: DRAFT → OPEN → ACCEPTING_BIDS → EVALUATING → ALLOCATED → CLOSED
Bid lifecycle: SUBMITTED → ACCEPTED / REJECTED / WITHDRAWN
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from genesis.models.skill import SkillRequirement


class ListingState(str, enum.Enum):
    """Lifecycle state of a market listing."""
    DRAFT = "draft"
    OPEN = "open"
    ACCEPTING_BIDS = "accepting_bids"
    EVALUATING = "evaluating"
    ALLOCATED = "allocated"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class BidState(str, enum.Enum):
    """Lifecycle state of a bid."""
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


@dataclass
class MarketListing:
    """A work listing posted by a mission creator.

    Describes the work to be done and the skill requirements.
    Workers browse listings and submit bids.
    """
    listing_id: str
    title: str
    description: str
    creator_id: str
    state: ListingState = ListingState.DRAFT
    skill_requirements: list[SkillRequirement] = field(default_factory=list)
    created_utc: Optional[datetime] = None
    opened_utc: Optional[datetime] = None
    allocated_utc: Optional[datetime] = None
    allocated_worker_id: Optional[str] = None
    allocated_mission_id: Optional[str] = None
    # Optional metadata for search and filtering
    domain_tags: list[str] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)


@dataclass
class Bid:
    """A worker's bid on a market listing.

    Relevance is auto-computed by the SkillMatchEngine.
    """
    bid_id: str
    listing_id: str
    worker_id: str
    state: BidState = BidState.SUBMITTED
    relevance_score: float = 0.0
    global_trust: float = 0.0
    domain_trust: float = 0.0
    composite_score: float = 0.0
    submitted_utc: Optional[datetime] = None
    notes: str = ""


@dataclass(frozen=True)
class AllocationResult:
    """Result of bid evaluation and worker allocation."""
    listing_id: str
    selected_bid_id: str
    selected_worker_id: str
    composite_score: float
    runner_up_bid_ids: list[str] = field(default_factory=list)
