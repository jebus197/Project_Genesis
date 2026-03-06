"""Wallet and payments — escrow lifecycle and commission breakdowns."""

from fastapi import APIRouter, Request

from genesis.web.deps import get_service, get_templates
from genesis.web.negotiate import respond

router = APIRouter()


@router.get("")
async def wallet_page(request: Request):
    service = get_service()
    templates = get_templates(request)
    status = service.status()
    context = {
        "request": request,
        "status": status,
    }
    return respond(request, templates, "wallet.html", context)
