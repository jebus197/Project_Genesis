"""Unit tests for skill data models.

Tests SkillId, SkillProficiency, ActorSkillProfile, SkillRequirement.
"""

import pytest
from datetime import datetime, timezone

from genesis.models.skill import (
    ActorSkillProfile,
    SkillId,
    SkillProficiency,
    SkillRequirement,
)


# ===================================================================
# SkillId
# ===================================================================

class TestSkillId:
    def test_canonical_form(self) -> None:
        sid = SkillId(domain="software_engineering", skill="python")
        assert sid.canonical == "software_engineering:python"

    def test_str_returns_canonical(self) -> None:
        sid = SkillId(domain="data_science", skill="ml_pipelines")
        assert str(sid) == "data_science:ml_pipelines"

    def test_parse_valid(self) -> None:
        sid = SkillId.parse("legal_analysis:contract_review")
        assert sid.domain == "legal_analysis"
        assert sid.skill == "contract_review"

    def test_parse_preserves_colons_in_skill(self) -> None:
        """Skill names with colons are allowed (split on first colon only)."""
        sid = SkillId.parse("domain:skill:extra")
        assert sid.domain == "domain"
        assert sid.skill == "skill:extra"

    def test_parse_no_colon_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid skill ID format"):
            SkillId.parse("nocolon")

    def test_parse_empty_domain_raises(self) -> None:
        with pytest.raises(ValueError, match="Both domain and skill must be non-empty"):
            SkillId.parse(":skill")

    def test_parse_empty_skill_raises(self) -> None:
        with pytest.raises(ValueError, match="Both domain and skill must be non-empty"):
            SkillId.parse("domain:")

    def test_equality(self) -> None:
        a = SkillId(domain="se", skill="py")
        b = SkillId(domain="se", skill="py")
        assert a == b

    def test_inequality(self) -> None:
        a = SkillId(domain="se", skill="py")
        b = SkillId(domain="se", skill="rust")
        assert a != b

    def test_hashable(self) -> None:
        """SkillId is frozen, so it should be hashable."""
        sid = SkillId(domain="se", skill="py")
        s = {sid}
        assert sid in s


# ===================================================================
# SkillProficiency
# ===================================================================

class TestSkillProficiency:
    def test_valid_proficiency(self) -> None:
        sp = SkillProficiency(
            skill_id=SkillId("se", "python"),
            proficiency_score=0.75,
            evidence_count=10,
        )
        assert sp.proficiency_score == 0.75
        assert sp.evidence_count == 10
        assert sp.source == "outcome_derived"

    def test_boundary_zero(self) -> None:
        sp = SkillProficiency(
            skill_id=SkillId("se", "python"),
            proficiency_score=0.0,
            evidence_count=0,
        )
        assert sp.proficiency_score == 0.0

    def test_boundary_one(self) -> None:
        sp = SkillProficiency(
            skill_id=SkillId("se", "python"),
            proficiency_score=1.0,
            evidence_count=100,
        )
        assert sp.proficiency_score == 1.0

    def test_invalid_proficiency_too_high(self) -> None:
        with pytest.raises(ValueError, match="proficiency_score must be in"):
            SkillProficiency(
                skill_id=SkillId("se", "python"),
                proficiency_score=1.1,
                evidence_count=0,
            )

    def test_invalid_proficiency_negative(self) -> None:
        with pytest.raises(ValueError, match="proficiency_score must be in"):
            SkillProficiency(
                skill_id=SkillId("se", "python"),
                proficiency_score=-0.1,
                evidence_count=0,
            )

    def test_invalid_source(self) -> None:
        with pytest.raises(ValueError, match="source must be one of"):
            SkillProficiency(
                skill_id=SkillId("se", "python"),
                proficiency_score=0.5,
                evidence_count=0,
                source="magic",
            )

    def test_all_valid_sources(self) -> None:
        for source in ("outcome_derived", "peer_endorsed", "self_declared"):
            sp = SkillProficiency(
                skill_id=SkillId("se", "python"),
                proficiency_score=0.5,
                evidence_count=0,
                source=source,
            )
            assert sp.source == source

    def test_display_score(self) -> None:
        """display_score() maps internal 0.0-1.0 to display 0-1000."""
        cases = [
            (0.0, 0),
            (0.001, 1),
            (0.010, 10),
            (0.100, 100),
            (0.500, 500),
            (0.750, 750),
            (1.000, 1000),
            (0.0005, 0),      # round(0.5) = 0 (banker's rounding)
            (0.0015, 2),      # round(1.5) = 2 (banker's rounding)
            (0.9999, 1000),   # rounds 999.9 -> 1000
        ]
        for internal, expected in cases:
            sp = SkillProficiency(
                skill_id=SkillId("se", "python"),
                proficiency_score=internal,
                evidence_count=1,
            )
            assert sp.display_score() == expected, (
                f"display_score({internal}) = {sp.display_score()}, "
                f"expected {expected}"
            )

    def test_with_timestamp(self) -> None:
        now = datetime.now(timezone.utc)
        sp = SkillProficiency(
            skill_id=SkillId("se", "python"),
            proficiency_score=0.5,
            evidence_count=5,
            last_demonstrated_utc=now,
        )
        assert sp.last_demonstrated_utc == now


# ===================================================================
# ActorSkillProfile
# ===================================================================

class TestActorSkillProfile:
    @pytest.fixture
    def sample_profile(self) -> ActorSkillProfile:
        """A profile with skills across two domains."""
        profile = ActorSkillProfile(actor_id="worker-1")
        profile.skills = {
            "software_engineering:python": SkillProficiency(
                skill_id=SkillId("software_engineering", "python"),
                proficiency_score=0.9,
                evidence_count=20,
            ),
            "software_engineering:rust": SkillProficiency(
                skill_id=SkillId("software_engineering", "rust"),
                proficiency_score=0.6,
                evidence_count=5,
            ),
            "data_science:ml_pipelines": SkillProficiency(
                skill_id=SkillId("data_science", "ml_pipelines"),
                proficiency_score=0.4,
                evidence_count=3,
            ),
        }
        return profile

    def test_get_proficiency_exists(self, sample_profile: ActorSkillProfile) -> None:
        sp = sample_profile.get_proficiency(SkillId("software_engineering", "python"))
        assert sp is not None
        assert sp.proficiency_score == 0.9

    def test_get_proficiency_missing(self, sample_profile: ActorSkillProfile) -> None:
        sp = sample_profile.get_proficiency(SkillId("legal_analysis", "contract_review"))
        assert sp is None

    def test_has_skill(self, sample_profile: ActorSkillProfile) -> None:
        assert sample_profile.has_skill(SkillId("software_engineering", "python"))
        assert not sample_profile.has_skill(SkillId("legal_analysis", "contract_review"))

    def test_domain_proficiency(self, sample_profile: ActorSkillProfile) -> None:
        # software_engineering: avg(0.9, 0.6) = 0.75
        assert sample_profile.domain_proficiency("software_engineering") == pytest.approx(0.75)
        # data_science: avg(0.4) = 0.4
        assert sample_profile.domain_proficiency("data_science") == pytest.approx(0.4)

    def test_domain_proficiency_unknown_domain(self, sample_profile: ActorSkillProfile) -> None:
        assert sample_profile.domain_proficiency("legal_analysis") == 0.0

    def test_recompute_primary_domains(self, sample_profile: ActorSkillProfile) -> None:
        sample_profile.recompute_primary_domains()
        # software_engineering (0.75 avg) > data_science (0.4 avg)
        assert sample_profile.primary_domains == [
            "software_engineering",
            "data_science",
        ]

    def test_empty_profile(self) -> None:
        profile = ActorSkillProfile(actor_id="empty")
        assert profile.domain_proficiency("any") == 0.0
        profile.recompute_primary_domains()
        assert profile.primary_domains == []


# ===================================================================
# SkillRequirement
# ===================================================================

class TestSkillRequirement:
    def test_valid_requirement(self) -> None:
        req = SkillRequirement(
            skill_id=SkillId("software_engineering", "python"),
            minimum_proficiency=0.5,
            required=True,
        )
        assert req.minimum_proficiency == 0.5
        assert req.required is True

    def test_default_values(self) -> None:
        req = SkillRequirement(
            skill_id=SkillId("se", "py"),
        )
        assert req.minimum_proficiency == 0.0
        assert req.required is True

    def test_optional_requirement(self) -> None:
        req = SkillRequirement(
            skill_id=SkillId("se", "py"),
            minimum_proficiency=0.3,
            required=False,
        )
        assert req.required is False

    def test_invalid_proficiency_too_high(self) -> None:
        with pytest.raises(ValueError, match="minimum_proficiency must be in"):
            SkillRequirement(
                skill_id=SkillId("se", "py"),
                minimum_proficiency=1.5,
            )

    def test_invalid_proficiency_negative(self) -> None:
        with pytest.raises(ValueError, match="minimum_proficiency must be in"):
            SkillRequirement(
                skill_id=SkillId("se", "py"),
                minimum_proficiency=-0.1,
            )
