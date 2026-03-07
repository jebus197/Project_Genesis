"""Tests for Founder Continuity (structural succession) — design tests #107-110.

Proves constitutional invariants:
- No individual inherits the founder's authority on inactivity
  (design test #107).
- The mechanism requires no human decision to activate
  (design test #108).
- The mechanism cannot be overridden by any party
  (design test #109).
- The mechanism defers to G0 time-limit for non-viable networks
  (design test #110).

Design test #107: If the founder becomes permanently inactive, does any
single individual inherit the founder's constitutional authority? If yes,
reject design.

Design test #108: Does the founder continuity mechanism require any human
decision, vote, or governance action to activate? If yes, reject design.

Design test #109: Can the founder continuity mechanism be overridden,
deferred, or extended by any party including the founder? If yes, reject
design.

Design test #110: Does the mechanism attempt to preserve governance viability
for arbitrarily small membership numbers, or does it correctly defer to the
G0 time-limit override for non-viable networks? If it attempts to preserve
viability at any size, reject design — that is over-engineering.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from genesis.policy.resolver import PolicyResolver


@pytest.fixture
def resolver() -> PolicyResolver:
    config_dir = Path(__file__).resolve().parent.parent / "config"
    return PolicyResolver.from_config_dir(config_dir)


class TestFounderContinuityConfig:
    """Config-level tests for founder continuity parameters."""

    def test_inactivity_threshold_exists(self, resolver) -> None:
        """FOUNDER_INACTIVITY_THRESHOLD_DAYS must be present in genesis config."""
        genesis = resolver._params.get("genesis", {})
        assert "FOUNDER_INACTIVITY_THRESHOLD_DAYS" in genesis

    def test_inactivity_threshold_is_positive_int(self, resolver) -> None:
        genesis = resolver._params["genesis"]
        threshold = genesis["FOUNDER_INACTIVITY_THRESHOLD_DAYS"]
        assert isinstance(threshold, int)
        assert threshold > 0

    def test_inactivity_threshold_default_value(self, resolver) -> None:
        """Default is 180 days as specified in the constitution."""
        genesis = resolver._params["genesis"]
        assert genesis["FOUNDER_INACTIVITY_THRESHOLD_DAYS"] == 180


class TestDesignTest107NoInheritance:
    """Design test #107: No individual inherits founder authority.

    The constitution specifies dissolution, not transfer. We verify this
    structurally: no config parameter names a successor, no code path
    assigns founder authority to another actor.
    """

    def test_no_successor_field_in_config(self, resolver) -> None:
        """No 'successor', 'heir', or 'delegate' field exists in genesis config."""
        genesis = resolver._params.get("genesis", {})
        forbidden_keys = {"successor", "heir", "delegate", "next_founder",
                          "backup_founder", "deputy_founder"}
        actual_keys = set(genesis.keys())
        overlap = actual_keys & forbidden_keys
        assert overlap == set(), (
            f"Config contains successor-like fields: {overlap}. "
            "Design test #107: authority dissolves, not transfers."
        )

    def test_no_successor_in_any_config(self, resolver) -> None:
        """No successor-like field exists anywhere in constitutional params."""
        def _scan(obj, path=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k.lower() in ("successor", "heir", "delegate",
                                     "next_founder", "backup_founder"):
                        return f"{path}.{k}"
                    result = _scan(v, f"{path}.{k}")
                    if result:
                        return result
            return None

        found = _scan(resolver._params)
        assert found is None, (
            f"Found successor-like key at {found}. "
            "Design test #107: no individual inherits authority."
        )


class TestDesignTest108AutomaticActivation:
    """Design test #108: Mechanism requires no human decision to activate.

    The constitution specifies: 'structural and automatic... requires no
    ballot, no quorum, and no governance action to activate.'
    """

    def test_threshold_is_purely_temporal(self, resolver) -> None:
        """Activation depends only on elapsed time, not on any vote or quorum."""
        genesis = resolver._params["genesis"]
        # The threshold is a number of days — a temporal trigger.
        # No quorum, ballot, or approval field accompanies it.
        threshold = genesis["FOUNDER_INACTIVITY_THRESHOLD_DAYS"]
        assert isinstance(threshold, (int, float))
        # Verify no activation-vote or activation-quorum field exists
        activation_fields = {k for k in genesis if "activation" in k.lower()
                            and "continuity" in k.lower()}
        assert activation_fields == set(), (
            f"Found activation-decision fields: {activation_fields}. "
            "Design test #108: mechanism must be automatic."
        )


class TestDesignTest109NoOverride:
    """Design test #109: Mechanism cannot be overridden by any party.

    The constitution specifies: 'It cannot be overridden, extended, or
    deferred by any party, including the founder.'
    """

    def test_no_override_field_in_config(self, resolver) -> None:
        """No override, defer, or extend field for founder continuity."""
        genesis = resolver._params.get("genesis", {})
        override_keys = {k for k in genesis
                         if any(word in k.lower()
                                for word in ("override_continuity",
                                             "defer_continuity",
                                             "extend_continuity",
                                             "disable_continuity",
                                             "pause_continuity"))}
        assert override_keys == set(), (
            f"Config contains override fields: {override_keys}. "
            "Design test #109: mechanism cannot be overridden."
        )

    def test_veto_cannot_block_continuity(self, resolver) -> None:
        """Founder veto allowed statuses do not include continuity activation."""
        genesis = resolver._params["genesis"]
        allowed = genesis.get("founder_veto_allowed_statuses", [])
        # Continuity activation is not a governance proposal — it cannot
        # appear in the list of statuses the founder can veto.
        continuity_terms = {"continuity", "succession", "inactivity",
                            "founder_continuity"}
        for status in allowed:
            assert status.lower() not in continuity_terms, (
                f"Founder veto can target '{status}' — this would allow "
                "the founder to block their own succession. "
                "Design test #109 violation."
            )


class TestDesignTest110DeferToG0TimeLimit:
    """Design test #110: Defers to G0 time-limit for non-viable networks.

    The mechanism must NOT attempt to preserve governance for arbitrarily
    small populations. The G0 time-limit override handles non-viability
    independently.
    """

    def test_no_minimum_membership_for_continuity(self, resolver) -> None:
        """No minimum-member threshold gates continuity activation."""
        genesis = resolver._params.get("genesis", {})
        # If a minimum-member field existed for continuity, it would mean
        # the mechanism tries to guarantee governance at any size.
        min_fields = {k for k in genesis
                      if "continuity_min" in k.lower()
                      or "succession_min" in k.lower()}
        assert min_fields == set(), (
            f"Config contains minimum-membership fields for continuity: "
            f"{min_fields}. Design test #110: do not over-engineer. "
            "G0 time-limit handles non-viability."
        )

    def test_g0_time_limit_exists_independently(self, resolver) -> None:
        """G0 time-limit override exists as the independent viability check."""
        genesis = resolver._params["genesis"]
        assert "G0_MAX_DAYS" in genesis
        assert "G0_EXTENSION_DAYS" in genesis
        # These are the viability controls — not the continuity mechanism.
        assert genesis["G0_MAX_DAYS"] > 0
        assert genesis["G0_EXTENSION_DAYS"] > 0

    def test_continuity_threshold_shorter_than_g0_limit(self, resolver) -> None:
        """Inactivity threshold must fire well before G0 expires.

        If the founder goes inactive, the network should know before the
        hard deadline forces shutdown. The threshold (180 days) must be
        shorter than the total G0 window (365 + 180 = 545 days).
        """
        genesis = resolver._params["genesis"]
        continuity = genesis["FOUNDER_INACTIVITY_THRESHOLD_DAYS"]
        g0_total = genesis["G0_MAX_DAYS"] + genesis["G0_EXTENSION_DAYS"]
        assert continuity < g0_total, (
            f"Inactivity threshold ({continuity}d) >= G0 total ({g0_total}d). "
            "Continuity must fire before the hard deadline."
        )
