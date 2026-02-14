"""Mission state machine — enforces the exact transition rules.

Transitions are fail-closed: any transition not explicitly allowed is rejected.
No bypass path exists for self-review on critical tasks.
"""

from __future__ import annotations

from genesis.models.mission import (
    Mission,
    MissionState,
    ReviewDecisionVerdict,
)
from genesis.policy.resolver import PolicyResolver, TierPolicy


# Legal transitions: (from_state, to_state)
_TRANSITIONS: set[tuple[MissionState, MissionState]] = {
    (MissionState.DRAFT, MissionState.SUBMITTED),
    (MissionState.SUBMITTED, MissionState.ASSIGNED),
    (MissionState.ASSIGNED, MissionState.IN_REVIEW),
    (MissionState.IN_REVIEW, MissionState.REVIEW_COMPLETE),
    (MissionState.REVIEW_COMPLETE, MissionState.HUMAN_GATE_PENDING),
    (MissionState.REVIEW_COMPLETE, MissionState.APPROVED),
    (MissionState.REVIEW_COMPLETE, MissionState.REJECTED),
    (MissionState.HUMAN_GATE_PENDING, MissionState.APPROVED),
    (MissionState.HUMAN_GATE_PENDING, MissionState.REJECTED),
    # Cancel from any active state
    (MissionState.DRAFT, MissionState.CANCELLED),
    (MissionState.SUBMITTED, MissionState.CANCELLED),
    (MissionState.ASSIGNED, MissionState.CANCELLED),
    (MissionState.IN_REVIEW, MissionState.CANCELLED),
}


class TransitionError(Exception):
    """Raised when a state transition is not allowed."""


class MissionStateMachine:
    """Enforces mission lifecycle transitions.

    Every transition is validated against:
    1. Legal transition set (fail-closed).
    2. Risk-tier policy requirements.
    3. Evidence and review constraints.
    """

    def __init__(self, resolver: PolicyResolver) -> None:
        self._resolver = resolver

    def transition(self, mission: Mission, target: MissionState) -> list[str]:
        """Attempt to transition a mission to a target state.

        Returns a list of validation errors. Empty list means success.
        The caller is responsible for applying the state change only
        if the error list is empty.
        """
        errors: list[str] = []

        # Check legal transition
        if (mission.state, target) not in _TRANSITIONS:
            errors.append(
                f"Illegal transition: {mission.state.value} → {target.value}"
            )
            return errors  # No point checking further

        policy = self._resolver.tier_policy(mission.risk_tier)

        if target == MissionState.SUBMITTED:
            errors.extend(self._validate_submission(mission))

        elif target == MissionState.ASSIGNED:
            errors.extend(self._validate_assignment(mission, policy))

        elif target == MissionState.REVIEW_COMPLETE:
            errors.extend(self._validate_review_complete(mission, policy))

        elif target == MissionState.APPROVED:
            errors.extend(self._validate_approval(mission, policy))

        elif target == MissionState.HUMAN_GATE_PENDING:
            if not policy.human_final_gate:
                errors.append(
                    f"{mission.mission_id}: human gate not required for {policy.tier.value}"
                )

        return errors

    def _validate_submission(self, mission: Mission) -> list[str]:
        errors: list[str] = []
        if not mission.mission_title:
            errors.append(f"{mission.mission_id}: missing mission_title")
        if not mission.domain_type:
            errors.append(f"{mission.mission_id}: missing domain_type")
        return errors

    def _validate_assignment(self, mission: Mission, policy: TierPolicy) -> list[str]:
        errors: list[str] = []
        if not mission.worker_id:
            errors.append(f"{mission.mission_id}: no worker assigned")

        # Self-review check: worker cannot be a reviewer
        reviewer_ids = {r.id for r in mission.reviewers}
        if mission.worker_id and mission.worker_id in reviewer_ids:
            errors.append(
                f"{mission.mission_id}: worker {mission.worker_id} "
                f"cannot be a reviewer (self-review blocked)"
            )

        if not policy.constitutional_flow:
            if len(mission.reviewers) < policy.reviewers_required:
                errors.append(
                    f"{mission.mission_id}: needs {policy.reviewers_required} "
                    f"reviewers, got {len(mission.reviewers)}"
                )
        return errors

    def _validate_review_complete(
        self, mission: Mission, policy: TierPolicy
    ) -> list[str]:
        errors: list[str] = []

        if policy.constitutional_flow:
            return errors  # Constitutional flow has its own validation

        # Check approval count — deduplicate by reviewer_id so that
        # the same reviewer cannot inflate the approval count.
        seen_reviewers: set[str] = set()
        approvals = 0
        for d in mission.review_decisions:
            if d.decision == ReviewDecisionVerdict.APPROVE and d.reviewer_id not in seen_reviewers:
                seen_reviewers.add(d.reviewer_id)
                approvals += 1
        if approvals < policy.approvals_required:
            errors.append(
                f"{mission.mission_id}: needs {policy.approvals_required} "
                f"approvals, got {approvals}"
            )

        # Check evidence
        if not mission.evidence:
            errors.append(f"{mission.mission_id}: no evidence records")

        # Check region and org diversity among approving reviewers
        approved_ids = {
            d.reviewer_id
            for d in mission.review_decisions
            if d.decision == ReviewDecisionVerdict.APPROVE
        }
        approved_reviewers = [r for r in mission.reviewers if r.id in approved_ids]
        regions = {r.region for r in approved_reviewers}
        orgs = {r.organization for r in approved_reviewers}

        if len(regions) < policy.min_regions:
            errors.append(
                f"{mission.mission_id}: needs {policy.min_regions} regions "
                f"among approvals, got {len(regions)}"
            )
        if len(orgs) < policy.min_organizations:
            errors.append(
                f"{mission.mission_id}: needs {policy.min_organizations} "
                f"organizations among approvals, got {len(orgs)}"
            )

        return errors

    def _validate_approval(self, mission: Mission, policy: TierPolicy) -> list[str]:
        errors: list[str] = []
        if policy.human_final_gate and not mission.human_final_approval:
            errors.append(
                f"{mission.mission_id}: requires human_final_approval=true"
            )
        if mission.state == MissionState.REVIEW_COMPLETE and policy.human_final_gate:
            errors.append(
                f"{mission.mission_id}: must pass through HUMAN_GATE_PENDING first"
            )
        return errors
