"""CX review regression tests — Phase F findings (2026-02-20).

P1-1: Autonomous clearance evaluation crashed when machine had domain trust
      (dict key iteration instead of keyed lookup). Fixed in service.py:9762.

P1-2: Tier-3 prerequisite check crashed on active autonomous clearance
      (referenced nonexistent created_utc). Fixed in service.py:10030.

P2:   Duplicate concurrent renewal guard was missing in domain_expert.py.
      renew_clearance() now rejects if a PENDING renewal already exists
      for the same (machine_id, org_id, domain, level) tuple.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from genesis.governance.domain_expert import (
    ClearanceLevel,
    DomainClearanceStatus,
    DomainExpertEngine,
)
from genesis.models.domain_trust import DomainTrustScore
from genesis.models.trust import ActorKind
from genesis.persistence.event_log import EventLog
from genesis.policy.resolver import PolicyResolver
from genesis.service import GenesisService

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _now() -> datetime:
    return datetime(2026, 2, 20, 12, 0, 0, tzinfo=timezone.utc)


def _make_service() -> GenesisService:
    """Service with enough actors for autonomous clearance quorum (5)."""
    resolver = PolicyResolver.from_config_dir(CONFIG_DIR)
    svc = GenesisService(resolver, event_log=EventLog())
    svc.open_epoch()
    for i in range(1, 8):
        region = ["eu", "us", "asia", "af"][i % 4]
        org = ["acme", "beta", "gamma", "delta"][i % 4]
        svc.register_actor(
            f"human-{i}", ActorKind.HUMAN, region, org, initial_trust=0.65,
        )
    svc.register_machine(
        "bot-1", operator_id="human-1", region="eu", organization="acme",
        model_family="gpt", method_type="reasoning_model",
    )
    # Give humans domain trust in "engineering" for clearance voting
    for i in range(1, 8):
        trust = svc._trust_records.get(f"human-{i}")
        if trust is not None:
            trust.domain_scores["engineering"] = DomainTrustScore(
                domain="engineering", score=0.80,
            )
    return svc


def _activate_autonomous_clearance(svc: GenesisService) -> str:
    """Nominate and approve an autonomous clearance for bot-1, return clearance_id."""
    nom = svc.nominate_for_clearance(
        "bot-1", "acme", "engineering", "human-1",
        level="autonomous",
    )
    cid = nom.data["clearance_id"]
    # Vote with 5 approvals (autonomous quorum)
    for i in range(1, 6):
        svc._domain_expert_engine.vote_on_clearance(
            cid, f"human-{i}", 0.80, True, "Approved", now=_now(),
        )
    svc._domain_expert_engine.evaluate_clearance(cid, 0.80, now=_now())
    c = svc._domain_expert_engine.get_clearance(cid)
    assert c.status == DomainClearanceStatus.ACTIVE
    return cid


class TestP1AutonomousClearanceEvaluation:
    """P1-1: evaluate_clearance must not crash when machine has domain trust.

    Before fix: iterating dict keys as objects caused AttributeError.
    After fix: direct keyed lookup via domain_scores.get().
    """

    def test_evaluate_autonomous_with_machine_domain_trust(self) -> None:
        """Autonomous clearance evaluation succeeds when machine has
        domain_scores populated — the exact scenario that crashed."""
        svc = _make_service()

        # Give the MACHINE domain trust (this is what triggers the bug path)
        machine_trust = svc._trust_records.get("bot-1")
        assert machine_trust is not None
        machine_trust.domain_scores["engineering"] = DomainTrustScore(
            domain="engineering", score=0.75,
        )

        # Nominate for autonomous clearance
        nom = svc.nominate_for_clearance(
            "bot-1", "acme", "engineering", "human-1",
            level="autonomous",
        )
        cid = nom.data["clearance_id"]

        # Vote with 5 approvals
        for i in range(1, 6):
            svc._domain_expert_engine.vote_on_clearance(
                cid, f"human-{i}", 0.80, True, "Approved", now=_now(),
            )

        # This is the call that crashed before the fix
        result = svc.evaluate_clearance(cid)
        assert result.success


class TestP1Tier3PrerequisiteTimestamp:
    """P1-2: check_tier3_prerequisites must not crash on active autonomous clearance.

    Before fix: referenced tier2_clearance.created_utc (nonexistent field).
    After fix: uses approved_utc (fallback nominated_utc).
    """

    def test_tier3_prerequisites_with_active_autonomous(self) -> None:
        """Tier-3 prerequisite check succeeds when active autonomous
        clearance exists — the exact scenario that crashed."""
        svc = _make_service()

        # Give machine domain trust
        machine_trust = svc._trust_records.get("bot-1")
        machine_trust.domain_scores["engineering"] = DomainTrustScore(
            domain="engineering", score=0.80,
        )

        # Activate autonomous clearance
        _activate_autonomous_clearance(svc)

        # This is the call that crashed before the fix
        result = svc.check_tier3_prerequisites("bot-1", "engineering")
        assert result.success
        # Should report tier2 status (won't have 5 years, but must not crash)
        assert "has_5_years_tier2" in result.data
        # Active autonomous clearance means reauth chain is intact
        assert result.data["unbroken_reauth_chain"] is True


class TestP2DuplicateRenewalGuard:
    """P2: renew_clearance must reject duplicate concurrent pending renewals.

    Before fix: calling renew_clearance() twice created duplicate PENDING records.
    After fix: second call raises ValueError.
    """

    def test_second_renewal_rejected(self) -> None:
        """Second renewal on same clearance raises ValueError."""
        engine = DomainExpertEngine({
            "clearance_min_quorum": 3,
            "clearance_min_domain_trust": 0.60,
            "autonomous_min_quorum": 5,
            "autonomous_min_domain_trust": 0.70,
            "autonomous_min_machine_trust": 0.60,
            "clearance_expiry_days": 365,
        })

        # Create and activate a clearance
        now = _now()
        c = engine.nominate_for_clearance(
            "m1", "org1", "medical", "h1", now=now,
        )
        for voter in ["h1", "h2", "h3"]:
            engine.vote_on_clearance(
                c.clearance_id, voter, 0.70, True, "Good", now=now,
            )
        engine.evaluate_clearance(c.clearance_id, now=now)

        # First renewal — should succeed
        new1 = engine.renew_clearance(c.clearance_id)
        assert new1.status == DomainClearanceStatus.PENDING

        # Second renewal on the ORIGINAL clearance (now expired) —
        # should be rejected because a PENDING renewal already exists
        # for the same (machine_id, org_id, domain, level) tuple
        with pytest.raises(ValueError, match="Pending renewal already exists"):
            engine.renew_clearance(c.clearance_id)
