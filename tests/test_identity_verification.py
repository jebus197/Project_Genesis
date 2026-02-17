"""Tests for identity verification framework (Phase C-2).

Covers the full lifecycle: request → complete → lapse → flag,
high-stakes gate checks, batch expiry scanning, persistence
round-trip, and invariant checks against the executable config.
"""

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from genesis.models.trust import ActorKind
from genesis.persistence.event_log import EventLog, EventKind
from genesis.persistence.state_store import StateStore
from genesis.policy.resolver import PolicyResolver
from genesis.review.roster import ActorStatus, IdentityVerificationStatus
from genesis.service import GenesisService


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _make_service(event_log=None, state_store=None):
    resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
    return GenesisService(resolver, event_log=event_log, state_store=state_store)


def _setup_identity_scenario(service):
    """Open epoch, register a human and a machine, return their IDs."""
    service.open_epoch("test-epoch")

    result = service.register_human(
        actor_id="HUMAN-001", region="EU", organization="Org",
    )
    assert result.success, f"Human registration failed: {result.errors}"

    result = service.register_machine(
        actor_id="BOT-001",
        operator_id="HUMAN-001",
        region="EU",
        organization="Org",
        model_family="gpt-4",
        method_type="reasoning_model",
        initial_trust=0.5,
    )
    assert result.success, f"Machine registration failed: {result.errors}"

    return {"human": "HUMAN-001", "bot": "BOT-001"}


class TestIdentityVerification:
    """Prove identity verification lifecycle, gate checks, and persistence."""

    # ------------------------------------------------------------------
    # 1. Request verification — UNVERIFIED → PENDING
    # ------------------------------------------------------------------

    def test_request_verification_unverified(self) -> None:
        """UNVERIFIED actor can request verification → PENDING."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_identity_scenario(svc)

        # Pre-condition: default is UNVERIFIED
        entry = svc._roster.get(ids["human"])
        assert entry.identity_status == IdentityVerificationStatus.UNVERIFIED

        result = svc.request_verification(ids["human"])
        assert result.success

        entry = svc._roster.get(ids["human"])
        assert entry.identity_status == IdentityVerificationStatus.PENDING

        # Event emitted
        events = event_log.events(kind=EventKind.IDENTITY_VERIFICATION_REQUESTED)
        assert len(events) >= 1
        assert events[-1].actor_id == ids["human"]

    # ------------------------------------------------------------------
    # 2. Request verification — LAPSED → PENDING
    # ------------------------------------------------------------------

    def test_request_verification_lapsed(self) -> None:
        """LAPSED actor can request verification → PENDING."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_identity_scenario(svc)

        entry = svc._roster.get(ids["human"])
        entry.identity_status = IdentityVerificationStatus.LAPSED

        result = svc.request_verification(ids["human"])
        assert result.success

        entry = svc._roster.get(ids["human"])
        assert entry.identity_status == IdentityVerificationStatus.PENDING

    # ------------------------------------------------------------------
    # 3. Request verification — already PENDING fails
    # ------------------------------------------------------------------

    def test_request_verification_already_pending(self) -> None:
        """PENDING actor cannot request verification again."""
        svc = _make_service(event_log=EventLog())
        ids = _setup_identity_scenario(svc)

        entry = svc._roster.get(ids["human"])
        entry.identity_status = IdentityVerificationStatus.PENDING

        result = svc.request_verification(ids["human"])
        assert not result.success

    # ------------------------------------------------------------------
    # 4. Request verification — already VERIFIED fails
    # ------------------------------------------------------------------

    def test_request_verification_already_verified(self) -> None:
        """VERIFIED actor cannot request verification again."""
        svc = _make_service(event_log=EventLog())
        ids = _setup_identity_scenario(svc)

        entry = svc._roster.get(ids["human"])
        entry.identity_status = IdentityVerificationStatus.VERIFIED

        result = svc.request_verification(ids["human"])
        assert not result.success

    # ------------------------------------------------------------------
    # 5. Request verification — FLAGGED fails
    # ------------------------------------------------------------------

    def test_request_verification_flagged(self) -> None:
        """FLAGGED actor cannot request verification."""
        svc = _make_service(event_log=EventLog())
        ids = _setup_identity_scenario(svc)

        entry = svc._roster.get(ids["human"])
        entry.identity_status = IdentityVerificationStatus.FLAGGED

        result = svc.request_verification(ids["human"])
        assert not result.success

    # ------------------------------------------------------------------
    # 6. Request verification — unknown actor fails
    # ------------------------------------------------------------------

    def test_request_verification_not_found(self) -> None:
        """Unknown actor_id returns failure."""
        svc = _make_service(event_log=EventLog())
        _setup_identity_scenario(svc)

        result = svc.request_verification("GHOST-999")
        assert not result.success
        assert "not found" in result.errors[0].lower()

    # ------------------------------------------------------------------
    # 7. Complete verification — PENDING → VERIFIED
    # ------------------------------------------------------------------

    def test_complete_verification(self) -> None:
        """Request then complete verification with method='liveness_3d'."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_identity_scenario(svc)

        svc.request_verification(ids["human"])
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = svc.complete_verification(ids["human"], method="liveness_3d", now=now)
        assert result.success

        entry = svc._roster.get(ids["human"])
        assert entry.identity_status == IdentityVerificationStatus.VERIFIED
        assert entry.identity_verified_utc == now
        assert entry.identity_expires_utc == now + timedelta(days=365)
        assert entry.identity_method == "liveness_3d"

        # IDENTITY_VERIFIED event emitted
        verified_events = event_log.events(kind=EventKind.IDENTITY_VERIFIED)
        assert len(verified_events) >= 1
        assert verified_events[-1].actor_id == ids["human"]
        assert verified_events[-1].payload["method"] == "liveness_3d"

    # ------------------------------------------------------------------
    # 8. Complete verification — not PENDING fails
    # ------------------------------------------------------------------

    def test_complete_verification_not_pending(self) -> None:
        """Cannot complete verification on UNVERIFIED actor."""
        svc = _make_service(event_log=EventLog())
        ids = _setup_identity_scenario(svc)

        # Actor is UNVERIFIED (never requested)
        result = svc.complete_verification(ids["human"], method="liveness_3d")
        assert not result.success
        assert "PENDING" in result.errors[0]

    # ------------------------------------------------------------------
    # 9. Lapse verification — VERIFIED → LAPSED
    # ------------------------------------------------------------------

    def test_lapse_verification(self) -> None:
        """Complete verification then lapse it."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_identity_scenario(svc)

        svc.request_verification(ids["human"])
        svc.complete_verification(ids["human"], method="liveness_3d")

        result = svc.lapse_verification(ids["human"])
        assert result.success

        entry = svc._roster.get(ids["human"])
        assert entry.identity_status == IdentityVerificationStatus.LAPSED

        # IDENTITY_LAPSED event emitted
        lapsed_events = event_log.events(kind=EventKind.IDENTITY_LAPSED)
        assert len(lapsed_events) >= 1
        assert lapsed_events[-1].actor_id == ids["human"]

    # ------------------------------------------------------------------
    # 10. Lapse not verified — fails
    # ------------------------------------------------------------------

    def test_lapse_not_verified(self) -> None:
        """Cannot lapse a PENDING actor."""
        svc = _make_service(event_log=EventLog())
        ids = _setup_identity_scenario(svc)

        entry = svc._roster.get(ids["human"])
        entry.identity_status = IdentityVerificationStatus.PENDING

        result = svc.lapse_verification(ids["human"])
        assert not result.success

    # ------------------------------------------------------------------
    # 11. Flag identity — any → FLAGGED
    # ------------------------------------------------------------------

    def test_flag_identity(self) -> None:
        """Flag any actor, verify FLAGGED status and event."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_identity_scenario(svc)

        result = svc.flag_identity(ids["human"], reason="Suspicious activity")
        assert result.success

        entry = svc._roster.get(ids["human"])
        assert entry.identity_status == IdentityVerificationStatus.FLAGGED

        # IDENTITY_FLAGGED event with reason
        flagged_events = event_log.events(kind=EventKind.IDENTITY_FLAGGED)
        assert len(flagged_events) >= 1
        assert flagged_events[-1].payload["reason"] == "Suspicious activity"

    # ------------------------------------------------------------------
    # 12. Flag from VERIFIED
    # ------------------------------------------------------------------

    def test_flag_from_verified(self) -> None:
        """Verify then flag — status becomes FLAGGED."""
        svc = _make_service(event_log=EventLog())
        ids = _setup_identity_scenario(svc)

        svc.request_verification(ids["human"])
        svc.complete_verification(ids["human"], method="liveness_3d")

        entry = svc._roster.get(ids["human"])
        assert entry.identity_status == IdentityVerificationStatus.VERIFIED

        result = svc.flag_identity(ids["human"], reason="Post-verification concern")
        assert result.success

        entry = svc._roster.get(ids["human"])
        assert entry.identity_status == IdentityVerificationStatus.FLAGGED

    # ------------------------------------------------------------------
    # 13. Flag unknown actor fails
    # ------------------------------------------------------------------

    def test_flag_not_found(self) -> None:
        """Flag unknown actor returns failure."""
        svc = _make_service(event_log=EventLog())
        _setup_identity_scenario(svc)

        result = svc.flag_identity("GHOST-999", reason="N/A")
        assert not result.success
        assert "not found" in result.errors[0].lower()

    # ------------------------------------------------------------------
    # 14. Check identity — action not required
    # ------------------------------------------------------------------

    def test_check_identity_not_required(self) -> None:
        """Action not in reverification_required_for → gate='not_required'."""
        svc = _make_service(event_log=EventLog())
        ids = _setup_identity_scenario(svc)

        result = svc.check_identity_for_high_stakes(
            ids["human"], action_type="some_random_action",
        )
        assert result.success
        assert result.data["gate"] == "not_required"

    # ------------------------------------------------------------------
    # 15. Check identity — verified and valid
    # ------------------------------------------------------------------

    def test_check_identity_verified_valid(self) -> None:
        """Verified actor passes gate for 'constitutional_vote'."""
        svc = _make_service(event_log=EventLog())
        ids = _setup_identity_scenario(svc)

        svc.request_verification(ids["human"])
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        svc.complete_verification(ids["human"], method="liveness_3d", now=now)

        # Check within validity window
        check_time = now + timedelta(days=30)
        result = svc.check_identity_for_high_stakes(
            ids["human"], action_type="constitutional_vote", now=check_time,
        )
        assert result.success
        assert result.data["gate"] == "verified"

    # ------------------------------------------------------------------
    # 16. Check identity — unverified blocked
    # ------------------------------------------------------------------

    def test_check_identity_unverified_blocked(self) -> None:
        """Unverified actor blocked for 'constitutional_vote'."""
        svc = _make_service(event_log=EventLog())
        ids = _setup_identity_scenario(svc)

        result = svc.check_identity_for_high_stakes(
            ids["human"], action_type="constitutional_vote",
        )
        assert not result.success
        assert "verification required" in result.errors[0].lower()

    # ------------------------------------------------------------------
    # 17. Check identity — expired triggers auto-lapse
    # ------------------------------------------------------------------

    def test_check_identity_expired_auto_lapse(self) -> None:
        """Expired verification auto-lapses and blocks high-stakes action."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        ids = _setup_identity_scenario(svc)

        svc.request_verification(ids["human"])
        verified_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        svc.complete_verification(ids["human"], method="liveness_3d", now=verified_at)

        # Check AFTER expiry (365 days + 1 day)
        future = verified_at + timedelta(days=366)
        result = svc.check_identity_for_high_stakes(
            ids["human"], action_type="constitutional_vote", now=future,
        )
        assert not result.success
        assert "expired" in result.errors[0].lower()

        # Status should now be LAPSED (auto-lapse fired)
        entry = svc._roster.get(ids["human"])
        assert entry.identity_status == IdentityVerificationStatus.LAPSED

    # ------------------------------------------------------------------
    # 18. Check identity — flagged blocked
    # ------------------------------------------------------------------

    def test_check_identity_flagged_blocked(self) -> None:
        """Flagged actor blocked for 'constitutional_vote'."""
        svc = _make_service(event_log=EventLog())
        ids = _setup_identity_scenario(svc)

        svc.flag_identity(ids["human"], reason="Under investigation")
        result = svc.check_identity_for_high_stakes(
            ids["human"], action_type="constitutional_vote",
        )
        assert not result.success
        assert "flagged" in result.errors[0].lower()

    # ------------------------------------------------------------------
    # 19. Batch check — lapse expired actors
    # ------------------------------------------------------------------

    def test_check_lapsed_identities_batch(self) -> None:
        """Verify 3 actors, expire 2, batch-lapse correctly."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        svc.open_epoch("batch-epoch")

        # Register 3 humans
        for i in range(1, 4):
            result = svc.register_human(
                actor_id=f"BATCH-H{i}", region="EU", organization="Org",
            )
            assert result.success

        verified_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Verify all 3
        for i in range(1, 4):
            svc.request_verification(f"BATCH-H{i}")
            svc.complete_verification(f"BATCH-H{i}", method="liveness_3d", now=verified_at)

        # Expire 2 of them by setting their expiry to the past
        for i in (1, 2):
            entry = svc._roster.get(f"BATCH-H{i}")
            entry.identity_expires_utc = verified_at - timedelta(days=1)

        # BATCH-H3 remains valid
        now = verified_at + timedelta(days=10)
        result = svc.check_lapsed_identities(now=now)
        assert result.success
        assert result.data["lapsed_count"] == 2
        assert set(result.data["actors"]) == {"BATCH-H1", "BATCH-H2"}

        # Confirm statuses
        assert svc._roster.get("BATCH-H1").identity_status == IdentityVerificationStatus.LAPSED
        assert svc._roster.get("BATCH-H2").identity_status == IdentityVerificationStatus.LAPSED
        assert svc._roster.get("BATCH-H3").identity_status == IdentityVerificationStatus.VERIFIED

    # ------------------------------------------------------------------
    # 20. Batch check — none expired
    # ------------------------------------------------------------------

    def test_check_lapsed_identities_none_expired(self) -> None:
        """All actors valid — 0 lapsed."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        svc.open_epoch("batch-epoch-2")

        for i in range(1, 4):
            svc.register_human(actor_id=f"VALID-H{i}", region="EU", organization="Org")

        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(1, 4):
            svc.request_verification(f"VALID-H{i}")
            svc.complete_verification(f"VALID-H{i}", method="liveness_3d", now=now)

        # Check well within validity window
        check_time = now + timedelta(days=30)
        result = svc.check_lapsed_identities(now=check_time)
        assert result.success
        assert result.data["lapsed_count"] == 0

    # ------------------------------------------------------------------
    # 21. Persistence round-trip
    # ------------------------------------------------------------------

    def test_persistence_round_trip(self, tmp_path) -> None:
        """Identity fields survive save → load cycle."""
        state_path = tmp_path / "state.json"
        store = StateStore(state_path)
        svc = _make_service(event_log=EventLog(), state_store=store)
        svc.open_epoch("persist-epoch")

        svc.register_human(actor_id="PERSIST-H1", region="EU", organization="Org")
        svc.request_verification("PERSIST-H1")

        verified_at = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        svc.complete_verification("PERSIST-H1", method="liveness", now=verified_at)

        entry = svc._roster.get("PERSIST-H1")
        assert entry.identity_status == IdentityVerificationStatus.VERIFIED
        assert entry.identity_method == "liveness"

        # Save roster explicitly
        store.save_roster(svc._roster)

        # Load into a fresh store
        store2 = StateStore(state_path)
        loaded_roster = store2.load_roster()
        loaded_entry = loaded_roster.get("PERSIST-H1")

        assert loaded_entry is not None
        assert loaded_entry.identity_status == IdentityVerificationStatus.VERIFIED
        assert loaded_entry.identity_verified_utc == verified_at
        assert loaded_entry.identity_expires_utc == verified_at + timedelta(days=365)
        assert loaded_entry.identity_method == "liveness"

    # ------------------------------------------------------------------
    # 22. Invariant checks pass with identity_verification config
    # ------------------------------------------------------------------

    def test_invariant_checks(self) -> None:
        """check_invariants.check() returns 0 — config is consistent."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from check_invariants import check
        assert check() == 0
