"""Evidence validator — enforces evidence schema and integrity rules.

Every mission must include at least one evidence record before completion.
Each evidence record requires:
- artifact_hash: SHA-256 prefixed hash.
- signature: Ed25519 prefixed signature.

Incomplete evidence submissions are blocked (acceptance rate target = 0).
"""

from __future__ import annotations

import re

from genesis.models.mission import EvidenceRecord, Mission


# Expected hash and signature prefix patterns
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_ED25519_PATTERN = re.compile(r"^ed25519:[0-9a-f]{64,128}$")


class EvidenceValidator:
    """Validates evidence records against constitutional schema rules."""

    def validate_record(self, record: EvidenceRecord) -> list[str]:
        """Validate a single evidence record. Returns list of errors."""
        errors: list[str] = []

        if not record.artifact_hash:
            errors.append("evidence record missing artifact_hash")
        elif not _SHA256_PATTERN.match(record.artifact_hash):
            errors.append(
                f"artifact_hash must match sha256:<64-hex-chars>, "
                f"got: {record.artifact_hash[:40]}..."
            )

        if not record.signature:
            errors.append("evidence record missing signature")
        elif not _ED25519_PATTERN.match(record.signature):
            errors.append(
                f"signature must match ed25519:<64-128-hex-chars>, "
                f"got: {record.signature[:40]}..."
            )

        return errors

    def validate_mission_evidence(self, mission: Mission) -> list[str]:
        """Validate all evidence records on a mission.

        Returns list of errors. Empty list = valid.
        """
        errors: list[str] = []

        if not mission.evidence:
            errors.append(
                f"{mission.mission_id}: must include at least one evidence record"
            )
            return errors

        for idx, record in enumerate(mission.evidence):
            record_errors = self.validate_record(record)
            for err in record_errors:
                errors.append(f"{mission.mission_id} evidence[{idx}]: {err}")

        return errors
