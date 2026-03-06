"""Registration — human and machine actor onboarding."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from genesis.web.deps import get_service, get_templates
from genesis.web.negotiate import respond, wants_json

router = APIRouter()


@router.get("")
async def registration_form(request: Request):
    templates = get_templates(request)
    return respond(request, templates, "registration.html", {"request": request})


@router.post("")
async def register_human(
    request: Request,
    actor_id: str = Form(...),
    region: str = Form(...),
    organization: str = Form("Independent"),
):
    service = get_service()
    result = service.register_human(
        actor_id=actor_id, region=region, organization=organization,
    )
    if wants_json(request):
        from fastapi.responses import JSONResponse
        if result.success:
            return JSONResponse(result.data, status_code=201)
        return JSONResponse({"errors": result.errors}, status_code=422)
    if result.success:
        return RedirectResponse(f"/actors/{actor_id}", status_code=303)
    templates = get_templates(request)
    return templates.TemplateResponse(
        "registration.html",
        {"request": request, "errors": result.errors},
        status_code=422,
    )


@router.get("/machine")
async def machine_registration_form(request: Request):
    templates = get_templates(request)
    return respond(request, templates, "registration_machine.html", {"request": request})


@router.post("/machine")
async def register_machine(
    request: Request,
    actor_id: str = Form(...),
    operator_id: str = Form(...),
    region: str = Form(...),
    organization: str = Form("Independent"),
    model_family: str = Form("generic_model"),
):
    service = get_service()
    result = service.register_machine(
        actor_id=actor_id,
        operator_id=operator_id,
        region=region,
        organization=organization,
        model_family=model_family,
    )
    if wants_json(request):
        from fastapi.responses import JSONResponse
        if result.success:
            return JSONResponse(result.data, status_code=201)
        return JSONResponse({"errors": result.errors}, status_code=422)
    if result.success:
        return RedirectResponse(f"/actors/{actor_id}", status_code=303)
    templates = get_templates(request)
    return templates.TemplateResponse(
        "registration_machine.html",
        {"request": request, "errors": result.errors},
        status_code=422,
    )
