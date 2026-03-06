"""PoC mode indicators — sustainability tracking."""

from fastapi import APIRouter, Request

from genesis.web.deps import get_service, get_templates
from genesis.web.negotiate import respond

router = APIRouter()


@router.get("")
async def poc_status(request: Request):
    service = get_service()
    templates = get_templates(request)
    status = service.status()
    context = {
        "request": request,
        "status": status,
        "first_light": status.get("first_light", {}),
    }
    return respond(request, templates, "poc.html", context)
