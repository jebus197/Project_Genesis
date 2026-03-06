"""Genesis web application — FastAPI + Jinja2 + HTMX.

Usage:
    uvicorn genesis.web.app:create_app --factory
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from genesis.web.deps import get_service
from genesis.web.routers import landing, registration, missions, profiles, audit, wallet, poc, circles, social
from genesis.web.social_context import social_globals


def create_app() -> FastAPI:
    app = FastAPI(title="Genesis", version="0.1.0")

    # Service is initialized once for app lifecycle decisions (PoC/live mode).
    service = get_service()
    service_status = service.status()
    poc_mode_active = bool(
        service_status.get("first_light", {}).get("poc_mode_active", False),
    )

    # Static files
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Templates
    template_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=template_dir)
    app.state.templates = templates

    # Global template context
    templates.env.globals["poc_mode"] = poc_mode_active

    # Social layout globals — current_user, circles, stats, etc.
    # In PoC mode these are demo data; post-First Light they query the service.
    for key, value in social_globals().items():
        templates.env.globals[key] = value

    # Routers
    app.include_router(landing.router)
    app.include_router(registration.router, prefix="/register", tags=["registration"])
    app.include_router(missions.router, prefix="/missions", tags=["missions"])
    app.include_router(profiles.router, prefix="/actors", tags=["profiles"])
    app.include_router(audit.router, prefix="/audit", tags=["audit"])
    app.include_router(wallet.router, prefix="/wallet", tags=["wallet"])
    app.include_router(poc.router, prefix="/poc", tags=["poc"])
    app.include_router(circles.router, prefix="/circles", tags=["circles"])
    app.include_router(social.router, tags=["social"])

    # Error handlers
    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        return templates.TemplateResponse(
            "errors/404.html", {"request": request}, status_code=404,
        )

    @app.exception_handler(500)
    async def server_error(request: Request, exc):
        return templates.TemplateResponse(
            "errors/500.html", {"request": request}, status_code=500,
        )

    # Seed demo data only while PoC mode is active and state is otherwise empty.
    if poc_mode_active:
        has_existing_data = (
            service_status.get("actors", {}).get("total", 0) > 0
            or service_status.get("missions", {}).get("total", 0) > 0
            or service_status.get("market", {}).get("total_listings", 0) > 0
        )
        if not has_existing_data:
            from genesis.web.seed import seed_poc_data
            seed_poc_data(service)

    return app
