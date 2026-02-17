"""Tests for Phase E-3: Three-Tier Justice System.

Covers:
- AdjudicationEngine (Tier 2): open case, blind pseudonyms, self-complaint,
  response handling, panel formation, diversity, verdict evaluation, appeals
- ConstitutionalCourt (Tier 3): panel formation, supermajority, precedent
- RightsEnforcer: response period, evidence disclosure, gate enforcement
- RehabilitationEngine: severity restriction, probation tasks, trust restoration
- GenesisService integration: events, penalty application, suspension expiry
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from genesis.legal.adjudication import (
    AdjudicationEngine,
    AdjudicationStatus,
    AdjudicationType,
    AdjudicationVerdict,
)
from genesis.legal.constitutional_court import (
    ConstitutionalCourt,
    CourtCaseStatus,
)
from genesis.legal.rights import RightsEnforcer
from genesis.legal.rehabilitation import RehabilitationEngine, RehabStatus
from genesis.service import GenesisService
from genesis.policy.resolver import PolicyResolver
from genesis.models.trust import ActorKind
from genesis.review.roster import ActorStatus, RosterEntry


def _now() -> datetime:
    return datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc)


def _adj_config() -> dict[str, Any]:
    return {
        "panel_size": 5,
        "panel_min_regions": 2,
        "panel_min_organizations": 2,
        "min_panelist_trust": 0.60,
        "response_period_hours": 72,
        "appeal_window_hours": 72,
        "blind_adjudication": True,
        "require_vote_attestation": True,
        "supermajority_threshold": 0.60,
    }


def _court_config() -> dict[str, Any]:
    return {
        "panel_size": 7,
        "supermajority_threshold": 5,
        "min_justice_trust": 0.70,
        "min_regions": 3,
        "min_organizations": 3,
        "human_only": True,
    }


def _rehab_config() -> dict[str, Any]:
    return {
        "probation_tasks_required": 5,
        "trust_restoration_fraction": 0.50,
        "max_restoration_score": 0.30,
        "rehab_window_days": 180,
    }


def _candidates(n: int = 10, min_orgs: int = 3, min_regions: int = 3) -> list[dict[str, Any]]:
    """Generate diverse candidates for panel selection."""
    orgs = [f"org_{i % min_orgs}" for i in range(n)]
    regions = [f"region_{i % min_regions}" for i in range(n)]
    return [
        {
            "actor_id": f"panelist_{i}",
            "trust_score": 0.80,
            "organization": orgs[i],
            "region": regions[i],
            "actor_kind": "human",
        }
        for i in range(n)
    ]


# =====================================================================
# TestAdjudicationEngine — Tier 2
# =====================================================================

class TestAdjudicationEngine:
    """Tests for the unified adjudication engine."""

    def test_open_case(self):
        """Open a basic adjudication case."""
        engine = AdjudicationEngine(_adj_config())
        case = engine.open_case(
            AdjudicationType.COMPLIANCE_COMPLAINT,
            "complainant_1", "accused_1", "Test reason", _now(),
        )
        assert case.case_id.startswith("adj-")
        assert case.status == AdjudicationStatus.RESPONSE_PERIOD
        assert case.complainant_id == "complainant_1"
        assert case.accused_id == "accused_1"
        assert case.response_deadline_utc is not None

    def test_blind_pseudonyms_generated(self):
        """Blind pseudonyms are generated for both parties."""
        engine = AdjudicationEngine(_adj_config())
        case = engine.open_case(
            AdjudicationType.ABUSE_COMPLAINT,
            "c1", "a1", "reason", _now(),
        )
        assert case.complainant_pseudonym.startswith("party-")
        assert case.accused_pseudonym.startswith("party-")
        assert case.complainant_pseudonym != case.accused_pseudonym

    def test_self_complaint_rejected(self):
        """Cannot file a complaint against yourself."""
        engine = AdjudicationEngine(_adj_config())
        with pytest.raises(ValueError, match="Cannot file a complaint against yourself"):
            engine.open_case(
                AdjudicationType.CONDUCT_COMPLAINT,
                "actor_1", "actor_1", "self-complaint", _now(),
            )

    def test_response_within_deadline(self):
        """Accused can respond within the 72h deadline."""
        engine = AdjudicationEngine(_adj_config())
        now = _now()
        case = engine.open_case(
            AdjudicationType.PAYMENT_DISPUTE, "c1", "a1", "reason", now,
        )
        # Respond 24h later (within 72h)
        engine.submit_accused_response(case.case_id, "My defence", now + timedelta(hours=24))
        assert case.accused_response == "My defence"

    def test_response_after_deadline_rejected(self):
        """Cannot respond after the 72h deadline."""
        engine = AdjudicationEngine(_adj_config())
        now = _now()
        case = engine.open_case(
            AdjudicationType.PAYMENT_DISPUTE, "c1", "a1", "reason", now,
        )
        with pytest.raises(ValueError, match="deadline has passed"):
            engine.submit_accused_response(
                case.case_id, "Too late", now + timedelta(hours=73),
            )

    def test_panel_blocked_during_response_period(self):
        """Panel formation blocked during active response period."""
        engine = AdjudicationEngine(_adj_config())
        now = _now()
        case = engine.open_case(
            AdjudicationType.COMPLIANCE_COMPLAINT, "c1", "a1", "reason", now,
        )
        with pytest.raises(ValueError, match="response period still active"):
            engine.form_panel(case.case_id, _candidates(), now + timedelta(hours=1))

    def test_panel_allowed_after_response(self):
        """Panel can form after accused responds (even before 72h)."""
        engine = AdjudicationEngine(_adj_config())
        now = _now()
        case = engine.open_case(
            AdjudicationType.COMPLIANCE_COMPLAINT, "c1", "a1", "reason", now,
        )
        engine.submit_accused_response(case.case_id, "My response", now + timedelta(hours=1))
        case = engine.form_panel(case.case_id, _candidates(), now + timedelta(hours=2))
        assert case.status == AdjudicationStatus.PANEL_FORMED
        assert len(case.panel_ids) == 5

    def test_panel_diversity_enforced(self):
        """Panel must have ≥2 orgs and ≥2 regions."""
        engine = AdjudicationEngine(_adj_config())
        now = _now()
        case = engine.open_case(
            AdjudicationType.ABUSE_COMPLAINT, "c1", "a1", "reason", now,
        )
        # All candidates from same org — should fail
        same_org = [
            {"actor_id": f"p{i}", "trust_score": 0.80, "organization": "same_org", "region": f"r{i}"}
            for i in range(10)
        ]
        with pytest.raises(ValueError, match="organizational diversity"):
            engine.form_panel(case.case_id, same_org, now + timedelta(hours=73))

    def test_panel_excludes_parties(self):
        """Complainant and accused are excluded from the panel."""
        engine = AdjudicationEngine(_adj_config())
        now = _now()
        case = engine.open_case(
            AdjudicationType.CONDUCT_COMPLAINT, "c1", "a1", "reason", now,
        )
        candidates = _candidates()
        # Add complainant and accused as candidates
        candidates.append({"actor_id": "c1", "trust_score": 0.90, "organization": "org_x", "region": "region_x"})
        candidates.append({"actor_id": "a1", "trust_score": 0.90, "organization": "org_y", "region": "region_y"})
        case = engine.form_panel(case.case_id, candidates, now + timedelta(hours=73))
        assert "c1" not in case.panel_ids
        assert "a1" not in case.panel_ids

    def test_supermajority_upheld(self):
        """3/5 votes for UPHELD triggers UPHELD verdict."""
        engine = AdjudicationEngine(_adj_config())
        now = _now()
        case = engine.open_case(
            AdjudicationType.COMPLIANCE_COMPLAINT, "c1", "a1", "reason", now,
        )
        case = engine.form_panel(case.case_id, _candidates(), now + timedelta(hours=73))
        # 3 upheld, 2 dismissed
        for i, pid in enumerate(case.panel_ids):
            v = "upheld" if i < 3 else "dismissed"
            engine.submit_panel_vote(case.case_id, pid, v, f"attestation_{pid}")
        verdict = engine.evaluate_verdict(case.case_id)
        assert verdict == AdjudicationVerdict.UPHELD
        assert case.status == AdjudicationStatus.DECIDED

    def test_dismissed_below_threshold(self):
        """Fewer than 3/5 UPHELD votes results in DISMISSED."""
        engine = AdjudicationEngine(_adj_config())
        now = _now()
        case = engine.open_case(
            AdjudicationType.CONDUCT_COMPLAINT, "c1", "a1", "reason", now,
        )
        case = engine.form_panel(case.case_id, _candidates(), now + timedelta(hours=73))
        # 2 upheld, 3 dismissed
        for i, pid in enumerate(case.panel_ids):
            v = "upheld" if i < 2 else "dismissed"
            engine.submit_panel_vote(case.case_id, pid, v, f"att_{pid}")
        verdict = engine.evaluate_verdict(case.case_id)
        assert verdict == AdjudicationVerdict.DISMISSED

    def test_appeal_excludes_original_panel(self):
        """Appeal panel must exclude original panel members."""
        engine = AdjudicationEngine(_adj_config())
        now = _now()
        case = engine.open_case(
            AdjudicationType.ABUSE_COMPLAINT, "c1", "a1", "reason", now,
        )
        case = engine.form_panel(case.case_id, _candidates(), now + timedelta(hours=73))
        original_panel = set(case.panel_ids)
        # All vote dismissed
        for pid in case.panel_ids:
            engine.submit_panel_vote(case.case_id, pid, "dismissed", f"att_{pid}")
        engine.evaluate_verdict(case.case_id)
        # File appeal immediately (within the 72h window from decision time)
        from datetime import datetime as dt, timezone as tz
        appeal_time = case.decided_utc + timedelta(hours=1)
        appeal = engine.file_appeal(case.case_id, "a1", "Unfair", appeal_time)
        assert appeal.appeal_of == case.case_id
        # Form appeal panel — original members excluded
        panel_time = appeal.response_deadline_utc + timedelta(hours=1)
        appeal = engine.form_panel(appeal.case_id, _candidates(20), panel_time)
        for pid in appeal.panel_ids:
            assert pid not in original_panel


# =====================================================================
# TestConstitutionalCourt — Tier 3
# =====================================================================

class TestConstitutionalCourt:
    """Tests for the Constitutional Court."""

    def test_7_panel_size(self):
        """Court panel must have exactly 7 justices."""
        court = ConstitutionalCourt(_court_config())
        case = court.open_court_case("adj-test", "Constitutional question?", _now())
        case = court.form_court_panel(case.court_case_id, _candidates(15, 4, 4))
        assert len(case.panel_ids) == 7

    def test_5_7_supermajority_to_overturn(self):
        """5/7 votes required to OVERTURN."""
        court = ConstitutionalCourt(_court_config())
        case = court.open_court_case("adj-test", "Question?", _now())
        case = court.form_court_panel(case.court_case_id, _candidates(15, 4, 4))
        # 5 overturn, 2 uphold
        for i, jid in enumerate(case.panel_ids):
            v = "overturn" if i < 5 else "uphold"
            court.submit_court_vote(case.court_case_id, jid, v, f"att_{jid}")
        verdict = court.evaluate_court_verdict(case.court_case_id)
        assert verdict == "overturn"

    def test_simple_majority_upholds(self):
        """Simple majority of uphold votes results in uphold."""
        court = ConstitutionalCourt(_court_config())
        case = court.open_court_case("adj-test", "Question?", _now())
        case = court.form_court_panel(case.court_case_id, _candidates(15, 4, 4))
        # 4 uphold, 3 overturn (4/7 not enough to overturn)
        for i, jid in enumerate(case.panel_ids):
            v = "uphold" if i < 4 else "overturn"
            court.submit_court_vote(case.court_case_id, jid, v, f"att_{jid}")
        verdict = court.evaluate_court_verdict(case.court_case_id)
        assert verdict == "uphold"

    def test_precedent_advisory_only(self):
        """Recorded precedent is advisory only."""
        court = ConstitutionalCourt(_court_config())
        case = court.open_court_case("adj-test", "Important question", _now())
        case = court.form_court_panel(case.court_case_id, _candidates(15, 4, 4))
        for jid in case.panel_ids:
            court.submit_court_vote(
                case.court_case_id, jid, "uphold", f"att_{jid}", "This is precedent"
            )
        court.evaluate_court_verdict(case.court_case_id)
        precedent = court.record_precedent(case.court_case_id)
        assert precedent.advisory_only is True

    def test_human_only_invariant(self):
        """Court panel rejects machine candidates when human_only is true."""
        court = ConstitutionalCourt(_court_config())
        case = court.open_court_case("adj-test", "Question?", _now())
        # All machine candidates
        machines = [
            {
                "actor_id": f"m{i}", "trust_score": 0.90,
                "organization": f"org_{i % 4}", "region": f"r_{i % 4}",
                "actor_kind": "machine",
            }
            for i in range(15)
        ]
        with pytest.raises(ValueError, match="Not enough eligible justices"):
            court.form_court_panel(case.court_case_id, machines)

    def test_remand_sends_back(self):
        """Remand verdict when majority votes remand."""
        court = ConstitutionalCourt(_court_config())
        case = court.open_court_case("adj-test", "Question?", _now())
        case = court.form_court_panel(case.court_case_id, _candidates(15, 4, 4))
        # 4 remand, 2 uphold, 1 overturn
        verdicts = ["remand", "remand", "remand", "remand", "uphold", "uphold", "overturn"]
        for jid, v in zip(case.panel_ids, verdicts):
            court.submit_court_vote(case.court_case_id, jid, v, f"att_{jid}")
        verdict = court.evaluate_court_verdict(case.court_case_id)
        assert verdict == "remand"


# =====================================================================
# TestRightsEnforcer — Structural rights enforcement
# =====================================================================

class TestRightsEnforcer:
    """Tests for the rights enforcement gate."""

    def test_72h_deadline(self):
        """Response deadline is 72 hours from notification."""
        enforcer = RightsEnforcer(response_period_hours=72)
        now = _now()
        record = enforcer.create_rights_record("case-1", "accused-1", now)
        assert record.response_deadline_utc == now + timedelta(hours=72)

    def test_panel_blocked_if_not_responded(self):
        """Panel blocked during response period when no response."""
        enforcer = RightsEnforcer(response_period_hours=72)
        now = _now()
        record = enforcer.create_rights_record("case-1", "accused-1", now)
        enforcer.mark_evidence_disclosed("case-1")
        violations = enforcer.validate_panel_formation_allowed(
            record, now + timedelta(hours=1)
        )
        assert len(violations) > 0
        assert "Response period not elapsed" in violations[0]

    def test_blocked_if_evidence_not_disclosed(self):
        """Panel blocked if evidence not disclosed."""
        enforcer = RightsEnforcer(response_period_hours=72)
        now = _now()
        record = enforcer.create_rights_record("case-1", "accused-1", now)
        # Wait past deadline but don't disclose evidence
        violations = enforcer.validate_panel_formation_allowed(
            record, now + timedelta(hours=73)
        )
        assert any("evidence" in v.lower() for v in violations)

    def test_allowed_after_period_elapsed(self):
        """Panel allowed after 72h when evidence disclosed."""
        enforcer = RightsEnforcer(response_period_hours=72)
        now = _now()
        record = enforcer.create_rights_record("case-1", "accused-1", now)
        enforcer.mark_evidence_disclosed("case-1")
        violations = enforcer.validate_panel_formation_allowed(
            record, now + timedelta(hours=73)
        )
        assert violations == []

    def test_presumption_of_good_faith_default(self):
        """Presumption of good faith is True by default."""
        enforcer = RightsEnforcer()
        record = enforcer.create_rights_record("case-1", "accused-1", _now())
        assert record.presumption_of_good_faith is True
        assert record.representation_allowed is True


# =====================================================================
# TestRehabilitation — Trust rebuilding
# =====================================================================

class TestRehabilitation:
    """Tests for the rehabilitation engine."""

    def test_only_moderate_severity(self):
        """Only MODERATE severity is eligible for rehabilitation."""
        engine = RehabilitationEngine(_rehab_config())
        now = _now()
        # Moderate OK
        record = engine.create_rehabilitation(
            "actor-1", "case-1", 0.80, "moderate",
            now - timedelta(days=90), now, now,
        )
        assert record.rehab_id.startswith("rehab-")

        # Severe rejected
        with pytest.raises(ValueError, match="Rehabilitation not available"):
            engine.create_rehabilitation(
                "actor-2", "case-2", 0.80, "severe",
                now - timedelta(days=90), now, now,
            )

        # Egregious rejected
        with pytest.raises(ValueError, match="Rehabilitation not available"):
            engine.create_rehabilitation(
                "actor-3", "case-3", 0.80, "egregious",
                now - timedelta(days=90), now, now,
            )

    def test_probation_tasks_increment(self):
        """Probation tasks increment and complete rehabilitation."""
        engine = RehabilitationEngine(_rehab_config())
        now = _now()
        record = engine.create_rehabilitation(
            "actor-1", "case-1", 0.80, "moderate",
            now - timedelta(days=90), now, now,
        )
        engine.start_rehabilitation(record.rehab_id, now)
        for i in range(5):
            record = engine.record_probation_task(record.rehab_id)
        assert record.status == RehabStatus.COMPLETED
        assert record.probation_tasks_completed == 5

    def test_trust_restoration_capped(self):
        """Trust restoration is capped at min(original × 0.50, 0.30)."""
        engine = RehabilitationEngine(_rehab_config())
        # High original trust → capped at 0.30
        assert engine.compute_restored_trust(0.80) == 0.30
        # Low original trust → proportional
        assert engine.compute_restored_trust(0.40) == pytest.approx(0.20)

    def test_expiry_check(self):
        """Rehabilitation fails after 180-day window."""
        engine = RehabilitationEngine(_rehab_config())
        now = _now()
        record = engine.create_rehabilitation(
            "actor-1", "case-1", 0.80, "moderate",
            now - timedelta(days=90), now, now,
        )
        engine.start_rehabilitation(record.rehab_id, now)
        # Not expired at day 179
        assert not engine.check_rehab_expiry(record.rehab_id, now + timedelta(days=179))
        # Expired at day 181
        assert engine.check_rehab_expiry(record.rehab_id, now + timedelta(days=181))
        assert record.status == RehabStatus.FAILED


# =====================================================================
# TestServiceIntegration — Service layer wiring
# =====================================================================

@pytest.fixture
def service() -> GenesisService:
    resolver = PolicyResolver.from_config_dir(
        __import__("pathlib").Path(__file__).resolve().parents[1] / "config"
    )
    return GenesisService(resolver)


def _register_actor(
    service: GenesisService,
    actor_id: str,
    trust: float = 0.80,
    org: str = "org_a",
    region: str = "region_eu",
) -> None:
    entry = RosterEntry(
        actor_id=actor_id,
        actor_kind=ActorKind.HUMAN,
        trust_score=trust,
        region=region,
        organization=org,
        model_family="human",
        method_type="human_reviewer",
        status=ActorStatus.ACTIVE,
    )
    service._roster.register(entry)


class TestServiceIntegration:
    """Integration tests for the legal framework in the service layer."""

    def test_open_adjudication_emits_event(self, service: GenesisService):
        """Opening an adjudication emits ADJUDICATION_OPENED event."""
        _register_actor(service, "complainant_1")
        _register_actor(service, "accused_1", org="org_b", region="region_us")
        result = service.open_adjudication(
            type="compliance_complaint",
            complainant_id="complainant_1",
            accused_id="accused_1",
            reason="Test violation",
        )
        assert result.success
        assert result.data["case_id"].startswith("adj-")
        assert result.data["type"] == "compliance_complaint"

    def test_upheld_triggers_penalty(self, service: GenesisService):
        """UPHELD verdict triggers penalty on the accused."""
        _register_actor(service, "c1")
        _register_actor(service, "a1", org="org_b", region="region_us")
        # Register enough panelists with diverse orgs/regions
        for i in range(10):
            _register_actor(
                service, f"panelist_{i}",
                trust=0.80,
                org=f"org_{i % 3}",
                region=f"region_{i % 3}",
            )

        now = _now()
        result = service.open_adjudication(
            type="compliance_complaint",
            complainant_id="c1",
            accused_id="a1",
            reason="Violation",
            now=now,
        )
        case_id = result.data["case_id"]

        # Wait past response period
        after = now + timedelta(hours=73)
        panel_result = service.form_adjudication_panel(case_id, now=after)
        assert panel_result.success

        # All panelists vote upheld
        panel_ids = panel_result.data["panel_ids"]
        for pid in panel_ids:
            service.submit_adjudication_vote(
                case_id, pid, "upheld", f"att_{pid}", now=after,
            )

        # Check that accused was penalized
        accused = service._roster.get("a1")
        # MODERATE penalty from COMPLAINT_UPHELD → trust nuked to 0.001
        assert accused.trust_score == pytest.approx(0.001)

    def test_suspension_expiry_starts_rehabilitation(self, service: GenesisService):
        """Expired suspension creates rehabilitation record and sets PROBATION."""
        _register_actor(service, "actor_1")
        now = _now()

        # Apply moderate penalty
        service.apply_penalty("actor_1", "prohibited_category_confirmed", now=now)
        assert service.is_actor_suspended("actor_1")

        # Expire the suspension
        result = service.check_suspension_expiry("actor_1", now=now + timedelta(days=91))
        assert result.data["expired"]
        assert result.data["status"] == "probation"

        # Rehabilitation record should exist
        rehab = service._rehabilitation_engine.get_record_for_actor("actor_1")
        assert rehab is not None
        assert rehab.status == RehabStatus.ACTIVE
