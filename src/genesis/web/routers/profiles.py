"""Actor profiles — trust evidence dashboard."""

from fastapi import APIRouter, Request

from genesis.web.deps import get_service, get_templates
from genesis.web.negotiate import respond, wants_json

router = APIRouter()


@router.get("/{actor_id}")
async def actor_profile(request: Request, actor_id: str):
    service = get_service()
    templates = get_templates(request)
    actor = service.get_actor(actor_id)
    if actor is None:
        if wants_json(request):
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "Actor not found"}, status_code=404)
        return templates.TemplateResponse(
            "errors/404.html", {"request": request}, status_code=404,
        )
    trust = service.get_trust(actor_id)
    skills = service.get_actor_skills(actor_id)
    # Convert objects to dicts for template access
    actor_data = {
        "actor_id": actor.actor_id,
        "actor_kind": actor.actor_kind.value if hasattr(actor.actor_kind, 'value') else str(actor.actor_kind),
        "status": actor.status.value if hasattr(actor.status, 'value') else str(actor.status),
        "region": actor.region,
        "organization": actor.organization,
    }
    trust_data = {}
    if trust is not None:
        trust_data = {
            "score": trust.score,
            "quality": trust.quality,
            "reliability": trust.reliability,
            "volume": trust.volume,
            "effort": trust.effort,
        }
    skills_data = {}
    if skills is not None:
        skills_data = {
            "skills": [
                {"skill_id": str(s.skill_id), "proficiency_score": s.proficiency_score}
                for s in skills.skills
            ],
        }

    # Shape into profile format for social layout
    actor_kind = actor.actor_kind.value if hasattr(actor.actor_kind, 'value') else str(actor.actor_kind)
    is_machine = actor_kind == "machine"
    initials = actor.actor_id[:2].upper()
    display_name = actor.actor_id.replace("-", " ").title()

    profile = {
        "actor_id": actor.actor_id,
        "actor_type": "machine" if is_machine else "human",
        "display_name": display_name,
        "initials": initials,
        "trust_score": int(trust.score * 1000) if trust else 0,
        "quality_score": int(trust.quality * 100) if trust else None,
        "volume_score": int(trust.volume * 100) if trust else None,
        "completed_missions": 0,  # Not yet tracked in service layer
        "join_date": None,
        "operator_name": None,
        "machine_tier": 0 if is_machine else None,
        "circles": [],  # Not yet in service layer
    }

    context = {
        "request": request,
        "active_tab": None,  # Profile isn't a nav tab
        "actor": actor_data,
        "trust": trust_data,
        "skills": skills_data,
        "profile": profile,
    }
    return respond(request, templates, "social_profile.html", context)
