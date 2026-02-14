"""Skill decay engine — time-based proficiency decay with volume dampening.

Skills decay when not exercised. The decay formula mirrors trust decay:
    factor = max(floor, 1 - (days / half_life) / (1 + ln(1 + volume)))

Deep experience (high evidence_count) decays slower than shallow experience.

Key rules:
- Skills below a pruning threshold (default 0.01) are removed entirely.
- Decay floor prevents skills from reaching exactly zero.
- Only skills with a last_demonstrated timestamp are subject to decay.
- Decay is a pure computation — no side effects.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from genesis.models.skill import ActorSkillProfile, SkillProficiency
from genesis.policy.resolver import PolicyResolver


@dataclass(frozen=True)
class SkillDecayResult:
    """Result of applying decay to an actor's skill profile."""
    actor_id: str
    decayed_count: int
    pruned_count: int
    skills_before: int
    skills_after: int


class SkillDecayEngine:
    """Applies time-based decay to skill proficiencies.

    Usage:
        engine = SkillDecayEngine(resolver)
        new_profile, result = engine.apply_decay(profile)
    """

    def __init__(self, resolver: PolicyResolver) -> None:
        self._resolver = resolver

    def compute_decay_factor(
        self,
        days_since_last: float,
        half_life: float,
        evidence_count: int,
    ) -> float:
        """Compute the skill decay multiplier.

        Formula: factor = max(floor, 1 - (days / half_life) / (1 + ln(1 + evidence)))

        Higher evidence_count = slower decay (deeper expertise).
        Returns a value in [floor, 1.0] where 1.0 means no decay.
        """
        if days_since_last <= 0 or half_life <= 0:
            return 1.0

        dampening = 1.0 + math.log(1.0 + evidence_count)
        raw = 1.0 - (days_since_last / half_life) / dampening

        config = self._decay_config()
        floor = config.get("skill_decay_floor", 0.01)
        return max(floor, min(1.0, raw))

    def apply_decay(
        self,
        profile: ActorSkillProfile,
        now: Optional[datetime] = None,
        is_machine: bool = False,
    ) -> tuple[ActorSkillProfile, SkillDecayResult]:
        """Apply time-based decay to all skills in a profile.

        Does NOT mutate the input profile. Returns a new profile
        with decayed proficiencies and a result summary.

        Skills below the pruning threshold are removed entirely.
        """
        now = now or datetime.now(timezone.utc)
        config = self._decay_config()
        half_life = config.get("skill_half_life_days_machine" if is_machine else "skill_half_life_days_human", 365.0)
        prune_threshold = config.get("skill_prune_threshold", 0.01)

        new_skills: dict[str, SkillProficiency] = {}
        decayed_count = 0
        pruned_count = 0

        for canonical, sp in profile.skills.items():
            if sp.last_demonstrated_utc is None:
                # No timestamp — skip decay, keep skill
                new_skills[canonical] = sp
                continue

            days_since = (now - sp.last_demonstrated_utc).total_seconds() / 86400.0
            factor = self.compute_decay_factor(days_since, half_life, sp.evidence_count)

            # Only count as decayed if the effect is material (>0.1% change)
            if factor < 0.999:
                new_score = sp.proficiency_score * factor
                if new_score < prune_threshold:
                    pruned_count += 1
                    continue  # Skill removed

                decayed_count += 1
                new_skills[canonical] = SkillProficiency(
                    skill_id=sp.skill_id,
                    proficiency_score=new_score,
                    evidence_count=sp.evidence_count,
                    last_demonstrated_utc=sp.last_demonstrated_utc,
                    endorsement_count=sp.endorsement_count,
                    source=sp.source,
                )
            else:
                new_skills[canonical] = sp

        new_profile = ActorSkillProfile(
            actor_id=profile.actor_id,
            skills=new_skills,
            primary_domains=list(profile.primary_domains),
            updated_utc=now,
        )
        new_profile.recompute_primary_domains()

        result = SkillDecayResult(
            actor_id=profile.actor_id,
            decayed_count=decayed_count,
            pruned_count=pruned_count,
            skills_before=len(profile.skills),
            skills_after=len(new_skills),
        )

        return new_profile, result

    def _decay_config(self) -> dict:
        """Get skill lifecycle decay parameters."""
        if self._resolver.has_skill_lifecycle_config():
            return dict(self._resolver.skill_lifecycle_params())
        return {
            "skill_half_life_days_human": 365.0,
            "skill_half_life_days_machine": 90.0,
            "skill_decay_floor": 0.01,
            "skill_prune_threshold": 0.01,
        }
