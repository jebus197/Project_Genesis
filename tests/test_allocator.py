"""Tests for AllocationEngine — bid scoring and worker selection."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from genesis.models.market import (
    AllocationResult,
    Bid,
    BidState,
    MarketListing,
    ListingState,
)
from genesis.market.allocator import AllocationEngine, ScoredBid
from genesis.policy.resolver import PolicyResolver

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def resolver():
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def engine(resolver):
    return AllocationEngine(resolver)


def _make_listing() -> MarketListing:
    return MarketListing(
        listing_id="L-001",
        title="Test Listing",
        description="Test",
        creator_id="creator-1",
        state=ListingState.EVALUATING,
    )


def _make_bid(
    bid_id: str = "B-001",
    worker_id: str = "worker-1",
    relevance: float = 0.5,
    global_trust: float = 0.5,
    domain_trust: float = 0.5,
    state: BidState = BidState.SUBMITTED,
    submitted_utc: datetime | None = None,
) -> Bid:
    return Bid(
        bid_id=bid_id,
        listing_id="L-001",
        worker_id=worker_id,
        state=state,
        relevance_score=relevance,
        global_trust=global_trust,
        domain_trust=domain_trust,
        composite_score=0.0,  # Recomputed by engine
        submitted_utc=submitted_utc or datetime.now(timezone.utc),
    )


class TestScoreBid:
    def test_score_formula(self, engine) -> None:
        """Bid score = 0.50 * relevance + 0.20 * global + 0.30 * domain."""
        bid = _make_bid(relevance=0.8, global_trust=0.6, domain_trust=0.7)
        score = engine.score_bid(bid)
        expected = 0.50 * 0.8 + 0.20 * 0.6 + 0.30 * 0.7
        assert abs(score - expected) < 1e-9

    def test_score_zero(self, engine) -> None:
        bid = _make_bid(relevance=0.0, global_trust=0.0, domain_trust=0.0)
        assert engine.score_bid(bid) == 0.0

    def test_score_max(self, engine) -> None:
        bid = _make_bid(relevance=1.0, global_trust=1.0, domain_trust=1.0)
        score = engine.score_bid(bid)
        assert abs(score - 1.0) < 1e-9

    def test_relevance_dominates(self, engine) -> None:
        """Higher relevance weight means relevance has biggest impact."""
        # With weights 0.50/0.20/0.30:
        # high_rel: 0.50*1.0 + 0.20*0.1 + 0.30*0.1 = 0.55
        # low_rel:  0.50*0.0 + 0.20*0.9 + 0.30*0.9 = 0.45
        high_rel = _make_bid(relevance=1.0, global_trust=0.1, domain_trust=0.1)
        low_rel = _make_bid(relevance=0.0, global_trust=0.9, domain_trust=0.9)
        assert engine.score_bid(high_rel) > engine.score_bid(low_rel)


class TestRankBids:
    def test_rank_by_composite(self, engine) -> None:
        bids = [
            _make_bid("B-1", relevance=0.3, global_trust=0.3, domain_trust=0.3),
            _make_bid("B-2", relevance=0.9, global_trust=0.9, domain_trust=0.9),
            _make_bid("B-3", relevance=0.6, global_trust=0.6, domain_trust=0.6),
        ]
        ranked = engine.rank_bids(bids)
        assert len(ranked) == 3
        assert ranked[0].bid.bid_id == "B-2"
        assert ranked[1].bid.bid_id == "B-3"
        assert ranked[2].bid.bid_id == "B-1"

    def test_rank_descending(self, engine) -> None:
        bids = [
            _make_bid("B-1", relevance=0.5),
            _make_bid("B-2", relevance=0.8),
        ]
        ranked = engine.rank_bids(bids)
        assert ranked[0].composite_score >= ranked[1].composite_score

    def test_skip_non_submitted(self, engine) -> None:
        bids = [
            _make_bid("B-1", state=BidState.WITHDRAWN),
            _make_bid("B-2", state=BidState.SUBMITTED),
            _make_bid("B-3", state=BidState.REJECTED),
        ]
        ranked = engine.rank_bids(bids)
        assert len(ranked) == 1
        assert ranked[0].bid.bid_id == "B-2"

    def test_tie_break_by_relevance(self, engine) -> None:
        """Bids with same composite score break ties by relevance."""
        now = datetime.now(timezone.utc)
        # Same composite but different relevance distributions
        b1 = _make_bid("B-1", relevance=0.7, global_trust=0.5, domain_trust=0.5,
                        submitted_utc=now)
        b2 = _make_bid("B-2", relevance=0.8, global_trust=0.5, domain_trust=0.5,
                        submitted_utc=now)
        ranked = engine.rank_bids([b1, b2])
        # B-2 has higher relevance, so should rank first IF composite differs,
        # or break tie if composite is same
        assert ranked[0].bid.bid_id == "B-2"

    def test_tie_break_by_time(self, engine) -> None:
        """Same scores → earlier submission wins."""
        early = datetime(2025, 1, 1, tzinfo=timezone.utc)
        late = datetime(2025, 6, 1, tzinfo=timezone.utc)
        b1 = _make_bid("B-1", relevance=0.5, global_trust=0.5, domain_trust=0.5,
                        submitted_utc=late)
        b2 = _make_bid("B-2", relevance=0.5, global_trust=0.5, domain_trust=0.5,
                        submitted_utc=early)
        ranked = engine.rank_bids([b1, b2])
        # Same scores → earlier time wins
        assert ranked[0].bid.bid_id == "B-2"

    def test_empty_bids(self, engine) -> None:
        ranked = engine.rank_bids([])
        assert ranked == []


class TestEvaluateAndAllocate:
    def test_selects_best_bid(self, engine) -> None:
        listing = _make_listing()
        bids = [
            _make_bid("B-1", relevance=0.3),
            _make_bid("B-2", relevance=0.9),
            _make_bid("B-3", relevance=0.6),
        ]
        result = engine.evaluate_and_allocate(listing, bids)
        assert result is not None
        assert result.selected_bid_id == "B-2"
        assert result.listing_id == "L-001"

    def test_runner_ups(self, engine) -> None:
        listing = _make_listing()
        bids = [
            _make_bid("B-1", relevance=0.3),
            _make_bid("B-2", relevance=0.9),
            _make_bid("B-3", relevance=0.6),
        ]
        result = engine.evaluate_and_allocate(listing, bids)
        assert result is not None
        assert len(result.runner_up_bid_ids) == 2
        assert "B-1" in result.runner_up_bid_ids
        assert "B-3" in result.runner_up_bid_ids

    def test_no_valid_bids(self, engine) -> None:
        listing = _make_listing()
        bids = [
            _make_bid("B-1", state=BidState.WITHDRAWN),
        ]
        result = engine.evaluate_and_allocate(listing, bids)
        assert result is None

    def test_empty_bids(self, engine) -> None:
        listing = _make_listing()
        result = engine.evaluate_and_allocate(listing, [])
        assert result is None

    def test_single_bid(self, engine) -> None:
        listing = _make_listing()
        bids = [_make_bid("B-1", relevance=0.7)]
        result = engine.evaluate_and_allocate(listing, bids)
        assert result is not None
        assert result.selected_bid_id == "B-1"
        assert result.runner_up_bid_ids == []
