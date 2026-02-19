"""Skill data models — skill identifiers, proficiency, profiles, and requirements.

These models represent the skill dimension of the labour market:
- What skills exist (SkillId — references canonical taxonomy)
- How proficient an actor is (SkillProficiency)
- An actor's complete skill profile (ActorSkillProfile)
- What a mission requires (SkillRequirement)

All fields map to the skill taxonomy in config/skill_taxonomy.json.
Taxonomy changes require constitutional governance at G1+.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class SkillId:
    """Canonical skill reference: domain:skill.

    The two-level taxonomy uses domains (broad areas) containing
    skills (specific capabilities). The canonical string form is
    "domain:skill", e.g., "software_engineering:python".
    """
    domain: str
    skill: str

    @property
    def canonical(self) -> str:
        """Return the canonical string form 'domain:skill'."""
        return f"{self.domain}:{self.skill}"

    @classmethod
    def parse(cls, canonical: str) -> SkillId:
        """Parse a canonical skill string into a SkillId.

        Args:
            canonical: String in "domain:skill" format.

        Raises:
            ValueError: If the string is not in valid format.
        """
        if ":" not in canonical:
            raise ValueError(
                f"Invalid skill ID format: '{canonical}'. "
                f"Expected 'domain:skill'."
            )
        parts = canonical.split(":", 1)
        domain = parts[0].strip()
        skill = parts[1].strip()
        if not domain or not skill:
            raise ValueError(
                f"Invalid skill ID: '{canonical}'. "
                f"Both domain and skill must be non-empty."
            )
        return cls(domain=domain, skill=skill)

    def __str__(self) -> str:
        return self.canonical


@dataclass
class SkillProficiency:
    """An actor's proficiency in a single skill.

    Proficiency is derived primarily from mission outcomes (outcome_derived)
    and can be boosted by peer endorsement (peer_endorsed). Self-declared
    skills carry no weight until validated by outcomes.
    """
    skill_id: SkillId
    proficiency_score: float  # 0.0 - 1.0
    evidence_count: int  # missions completed exercising this skill
    last_demonstrated_utc: Optional[datetime] = None
    endorsement_count: int = 0
    source: str = "outcome_derived"  # "outcome_derived" | "peer_endorsed" | "self_declared"

    def __post_init__(self) -> None:
        if not (0.0 <= self.proficiency_score <= 1.0):
            raise ValueError(
                f"proficiency_score must be in [0.0, 1.0], "
                f"got {self.proficiency_score}"
            )
        valid_sources = ("outcome_derived", "peer_endorsed", "self_declared")
        if self.source not in valid_sources:
            raise ValueError(
                f"source must be one of {valid_sources}, got '{self.source}'"
            )

    def display_score(self) -> int:
        """Return proficiency on the 1-1000 display scale.

        Internal math stays 0.0-1.0. This multiplies by 1000 and
        returns an integer for display purposes.
        """
        return int(round(self.proficiency_score * 1000))


@dataclass
class ActorSkillProfile:
    """Complete skill profile for an actor.

    Aggregates all skills an actor has demonstrated or declared.
    The primary_domains list is ordered by overall proficiency in
    each domain (highest first).
    """
    actor_id: str
    skills: dict[str, SkillProficiency] = field(default_factory=dict)
    # keyed by canonical skill ID ("domain:skill")
    primary_domains: list[str] = field(default_factory=list)
    # ordered by domain proficiency (highest first)
    updated_utc: Optional[datetime] = None

    def get_proficiency(self, skill_id: SkillId) -> Optional[SkillProficiency]:
        """Look up proficiency for a specific skill."""
        return self.skills.get(skill_id.canonical)

    def has_skill(self, skill_id: SkillId) -> bool:
        """Check if the actor has any proficiency in a skill."""
        return skill_id.canonical in self.skills

    def domain_proficiency(self, domain: str) -> float:
        """Average proficiency across all skills in a domain.

        Returns 0.0 if the actor has no skills in the domain.
        """
        domain_skills = [
            sp for key, sp in self.skills.items()
            if sp.skill_id.domain == domain
        ]
        if not domain_skills:
            return 0.0
        return sum(sp.proficiency_score for sp in domain_skills) / len(domain_skills)

    def recompute_primary_domains(self) -> None:
        """Recompute the primary_domains list based on current proficiencies.

        Domains are ordered by average proficiency (highest first).
        Only domains where the actor has at least one skill are included.
        """
        domain_scores: dict[str, list[float]] = {}
        for sp in self.skills.values():
            domain = sp.skill_id.domain
            domain_scores.setdefault(domain, []).append(sp.proficiency_score)

        ranked = sorted(
            domain_scores.keys(),
            key=lambda d: sum(domain_scores[d]) / len(domain_scores[d]),
            reverse=True,
        )
        self.primary_domains = ranked


@dataclass(frozen=True)
class SkillRequirement:
    """A skill requirement for a mission.

    Missions can declare what skills they need. Each requirement
    specifies a minimum proficiency and whether it's mandatory
    or preferred.
    """
    skill_id: SkillId
    minimum_proficiency: float = 0.0  # 0.0 - 1.0
    required: bool = True  # True = must have, False = nice to have

    def __post_init__(self) -> None:
        if not (0.0 <= self.minimum_proficiency <= 1.0):
            raise ValueError(
                f"minimum_proficiency must be in [0.0, 1.0], "
                f"got {self.minimum_proficiency}"
            )
