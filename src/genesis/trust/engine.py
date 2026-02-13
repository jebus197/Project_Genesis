"""Trust update engine — computes trust scores and enforces all trust invariants.

Trust model:
  T = w_Q * Q + w_R * R + w_V * V

Invariants enforced:
- w_Q + w_R + w_V = 1.0
- w_Q >= 0.70 (quality dominates)
- w_V <= 0.10 (volume never dominates)
- Human floor > 0 (humans always retain minimum trust)
- Machine floor = 0 (machines can decay to zero)
- Quality gate: Q must meet Q_min before trust gain is allowed
- Fast elevation: |delta| > delta_fast triggers automatic suspension
- Proof-of-work alone cannot mint trust (must have proof-of-trust via review)
"""

from __future__ import annotations

from genesis.models.trust import ActorKind, TrustDelta, TrustRecord
from genesis.policy.resolver import PolicyResolver


class TrustEngine:
    """Computes and validates trust score changes."""

    def __init__(self, resolver: PolicyResolver) -> None:
        self._resolver = resolver

    def compute_score(
        self,
        quality: float,
        reliability: float,
        volume: float,
    ) -> float:
        """Compute raw trust score from components."""
        w_q, w_r, w_v = self._resolver.trust_weights()
        return w_q * quality + w_r * reliability + w_v * volume

    def apply_update(
        self,
        record: TrustRecord,
        quality: float,
        reliability: float,
        volume: float,
        reason: str,
        mission_id: str | None = None,
    ) -> tuple[TrustRecord, TrustDelta]:
        """Apply a trust update and return the new record + delta.

        Enforces:
        1. Quality gate — no trust gain if Q < Q_min.
        2. Trust floor — score cannot drop below floor.
        3. Fast elevation — flags suspension if delta exceeds threshold.

        Does NOT mutate the input record. Returns new copies.
        """
        is_machine = record.actor_kind == ActorKind.MACHINE
        q_min = self._resolver.quality_gate(is_machine)
        floor = self._resolver.trust_floor(is_machine)
        delta_fast = self._resolver.delta_fast()

        # Compute new raw score
        new_raw = self.compute_score(quality, reliability, volume)

        # Quality gate: if Q < Q_min, no trust gain allowed
        if quality < q_min and new_raw > record.score:
            new_raw = record.score  # Clamp to current (no gain)

        # Trust floor enforcement
        new_score = max(new_raw, floor)

        # Decommissioned actors cannot gain trust
        if record.decommissioned and new_score > record.score:
            new_score = record.score

        # Quarantined actors cannot gain trust
        if record.quarantined and new_score > record.score:
            new_score = record.score

        # Build delta
        suspended = abs(new_score - record.score) > delta_fast
        delta = TrustDelta(
            actor_id=record.actor_id,
            actor_kind=record.actor_kind,
            previous_score=record.score,
            new_score=new_score,
            reason=reason,
            mission_id=mission_id,
            suspended=suspended,
        )

        # Build new record
        new_record = TrustRecord(
            actor_id=record.actor_id,
            actor_kind=record.actor_kind,
            score=new_score,
            quality=quality,
            reliability=reliability,
            volume=volume,
            quarantined=record.quarantined,
            recertification_failures=record.recertification_failures,
            last_recertification_utc=record.last_recertification_utc,
            decommissioned=record.decommissioned,
            last_active_utc=record.last_active_utc,
        )

        return new_record, delta

    def check_recertification(self, record: TrustRecord) -> list[str]:
        """Check if a machine actor needs or fails recertification.

        Returns list of issues. Empty = healthy.
        """
        errors: list[str] = []
        if record.actor_kind != ActorKind.MACHINE:
            return errors

        reqs = self._resolver.recertification_requirements()

        if record.quality < reqs["RECERT_CORRECTNESS_MIN"]:
            errors.append(
                f"{record.actor_id}: quality {record.quality:.3f} "
                f"< RECERT_CORRECTNESS_MIN {reqs['RECERT_CORRECTNESS_MIN']}"
            )

        if record.reliability < reqs["RECERT_REPRO_MIN"]:
            errors.append(
                f"{record.actor_id}: reliability {record.reliability:.3f} "
                f"< RECERT_REPRO_MIN {reqs['RECERT_REPRO_MIN']}"
            )

        decomm = self._resolver.decommission_rules()
        if record.recertification_failures >= decomm["M_RECERT_FAIL_MAX"]:
            errors.append(
                f"{record.actor_id}: recertification failures "
                f"{record.recertification_failures} >= M_RECERT_FAIL_MAX "
                f"{decomm['M_RECERT_FAIL_MAX']} — decommission required"
            )

        return errors
