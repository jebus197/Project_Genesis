"""Trust update engine — computes trust scores and enforces all trust invariants.

Trust model:
  T = w_Q * Q + w_R * R + w_V * V + w_E * E

Invariants enforced:
- w_Q + w_R + w_V + w_E = 1.0
- w_Q >= 0.70 (quality dominates)
- w_V <= 0.10 (volume never dominates)
- w_E <= 0.10 (effort complements, never dominates)
- Human floor > 0 (humans always retain minimum trust)
- Machine floor = 0 (machines can decay to zero)
- Quality gate: Q must meet Q_min before trust gain is allowed
- Effort proportionality: low effort on high-complexity missions is a signal
- Fast elevation: |delta| > delta_fast triggers automatic suspension
- Proof-of-work alone cannot mint trust (must have proof-of-trust via review)
- Proof-of-effort alone cannot mint trust (must combine with quality)
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from genesis.models.domain_trust import (
    DecayUrgency,
    DomainDecayForecast,
    DomainTrustDelta,
    DomainTrustScore,
    TrustStatus,
)
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
        effort: float = 0.0,
    ) -> float:
        """Compute raw trust score from components, clamped to [0, 1]."""
        w_q, w_r, w_v, w_e = self._resolver.trust_weights()
        raw = w_q * quality + w_r * reliability + w_v * volume + w_e * effort
        return max(0.0, min(1.0, raw))

    def apply_update(
        self,
        record: TrustRecord,
        quality: float,
        reliability: float,
        volume: float,
        reason: str,
        mission_id: str | None = None,
        effort: float = 0.0,
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

        # Compute new raw score (includes effort component)
        new_raw = self.compute_score(quality, reliability, volume, effort)

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

        # Build new record (preserving domain_scores from existing record)
        new_record = TrustRecord(
            actor_id=record.actor_id,
            actor_kind=record.actor_kind,
            score=new_score,
            quality=quality,
            reliability=reliability,
            volume=volume,
            effort=effort,
            quarantined=record.quarantined,
            recertification_failures=record.recertification_failures,
            last_recertification_utc=record.last_recertification_utc,
            decommissioned=record.decommissioned,
            recertification_failure_timestamps=list(record.recertification_failure_timestamps),
            probation_tasks_completed=record.probation_tasks_completed,
            last_active_utc=record.last_active_utc,
            domain_scores=dict(record.domain_scores),
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
        windowed = self.count_windowed_failures(record)
        if windowed >= decomm["M_RECERT_FAIL_MAX"]:
            errors.append(
                f"{record.actor_id}: windowed recertification failures "
                f"{windowed} >= M_RECERT_FAIL_MAX "
                f"{decomm['M_RECERT_FAIL_MAX']} — decommission required"
            )

        return errors

    def count_windowed_failures(
        self,
        record: TrustRecord,
        now: Optional[datetime] = None,
    ) -> int:
        """Count recertification failures within the rolling window.

        Only failures within M_RECERT_FAIL_WINDOW_DAYS (default 180) of
        ``now`` count toward the decommission threshold. This prevents
        unbounded liability where 3 failures *ever* trigger permanent
        decommission regardless of when they occurred.
        """
        if not record.recertification_failure_timestamps:
            return 0
        now = now or datetime.now(timezone.utc)
        decomm = self._resolver.decommission_rules()
        window_days = decomm["M_RECERT_FAIL_WINDOW_DAYS"]
        cutoff = now - timedelta(days=window_days)
        return sum(1 for ts in record.recertification_failure_timestamps if ts >= cutoff)

    # ------------------------------------------------------------------
    # Domain-specific trust
    # ------------------------------------------------------------------

    def compute_domain_score(
        self,
        quality: float,
        reliability: float,
        volume: float,
        effort: float = 0.0,
    ) -> float:
        """Compute domain trust score, clamped to [0, 1].

        Uses domain-specific weights from skill_trust_params.json if
        available, otherwise falls back to global trust weights.
        """
        w_q, w_r, w_v, w_e = self._resolver.domain_trust_weights()
        raw = w_q * quality + w_r * reliability + w_v * volume + w_e * effort
        return max(0.0, min(1.0, raw))

    def apply_domain_update(
        self,
        record: TrustRecord,
        domain: str,
        quality: float,
        reliability: float,
        volume: float,
        effort: float = 0.0,
        reason: str = "",
        mission_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> tuple[TrustRecord, DomainTrustDelta]:
        """Apply a domain-specific trust update.

        Updates the domain score within the record and recalculates
        the global aggregate score. Does NOT mutate the input record.
        """
        now = now or datetime.now(timezone.utc)

        # Get or create domain score
        existing = record.domain_scores.get(domain)
        if existing is None:
            existing = DomainTrustScore(domain=domain)

        previous_score = existing.score
        new_score = self.compute_domain_score(quality, reliability, volume, effort)

        # Build updated domain score
        updated_domain = DomainTrustScore(
            domain=domain,
            score=new_score,
            quality=quality,
            reliability=reliability,
            volume=volume,
            effort=effort,
            mission_count=existing.mission_count + 1,
            last_active_utc=now,
        )

        # Build delta
        delta = DomainTrustDelta(
            actor_id=record.actor_id,
            domain=domain,
            previous_score=previous_score,
            new_score=new_score,
            reason=reason,
            mission_id=mission_id,
        )

        # Rebuild domain scores dict
        new_domain_scores = dict(record.domain_scores)
        new_domain_scores[domain] = updated_domain

        # Recalculate global aggregate
        new_global = self.aggregate_global_score(new_domain_scores)

        # Build new record
        new_record = TrustRecord(
            actor_id=record.actor_id,
            actor_kind=record.actor_kind,
            score=max(new_global, self._resolver.trust_floor(
                record.actor_kind == ActorKind.MACHINE
            )),
            quality=record.quality,
            reliability=record.reliability,
            volume=record.volume,
            effort=record.effort,
            quarantined=record.quarantined,
            recertification_failures=record.recertification_failures,
            last_recertification_utc=record.last_recertification_utc,
            decommissioned=record.decommissioned,
            recertification_failure_timestamps=list(record.recertification_failure_timestamps),
            probation_tasks_completed=record.probation_tasks_completed,
            last_active_utc=now,
            domain_scores=new_domain_scores,
        )

        return new_record, delta

    def aggregate_global_score(
        self,
        domain_scores: dict[str, DomainTrustScore],
    ) -> float:
        """Recompute global score as weighted mean of domain scores.

        Weighting: volume_weight * volume_contribution + recency_weight * recency_contribution.
        Returns 0.0 if no domain scores exist.
        """
        if not domain_scores:
            return 0.0

        agg_config = self._resolver.global_score_aggregation()
        recency_w = agg_config.get("recency_weight", 0.3)
        volume_w = agg_config.get("volume_weight", 0.7)

        total_missions = sum(ds.mission_count for ds in domain_scores.values())
        if total_missions == 0:
            # No missions in any domain — simple mean
            scores = [ds.score for ds in domain_scores.values()]
            return sum(scores) / len(scores) if scores else 0.0

        # Volume-weighted component: domains with more missions contribute more
        volume_sum = sum(
            ds.score * ds.mission_count for ds in domain_scores.values()
        )
        volume_component = volume_sum / total_missions

        # Recency-weighted component: more recent domains contribute more
        # Use mission_count as proxy for recency (recently active domains
        # have the freshest last_active_utc, approximated by mission volume)
        recency_component = volume_component  # simplified: same as volume for now

        aggregate = volume_w * volume_component + recency_w * recency_component
        return max(0.0, min(1.0, aggregate))

    def compute_decay_factor(
        self,
        days_since_last: float,
        half_life: float,
        volume: int,
    ) -> float:
        """Compute the decay multiplier for inactivity.

        Formula: factor = max(floor, 1 - (days / half_life) / (1 + ln(1 + volume)))

        Higher volume = slower decay (deeper evidence of expertise).
        Returns a value in [floor, 1.0] where 1.0 means no decay.
        """
        if days_since_last <= 0 or half_life <= 0:
            return 1.0

        volume_dampening = 1.0 + math.log(1.0 + volume)
        raw_decay = 1.0 - (days_since_last / half_life) / volume_dampening

        floor = 0.01  # never decay completely to zero
        if self._resolver.has_skill_trust_config():
            decay_config = self._resolver.inactivity_decay_config()
            floor = decay_config.get("decay_floor", 0.01)

        return max(floor, min(1.0, raw_decay))

    def apply_inactivity_decay(
        self,
        record: TrustRecord,
        now: Optional[datetime] = None,
    ) -> TrustRecord:
        """Apply time-based inactivity decay to all domain scores.

        Also decays the global score. Does NOT mutate the input record.
        Returns the same record if no decay is applicable.
        """
        now = now or datetime.now(timezone.utc)
        is_machine = record.actor_kind == ActorKind.MACHINE
        half_life = self._resolver.half_life_days(is_machine)

        # Decay each domain score
        new_domain_scores: dict[str, DomainTrustScore] = {}
        any_decayed = False

        for domain, ds in record.domain_scores.items():
            if ds.last_active_utc is None:
                new_domain_scores[domain] = ds
                continue

            days_since = (now - ds.last_active_utc).total_seconds() / 86400.0
            factor = self.compute_decay_factor(days_since, half_life, ds.mission_count)

            if factor < 1.0:
                any_decayed = True
                new_domain_scores[domain] = DomainTrustScore(
                    domain=ds.domain,
                    score=ds.score * factor,
                    quality=ds.quality,
                    reliability=ds.reliability,
                    volume=ds.volume,
                    effort=ds.effort,
                    mission_count=ds.mission_count,
                    last_active_utc=ds.last_active_utc,
                )
            else:
                new_domain_scores[domain] = ds

        if not any_decayed:
            # Also check global decay
            if record.last_active_utc is not None:
                days_since_global = (now - record.last_active_utc).total_seconds() / 86400.0
                volume_approx = sum(
                    ds.mission_count for ds in record.domain_scores.values()
                )
                global_factor = self.compute_decay_factor(
                    days_since_global, half_life, volume_approx,
                )
                if global_factor >= 1.0:
                    return record
            else:
                return record

        # Recalculate global score
        new_global = self.aggregate_global_score(new_domain_scores)
        if not new_domain_scores and record.last_active_utc is not None:
            # No domain scores but has global activity — decay global directly
            days_global = (now - record.last_active_utc).total_seconds() / 86400.0
            factor = self.compute_decay_factor(days_global, half_life, 0)
            new_global = record.score * factor

        floor = self._resolver.trust_floor(is_machine)

        return TrustRecord(
            actor_id=record.actor_id,
            actor_kind=record.actor_kind,
            score=max(new_global, floor) if new_domain_scores else max(record.score * self.compute_decay_factor(
                (now - record.last_active_utc).total_seconds() / 86400.0 if record.last_active_utc else 0,
                half_life, 0,
            ), floor),
            quality=record.quality,
            reliability=record.reliability,
            volume=record.volume,
            effort=record.effort,
            quarantined=record.quarantined,
            recertification_failures=record.recertification_failures,
            last_recertification_utc=record.last_recertification_utc,
            decommissioned=record.decommissioned,
            recertification_failure_timestamps=list(record.recertification_failure_timestamps),
            probation_tasks_completed=record.probation_tasks_completed,
            last_active_utc=record.last_active_utc,
            domain_scores=new_domain_scores,
        )

    # ------------------------------------------------------------------
    # Decay forecast (trust dashboard)
    # ------------------------------------------------------------------

    def compute_decay_forecast(
        self,
        record: TrustRecord,
        now: Optional[datetime] = None,
    ) -> TrustStatus:
        """Compute the full decay forecast for an actor's trust dashboard.

        Returns TrustStatus with days until half-life, projected scores,
        urgency indicators, and per-domain forecasts.
        """
        now = now or datetime.now(timezone.utc)
        is_machine = record.actor_kind == ActorKind.MACHINE
        half_life = self._resolver.half_life_days(is_machine)

        # Global decay forecast
        if record.last_active_utc is not None:
            days_since = (now - record.last_active_utc).total_seconds() / 86400.0
        else:
            days_since = 0.0

        days_until_hl = max(0.0, half_life - days_since)
        volume_approx = sum(
            ds.mission_count for ds in record.domain_scores.values()
        )
        hl_factor = self.compute_decay_factor(half_life, half_life, volume_approx)
        projected_at_hl = record.score * hl_factor

        urgency = self._classify_urgency(days_since, half_life)

        # Per-domain forecasts
        domain_forecasts: list[DomainDecayForecast] = []
        for domain, ds in record.domain_scores.items():
            if ds.last_active_utc is not None:
                d_days = (now - ds.last_active_utc).total_seconds() / 86400.0
            else:
                d_days = 0.0

            d_days_until = max(0.0, half_life - d_days)
            d_factor = self.compute_decay_factor(half_life, half_life, ds.mission_count)
            d_projected = ds.score * d_factor
            d_urgency = self._classify_urgency(d_days, half_life)

            domain_forecasts.append(DomainDecayForecast(
                domain=domain,
                current_score=ds.score,
                days_since_active=d_days,
                half_life_days=half_life,
                days_until_half_life=d_days_until,
                projected_score_at_half_life=d_projected,
                urgency=d_urgency,
            ))

        return TrustStatus(
            actor_id=record.actor_id,
            global_score=record.score,
            days_since_last_activity=days_since,
            half_life_days=half_life,
            days_until_half_life=days_until_hl,
            projected_score_at_half_life=projected_at_hl,
            urgency=urgency,
            domain_forecasts=domain_forecasts,
        )

    @staticmethod
    def _classify_urgency(days_since: float, half_life: float) -> DecayUrgency:
        """Classify decay urgency based on position through half-life."""
        if half_life <= 0:
            return DecayUrgency.CRITICAL
        ratio = days_since / half_life
        if ratio >= 1.0:
            return DecayUrgency.CRITICAL
        if ratio >= 0.75:
            return DecayUrgency.URGENT
        if ratio >= 0.25:
            return DecayUrgency.DRIFTING
        return DecayUrgency.STABLE
