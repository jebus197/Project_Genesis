"""Tests for listing state machine — lifecycle transitions."""

import pytest

from genesis.models.market import ListingState, MarketListing
from genesis.market.listing_state_machine import ListingStateMachine


def _make_listing(state: ListingState = ListingState.DRAFT) -> MarketListing:
    return MarketListing(
        listing_id="L-001",
        title="Test Listing",
        description="Test",
        creator_id="creator-1",
        state=state,
    )


class TestValidTransitions:
    def test_draft_to_open(self) -> None:
        listing = _make_listing(ListingState.DRAFT)
        errors = ListingStateMachine.validate_transition(listing, ListingState.OPEN)
        assert errors == []

    def test_draft_to_cancelled(self) -> None:
        listing = _make_listing(ListingState.DRAFT)
        errors = ListingStateMachine.validate_transition(listing, ListingState.CANCELLED)
        assert errors == []

    def test_open_to_accepting_bids(self) -> None:
        listing = _make_listing(ListingState.OPEN)
        errors = ListingStateMachine.validate_transition(listing, ListingState.ACCEPTING_BIDS)
        assert errors == []

    def test_accepting_bids_to_evaluating(self) -> None:
        listing = _make_listing(ListingState.ACCEPTING_BIDS)
        errors = ListingStateMachine.validate_transition(listing, ListingState.EVALUATING)
        assert errors == []

    def test_evaluating_to_allocated(self) -> None:
        listing = _make_listing(ListingState.EVALUATING)
        errors = ListingStateMachine.validate_transition(listing, ListingState.ALLOCATED)
        assert errors == []

    def test_allocated_to_closed(self) -> None:
        listing = _make_listing(ListingState.ALLOCATED)
        errors = ListingStateMachine.validate_transition(listing, ListingState.CLOSED)
        assert errors == []

    def test_any_non_terminal_to_cancelled(self) -> None:
        """All non-terminal states can transition to CANCELLED."""
        cancellable = [
            ListingState.DRAFT,
            ListingState.OPEN,
            ListingState.ACCEPTING_BIDS,
            ListingState.EVALUATING,
        ]
        for state in cancellable:
            listing = _make_listing(state)
            errors = ListingStateMachine.validate_transition(listing, ListingState.CANCELLED)
            assert errors == [], f"{state.value} → CANCELLED should be valid"


class TestInvalidTransitions:
    def test_draft_to_evaluating(self) -> None:
        listing = _make_listing(ListingState.DRAFT)
        errors = ListingStateMachine.validate_transition(listing, ListingState.EVALUATING)
        assert len(errors) == 1
        assert "Invalid listing transition" in errors[0]

    def test_open_to_allocated(self) -> None:
        listing = _make_listing(ListingState.OPEN)
        errors = ListingStateMachine.validate_transition(listing, ListingState.ALLOCATED)
        assert len(errors) == 1

    def test_closed_to_anything(self) -> None:
        """Terminal state CLOSED has no outgoing transitions."""
        listing = _make_listing(ListingState.CLOSED)
        for target in ListingState:
            if target == ListingState.CLOSED:
                continue
            errors = ListingStateMachine.validate_transition(listing, target)
            assert len(errors) == 1, f"CLOSED → {target.value} should be invalid"

    def test_cancelled_to_anything(self) -> None:
        """Terminal state CANCELLED has no outgoing transitions."""
        listing = _make_listing(ListingState.CANCELLED)
        for target in ListingState:
            if target == ListingState.CANCELLED:
                continue
            errors = ListingStateMachine.validate_transition(listing, target)
            assert len(errors) == 1, f"CANCELLED → {target.value} should be invalid"

    def test_allocated_to_open(self) -> None:
        listing = _make_listing(ListingState.ALLOCATED)
        errors = ListingStateMachine.validate_transition(listing, ListingState.OPEN)
        assert len(errors) == 1


class TestApplyTransition:
    def test_apply_valid_transition(self) -> None:
        listing = _make_listing(ListingState.DRAFT)
        errors = ListingStateMachine.apply_transition(listing, ListingState.OPEN)
        assert errors == []
        assert listing.state == ListingState.OPEN

    def test_apply_invalid_transition_no_mutation(self) -> None:
        listing = _make_listing(ListingState.DRAFT)
        errors = ListingStateMachine.apply_transition(listing, ListingState.ALLOCATED)
        assert len(errors) == 1
        assert listing.state == ListingState.DRAFT  # Unchanged


class TestTerminalAndValidTransitions:
    def test_is_terminal_closed(self) -> None:
        assert ListingStateMachine.is_terminal(ListingState.CLOSED)

    def test_is_terminal_cancelled(self) -> None:
        assert ListingStateMachine.is_terminal(ListingState.CANCELLED)

    def test_not_terminal_draft(self) -> None:
        assert not ListingStateMachine.is_terminal(ListingState.DRAFT)

    def test_valid_transitions_from_draft(self) -> None:
        valid = ListingStateMachine.valid_transitions(ListingState.DRAFT)
        assert valid == {ListingState.OPEN, ListingState.CANCELLED}

    def test_valid_transitions_from_closed(self) -> None:
        valid = ListingStateMachine.valid_transitions(ListingState.CLOSED)
        assert valid == set()
