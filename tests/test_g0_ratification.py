"""Tests for G0 retroactive ratification — proves the community reviews
every provisional decision the founder made during the early period.

When Genesis moves from G0 (founder stewardship) to G1 (provisional
chambers), a 90-day clock starts. A panel of 11 randomly selected
community members reviews each G0 decision. 8 out of 11 must approve
for a decision to stand permanently. Decisions that fail or expire
are reversed — undone as if they never happened.

Design test #32: Can G0 provisional decisions survive without retroactive
ratification in G1? If yes, reject design.
Design test #61: Can a G0 provisional decision persist into G1 without
ratification vote? If yes, reject.
Design test #62: Can a lapsed G0 decision remain in effect? If yes,
reject — it must be reversed.
Design test #63: Can the 90-day ratification window be bypassed?
If yes, reject.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from typing import Any

from genesis.governance.g0_ratification import (
    G0RatificationEngine,
    G0RatificationItem,
    G0RatificationStatus,
    G0RatificationVote,
    RATIFIABLE_EVENT_KINDS,
    REVERSAL_HANDLERS,
)
from genesis.models.governance import GenesisPhase
from genesis.policy.resolver import PolicyResolver

from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def engine() -> G0RatificationEngine:
    return G0RatificationEngine(config={}, ratification_window_days=90)


def _now() -> datetime:
    return datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_eligible_voters(
    count: int,
    regions: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Create mock eligible voters with geographic diversity."""
    if regions is None:
        # Default: cycle through 4 regions for diversity
        regions = ["eu", "na", "apac", "sa"]
    voters = []
    for i in range(count):
        voters.append({
            "actor_id": f"voter_{i}",
            "region": regions[i % len(regions)],
            "organization": f"org_{i % 3}",
        })
    return voters


# ===========================================================================
# TestG0RatificationCreation
# ===========================================================================

class TestG0RatificationCreation:
    """Test submitting G0 provisional decisions for community review."""

    def test_submit_item_happy_path(self, engine: G0RatificationEngine) -> None:
        """A G0 decision can be submitted for ratification."""
        item = engine.submit_for_ratification(
            event_kind="founder_veto_exercised",
            event_id="ev_abc123",
            description="Founder vetoed proposal X during G0",
            payload={"proposal": "X", "reason": "premature"},
            now=_now(),
        )
        assert item.status == G0RatificationStatus.PENDING
        assert item.genesis_provisional is True
        assert item.event_kind == "founder_veto_exercised"
        assert item.event_id == "ev_abc123"
        assert item.description == "Founder vetoed proposal X during G0"

    def test_auto_provisional_tag(self, engine: G0RatificationEngine) -> None:
        """Every submitted item is automatically tagged as genesis_provisional."""
        item = engine.submit_for_ratification(
            event_kind="compliance_review_completed",
            event_id="ev_def456",
            description="Compliance ruling during G0",
            payload={},
            now=_now(),
        )
        assert item.genesis_provisional is True

    def test_duplicate_event_rejected(self, engine: G0RatificationEngine) -> None:
        """The same event cannot be submitted twice."""
        engine.submit_for_ratification(
            event_kind="founder_veto_exercised",
            event_id="ev_same",
            description="First submission",
            payload={},
            now=_now(),
        )
        with pytest.raises(ValueError, match="already submitted"):
            engine.submit_for_ratification(
                event_kind="founder_veto_exercised",
                event_id="ev_same",
                description="Duplicate submission",
                payload={},
                now=_now(),
            )

    def test_empty_description_rejected(self, engine: G0RatificationEngine) -> None:
        """Items must have a meaningful description."""
        with pytest.raises(ValueError, match="Description cannot be empty"):
            engine.submit_for_ratification(
                event_kind="founder_veto_exercised",
                event_id="ev_empty",
                description="",
                payload={},
                now=_now(),
            )


# ===========================================================================
# TestG0RatificationPanel
# ===========================================================================

class TestG0RatificationPanel:
    """Test panel selection for G0 ratification review."""

    def test_panel_selected_with_correct_size(
        self, engine: G0RatificationEngine,
    ) -> None:
        """Panel should be 11 members (G1 proposal chamber size)."""
        item = engine.submit_for_ratification(
            event_kind="founder_veto_exercised",
            event_id="ev_001",
            description="Test decision",
            payload={},
            now=_now(),
        )
        voters = _make_eligible_voters(20)
        panel = engine.select_panel(
            item_id=item.item_id,
            eligible_voters=voters,
            chamber_size=11,
            r_min=3,
            c_max=0.40,
            now=_now(),
        )
        assert len(panel) == 11
        assert item.status == G0RatificationStatus.PANEL_VOTING

    def test_diversity_enforced(
        self, engine: G0RatificationEngine,
    ) -> None:
        """Panel must include members from at least R_min=3 regions."""
        item = engine.submit_for_ratification(
            event_kind="founder_veto_exercised",
            event_id="ev_002",
            description="Test decision",
            payload={},
            now=_now(),
        )
        voters = _make_eligible_voters(20, regions=["eu", "na", "apac", "sa"])
        panel = engine.select_panel(
            item_id=item.item_id,
            eligible_voters=voters,
            chamber_size=11,
            r_min=3,
            c_max=0.40,
            now=_now(),
        )
        # Check that at least 3 regions are represented
        panel_regions = set()
        for pid in panel:
            for v in voters:
                if v["actor_id"] == pid:
                    panel_regions.add(v["region"])
        assert len(panel_regions) >= 3

    def test_insufficient_candidates_raises(
        self, engine: G0RatificationEngine,
    ) -> None:
        """Must raise if not enough eligible voters for the panel size."""
        item = engine.submit_for_ratification(
            event_kind="founder_veto_exercised",
            event_id="ev_003",
            description="Test decision",
            payload={},
            now=_now(),
        )
        voters = _make_eligible_voters(5)  # Only 5, need 11
        with pytest.raises(ValueError, match="Not enough eligible voters"):
            engine.select_panel(
                item_id=item.item_id,
                eligible_voters=voters,
                chamber_size=11,
                r_min=3,
                c_max=0.40,
                now=_now(),
            )


# ===========================================================================
# TestG0RatificationVoting
# ===========================================================================

class TestG0RatificationVoting:
    """Test the voting process for G0 ratification items."""

    def _setup_item_with_panel(
        self, engine: G0RatificationEngine,
    ) -> tuple[G0RatificationItem, list[dict[str, Any]]]:
        """Helper: create an item and select a panel."""
        item = engine.submit_for_ratification(
            event_kind="founder_veto_exercised",
            event_id="ev_vote_test",
            description="Veto to ratify",
            payload={"action": "block_proposal_X"},
            now=_now(),
        )
        voters = _make_eligible_voters(20)
        engine.select_panel(
            item_id=item.item_id,
            eligible_voters=voters,
            chamber_size=11,
            r_min=3,
            c_max=0.40,
            now=_now(),
        )
        return item, voters

    def test_happy_path_ratified(self, engine: G0RatificationEngine) -> None:
        """8 out of 11 YES votes = RATIFIED."""
        item, voters = self._setup_item_with_panel(engine)
        # Cast 8 YES votes
        for i, vid in enumerate(item.panel_ids[:8]):
            engine.cast_vote(
                item_id=item.item_id,
                voter_id=vid,
                vote=True,
                attestation=f"I approve decision {i}",
                region="eu",
                organization="org",
                now=_now(),
            )
        status = engine.close_voting(item.item_id, pass_threshold=8, now=_now())
        assert status == G0RatificationStatus.RATIFIED

    def test_insufficient_votes_lapsed(
        self, engine: G0RatificationEngine,
    ) -> None:
        """Fewer than 8 YES votes = LAPSED (must be reversed)."""
        item, voters = self._setup_item_with_panel(engine)
        # Cast only 5 YES votes
        for i, vid in enumerate(item.panel_ids[:5]):
            engine.cast_vote(
                item_id=item.item_id,
                voter_id=vid,
                vote=True,
                attestation=f"I approve {i}",
                region="eu",
                organization="org",
                now=_now(),
            )
        status = engine.close_voting(item.item_id, pass_threshold=8, now=_now())
        assert status == G0RatificationStatus.LAPSED

    def test_non_panel_member_rejected(
        self, engine: G0RatificationEngine,
    ) -> None:
        """Only panel members can vote."""
        item, voters = self._setup_item_with_panel(engine)
        with pytest.raises(ValueError, match="not on the panel"):
            engine.cast_vote(
                item_id=item.item_id,
                voter_id="outsider_999",
                vote=True,
                attestation="I want to vote",
                region="eu",
                organization="org",
                now=_now(),
            )

    def test_duplicate_vote_rejected(
        self, engine: G0RatificationEngine,
    ) -> None:
        """Each panel member can only vote once."""
        item, voters = self._setup_item_with_panel(engine)
        vid = item.panel_ids[0]
        engine.cast_vote(
            item_id=item.item_id,
            voter_id=vid,
            vote=True,
            attestation="First vote",
            region="eu",
            organization="org",
            now=_now(),
        )
        with pytest.raises(ValueError, match="already voted"):
            engine.cast_vote(
                item_id=item.item_id,
                voter_id=vid,
                vote=False,
                attestation="Changed my mind",
                region="eu",
                organization="org",
                now=_now(),
            )


# ===========================================================================
# TestG0RatificationDeadline
# ===========================================================================

class TestG0RatificationDeadline:
    """Test the 90-day deadline enforcement."""

    def test_deadline_not_reached_no_lapse(
        self, engine: G0RatificationEngine,
    ) -> None:
        """Items are not lapsed before the deadline."""
        item = engine.submit_for_ratification(
            event_kind="founder_veto_exercised",
            event_id="ev_deadline_1",
            description="Pre-deadline test",
            payload={},
            now=_now(),
        )
        deadline = _now() + timedelta(days=90)
        # Check 30 days in — should not lapse
        lapsed = engine.check_deadline(
            now=_now() + timedelta(days=30),
            deadline=deadline,
        )
        assert len(lapsed) == 0
        assert item.status == G0RatificationStatus.PENDING

    def test_deadline_expired_auto_lapse(
        self, engine: G0RatificationEngine,
    ) -> None:
        """Items still pending after 90 days are automatically lapsed."""
        item = engine.submit_for_ratification(
            event_kind="founder_veto_exercised",
            event_id="ev_deadline_2",
            description="Expired deadline test",
            payload={},
            now=_now(),
        )
        deadline = _now() + timedelta(days=90)
        # Check 91 days in — should lapse
        lapsed = engine.check_deadline(
            now=_now() + timedelta(days=91),
            deadline=deadline,
        )
        assert item.item_id in lapsed
        assert item.status == G0RatificationStatus.LAPSED


# ===========================================================================
# TestG0RatificationReversal
# ===========================================================================

class TestG0RatificationReversal:
    """Test the reversal mechanism for lapsed G0 decisions."""

    def test_reversal_marks_item_reversed(
        self, engine: G0RatificationEngine,
    ) -> None:
        """A lapsed item can be marked as reversed."""
        item = engine.submit_for_ratification(
            event_kind="founder_veto_exercised",
            event_id="ev_rev_1",
            description="Decision to reverse",
            payload={},
            now=_now(),
        )
        # Force lapse via deadline
        deadline = _now() + timedelta(days=90)
        engine.check_deadline(now=_now() + timedelta(days=91), deadline=deadline)
        assert item.status == G0RatificationStatus.LAPSED

        # Mark reversed
        reversed_item = engine.mark_reversed(item.item_id, now=_now())
        assert reversed_item.status == G0RatificationStatus.REVERSED

    def test_cannot_reverse_non_lapsed(
        self, engine: G0RatificationEngine,
    ) -> None:
        """Only LAPSED items can be reversed."""
        item = engine.submit_for_ratification(
            event_kind="founder_veto_exercised",
            event_id="ev_rev_2",
            description="Still pending",
            payload={},
            now=_now(),
        )
        with pytest.raises(ValueError, match="expected lapsed"):
            engine.mark_reversed(item.item_id, now=_now())

    def test_reversal_handler_lookup(self) -> None:
        """Every ratifiable event kind has a reversal handler."""
        for kind in RATIFIABLE_EVENT_KINDS:
            handler = G0RatificationEngine.get_reversal_handler(kind)
            assert handler is not None, f"No reversal handler for {kind}"
            assert handler in REVERSAL_HANDLERS.values()


# ===========================================================================
# TestG0RatificationService
# ===========================================================================

class TestG0RatificationService:
    """Test the service-layer integration for G0 ratification."""

    def _register_human(
        self,
        service: Any,
        actor_id: str,
        trust: float,
        region: str = "eu",
        org: str = "acme",
    ) -> None:
        """Register an ACTIVE human actor with given trust."""
        from genesis.review.roster import ActorKind, ActorStatus
        service.register_actor(
            actor_id=actor_id,
            actor_kind=ActorKind.HUMAN,
            initial_trust=trust,
            region=region,
            organization=org,
        )

    def test_service_round_trip(self, resolver: PolicyResolver) -> None:
        """Full round trip: start → panel → vote → close."""
        service = _make_service(resolver)

        # Register enough humans for a panel (11 needed, with diversity)
        regions = ["eu", "na", "apac", "sa"]
        for i in range(20):
            self._register_human(
                service, f"h_{i}", 0.80,
                region=regions[i % len(regions)],
                org=f"org_{i % 3}",
            )

        # Start ratification (no G0 events in log, so 0 items)
        result = service.start_g0_ratification(now=_now())
        assert result.success
        assert result.data["items_submitted"] == 0

        # Manually submit an item via the engine
        engine = service._g0_ratification_engine
        item = engine.submit_for_ratification(
            event_kind="founder_veto_exercised",
            event_id="ev_svc_001",
            description="Test veto",
            payload={},
            now=_now(),
        )

        # Open panel
        result = service.open_ratification_panel(item.item_id, now=_now())
        assert result.success
        assert result.data["panel_size"] == 11

        # Vote (8 YES)
        panel_ids = result.data["panel_ids"]
        for vid in panel_ids[:8]:
            result = service.vote_on_ratification(
                item_id=item.item_id,
                voter_id=vid,
                vote=True,
                attestation="I ratify this G0 decision",
                now=_now(),
            )
            assert result.success

        # Close
        result = service.close_ratification_item(item.item_id, now=_now())
        assert result.success
        assert result.data["status"] == "ratified"

    def test_reversal_emits_event(self, resolver: PolicyResolver) -> None:
        """Reversing a lapsed decision emits G0_DECISION_REVERSED event."""
        service = _make_service(resolver)

        # Start ratification
        service.start_g0_ratification(now=_now())
        engine = service._g0_ratification_engine

        # Submit and force lapse
        item = engine.submit_for_ratification(
            event_kind="founder_veto_exercised",
            event_id="ev_svc_002",
            description="Veto to reverse",
            payload={},
            now=_now(),
        )
        deadline = _now() + timedelta(days=90)
        engine.check_deadline(now=_now() + timedelta(days=91), deadline=deadline)
        assert item.status == G0RatificationStatus.LAPSED

        # Reverse
        result = service.reverse_lapsed_g0_decision(
            item_id=item.item_id, now=_now(),
        )
        assert result.success
        assert result.data["status"] == "reversed"
        assert result.data["reversal_handler"] == "undo_veto"


# ===========================================================================
# TestG0RatificationPersistence
# ===========================================================================

class TestG0RatificationPersistence:
    """Test round-trip persistence of ratification items."""

    def test_round_trip_save_load(self) -> None:
        """Items survive save/load cycle through G0RatificationEngine.from_records()."""
        engine = G0RatificationEngine(config={}, ratification_window_days=90)
        item = engine.submit_for_ratification(
            event_kind="founder_veto_exercised",
            event_id="ev_persist_1",
            description="Persistent veto",
            payload={"reason": "test"},
            now=_now(),
        )
        # Select panel and cast a vote
        voters = _make_eligible_voters(15)
        engine.select_panel(item.item_id, voters, 11, 3, 0.40, _now())
        engine.cast_vote(
            item.item_id, item.panel_ids[0], True,
            "I attest", "eu", "acme", _now(),
        )

        # Serialize (mimicking StateStore)
        serialized = []
        for iid, it in engine.items.items():
            votes_data = [
                {
                    "vote_id": v.vote_id,
                    "voter_id": v.voter_id,
                    "vote": v.vote,
                    "attestation": v.attestation,
                    "cast_utc": v.cast_utc.isoformat(),
                    "region": v.region,
                    "organization": v.organization,
                }
                for v in it.votes
            ]
            serialized.append({
                "item_id": it.item_id,
                "event_kind": it.event_kind,
                "event_id": it.event_id,
                "description": it.description,
                "payload": it.payload,
                "status": it.status.value,
                "created_utc": it.created_utc.isoformat() if it.created_utc else None,
                "decided_utc": it.decided_utc.isoformat() if it.decided_utc else None,
                "panel_ids": it.panel_ids,
                "votes": votes_data,
                "genesis_provisional": it.genesis_provisional,
            })

        # Restore
        restored = G0RatificationEngine.from_records(
            config={}, ratification_window_days=90, items=serialized,
        )
        restored_item = restored.get_item(item.item_id)
        assert restored_item is not None
        assert restored_item.status == G0RatificationStatus.PANEL_VOTING
        assert len(restored_item.votes) == 1
        assert restored_item.votes[0].vote is True
        assert restored_item.genesis_provisional is True


# ===========================================================================
# TestG0RatificationInvariants
# ===========================================================================

class TestG0RatificationInvariants:
    """Test that invariant checks pass for G0 ratification configuration."""

    def test_invariants_pass(self) -> None:
        """check_invariants.py should pass with current config."""
        import subprocess
        result = subprocess.run(
            ["python3", "tools/check_invariants.py"],
            capture_output=True, text=True,
            cwd="/Users/georgejackson/Developer_Projects/Project_Genesis",
        )
        assert result.returncode == 0, f"Invariants failed: {result.stdout}"

    def test_ratification_window_is_90(self, resolver: PolicyResolver) -> None:
        """G0_RATIFICATION_WINDOW_DAYS must be 90."""
        time_limits = resolver.genesis_time_limits()
        assert time_limits["G0_RATIFICATION_WINDOW_DAYS"] == 90


# ===========================================================================
# Helpers
# ===========================================================================

def _make_service(resolver: PolicyResolver) -> Any:
    """Create a minimal GenesisService for testing."""
    from genesis.service import GenesisService
    return GenesisService(resolver)
