"""Skill outcome updater — updates proficiency from mission outcomes.

When a mission is approved or rejected, skills used in that mission
are updated based on the outcome:
- Approved: proficiency increases (magnitude based on complexity)
- Rejected: proficiency decreases slightly (magnitude smaller)

Key rules:
- Outcome-derived is the primary source of skill evidence.
- Approval boosts more than rejection decreases (asymmetric update).
- Higher-tier missions produce larger updates (complexity multiplier).
- Evidence count is always incremented (track participation).
- Proficiency is clamped to [0, 1].
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from genesis.models.mission import Mission, MissionState, RiskTier
from genesis.models.skill import (
    ActorSkillProfile,
    SkillId,
    SkillProficiency,
    SkillRequirement,
)
from genesis.policy.resolver import PolicyResolver


@dataclass(frozen=True)
class SkillUpdateResult:
    """Result of a skill outcome update."""
    actor_id: str
    skills_updated: int
    updates: list[SkillUpdateDetail]


@dataclass(frozen=True)
class SkillUpdateDetail:
    """Detail of a single skill update."""
    skill_id: str
    old_proficiency: float
    new_proficiency: float
    delta: float
    evidence_count: int


class SkillOutcomeUpdater:
    """Updates skill proficiencies based on mission outcomes.

    Usage:
        updater = SkillOutcomeUpdater(resolver)
        result = updater.update_from_outcome(profile, mission, approved=True)
    """

    def __init__(self, resolver: PolicyResolver) -> None:
        self._resolver = resolver

    def update_from_outcome(
        self,
        profile: ActorSkillProfile,
        mission: Mission,
        approved: bool,
        now: Optional[datetime] = None,
    ) -> SkillUpdateResult:
        """Update skill proficiencies based on a mission outcome.

        Args:
            profile: The worker's skill profile to update.
            mission: The completed mission.
            approved: True if mission was approved, False if rejected.
            now: Override current time (for testing).

        Returns:
            SkillUpdateResult with details of all updates.
        """
        now = now or datetime.now(timezone.utc)
        config = self._outcome_config()

        approval_boost = config.get("approval_boost", 0.05)
        rejection_penalty = config.get("rejection_penalty", 0.02)
        complexity_multipliers = config.get("complexity_multipliers", {
            "R0": 1.0, "R1": 1.5, "R2": 2.0, "R3": 2.5,
        })

        # Complexity multiplier based on risk tier
        tier_key = mission.risk_tier.value if mission.risk_tier else "R0"
        complexity = complexity_multipliers.get(tier_key, 1.0)

        updates: list[SkillUpdateDetail] = []

        for req in mission.skill_requirements:
            canonical = req.skill_id.canonical
            existing = profile.skills.get(canonical)

            if existing is not None:
                old_score = existing.proficiency_score
            else:
                old_score = 0.0

            # Compute delta
            if approved:
                # Approved: boost proportional to complexity
                raw_delta = approval_boost * complexity
                # Diminishing returns near ceiling
                remaining_headroom = 1.0 - old_score
                delta = raw_delta * max(0.1, remaining_headroom)
            else:
                # Rejected: smaller penalty
                delta = -rejection_penalty * complexity

            new_score = max(0.0, min(1.0, old_score + delta))
            new_evidence = (existing.evidence_count if existing else 0) + 1

            # Update or create skill
            profile.skills[canonical] = SkillProficiency(
                skill_id=req.skill_id,
                proficiency_score=new_score,
                evidence_count=new_evidence,
                last_demonstrated_utc=now,
                endorsement_count=existing.endorsement_count if existing else 0,
                source="outcome_derived",
            )

            updates.append(SkillUpdateDetail(
                skill_id=canonical,
                old_proficiency=old_score,
                new_proficiency=new_score,
                delta=new_score - old_score,
                evidence_count=new_evidence,
            ))

        if updates:
            profile.updated_utc = now
            profile.recompute_primary_domains()

        return SkillUpdateResult(
            actor_id=profile.actor_id,
            skills_updated=len(updates),
            updates=updates,
        )

    def _outcome_config(self) -> dict:
        """Get skill outcome update parameters."""
        if self._resolver.has_skill_lifecycle_config():
            params = self._resolver.skill_lifecycle_params()
            return dict(params.get("outcome_updates", {}))
        return {
            "approval_boost": 0.05,
            "rejection_penalty": 0.02,
            "complexity_multipliers": {
                "R0": 1.0, "R1": 1.5, "R2": 2.0, "R3": 2.5,
            },
        }
