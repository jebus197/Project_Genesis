"""Reviewer router with heterogeneity enforcement.

Routes reviewer assignment for missions based on risk-tier policy:
- R0: 1 reviewer, no diversity requirements.
- R1: 2 reviewers, >= 2 model families.
- R2: 5 reviewers, >= 2 model families, >= 2 method types,
      >= 3 regions, >= 3 organizations.
- R3: Constitutional flow (handled by governance module).

Self-review is unconditionally blocked: a worker cannot review
their own mission.
"""

from __future__ import annotations

from genesis.models.mission import DomainType, Mission, Reviewer, RiskTier
from genesis.policy.resolver import PolicyResolver, TierPolicy


class ReviewerAssignmentError(Exception):
    """Raised when reviewer assignment constraints cannot be met."""


class ReviewerRouter:
    """Validates reviewer assignments against policy constraints.

    This module does NOT select reviewers (that requires a roster/pool).
    It validates that a proposed set of reviewers satisfies all
    constitutional constraints for the mission's risk tier.
    """

    def __init__(self, resolver: PolicyResolver) -> None:
        self._resolver = resolver

    def validate_assignment(
        self,
        mission: Mission,
        proposed_reviewers: list[Reviewer],
    ) -> list[str]:
        """Validate a proposed reviewer set against policy.

        Returns list of errors. Empty list = valid assignment.
        """
        errors: list[str] = []
        policy = self._resolver.tier_policy(mission.risk_tier)

        if policy.constitutional_flow:
            # R3: constitutional flow — reviewers handled by governance module
            return errors

        # Canonicalise and validate reviewer IDs: strip whitespace,
        # reject blank/empty, then check uniqueness on canonical forms.
        canonical_ids: list[str] = []
        for idx, rev in enumerate(proposed_reviewers):
            canonical = rev.id.strip() if rev.id else ""
            if not canonical:
                errors.append(
                    f"{mission.mission_id}: reviewer[{idx}] has blank or empty ID"
                )
            canonical_ids.append(canonical)

        # Unique reviewer IDs — duplicates cannot satisfy count constraints
        reviewer_ids = set(canonical_ids)
        if len(reviewer_ids) < len(proposed_reviewers):
            errors.append(
                f"{mission.mission_id}: duplicate reviewer IDs detected — "
                f"{len(proposed_reviewers)} entries but only "
                f"{len(reviewer_ids)} unique"
            )

        # Self-review block
        if mission.worker_id and mission.worker_id in reviewer_ids:
            errors.append(
                f"{mission.mission_id}: worker {mission.worker_id} "
                f"cannot be a reviewer (self-review blocked)"
            )

        # Reviewer count — use unique IDs, not list length
        if len(reviewer_ids) < policy.reviewers_required:
            errors.append(
                f"{mission.mission_id}: needs {policy.reviewers_required} "
                f"reviewers, got {len(reviewer_ids)}"
            )

        # Method type validation
        valid_methods = self._resolver.valid_method_types()
        for idx, rev in enumerate(proposed_reviewers):
            if not rev.model_family:
                errors.append(
                    f"{mission.mission_id}: reviewer[{idx}] missing model_family"
                )
            if not rev.method_type:
                errors.append(
                    f"{mission.mission_id}: reviewer[{idx}] missing method_type"
                )
            elif rev.method_type not in valid_methods:
                errors.append(
                    f"{mission.mission_id}: reviewer[{idx}] method_type "
                    f"'{rev.method_type}' not in {sorted(valid_methods)}"
                )

        # Heterogeneity: model family diversity
        families = {r.model_family for r in proposed_reviewers if r.model_family}
        if len(families) < policy.min_model_families:
            errors.append(
                f"{mission.mission_id}: needs {policy.min_model_families} "
                f"model families, got {len(families)}: {sorted(families)}"
            )

        # Heterogeneity: method type diversity
        methods = {r.method_type for r in proposed_reviewers if r.method_type}
        if len(methods) < policy.min_method_types:
            errors.append(
                f"{mission.mission_id}: needs {policy.min_method_types} "
                f"method types, got {len(methods)}: {sorted(methods)}"
            )

        # Geographic diversity
        regions = {r.region for r in proposed_reviewers}
        if len(regions) < policy.min_regions:
            errors.append(
                f"{mission.mission_id}: needs {policy.min_regions} "
                f"regions, got {len(regions)}: {sorted(regions)}"
            )

        # Organizational diversity
        orgs = {r.organization for r in proposed_reviewers}
        if len(orgs) < policy.min_organizations:
            errors.append(
                f"{mission.mission_id}: needs {policy.min_organizations} "
                f"organizations, got {len(orgs)}: {sorted(orgs)}"
            )

        return errors

    def check_normative_escalation(
        self,
        mission: Mission,
        agreement_ratio: float,
    ) -> bool:
        """Check if a mission requires normative human adjudication.

        Returns True if the domain is normative/mixed AND reviewer
        agreement is below the threshold.
        """
        if mission.domain_type == DomainType.OBJECTIVE:
            return False

        threshold = self._resolver.normative_agreement_threshold()
        return agreement_ratio < threshold
