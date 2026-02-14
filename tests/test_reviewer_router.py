"""Tests for reviewer router — proves heterogeneity and self-review enforcement."""

import pytest
from pathlib import Path

from genesis.policy.resolver import PolicyResolver
from genesis.engine.reviewer_router import ReviewerRouter
from genesis.models.mission import (
    DomainType,
    Mission,
    MissionClass,
    MissionState,
    Reviewer,
    RiskTier,
)


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def router(resolver: PolicyResolver) -> ReviewerRouter:
    return ReviewerRouter(resolver)


def _rev(id: str, family: str = "claude", method: str = "reasoning_model",
         region: str = "NA", org: str = "Org1") -> Reviewer:
    return Reviewer(id=id, model_family=family, method_type=method,
                    region=region, organization=org)


class TestR0Assignment:
    def test_valid_r0(self, router: ReviewerRouter) -> None:
        mission = Mission(
            mission_id="M-R0",
            mission_title="R0 test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            worker_id="worker_1",
        )
        reviewers = [_rev("rev_1")]
        errors = router.validate_assignment(mission, reviewers)
        assert errors == []


class TestR2Heterogeneity:
    def test_r2_monoculture_blocked(self, router: ReviewerRouter) -> None:
        """All same model family and method — should fail."""
        mission = Mission(
            mission_id="M-R2",
            mission_title="R2 test",
            mission_class=MissionClass.REGULATED_ANALYSIS,
            risk_tier=RiskTier.R2,
            domain_type=DomainType.MIXED,
            worker_id="worker_1",
        )
        # All same family and method — violates heterogeneity
        reviewers = [
            _rev(f"rev_{i}", family="claude", method="reasoning_model",
                 region=r, org=o)
            for i, (r, o) in enumerate([
                ("NA", "Org1"), ("EU", "Org2"), ("APAC", "Org3"),
                ("LATAM", "Org4"), ("AF", "Org5"),
            ])
        ]
        errors = router.validate_assignment(mission, reviewers)
        assert any("method types" in e for e in errors)

    def test_r2_valid_diverse(self, router: ReviewerRouter) -> None:
        """Properly diverse reviewer set — should pass."""
        mission = Mission(
            mission_id="M-R2-OK",
            mission_title="R2 diverse",
            mission_class=MissionClass.REGULATED_ANALYSIS,
            risk_tier=RiskTier.R2,
            domain_type=DomainType.MIXED,
            worker_id="worker_1",
        )
        reviewers = [
            _rev("rev_1", family="claude", method="reasoning_model", region="NA", org="Org1"),
            _rev("rev_2", family="gpt", method="retrieval_augmented", region="EU", org="Org2"),
            _rev("rev_3", family="gemini", method="reasoning_model", region="APAC", org="Org3"),
            _rev("rev_4", family="claude", method="rule_based_deterministic", region="LATAM", org="Org4"),
            _rev("rev_5", family="gpt", method="retrieval_augmented", region="NA", org="Org5"),
        ]
        errors = router.validate_assignment(mission, reviewers)
        assert errors == []


class TestReviewerUniqueness:
    def test_duplicate_reviewer_ids_rejected(self, router: ReviewerRouter) -> None:
        """Same reviewer ID submitted twice should be flagged."""
        mission = Mission(
            mission_id="M-DUP",
            mission_title="Duplicate reviewer test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            worker_id="worker_1",
        )
        reviewers = [_rev("same_id"), _rev("same_id")]
        errors = router.validate_assignment(mission, reviewers)
        assert any("duplicate" in e.lower() for e in errors)

    def test_duplicate_ids_cannot_satisfy_count(self, router: ReviewerRouter) -> None:
        """Three entries with one unique ID cannot satisfy a 'needs 1' constraint."""
        mission = Mission(
            mission_id="M-DUP2",
            mission_title="Duplicate count test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            worker_id="worker_1",
        )
        # R0 needs 1 reviewer — but submitting the same ID should still flag duplicates
        reviewers = [_rev("rev_1"), _rev("rev_1"), _rev("rev_1")]
        errors = router.validate_assignment(mission, reviewers)
        assert any("duplicate" in e.lower() for e in errors)


class TestBlankReviewerID:
    def test_empty_id_rejected(self, router: ReviewerRouter) -> None:
        """A reviewer with an empty string ID must be rejected."""
        mission = Mission(
            mission_id="M-BLANK",
            mission_title="Blank ID test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            worker_id="worker_1",
        )
        reviewers = [_rev("")]
        errors = router.validate_assignment(mission, reviewers)
        assert any("blank" in e.lower() or "empty" in e.lower() for e in errors)

    def test_whitespace_id_rejected(self, router: ReviewerRouter) -> None:
        """A reviewer with a whitespace-only ID must be rejected."""
        mission = Mission(
            mission_id="M-SPACE",
            mission_title="Whitespace ID test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            worker_id="worker_1",
        )
        reviewers = [_rev("   ")]
        errors = router.validate_assignment(mission, reviewers)
        assert any("blank" in e.lower() or "empty" in e.lower() for e in errors)


class TestSelfReview:
    def test_worker_blocked_as_reviewer(self, router: ReviewerRouter) -> None:
        mission = Mission(
            mission_id="M-SELF",
            mission_title="Self-review test",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            worker_id="sneaky_worker",
        )
        reviewers = [_rev("sneaky_worker")]
        errors = router.validate_assignment(mission, reviewers)
        assert any("self-review" in e for e in errors)


class TestNormativeEscalation:
    def test_objective_no_escalation(self, router: ReviewerRouter) -> None:
        mission = Mission(
            mission_id="M-OBJ",
            mission_title="Objective",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
        )
        assert router.check_normative_escalation(mission, 0.3) is False

    def test_normative_low_agreement_escalates(self, router: ReviewerRouter) -> None:
        mission = Mission(
            mission_id="M-NORM",
            mission_title="Normative",
            mission_class=MissionClass.REGULATED_ANALYSIS,
            risk_tier=RiskTier.R2,
            domain_type=DomainType.NORMATIVE,
        )
        assert router.check_normative_escalation(mission, 0.4) is True

    def test_normative_high_agreement_no_escalation(self, router: ReviewerRouter) -> None:
        mission = Mission(
            mission_id="M-NORM2",
            mission_title="Normative agreed",
            mission_class=MissionClass.REGULATED_ANALYSIS,
            risk_tier=RiskTier.R2,
            domain_type=DomainType.NORMATIVE,
        )
        assert router.check_normative_escalation(mission, 0.8) is False
