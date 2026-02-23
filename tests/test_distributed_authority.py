"""Distributed authority design tests — governance separation of powers.

Validates that no single governance body can override, bypass, or subsume
the authority of another. Traces constitutional amendments through the full
legislative pipeline and verifies structural safeguards.

Design tests covered:
  #87 — No governance body can override another
  #88 — No permanent ruling class or binding judicial precedent
  #89 — No amendment permanently stalled by non-participation (voting deadline)
  #90 — No single org can dominate amendment chambers
  #91 — Founder cannot veto post-ratification amendments
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from genesis.governance.amendment import (
    AmendmentEngine,
    AmendmentProposal,
    AmendmentStatus,
    ConstitutionalViolation,
)
from genesis.models.governance import Chamber, ChamberKind

ROOT = Path(__file__).resolve().parent.parent
PARAMS_PATH = ROOT / "config" / "constitutional_params.json"


def _load_params() -> dict[str, Any]:
    return json.loads(PARAMS_PATH.read_text())


def _amendment_config() -> dict[str, Any]:
    """Default amendment config for engine init."""
    params = _load_params()
    entrenched = params.get("entrenched_provisions", {})
    lifecycle = params.get("amendment_lifecycle", {})
    return {
        "entrenched_amendment_threshold": entrenched.get("entrenched_amendment_threshold", 0.80),
        "entrenched_participation_minimum": entrenched.get("entrenched_participation_minimum", 0.50),
        "entrenched_cooling_off_days": entrenched.get("entrenched_cooling_off_days", 90),
        "entrenched_confirmation_vote_required": entrenched.get("entrenched_confirmation_vote_required", True),
        "chamber_voting_window_days": lifecycle.get("chamber_voting_window_days", 14),
        "chamber_org_diversity_min": lifecycle.get("chamber_org_diversity_min", 2),
        "lapse_participation_threshold": lifecycle.get("lapse_participation_threshold", 0.50),
    }


def _make_engine() -> AmendmentEngine:
    return AmendmentEngine(
        config=_amendment_config(),
        constitutional_params=_load_params(),
    )


def _g1_chamber(kind: str) -> Chamber:
    """Return G1 chamber definition."""
    params = _load_params()
    ch = params["genesis"]["G1_chambers"][kind]
    return Chamber(
        kind=ChamberKind(kind),
        size=ch["size"],
        pass_threshold=ch["pass_threshold"],
    )


def _make_voters(count: int, regions: int = 3, orgs: int = 3) -> list[dict[str, Any]]:
    """Generate voters with specified regional and org diversity."""
    voters = []
    for i in range(count):
        voters.append({
            "actor_id": f"voter_{i:03d}",
            "region": f"region_{i % regions}",
            "organization": f"org_{i % orgs}",
        })
    return voters


NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------------
# Design test #87: No single governance body can override another
# ------------------------------------------------------------------


class TestDesignTest87NoGovernanceOverride:
    """No single governance body can override, bypass, or subsume another."""

    def test_amendment_engine_has_no_admin_bypass(self):
        """AmendmentEngine has no method to skip chambers or force status."""
        engine = _make_engine()
        public_methods = [m for m in dir(engine) if not m.startswith("_")]
        bypass_words = {"force", "admin", "override", "bypass", "skip"}
        for method in public_methods:
            for word in bypass_words:
                assert word not in method.lower(), (
                    f"Amendment engine has suspicious method: {method}"
                )

    def test_three_chambers_required_for_all_phases(self):
        """All governance phases define all three chambers."""
        params = _load_params()
        for phase in ("G1_chambers", "G2_chambers"):
            chambers = params["genesis"][phase]
            for kind in ("proposal", "ratification", "challenge"):
                assert kind in chambers, f"{phase} missing {kind} chamber"
        full = params["full_constitution"]["chambers"]
        for kind in ("proposal", "ratification", "challenge"):
            assert kind in full, f"Full constitution missing {kind} chamber"

    def test_no_chamber_overlap_enforced(self):
        """Panel selection excludes members already on another chamber."""
        engine = _make_engine()
        proposal = engine.create_amendment(
            proposer_id="proposer_001",
            provision_key="quality_gates.Q_min_H",
            current_value=0.7,
            proposed_value=0.75,
            justification="Raise quality minimum for humans",
            now=NOW,
        )
        voters = _make_voters(60, regions=5, orgs=5)
        chamber = _g1_chamber("proposal")
        panel_a = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL, voters, chamber,
            r_min=3, c_max=0.40, now=NOW,
        )
        # Vote to pass proposal chamber
        for vid in panel_a:
            v = next(v for v in voters if v["actor_id"] == vid)
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.PROPOSAL,
                True, "I approve", v["region"], v["organization"], NOW,
            )
        engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.PROPOSAL, chamber, NOW,
        )
        # Select ratification panel
        rat_chamber = _g1_chamber("ratification")
        panel_b = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.RATIFICATION, voters,
            rat_chamber, r_min=3, c_max=0.40, now=NOW,
        )
        # No overlap between panels
        assert set(panel_a).isdisjoint(set(panel_b)), (
            "Proposal and ratification panels must not overlap"
        )


# ------------------------------------------------------------------
# Design test #88: No permanent ruling class or binding precedent
# ------------------------------------------------------------------


class TestDesignTest88NoPermanentAuthority:
    """No governance mechanism creates permanent authority or binding precedent."""

    def test_court_precedent_is_soft(self):
        """Constitutional Court module uses advisory, non-binding precedent."""
        from genesis.legal.adjudication import AdjudicationEngine
        # AdjudicationEngine doesn't have binding_precedent or mandatory_follow
        public_methods = [m for m in dir(AdjudicationEngine) if not m.startswith("_")]
        binding_words = {"binding", "mandatory", "precedent_enforce"}
        for method in public_methods:
            for word in binding_words:
                assert word not in method.lower(), (
                    f"AdjudicationEngine has binding-precedent method: {method}"
                )

    def test_assembly_has_no_decision_power(self):
        """Assembly module produces no binding resolutions."""
        from genesis.governance.assembly import AssemblyEngine
        public_methods = [m for m in dir(AssemblyEngine) if not m.startswith("_")]
        decision_words = {"vote", "decide", "resolve", "mandate", "binding"}
        for method in public_methods:
            for word in decision_words:
                assert word not in method.lower(), (
                    f"AssemblyEngine has decision-power method: {method}"
                )

    def test_org_registry_has_no_governance_power(self):
        """Organisation Registry cannot govern or create bloc voting."""
        from genesis.governance.org_registry import OrgRegistryEngine
        public_methods = [m for m in dir(OrgRegistryEngine) if not m.startswith("_")]
        governance_words = {"vote", "govern", "legislate", "bloc", "mandate"}
        for method in public_methods:
            for word in governance_words:
                assert word not in method.lower(), (
                    f"OrgRegistryEngine has governance method: {method}"
                )

    def test_machine_voting_weight_zero(self):
        """Machine constitutional voting weight is permanently zero."""
        params = _load_params()
        assert params["constitutional_voting"]["w_M_const"] == 0.0
        assert params["entrenched_provisions"]["MACHINE_VOTING_EXCLUSION"] is True


# ------------------------------------------------------------------
# Design test #89: No amendment permanently stalled by non-participation
# ------------------------------------------------------------------


class TestDesignTest89VotingDeadline:
    """Governance liveness — voting deadline prevents stalling."""

    def test_voting_deadline_set_on_panel_selection(self):
        """Panel selection sets a voting deadline."""
        engine = _make_engine()
        proposal = engine.create_amendment(
            proposer_id="proposer_001",
            provision_key="quality_gates.Q_min_H",
            current_value=0.7, proposed_value=0.75,
            justification="Raise quality", now=NOW,
        )
        voters = _make_voters(60, regions=5, orgs=5)
        engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL, voters,
            _g1_chamber("proposal"), r_min=3, c_max=0.40, now=NOW,
        )
        assert proposal.voting_deadline_utc is not None
        expected = NOW + timedelta(days=14)
        assert proposal.voting_deadline_utc == expected

    def test_lapse_on_deadline_with_low_participation(self):
        """Amendment lapses when deadline expires with < 50% participation."""
        engine = _make_engine()
        proposal = engine.create_amendment(
            proposer_id="proposer_001",
            provision_key="quality_gates.Q_min_H",
            current_value=0.7, proposed_value=0.75,
            justification="Raise quality", now=NOW,
        )
        voters = _make_voters(60, regions=5, orgs=5)
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL, voters,
            _g1_chamber("proposal"), r_min=3, c_max=0.40, now=NOW,
        )
        # Cast only 2 votes out of 11 (< 50%)
        for vid in panel[:2]:
            v = next(v for v in voters if v["actor_id"] == vid)
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.PROPOSAL,
                True, "I approve", v["region"], v["organization"], NOW,
            )
        # Close AFTER deadline
        after_deadline = NOW + timedelta(days=15)
        result, passed = engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            _g1_chamber("proposal"), after_deadline,
        )
        assert not passed
        assert result.status == AmendmentStatus.LAPSED

    def test_normal_close_before_deadline(self):
        """Closing before deadline works normally (no lapse)."""
        engine = _make_engine()
        proposal = engine.create_amendment(
            proposer_id="proposer_001",
            provision_key="quality_gates.Q_min_H",
            current_value=0.7, proposed_value=0.75,
            justification="Raise quality", now=NOW,
        )
        voters = _make_voters(60, regions=5, orgs=5)
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL, voters,
            _g1_chamber("proposal"), r_min=3, c_max=0.40, now=NOW,
        )
        # Cast enough votes to pass (threshold is 8 for G1 proposal)
        for vid in panel[:8]:
            v = next(v for v in voters if v["actor_id"] == vid)
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.PROPOSAL,
                True, "I approve", v["region"], v["organization"], NOW,
            )
        # Close BEFORE deadline
        before_deadline = NOW + timedelta(days=5)
        result, passed = engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            _g1_chamber("proposal"), before_deadline,
        )
        assert passed
        assert result.status == AmendmentStatus.RATIFICATION_CHAMBER_VOTING

    def test_sufficient_participation_after_deadline_still_counted(self):
        """If participation >= 50% after deadline, votes are counted normally."""
        engine = _make_engine()
        proposal = engine.create_amendment(
            proposer_id="proposer_001",
            provision_key="quality_gates.Q_min_H",
            current_value=0.7, proposed_value=0.75,
            justification="Raise quality", now=NOW,
        )
        voters = _make_voters(60, regions=5, orgs=5)
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL, voters,
            _g1_chamber("proposal"), r_min=3, c_max=0.40, now=NOW,
        )
        # 6 out of 11 vote (> 50% participation), but all NO
        for vid in panel[:6]:
            v = next(v for v in voters if v["actor_id"] == vid)
            engine.cast_chamber_vote(
                proposal.proposal_id, vid, ChamberKind.PROPOSAL,
                False, "I reject", v["region"], v["organization"], NOW,
            )
        after_deadline = NOW + timedelta(days=15)
        result, passed = engine.close_chamber_voting(
            proposal.proposal_id, ChamberKind.PROPOSAL,
            _g1_chamber("proposal"), after_deadline,
        )
        # Participation >= 50%, so it's a normal REJECTED, not LAPSED
        assert not passed
        assert result.status == AmendmentStatus.REJECTED

    def test_voting_window_days_in_config(self):
        """Constitutional params must define chamber_voting_window_days."""
        params = _load_params()
        lifecycle = params.get("amendment_lifecycle", {})
        assert lifecycle.get("chamber_voting_window_days") == 14


# ------------------------------------------------------------------
# Design test #90: No single org can dominate amendment chambers
# ------------------------------------------------------------------


class TestDesignTest90OrgDiversity:
    """Single-org domination of amendment chambers prevented."""

    def test_org_diversity_enforced_in_panel_selection(self):
        """Panel selection requires minimum 2 distinct organisations."""
        engine = _make_engine()
        proposal = engine.create_amendment(
            proposer_id="proposer_001",
            provision_key="quality_gates.Q_min_H",
            current_value=0.7, proposed_value=0.75,
            justification="Raise quality", now=NOW,
        )
        # All voters from ONE organisation, multiple regions
        single_org_voters = [
            {"actor_id": f"voter_{i:03d}", "region": f"region_{i % 5}",
             "organization": "mega_corp"}
            for i in range(60)
        ]
        with pytest.raises(ValueError, match="organisational diversity"):
            engine.select_chamber_panel(
                proposal.proposal_id, ChamberKind.PROPOSAL,
                single_org_voters, _g1_chamber("proposal"),
                r_min=3, c_max=0.40, org_diversity_min=2, now=NOW,
            )

    def test_org_concentration_cap_enforced(self):
        """No single org exceeds c_max of any chamber."""
        engine = _make_engine()
        proposal = engine.create_amendment(
            proposer_id="proposer_001",
            provision_key="quality_gates.Q_min_H",
            current_value=0.7, proposed_value=0.75,
            justification="Raise quality", now=NOW,
        )
        voters = _make_voters(60, regions=5, orgs=5)
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL, voters,
            _g1_chamber("proposal"), r_min=3, c_max=0.40,
            org_diversity_min=2, now=NOW,
        )
        # Check org distribution
        org_counts = proposal.chamber_org_counts.get(ChamberKind.PROPOSAL.value, {})
        chamber_size = _g1_chamber("proposal").size
        max_per_org = max(1, int(chamber_size * 0.40))
        for org, count in org_counts.items():
            assert count <= max_per_org, (
                f"Org '{org}' has {count} members, exceeds c_max cap of {max_per_org}"
            )

    def test_org_diversity_min_in_config(self):
        """Constitutional params must define chamber_org_diversity_min."""
        params = _load_params()
        lifecycle = params.get("amendment_lifecycle", {})
        assert lifecycle.get("chamber_org_diversity_min") == 2


# ------------------------------------------------------------------
# Design test #91: Founder cannot veto post-ratification
# ------------------------------------------------------------------


class TestDesignTest91VetoScope:
    """Founder veto is bounded — early-stage only, not post-democratic."""

    def test_veto_allowed_statuses_config(self):
        """Config defines allowed veto statuses as early-stage only."""
        params = _load_params()
        allowed = params["genesis"].get("founder_veto_allowed_statuses", [])
        assert "proposed" in allowed
        assert "proposal_chamber_voting" in allowed
        assert "ratification_chamber_voting" in allowed
        # Post-ratification statuses must NOT be allowed
        forbidden = {"challenge_window", "challenge_chamber_voting",
                     "cooling_off", "confirmation_vote", "confirmed", "applied"}
        for status in forbidden:
            assert status not in allowed, (
                f"Founder veto must not be allowed in post-ratification status: {status}"
            )

    def test_veto_expires_at_first_light(self):
        """Founder veto expiry is irreversibly tied to First Light."""
        params = _load_params()
        assert params["genesis"]["founder_veto_expiry"] == "first_light"
        assert params["genesis"]["founder_veto_active"] is True


# ------------------------------------------------------------------
# Proposal withdrawal (Fix 4)
# ------------------------------------------------------------------


class TestProposalWithdrawal:
    """Proposer can withdraw before any vote is cast."""

    def test_withdraw_in_proposed_status(self):
        """Withdrawal allowed when status is PROPOSED."""
        engine = _make_engine()
        proposal = engine.create_amendment(
            proposer_id="proposer_001",
            provision_key="quality_gates.Q_min_H",
            current_value=0.7, proposed_value=0.75,
            justification="Raise quality", now=NOW,
        )
        result = engine.withdraw_amendment(
            proposal.proposal_id, "proposer_001", NOW,
        )
        assert result.status == AmendmentStatus.WITHDRAWN

    def test_withdraw_in_voting_with_no_votes(self):
        """Withdrawal allowed in PROPOSAL_CHAMBER_VOTING if zero votes cast."""
        engine = _make_engine()
        proposal = engine.create_amendment(
            proposer_id="proposer_001",
            provision_key="quality_gates.Q_min_H",
            current_value=0.7, proposed_value=0.75,
            justification="Raise quality", now=NOW,
        )
        voters = _make_voters(60, regions=5, orgs=5)
        engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL, voters,
            _g1_chamber("proposal"), r_min=3, c_max=0.40, now=NOW,
        )
        assert proposal.status == AmendmentStatus.PROPOSAL_CHAMBER_VOTING
        result = engine.withdraw_amendment(
            proposal.proposal_id, "proposer_001", NOW,
        )
        assert result.status == AmendmentStatus.WITHDRAWN

    def test_withdraw_blocked_after_vote_cast(self):
        """Withdrawal blocked once any vote is cast."""
        engine = _make_engine()
        proposal = engine.create_amendment(
            proposer_id="proposer_001",
            provision_key="quality_gates.Q_min_H",
            current_value=0.7, proposed_value=0.75,
            justification="Raise quality", now=NOW,
        )
        voters = _make_voters(60, regions=5, orgs=5)
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL, voters,
            _g1_chamber("proposal"), r_min=3, c_max=0.40, now=NOW,
        )
        # Cast one vote
        vid = panel[0]
        v = next(v for v in voters if v["actor_id"] == vid)
        engine.cast_chamber_vote(
            proposal.proposal_id, vid, ChamberKind.PROPOSAL,
            True, "I approve", v["region"], v["organization"], NOW,
        )
        with pytest.raises(ValueError, match="votes have been cast"):
            engine.withdraw_amendment(proposal.proposal_id, "proposer_001", NOW)

    def test_only_proposer_can_withdraw(self):
        """Non-proposer cannot withdraw."""
        engine = _make_engine()
        proposal = engine.create_amendment(
            proposer_id="proposer_001",
            provision_key="quality_gates.Q_min_H",
            current_value=0.7, proposed_value=0.75,
            justification="Raise quality", now=NOW,
        )
        with pytest.raises(ValueError, match="Only the proposer"):
            engine.withdraw_amendment(proposal.proposal_id, "impostor_999", NOW)


# ------------------------------------------------------------------
# Proposer recusal (Fix 6)
# ------------------------------------------------------------------


class TestProposerRecusal:
    """Proposer excluded from all panels on their own amendment."""

    def test_proposer_excluded_from_proposal_panel(self):
        """Proposer cannot appear on the proposal chamber panel."""
        engine = _make_engine()
        proposal = engine.create_amendment(
            proposer_id="voter_000",  # Uses a voter ID as proposer
            provision_key="quality_gates.Q_min_H",
            current_value=0.7, proposed_value=0.75,
            justification="Raise quality", now=NOW,
        )
        voters = _make_voters(60, regions=5, orgs=5)
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL, voters,
            _g1_chamber("proposal"), r_min=3, c_max=0.40, now=NOW,
        )
        assert "voter_000" not in panel, (
            "Proposer must be excluded from their own amendment's panels"
        )


# ------------------------------------------------------------------
# Phase transition handling (Fix 5)
# ------------------------------------------------------------------


class TestPhaseTransition:
    """In-flight amendments handled correctly during phase transitions."""

    def test_no_votes_amendment_reset(self):
        """Amendment with no votes is reset to PROPOSED on phase transition."""
        engine = _make_engine()
        proposal = engine.create_amendment(
            proposer_id="proposer_001",
            provision_key="quality_gates.Q_min_H",
            current_value=0.7, proposed_value=0.75,
            justification="Raise quality", now=NOW,
        )
        # Select panel but don't vote
        voters = _make_voters(60, regions=5, orgs=5)
        engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL, voters,
            _g1_chamber("proposal"), r_min=3, c_max=0.40, now=NOW,
        )
        assert proposal.status == AmendmentStatus.PROPOSAL_CHAMBER_VOTING

        results = engine.handle_phase_transition("G2", NOW)
        assert results[proposal.proposal_id] == "reset"
        assert proposal.status == AmendmentStatus.PROPOSED
        assert len(proposal.chamber_panels) == 0

    def test_voted_amendment_continues(self):
        """Amendment with votes cast continues under original thresholds."""
        engine = _make_engine()
        proposal = engine.create_amendment(
            proposer_id="proposer_001",
            provision_key="quality_gates.Q_min_H",
            current_value=0.7, proposed_value=0.75,
            justification="Raise quality", now=NOW,
        )
        voters = _make_voters(60, regions=5, orgs=5)
        panel = engine.select_chamber_panel(
            proposal.proposal_id, ChamberKind.PROPOSAL, voters,
            _g1_chamber("proposal"), r_min=3, c_max=0.40, now=NOW,
        )
        # Cast a vote
        vid = panel[0]
        v = next(v for v in voters if v["actor_id"] == vid)
        engine.cast_chamber_vote(
            proposal.proposal_id, vid, ChamberKind.PROPOSAL,
            True, "I approve", v["region"], v["organization"], NOW,
        )
        results = engine.handle_phase_transition("G2", NOW)
        assert results[proposal.proposal_id] == "continued"
        assert proposal.status == AmendmentStatus.PROPOSAL_CHAMBER_VOTING

    def test_terminal_amendments_unaffected(self):
        """Rejected/applied/withdrawn amendments not affected by phase transition."""
        engine = _make_engine()
        proposal = engine.create_amendment(
            proposer_id="proposer_001",
            provision_key="quality_gates.Q_min_H",
            current_value=0.7, proposed_value=0.75,
            justification="Raise quality", now=NOW,
        )
        engine.withdraw_amendment(proposal.proposal_id, "proposer_001", NOW)
        assert proposal.status == AmendmentStatus.WITHDRAWN

        results = engine.handle_phase_transition("G2", NOW)
        assert proposal.proposal_id not in results


# ------------------------------------------------------------------
# Invariant checker covers new params
# ------------------------------------------------------------------


class TestInvariantCheckerIntegration:
    """Invariant checker validates distributed authority params."""

    def test_invariant_checker_passes(self):
        """Full invariant check passes with new params."""
        import subprocess
        result = subprocess.run(
            ["python3", "tools/check_invariants.py"],
            capture_output=True, text=True,
            cwd=str(ROOT),
        )
        assert result.returncode == 0, (
            f"Invariant checker failed:\n{result.stdout}\n{result.stderr}"
        )
