"""Endorsement engine — peer endorsement with diminishing returns.

Rules:
- Endorsement can only boost existing outcome-derived skills, never create.
- Endorser must have the skill at proficiency >= threshold.
- Self-endorsement is structurally blocked.
- Diminishing returns: boost = base_boost * endorser_trust / (1 + existing_endorsements).
- Endorsement source is tagged as "peer_endorsed".

This is a secondary signal. Outcome-derived is always primary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from genesis.models.skill import (
    ActorSkillProfile,
    SkillId,
    SkillProficiency,
)
from genesis.models.trust import TrustRecord
from genesis.policy.resolver import PolicyResolver


@dataclass(frozen=True)
class EndorsementResult:
    """Result of an endorsement attempt."""
    success: bool
    errors: list[str]
    old_proficiency: float = 0.0
    new_proficiency: float = 0.0
    boost_applied: float = 0.0


class EndorsementEngine:
    """Processes peer endorsements with validation and diminishing returns.

    Usage:
        engine = EndorsementEngine(resolver)
        result = engine.endorse(
            endorser_profile, endorser_trust,
            target_profile, skill_id,
        )
    """

    def __init__(self, resolver: PolicyResolver) -> None:
        self._resolver = resolver

    def endorse(
        self,
        endorser_id: str,
        endorser_profile: ActorSkillProfile,
        endorser_trust: TrustRecord,
        target_profile: ActorSkillProfile,
        skill_id: SkillId,
        now: Optional[datetime] = None,
    ) -> EndorsementResult:
        """Process a peer endorsement of a skill.

        Args:
            endorser_id: The actor endorsing the skill.
            endorser_profile: Endorser's skill profile.
            endorser_trust: Endorser's trust record.
            target_profile: The profile being endorsed.
            skill_id: The skill being endorsed.
            now: Override current time (for testing).

        Returns:
            EndorsementResult with success/error info.
        """
        now = now or datetime.now(timezone.utc)
        config = self._endorsement_config()

        # Rule 1: Self-endorsement blocked
        if endorser_id == target_profile.actor_id:
            return EndorsementResult(
                success=False,
                errors=["Self-endorsement is not allowed"],
            )

        # Rule 2: Endorser must have the skill at sufficient proficiency
        min_endorser_proficiency = config.get("min_endorser_proficiency", 0.5)
        endorser_sp = endorser_profile.get_proficiency(skill_id)
        if endorser_sp is None:
            return EndorsementResult(
                success=False,
                errors=[
                    f"Endorser does not have skill {skill_id.canonical}"
                ],
            )
        if endorser_sp.proficiency_score < min_endorser_proficiency:
            return EndorsementResult(
                success=False,
                errors=[
                    f"Endorser proficiency {endorser_sp.proficiency_score:.2f} "
                    f"below minimum {min_endorser_proficiency:.2f} to endorse"
                ],
            )

        # Rule 3: Target must already have this skill (outcome-derived)
        target_sp = target_profile.get_proficiency(skill_id)
        if target_sp is None:
            return EndorsementResult(
                success=False,
                errors=[
                    f"Target has no existing skill {skill_id.canonical}. "
                    f"Endorsement can only boost existing skills, not create them."
                ],
            )

        # Compute boost with diminishing returns
        base_boost = config.get("base_boost", 0.05)
        endorser_trust_score = endorser_trust.score if endorser_trust else 0.0
        existing_endorsements = target_sp.endorsement_count

        # boost = base_boost * endorser_trust / (1 + existing_endorsements)
        boost = base_boost * endorser_trust_score / (1.0 + existing_endorsements)

        # Cap total proficiency at 1.0
        old_score = target_sp.proficiency_score
        new_score = min(1.0, old_score + boost)

        # Update skill in target profile (mutates profile)
        target_profile.skills[skill_id.canonical] = SkillProficiency(
            skill_id=skill_id,
            proficiency_score=new_score,
            evidence_count=target_sp.evidence_count,
            last_demonstrated_utc=target_sp.last_demonstrated_utc,
            endorsement_count=existing_endorsements + 1,
            source="peer_endorsed" if target_sp.source == "peer_endorsed" else target_sp.source,
        )
        target_profile.updated_utc = now

        return EndorsementResult(
            success=True,
            errors=[],
            old_proficiency=old_score,
            new_proficiency=new_score,
            boost_applied=boost,
        )

    def _endorsement_config(self) -> dict:
        """Get endorsement parameters."""
        if self._resolver.has_skill_lifecycle_config():
            params = self._resolver.skill_lifecycle_params()
            return dict(params.get("endorsement", {}))
        return {
            "base_boost": 0.05,
            "min_endorser_proficiency": 0.5,
            "max_endorsements_per_skill": 10,
        }
