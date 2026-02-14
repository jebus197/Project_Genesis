"""Skill match engine — computes relevance scores between actors and missions.

Pure computation. No side effects.

Relevance measures how well an actor's skill profile matches a mission's
skill requirements. Used for:
- Pre-filtering reviewer candidates (skill-aware selection)
- Worker discovery and ranking (labour market)
- Bid scoring (market allocation)

relevance = proficiency_weight * avg_proficiency_match + domain_trust_weight * avg_domain_trust
"""

from __future__ import annotations

from typing import Any, Optional

from genesis.models.domain_trust import DomainTrustScore
from genesis.models.skill import (
    ActorSkillProfile,
    SkillId,
    SkillRequirement,
)
from genesis.models.trust import TrustRecord
from genesis.policy.resolver import PolicyResolver


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class SkillMatchEngine:
    """Computes relevance scores between actor skill profiles and mission requirements.

    Usage:
        engine = SkillMatchEngine(resolver)
        score = engine.compute_relevance(profile, requirements, trust_record)
    """

    def __init__(self, resolver: PolicyResolver) -> None:
        self._resolver = resolver

    def compute_relevance(
        self,
        profile: Optional[ActorSkillProfile],
        requirements: list[SkillRequirement],
        trust_record: Optional[TrustRecord] = None,
    ) -> float:
        """Compute relevance score for an actor against mission requirements.

        Args:
            profile: The actor's skill profile. If None, returns 0.0.
            requirements: The mission's skill requirements. If empty, returns 1.0
                (any actor is relevant to a mission with no requirements).
            trust_record: Optional trust record for domain trust component.

        Returns:
            Relevance score in [0.0, 1.0].
        """
        if not requirements:
            return 1.0  # No requirements → everyone is relevant

        if profile is None:
            return 0.0  # No profile → zero relevance

        p_weight, dt_weight = self._match_weights()

        # Proficiency component: how well does the actor's proficiency
        # match the requirements?
        proficiency_score = self._compute_proficiency_match(profile, requirements)

        # Domain trust component: how much domain-specific trust does
        # the actor have in the required domains?
        domain_trust_score = 0.0
        if trust_record is not None and dt_weight > 0:
            domain_trust_score = self._compute_domain_trust_match(
                trust_record, requirements,
            )

        relevance = p_weight * proficiency_score + dt_weight * domain_trust_score
        return _clamp(relevance)

    def _compute_proficiency_match(
        self,
        profile: ActorSkillProfile,
        requirements: list[SkillRequirement],
    ) -> float:
        """Average proficiency match across all requirements.

        For each requirement:
        - If actor has the skill, match = proficiency / max(minimum, 1.0)
          (clamped to [0, 1] — meeting minimum = 1.0, exceeding = still 1.0)
        - If actor lacks the skill but requirement is optional, match = 0.0
        - If actor lacks the skill and requirement is required, match = 0.0

        Returns average of all matches. 0.0 if no requirements.
        """
        if not requirements:
            return 0.0

        total_match = 0.0
        for req in requirements:
            sp = profile.get_proficiency(req.skill_id)
            if sp is not None:
                if req.minimum_proficiency > 0:
                    match = min(1.0, sp.proficiency_score / req.minimum_proficiency)
                else:
                    # No minimum set — having any proficiency is a full match
                    match = 1.0 if sp.proficiency_score > 0 else 0.5
                total_match += match
            # else: 0.0 — actor lacks the skill

        return total_match / len(requirements)

    def _compute_domain_trust_match(
        self,
        trust_record: TrustRecord,
        requirements: list[SkillRequirement],
    ) -> float:
        """Average domain trust across required domains.

        Extracts unique domains from requirements and averages the
        actor's domain trust scores for those domains.
        """
        domains: set[str] = set()
        for req in requirements:
            domains.add(req.skill_id.domain)

        if not domains:
            return 0.0

        total = 0.0
        for domain in domains:
            ds = trust_record.domain_scores.get(domain)
            if ds is not None:
                total += ds.score

        return total / len(domains)

    def meets_minimum_relevance(
        self,
        profile: Optional[ActorSkillProfile],
        requirements: list[SkillRequirement],
        trust_record: Optional[TrustRecord] = None,
    ) -> bool:
        """Check if an actor meets the minimum relevance threshold."""
        if not requirements:
            return True
        relevance = self.compute_relevance(profile, requirements, trust_record)
        return relevance >= self._min_relevance()

    def meets_required_skills(
        self,
        profile: Optional[ActorSkillProfile],
        requirements: list[SkillRequirement],
    ) -> bool:
        """Check if an actor has all required skills at minimum proficiency.

        This is a hard filter — required skills must be present.
        Optional skills are ignored.
        """
        if not requirements:
            return True
        if profile is None:
            # Check if any skills are actually required
            return not any(r.required for r in requirements)

        for req in requirements:
            if not req.required:
                continue
            sp = profile.get_proficiency(req.skill_id)
            if sp is None:
                return False
            if sp.proficiency_score < req.minimum_proficiency:
                return False

        return True

    def _match_weights(self) -> tuple[float, float]:
        """Return (proficiency_weight, domain_trust_weight)."""
        if not self._resolver.has_skill_trust_config():
            return (0.60, 0.40)
        config = self._resolver.skill_matching_config()
        return (
            config.get("proficiency_weight", 0.60),
            config.get("domain_trust_weight", 0.40),
        )

    def _min_relevance(self) -> float:
        """Return the minimum relevance score threshold."""
        if not self._resolver.has_skill_trust_config():
            return 0.3
        config = self._resolver.skill_matching_config()
        return config.get("min_relevance_score", 0.3)
