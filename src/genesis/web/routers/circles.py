"""Circles — hierarchical forum navigation with PoC interactivity."""

from __future__ import annotations

import re
from hashlib import sha256
from random import Random
from secrets import token_hex
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from genesis.web.deps import get_resolver, get_templates
from genesis.web.negotiate import respond

router = APIRouter()
ALIAS_COOKIE_NAME = "genesis_alias_session"


FORUM_SECTIONS = [
    {
        "id": "public-health",
        "title": "Public Health Circle",
        "summary": "Clinical quality, triage integrity, patient safety, and health evidence review.",
        "bridges": ["Public Health x Civic QA", "Public Health x Governance"],
        "boards": [
            {
                "slug": "maternal-outcomes-lane",
                "title": "Maternal Outcomes Lane",
                "description": "Frontline case consistency, escalation timing, and outcome accountability.",
                "kind": "Discussion",
                "gate": 780,
                "threads": 83,
                "posts": 411,
                "last_topic": "NICU transfer threshold challenged with new ward evidence",
                "last_seen": "7m ago",
            },
            {
                "slug": "triage-integrity-lane",
                "title": "Triage Integrity Lane",
                "description": "Comparative triage logic, fairness checks, and patient-risk escalation debates.",
                "kind": "Debate",
                "gate": 840,
                "threads": 62,
                "posts": 296,
                "last_topic": "48h versus 72h escalation split reopened by case replay",
                "last_seen": "15m ago",
            },
            {
                "slug": "epidemiology-watch-lane",
                "title": "Epidemiology Watch Lane",
                "description": "Signal corroboration, outbreak interpretation, and public communication circles.",
                "kind": "Current Affairs",
                "gate": 780,
                "threads": 51,
                "posts": 219,
                "last_topic": "Regional spread model confidence update and public notice wording",
                "last_seen": "22m ago",
            },
            {
                "slug": "hospital-data-governance-lane",
                "title": "Hospital Data Governance Lane",
                "description": "Schema drift, consent handling, and cross-hospital data traceability.",
                "kind": "Policy",
                "gate": 840,
                "threads": 47,
                "posts": 207,
                "last_topic": "Common coding dictionary proposal moved to drafting table",
                "last_seen": "39m ago",
            },
            {
                "slug": "vaccination-signal-lane",
                "title": "Vaccination Signal Lane",
                "description": "High-sensitivity adverse-signal review under strict evidence thresholds.",
                "kind": "Jobs",
                "gate": 840,
                "threads": 34,
                "posts": 155,
                "last_topic": "Reviewer call for corroboration sprint (2 human + 1 machine)",
                "last_seen": "1h ago",
            },
        ],
    },
    {
        "id": "civic-qa",
        "title": "Civic QA Lab",
        "summary": "Public systems assurance, procurement checks, records integrity, and transit reliability.",
        "bridges": ["Civic QA x Water Infrastructure", "Civic QA x Assembly"],
        "boards": [
            {
                "slug": "sensor-integrity-lane",
                "title": "Municipal Sensor Integrity Lane",
                "description": "Sensor reliability, drift disputes, and city-level validation standards.",
                "kind": "Discussion",
                "gate": 780,
                "threads": 76,
                "posts": 343,
                "last_topic": "Cross-city calibration mismatch confirmed in two districts",
                "last_seen": "11m ago",
            },
            {
                "slug": "public-records-lane",
                "title": "Public Records Verification Lane",
                "description": "Revision provenance, disclosure quality, and accountability documentation.",
                "kind": "Policy",
                "gate": 840,
                "threads": 44,
                "posts": 188,
                "last_topic": "Archive gap discovered in procurement revision chain",
                "last_seen": "26m ago",
            },
            {
                "slug": "procurement-review-lane",
                "title": "Procurement Review Lane",
                "description": "Anomaly challenge circles and fair-process interpretation debates.",
                "kind": "Debate",
                "gate": 840,
                "threads": 59,
                "posts": 274,
                "last_topic": "Seasonality defense accepted in one flagged tender cluster",
                "last_seen": "31m ago",
            },
            {
                "slug": "transit-safety-lane",
                "title": "Transit Safety Lane",
                "description": "Incident replay, response planning, and commuter safety governance.",
                "kind": "Current Affairs",
                "gate": 780,
                "threads": 68,
                "posts": 321,
                "last_topic": "Night-service incident root-cause memo opened for challenge",
                "last_seen": "47m ago",
            },
            {
                "slug": "service-quality-floor-lane",
                "title": "Service Quality Floor Lane",
                "description": "Real-world service outcomes versus public quality commitments.",
                "kind": "Jobs",
                "gate": 840,
                "threads": 38,
                "posts": 167,
                "last_topic": "Need two reviewers for district quality floor check",
                "last_seen": "1h 12m ago",
            },
        ],
    },
    {
        "id": "enviro-analytics",
        "title": "Enviro Analytics Circle",
        "summary": "Climate signals, air-quality response, resilience modelling, and ecological evidence.",
        "bridges": ["Enviro Analytics x Water Infrastructure", "Enviro Analytics x Public Health"],
        "boards": [
            {
                "slug": "flood-replay-lane",
                "title": "Flood Replay Lane",
                "description": "Hydraulic model stress tests, counter-examples, and response planning.",
                "kind": "Discussion",
                "gate": 780,
                "threads": 73,
                "posts": 354,
                "last_topic": "Snowmelt scenario invalidated one high-risk drainage assumption",
                "last_seen": "9m ago",
            },
            {
                "slug": "air-drift-lane",
                "title": "Air Drift Lane",
                "description": "Regional drift disputes and plain-language public warning standards.",
                "kind": "Current Affairs",
                "gate": 780,
                "threads": 57,
                "posts": 266,
                "last_topic": "School closure guidance alignment requested across four boroughs",
                "last_seen": "18m ago",
            },
            {
                "slug": "heatwave-response-lane",
                "title": "Heatwave Response Lane",
                "description": "Threshold policy, emergency capacity planning, and vulnerable-group protections.",
                "kind": "Debate",
                "gate": 840,
                "threads": 49,
                "posts": 224,
                "last_topic": "Cooling-center trigger threshold proposal enters challenge window",
                "last_seen": "43m ago",
            },
            {
                "slug": "biodiversity-trace-lane",
                "title": "Biodiversity Trace Lane",
                "description": "Habitat anomaly interpretation and ecological action prioritization.",
                "kind": "Discussion",
                "gate": 780,
                "threads": 36,
                "posts": 146,
                "last_topic": "Wetland anomaly signal confirmed after survey cross-check",
                "last_seen": "58m ago",
            },
            {
                "slug": "carbon-methods-lane",
                "title": "Carbon Methods Lane",
                "description": "Method transparency, estimate quality, and disclosure governance.",
                "kind": "Policy",
                "gate": 840,
                "threads": 41,
                "posts": 179,
                "last_topic": "Uncertainty band wording updated for public release note",
                "last_seen": "1h 25m ago",
            },
        ],
    },
    {
        "id": "water-infra",
        "title": "Water Infrastructure Circle",
        "summary": "Resilience planning, grid reliability, compliance quality, and operational safety.",
        "bridges": ["Water Infrastructure x Civic QA", "Water Infrastructure x Enviro Analytics"],
        "boards": [
            {
                "slug": "grid-calibration-lane",
                "title": "Grid Calibration Lane",
                "description": "Sensor calibration replay and network consistency decisions.",
                "kind": "Discussion",
                "gate": 780,
                "threads": 64,
                "posts": 289,
                "last_topic": "Outlier array W-17 moved to supervised retest",
                "last_seen": "8m ago",
            },
            {
                "slug": "leak-detection-lane",
                "title": "Leak Detection Lane",
                "description": "False-positive suppression, incident triage, and field verification.",
                "kind": "Current Affairs",
                "gate": 780,
                "threads": 52,
                "posts": 238,
                "last_topic": "False alarm cluster traced to maintenance window metadata",
                "last_seen": "21m ago",
            },
            {
                "slug": "reservoir-risk-lane",
                "title": "Reservoir Risk Lane",
                "description": "Stress scenario debates and high-impact contingency planning.",
                "kind": "Debate",
                "gate": 840,
                "threads": 48,
                "posts": 213,
                "last_topic": "Dry-season reserve policy challenged by new demand model",
                "last_seen": "37m ago",
            },
            {
                "slug": "compliance-adjudication-lane",
                "title": "Treatment Compliance Lane",
                "description": "Outlier adjudication and regulatory consistency across operators.",
                "kind": "Policy",
                "gate": 840,
                "threads": 39,
                "posts": 171,
                "last_topic": "Operator appeal reopened after independent replay pass",
                "last_seen": "49m ago",
            },
            {
                "slug": "maintenance-forecast-lane",
                "title": "Maintenance Forecast Lane",
                "description": "Predictive maintenance jobs, review calls, and field support requests.",
                "kind": "Jobs",
                "gate": 840,
                "threads": 33,
                "posts": 127,
                "last_topic": "Looking for two reviewers on north-sector failure forecast",
                "last_seen": "1h 34m ago",
            },
        ],
    },
    {
        "id": "education-skills",
        "title": "Education and Skills Circle",
        "summary": "Learning outcomes, support equity, school operations, and pathway durability.",
        "bridges": ["Education and Skills x Public Health", "Education and Skills x Assembly"],
        "boards": [
            {
                "slug": "literacy-outcomes-lane",
                "title": "Literacy Outcomes Lane",
                "description": "Cohort evidence, intervention durability, and classroom implementation.",
                "kind": "Discussion",
                "gate": 780,
                "threads": 53,
                "posts": 231,
                "last_topic": "Cohort B gains revised after six-month retention check",
                "last_seen": "13m ago",
            },
            {
                "slug": "curriculum-efficacy-lane",
                "title": "Curriculum Efficacy Lane",
                "description": "What scales, what fails, and how to report uncertainty honestly.",
                "kind": "Debate",
                "gate": 840,
                "threads": 46,
                "posts": 203,
                "last_topic": "Comparative writing outcomes show mixed transfer effects",
                "last_seen": "29m ago",
            },
            {
                "slug": "vocational-placement-lane",
                "title": "Vocational Placement Lane",
                "description": "Placement quality, retention evidence, and pathway transparency.",
                "kind": "Current Affairs",
                "gate": 780,
                "threads": 42,
                "posts": 186,
                "last_topic": "Six-month placement drop-off cluster escalated for review",
                "last_seen": "36m ago",
            },
            {
                "slug": "support-equity-lane",
                "title": "Support Equity Lane",
                "description": "Needs-based allocation checks and fairness policy proposals.",
                "kind": "Policy",
                "gate": 840,
                "threads": 44,
                "posts": 191,
                "last_topic": "Equity floor amendment draft enters comment period",
                "last_seen": "55m ago",
            },
            {
                "slug": "resource-audit-lane",
                "title": "Resource Audit Lane",
                "description": "School resource distribution jobs and verification requests.",
                "kind": "Jobs",
                "gate": 840,
                "threads": 31,
                "posts": 119,
                "last_topic": "Need one verifier for district 5 textbook allocation trail",
                "last_seen": "1h 19m ago",
            },
        ],
    },
    {
        "id": "governance-justice",
        "title": "Governance and Justice Circle",
        "summary": "Constitutional process, trust appeals, compliance rulings, and platform politics.",
        "bridges": ["Governance and Justice x All Circles", "Governance and Justice x Assembly"],
        "boards": [
            {
                "slug": "amendment-deliberation-lane",
                "title": "Amendment Deliberation Lane",
                "description": "Constitutional proposals, challenge windows, and ratification drafts.",
                "kind": "Policy",
                "gate": 840,
                "threads": 72,
                "posts": 388,
                "last_topic": "Reviewer diversity amendment enters chamber discussion",
                "last_seen": "6m ago",
            },
            {
                "slug": "compliance-rulings-lane",
                "title": "Compliance Rulings Lane",
                "description": "Case-law style review of contested compliance outcomes.",
                "kind": "Debate",
                "gate": 840,
                "threads": 58,
                "posts": 267,
                "last_topic": "Case C-211 reopened after procedural challenge accepted",
                "last_seen": "17m ago",
            },
            {
                "slug": "trust-appeals-lane",
                "title": "Trust Appeals Lane",
                "description": "Appeals backlog, fairness trade-offs, and queue policy design.",
                "kind": "Current Affairs",
                "gate": 780,
                "threads": 54,
                "posts": 243,
                "last_topic": "Latency reduction package posted for community scrutiny",
                "last_seen": "28m ago",
            },
            {
                "slug": "expert-vetting-lane",
                "title": "Expert Vetting Lane",
                "description": "Conflict checks, appointment standards, and trust-sensitive nominations.",
                "kind": "Discussion",
                "gate": 780,
                "threads": 37,
                "posts": 162,
                "last_topic": "COI declaration template revised after legal panel review",
                "last_seen": "44m ago",
            },
            {
                "slug": "ratification-readiness-lane",
                "title": "Ratification Readiness Lane",
                "description": "Final proof-pack checks before high-impact chamber votes.",
                "kind": "Jobs",
                "gate": 840,
                "threads": 29,
                "posts": 109,
                "last_topic": "Call for legal proofreader on amendment pack R-14",
                "last_seen": "1h 08m ago",
            },
        ],
    },
]

EXPERTISE_POOL = [
    "Public health",
    "Audit",
    "Education",
    "Transport safety",
    "Water infra",
    "Governance",
    "Policy writing",
    "Model evaluation",
    "Legal review",
]

MACHINE_MODEL_POOL = [
    "Claude Opus-class",
    "GPT-5 class",
    "Gemini 2.x class",
    "Mistral Enterprise class",
    "Llama enterprise-tuned",
]

MACHINE_AGENT_POOL = [
    "Evidence triage agent",
    "Replay verification agent",
    "Policy drafting agent",
    "Cross-domain synthesis agent",
    "Monitoring agent",
]

CAPABILITY_POOL = [
    "structured summarization",
    "counter-example search",
    "evidence replay",
    "traceability checks",
    "policy diffing",
    "risk scoring",
]

KIND_STAGE_POOL = {
    "Discussion": ["Open review", "Synthesis", "Ready for field test", "Recheck requested"],
    "Debate": ["Challenge window", "Counter-example review", "Deliberation", "Escalation check"],
    "Current Affairs": ["Live signal", "Verification", "Community briefing", "Monitoring"],
    "Policy": ["Drafting", "Public comment", "Ratification prep", "Legal pass"],
    "Jobs": ["Intake open", "Shortlisting", "Onboarding", "Roster hold"],
}

KIND_TITLE_POOL = {
    "Discussion": [
        "{focus}: what changed after this week of submissions",
        "Field handover note from {circle} contributors in {focus}",
        "Independent check requested on {focus} evidence pack",
        "Operational alignment thread for {focus}",
        "Community update: practical blockers in {focus}",
    ],
    "Debate": [
        "{focus}: strict-threshold model challenged by adaptive proposal",
        "Competing interpretation thread opened for {focus}",
        "Counter-example filed against current {focus} recommendation",
        "Should {focus} move to Assembly queue this week?",
        "Debate synthesis: unresolved trade-offs in {focus}",
    ],
    "Current Affairs": [
        "Latest public update from {focus} lane",
        "What residents are asking this week about {focus}",
        "Cross-district update: {focus} communication consistency",
        "Live briefing thread for {focus} developments",
        "Weekend watch: {focus} indicators and response timing",
    ],
    "Policy": [
        "Draft amendment opened for {focus} standards",
        "Policy wording review for {focus} publication",
        "Comment window: accountability language in {focus}",
        "Ratification pre-check for {focus} package",
        "Legal consistency pass requested in {focus}",
    ],
    "Jobs": [
        "Contributor call: {focus} review roster",
        "Open role notice for {focus} verification sprint",
        "Short-term assignment posted in {focus}",
        "Need cross-domain reviewer for {focus} handover",
        "Urgent staffing request for {focus} evidence cycle",
    ],
}

KIND_SUMMARY_POOL = {
    "Discussion": [
        "This thread captures practical findings from this cycle so teams can align before the next operational brief.",
        "Members are comparing on-the-ground reports and trying to settle one shared picture people can act on.",
        "The aim is to surface what actually worked, what did not, and what should change immediately.",
    ],
    "Debate": [
        "Two serious interpretations are now on record and both have credible evidence attached.",
        "Participants are stress-testing assumptions before anything escalates into policy or enforcement.",
        "The moderation ask is simple: keep claims auditable and keep disagreement constructive.",
    ],
    "Current Affairs": [
        "This lane tracks live updates and focuses on clear, plain-language communication for mixed audiences.",
        "The thread follows incoming reports and highlights what is confirmed versus what still needs verification.",
        "Members are coordinating fast updates without dropping evidence quality under time pressure.",
    ],
    "Policy": [
        "Draft language is being refined so implementation teams can apply it without ambiguity.",
        "Contributors are reviewing edge-cases and making sure wording survives legal and operational scrutiny.",
        "The immediate goal is a policy text that is understandable, enforceable, and easy to audit later.",
    ],
    "Jobs": [
        "This posting is a targeted call for contributors who can complete a specific deliverable within the current cycle.",
        "Applicants are asked to show relevant work history, likely turnaround, and any conflict disclosures.",
        "The lane is intended for practical staffing, not long-form debate, so intake decisions can move quickly.",
    ],
}

RING_CLASS_BY_SECTION = {
    "public-health": "ring-health",
    "civic-qa": "ring-civic",
    "enviro-analytics": "ring-enviro",
    "water-infra": "ring-water",
    "education-skills": "ring-civic",
    "governance-justice": "ring-enviro",
}


def _scale_policy_gate(value: float | int, fallback: int) -> int:
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return fallback
    if raw <= 1.0:
        raw *= 1000.0
    return max(0, min(1000, int(round(raw))))


def _circle_policy_gates() -> dict[str, int]:
    """Derive circles trust gates from constitutional parameters."""
    try:
        resolver = get_resolver()
        tau_vote, tau_prop = resolver.eligibility_thresholds()
        immune = resolver.immune_system_config()
    except Exception:
        return {
            "join": 700,
            "propose": 840,
            "moderate": 880,
        }

    join_gate = _scale_policy_gate(tau_vote, 700)
    propose_gate = max(join_gate, _scale_policy_gate(tau_prop, 840))
    moderate_gate = max(
        propose_gate,
        _scale_policy_gate(immune.get("oversight_trust_min", 0.88), 880),
    )
    return {
        "join": join_gate,
        "propose": propose_gate,
        "moderate": moderate_gate,
    }


CIRCLE_GATES = _circle_policy_gates()
_MAX_BOARD_GATE = max(int(board["gate"]) for section in FORUM_SECTIONS for board in section["boards"])
_TRUST_BAND_LEVELS = sorted(
    {
        CIRCLE_GATES["join"],
        CIRCLE_GATES["propose"],
        CIRCLE_GATES["moderate"],
        _MAX_BOARD_GATE,
    }
)
TRUST_BANDS = [f"{level}+" for level in _TRUST_BAND_LEVELS]


@router.get("")
async def circles_listing(request: Request):
    templates = get_templates(request)
    payload = _build_forum_payload(request)
    state = _circles_state(request)

    context = {
        "request": request,
        "active_tab": "circles",
        "view_mode": "index",
        "page_heading": "Circles Directory",
        "page_subheading": "Choose a Circle, enter a Working Circle, then join a Circle.",
        "breadcrumbs": [{"label": "Circles", "url": None}],
        "notice": request.query_params.get("notice"),
        "notice_type": request.query_params.get("notice_type", "info"),
        "recent_circle_proposals": _recent_circle_proposals(state),
        **payload,
    }
    context.update(_access_context(request))

    return respond(request, templates, "circles.html", context)


@router.get("/{circle_id}")
async def circle_detail(request: Request, circle_id: str):
    templates = get_templates(request)
    payload = _build_forum_payload(request)
    circle = _find_circle(payload["forum_sections_by_id"], circle_id)

    state = _circles_state(request)
    applications = state["applications"].get(circle_id, [])[:8]

    context = {
        "request": request,
        "active_tab": "circles",
        "view_mode": "circle",
        "page_heading": f"Circle: {circle['title']}",
        "page_subheading": circle["summary"],
        "breadcrumbs": [
            {"label": "Circles", "url": "/circles"},
            {"label": "Circle", "url": None},
        ],
        "notice": request.query_params.get("notice"),
        "notice_type": request.query_params.get("notice_type", "info"),
        "circle": circle,
        "circle_applications": applications,
        "recent_circle_proposals": _recent_circle_proposals(state, circle_id=circle_id),
        "other_circles": [s for s in payload["forum_sections"] if s["id"] != circle_id],
        **payload,
    }
    context.update(_access_context(request))

    return respond(request, templates, "circles.html", context)


@router.post("/{circle_id}/apply")
async def apply_circle(request: Request, circle_id: str):
    payload = _build_forum_payload(request)
    _find_circle(payload["forum_sections_by_id"], circle_id)
    form = await request.form()

    access = _access_context(request)
    actor = _participant_from_form(
        request,
        form,
        viewer_trust=access["viewer_trust"],
        current_user=access["current_user"],
        scope_key=f"circle:{circle_id}:join",
    )
    if actor["trust_score"] < access["follow_gate"]:
        return _redirect_with_notice(
            request,
            f"/circles/{circle_id}",
            (
                "Join request blocked: participant trust is below Circle entry threshold "
                f"({access['follow_gate']})."
            ),
            "warning",
        )

    state = _circles_state(request)
    bucket = state["applications"].setdefault(circle_id, [])
    bucket.insert(
        0,
        {
            "alias": actor["alias"],
            "actor_id": actor["actor_id"],
            "actor_type": actor["actor_type"],
            "trust_score": actor["trust_score"],
            "specialty": actor.get("specialty", ""),
            "model_name": actor.get("model_name", ""),
            "agent_type": actor.get("agent_type", ""),
            "capabilities": actor.get("capabilities", ""),
            "status": "Accepted for review" if actor["trust_score"] >= access["propose_gate"] else "Queued",
            "submitted_at": "just now",
            "note": str(form.get("note", "")).strip(),
        },
    )

    return _redirect_with_notice(
        request,
        f"/circles/{circle_id}",
        "Join request submitted. Circle stewards can now review this participant.",
        "success",
    )


@router.post("/proposals")
async def propose_circle_or_domain(request: Request):
    payload = _build_forum_payload(request)
    access = _access_context(request)
    if not access["can_propose"]:
        return _redirect_with_notice(
            request,
            "/circles",
            f"Circle proposal locked: proposer trust is below {access['propose_gate']}+.",
            "warning",
        )

    form = await request.form()
    title = str(form.get("title", "")).strip()
    summary = str(form.get("summary", "")).strip()
    proposal_scope = str(form.get("proposal_scope", "existing_domain")).strip().lower()
    target_circle_id = str(form.get("target_circle_id", "")).strip()
    rationale = str(form.get("rationale", "")).strip()

    if not title:
        return _redirect_with_notice(request, "/circles", "Circle proposal title is required.", "warning")
    if not summary:
        return _redirect_with_notice(request, "/circles", "Circle proposal summary is required.", "warning")

    status = "Queued for steward review"
    scope_label = "Within existing domain"
    target_label = ""
    resolved_circle_id: str | None = None

    if proposal_scope == "new_domain":
        if not rationale:
            return _redirect_with_notice(
                request,
                "/circles",
                "New domain proposals require a rationale.",
                "warning",
            )
        scope_label = "New domain"
        status = "Queued for moderation + quorum verification"
        target_label = "Proposed new domain"
    else:
        proposal_scope = "existing_domain"
        target = payload["forum_sections_by_id"].get(target_circle_id)
        if not target:
            return _redirect_with_notice(
                request,
                "/circles",
                "Select a valid domain for this circle proposal.",
                "warning",
            )
        resolved_circle_id = target["id"]
        target_label = target["title"]

    actor = _participant_from_form(
        request,
        form,
        viewer_trust=access["viewer_trust"],
        current_user=access["current_user"],
        scope_key=f"proposal:{proposal_scope}:{resolved_circle_id or 'new-domain'}",
    )

    proposal = {
        "proposal_id": f"proposal-{token_hex(4)}",
        "title": title,
        "summary": summary,
        "scope_label": scope_label,
        "circle_id": resolved_circle_id,
        "target_label": target_label,
        "rationale": rationale,
        "status": status,
        "submitted_at": "just now",
        "alias": actor["alias"],
        "actor_type": actor["actor_type"],
        "trust_score": actor["trust_score"],
    }
    state = _circles_state(request)
    state["proposals"].insert(0, proposal)

    return _redirect_with_notice(
        request,
        "/circles",
        "Circle proposal submitted for review.",
        "success",
    )


@router.post("/{circle_id}/proposals")
async def propose_circle_in_domain(request: Request, circle_id: str):
    payload = _build_forum_payload(request)
    circle = _find_circle(payload["forum_sections_by_id"], circle_id)
    access = _access_context(request)
    if not access["can_propose"]:
        return _redirect_with_notice(
            request,
            f"/circles/{circle_id}",
            f"Circle proposal locked: proposer trust is below {access['propose_gate']}+.",
            "warning",
        )

    form = await request.form()
    title = str(form.get("title", "")).strip()
    summary = str(form.get("summary", "")).strip()
    rationale = str(form.get("rationale", "")).strip()

    if not title:
        return _redirect_with_notice(
            request,
            f"/circles/{circle_id}",
            "Circle proposal title is required.",
            "warning",
        )
    if not summary:
        return _redirect_with_notice(
            request,
            f"/circles/{circle_id}",
            "Circle proposal summary is required.",
            "warning",
        )

    actor = _participant_from_form(
        request,
        form,
        viewer_trust=access["viewer_trust"],
        current_user=access["current_user"],
        scope_key=f"proposal:existing_domain:{circle_id}",
    )

    proposal = {
        "proposal_id": f"proposal-{token_hex(4)}",
        "title": title,
        "summary": summary,
        "scope_label": "Within existing domain",
        "circle_id": circle["id"],
        "target_label": circle["title"],
        "rationale": rationale,
        "status": "Queued for steward review",
        "submitted_at": "just now",
        "alias": actor["alias"],
        "actor_type": actor["actor_type"],
        "trust_score": actor["trust_score"],
    }
    state = _circles_state(request)
    state["proposals"].insert(0, proposal)

    return _redirect_with_notice(
        request,
        f"/circles/{circle_id}",
        "Circle proposal submitted to domain stewards.",
        "success",
    )


@router.get("/{circle_id}/{board_slug}")
async def board_detail(request: Request, circle_id: str, board_slug: str):
    templates = get_templates(request)
    payload = _build_forum_payload(request)
    circle = _find_circle(payload["forum_sections_by_id"], circle_id)
    board = _find_board(circle, board_slug)

    access = _access_context(request, board_gate=int(board["gate"]))
    context = {
        "request": request,
        "active_tab": "circles",
        "view_mode": "board",
        "page_heading": f"Working Circle: {board['title']}",
        "page_subheading": f"{board['description']} Start or join circles in this working domain.",
        "breadcrumbs": [
            {"label": "Circles", "url": "/circles"},
            {"label": "Circle", "url": f"/circles/{circle['id']}"},
            {"label": "Working Circle", "url": None},
        ],
        "notice": request.query_params.get("notice"),
        "notice_type": request.query_params.get("notice_type", "info"),
        "circle": circle,
        "board": board,
        "threads": board["thread_items"],
        "related_boards": [b for b in circle["boards"] if b["slug"] != board_slug][:4],
        **payload,
    }
    context.update(access)

    return respond(request, templates, "circles.html", context)


@router.post("/{circle_id}/{board_slug}/threads")
async def create_thread(request: Request, circle_id: str, board_slug: str):
    payload = _build_forum_payload(request)
    circle = _find_circle(payload["forum_sections_by_id"], circle_id)
    board = _find_board(circle, board_slug)

    access = _access_context(request, board_gate=int(board["gate"]))
    if not access["can_post"]:
        return _redirect_with_notice(
            request,
            f"/circles/{circle_id}/{board_slug}",
            f"Circle creation locked: viewer trust is below {access['post_gate']}+ gate.",
            "warning",
        )

    form = await request.form()
    title = str(form.get("title", "")).strip()
    summary = str(form.get("summary", "")).strip()
    opening = str(form.get("opening_body", "")).strip()

    if not title:
        return _redirect_with_notice(
            request,
            f"/circles/{circle_id}/{board_slug}",
            "Circle title is required.",
            "warning",
        )

    state = _circles_state(request)
    board_key = _board_key(circle_id, board_slug)
    dynamic_threads = state["threads"].setdefault(board_key, [])

    existing_ids = {thread["id"] for thread in board["thread_items"]}
    thread_id = _make_unique_thread_id(title, existing_ids)
    actor = _participant_from_form(
        request,
        form,
        viewer_trust=access["viewer_trust"],
        current_user=access["current_user"],
        scope_key=f"thread:{circle_id}:{board_slug}:{thread_id}",
    )
    if actor["trust_score"] < access["post_gate"]:
        return _redirect_with_notice(
            request,
            f"/circles/{circle_id}/{board_slug}",
            f"Circle creation blocked: participant trust is below {access['post_gate']}.",
            "warning",
        )

    thread = {
        "id": thread_id,
        "title": title,
        "summary": summary or "Community circle opened for this working circle.",
        "stage": "Open review",
        "replies": 0,
        "participants": 1,
        "last_seen": "just now",
        "last_actor": actor["alias"],
        "starter_alias": actor["alias"],
        "starter_actor_id": actor["actor_id"],
        "starter_role": _actor_role_label(actor),
        "required_trust": access["post_gate"],
        "trust_band": _trust_band(actor["trust_score"]),
        "seeded": False,
        "is_dynamic": True,
    }
    dynamic_threads.insert(0, thread)

    thread_key = _thread_key(circle_id, board_slug, thread_id)
    posts = state["posts"].setdefault(thread_key, [])
    status = _post_status(board, actor)
    posts.append(
        {
            "alias": actor["alias"],
            "actor_id": actor["actor_id"],
            "actor_type": actor["actor_type"],
            "trust_score": actor["trust_score"],
            "specialty": actor.get("specialty", ""),
            "model_name": actor.get("model_name", ""),
            "agent_type": actor.get("agent_type", ""),
            "capabilities": actor.get("capabilities", ""),
            "when": "just now",
            "body": opening or (summary if summary else "Opening note pending."),
            "reply_to": "",
            "status": status,
        }
    )

    return _redirect_with_notice(
        request,
        f"/circles/{circle_id}/{board_slug}/{thread_id}",
        "Circle created and opened for responses.",
        "success",
    )


@router.get("/{circle_id}/{board_slug}/{thread_id}")
async def thread_detail(request: Request, circle_id: str, board_slug: str, thread_id: str):
    templates = get_templates(request)
    payload = _build_forum_payload(request)
    circle = _find_circle(payload["forum_sections_by_id"], circle_id)
    board = _find_board(circle, board_slug)
    thread = _find_thread(board, thread_id)

    access = _access_context(request, board_gate=int(board["gate"]))
    posts = _thread_posts(request, circle, board, thread)

    context = {
        "request": request,
        "active_tab": "circles",
        "view_mode": "thread",
        "page_heading": f"Circle: {thread['title']}",
        "page_subheading": thread["summary"],
        "breadcrumbs": [
            {"label": "Circles", "url": "/circles"},
            {"label": "Circle", "url": f"/circles/{circle['id']}"},
            {"label": "Working Circle", "url": f"/circles/{circle['id']}/{board['slug']}"},
            {"label": "Circle", "url": None},
        ],
        "notice": request.query_params.get("notice"),
        "notice_type": request.query_params.get("notice_type", "info"),
        "circle": circle,
        "board": board,
        "thread": thread,
        "thread_posts": posts,
        "related_threads": [t for t in board["thread_items"] if t["id"] != thread_id][:5],
        **payload,
    }
    context.update(access)

    return respond(request, templates, "circles.html", context)


@router.post("/{circle_id}/{board_slug}/{thread_id}/reply")
async def reply_thread(request: Request, circle_id: str, board_slug: str, thread_id: str):
    payload = _build_forum_payload(request)
    circle = _find_circle(payload["forum_sections_by_id"], circle_id)
    board = _find_board(circle, board_slug)
    _find_thread(board, thread_id)

    access = _access_context(request, board_gate=int(board["gate"]))
    if not access["can_post"]:
        return _redirect_with_notice(
            request,
            f"/circles/{circle_id}/{board_slug}/{thread_id}",
            f"Reply locked: viewer trust is below {access['post_gate']}+ gate.",
            "warning",
        )

    form = await request.form()
    body = str(form.get("body", "")).strip()
    reply_to = str(form.get("reply_to", "")).strip()
    if not body:
        return _redirect_with_notice(
            request,
            f"/circles/{circle_id}/{board_slug}/{thread_id}",
            "Reply text is required.",
            "warning",
        )

    actor = _participant_from_form(
        request,
        form,
        viewer_trust=access["viewer_trust"],
        current_user=access["current_user"],
        scope_key=f"thread:{circle_id}:{board_slug}:{thread_id}",
    )
    if actor["trust_score"] < access["post_gate"]:
        return _redirect_with_notice(
            request,
            f"/circles/{circle_id}/{board_slug}/{thread_id}",
            f"Reply blocked: participant trust is below {access['post_gate']}.",
            "warning",
        )

    state = _circles_state(request)
    thread_key = _thread_key(circle_id, board_slug, thread_id)
    posts = state["posts"].setdefault(thread_key, [])
    status = _post_status(board, actor)

    posts.append(
        {
            "alias": actor["alias"],
            "actor_id": actor["actor_id"],
            "actor_type": actor["actor_type"],
            "trust_score": actor["trust_score"],
            "specialty": actor.get("specialty", ""),
            "model_name": actor.get("model_name", ""),
            "agent_type": actor.get("agent_type", ""),
            "capabilities": actor.get("capabilities", ""),
            "when": "just now",
            "body": body,
            "reply_to": reply_to,
            "status": status,
        }
    )

    return _redirect_with_notice(
        request,
        f"/circles/{circle_id}/{board_slug}/{thread_id}",
        "Reply posted to the circle.",
        "success",
    )


def _build_forum_payload(request: Request) -> dict:
    state = _circles_state(request)

    sections: list[dict] = []
    stats = {
        "circle_count": 0,
        "board_count": 0,
        "thread_count": 0,
        "post_count": 0,
    }

    for section in FORUM_SECTIONS:
        shaped_boards: list[dict] = []
        for board in section["boards"]:
            stats["board_count"] += 1
            board_key = _board_key(section["id"], board["slug"])
            base_threads = _build_seed_threads(section, board)
            dynamic_threads = list(state["threads"].get(board_key, []))
            thread_items = [_apply_thread_activity(t, state, section["id"], board["slug"]) for t in (dynamic_threads + base_threads)]

            shaped = {
                **board,
                "ring_class": RING_CLASS_BY_SECTION.get(section["id"], "ring-civic"),
                "thread_items": thread_items,
                "preview_thread_count": len(thread_items),
            }

            if thread_items:
                shaped["last_topic"] = thread_items[0]["title"]
                shaped["last_seen"] = thread_items[0]["last_seen"]
                shaped["last_actor"] = thread_items[0]["last_actor"]
                shaped["trust_band"] = thread_items[0]["trust_band"]
            else:
                shaped["last_actor"] = "-"
                shaped["trust_band"] = f"{CIRCLE_GATES['join']}+"

            shaped_boards.append(shaped)

            stats["thread_count"] += len(thread_items)
            stats["post_count"] += int(board["posts"])
            for thread in thread_items:
                extra_posts = len(state["posts"].get(_thread_key(section["id"], board["slug"], thread["id"]), []))
                stats["post_count"] += extra_posts

        sections.append(
            {
                **section,
                "ring_class": RING_CLASS_BY_SECTION.get(section["id"], "ring-civic"),
                "boards": shaped_boards,
                "board_count": len(shaped_boards),
                "thread_count": sum(len(board["thread_items"]) for board in shaped_boards),
                "post_count": sum(int(board["posts"]) for board in shaped_boards),
                "last_seen": shaped_boards[0]["last_seen"] if shaped_boards else "-",
            }
        )

    stats["circle_count"] = len(sections)
    return {
        "forum_sections": sections,
        "forum_sections_by_id": {section["id"]: section for section in sections},
        "forum_stats": stats,
    }


def _build_seed_threads(section: dict, board: dict) -> list[dict]:
    focus = board["title"].replace("Lane", "").strip()
    circle = section["title"].replace(" Circle", "")
    kind = board["kind"]

    title_pool = KIND_TITLE_POOL.get(kind, KIND_TITLE_POOL["Discussion"])
    summary_pool = KIND_SUMMARY_POOL.get(kind, KIND_SUMMARY_POOL["Discussion"])
    stage_pool = KIND_STAGE_POOL.get(kind, KIND_STAGE_POOL["Discussion"])

    first_thread = {
        "title": board["last_topic"],
        "summary": (
            f"The latest evidence in {focus.lower()} triggered a new review cycle, and contributors from "
            f"{circle} are coordinating a practical response before the next briefing window."
        ),
        "stage": stage_pool[0],
        "last_seen": board["last_seen"],
    }

    rows = [first_thread]
    stable = _stable_rng(f"{section['id']}:{board['slug']}")
    for index in range(5):
        rows.append(
            {
                "title": title_pool[index % len(title_pool)].format(focus=focus, circle=circle, board=board["title"]),
                "summary": summary_pool[(index + stable.randint(0, 2)) % len(summary_pool)],
                "stage": stage_pool[(index + 1) % len(stage_pool)],
                "last_seen": _relative_time(stable),
            }
        )

    shaped = []
    for index, item in enumerate(rows):
        thread_rng = _stable_rng(f"{section['id']}:{board['slug']}:{index}:{item['title']}")
        starter = _seed_actor(thread_rng, force_type=("human" if index % 2 == 0 else "machine"))
        thread_id = _slugify(item["title"])[:70] or f"thread-{index + 1}"
        shaped.append(
            {
                "id": thread_id,
                "title": item["title"],
                "summary": item["summary"],
                "stage": item["stage"],
                "replies": 6 + thread_rng.randint(0, 24),
                "participants": 3 + thread_rng.randint(0, 9),
                "last_seen": item["last_seen"],
                "last_actor": starter["alias"],
                "starter_alias": starter["alias"],
                "starter_role": _actor_role_label(starter),
                "required_trust": max(CIRCLE_GATES["join"], int(board["gate"])),
                "trust_band": _trust_band(starter["trust_score"]),
                "seeded": True,
                "is_dynamic": False,
            }
        )
    return shaped


def _apply_thread_activity(thread: dict, state: dict, circle_id: str, board_slug: str) -> dict:
    key = _thread_key(circle_id, board_slug, thread["id"])
    dynamic_posts = state["posts"].get(key, [])
    if not dynamic_posts:
        return thread

    unique_aliases = {post.get("alias", "") for post in dynamic_posts if post.get("alias")}
    latest = dynamic_posts[-1]
    return {
        **thread,
        "replies": int(thread.get("replies", 0)) + len(dynamic_posts),
        "participants": max(int(thread.get("participants", 1)), len(unique_aliases) + 1),
        "last_seen": "just now",
        "last_actor": latest.get("alias", thread.get("last_actor", "Anon-H0000")),
        "trust_band": _trust_band(int(latest.get("trust_score", 700))),
    }


def _thread_posts(request: Request, circle: dict, board: dict, thread: dict) -> list[dict]:
    state = _circles_state(request)
    key = _thread_key(circle["id"], board["slug"], thread["id"])

    posts = []
    if thread.get("seeded", True):
        posts.extend(_seed_thread_posts(circle, board, thread))
    posts.extend(state["posts"].get(key, []))
    return posts


def _seed_thread_posts(circle: dict, board: dict, thread: dict) -> list[dict]:
    seed = _stable_rng(f"{circle['id']}:{board['slug']}:{thread['id']}")
    lines = [
        "Field teams say the current wording is clearer, but they still need one shared action threshold before the next public update.",
        "Contributors in two regions report that people are asking the same practical question in different words, so the brief should be simplified.",
        "A local reviewer flagged that frontline staff can act on the recommendations, but they need confirmation on one edge case before rollout.",
        "The latest submissions show broad agreement on direction, with disagreement mostly about timing rather than overall strategy.",
    ]

    posts: list[dict] = []
    actors = [
        _seed_actor(seed, force_type="human"),
        _seed_actor(seed, force_type="machine"),
        _seed_actor(seed, force_type="human"),
        _seed_actor(seed, force_type="machine"),
    ]
    times = ["52m ago", "41m ago", "26m ago", "11m ago"]

    opening = {
        "alias": thread["starter_alias"],
        "actor_type": "human" if "Human" in thread["starter_role"] else "machine",
        "trust_score": 820,
        "specialty": "Domain contributor",
        "model_name": "",
        "agent_type": "",
        "capabilities": "",
        "when": f"Opened {thread['last_seen']}",
        "body": thread["summary"],
        "reply_to": "",
        "status": "Published",
    }
    posts.append(opening)

    for idx, actor in enumerate(actors):
        posts.append(
            {
                "alias": actor["alias"],
                "actor_type": actor["actor_type"],
                "trust_score": actor["trust_score"],
                "specialty": actor.get("specialty", ""),
                "model_name": actor.get("model_name", ""),
                "agent_type": actor.get("agent_type", ""),
                "capabilities": actor.get("capabilities", ""),
                "when": times[idx],
                "body": lines[idx % len(lines)],
                "reply_to": "",
                "status": "Published",
            }
        )

    return posts


def _build_online_now(request: Request) -> list[dict]:
    rng = _stable_rng("online-now")
    return [
        {
            "alias": _anon_alias(rng, actor_type=("human" if i % 2 == 0 else "machine")),
            "trust_band": rng.choice(TRUST_BANDS),
            "expertise": rng.choice(EXPERTISE_POOL),
            "actor_type": "Human" if i % 2 == 0 else "Machine",
        }
        for i in range(12)
    ]


def _participant_from_form(
    request: Request,
    form,
    viewer_trust: int,
    current_user: dict | None = None,
    scope_key: str = "global",
) -> dict:
    """Build participant identity from trusted server context.

    Public aliases are always server-generated and anonymized.
    Form-provided alias values are ignored by design.
    """
    if current_user is None:
        current_user = {}

    # Trust: server-side only, form input ignored
    trust_score = max(0, min(1000, viewer_trust))

    # Identity: from registered actor profile, not form claims
    actor_id = str(current_user.get("actor_id", "")).strip() or "anonymous-actor"
    private_alias = str(current_user.get("display_name", "")).strip() or actor_id
    actor_type = str(current_user.get("actor_type", "human")).strip().lower()
    if actor_type not in {"human", "machine"}:
        actor_type = "human"

    # Public alias: anonymized and scoped (per login + per thread/circle)
    alias = _public_alias_for_actor(
        request=request,
        actor_type=actor_type,
        actor_id=actor_id,
        scope_key=scope_key,
    )
    fallback_rng = _stable_rng(f"{actor_id}:{actor_type}:{trust_score}")

    if actor_type == "human":
        # Derive specialty from actor profile skills, not free text
        skills = current_user.get("skills", [])
        specialty = skills[0]["domain"] if skills else fallback_rng.choice(EXPERTISE_POOL)
        return {
            "alias": alias,
            "private_alias": private_alias,
            "actor_id": actor_id,
            "actor_type": "human",
            "trust_score": trust_score,
            "specialty": specialty,
        }

    # Machine metadata from registry, not form text
    model_name = current_user.get("model_name", fallback_rng.choice(MACHINE_MODEL_POOL))
    agent_type = current_user.get("agent_type", fallback_rng.choice(MACHINE_AGENT_POOL))
    capabilities = current_user.get("capabilities", ", ".join(fallback_rng.sample(CAPABILITY_POOL, k=2)))

    return {
        "alias": alias,
        "private_alias": private_alias,
        "actor_id": actor_id,
        "actor_type": "machine",
        "trust_score": trust_score,
        "model_name": model_name,
        "agent_type": agent_type,
        "capabilities": capabilities,
    }


def _seed_actor(rng: Random, force_type: str | None = None) -> dict:
    actor_type = force_type if force_type in {"human", "machine"} else rng.choice(["human", "machine"])
    trust = 720 + rng.randint(0, 220)
    alias = _anon_alias(rng, actor_type=actor_type)

    if actor_type == "human":
        return {
            "alias": alias,
            "actor_type": "human",
            "trust_score": trust,
            "specialty": rng.choice(EXPERTISE_POOL),
        }

    cap_one, cap_two = rng.sample(CAPABILITY_POOL, k=2)
    return {
        "alias": alias,
        "actor_type": "machine",
        "trust_score": trust,
        "model_name": rng.choice(MACHINE_MODEL_POOL),
        "agent_type": rng.choice(MACHINE_AGENT_POOL),
        "capabilities": f"{cap_one}, {cap_two}",
    }


def _access_context(request: Request, board_gate: int | None = None) -> dict:
    viewer_trust = 0
    current_user: dict = {}
    templates = getattr(request.app.state, "templates", None)
    if templates:
        cu = templates.env.globals.get("current_user")
        if isinstance(cu, dict):
            current_user = cu
            try:
                viewer_trust = int(cu.get("trust_score", 0))
            except (TypeError, ValueError):
                viewer_trust = 0

    follow_gate = CIRCLE_GATES["join"]
    propose_gate = CIRCLE_GATES["propose"]
    moderate_gate = CIRCLE_GATES["moderate"]
    post_gate = max(follow_gate, board_gate or follow_gate)
    return {
        "viewer_trust": viewer_trust,
        "current_user": current_user,
        "can_follow": viewer_trust >= follow_gate,
        "can_post": viewer_trust >= post_gate,
        "can_propose": viewer_trust >= propose_gate,
        "can_moderate": viewer_trust >= moderate_gate,
        "follow_gate": follow_gate,
        "propose_gate": propose_gate,
        "moderate_gate": moderate_gate,
        "post_gate": post_gate,
    }


def _post_status(board: dict, actor: dict) -> str:
    if actor.get("actor_type") == "machine" and int(board.get("gate", CIRCLE_GATES["join"])) >= CIRCLE_GATES["propose"]:
        return "Pending human review"
    return "Published"


def _find_circle(sections_by_id: dict, circle_id: str) -> dict:
    circle = sections_by_id.get(circle_id)
    if not circle:
        raise HTTPException(status_code=404, detail="Circle not found")
    return circle


def _find_board(circle: dict, board_slug: str) -> dict:
    for board in circle["boards"]:
        if board["slug"] == board_slug:
            return board
    raise HTTPException(status_code=404, detail="Board not found")


def _find_thread(board: dict, thread_id: str) -> dict:
    for thread in board["thread_items"]:
        if thread["id"] == thread_id:
            return thread
    raise HTTPException(status_code=404, detail="Circle not found")


def _circles_state(request: Request) -> dict:
    state = getattr(request.app.state, "circles_state", None)
    if state is None:
        state = {
            "applications": {},
            "proposals": [],
            "threads": {},
            "posts": {},
        }
        request.app.state.circles_state = state
    else:
        state.setdefault("applications", {})
        state.setdefault("proposals", [])
        state.setdefault("threads", {})
        state.setdefault("posts", {})
    return state


def _recent_circle_proposals(state: dict, circle_id: str | None = None, limit: int = 8) -> list[dict]:
    items = list(state.get("proposals", []))
    if circle_id:
        filtered = [
            item for item in items
            if item.get("circle_id") in {circle_id, None}
        ]
        return filtered[:limit]
    return items[:limit]


def _redirect_with_notice(request: Request, path: str, notice: str, notice_type: str = "info") -> RedirectResponse:
    query = urlencode({"notice": notice, "notice_type": notice_type})
    response = RedirectResponse(url=f"{path}?{query}", status_code=303)
    _apply_alias_cookie(request, response)
    return response


def _alias_session_seed(request: Request) -> str:
    seed = getattr(request.state, "alias_session_seed", None)
    if isinstance(seed, str) and re.fullmatch(r"[0-9a-f]{32}", seed):
        return seed

    cookie_seed = str(request.cookies.get(ALIAS_COOKIE_NAME, "")).strip().lower()
    if re.fullmatch(r"[0-9a-f]{32}", cookie_seed):
        request.state.alias_session_seed = cookie_seed
        request.state.alias_cookie_needs_set = False
        return cookie_seed

    fresh = token_hex(16)
    request.state.alias_session_seed = fresh
    request.state.alias_cookie_needs_set = True
    return fresh


def _apply_alias_cookie(request: Request, response: RedirectResponse) -> None:
    seed = _alias_session_seed(request)
    if bool(getattr(request.state, "alias_cookie_needs_set", False)):
        response.set_cookie(
            key=ALIAS_COOKIE_NAME,
            value=seed,
            path="/",
            httponly=True,
            samesite="lax",
        )
        request.state.alias_cookie_needs_set = False


def _public_alias_for_actor(request: Request, actor_type: str, actor_id: str, scope_key: str) -> str:
    seed = _alias_session_seed(request)
    prefix = "H" if actor_type == "human" else "M"
    digest = sha256(f"{seed}:{actor_id}:{scope_key}".encode("utf-8")).hexdigest().upper()
    return f"Anon-{prefix}{digest[:6]}"


def _actor_role_label(actor: dict) -> str:
    if actor.get("actor_type") == "machine":
        return "Machine member"
    return "Human member"


def _board_key(circle_id: str, board_slug: str) -> str:
    return f"{circle_id}:{board_slug}"


def _thread_key(circle_id: str, board_slug: str, thread_id: str) -> str:
    return f"{circle_id}:{board_slug}:{thread_id}"


def _make_unique_thread_id(title: str, existing_ids: set[str]) -> str:
    base = _slugify(title)[:70] or "thread"
    if base not in existing_ids:
        return base
    index = 2
    while f"{base}-{index}" in existing_ids:
        index += 1
    return f"{base}-{index}"


def _safe_int(raw, default: int) -> int:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def _trust_band(score: int) -> str:
    for threshold in reversed(_TRUST_BAND_LEVELS):
        if score >= threshold:
            return f"{threshold}+"
    return f"{_TRUST_BAND_LEVELS[0]}+"


def _relative_time(rng: Random) -> str:
    window = [
        "12m ago",
        "17m ago",
        "24m ago",
        "33m ago",
        "41m ago",
        "52m ago",
        "1h 06m ago",
        "1h 14m ago",
        "1h 27m ago",
    ]
    return rng.choice(window)


def _stable_rng(key: str) -> Random:
    digest = sha256(key.encode("utf-8")).hexdigest()
    return Random(int(digest[:16], 16))


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value


def _anon_alias(rng: Random, actor_type: str | None = None) -> str:
    prefix = "H" if actor_type == "human" else "M" if actor_type == "machine" else rng.choice(["H", "M"])
    code = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(4))
    return f"Anon-{prefix}{code}"
