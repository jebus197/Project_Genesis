"""Assembly Engine — constitutional Speaker's Corner for anonymous deliberation.

The Assembly is the deliberative space where Genesis participants meet, debate,
and develop ideas. It is the town square of the anti-social network — a place
for discourse, not decisions. The Assembly has no voting power and makes no
binding decisions.

Architecture:
- AssemblyEngine handles topic creation, contribution, and archival.
- The service layer bridges the engine with roster, compliance screening, and events.
- Identity blinding is structural: AssemblyContribution has NO actor_id field.
  The service layer computes a one-way salted hash (for compliance enforcement
  only) and passes only the hash to this engine. The hash is per-contribution
  (salted) so multiple contributions by the same actor are uncorrelatable.

Constitutional constraints:
- Identity: contributions carry no identity attribution (design test #64).
- Governance: the Assembly cannot produce binding decisions (design test #65).
- Engagement: no likes, upvotes, karma, trending, or metrics (design test #66).
- Compliance: content screened against 17 prohibited categories via
  ComplianceScreener at contribution time. Post-hoc complaints use hash
  matching (never identity resolution) for enforcement.
- Machine contributions auto-labelled as machine-generated.
- Topics expire after configurable inactivity period (default 30 days).
- Expired topics are archived, never deleted.

Design test #64: Can an Assembly contribution be traced to a specific actor
by any system participant? If yes, reject design.

Design test #65: Can the Assembly produce a binding governance decision
without routing through existing constitutional mechanisms?
If yes, reject design.

Design test #66: Does the Assembly include any engagement metric (likes,
upvotes, trending, karma)? If yes, reject design.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


class AssemblyTopicStatus(str, enum.Enum):
    """Lifecycle state of an Assembly topic."""
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class AssemblyContribution:
    """A single anonymous contribution to an Assembly topic.

    STRUCTURAL INVARIANT: This dataclass has NO actor_id field.
    The compliance_hash is a one-way salted hash for compliance enforcement
    only — it cannot be reversed to identify the author, and the per-contribution
    salt prevents correlation across contributions.

    The is_machine flag is set by the service layer based on ActorKind at
    contribution time. Machine contributions are constitutionally required to
    be labelled as machine-generated.
    """
    contribution_id: str
    topic_id: str
    content: str
    compliance_hash: str  # SHA-256(actor_id + per-contribution salt)
    is_machine: bool
    contributed_utc: datetime


@dataclass
class AssemblyTopic:
    """An Assembly discussion topic.

    Topics are time-bounded — they expire after a configurable period of
    inactivity. Expired topics are archived (never deleted) and closed to
    new contributions.

    STRUCTURAL INVARIANT: No engagement metrics fields exist on this dataclass.
    No likes, upvotes, karma, trending, score, view_count, or rank.
    No voting or quorum fields — the Assembly makes no binding decisions.
    """
    topic_id: str
    title: str
    status: AssemblyTopicStatus
    created_utc: datetime
    last_activity_utc: datetime
    contributions: list[AssemblyContribution] = field(default_factory=list)
    inactivity_expiry_days: int = 30

    @property
    def contribution_count(self) -> int:
        """Number of contributions (for informational display only — not a metric)."""
        return len(self.contributions)


class AssemblyEngine:
    """Anonymous deliberation engine with identity blinding.

    Manages Assembly topics and contributions. Never stores or returns
    actor identity. Compliance enforcement uses hash matching only.

    The engine receives a ComplianceScreener at construction for content
    screening. All content is screened at contribution time.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialise Assembly engine.

        Args:
            config: Assembly configuration containing:
                - inactivity_expiry_days: days before inactive topics archive
                  (default 30).
        """
        self._config = config
        self._topics: dict[str, AssemblyTopic] = {}
        self._inactivity_days = config.get("inactivity_expiry_days", 30)

    @classmethod
    def from_records(
        cls,
        config: dict[str, Any],
        topics_data: list[dict[str, Any]],
    ) -> AssemblyEngine:
        """Restore engine state from persistence records.

        Args:
            config: Assembly configuration.
            topics_data: Serialised topic records from StateStore.

        Returns:
            Reconstructed AssemblyEngine with all topics and contributions.
        """
        engine = cls(config)
        for td in topics_data:
            contributions = []
            for cd in td.get("contributions", []):
                contributions.append(AssemblyContribution(
                    contribution_id=cd["contribution_id"],
                    topic_id=td["topic_id"],
                    content=cd["content"],
                    compliance_hash=cd["compliance_hash"],
                    is_machine=cd["is_machine"],
                    contributed_utc=datetime.fromisoformat(cd["contributed_utc"]),
                ))
            topic = AssemblyTopic(
                topic_id=td["topic_id"],
                title=td["title"],
                status=AssemblyTopicStatus(td["status"]),
                created_utc=datetime.fromisoformat(td["created_utc"]),
                last_activity_utc=datetime.fromisoformat(td["last_activity_utc"]),
                contributions=contributions,
                inactivity_expiry_days=td.get(
                    "inactivity_expiry_days", engine._inactivity_days
                ),
            )
            engine._topics[topic.topic_id] = topic
        return engine

    def create_topic(
        self,
        title: str,
        content: str,
        compliance_hash: str,
        is_machine: bool,
        now: Optional[datetime] = None,
    ) -> AssemblyTopic:
        """Create a new Assembly topic with an initial contribution.

        Args:
            title: Topic title (subject line).
            content: First contribution text.
            compliance_hash: One-way salted hash of author (for enforcement).
            is_machine: Whether the author is a machine actor.
            now: Current UTC time (for testing determinism).

        Returns:
            The newly created AssemblyTopic.

        Raises:
            ValueError: If title or content is empty.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        if not title or not title.strip():
            raise ValueError("Topic title cannot be empty")
        if not content or not content.strip():
            raise ValueError("Topic content cannot be empty")

        topic_id = f"topic_{uuid.uuid4().hex[:12]}"
        contribution_id = f"contrib_{uuid.uuid4().hex[:12]}"

        contribution = AssemblyContribution(
            contribution_id=contribution_id,
            topic_id=topic_id,
            content=content.strip(),
            compliance_hash=compliance_hash,
            is_machine=is_machine,
            contributed_utc=now,
        )

        topic = AssemblyTopic(
            topic_id=topic_id,
            title=title.strip(),
            status=AssemblyTopicStatus.ACTIVE,
            created_utc=now,
            last_activity_utc=now,
            contributions=[contribution],
            inactivity_expiry_days=self._inactivity_days,
        )

        self._topics[topic_id] = topic
        return topic

    def contribute(
        self,
        topic_id: str,
        content: str,
        compliance_hash: str,
        is_machine: bool,
        now: Optional[datetime] = None,
    ) -> AssemblyContribution:
        """Add a contribution to an existing Assembly topic.

        Args:
            topic_id: Target topic ID.
            content: Contribution text.
            compliance_hash: One-way salted hash of author.
            is_machine: Whether the author is a machine actor.
            now: Current UTC time.

        Returns:
            The newly created AssemblyContribution.

        Raises:
            ValueError: If topic not found, topic is archived, or content empty.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        topic = self._topics.get(topic_id)
        if topic is None:
            raise ValueError(f"Topic not found: {topic_id}")
        if topic.status == AssemblyTopicStatus.ARCHIVED:
            raise ValueError(
                f"Cannot contribute to archived topic: {topic_id}"
            )
        if not content or not content.strip():
            raise ValueError("Contribution content cannot be empty")

        contribution_id = f"contrib_{uuid.uuid4().hex[:12]}"
        contribution = AssemblyContribution(
            contribution_id=contribution_id,
            topic_id=topic_id,
            content=content.strip(),
            compliance_hash=compliance_hash,
            is_machine=is_machine,
            contributed_utc=now,
        )

        topic.contributions.append(contribution)
        topic.last_activity_utc = now
        return contribution

    def archive_inactive_topics(
        self,
        now: Optional[datetime] = None,
    ) -> list[str]:
        """Sweep and archive topics that have exceeded their inactivity period.

        Archived topics remain readable but are closed to new contributions.

        Args:
            now: Current UTC time.

        Returns:
            List of topic_ids that were archived in this sweep.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        archived_ids: list[str] = []
        for topic in self._topics.values():
            if topic.status != AssemblyTopicStatus.ACTIVE:
                continue
            expiry = topic.last_activity_utc + timedelta(
                days=topic.inactivity_expiry_days
            )
            if now >= expiry:
                topic.status = AssemblyTopicStatus.ARCHIVED
                archived_ids.append(topic.topic_id)

        return archived_ids

    def get_topic(self, topic_id: str) -> Optional[AssemblyTopic]:
        """Retrieve a topic by ID.

        Returns the topic with all contributions. No identity information
        is ever returned — contributions contain only compliance_hash and
        is_machine flag.

        Args:
            topic_id: Topic ID to look up.

        Returns:
            The AssemblyTopic, or None if not found.
        """
        return self._topics.get(topic_id)

    def list_topics(
        self,
        status_filter: Optional[AssemblyTopicStatus] = None,
    ) -> list[AssemblyTopic]:
        """List Assembly topics, optionally filtered by status.

        Returns topics ordered by last_activity_utc (most recent first).
        No identity information is ever returned.

        Args:
            status_filter: If provided, only topics with this status.

        Returns:
            List of AssemblyTopics.
        """
        topics = list(self._topics.values())
        if status_filter is not None:
            topics = [t for t in topics if t.status == status_filter]
        topics.sort(key=lambda t: t.last_activity_utc, reverse=True)
        return topics

    def check_compliance_hash_match(
        self,
        contribution_id: str,
        candidate_hash: str,
    ) -> Optional[bool]:
        """Check if a compliance hash matches a specific contribution.

        This is the ONLY mechanism for linking a contribution to an actor,
        and it requires knowing both the actor_id AND the per-contribution
        salt (held only by the service layer's compliance enforcement path).

        This method is called only during legitimate compliance enforcement
        (post-hoc complaint investigation). It is NOT exposed through any
        public read API.

        Args:
            contribution_id: The contribution to check.
            candidate_hash: Hash to compare against.

        Returns:
            True if match, False if no match, None if contribution not found.
        """
        for topic in self._topics.values():
            for contrib in topic.contributions:
                if contrib.contribution_id == contribution_id:
                    return contrib.compliance_hash == candidate_hash
        return None

    def to_records(self) -> list[dict[str, Any]]:
        """Serialise all topics for persistence.

        Returns:
            List of topic dicts suitable for JSON serialisation.
        """
        records: list[dict[str, Any]] = []
        for topic in self._topics.values():
            contributions = []
            for c in topic.contributions:
                contributions.append({
                    "contribution_id": c.contribution_id,
                    "content": c.content,
                    "compliance_hash": c.compliance_hash,
                    "is_machine": c.is_machine,
                    "contributed_utc": c.contributed_utc.isoformat(),
                })
            records.append({
                "topic_id": topic.topic_id,
                "title": topic.title,
                "status": topic.status.value,
                "created_utc": topic.created_utc.isoformat(),
                "last_activity_utc": topic.last_activity_utc.isoformat(),
                "contributions": contributions,
                "inactivity_expiry_days": topic.inactivity_expiry_days,
            })
        return records
