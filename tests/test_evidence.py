"""Tests for evidence validator — proves schema enforcement blocks bad submissions."""

import pytest

from genesis.engine.evidence import EvidenceValidator
from genesis.models.mission import (
    DomainType,
    EvidenceRecord,
    Mission,
    MissionClass,
    MissionState,
    RiskTier,
)


@pytest.fixture
def validator() -> EvidenceValidator:
    return EvidenceValidator()


class TestRecordValidation:
    def test_valid_record(self, validator: EvidenceValidator) -> None:
        record = EvidenceRecord(
            artifact_hash="sha256:5f2d8cb0325f4dc8c713f67c6482dfe4512b7064c9201022fc07012e31cb4037",
            signature="ed25519:8d43f2d567fa0c2ac4e13ab72d7f539ca4301e1a5ec2f7108e8f4b7b61a0c16f",
        )
        assert validator.validate_record(record) == []

    def test_missing_hash(self, validator: EvidenceValidator) -> None:
        record = EvidenceRecord(artifact_hash="", signature="ed25519:abcdef" + "0" * 58)
        errors = validator.validate_record(record)
        assert any("artifact_hash" in e for e in errors)

    def test_missing_signature(self, validator: EvidenceValidator) -> None:
        record = EvidenceRecord(
            artifact_hash="sha256:" + "a" * 64,
            signature="",
        )
        errors = validator.validate_record(record)
        assert any("signature" in e for e in errors)

    def test_bad_hash_format(self, validator: EvidenceValidator) -> None:
        record = EvidenceRecord(
            artifact_hash="md5:not_sha256",
            signature="ed25519:" + "a" * 64,
        )
        errors = validator.validate_record(record)
        assert any("sha256" in e for e in errors)

    def test_bad_sig_format(self, validator: EvidenceValidator) -> None:
        record = EvidenceRecord(
            artifact_hash="sha256:" + "a" * 64,
            signature="rsa:" + "a" * 64,
        )
        errors = validator.validate_record(record)
        assert any("ed25519" in e for e in errors)


class TestMissionEvidence:
    def test_mission_with_no_evidence_fails(self, validator: EvidenceValidator) -> None:
        mission = Mission(
            mission_id="M-NOEV",
            mission_title="No evidence",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            evidence=[],
        )
        errors = validator.validate_mission_evidence(mission)
        assert len(errors) == 1
        assert "at least one" in errors[0]

    def test_mission_with_valid_evidence(self, validator: EvidenceValidator) -> None:
        mission = Mission(
            mission_id="M-GOOD",
            mission_title="Good evidence",
            mission_class=MissionClass.DOCUMENTATION_UPDATE,
            risk_tier=RiskTier.R0,
            domain_type=DomainType.OBJECTIVE,
            evidence=[
                EvidenceRecord(
                    artifact_hash="sha256:" + "b" * 64,
                    signature="ed25519:" + "c" * 64,
                ),
            ],
        )
        errors = validator.validate_mission_evidence(mission)
        assert errors == []
