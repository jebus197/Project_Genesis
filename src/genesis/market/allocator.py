"""Allocation engine — scores bids and selects the best worker.

Bid scoring formula:
    bid_score = w_relevance * relevance + w_global * global_trust + w_domain * domain_trust

The engine is a pure computation layer. It takes bids with
pre-computed relevance/trust scores and returns a ranking with
an allocation result. The service layer handles side effects
(event logging, mission creation, state transitions).

Tie-breaking: higher relevance first, then earlier submission time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from genesis.models.market import (
    AllocationResult,
    Bid,
    BidState,
    MarketListing,
)
from genesis.policy.resolver import PolicyResolver


@dataclass(frozen=True)
class ScoredBid:
    """A bid with its computed composite score."""
    bid: Bid
    composite_score: float


class AllocationEngine:
    """Scores bids and selects the optimal worker for a listing.

    Usage:
        engine = AllocationEngine(resolver)
        result = engine.evaluate_and_allocate(listing, bids)
        if result is not None:
            # result.selected_bid_id, result.selected_worker_id, etc.
    """

    def __init__(self, resolver: PolicyResolver) -> None:
        self._resolver = resolver

    def score_bid(self, bid: Bid) -> float:
        """Compute composite score for a single bid.

        Uses pre-computed relevance_score, global_trust, and
        domain_trust from the bid itself (populated by the service
        layer when the bid is submitted).
        """
        w_rel, w_global, w_domain = self._allocation_weights()
        return (
            w_rel * bid.relevance_score
            + w_global * bid.global_trust
            + w_domain * bid.domain_trust
        )

    def rank_bids(self, bids: list[Bid]) -> list[ScoredBid]:
        """Score and rank all submitted bids.

        Returns bids sorted by composite score descending. Ties
        are broken by higher relevance, then earlier submission.
        """
        scored: list[ScoredBid] = []
        for bid in bids:
            if bid.state != BidState.SUBMITTED:
                continue  # Only consider active bids
            composite = self.score_bid(bid)
            scored.append(ScoredBid(bid=bid, composite_score=composite))

        # Sort: composite descending, relevance descending, time ascending
        scored.sort(
            key=lambda s: (
                -s.composite_score,
                -s.bid.relevance_score,
                s.bid.submitted_utc or datetime.min,
            )
        )
        return scored

    def evaluate_and_allocate(
        self,
        listing: MarketListing,
        bids: list[Bid],
    ) -> Optional[AllocationResult]:
        """Score all bids and produce an allocation result.

        Returns None if no valid bids exist.
        Returns AllocationResult with the selected bid and runner-ups.
        """
        ranked = self.rank_bids(bids)
        if not ranked:
            return None

        winner = ranked[0]
        runner_ups = [s.bid.bid_id for s in ranked[1:]]

        return AllocationResult(
            listing_id=listing.listing_id,
            selected_bid_id=winner.bid.bid_id,
            selected_worker_id=winner.bid.worker_id,
            composite_score=winner.composite_score,
            runner_up_bid_ids=runner_ups,
        )

    def _allocation_weights(self) -> tuple[float, float, float]:
        """Return (w_relevance, w_global_trust, w_domain_trust).

        Reads from market_policy config, falls back to skill_matching
        config, then to hardcoded defaults.
        """
        # Try market-specific weights first
        if self._resolver.has_market_config():
            config = self._resolver.market_allocation_weights()
            return (
                config.get("relevance", 0.50),
                config.get("global_trust", 0.20),
                config.get("domain_trust", 0.30),
            )
        # Fall back to skill matching config
        sm = self._resolver.skill_matching_config()
        alloc = sm.get("worker_allocation_weights", {})
        return (
            alloc.get("relevance", 0.50),
            alloc.get("global_trust", 0.20),
            alloc.get("domain_trust", 0.30),
        )
