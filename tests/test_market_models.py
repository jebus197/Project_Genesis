"""Tests for market data models — MarketListing, Bid, AllocationResult."""

import pytest
from datetime import datetime, timezone

from genesis.models.market import (
    AllocationResult,
    Bid,
    BidState,
    ListingState,
    MarketListing,
)
from genesis.models.skill import SkillId, SkillRequirement


class TestListingState:
    def test_all_states_exist(self) -> None:
        """All expected listing states are defined."""
        expected = {"draft", "open", "accepting_bids", "evaluating",
                    "allocated", "closed", "cancelled"}
        actual = {s.value for s in ListingState}
        assert actual == expected

    def test_string_enum(self) -> None:
        """ListingState is a string enum."""
        assert isinstance(ListingState.DRAFT, str)
        assert ListingState.DRAFT == "draft"


class TestBidState:
    def test_all_states_exist(self) -> None:
        expected = {"submitted", "accepted", "rejected", "withdrawn"}
        actual = {s.value for s in BidState}
        assert actual == expected

    def test_string_enum(self) -> None:
        assert isinstance(BidState.SUBMITTED, str)
        assert BidState.SUBMITTED == "submitted"


class TestMarketListing:
    def test_creation_defaults(self) -> None:
        """Listing has sensible defaults."""
        listing = MarketListing(
            listing_id="L-001",
            title="Test Listing",
            description="A test job listing",
            creator_id="creator-1",
        )
        assert listing.state == ListingState.DRAFT
        assert listing.skill_requirements == []
        assert listing.created_utc is None
        assert listing.opened_utc is None
        assert listing.allocated_utc is None
        assert listing.allocated_worker_id is None
        assert listing.allocated_mission_id is None
        assert listing.domain_tags == []
        assert listing.preferences == {}

    def test_creation_with_all_fields(self) -> None:
        """Listing can be created with all optional fields."""
        now = datetime.now(timezone.utc)
        req = SkillRequirement(
            skill_id=SkillId("software_engineering", "python"),
            minimum_proficiency=0.5,
        )
        listing = MarketListing(
            listing_id="L-002",
            title="Python Dev",
            description="Build a REST API",
            creator_id="creator-2",
            state=ListingState.OPEN,
            skill_requirements=[req],
            created_utc=now,
            domain_tags=["software_engineering"],
            preferences={"urgency": "high"},
        )
        assert listing.state == ListingState.OPEN
        assert len(listing.skill_requirements) == 1
        assert listing.domain_tags == ["software_engineering"]

    def test_listing_is_mutable(self) -> None:
        """Listing state can be mutated (not frozen)."""
        listing = MarketListing(
            listing_id="L-003",
            title="Test",
            description="Test",
            creator_id="creator-1",
        )
        listing.state = ListingState.OPEN
        assert listing.state == ListingState.OPEN


class TestBid:
    def test_creation_defaults(self) -> None:
        bid = Bid(
            bid_id="B-001",
            listing_id="L-001",
            worker_id="worker-1",
        )
        assert bid.state == BidState.SUBMITTED
        assert bid.relevance_score == 0.0
        assert bid.global_trust == 0.0
        assert bid.domain_trust == 0.0
        assert bid.composite_score == 0.0
        assert bid.submitted_utc is None
        assert bid.notes == ""

    def test_creation_with_scores(self) -> None:
        now = datetime.now(timezone.utc)
        bid = Bid(
            bid_id="B-002",
            listing_id="L-001",
            worker_id="worker-2",
            relevance_score=0.8,
            global_trust=0.7,
            domain_trust=0.6,
            composite_score=0.72,
            submitted_utc=now,
            notes="Experienced in this domain",
        )
        assert bid.relevance_score == 0.8
        assert bid.composite_score == 0.72
        assert bid.notes == "Experienced in this domain"


class TestAllocationResult:
    def test_creation(self) -> None:
        result = AllocationResult(
            listing_id="L-001",
            selected_bid_id="B-001",
            selected_worker_id="worker-1",
            composite_score=0.85,
        )
        assert result.listing_id == "L-001"
        assert result.runner_up_bid_ids == []

    def test_with_runner_ups(self) -> None:
        result = AllocationResult(
            listing_id="L-001",
            selected_bid_id="B-001",
            selected_worker_id="worker-1",
            composite_score=0.85,
            runner_up_bid_ids=["B-002", "B-003"],
        )
        assert len(result.runner_up_bid_ids) == 2

    def test_frozen(self) -> None:
        """AllocationResult is immutable."""
        result = AllocationResult(
            listing_id="L-001",
            selected_bid_id="B-001",
            selected_worker_id="worker-1",
            composite_score=0.85,
        )
        with pytest.raises(AttributeError):
            result.listing_id = "L-999"
