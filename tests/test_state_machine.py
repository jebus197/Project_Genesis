"""Tests for mission state machine — proves transition rules are fail-closed."""

import pytest
from pathlib import Path

from genesis.policy.resolver import PolicyResolver
from genesis.engine.state_machine import MissionStateMachine
from genesis.models.mission import (
    DomainType,
    EvidenceRecord,
    Mission,
    MissionClass,
    MissionState,
    ReviewDecision,
    ReviewDecisionVerdict,
    Reviewer,
    RiskTier,
)


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def resolver() -> PolicyResolver:
    return PolicyResolver.from_config_dir(CONFIG_DIR)


@pytest.fixture
def sm(resolver: PolicyResolver) -> MissionStateMachine:
    return MissionStateMachine(resolver)


def _make_reviewer(id: str, region: str = "NA", org: str = "Org1",
                   family: str = "claude", method: str = "reasoning_model") -> Reviewer:
    return Reviewer(id=id, model_family=family, method_type=method,
                    region=region, organization=org)


def _make_r0_mission() -> Mission:
    return Mission(
        mission_id="M-TEST-R0",
        mission_title="Test R0 mission",
        mission_class=MissionClass.DOCUMENTATION_UPDATE,
        risk_tier=RiskTier.R0,
        domain_type=DomainType.OBJECTIVE,
        state=MissionState.DRAFT,
        worker_id="worker_1",
        reviewers=[_make_reviewer("reviewer_1")],
        review_decisions=[
            ReviewDecision(reviewer_id="reviewer_1", decision=ReviewDecisionVerdict.APPROVE),
        ],
        evidence=[
            EvidenceRecord(
                artifact_hash="sha256:5f2d8cb0325f4dc8c713f67c6482dfe4512b7064c9201022fc07012e31cb4037",
                signature="ed25519:8d43f2d567fa0c2ac4e13ab72d7f539ca4301e1a5ec2f7108e8f4b7b61a0c16f",
            ),
        ],
    )


class TestLegalTransitions:
    def test_draft_to_submitted(self, sm: MissionStateMachine) -> None:
        mission = _make_r0_mission()
        errors = sm.transition(mission, MissionState.SUBMITTED)
        assert errors == []

    def test_illegal_skip(self, sm: MissionStateMachine) -> None:
        mission = _make_r0_mission()
        errors = sm.transition(mission, MissionState.APPROVED)
        assert len(errors) > 0
        assert "Illegal transition" in errors[0]

    def test_cancel_from_draft(self, sm: MissionStateMachine) -> None:
        mission = _make_r0_mission()
        errors = sm.transition(mission, MissionState.CANCELLED)
        assert errors == []


class TestSelfReviewBlock:
    def test_worker_cannot_review_own_mission(self, sm: MissionStateMachine) -> None:
        mission = _make_r0_mission()
        mission.worker_id = "reviewer_1"  # Same as reviewer
        mission.state = MissionState.SUBMITTED
        errors = sm.transition(mission, MissionState.ASSIGNED)
        assert any("self-review" in e for e in errors)


class TestReviewComplete:
    def test_r0_review_complete_with_approval(self, sm: MissionStateMachine) -> None:
        mission = _make_r0_mission()
        mission.state = MissionState.IN_REVIEW
        errors = sm.transition(mission, MissionState.REVIEW_COMPLETE)
        assert errors == []

    def test_r0_review_complete_no_evidence_fails(self, sm: MissionStateMachine) -> None:
        mission = _make_r0_mission()
        mission.evidence = []
        mission.state = MissionState.IN_REVIEW
        errors = sm.transition(mission, MissionState.REVIEW_COMPLETE)
        assert any("evidence" in e.lower() for e in errors)

    def test_r0_review_complete_no_approval_fails(self, sm: MissionStateMachine) -> None:
        mission = _make_r0_mission()
        mission.review_decisions = [
            ReviewDecision(reviewer_id="reviewer_1", decision=ReviewDecisionVerdict.REJECT),
        ]
        mission.state = MissionState.IN_REVIEW
        errors = sm.transition(mission, MissionState.REVIEW_COMPLETE)
        assert any("approval" in e.lower() for e in errors)


class TestApprovalDeduplication:
    def test_duplicate_approvals_not_counted(self, sm: MissionStateMachine) -> None:
        """Same reviewer approving twice should count as one approval."""
        mission = _make_r0_mission()
        mission.review_decisions = [
            ReviewDecision(reviewer_id="reviewer_1", decision=ReviewDecisionVerdict.APPROVE),
            ReviewDecision(reviewer_id="reviewer_1", decision=ReviewDecisionVerdict.APPROVE),
        ]
        mission.state = MissionState.IN_REVIEW
        # R0 requires 1 approval; reviewer_1 counts once despite two records
        errors = sm.transition(mission, MissionState.REVIEW_COMPLETE)
        assert errors == []

    def test_duplicate_approvals_cannot_meet_higher_quorum(self, sm: MissionStateMachine) -> None:
        """Duplicate approvals from one reviewer cannot satisfy a quorum > 1."""
        mission = _make_r0_mission()
        mission.mission_class = MissionClass.INTERNAL_OPERATIONS_CHANGE
        mission.risk_tier = RiskTier.R1
        mission.reviewers = [
            _make_reviewer("rev_a", family="claude"),
            _make_reviewer("rev_b", family="gpt"),
        ]
        # Same reviewer approves twice — should only count as 1
        mission.review_decisions = [
            ReviewDecision(reviewer_id="rev_a", decision=ReviewDecisionVerdict.APPROVE),
            ReviewDecision(reviewer_id="rev_a", decision=ReviewDecisionVerdict.APPROVE),
        ]
        mission.state = MissionState.IN_REVIEW
        errors = sm.transition(mission, MissionState.REVIEW_COMPLETE)
        assert any("approval" in e.lower() for e in errors)


class TestHumanGate:
    def test_r2_requires_human_gate(self, sm: MissionStateMachine) -> None:
        mission = _make_r0_mission()
        mission.mission_class = MissionClass.REGULATED_ANALYSIS
        mission.risk_tier = RiskTier.R2
        mission.human_final_approval = False
        mission.state = MissionState.REVIEW_COMPLETE
        errors = sm.transition(mission, MissionState.APPROVED)
        assert any("human_final_approval" in e for e in errors)

    def test_r0_no_human_gate(self, sm: MissionStateMachine) -> None:
        mission = _make_r0_mission()
        mission.state = MissionState.REVIEW_COMPLETE
        errors = sm.transition(mission, MissionState.APPROVED)
        assert errors == []
