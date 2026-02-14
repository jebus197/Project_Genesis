"""Listing state machine — enforces valid lifecycle transitions.

Listing lifecycle:
    DRAFT → OPEN → ACCEPTING_BIDS → EVALUATING → ALLOCATED → CLOSED
    Any non-terminal state → CANCELLED

State semantics:
- DRAFT: listing created but not yet visible to workers.
- OPEN: visible to workers, bids may start arriving.
- ACCEPTING_BIDS: actively accepting bids (explicit bid window).
- EVALUATING: bid window closed, allocator is scoring bids.
- ALLOCATED: worker selected, mission created from listing.
- CLOSED: terminal — listing fulfilled or expired.
- CANCELLED: terminal — listing withdrawn by creator.

Fail-closed: invalid transitions raise or return errors. There are
no implicit transitions.
"""

from __future__ import annotations

from genesis.models.market import ListingState, MarketListing


# Valid transitions: {from_state: {allowed_to_states}}
_TRANSITIONS: dict[ListingState, set[ListingState]] = {
    ListingState.DRAFT: {ListingState.OPEN, ListingState.CANCELLED},
    ListingState.OPEN: {
        ListingState.ACCEPTING_BIDS,
        ListingState.CANCELLED,
    },
    ListingState.ACCEPTING_BIDS: {
        ListingState.EVALUATING,
        ListingState.CANCELLED,
    },
    ListingState.EVALUATING: {
        ListingState.ALLOCATED,
        ListingState.CANCELLED,
    },
    ListingState.ALLOCATED: {ListingState.CLOSED},
    # Terminal states — no outgoing transitions
    ListingState.CLOSED: set(),
    ListingState.CANCELLED: set(),
}


class ListingStateMachine:
    """Validates and applies listing state transitions.

    Pure computation: validates transitions only. Side effects (event
    logging, persistence) are handled by the service layer.
    """

    @staticmethod
    def validate_transition(
        listing: MarketListing,
        target: ListingState,
    ) -> list[str]:
        """Check if a transition is valid. Returns errors (empty = OK)."""
        current = listing.state
        allowed = _TRANSITIONS.get(current, set())

        if target not in allowed:
            allowed_str = ", ".join(s.value for s in sorted(allowed, key=lambda x: x.value))
            return [
                f"Invalid listing transition: {current.value} → {target.value}. "
                f"Allowed from {current.value}: [{allowed_str}]"
            ]
        return []

    @staticmethod
    def apply_transition(
        listing: MarketListing,
        target: ListingState,
    ) -> list[str]:
        """Validate and apply a state transition.

        Returns errors if transition is invalid. On success,
        mutates listing.state and returns empty list.
        """
        errors = ListingStateMachine.validate_transition(listing, target)
        if errors:
            return errors
        listing.state = target
        return []

    @staticmethod
    def is_terminal(state: ListingState) -> bool:
        """Check if a state is terminal (no further transitions)."""
        return state in (ListingState.CLOSED, ListingState.CANCELLED)

    @staticmethod
    def valid_transitions(state: ListingState) -> set[ListingState]:
        """Return the set of valid target states from the given state."""
        return set(_TRANSITIONS.get(state, set()))
