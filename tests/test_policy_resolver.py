"""Tests for the policy resolver — proves it loads and resolves all config correctly."""

import pytest
from pathlib import Path

from genesis.policy.resolver import PolicyResolver
from genesis.models.mission import MissionClass, RiskTier
from genesis.models.governance import GenesisPhase, ChamberKind


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


class TestMissionClassToTier:
    def test_documentation_maps_to_r0(self, resolver: PolicyResolver) -> None:
        assert resolver.resolve_tier(MissionClass.DOCUMENTATION_UPDATE) == RiskTier.R0

    def test_internal_ops_maps_to_r1(self, resolver: PolicyResolver) -> None:
        assert resolver.resolve_tier(MissionClass.INTERNAL_OPERATIONS_CHANGE) == RiskTier.R1

    def test_regulated_maps_to_r2(self, resolver: PolicyResolver) -> None:
        assert resolver.resolve_tier(MissionClass.REGULATED_ANALYSIS) == RiskTier.R2

    def test_constitutional_maps_to_r3(self, resolver: PolicyResolver) -> None:
        assert resolver.resolve_tier(MissionClass.CONSTITUTIONAL_CHANGE) == RiskTier.R3


class TestTierPolicy:
    def test_r0_basic(self, resolver: PolicyResolver) -> None:
        p = resolver.tier_policy(RiskTier.R0)
        assert p.reviewers_required == 1
        assert p.approvals_required == 1
        assert p.human_final_gate is False
        assert p.constitutional_flow is False

    def test_r2_high_risk(self, resolver: PolicyResolver) -> None:
        p = resolver.tier_policy(RiskTier.R2)
        assert p.reviewers_required >= 5
        assert p.approvals_required >= 4
        assert p.human_final_gate is True
        assert p.min_regions >= 3
        assert p.min_organizations >= 3
        assert p.min_model_families >= 2
        assert p.min_method_types >= 2

    def test_r3_constitutional(self, resolver: PolicyResolver) -> None:
        p = resolver.tier_policy(RiskTier.R3)
        assert p.constitutional_flow is True
        assert p.human_final_gate is True


class TestTrustWeights:
    def test_weights_sum_to_one(self, resolver: PolicyResolver) -> None:
        w_q, w_r, w_v, w_e = resolver.trust_weights()
        assert abs((w_q + w_r + w_v + w_e) - 1.0) < 1e-9

    def test_quality_dominates(self, resolver: PolicyResolver) -> None:
        w_q, _, _, _ = resolver.trust_weights()
        assert w_q >= 0.70

    def test_volume_bounded(self, resolver: PolicyResolver) -> None:
        _, _, w_v, _ = resolver.trust_weights()
        assert w_v <= 0.10

    def test_effort_bounded(self, resolver: PolicyResolver) -> None:
        _, _, _, w_e = resolver.trust_weights()
        assert w_e <= 0.10
        assert w_e >= 0.0


class TestConstitutionalVoting:
    def test_machine_weight_zero(self, resolver: PolicyResolver) -> None:
        _, w_m = resolver.constitutional_voting_weights()
        assert w_m == 0.0

    def test_human_weight_one(self, resolver: PolicyResolver) -> None:
        w_h, _ = resolver.constitutional_voting_weights()
        assert w_h == 1.0


class TestEligibility:
    def test_tau_prop_stricter_than_tau_vote(self, resolver: PolicyResolver) -> None:
        tau_vote, tau_prop = resolver.eligibility_thresholds()
        assert tau_prop > tau_vote
        assert 0.0 < tau_vote < 1.0
        assert 0.0 < tau_prop < 1.0


class TestGenesisChambers:
    def test_g1_chambers_exist(self, resolver: PolicyResolver) -> None:
        chambers = resolver.chambers_for_phase(GenesisPhase.G1)
        assert ChamberKind.PROPOSAL in chambers
        assert ChamberKind.RATIFICATION in chambers
        assert ChamberKind.CHALLENGE in chambers

    def test_g2_chambers_larger_than_g1(self, resolver: PolicyResolver) -> None:
        g1 = resolver.chambers_for_phase(GenesisPhase.G1)
        g2 = resolver.chambers_for_phase(GenesisPhase.G2)
        for kind in ChamberKind:
            assert g2[kind].size > g1[kind].size

    def test_g3_chambers_largest(self, resolver: PolicyResolver) -> None:
        g2 = resolver.chambers_for_phase(GenesisPhase.G2)
        g3 = resolver.chambers_for_phase(GenesisPhase.G3)
        for kind in ChamberKind:
            assert g3[kind].size > g2[kind].size

    def test_strict_majority(self, resolver: PolicyResolver) -> None:
        for phase in (GenesisPhase.G1, GenesisPhase.G2, GenesisPhase.G3):
            chambers = resolver.chambers_for_phase(phase)
            for kind, chamber in chambers.items():
                assert chamber.pass_threshold > chamber.size // 2

    def test_g0_raises(self, resolver: PolicyResolver) -> None:
        with pytest.raises(ValueError, match="G0"):
            resolver.chambers_for_phase(GenesisPhase.G0)


class TestGeoConstraints:
    def test_constraints_get_stricter(self, resolver: PolicyResolver) -> None:
        g1_rmin, g1_cmax = resolver.geo_constraints_for_phase(GenesisPhase.G1)
        g2_rmin, g2_cmax = resolver.geo_constraints_for_phase(GenesisPhase.G2)
        g3_rmin, g3_cmax = resolver.geo_constraints_for_phase(GenesisPhase.G3)
        assert g2_rmin > g1_rmin
        assert g3_rmin > g2_rmin
        assert g2_cmax < g1_cmax
        assert g3_cmax < g2_cmax


class TestEffortThresholds:
    def test_all_tiers_present(self, resolver: PolicyResolver) -> None:
        et = resolver.effort_thresholds()
        for tier in ("R0", "R1", "R2", "R3"):
            assert tier in et["E_min_per_tier"]

    def test_monotonically_increasing(self, resolver: PolicyResolver) -> None:
        et = resolver.effort_thresholds()
        e_min = et["E_min_per_tier"]
        assert e_min["R0"] <= e_min["R1"] <= e_min["R2"] <= e_min["R3"]

    def test_values_in_unit_interval(self, resolver: PolicyResolver) -> None:
        et = resolver.effort_thresholds()
        for tier, val in et["E_min_per_tier"].items():
            assert 0.0 <= val <= 1.0, f"E_min_per_tier[{tier}] out of range"

    def test_suspicious_low_non_negative(self, resolver: PolicyResolver) -> None:
        et = resolver.effort_thresholds()
        assert et["E_suspicious_low"] >= 0.0

    def test_max_credit_capped(self, resolver: PolicyResolver) -> None:
        et = resolver.effort_thresholds()
        assert et["E_max_credit"] <= 1.0

    def test_suspicious_low_below_r0_minimum(self, resolver: PolicyResolver) -> None:
        """E_suspicious_low should be strictly below the lowest tier minimum."""
        et = resolver.effort_thresholds()
        assert et["E_suspicious_low"] < et["E_min_per_tier"]["R0"]


class TestCommitmentTiers:
    def test_epoch_positive(self, resolver: PolicyResolver) -> None:
        assert resolver.epoch_hours() > 0

    def test_c1_faster_than_c0(self, resolver: PolicyResolver) -> None:
        c0_interval = resolver.l1_anchor_interval_hours("C0")
        c1_interval = resolver.l1_anchor_interval_hours("C1")
        assert c1_interval < c0_interval

    def test_committee_majority(self, resolver: PolicyResolver) -> None:
        n, t = resolver.commitment_committee()
        assert t > n // 2
        assert t <= n
