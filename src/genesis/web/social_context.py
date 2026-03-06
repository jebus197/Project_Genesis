"""Social layout context for PoC mode.

Provides the shared template variables needed by base_social.html
and its partials (sidebar, header, activity panel).

In PoC mode these return demonstration data. Post-First Light,
they will query the real service layer.
"""

from __future__ import annotations


def poc_current_user() -> dict:
    """Simulated logged-in user for PoC demonstration."""
    return {
        "actor_id": "demo-human-1",
        "actor_type": "human",
        "display_name": "Demo User",
        "initials": "DU",
        "trust_score": 847,
        "quality_score": 91,
        "volume_score": 74,
        "open_bids": 3,
        "skills": [
            {"domain": "healthcare", "level": "advanced"},
            {"domain": "audit", "level": "advanced"},
            {"domain": "environment", "level": "intermediate"},
            {"domain": "education", "level": "intermediate"},
            {"domain": "transport", "level": "intermediate"},
            {"domain": "governance", "level": "baseline"},
        ],
    }


def poc_circles() -> list[dict]:
    """Simulated circle memberships for PoC demonstration."""
    return [
        {
            "id": "public-health",
            "name": "Public Health",
            "initials": "PH",
            "color": "linear-gradient(135deg, #059669, #34d399)",
            "member_count": 31,
        },
        {
            "id": "civic-qa",
            "name": "Civic QA Lab",
            "initials": "CI",
            "color": "linear-gradient(135deg, #0891b2, #22d3ee)",
            "member_count": 29,
        },
        {
            "id": "water-infra",
            "name": "Water Infra",
            "initials": "WI",
            "color": "linear-gradient(135deg, #f59e0b, #fbbf24)",
            "member_count": 13,
        },
    ]


def poc_stats(service=None) -> dict:
    """Platform-wide statistics for sidebar."""
    if service is not None:
        try:
            status = service.status()
            return {
                "humans": status.get("humans", 0),
                "machines": status.get("machines", 0),
                "open_missions": status.get("listings", 0),
            }
        except Exception:
            pass
    return {"humans": 5, "machines": 2, "open_missions": 4}


def social_globals(service=None) -> dict:
    """All global template variables for the social layout.

    Called once at app startup and injected into Jinja2 globals
    so every template inheriting base_social.html gets them.
    """
    return {
        "current_user": poc_current_user(),
        "circles": poc_circles(),
        "stats": poc_stats(service),
        "active_count": 14,
        "unread_messages": 2,
        "unread_notifications": 5,
    }
