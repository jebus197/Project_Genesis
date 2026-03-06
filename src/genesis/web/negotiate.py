"""Content negotiation — JSON for machines, HTML for humans."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates


def wants_json(request: Request) -> bool:
    """True if the client prefers JSON over HTML."""
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return True
    return False


def is_htmx(request: Request) -> bool:
    """True if this is an HTMX partial request."""
    return request.headers.get("HX-Request") == "true"


def respond(request: Request, templates: Jinja2Templates,
            template_name: str, context: dict):
    """Return JSON or rendered HTML based on client preference."""
    if wants_json(request):
        json_data = {k: v for k, v in context.items() if k != "request"}
        return JSONResponse(_make_serialisable(json_data))
    return templates.TemplateResponse(template_name, context)


def _make_serialisable(obj):
    """Best-effort conversion for JSON serialisation."""
    if isinstance(obj, dict):
        return {k: _make_serialisable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serialisable(item) for item in obj]
    if hasattr(obj, "__dict__"):
        return {k: _make_serialisable(v) for k, v in obj.__dict__.items()
                if not k.startswith("_")}
    try:
        import json
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)
