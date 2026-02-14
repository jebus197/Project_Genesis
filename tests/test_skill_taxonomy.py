"""Unit tests for the skill taxonomy loader and validator.

Tests SkillTaxonomy against the canonical skill_taxonomy.json config.
"""

import pytest
from pathlib import Path
from typing import Any

from genesis.models.skill import SkillId, SkillRequirement
from genesis.skills.taxonomy import SkillTaxonomy


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def taxonomy() -> SkillTaxonomy:
    """Load from the real config file."""
    return SkillTaxonomy.from_config_dir(CONFIG_DIR)


@pytest.fixture
def minimal_taxonomy() -> SkillTaxonomy:
    """A minimal taxonomy for edge-case testing."""
    return SkillTaxonomy({
        "version": "test",
        "domains": {
            "alpha": {
                "description": "Alpha domain",
                "skills": ["a1", "a2"],
            },
            "beta": {
                "description": "Beta domain",
                "skills": ["b1"],
            },
        },
    })


# ===================================================================
# Loading and validation
# ===================================================================

class TestTaxonomyLoading:
    def test_loads_from_config_dir(self, taxonomy: SkillTaxonomy) -> None:
        """Real config file loads successfully."""
        assert taxonomy.domain_count() > 0
        assert taxonomy.skill_count() > 0

    def test_version(self, taxonomy: SkillTaxonomy) -> None:
        assert taxonomy.version == "0.1"

    def test_governance_phase(self, taxonomy: SkillTaxonomy) -> None:
        assert taxonomy.governance_phase_required == "G1"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Skill taxonomy not found"):
            SkillTaxonomy.from_config_dir(tmp_path)

    def test_missing_version_raises(self) -> None:
        with pytest.raises(ValueError, match="missing 'version'"):
            SkillTaxonomy({"domains": {"d": {"skills": ["s"]}}})

    def test_missing_domains_raises(self) -> None:
        with pytest.raises(ValueError, match="missing 'domains'"):
            SkillTaxonomy({"version": "1"})

    def test_empty_domain_skills_raises(self) -> None:
        with pytest.raises(ValueError, match="must have at least one skill"):
            SkillTaxonomy({
                "version": "1",
                "domains": {"empty": {"skills": []}},
            })

    def test_duplicate_skills_raises(self) -> None:
        with pytest.raises(ValueError, match="duplicate skills"):
            SkillTaxonomy({
                "version": "1",
                "domains": {"d": {"skills": ["s1", "s1"]}},
            })

    def test_blank_skill_name_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid skill"):
            SkillTaxonomy({
                "version": "1",
                "domains": {"d": {"skills": [""]}},
            })

    def test_missing_skills_key_raises(self) -> None:
        with pytest.raises(ValueError, match="missing 'skills' list"):
            SkillTaxonomy({
                "version": "1",
                "domains": {"d": {"description": "no skills key"}},
            })


# ===================================================================
# Domain queries
# ===================================================================

class TestDomainQueries:
    def test_all_domains_sorted(self, taxonomy: SkillTaxonomy) -> None:
        domains = taxonomy.all_domains()
        assert domains == sorted(domains)
        assert "software_engineering" in domains
        assert "documentation" in domains

    def test_is_valid_domain(self, taxonomy: SkillTaxonomy) -> None:
        assert taxonomy.is_valid_domain("software_engineering")
        assert taxonomy.is_valid_domain("data_science")
        assert not taxonomy.is_valid_domain("underwater_basket_weaving")

    def test_domain_description(self, taxonomy: SkillTaxonomy) -> None:
        desc = taxonomy.domain_description("software_engineering")
        assert "software" in desc.lower() or "engineering" in desc.lower()

    def test_domain_description_unknown_raises(self, taxonomy: SkillTaxonomy) -> None:
        with pytest.raises(KeyError, match="Unknown domain"):
            taxonomy.domain_description("nonexistent")

    def test_domain_count(self, taxonomy: SkillTaxonomy) -> None:
        assert taxonomy.domain_count() == 6  # from canonical config


# ===================================================================
# Skill queries
# ===================================================================

class TestSkillQueries:
    def test_skills_in_domain(self, taxonomy: SkillTaxonomy) -> None:
        skills = taxonomy.skills_in_domain("software_engineering")
        assert "python" in skills
        assert "rust" in skills

    def test_skills_in_domain_unknown_raises(self, taxonomy: SkillTaxonomy) -> None:
        with pytest.raises(KeyError, match="Unknown domain"):
            taxonomy.skills_in_domain("nonexistent")

    def test_is_valid_skill(self, taxonomy: SkillTaxonomy) -> None:
        assert taxonomy.is_valid_skill(SkillId("software_engineering", "python"))
        assert taxonomy.is_valid_skill(SkillId("data_science", "ml_pipelines"))
        assert not taxonomy.is_valid_skill(SkillId("software_engineering", "cobol"))
        assert not taxonomy.is_valid_skill(SkillId("nonexistent", "python"))

    def test_all_skills(self, taxonomy: SkillTaxonomy) -> None:
        all_skills = taxonomy.all_skills()
        assert len(all_skills) == taxonomy.skill_count()
        # Should be sorted by canonical form
        canonicals = [s.canonical for s in all_skills]
        assert canonicals == sorted(canonicals)

    def test_skill_count(self, taxonomy: SkillTaxonomy) -> None:
        # 5 + 4 + 3 + 3 + 3 + 3 = 21 from canonical config
        assert taxonomy.skill_count() == 21

    def test_all_skills_have_valid_domain(self, taxonomy: SkillTaxonomy) -> None:
        for skill in taxonomy.all_skills():
            assert taxonomy.is_valid_domain(skill.domain)


# ===================================================================
# Validation
# ===================================================================

class TestValidation:
    def test_validate_valid_skill_id(self, taxonomy: SkillTaxonomy) -> None:
        errors = taxonomy.validate_skill_id(
            SkillId("software_engineering", "python")
        )
        assert errors == []

    def test_validate_unknown_domain(self, taxonomy: SkillTaxonomy) -> None:
        errors = taxonomy.validate_skill_id(
            SkillId("nonexistent", "python")
        )
        assert len(errors) == 1
        assert "Unknown domain" in errors[0]

    def test_validate_unknown_skill(self, taxonomy: SkillTaxonomy) -> None:
        errors = taxonomy.validate_skill_id(
            SkillId("software_engineering", "cobol")
        )
        assert len(errors) == 1
        assert "Unknown skill" in errors[0]

    def test_validate_requirements_valid(self, taxonomy: SkillTaxonomy) -> None:
        reqs = [
            SkillRequirement(
                skill_id=SkillId("software_engineering", "python"),
                minimum_proficiency=0.5,
            ),
            SkillRequirement(
                skill_id=SkillId("data_science", "ml_pipelines"),
                minimum_proficiency=0.3,
                required=False,
            ),
        ]
        errors = taxonomy.validate_requirements(reqs)
        assert errors == []

    def test_validate_requirements_invalid_skill(self, taxonomy: SkillTaxonomy) -> None:
        reqs = [
            SkillRequirement(
                skill_id=SkillId("software_engineering", "cobol"),
            ),
        ]
        errors = taxonomy.validate_requirements(reqs)
        assert len(errors) == 1

    def test_validate_requirements_duplicate(self, taxonomy: SkillTaxonomy) -> None:
        reqs = [
            SkillRequirement(
                skill_id=SkillId("software_engineering", "python"),
            ),
            SkillRequirement(
                skill_id=SkillId("software_engineering", "python"),
                minimum_proficiency=0.5,
            ),
        ]
        errors = taxonomy.validate_requirements(reqs)
        assert any("Duplicate" in e for e in errors)

    def test_validate_requirements_empty_list(self, taxonomy: SkillTaxonomy) -> None:
        errors = taxonomy.validate_requirements([])
        assert errors == []


# ===================================================================
# Minimal taxonomy edge cases
# ===================================================================

class TestMinimalTaxonomy:
    def test_domain_count(self, minimal_taxonomy: SkillTaxonomy) -> None:
        assert minimal_taxonomy.domain_count() == 2

    def test_skill_count(self, minimal_taxonomy: SkillTaxonomy) -> None:
        assert minimal_taxonomy.skill_count() == 3  # a1, a2, b1

    def test_cross_domain_skill_invalid(self, minimal_taxonomy: SkillTaxonomy) -> None:
        """Skill 'a1' exists in 'alpha' but not in 'beta'."""
        assert minimal_taxonomy.is_valid_skill(SkillId("alpha", "a1"))
        assert not minimal_taxonomy.is_valid_skill(SkillId("beta", "a1"))
