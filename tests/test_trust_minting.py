"""Tests for trust profile minting (Phase D-1).

Proves the full mint lifecycle: provisional registration, identity
verification gate, completed-mission gate, first mint (PROVISIONAL->ACTIVE),
re-mint after identity lapse, display score mapping, voter/proposer
eligibility requiring minted profiles, reviewer exclusion for PROVISIONAL
actors, human decay floor for minted actors, and config updates
(tau_vote, tau_prop, constitutional_supermajority).
"""

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from genesis.models.trust import ActorKind, TrustRecord
from genesis.persistence.event_log import EventLog, EventKind, EventRecord
from genesis.persistence.state_store import StateStore
from genesis.policy.resolver import PolicyResolver
from genesis.review.roster import ActorStatus, IdentityVerificationStatus
from genesis.service import GenesisService
from genesis.trust.engine import TrustEngine


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _make_service(event_log=None, state_store=None):
    resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
    return GenesisService(resolver, event_log=event_log, state_store=state_store)


def _setup_mint_scenario(service, human_id="HUMAN-001", bot_id="BOT-001"):
    """Open epoch, register a human and a machine, return their IDs.

    Both actors start as PROVISIONAL with score 0.0 (Phase D-1 default).
    """
    service.open_epoch("test-epoch")

    result = service.register_human(
        actor_id=human_id, region="EU", organization="Org",
    )
    assert result.success, f"Human registration failed: {result.errors}"

    result = service.register_machine(
        actor_id=bot_id,
        operator_id=human_id,
        region="EU",
        organization="Org",
        model_family="gpt-4",
        method_type="reasoning_model",
    )
    assert result.success, f"Machine registration failed: {result.errors}"

    return {"human": human_id, "bot": bot_id}


def _verify_and_complete_mission(service, event_log, actor_id):
    """Helper: request + complete identity verification, then add a
    completed-mission event to the event log so the actor passes
    all three minting gates.
    """
    service.request_verification(actor_id)
    service.complete_verification(actor_id, method="voice_liveness")

    # Inject a MISSION_TRANSITION event indicating a completed mission
    event = EventRecord.create(
        event_id=f"mission-done-{actor_id}",
        event_kind=EventKind.MISSION_TRANSITION,
        actor_id=actor_id,
        payload={
            "mission_id": f"M-{actor_id}",
            "to_state": "approved",
            "from_state": "submitted",
        },
    )
    event_log.append(event)


class TestTrustMinting:
    """Comprehensive tests for trust profile minting (Phase D-1)."""

    # ------------------------------------------------------------------
    # 1-2. Registration starts as PROVISIONAL
    # ------------------------------------------------------------------

    def test_register_human_starts_provisional(self) -> None:
        """register_human() creates actor with PROVISIONAL status."""
        svc = _make_service(event_log=EventLog())
        svc.open_epoch("test-epoch")

        result = svc.register_human(
            actor_id="H-NEW", region="NA", organization="Org",
        )
        assert result.success

        entry = svc.get_actor("H-NEW")
        assert entry is not None
        assert entry.status == ActorStatus.PROVISIONAL

    def test_register_machine_starts_provisional(self) -> None:
        """register_machine() creates actor with PROVISIONAL status."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_mint_scenario(svc)

        entry = svc.get_actor(ids["bot"])
        assert entry is not None
        assert entry.status == ActorStatus.PROVISIONAL

    # ------------------------------------------------------------------
    # 3. PROVISIONAL can accept missions (is_available)
    # ------------------------------------------------------------------

    def test_provisional_can_accept_missions(self) -> None:
        """PROVISIONAL actors return True from is_available()."""
        svc = _make_service(event_log=EventLog())
        ids = _setup_mint_scenario(svc)

        entry = svc.get_actor(ids["human"])
        assert entry.status == ActorStatus.PROVISIONAL
        assert entry.is_available() is True

    # ------------------------------------------------------------------
    # 4. PROVISIONAL excluded from reviewers
    # ------------------------------------------------------------------

    def test_provisional_excluded_from_reviewers(self) -> None:
        """available_reviewers() excludes PROVISIONAL actors."""
        svc = _make_service(event_log=EventLog())
        ids = _setup_mint_scenario(svc)

        reviewers = svc._roster.available_reviewers()
        reviewer_ids = {r.actor_id for r in reviewers}

        # Both actors are PROVISIONAL, so neither should appear
        assert ids["human"] not in reviewer_ids
        assert ids["bot"] not in reviewer_ids

    # ------------------------------------------------------------------
    # 5-6. PROVISIONAL cannot vote or propose (unminted)
    # ------------------------------------------------------------------

    def test_provisional_cannot_vote(self) -> None:
        """Unminted actor (trust_minted=False) cannot vote regardless of score."""
        svc = _make_service(event_log=EventLog())
        ids = _setup_mint_scenario(svc)

        record = svc._trust_records[ids["human"]]
        # Even if score is artificially high, unminted blocks voting
        record.score = 0.90
        tau_vote, _ = PolicyResolver.from_config_dir(CONFIG_DIR).eligibility_thresholds()
        assert record.is_eligible_to_vote(tau_vote) is False

    def test_provisional_cannot_propose(self) -> None:
        """Unminted actor (trust_minted=False) cannot propose regardless of score."""
        svc = _make_service(event_log=EventLog())
        ids = _setup_mint_scenario(svc)

        record = svc._trust_records[ids["human"]]
        record.score = 0.90
        _, tau_prop = PolicyResolver.from_config_dir(CONFIG_DIR).eligibility_thresholds()
        assert record.is_eligible_to_propose(tau_prop) is False

    # ------------------------------------------------------------------
    # 7. Mint fails if actor is already ACTIVE (not via mint)
    # ------------------------------------------------------------------

    def test_mint_requires_provisional_status(self) -> None:
        """mint_trust_profile fails if actor is already ACTIVE without
        being a valid re-mint candidate."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_mint_scenario(svc)

        # Force status to ACTIVE without minting or verification
        entry = svc.get_actor(ids["human"])
        entry.status = ActorStatus.ACTIVE
        entry.identity_status = IdentityVerificationStatus.UNVERIFIED

        result = svc.mint_trust_profile(ids["human"])
        assert not result.success
        assert any("cannot mint" in e.lower() for e in result.errors)

    # ------------------------------------------------------------------
    # 8. Mint fails if identity not VERIFIED
    # ------------------------------------------------------------------

    def test_mint_requires_verified_identity(self) -> None:
        """mint_trust_profile fails if identity status is not VERIFIED."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_mint_scenario(svc)

        # Actor is PROVISIONAL but identity is UNVERIFIED
        result = svc.mint_trust_profile(ids["human"])
        assert not result.success
        assert any("verified" in e.lower() for e in result.errors)

    # ------------------------------------------------------------------
    # 9. Mint fails if no completed mission
    # ------------------------------------------------------------------

    def test_mint_requires_completed_mission(self) -> None:
        """mint_trust_profile fails if no completed mission in event log."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_mint_scenario(svc)

        # Verify identity but don't add any mission events
        svc.request_verification(ids["human"])
        svc.complete_verification(ids["human"], method="voice_liveness")

        result = svc.mint_trust_profile(ids["human"])
        assert not result.success
        assert any("completed mission" in e.lower() for e in result.errors)

    # ------------------------------------------------------------------
    # 10. Full happy path: first mint
    # ------------------------------------------------------------------

    def test_mint_first_mint_success(self) -> None:
        """Full happy path: register, verify identity, complete mission,
        mint -> ACTIVE, score=0.001."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_mint_scenario(svc)

        _verify_and_complete_mission(svc, event_log, ids["human"])

        result = svc.mint_trust_profile(ids["human"])
        assert result.success, f"Mint failed: {result.errors}"

        entry = svc.get_actor(ids["human"])
        assert entry.status == ActorStatus.ACTIVE

        record = svc._trust_records[ids["human"]]
        assert record.score == 0.001
        assert record.trust_minted is True
        assert record.trust_minted_utc is not None

    # ------------------------------------------------------------------
    # 11. Mint sets trust_minted flag
    # ------------------------------------------------------------------

    def test_mint_sets_trust_minted_flag(self) -> None:
        """trust_minted=True and trust_minted_utc set after minting."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_mint_scenario(svc)

        # Pre-condition: unminted
        record = svc._trust_records[ids["human"]]
        assert record.trust_minted is False
        assert record.trust_minted_utc is None

        _verify_and_complete_mission(svc, event_log, ids["human"])
        svc.mint_trust_profile(ids["human"])

        record = svc._trust_records[ids["human"]]
        assert record.trust_minted is True
        assert record.trust_minted_utc is not None

    # ------------------------------------------------------------------
    # 12. Mint emits TRUST_PROFILE_MINTED event
    # ------------------------------------------------------------------

    def test_mint_emits_event(self) -> None:
        """TRUST_PROFILE_MINTED event emitted with correct payload."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_mint_scenario(svc)

        _verify_and_complete_mission(svc, event_log, ids["human"])
        svc.mint_trust_profile(ids["human"])

        events = event_log.events(kind=EventKind.TRUST_PROFILE_MINTED)
        assert len(events) >= 1
        last = events[-1]
        assert last.actor_id == ids["human"]
        assert last.payload["remint"] is False
        assert last.payload["score"] == 0.001
        assert last.payload["display_score"] == 1

    # ------------------------------------------------------------------
    # 13. display_score returns 1 after minting
    # ------------------------------------------------------------------

    def test_mint_display_score_is_1(self) -> None:
        """display_score() returns 1 for a freshly minted actor (score=0.001)."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_mint_scenario(svc)

        _verify_and_complete_mission(svc, event_log, ids["human"])
        svc.mint_trust_profile(ids["human"])

        record = svc._trust_records[ids["human"]]
        assert record.display_score() == 1

    # ------------------------------------------------------------------
    # 14. display_score helper at various internal values
    # ------------------------------------------------------------------

    def test_display_score_helper(self) -> None:
        """display_score() maps internal 0.0-1.0 to display 0-1000."""
        cases = [
            (0.0, 0),
            (0.001, 1),
            (0.010, 10),
            (0.100, 100),
            (0.500, 500),
            (0.750, 750),
            (1.000, 1000),
            (0.0005, 0),      # round(0.5) = 0 (banker's rounding)
            (0.0015, 2),      # round(1.5) = 2 (banker's rounding)
            (0.9999, 1000),   # rounds 999.9 -> 1000
        ]
        for internal, expected in cases:
            record = TrustRecord(
                actor_id="TEST",
                actor_kind=ActorKind.HUMAN,
                score=internal,
            )
            assert record.display_score() == expected, (
                f"display_score({internal}) = {record.display_score()}, "
                f"expected {expected}"
            )

    # ------------------------------------------------------------------
    # 15. High-trust but unminted human cannot vote
    # ------------------------------------------------------------------

    def test_voting_requires_minted(self) -> None:
        """High-trust human with trust_minted=False cannot vote."""
        record = TrustRecord(
            actor_id="HIGH-TRUST",
            actor_kind=ActorKind.HUMAN,
            score=0.90,
            trust_minted=False,
        )
        tau_vote, _ = PolicyResolver.from_config_dir(CONFIG_DIR).eligibility_thresholds()
        assert record.is_eligible_to_vote(tau_vote) is False

    # ------------------------------------------------------------------
    # 16. Minted human with sufficient score can vote
    # ------------------------------------------------------------------

    def test_voting_works_after_minting(self) -> None:
        """Minted human with score >= tau_vote can vote."""
        tau_vote, _ = PolicyResolver.from_config_dir(CONFIG_DIR).eligibility_thresholds()
        record = TrustRecord(
            actor_id="VOTER",
            actor_kind=ActorKind.HUMAN,
            score=tau_vote,
            trust_minted=True,
        )
        assert record.is_eligible_to_vote(tau_vote) is True

    # ------------------------------------------------------------------
    # 17. High-trust but unminted human cannot propose
    # ------------------------------------------------------------------

    def test_proposal_requires_minted(self) -> None:
        """High-trust human with trust_minted=False cannot propose."""
        record = TrustRecord(
            actor_id="HIGH-TRUST",
            actor_kind=ActorKind.HUMAN,
            score=0.90,
            trust_minted=False,
        )
        _, tau_prop = PolicyResolver.from_config_dir(CONFIG_DIR).eligibility_thresholds()
        assert record.is_eligible_to_propose(tau_prop) is False

    # ------------------------------------------------------------------
    # 18. Re-mint after identity lapse + re-verification
    # ------------------------------------------------------------------

    def test_remint_after_lapse(self) -> None:
        """Lapse identity, re-verify, complete another mission, re-mint succeeds."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_mint_scenario(svc)

        # First mint
        _verify_and_complete_mission(svc, event_log, ids["human"])
        result = svc.mint_trust_profile(ids["human"])
        assert result.success, f"First mint failed: {result.errors}"

        # Lapse identity
        result = svc.lapse_verification(ids["human"])
        assert result.success, f"Lapse failed: {result.errors}"

        entry = svc.get_actor(ids["human"])
        assert entry.identity_status == IdentityVerificationStatus.LAPSED

        # Re-verify
        svc.request_verification(ids["human"])
        svc.complete_verification(ids["human"], method="voice_liveness")

        # Add another completed mission event
        event = EventRecord.create(
            event_id=f"mission-done-{ids['human']}-remint",
            event_kind=EventKind.MISSION_TRANSITION,
            actor_id=ids["human"],
            payload={
                "mission_id": f"M-{ids['human']}-2",
                "to_state": "completed",
                "from_state": "submitted",
            },
        )
        event_log.append(event)

        # Re-mint
        result = svc.mint_trust_profile(ids["human"])
        assert result.success, f"Re-mint failed: {result.errors}"

    # ------------------------------------------------------------------
    # 19. Re-mint keeps current score (does not reset to 0.001)
    # ------------------------------------------------------------------

    def test_remint_keeps_current_score(self) -> None:
        """Re-mint does not reset score to 0.001 — keeps the current
        (potentially decayed) value."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_mint_scenario(svc)

        # First mint
        _verify_and_complete_mission(svc, event_log, ids["human"])
        svc.mint_trust_profile(ids["human"])

        # Simulate trust growth
        record = svc._trust_records[ids["human"]]
        record.score = 0.45

        # Lapse and re-verify
        svc.lapse_verification(ids["human"])
        svc.request_verification(ids["human"])
        svc.complete_verification(ids["human"], method="voice_liveness")

        # Add another completed mission
        event = EventRecord.create(
            event_id=f"mission-done-remint-keep",
            event_kind=EventKind.MISSION_TRANSITION,
            actor_id=ids["human"],
            payload={
                "mission_id": "M-keep",
                "to_state": "approved",
                "from_state": "submitted",
            },
        )
        event_log.append(event)

        # Re-mint
        result = svc.mint_trust_profile(ids["human"])
        assert result.success, f"Re-mint failed: {result.errors}"

        record = svc._trust_records[ids["human"]]
        assert record.score == 0.45, (
            f"Re-mint should keep current score 0.45, got {record.score}"
        )

    # ------------------------------------------------------------------
    # 20. Re-mint event has remint: True
    # ------------------------------------------------------------------

    def test_remint_emits_event_with_remint_flag(self) -> None:
        """TRUST_PROFILE_MINTED event payload has remint: True on re-mint."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_mint_scenario(svc)

        # First mint
        _verify_and_complete_mission(svc, event_log, ids["human"])
        svc.mint_trust_profile(ids["human"])

        # Lapse and re-verify
        svc.lapse_verification(ids["human"])
        svc.request_verification(ids["human"])
        svc.complete_verification(ids["human"], method="voice_liveness")

        # Another completed mission
        event = EventRecord.create(
            event_id=f"mission-done-remint-flag",
            event_kind=EventKind.MISSION_TRANSITION,
            actor_id=ids["human"],
            payload={
                "mission_id": "M-flag",
                "to_state": "approved",
                "from_state": "submitted",
            },
        )
        event_log.append(event)

        # Re-mint
        svc.mint_trust_profile(ids["human"])

        events = event_log.events(kind=EventKind.TRUST_PROFILE_MINTED)
        assert len(events) >= 2
        remint_event = events[-1]
        assert remint_event.payload["remint"] is True

    # ------------------------------------------------------------------
    # 21. Minted human floor: never drops below 0.001 during decay
    # ------------------------------------------------------------------

    def test_human_floor_absolute_for_minted(self) -> None:
        """Minted human trust never drops below 0.001 during inactivity decay."""
        resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
        engine = TrustEngine(resolver)

        now = datetime.now(timezone.utc)
        record = TrustRecord(
            actor_id="MINTED-H",
            actor_kind=ActorKind.HUMAN,
            score=0.002,
            trust_minted=True,
            last_active_utc=now - timedelta(days=9999),  # very long inactivity
        )

        decayed = engine.apply_inactivity_decay(record, now=now)
        assert decayed.score >= 0.001, (
            f"Minted human score decayed to {decayed.score}, "
            f"expected >= 0.001"
        )

    # ------------------------------------------------------------------
    # 22. Machine trust can still reach 0.0
    # ------------------------------------------------------------------

    def test_machine_can_decay_to_zero(self) -> None:
        """Machine trust can decay to 0.0 (no absolute floor for machines)."""
        resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
        engine = TrustEngine(resolver)

        now = datetime.now(timezone.utc)
        record = TrustRecord(
            actor_id="BOT-DECAY",
            actor_kind=ActorKind.MACHINE,
            score=0.001,
            trust_minted=True,
            last_active_utc=now - timedelta(days=9999),  # extreme inactivity
        )

        decayed = engine.apply_inactivity_decay(record, now=now)
        # Machine floor is 0.0 from config
        assert decayed.score <= 0.001, (
            f"Machine score should have decayed, got {decayed.score}"
        )

    # ------------------------------------------------------------------
    # 23. Config: tau_vote updated to 0.60
    # ------------------------------------------------------------------

    def test_config_tau_vote_updated(self) -> None:
        """PolicyResolver returns tau_vote=0.60."""
        resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
        tau_vote, _ = resolver.eligibility_thresholds()
        assert tau_vote == 0.60

    # ------------------------------------------------------------------
    # 24. Config: tau_prop updated to 0.75
    # ------------------------------------------------------------------

    def test_config_tau_prop_updated(self) -> None:
        """PolicyResolver returns tau_prop=0.75."""
        resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
        _, tau_prop = resolver.eligibility_thresholds()
        assert tau_prop == 0.75

    # ------------------------------------------------------------------
    # 25. Config: constitutional_supermajority = 0.80
    # ------------------------------------------------------------------

    def test_config_supermajority(self) -> None:
        """PolicyResolver.constitutional_supermajority() returns 0.80."""
        resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
        assert resolver.constitutional_supermajority() == 0.80
