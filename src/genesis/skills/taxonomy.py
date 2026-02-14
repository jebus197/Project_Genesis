"""Skill taxonomy — loads, validates, and queries the canonical skill taxonomy.

The taxonomy is a two-level structure: domains → skills.
Changes to the taxonomy require constitutional governance at G1+.

Usage:
    taxonomy = SkillTaxonomy.from_config_dir(Path("config"))
    assert taxonomy.is_valid_skill(SkillId("software_engineering", "python"))
    domains = taxonomy.all_domains()
    skills = taxonomy.skills_in_domain("data_science")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genesis.models.skill import SkillId, SkillRequirement


class SkillTaxonomy:
    """Loads and validates the skill taxonomy from config.

    The taxonomy defines the canonical set of domains and skills.
    All skill references in the system must be validated against
    this taxonomy.
    """

    TAXONOMY_FILENAME = "skill_taxonomy.json"

    def __init__(self, taxonomy_data: dict[str, Any]) -> None:
        self._data = taxonomy_data
        self._domains: dict[str, dict[str, Any]] = taxonomy_data.get("domains", {})
        self._validate()

    @classmethod
    def from_config_dir(cls, config_dir: Path) -> SkillTaxonomy:
        """Load taxonomy from the canonical config directory.

        Args:
            config_dir: Path to the config directory containing
                skill_taxonomy.json.

        Returns:
            A validated SkillTaxonomy instance.

        Raises:
            FileNotFoundError: If skill_taxonomy.json does not exist.
            ValueError: If the taxonomy is structurally invalid.
        """
        path = config_dir / cls.TAXONOMY_FILENAME
        if not path.exists():
            raise FileNotFoundError(f"Skill taxonomy not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data)

    def _validate(self) -> None:
        """Validate taxonomy structure.

        Raises:
            ValueError: If the taxonomy is structurally invalid.
        """
        if "version" not in self._data:
            raise ValueError("Skill taxonomy missing 'version' field")
        if "domains" not in self._data:
            raise ValueError("Skill taxonomy missing 'domains' field")
        if not isinstance(self._domains, dict):
            raise ValueError("Skill taxonomy 'domains' must be a dict")

        for domain_name, domain_data in self._domains.items():
            if not isinstance(domain_name, str) or not domain_name.strip():
                raise ValueError(f"Invalid domain name: {domain_name!r}")
            if not isinstance(domain_data, dict):
                raise ValueError(
                    f"Domain '{domain_name}' must be a dict, "
                    f"got {type(domain_data).__name__}"
                )
            if "skills" not in domain_data:
                raise ValueError(f"Domain '{domain_name}' missing 'skills' list")
            skills = domain_data["skills"]
            if not isinstance(skills, list):
                raise ValueError(
                    f"Domain '{domain_name}' skills must be a list"
                )
            if len(skills) == 0:
                raise ValueError(
                    f"Domain '{domain_name}' must have at least one skill"
                )
            for skill in skills:
                if not isinstance(skill, str) or not skill.strip():
                    raise ValueError(
                        f"Invalid skill in domain '{domain_name}': {skill!r}"
                    )
            # Check for duplicate skills within a domain
            if len(skills) != len(set(skills)):
                raise ValueError(
                    f"Domain '{domain_name}' has duplicate skills"
                )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def is_valid_domain(self, domain: str) -> bool:
        """Check if a domain exists in the taxonomy."""
        return domain in self._domains

    def is_valid_skill(self, skill_id: SkillId) -> bool:
        """Check if a skill exists in the taxonomy."""
        domain_data = self._domains.get(skill_id.domain)
        if domain_data is None:
            return False
        return skill_id.skill in domain_data["skills"]

    def all_domains(self) -> list[str]:
        """Return all domain names, sorted alphabetically."""
        return sorted(self._domains.keys())

    def domain_description(self, domain: str) -> str:
        """Return the description of a domain.

        Raises:
            KeyError: If the domain does not exist.
        """
        domain_data = self._domains.get(domain)
        if domain_data is None:
            raise KeyError(f"Unknown domain: {domain}")
        return domain_data.get("description", "")

    def skills_in_domain(self, domain: str) -> list[str]:
        """Return all skill names in a domain, in taxonomy order.

        Raises:
            KeyError: If the domain does not exist.
        """
        domain_data = self._domains.get(domain)
        if domain_data is None:
            raise KeyError(f"Unknown domain: {domain}")
        return list(domain_data["skills"])

    def all_skills(self) -> list[SkillId]:
        """Return all skills across all domains, sorted by canonical form."""
        result: list[SkillId] = []
        for domain_name, domain_data in self._domains.items():
            for skill_name in domain_data["skills"]:
                result.append(SkillId(domain=domain_name, skill=skill_name))
        result.sort(key=lambda s: s.canonical)
        return result

    def skill_count(self) -> int:
        """Return the total number of skills across all domains."""
        return sum(
            len(d["skills"]) for d in self._domains.values()
        )

    def domain_count(self) -> int:
        """Return the number of domains."""
        return len(self._domains)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_skill_id(self, skill_id: SkillId) -> list[str]:
        """Validate a SkillId against the taxonomy.

        Returns:
            Empty list if valid, list of error strings otherwise.
        """
        errors: list[str] = []
        if not self.is_valid_domain(skill_id.domain):
            errors.append(f"Unknown domain: '{skill_id.domain}'")
        elif not self.is_valid_skill(skill_id):
            errors.append(
                f"Unknown skill '{skill_id.skill}' in domain "
                f"'{skill_id.domain}'"
            )
        return errors

    def validate_requirements(
        self, requirements: list[SkillRequirement],
    ) -> list[str]:
        """Validate a list of skill requirements against the taxonomy.

        Returns:
            Empty list if all valid, list of error strings otherwise.
        """
        errors: list[str] = []
        seen: set[str] = set()

        for req in requirements:
            # Check for duplicates
            canonical = req.skill_id.canonical
            if canonical in seen:
                errors.append(f"Duplicate skill requirement: '{canonical}'")
            seen.add(canonical)

            # Validate against taxonomy
            skill_errors = self.validate_skill_id(req.skill_id)
            errors.extend(skill_errors)

        return errors

    @property
    def version(self) -> str:
        """Return the taxonomy version."""
        return self._data.get("version", "unknown")

    @property
    def governance_phase_required(self) -> str:
        """Return the governance phase required for taxonomy changes."""
        return self._data.get("governance_phase_required", "G1")
