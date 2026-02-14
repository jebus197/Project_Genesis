"""Worker matcher — combines skill relevance, trust, and availability.

Ranks workers for mission allocation using:
  bid_score = w_relevance * relevance + w_global * global_trust + w_domain * domain_trust

Pure computation engine. The service layer handles side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from genesis.models.domain_trust import DomainTrustScore
from genesis.models.skill import ActorSkillProfile, SkillRequirement
from genesis.models.trust import TrustRecord
from genesis.policy.resolver import PolicyResolver
from genesis.review.roster import ActorRoster, RosterEntry
from genesis.skills.matching import SkillMatchEngine


@dataclass(frozen=True)
class WorkerMatch:
    """A ranked worker match result."""
    actor_id: str
    relevance_score: float
    global_trust: float
    domain_trust: float
    composite_score: float


class WorkerMatcher:
    """Finds and ranks workers for mission allocation.

    Usage:
        matcher = WorkerMatcher(resolver, roster, trust_records, skill_profiles)
        matches = matcher.find_matches(requirements)
        # matches is sorted by composite_score descending
    """

    def __init__(
        self,
        resolver: PolicyResolver,
        roster: ActorRoster,
        trust_records: dict[str, TrustRecord],
        skill_profiles: dict[str, ActorSkillProfile],
    ) -> None:
        self._resolver = resolver
        self._roster = roster
        self._trust_records = trust_records
        self._skill_profiles = skill_profiles
        self._match_engine = SkillMatchEngine(resolver)

    def find_matches(
        self,
        requirements: list[SkillRequirement],
        exclude_ids: set[str] | None = None,
        min_trust: float = 0.0,
        limit: int = 10,
    ) -> list[WorkerMatch]:
        """Find and rank workers matching the given skill requirements.

        Args:
            requirements: Mission skill requirements to match against.
            exclude_ids: Actor IDs to exclude (e.g. mission creator).
            min_trust: Minimum global trust score.
            limit: Maximum number of results.

        Returns:
            List of WorkerMatch, sorted by composite_score descending.
        """
        exclude = exclude_ids or set()
        w_rel, w_global, w_domain = self._allocation_weights()

        matches: list[WorkerMatch] = []
        for entry in self._roster.all_actors():
            if not entry.is_available():
                continue
            if entry.actor_id in exclude:
                continue
            if entry.trust_score < min_trust:
                continue

            profile = self._skill_profiles.get(entry.actor_id)
            trust_record = self._trust_records.get(entry.actor_id)

            # Compute relevance
            relevance = self._match_engine.compute_relevance(
                profile, requirements, trust_record,
            )

            # Check minimum relevance (skip if below threshold and requirements exist)
            if requirements and not self._match_engine.meets_minimum_relevance(
                profile, requirements, trust_record,
            ):
                continue

            # Global trust
            global_trust = trust_record.score if trust_record else 0.0

            # Domain trust: average across required domains
            domain_trust = 0.0
            if trust_record and requirements:
                domains = {r.skill_id.domain for r in requirements}
                domain_scores = [
                    trust_record.domain_scores[d].score
                    for d in domains
                    if d in trust_record.domain_scores
                ]
                if domain_scores:
                    domain_trust = sum(domain_scores) / len(domains)

            composite = (
                w_rel * relevance
                + w_global * global_trust
                + w_domain * domain_trust
            )

            matches.append(WorkerMatch(
                actor_id=entry.actor_id,
                relevance_score=relevance,
                global_trust=global_trust,
                domain_trust=domain_trust,
                composite_score=composite,
            ))

        # Sort by composite score descending, then by relevance (tie-break)
        matches.sort(key=lambda m: (-m.composite_score, -m.relevance_score))

        return matches[:limit]

    def _allocation_weights(self) -> tuple[float, float, float]:
        """Return (w_relevance, w_global_trust, w_domain_trust)."""
        if not self._resolver.has_skill_trust_config():
            return (0.50, 0.20, 0.30)
        config = self._resolver.skill_matching_config()
        alloc = config.get("worker_allocation_weights", {})
        return (
            alloc.get("relevance", 0.50),
            alloc.get("global_trust", 0.20),
            alloc.get("domain_trust", 0.30),
        )
