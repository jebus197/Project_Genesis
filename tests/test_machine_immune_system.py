"""Tests for the machine immune system (Phase C-1).

Proves quarantine, recertification, decommission, auto-decommission,
lineage validation, probation task counting, windowed failure counting,
and persistence round-trip for all new immune-system fields.
"""

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from genesis.models.trust import ActorKind, TrustRecord
from genesis.persistence.event_log import EventLog, EventKind
from genesis.persistence.state_store import StateStore
from genesis.policy.resolver import PolicyResolver
from genesis.review.roster import ActorStatus
from genesis.service import GenesisService
from genesis.trust.engine import TrustEngine


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _make_service(event_log=None, state_store=None):
    config_dir = Path(__file__).parent.parent / "config"
    resolver = PolicyResolver.from_config_dir(config_dir)
    return GenesisService(resolver, event_log=event_log, state_store=state_store)


def _setup_machine_scenario(service: GenesisService):
    """Register an operator, a machine, open an epoch, and register reviewers.

    Creates:
    - Human operator OP-001
    - Machine BOT-001 (registered by OP-001, gpt-4, reasoning_model)
    - Open epoch "test-epoch"
    - 5 human reviewers REV-001 through REV-005
    """
    service.open_epoch("test-epoch")

    # Register operator
    result = service.register_human(
        actor_id="OP-001", region="NA", organization="Org1",
    )
    assert result.success, f"Operator registration failed: {result.errors}"

    # Register machine
    result = service.register_machine(
        actor_id="BOT-001",
        operator_id="OP-001",
        region="NA",
        organization="Org1",
        model_family="gpt-4",
        method_type="reasoning_model",
    )
    assert result.success, f"Machine registration failed: {result.errors}"

    # Register 5 human reviewers for recertification signatures
    for i in range(1, 6):
        rid = f"REV-{i:03d}"
        result = service.register_human(
            actor_id=rid, region="NA", organization="Org1",
        )
        assert result.success, f"Reviewer {rid} registration failed: {result.errors}"


class TestMachineImmuneSystem:
    """Comprehensive tests for quarantine, recertification, decommission,
    auto-decommission, lineage validation, probation counters, windowed
    failure counting, and persistence round-trip."""

    # ------------------------------------------------------------------
    # Quarantine
    # ------------------------------------------------------------------

    def test_quarantine_emits_event(self) -> None:
        """Quarantine a machine and verify MACHINE_QUARANTINED event emitted."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        _setup_machine_scenario(svc)

        result = svc.quarantine_actor("BOT-001")
        assert result.success, f"Quarantine failed: {result.errors}"

        events = event_log.events(kind=EventKind.MACHINE_QUARANTINED)
        assert len(events) == 1
        assert events[0].actor_id == "BOT-001"

    def test_quarantine_human_no_event(self) -> None:
        """Quarantine a human actor — no MACHINE_QUARANTINED event emitted."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        _setup_machine_scenario(svc)

        result = svc.quarantine_actor("OP-001")
        assert result.success

        events = event_log.events(kind=EventKind.MACHINE_QUARANTINED)
        assert len(events) == 0

    def test_quarantine_not_found(self) -> None:
        """Quarantine an unknown actor returns error."""
        svc = _make_service()
        svc.open_epoch("test-epoch")

        result = svc.quarantine_actor("GHOST-999")
        assert not result.success
        assert any("not found" in e.lower() for e in result.errors)

    # ------------------------------------------------------------------
    # Start recertification
    # ------------------------------------------------------------------

    def test_start_recertification_happy_path(self) -> None:
        """Quarantine BOT-001, then start recertification with 5 signatures."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        _setup_machine_scenario(svc)

        svc.quarantine_actor("BOT-001")

        sigs = [f"REV-{i:03d}" for i in range(1, 6)]
        result = svc.start_recertification("BOT-001", reviewer_signatures=sigs)
        assert result.success, f"Start recertification failed: {result.errors}"

        # Status should be PROBATION
        entry = svc.get_actor("BOT-001")
        assert entry.status == ActorStatus.PROBATION

        # Event should be emitted
        events = event_log.events(kind=EventKind.MACHINE_RECERTIFICATION_STARTED)
        assert len(events) == 1

    def test_start_recertification_not_quarantined(self) -> None:
        """Try start_recertification on an ACTIVE machine — expect failure."""
        svc = _make_service()
        _setup_machine_scenario(svc)

        sigs = [f"REV-{i:03d}" for i in range(1, 6)]
        result = svc.start_recertification("BOT-001", reviewer_signatures=sigs)
        assert not result.success
        assert any("quarantined" in e.lower() for e in result.errors)

    def test_start_recertification_not_machine(self) -> None:
        """Try start_recertification on a human actor — expect failure."""
        svc = _make_service()
        _setup_machine_scenario(svc)

        svc.quarantine_actor("OP-001")
        sigs = [f"REV-{i:03d}" for i in range(1, 6)]
        result = svc.start_recertification("OP-001", reviewer_signatures=sigs)
        assert not result.success
        assert any("machine" in e.lower() for e in result.errors)

    def test_start_recertification_insufficient_signatures(self) -> None:
        """Provide only 3 signatures (need 5) — expect failure."""
        svc = _make_service()
        _setup_machine_scenario(svc)
        svc.quarantine_actor("BOT-001")

        sigs = [f"REV-{i:03d}" for i in range(1, 4)]  # only 3
        result = svc.start_recertification("BOT-001", reviewer_signatures=sigs)
        assert not result.success
        assert any("5" in e and "3" in e for e in result.errors)

    def test_start_recertification_decommissioned_blocked(self) -> None:
        """Decommission BOT-001, then try start_recertification — blocked."""
        svc = _make_service()
        _setup_machine_scenario(svc)

        svc.decommission_actor("BOT-001", reason="test decommission")

        # Force quarantine status for the test path (decommission sets it)
        entry = svc.get_actor("BOT-001")
        entry.status = ActorStatus.QUARANTINED

        sigs = [f"REV-{i:03d}" for i in range(1, 6)]
        result = svc.start_recertification("BOT-001", reviewer_signatures=sigs)
        assert not result.success
        assert any("recertified" in e.lower() or "decommissioned" in e.lower()
                    for e in result.errors)

    def test_start_recertification_self_signature_excluded(self) -> None:
        """Include BOT-001's own ID as a signature — it should be filtered out."""
        svc = _make_service()
        _setup_machine_scenario(svc)
        svc.quarantine_actor("BOT-001")

        # 4 valid reviewers + BOT-001 itself = 5 total, but only 4 valid
        sigs = ["BOT-001", "REV-001", "REV-002", "REV-003", "REV-004"]
        result = svc.start_recertification("BOT-001", reviewer_signatures=sigs)
        assert not result.success
        assert any("5" in e and "4" in e for e in result.errors)

    # ------------------------------------------------------------------
    # Complete recertification
    # ------------------------------------------------------------------

    def test_complete_recertification_success(self) -> None:
        """Full happy path: quarantine, start recertification, meet all
        thresholds, complete recertification — ACTIVE and not quarantined."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        _setup_machine_scenario(svc)

        svc.quarantine_actor("BOT-001")
        sigs = [f"REV-{i:03d}" for i in range(1, 6)]
        svc.start_recertification("BOT-001", reviewer_signatures=sigs)

        # Set probation metrics to pass thresholds
        trust = svc._trust_records["BOT-001"]
        trust.probation_tasks_completed = 100
        trust.quality = 0.96
        trust.reliability = 0.99

        result = svc.complete_recertification("BOT-001")
        assert result.success, f"Complete recertification failed: {result.errors}"

        entry = svc.get_actor("BOT-001")
        assert entry.status == ActorStatus.ACTIVE
        assert svc._trust_records["BOT-001"].quarantined is False

        events = event_log.events(kind=EventKind.MACHINE_RECERTIFICATION_COMPLETED)
        assert len(events) == 1

    def test_complete_recertification_insufficient_tasks(self) -> None:
        """probation_tasks_completed=50 (need 100) — failure with message."""
        svc = _make_service()
        _setup_machine_scenario(svc)

        svc.quarantine_actor("BOT-001")
        sigs = [f"REV-{i:03d}" for i in range(1, 6)]
        svc.start_recertification("BOT-001", reviewer_signatures=sigs)

        trust = svc._trust_records["BOT-001"]
        trust.probation_tasks_completed = 50
        trust.quality = 0.96
        trust.reliability = 0.99

        result = svc.complete_recertification("BOT-001")
        assert not result.success
        assert any("50" in e and "100" in e for e in result.errors)

    def test_complete_recertification_low_quality(self) -> None:
        """tasks=100 but quality=0.80 — failure."""
        svc = _make_service()
        _setup_machine_scenario(svc)

        svc.quarantine_actor("BOT-001")
        sigs = [f"REV-{i:03d}" for i in range(1, 6)]
        svc.start_recertification("BOT-001", reviewer_signatures=sigs)

        trust = svc._trust_records["BOT-001"]
        trust.probation_tasks_completed = 100
        trust.quality = 0.80
        trust.reliability = 0.99

        result = svc.complete_recertification("BOT-001")
        assert not result.success
        assert any("quality" in e.lower() for e in result.errors)

    def test_complete_recertification_low_reliability(self) -> None:
        """tasks=100, quality=0.96, reliability=0.90 — failure."""
        svc = _make_service()
        _setup_machine_scenario(svc)

        svc.quarantine_actor("BOT-001")
        sigs = [f"REV-{i:03d}" for i in range(1, 6)]
        svc.start_recertification("BOT-001", reviewer_signatures=sigs)

        trust = svc._trust_records["BOT-001"]
        trust.probation_tasks_completed = 100
        trust.quality = 0.96
        trust.reliability = 0.90

        result = svc.complete_recertification("BOT-001")
        assert not result.success
        assert any("reliability" in e.lower() for e in result.errors)

    def test_complete_recertification_failure_increments_counter(self) -> None:
        """Recertification failure increments recertification_failures
        and emits MACHINE_RECERTIFICATION_FAILED event."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        _setup_machine_scenario(svc)

        svc.quarantine_actor("BOT-001")
        sigs = [f"REV-{i:03d}" for i in range(1, 6)]
        svc.start_recertification("BOT-001", reviewer_signatures=sigs)

        trust = svc._trust_records["BOT-001"]
        trust.probation_tasks_completed = 50  # insufficient
        trust.quality = 0.96
        trust.reliability = 0.99
        initial_failures = trust.recertification_failures

        result = svc.complete_recertification("BOT-001")
        assert not result.success

        assert trust.recertification_failures == initial_failures + 1

        events = event_log.events(kind=EventKind.MACHINE_RECERTIFICATION_FAILED)
        assert len(events) == 1

    def test_complete_recertification_failure_triggers_decommission(self) -> None:
        """With 2 recent failures already, a third failure triggers decommission."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        _setup_machine_scenario(svc)

        svc.quarantine_actor("BOT-001")
        sigs = [f"REV-{i:03d}" for i in range(1, 6)]
        svc.start_recertification("BOT-001", reviewer_signatures=sigs)

        # Pre-load 2 recent failures within the 180-day window
        now = datetime.now(timezone.utc)
        trust = svc._trust_records["BOT-001"]
        trust.recertification_failures = 2
        trust.recertification_failure_timestamps = [
            now - timedelta(days=30),
            now - timedelta(days=15),
        ]

        trust.probation_tasks_completed = 50  # will fail
        trust.quality = 0.96
        trust.reliability = 0.99

        result = svc.complete_recertification("BOT-001")
        assert not result.success

        # Windowed count should now be 3, triggering decommission
        assert trust.decommissioned is True
        entry = svc.get_actor("BOT-001")
        assert entry.status == ActorStatus.DECOMMISSIONED

    # ------------------------------------------------------------------
    # Decommission
    # ------------------------------------------------------------------

    def test_decommission_actor(self) -> None:
        """Decommission BOT-001 — status, trust=0, event emitted."""
        event_log = EventLog()
        svc = _make_service(event_log=event_log)
        _setup_machine_scenario(svc)

        result = svc.decommission_actor("BOT-001", reason="test decommission")
        assert result.success, f"Decommission failed: {result.errors}"

        entry = svc.get_actor("BOT-001")
        assert entry.status == ActorStatus.DECOMMISSIONED

        trust = svc._trust_records["BOT-001"]
        assert trust.score == 0.0
        assert trust.decommissioned is True

        events = event_log.events(kind=EventKind.MACHINE_DECOMMISSIONED)
        assert len(events) == 1

    def test_decommission_already_decommissioned(self) -> None:
        """Decommission twice — second call returns error."""
        svc = _make_service()
        _setup_machine_scenario(svc)

        svc.decommission_actor("BOT-001", reason="first time")
        result = svc.decommission_actor("BOT-001", reason="second time")
        assert not result.success
        assert any("already decommissioned" in e.lower() for e in result.errors)

    # ------------------------------------------------------------------
    # Windowed failure counting (TrustEngine)
    # ------------------------------------------------------------------

    def test_windowed_failure_counting(self) -> None:
        """TrustEngine.count_windowed_failures with 5 timestamps,
        3 within window, 2 outside — count should be 3."""
        resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
        engine = TrustEngine(resolver)

        now = datetime.now(timezone.utc)
        record = TrustRecord(
            actor_id="BOT-X",
            actor_kind=ActorKind.MACHINE,
            score=0.3,
            recertification_failure_timestamps=[
                now - timedelta(days=365),  # outside 180-day window
                now - timedelta(days=200),  # outside 180-day window
                now - timedelta(days=90),   # inside window
                now - timedelta(days=30),   # inside window
                now - timedelta(days=5),    # inside window
            ],
        )

        count = engine.count_windowed_failures(record, now=now)
        assert count == 3

    def test_windowed_failure_old_failures_excluded(self) -> None:
        """All failures older than 180 days — count should be 0."""
        resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
        engine = TrustEngine(resolver)

        now = datetime.now(timezone.utc)
        record = TrustRecord(
            actor_id="BOT-Y",
            actor_kind=ActorKind.MACHINE,
            score=0.3,
            recertification_failure_timestamps=[
                now - timedelta(days=365),
                now - timedelta(days=250),
                now - timedelta(days=200),
            ],
        )

        count = engine.count_windowed_failures(record, now=now)
        assert count == 0

    # ------------------------------------------------------------------
    # Auto-decommission
    # ------------------------------------------------------------------

    def test_check_auto_decommission(self) -> None:
        """Quarantined machine with T=0 and last_active_utc 200 days ago
        gets auto-decommissioned."""
        svc = _make_service()
        _setup_machine_scenario(svc)

        svc.quarantine_actor("BOT-001")
        trust = svc._trust_records["BOT-001"]
        trust.score = 0.0
        trust.last_active_utc = datetime.now(timezone.utc) - timedelta(days=200)

        result = svc.check_auto_decommission()
        assert result.success

        entry = svc.get_actor("BOT-001")
        assert entry.status == ActorStatus.DECOMMISSIONED
        assert trust.decommissioned is True

    def test_check_auto_decommission_skips_recent(self) -> None:
        """Quarantined machine with last_active_utc 30 days ago — NOT decommissioned."""
        svc = _make_service()
        _setup_machine_scenario(svc)

        svc.quarantine_actor("BOT-001")
        trust = svc._trust_records["BOT-001"]
        trust.score = 0.0
        trust.last_active_utc = datetime.now(timezone.utc) - timedelta(days=30)

        result = svc.check_auto_decommission()
        assert result.success

        entry = svc.get_actor("BOT-001")
        assert entry.status == ActorStatus.QUARANTINED
        assert trust.decommissioned is False

    def test_check_auto_decommission_skips_nonzero_trust(self) -> None:
        """Quarantined machine with T=0.5 — NOT decommissioned."""
        svc = _make_service()
        _setup_machine_scenario(svc)

        svc.quarantine_actor("BOT-001")
        trust = svc._trust_records["BOT-001"]
        trust.score = 0.5
        trust.last_active_utc = datetime.now(timezone.utc) - timedelta(days=200)

        result = svc.check_auto_decommission()
        assert result.success

        entry = svc.get_actor("BOT-001")
        assert entry.status == ActorStatus.QUARANTINED
        assert trust.decommissioned is False

    # ------------------------------------------------------------------
    # Lineage validation
    # ------------------------------------------------------------------

    def test_lineage_validation_required(self) -> None:
        """Decommission BOT-001, then register a NEW machine without
        lineage_ids in metadata — expect error about lineage."""
        svc = _make_service()
        _setup_machine_scenario(svc)

        svc.decommission_actor("BOT-001", reason="lineage test")

        result = svc.register_machine(
            actor_id="BOT-002",
            operator_id="OP-001",
            region="NA",
            organization="Org1",
            model_family="gpt-4",
            method_type="reasoning_model",
        )
        assert not result.success
        assert any("lineage" in e.lower() for e in result.errors)

    def test_lineage_validation_with_declaration(self) -> None:
        """Decommission BOT-001, provide lineage_ids=["BOT-001"] — success."""
        svc = _make_service()
        _setup_machine_scenario(svc)

        svc.decommission_actor("BOT-001", reason="lineage test")

        result = svc.register_machine(
            actor_id="BOT-002",
            operator_id="OP-001",
            region="NA",
            organization="Org1",
            model_family="gpt-4",
            method_type="reasoning_model",
            machine_metadata={"lineage_ids": ["BOT-001"]},
        )
        assert result.success, f"Registration with lineage failed: {result.errors}"

    def test_lineage_validation_not_needed_no_decommissioned(self) -> None:
        """Register a new machine for operator with no decommissioned machines
        — no lineage needed."""
        svc = _make_service()
        _setup_machine_scenario(svc)

        result = svc.register_machine(
            actor_id="BOT-002",
            operator_id="OP-001",
            region="NA",
            organization="Org1",
            model_family="gpt-4",
            method_type="reasoning_model",
        )
        assert result.success, f"Registration without lineage failed: {result.errors}"

    # ------------------------------------------------------------------
    # Probation task counter
    # ------------------------------------------------------------------

    def test_probation_task_counter_increments(self) -> None:
        """Machine in PROBATION — update_trust increments probation_tasks_completed."""
        svc = _make_service()
        _setup_machine_scenario(svc)

        # Move machine to PROBATION via quarantine + start_recertification
        svc.quarantine_actor("BOT-001")
        sigs = [f"REV-{i:03d}" for i in range(1, 6)]
        svc.start_recertification("BOT-001", reviewer_signatures=sigs)

        # Confirm on probation
        entry = svc.get_actor("BOT-001")
        assert entry.status == ActorStatus.PROBATION

        initial_count = svc._trust_records["BOT-001"].probation_tasks_completed
        assert initial_count == 0  # reset by start_recertification

        result = svc.update_trust(
            actor_id="BOT-001",
            quality=0.96,
            reliability=0.99,
            volume=0.3,
            reason="probation task",
        )
        assert result.success, f"Trust update failed: {result.errors}"

        assert svc._trust_records["BOT-001"].probation_tasks_completed == initial_count + 1

    def test_probation_task_counter_no_increment_for_active(self) -> None:
        """ACTIVE machine — update_trust does NOT increment probation_tasks_completed."""
        svc = _make_service()
        _setup_machine_scenario(svc)

        initial_count = svc._trust_records["BOT-001"].probation_tasks_completed
        assert initial_count == 0

        result = svc.update_trust(
            actor_id="BOT-001",
            quality=0.96,
            reliability=0.99,
            volume=0.3,
            reason="normal task",
        )
        assert result.success, f"Trust update failed: {result.errors}"

        assert svc._trust_records["BOT-001"].probation_tasks_completed == 0

    # ------------------------------------------------------------------
    # Persistence round-trip
    # ------------------------------------------------------------------

    def test_persistence_round_trip_new_fields(self, tmp_path) -> None:
        """Save trust records with immune-system fields, load back, verify match.
        Also test roster with lineage_ids and identity fields."""
        store_path = tmp_path / "state.json"
        store = StateStore(store_path)

        # --- Trust record round-trip ---
        now = datetime.now(timezone.utc).replace(microsecond=0)
        fail_ts_1 = (now - timedelta(days=30)).replace(microsecond=0)
        fail_ts_2 = (now - timedelta(days=10)).replace(microsecond=0)

        original_trust = TrustRecord(
            actor_id="BOT-RT",
            actor_kind=ActorKind.MACHINE,
            score=0.4,
            quality=0.85,
            reliability=0.92,
            volume=0.3,
            effort=0.1,
            recertification_failure_timestamps=[fail_ts_1, fail_ts_2],
            probation_tasks_completed=50,
            last_active_utc=now,
        )
        original_trust.quarantined = True
        original_trust.decommissioned = False
        original_trust.recertification_failures = 2
        original_trust.last_recertification_utc = now

        records = {"BOT-RT": original_trust}
        store.save_trust_records(records)

        # Load into a fresh store
        store2 = StateStore(store_path)
        loaded = store2.load_trust_records()

        assert "BOT-RT" in loaded
        tr = loaded["BOT-RT"]
        assert tr.actor_id == "BOT-RT"
        assert tr.actor_kind == ActorKind.MACHINE
        assert tr.score == 0.4
        assert tr.quality == 0.85
        assert tr.reliability == 0.92
        assert tr.volume == 0.3
        assert tr.effort == 0.1
        assert tr.quarantined is True
        assert tr.decommissioned is False
        assert tr.recertification_failures == 2
        assert tr.probation_tasks_completed == 50
        assert len(tr.recertification_failure_timestamps) == 2
        assert tr.recertification_failure_timestamps[0] == fail_ts_1
        assert tr.recertification_failure_timestamps[1] == fail_ts_2
        assert tr.last_recertification_utc == now
        assert tr.last_active_utc == now

        # --- Roster round-trip with lineage_ids ---
        from genesis.review.roster import ActorRoster, RosterEntry, IdentityVerificationStatus

        roster = ActorRoster()
        roster.register(RosterEntry(
            actor_id="OP-RT",
            actor_kind=ActorKind.HUMAN,
            trust_score=0.5,
            region="EU",
            organization="OrgRT",
            model_family="human_reviewer",
            method_type="human_reviewer",
            registered_utc=now,
            identity_status=IdentityVerificationStatus.VERIFIED,
            identity_verified_utc=now,
            identity_method="passport",
        ))
        roster.register(RosterEntry(
            actor_id="BOT-RT",
            actor_kind=ActorKind.MACHINE,
            trust_score=0.4,
            region="NA",
            organization="OrgRT",
            model_family="gpt-4",
            method_type="reasoning_model",
            registered_by="OP-RT",
            registered_utc=now,
            machine_metadata={"version": "4.0"},
            lineage_ids=["BOT-OLD-1", "BOT-OLD-2"],
            identity_status=IdentityVerificationStatus.UNVERIFIED,
        ))

        store.save_roster(roster)

        store3 = StateStore(store_path)
        loaded_roster = store3.load_roster()

        bot_entry = loaded_roster.get("BOT-RT")
        assert bot_entry is not None
        assert bot_entry.lineage_ids == ["BOT-OLD-1", "BOT-OLD-2"]
        assert bot_entry.registered_by == "OP-RT"
        assert bot_entry.machine_metadata == {"version": "4.0"}
        assert bot_entry.actor_kind == ActorKind.MACHINE

        human_entry = loaded_roster.get("OP-RT")
        assert human_entry is not None
        assert human_entry.identity_status == IdentityVerificationStatus.VERIFIED
        assert human_entry.identity_verified_utc == now
        assert human_entry.identity_method == "passport"
