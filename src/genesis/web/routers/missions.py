"""Mission board — work discovery, bidding, submission, review, settlement."""

import hashlib
from urllib.parse import quote_plus
from uuid import uuid4

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from genesis.web.deps import get_service, get_templates
from genesis.web.negotiate import respond, wants_json, is_htmx
from genesis.web.poc_scenarios import mission_catalog_list, mission_by_id, related_missions

router = APIRouter()

RISK_MIN_TRUST = {"R1": 720, "R2": 790, "R3": 840}
RISK_REQUIRED_LEVEL = {"R1": "intermediate", "R2": "advanced", "R3": "expert"}
RISK_CAPACITY = {"R1": 8, "R2": 10, "R3": 12}
LEVEL_RANK = {"baseline": 1, "intermediate": 2, "advanced": 3, "expert": 4}
SENSITIVE_DOMAINS = {"healthcare", "governance", "justice", "legal", "constitutional", "biosecurity"}
DOMAIN_ALIASES = {
    "data-analysis": "audit",
    "verification": "audit",
    "coordination": "governance",
}

LIFECYCLE_ORDER = [
    "active_operations",
    "org_submitted",
    "ratification_queue",
    "ratified_in_force",
    "validated_archive",
]

LIFECYCLE_LABELS = {
    "active_operations": "Current Community Missions",
    "org_submitted": "Domain Org Proposals",
    "ratification_queue": "Ratification Queue",
    "ratified_in_force": "Ratified and In Force",
    "validated_archive": "Validated Outcomes",
}

LIFECYCLE_DESCRIPTIONS = {
    "active_operations": "Live missions currently being worked, reviewed, and settled.",
    "org_submitted": "New or significant proposals submitted by domain expert organisations.",
    "ratification_queue": "Decisions that require chamber ratification before full activation.",
    "ratified_in_force": "Decisions that passed ratification and are now active policy.",
    "validated_archive": "Completed missions with validated evidence trails.",
}


@router.get("")
async def mission_board(
    request: Request,
    q: str = Query(""),
    domain: str = Query(None),
    sort: str = Query("fit"),
    limit: int = Query(20),
):
    service = get_service()
    templates = get_templates(request)
    domain_tags = [domain] if domain else None
    result = service.search_listings(domain_tags=domain_tags, limit=limit)
    service_listings = [
        _enrich_mission(_shape_service_listing(listing))
        for listing in result.data.get("listings", [])
    ]
    hypothetical = _filter_hypothetical_missions(mission_catalog_list(), q=q, domain=domain)
    hypothetical = _sort_hypothetical_missions(hypothetical, sort=sort)
    hypothetical = [_enrich_mission(dict(mission)) for mission in hypothetical]
    board_missions = service_listings + hypothetical
    lifecycle_sections = _group_missions_by_lifecycle(board_missions)
    context = {
        "request": request,
        "active_tab": "missions",
        "listings": service_listings,
        "hypothetical_missions": hypothetical,
        "lifecycle_sections": lifecycle_sections,
        "mission_catalog_count": len(hypothetical),
        "live_mission_count": len(service_listings),
        "query": q,
        "sort": sort,
        "domain": domain or "",
    }
    if is_htmx(request):
        return templates.TemplateResponse("partials/mission_list.html", context)
    return respond(request, templates, "missions/board.html", context)


@router.get("/create")
async def create_mission_form(request: Request):
    """Render the mission creation form."""
    templates = get_templates(request)
    context = {
        "request": request,
        "active_tab": "missions",
        "form_data": {},
        "errors": [],
    }
    return respond(request, templates, "missions/create.html", context)


@router.post("/create")
async def create_mission(request: Request):
    """Create a new mission listing from form submission."""
    service = get_service()
    templates = get_templates(request)
    form = await request.form()

    title = str(form.get("title", "")).strip()
    description = str(form.get("description", "")).strip()
    domain = str(form.get("domain", "general")).strip()
    risk_tier = str(form.get("risk_tier", "R2")).strip()
    reward_raw = str(form.get("reward", "")).strip()
    deadline_days = str(form.get("deadline_days", "7")).strip()

    form_data = {
        "title": title,
        "description": description,
        "domain": domain,
        "risk_tier": risk_tier,
        "reward": reward_raw,
        "deadline_days": deadline_days,
    }
    errors: list[str] = []

    if not title:
        errors.append("Title is required.")
    if not description:
        errors.append("Description is required.")
    try:
        reward = int(reward_raw)
        if reward < 1:
            errors.append("Reward must be at least 1.")
    except (ValueError, TypeError):
        errors.append("Reward must be a whole number.")
        reward = 0
    try:
        days = int(deadline_days)
        if days < 1 or days > 90:
            errors.append("Deadline must be between 1 and 90 days.")
    except (ValueError, TypeError):
        errors.append("Deadline must be a whole number of days.")

    if errors:
        if wants_json(request):
            return JSONResponse({"errors": errors}, status_code=422)
        context = {
            "request": request,
            "active_tab": "missions",
            "form_data": form_data,
            "errors": errors,
        }
        return templates.TemplateResponse("missions/create.html", context, status_code=422)

    viewer = _current_user_from_request(request)
    creator_id = str(viewer.get("actor_id", "demo-human-1"))
    listing_id = f"mission-{uuid4().hex[:12]}"

    result = service.create_listing(
        listing_id=listing_id,
        title=title,
        description=description,
        creator_id=creator_id,
        domain_tags=[domain],
        preferences={"risk_tier": risk_tier, "reward": reward, "deadline_days": int(deadline_days)},
    )

    if not result.success:
        if wants_json(request):
            return JSONResponse({"errors": result.errors}, status_code=422)
        context = {
            "request": request,
            "active_tab": "missions",
            "form_data": form_data,
            "errors": result.errors,
        }
        return templates.TemplateResponse("missions/create.html", context, status_code=422)

    # Auto-open and accept bids for PoC flow
    service.open_listing(listing_id)
    service.start_accepting_bids(listing_id)

    if wants_json(request):
        return JSONResponse(
            {"listing_id": listing_id, "state": "accepting_bids"},
            status_code=201,
        )
    return RedirectResponse(
        f"/missions/{listing_id}?notice=Mission+created+and+open+for+bids.&notice_level=success",
        status_code=303,
    )


@router.get("/{listing_id}")
async def mission_detail(
    request: Request,
    listing_id: str,
    notice: str = Query(""),
    notice_level: str = Query("info"),
):
    service = get_service()
    templates = get_templates(request)
    listing_data, bids_data, bid_workflow = _resolve_listing_payload(service, listing_id)
    if listing_data is None:
        if wants_json(request):
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "Listing not found"}, status_code=404)
        return templates.TemplateResponse(
            "errors/404.html", {"request": request}, status_code=404,
        )

    viewer = _current_user_from_request(request)
    apply_notice_level = notice_level if notice_level in {"info", "success", "warning"} else "info"

    context = {
        "request": request,
        "active_tab": "missions",
        "listing": listing_data,
        "bids": bids_data,
        "bid_workflow": bid_workflow,
        "application_gate": _build_application_gate(listing_data, viewer),
        "application_notice": notice,
        "application_notice_level": apply_notice_level,
        "related_examples": related_missions(
            listing_data.get("circle_name", "Mission Domain"),
            listing_data.get("listing_id", ""),
        ),
    }
    return respond(request, templates, "missions/detail.html", context)


@router.post("/{listing_id}/apply")
async def apply_to_mission(
    request: Request,
    listing_id: str,
):
    service = get_service()
    listing_data, _, _ = _resolve_listing_payload(service, listing_id)
    if listing_data is None:
        templates = get_templates(request)
        if wants_json(request):
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "Listing not found"}, status_code=404)
        return templates.TemplateResponse(
            "errors/404.html", {"request": request}, status_code=404,
        )

    viewer = _current_user_from_request(request)
    gate = _build_application_gate(listing_data, viewer)

    if gate["outcome"] == "intake_closed":
        return _apply_redirect(listing_id, gate["outcome_message"], "warning")
    if gate["outcome"] == "capacity_full":
        return _apply_redirect(listing_id, gate["outcome_message"], "warning")
    if gate["outcome"] == "trust_blocked":
        return _apply_redirect(listing_id, gate["outcome_message"], "warning")
    if gate["outcome"] == "skills_blocked":
        return _apply_redirect(listing_id, gate["outcome_message"], "warning")
    if gate["outcome"] == "human_review":
        return _apply_redirect(
            listing_id,
            "Application submitted and queued for human review.",
            "info",
        )

    # Eligible path: submit to live listing or stage in PoC catalogue.
    if listing_data.get("source") == "live":
        worker_id = viewer.get("actor_id", "demo-human-1")
        bid_id = f"web-{listing_id[:10]}-{uuid4().hex[:8]}"
        result = service.submit_bid(bid_id=bid_id, listing_id=listing_id, worker_id=worker_id)
        if result.success:
            return _apply_redirect(listing_id, f"Application submitted ({bid_id}).", "success")
        message = result.errors[0] if result.errors else "Application could not be submitted."
        return _apply_redirect(listing_id, message, "warning")

    return _apply_redirect(
        listing_id,
        "Application staged in the mission queue (PoC).",
        "success",
    )


@router.post("/{listing_id}/bid")
async def submit_bid(
    request: Request,
    listing_id: str,
):
    service = get_service()
    listing_data, _, _ = _resolve_listing_payload(service, listing_id)
    if listing_data is None:
        templates = get_templates(request)
        if wants_json(request):
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "Listing not found"}, status_code=404)
        return templates.TemplateResponse(
            "errors/404.html", {"request": request}, status_code=404,
        )

    viewer = _current_user_from_request(request)
    gate = _build_application_gate(listing_data, viewer)
    if gate["outcome"] != "eligible":
        message = gate["outcome_message"]
        if gate["outcome"] == "human_review":
            message = "Direct bid submission is disabled for missions pending human review."
        if wants_json(request):
            from fastapi.responses import JSONResponse
            return JSONResponse({"errors": [message]}, status_code=422)
        return _apply_redirect(listing_id, message, "warning")

    if listing_data.get("source") != "live":
        if wants_json(request):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                {"status": "staged", "message": "Bid staged in mission queue (PoC)."},
                status_code=201,
            )
        return _apply_redirect(listing_id, "Bid staged in mission queue (PoC).", "success")

    bid_id = f"web-{listing_id[:10]}-{uuid4().hex[:8]}"
    worker_id = str(viewer.get("actor_id", "demo-human-1"))
    result = service.submit_bid(
        bid_id=bid_id, listing_id=listing_id, worker_id=worker_id,
    )
    if wants_json(request):
        from fastapi.responses import JSONResponse
        if result.success:
            payload = dict(result.data or {})
            payload.setdefault("bid_id", bid_id)
            payload.setdefault("worker_id", worker_id)
            return JSONResponse(payload, status_code=201)
        return JSONResponse({"errors": result.errors}, status_code=422)
    if result.success:
        return _apply_redirect(listing_id, f"Bid submitted ({bid_id}).", "success")
    templates = get_templates(request)
    return templates.TemplateResponse(
        "missions/detail.html",
        {"request": request, "errors": result.errors},
        status_code=422,
    )


@router.get("/{listing_id}/submit-work")
async def submit_work_form(request: Request, listing_id: str):
    """Render the work submission form."""
    service = get_service()
    templates = get_templates(request)
    listing_data, _, _ = _resolve_listing_payload(service, listing_id)
    if listing_data is None:
        if wants_json(request):
            return JSONResponse({"error": "Listing not found"}, status_code=404)
        return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)

    context = {
        "request": request,
        "active_tab": "missions",
        "listing": listing_data,
        "errors": [],
    }
    return respond(request, templates, "missions/submit_work.html", context)


@router.post("/{listing_id}/submit-work")
async def submit_work(request: Request, listing_id: str):
    """Submit completed work for a mission."""
    service = get_service()
    templates = get_templates(request)
    form = await request.form()

    listing_data, _, _ = _resolve_listing_payload(service, listing_id)
    if listing_data is None:
        if wants_json(request):
            return JSONResponse({"error": "Listing not found"}, status_code=404)
        return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)

    evidence_summary = str(form.get("evidence_summary", "")).strip()
    artifact_references = str(form.get("artifact_references", "")).strip()

    errors: list[str] = []
    if not evidence_summary:
        errors.append("Evidence summary is required.")

    if errors:
        if wants_json(request):
            return JSONResponse({"errors": errors}, status_code=422)
        context = {
            "request": request,
            "active_tab": "missions",
            "listing": listing_data,
            "errors": errors,
        }
        return templates.TemplateResponse("missions/submit_work.html", context, status_code=422)

    # Generate evidence hashes from summary + artifact references
    evidence_hashes = []
    summary_hash = hashlib.sha256(evidence_summary.encode()).hexdigest()
    evidence_hashes.append(summary_hash)
    for line in artifact_references.splitlines():
        line = line.strip()
        if line:
            evidence_hashes.append(hashlib.sha256(line.encode()).hexdigest())

    # For live listings with a workflow, use the workflow path
    # For PoC/hypothetical, stage the submission
    if listing_data.get("source") == "live":
        # Check if a workflow exists for this listing
        wf = _find_workflow_for_listing(service, listing_id)
        if wf is not None:
            result = service.submit_work_workflow(wf.workflow_id, evidence_hashes)
            if not result.success:
                if wants_json(request):
                    return JSONResponse({"errors": result.errors}, status_code=422)
                context = {
                    "request": request,
                    "active_tab": "missions",
                    "listing": listing_data,
                    "errors": result.errors,
                }
                return templates.TemplateResponse("missions/submit_work.html", context, status_code=422)
        # Even without a workflow, record the submission intent

    if wants_json(request):
        return JSONResponse({
            "status": "submitted",
            "listing_id": listing_id,
            "evidence_count": len(evidence_hashes),
        }, status_code=201)
    return RedirectResponse(
        f"/missions/{listing_id}?notice=Work+submitted+for+review.+{len(evidence_hashes)}+evidence+records+attached.&notice_level=success",
        status_code=303,
    )


@router.get("/{listing_id}/review")
async def review_form(request: Request, listing_id: str):
    """Render the review form for submitted work."""
    service = get_service()
    templates = get_templates(request)
    listing_data, bids_data, _ = _resolve_listing_payload(service, listing_id)
    if listing_data is None:
        if wants_json(request):
            return JSONResponse({"error": "Listing not found"}, status_code=404)
        return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)

    # Gather evidence items for display
    evidence_items = _gather_evidence(service, listing_id, listing_data)

    # Build commission breakdown preview
    reward = listing_data.get("preferences", {}).get("reward", 100) if isinstance(listing_data.get("preferences"), dict) else 100
    commission_breakdown = _build_commission_preview(reward)

    context = {
        "request": request,
        "active_tab": "missions",
        "listing": listing_data,
        "evidence_items": evidence_items,
        "commission_breakdown": commission_breakdown,
        "breakdown": commission_breakdown,
        "escrow_state": "locked",
        "errors": [],
    }
    return respond(request, templates, "missions/review.html", context)


@router.post("/{listing_id}/review")
async def submit_review_route(request: Request, listing_id: str):
    """Submit a review verdict for a mission."""
    service = get_service()
    templates = get_templates(request)
    form = await request.form()

    listing_data, _, _ = _resolve_listing_payload(service, listing_id)
    if listing_data is None:
        if wants_json(request):
            return JSONResponse({"error": "Listing not found"}, status_code=404)
        return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)

    verdict = str(form.get("verdict", "")).strip().upper()
    review_notes = str(form.get("review_notes", "")).strip()

    errors: list[str] = []
    if verdict not in {"APPROVE", "REJECT", "ABSTAIN"}:
        errors.append("Select a verdict: Approve, Reject, or Abstain.")
    if not review_notes:
        errors.append("Review notes are required. Explain your verdict.")

    if errors:
        evidence_items = _gather_evidence(service, listing_id, listing_data)
        if wants_json(request):
            return JSONResponse({"errors": errors}, status_code=422)
        context = {
            "request": request,
            "active_tab": "missions",
            "listing": listing_data,
            "evidence_items": evidence_items,
            "commission_breakdown": None,
            "breakdown": None,
            "escrow_state": "locked",
            "errors": errors,
        }
        return templates.TemplateResponse("missions/review.html", context, status_code=422)

    viewer = _current_user_from_request(request)
    reviewer_id = str(viewer.get("actor_id", "demo-human-1"))

    # For live listings, submit through service layer
    if listing_data.get("source") == "live":
        # Find associated mission
        mission_id = _find_mission_for_listing(service, listing_id)
        if mission_id:
            result = service.submit_review(
                mission_id=mission_id,
                reviewer_id=reviewer_id,
                verdict=verdict,
                notes=review_notes,
            )
            if not result.success:
                if wants_json(request):
                    return JSONResponse({"errors": result.errors}, status_code=422)
                return _apply_redirect(listing_id, result.errors[0], "warning")

    verdict_label = verdict.lower()
    if wants_json(request):
        return JSONResponse({
            "status": "reviewed",
            "listing_id": listing_id,
            "verdict": verdict,
        }, status_code=201)
    return RedirectResponse(
        f"/missions/{listing_id}?notice=Review+submitted:+{verdict_label}.+Recorded+in+audit+trail.&notice_level=success",
        status_code=303,
    )


@router.get("/{listing_id}/settle")
async def settle_form(request: Request, listing_id: str):
    """Render the settlement / completion view."""
    service = get_service()
    templates = get_templates(request)
    listing_data, _, _ = _resolve_listing_payload(service, listing_id)
    if listing_data is None:
        if wants_json(request):
            return JSONResponse({"error": "Listing not found"}, status_code=404)
        return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)

    # Gather settlement context
    evidence_items = _gather_evidence(service, listing_id, listing_data)
    reward = (
        listing_data.get("preferences", {}).get("reward", 100)
        if isinstance(listing_data.get("preferences"), dict)
        else 100
    )
    commission_breakdown = _build_commission_preview(reward)
    review_verdict, review_notes, reviewer_id = _latest_review(service, listing_id)

    # Determine escrow state from review
    if review_verdict == "APPROVE":
        escrow_state = "locked"  # ready to release on settlement
    elif review_verdict == "REJECT":
        escrow_state = "refunded"
    else:
        escrow_state = "pending"

    can_settle = review_verdict == "APPROVE"

    context = {
        "request": request,
        "active_tab": "missions",
        "listing": listing_data,
        "evidence_items": evidence_items,
        "commission_breakdown": commission_breakdown,
        "breakdown": commission_breakdown,
        "escrow_state": escrow_state,
        "review_verdict": review_verdict,
        "review_notes": review_notes,
        "reviewer_id": reviewer_id,
        "can_settle": can_settle,
        "settlement_notice": None,
        "settlement_notice_level": "info",
        "errors": [],
    }
    return respond(request, templates, "missions/settle.html", context)


@router.post("/{listing_id}/settle")
async def settle_mission(request: Request, listing_id: str):
    """Trigger settlement — release escrow funds on approval."""
    service = get_service()
    templates = get_templates(request)
    listing_data, _, _ = _resolve_listing_payload(service, listing_id)
    if listing_data is None:
        if wants_json(request):
            return JSONResponse({"error": "Listing not found"}, status_code=404)
        return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)

    review_verdict, _, _ = _latest_review(service, listing_id)
    if review_verdict != "APPROVE":
        msg = "Cannot settle: mission has not been approved."
        if wants_json(request):
            return JSONResponse({"errors": [msg]}, status_code=422)
        return RedirectResponse(
            f"/missions/{listing_id}/settle?notice={quote_plus(msg)}&notice_level=warning",
            status_code=303,
        )

    # For live listings with a workflow, trigger the payment path
    if listing_data.get("source") == "live":
        wf = _find_workflow_for_listing(service, listing_id)
        if wf is not None:
            try:
                from genesis.compensation.ledger import Ledger
                from genesis.compensation.reserve import Reserve
                ledger = Ledger()
                reserve = Reserve()
                result = service.complete_and_pay_workflow(wf.workflow_id, ledger, reserve)
                if not result.success:
                    if wants_json(request):
                        return JSONResponse({"errors": result.errors}, status_code=422)
                    return RedirectResponse(
                        f"/missions/{listing_id}/settle?notice={quote_plus(result.errors[0])}&notice_level=warning",
                        status_code=303,
                    )
            except ImportError:
                pass  # Ledger/Reserve not available in PoC; fall through

    if wants_json(request):
        return JSONResponse({
            "status": "settled",
            "listing_id": listing_id,
            "escrow": "released",
        }, status_code=200)
    return RedirectResponse(
        f"/missions/{listing_id}?notice=Mission+settled.+Escrow+released.&notice_level=success",
        status_code=303,
    )


def _latest_review(service, listing_id: str) -> tuple[str | None, str | None, str | None]:
    """Get the latest review verdict, notes, and reviewer for a listing."""
    mission_id = _find_mission_for_listing(service, listing_id)
    if mission_id:
        mission = service.get_mission(mission_id)
        if mission is not None:
            reviews = getattr(mission, "reviews", [])
            if reviews:
                latest = reviews[-1]
                return (
                    getattr(latest, "verdict", None),
                    getattr(latest, "notes", None),
                    getattr(latest, "reviewer_id", None),
                )
    return None, None, None


def _find_workflow_for_listing(service, listing_id: str):
    """Find a workflow associated with a listing, if any."""
    orchestrator = getattr(service, "_workflow_orchestrator", None)
    if orchestrator is None:
        return None
    for wf in getattr(orchestrator, "_workflows", {}).values():
        if getattr(wf, "listing_id", None) == listing_id:
            return wf
    return None


def _find_mission_for_listing(service, listing_id: str) -> str | None:
    """Find a mission ID associated with a listing."""
    for mid, mission in getattr(service, "_missions", {}).items():
        if getattr(mission, "listing_id", None) == listing_id:
            return mid
    return None


def _gather_evidence(service, listing_id: str, listing_data: dict) -> list[dict]:
    """Gather evidence items for review display."""
    items = []
    mission_id = _find_mission_for_listing(service, listing_id)
    if mission_id:
        mission = service.get_mission(mission_id)
        if mission is not None:
            for ev in getattr(mission, "evidence", []):
                items.append({
                    "artifact_hash": getattr(ev, "artifact_hash", "n/a"),
                    "label": "Submitted evidence",
                })
    # For hypothetical missions, show placeholder evidence
    if not items and listing_data.get("source") == "catalog":
        items = [
            {"artifact_hash": "a1b2c3d4e5f6...hypothetical", "label": "Hypothetical evidence record"},
            {"artifact_hash": "f6e5d4c3b2a1...hypothetical", "label": "Hypothetical methods log"},
        ]
    return items


def _build_commission_preview(reward: int) -> dict:
    """Build a commission breakdown dict for template display."""
    rate = 0.10  # 10% commission (PoC default)
    commission_amount = round(reward * rate, 2)
    worker_payout = round(reward - commission_amount, 2)
    gcf = round(reward * 0.01, 2)
    employer_creator = round(reward * 0.05, 2)
    worker_creator = round(worker_payout * 0.05, 2)
    return {
        "reward": f"{reward}",
        "rate": f"{int(rate * 100)}%",
        "commission_amount": f"{commission_amount}",
        "worker_payout": f"{worker_payout}",
        "gcf_contribution": f"{gcf}",
        "employer_creator_fee": f"{employer_creator}",
        "worker_creator_fee": f"{worker_creator}",
    }


def _shape_service_listing(listing) -> dict:
    state_obj = _field(listing, "state", "OPEN")
    state = state_obj.value if hasattr(state_obj, "value") else str(state_obj)
    domain_tags = list(_field(listing, "domain_tags", []) or [])
    primary_tag = (domain_tags[0].replace("-", " ").title() if domain_tags else "General")
    listing_data = {
        "listing_id": _field(listing, "listing_id", "mission"),
        "source": "live",
        "title": _field(listing, "title", "Mission"),
        "summary": _field(listing, "description", "Mission listing from live service data."),
        "creator_id": _field(listing, "creator_id", "unknown-creator"),
        "domain_tags": domain_tags,
        "circle_name": f"{primary_tag} Domain",
        "bridge": f"{primary_tag} x Governance and Justice",
        "risk_tier": "R2",
        "stage_key": "packet_review",
        "state": state,
        "state_label": "Bid Proposal Review",
        "bid_count": _field(listing, "bid_count", 0),
        "due_window": "TBD",
        "stake_band": "mission band M2",
        "next_gate": "Composite scoring + conflict screening",
        "application_capacity": 10,
        "intake_open": state.lower() in {"open", "accepting_bids", "accepting-bids"},
        "requires_human_review": False,
        "why_reason": (
            "Ordered by transparent fit score and independent checks. "
            "No popularity ranking, no paid visibility."
        ),
    }
    listing_data["dossier"] = _build_default_dossier(listing_data)
    return listing_data


def _shape_service_bid(bid) -> dict:
    composite = _field(bid, "composite_score")
    score = round(composite * 100, 1) if composite else 0
    worker_id = _field(bid, "worker_id", "unknown-worker")
    return {
        "actor_name": worker_id,
        "actor_id": worker_id,
        "actor_type": "human",
        "org": "Service listing bidder",
        "trust_points": "n/a",
        "skill_points": "n/a",
        "domain_points": "n/a",
        "composite_score": score,
        "packet_ref": _field(bid, "bid_id", "service-bid"),
        "independence_check": "Independent review pending from service layer.",
        "status": "packet-review",
    }


def _filter_hypothetical_missions(missions: list[dict], q: str, domain: str | None) -> list[dict]:
    lowered = q.strip().lower()
    filtered: list[dict] = []
    for mission in missions:
        if domain and domain not in mission.get("domain_tags", []):
            continue
        if lowered:
            haystack = " ".join([
                mission.get("title", ""),
                mission.get("summary", ""),
                mission.get("circle_name", ""),
                " ".join(mission.get("domain_tags", [])),
                mission.get("bridge", ""),
            ]).lower()
            if lowered not in haystack:
                continue
        filtered.append(mission)
    return filtered


def _sort_hypothetical_missions(missions: list[dict], sort: str) -> list[dict]:
    if sort == "newest":
        return sorted(missions, key=lambda m: m.get("listing_id", ""), reverse=True)
    if sort == "deadline":
        return sorted(missions, key=lambda m: m.get("due_window", ""))
    return sorted(
        missions,
        key=lambda m: (
            m.get("state_label", ""),
            m.get("risk_tier", ""),
            -int(m.get("bid_count", 0)),
        ),
    )


def _resolve_listing_payload(service, listing_id: str) -> tuple[dict | None, list[dict], list[dict]]:
    listing = service.get_listing(listing_id)
    if listing is not None:
        bids = service.get_bids(listing_id)
        listing_data = _shape_service_listing(listing)
        listing_data = _enrich_mission(listing_data)
        listing_data["bid_count"] = len(bids)
        listing_data["skill_requirements"] = len(_field(listing, "skill_requirements", []) or [])
        bids_data = [_shape_service_bid(bid) for bid in bids]
        workflow_source = mission_by_id("demo-maternal-health") or {}
        bid_workflow = workflow_source.get("bid_workflow", [])
        return listing_data, bids_data, bid_workflow

    hypothetical = mission_by_id(listing_id)
    if hypothetical is None:
        return None, [], []
    listing_data = dict(hypothetical)
    listing_data["source"] = "catalog"
    listing_data["skill_requirements"] = max(2, len(hypothetical.get("domain_tags", [])) + 1)
    if "dossier" not in listing_data:
        listing_data["dossier"] = _build_default_dossier(listing_data)
    listing_data = _enrich_mission(listing_data)
    bids_data = hypothetical.get("bid_packets", [])
    bid_workflow = hypothetical.get("bid_workflow", [])
    return listing_data, bids_data, bid_workflow


def _build_default_dossier(listing: dict) -> dict:
    domain_tags = list(listing.get("domain_tags", []) or [])
    if not domain_tags:
        domain_tags = ["general"]
    domain_labels = [_domain_label(_normalize_domain(tag)) for tag in domain_tags]
    focus_label = ", ".join(domain_labels)
    risk_tier = str(listing.get("risk_tier", "R2")).upper()
    capacity = int(listing.get("application_capacity", RISK_CAPACITY.get(risk_tier, 10)))
    title = str(listing.get("title", "this mission"))
    stage_label = str(listing.get("state_label", "Bid Proposal Review"))
    domain_focus = domain_labels[0] if domain_labels else "General"
    primary_domain = _normalize_domain(domain_tags[0]) if domain_tags else "general"
    primary_frame = _fallback_human_domain_frame(primary_domain)
    secondary_domain = _normalize_domain(domain_tags[1]) if len(domain_tags) > 1 else ""
    secondary_label = _domain_label(secondary_domain) if secondary_domain else ""
    risk_quorum = {
        "R1": "1 independent reviewer before settlement",
        "R2": "2 independent reviewers before settlement",
        "R3": "2 human plus 1 machine reviewer, with human sign-off",
    }.get(risk_tier, "2 independent reviewers before settlement")
    due_window = listing.get("due_window", "this review window")

    brief = {
        "problem_signal": (
            f"Evidence around {title.lower()} still points in different directions, so teams cannot sign off yet."
        ),
        "decision_required": (
            f"Before this window closes, decide whether {domain_focus.lower()} controls can move beyond "
            f"{stage_label.lower()} or need revision first."
        ),
        "human_impact": (
            "Service reliability, fairness of outcomes, and public confidence all depend on this decision path."
        ),
        "success_definition": (
            "A fresh reviewer can reproduce the result and defend the final recommendation without unresolved severe conflicts."
        ),
        "constraints": [
            f"Deadline: {listing.get('due_window', 'TBD')}.",
            f"Risk tier: {risk_tier} ({risk_quorum}).",
            f"Intake capacity: {capacity} applicants ({'open' if listing.get('intake_open', True) else 'owner-closed'}).",
        ],
    }
    if listing.get("requires_human_review", risk_tier == "R3"):
        brief["constraints"].append("Human review required before activation.")

    what_happening_now = (
        f"{listing.get('summary', 'Mission briefing unavailable.')} Recent submissions show material disagreements that still block sign-off."
    )
    if secondary_label:
        what_happening_now += f" The most important gap sits between {domain_focus} and {secondary_label} reviewers."

    why_it_matters = (
        f"This mission affects {primary_frame['people']}. "
        f"If we leave this unresolved, {primary_frame['harm']}."
    )

    what_we_will_do = [
        "Consolidate current evidence into one shared baseline across all participating teams.",
        "Test each major claim against independent challenge evidence before recommendation.",
        "Publish a plain-language decision brief so operators can act without ambiguity.",
    ]
    if secondary_label:
        what_we_will_do.append(
            f"Reconcile disagreements so {domain_focus} and {secondary_label} teams can execute from one guidance line."
        )

    success_looks_like = list(primary_frame["success_outcomes"])
    success_looks_like.append(
        "Independent reviewers can reproduce the conclusion and explain it clearly to non-specialist readers."
    )

    who_should_apply = _fallback_who_should_apply(domain_focus, secondary_label, risk_tier)

    plan_paragraph = (
        f"Over the next {due_window}, contributors will consolidate current evidence, test major claims under "
        "independent challenge, and produce one decision brief that local teams can act on immediately."
    )
    if secondary_label:
        plan_paragraph += (
            f" A key target is agreement between {domain_focus} and {secondary_label} reviewers before closeout."
        )

    success_paragraph = (
        "If this mission succeeds, guidance becomes clearer for people affected, frontline teams can act sooner "
        "with fewer avoidable mistakes, and independent reviewers can verify the final recommendation end to end."
    )

    story_paragraphs = [
        f"{what_happening_now} {why_it_matters}",
        plan_paragraph,
        success_paragraph,
        primary_frame["risk_if_miss"],
        who_should_apply,
    ]

    return {
        "context": (
            f"{listing.get('summary', 'Mission briefing unavailable.')} "
            f"This cycle focuses on moving {focus_label} teams from disagreement to one clear, defensible decision."
        ),
        "human_description": {
            "whats_happening_now": what_happening_now,
            "why_it_matters": why_it_matters,
            "what_we_will_do": what_we_will_do,
            "success_looks_like": success_looks_like,
            "if_we_miss": primary_frame["risk_if_miss"],
            "who_should_apply": who_should_apply,
            "story_paragraphs": story_paragraphs,
        },
        "brief": brief,
        "objective": (
            f"Within {due_window}, deliver a mission brief for {title} "
            "that can be reproduced independently and used for a defensible decision."
        ),
        "scope_in": [
            "Validate the brief against current evidence and surface any material gaps.",
            "Run at least one independent replay and document assumptions clearly.",
            "Provide a recommendation that can be acted on immediately.",
        ],
        "scope_out": [
            "No governance ratification decisions in this mission lane.",
            "No hidden criteria outside the published acceptance rules.",
        ],
        "deliverables": [
            "A concise methods log and replay note",
            "A findings summary linked to source evidence",
            "A recommendation with explicit risk notes",
        ],
        "acceptance_criteria": [
            "Every key claim is linked to evidence.",
            "Independent review meets the required quorum.",
            "No unresolved severe conflict remains at closeout.",
        ],
        "evidence_inputs": [
            "Mission brief and reference records",
            "Operational logs relevant to mission scope",
            "Counter-example submissions from reviewers",
        ],
        "risk_watchpoints": [
            "Insufficient domain coverage in submitted proposals",
            "Unchallenged assumptions in edge cases",
            "Overfitting to short-window observations",
        ],
        "safeguards": [
            "Transparent gates before selection",
            "Independent review before settlement",
            "Audit-linked closure records",
        ],
        "dependencies": [
            f"Bridge lane: {listing.get('bridge', 'Cross-domain lane')}.",
            f"Current stage: {listing.get('state_label', 'Bid Proposal Review')}.",
        ],
        "timeline": [
            {"label": "Scoping", "window": "24h"},
            {"label": "Execution", "window": "2-5 days"},
            {"label": "Review and settlement", "window": listing.get("due_window", "TBD")},
        ],
        "intake_policy": {
            "owner_mode": "Open intake" if listing.get("intake_open", True) else "Owner-closed intake",
            "capacity": capacity,
            "human_review_required": bool(listing.get("requires_human_review", risk_tier == "R3")),
            "note": "Mission owner can pause intake when review capacity is saturated.",
        },
    }


def _enrich_mission(listing: dict) -> dict:
    lifecycle_key = listing.get("lifecycle_key")
    if lifecycle_key not in LIFECYCLE_LABELS:
        lifecycle_key = _infer_lifecycle_key(listing)
        listing["lifecycle_key"] = lifecycle_key
    listing.setdefault("lifecycle_label", LIFECYCLE_LABELS[lifecycle_key])
    listing.setdefault("lifecycle_description", LIFECYCLE_DESCRIPTIONS[lifecycle_key])
    listing.setdefault("mandate", _fallback_mandate(listing, lifecycle_key))
    listing.setdefault("story", _fallback_story(listing, lifecycle_key))
    return listing


def _infer_lifecycle_key(listing: dict) -> str:
    stage_key = str(listing.get("stage_key", "packet_review"))
    circle = str(listing.get("circle_name", "")).lower()
    bridge = str(listing.get("bridge", "")).lower()
    governance_lane = "assembly" in circle or "governance" in circle or "assembly" in bridge or "governance" in bridge
    if stage_key == "delivery_active":
        return "ratified_in_force" if governance_lane else "active_operations"
    if governance_lane and stage_key in {"shortlisting", "counter_example_review", "selection_pending_escrow"}:
        return "ratification_queue"
    if stage_key in {"eligibility_gate", "packet_review"}:
        return "org_submitted"
    return "active_operations"


def _fallback_mandate(listing: dict, lifecycle_key: str) -> dict:
    if lifecycle_key == "org_submitted":
        status = "Submitted by domain expert orgs"
        note = "Pending domain checks and evidence quality validation."
    elif lifecycle_key == "ratification_queue":
        status = "In chamber ratification flow"
        note = "Requires chamber confirmation before policy lock."
    elif lifecycle_key == "ratified_in_force":
        status = "Ratified and operational"
        note = "Ratification passed; mission is now active in operational lanes."
    elif lifecycle_key == "validated_archive":
        status = "Validated closure"
        note = "Mission closed with validated outcomes and auditable trace."
    else:
        status = "Community execution in progress"
        note = "Currently being executed under active review."
    return {
        "status": status,
        "stage": listing.get("state_label", "Bid Proposal Review"),
        "bridge_lane": listing.get("bridge", "Cross-domain lane"),
        "requires_chamber": lifecycle_key in {"ratification_queue", "ratified_in_force"},
        "ratification_note": note,
        "org_submission_note": f"Submitted via {listing.get('circle_name', 'domain lane')}.",
    }


def _fallback_story(listing: dict, lifecycle_key: str) -> dict:
    title = listing.get("title", "This mission")
    lede = (
        f"{title} is in {listing.get('state_label', 'review')}, and contributors are now "
        "working to resolve the final evidence disagreements before the next gate."
    )
    if lifecycle_key == "ratification_queue":
        apply_reason = "Clear evidence writing and strong rebuttals can still shape the ratification outcome."
    elif lifecycle_key == "ratified_in_force":
        apply_reason = "Policy is live now, so implementation quality and verification determine real-world impact."
    elif lifecycle_key == "org_submitted":
        apply_reason = "Strong first-pass analysis can improve scope before the mission hardens into mandate."
    else:
        apply_reason = "Disciplined execution and reproducible checks are needed now to protect outcome quality."
    return {
        "lede": lede,
        "human_frame": "This mission affects real service quality, fairness, and public trust outcomes.",
        "governance_frame": (
            f"Mandate status: {listing.get('mandate', {}).get('status', listing.get('state_label', 'Review'))}. "
            f"Bridge lane: {listing.get('bridge', 'Cross-domain lane')}."
        ),
        "apply_reason": apply_reason,
        "domain_focus": ", ".join(_domain_label(_normalize_domain(tag)) for tag in listing.get("domain_tags", [])) or "General",
    }


def _group_missions_by_lifecycle(missions: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {key: [] for key in LIFECYCLE_ORDER}
    for mission in missions:
        key = mission.get("lifecycle_key", "active_operations")
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(mission)

    sections: list[dict] = []
    for key in LIFECYCLE_ORDER:
        items = grouped.get(key, [])
        if not items:
            continue
        sections.append({
            "key": key,
            "label": LIFECYCLE_LABELS.get(key, key.replace("_", " ").title()),
            "description": LIFECYCLE_DESCRIPTIONS.get(key, ""),
            "count": len(items),
            "missions": items,
        })
    return sections


def _current_user_from_request(request: Request) -> dict:
    templates = get_templates(request)
    user = templates.env.globals.get("current_user", {})
    if not isinstance(user, dict):
        user = {}
    shaped = dict(user)
    shaped.setdefault("actor_id", "demo-human-1")
    shaped.setdefault("trust_score", 0)
    shaped.setdefault("skills", [])
    return shaped


def _build_application_gate(listing: dict, viewer: dict) -> dict:
    risk_tier = str(listing.get("risk_tier", "R2")).upper()
    min_trust = int(listing.get("min_trust_score", RISK_MIN_TRUST.get(risk_tier, 790)))
    required_level = str(listing.get("required_skill_level", RISK_REQUIRED_LEVEL.get(risk_tier, "advanced"))).lower()
    if required_level not in LEVEL_RANK:
        required_level = "advanced"

    raw_domains = list(listing.get("domain_tags", []) or [])
    if not raw_domains:
        raw_domains = ["general"]
    required_domains: list[str] = []
    for domain in raw_domains:
        normalized = _normalize_domain(domain)
        if normalized not in required_domains:
            required_domains.append(normalized)

    required_skills = [
        {"domain": _domain_label(domain), "minimum_level": required_level.title()}
        for domain in required_domains
    ]

    viewer_trust = int(viewer.get("trust_score") or 0)
    viewer_skills = _viewer_skill_index(viewer.get("skills", []))

    missing_domains: list[str] = []
    underlevel_domains: list[str] = []
    required_rank = LEVEL_RANK[required_level]
    for domain in required_domains:
        viewer_level = viewer_skills.get(domain)
        if viewer_level is None:
            missing_domains.append(_domain_label(domain))
            continue
        if LEVEL_RANK.get(viewer_level, 0) < required_rank:
            underlevel_domains.append(
                f"{_domain_label(domain)} ({viewer_level.title()}<{required_level.title()})"
            )

    trust_pass = viewer_trust >= min_trust
    skills_pass = not missing_domains and not underlevel_domains

    capacity_total = int(listing.get("application_capacity", RISK_CAPACITY.get(risk_tier, 10)))
    bid_count = int(listing.get("bid_count", 0) or 0)
    capacity_remaining = max(capacity_total - bid_count, 0)
    capacity_pass = capacity_remaining > 0

    if "intake_open" in listing:
        intake_open = bool(listing.get("intake_open"))
    else:
        stage_key = str(listing.get("stage_key", ""))
        state_label = str(listing.get("state_label", ""))
        intake_open = stage_key != "delivery_active" and "Delivery" not in state_label

    if "requires_human_review" in listing:
        requires_human_review = bool(listing.get("requires_human_review"))
    else:
        requires_human_review = risk_tier == "R3" or bool(set(required_domains) & SENSITIVE_DOMAINS)

    if not intake_open:
        outcome = "intake_closed"
        cta_label = "Intake closed"
        outcome_message = "Applications are currently closed by the mission owner."
    elif not capacity_pass:
        outcome = "capacity_full"
        cta_label = "Roster full"
        outcome_message = "This mission has reached applicant capacity."
    elif not trust_pass:
        outcome = "trust_blocked"
        cta_label = "Trust gate locked"
        outcome_message = f"Trust gate not met ({viewer_trust}/{min_trust})."
    elif not skills_pass:
        outcome = "skills_blocked"
        cta_label = "Skill gate locked"
        outcome_message = "Declared skills do not meet this mission's requirements yet."
    elif requires_human_review:
        outcome = "human_review"
        cta_label = "Apply (human review)"
        outcome_message = "Application can proceed, but requires human review before activation."
    else:
        outcome = "eligible"
        cta_label = "Apply to mission"
        outcome_message = "Eligible to apply now."

    return {
        "outcome": outcome,
        "cta_label": cta_label,
        "outcome_message": outcome_message,
        "min_trust": min_trust,
        "viewer_trust": viewer_trust,
        "trust_pass": trust_pass,
        "required_level": required_level.title(),
        "required_skills": required_skills,
        "missing_domains": missing_domains,
        "underlevel_domains": underlevel_domains,
        "skills_pass": skills_pass,
        "capacity_total": capacity_total,
        "capacity_remaining": capacity_remaining,
        "capacity_pass": capacity_pass,
        "intake_open": intake_open,
        "requires_human_review": requires_human_review,
        "intake_label": _intake_label(intake_open, capacity_pass),
        "intake_style": _intake_style(intake_open, capacity_pass),
    }


def _viewer_skill_index(raw_skills) -> dict[str, str]:
    index: dict[str, str] = {}
    if isinstance(raw_skills, dict):
        raw_skills = [
            {"domain": domain, "level": level}
            for domain, level in raw_skills.items()
        ]
    if not isinstance(raw_skills, list):
        return index
    for skill in raw_skills:
        if not isinstance(skill, dict):
            continue
        domain = _normalize_domain(str(skill.get("domain", "")))
        level = str(skill.get("level", "baseline")).lower()
        if not domain:
            continue
        if level not in LEVEL_RANK:
            level = "baseline"
        index[domain] = level
    return index


def _normalize_domain(domain: str) -> str:
    cleaned = "-".join(str(domain).strip().lower().replace("_", " ").replace("/", " ").split())
    if not cleaned:
        return ""
    return DOMAIN_ALIASES.get(cleaned, cleaned)


def _domain_label(domain: str) -> str:
    return domain.replace("-", " ").title()


def _fallback_human_domain_frame(domain: str) -> dict:
    frames = {
        "healthcare": {
            "people": "patients, carers, and frontline clinical teams",
            "harm": "case handling remains uneven and avoidable risk stays with vulnerable groups",
            "success_outcomes": [
                "Care teams can act on one consistent evidence standard.",
                "Patients and families receive clearer, more predictable decisions.",
            ],
            "risk_if_miss": "If this mission stalls, inconsistent care decisions will continue and confidence in escalation pathways will fall.",
        },
        "education": {
            "people": "students, families, and school support teams",
            "harm": "support remains uneven and those with the highest need are more likely to be missed",
            "success_outcomes": [
                "Support decisions are more consistent across similar learner profiles.",
                "Families can see a clear rationale for how support is allocated.",
            ],
            "risk_if_miss": "If unresolved, inequities in support quality will continue to compound across terms.",
        },
        "transport": {
            "people": "passengers, incident responders, and network operators",
            "harm": "response quality varies and preventable disruptions continue to spread",
            "success_outcomes": [
                "Operational teams act on one validated incident picture.",
                "Passenger safety messaging becomes clearer and more consistent.",
            ],
            "risk_if_miss": "If this drifts, incident response inconsistency will continue to raise safety and reliability risks.",
        },
        "environment": {
            "people": "communities, local service operators, and public-health responders",
            "harm": "risk signals stay inconsistent and protective actions are delayed",
            "success_outcomes": [
                "Risk communication improves for both public and operational teams.",
                "Interventions are better timed with fewer false positives.",
            ],
            "risk_if_miss": "If this remains unresolved, communities continue to absorb avoidable exposure from delayed or conflicting guidance.",
        },
        "audit": {
            "people": "community members and teams accountable for public decisions",
            "harm": "decision quality becomes harder to trust because reasoning is not consistently verifiable",
            "success_outcomes": [
                "Decisions can be traced from claim to evidence without hidden steps.",
                "Independent challenge becomes faster and more effective.",
            ],
            "risk_if_miss": "If audit quality remains weak, low-confidence decisions will continue to appear settled.",
        },
    }
    return frames.get(
        domain,
        {
            "people": "community members and frontline service teams",
            "harm": "decisions stay fragmented and confidence drops",
            "success_outcomes": [
                "Teams can work from one clear decision baseline.",
                "People affected by outcomes can understand why decisions were made.",
            ],
            "risk_if_miss": "If delayed, inconsistency will persist and corrective action will become more expensive.",
        },
    )


def _fallback_who_should_apply(primary_label: str, secondary_label: str, risk_tier: str) -> str:
    if secondary_label:
        lanes = f"{primary_label} and {secondary_label}"
    else:
        lanes = primary_label
    risk_note = {
        "R1": "This lane is suitable for contributors building mission experience with close reviewer guidance.",
        "R2": "This lane needs contributors who can handle contested evidence and write clearly for mixed audiences.",
        "R3": "This lane needs highly trusted contributors who can defend recommendations under formal scrutiny.",
    }.get(str(risk_tier).upper(), "This lane needs strong evidence discipline and clear communication.")
    return f"Apply if you can translate complex evidence into practical decisions for {lanes} teams. {risk_note}"


def _apply_redirect(listing_id: str, message: str, level: str) -> RedirectResponse:
    safe_level = level if level in {"info", "success", "warning"} else "info"
    target = (
        f"/missions/{listing_id}"
        f"?notice={quote_plus(message)}"
        f"&notice_level={safe_level}#apply"
    )
    return RedirectResponse(target, status_code=303)


def _intake_label(intake_open: bool, capacity_pass: bool) -> str:
    if not intake_open:
        return "Intake Closed"
    if not capacity_pass:
        return "Roster Full"
    return "Intake Open"


def _intake_style(intake_open: bool, capacity_pass: bool) -> str:
    if not intake_open or not capacity_pass:
        return "closed"
    return "open"


def _field(obj, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
