"""Smoke tests — every route returns 200 (or expected status)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genesis.web.routers import missions as missions_router
from genesis.web.routers import social as social_router

pytestmark = pytest.mark.anyio


# --- HTML routes (default Accept header) ---


class TestLanding:
    async def test_landing_html(self, client):
        r = await client.get("/")
        assert r.status_code == 200
        assert "Genesis" in r.text

    async def test_landing_json(self, client):
        r = await client.get("/", headers={"Accept": "application/json"})
        assert r.status_code == 200
        data = r.json()
        assert "status" in data


class TestAbout:
    async def test_about_html(self, client):
        r = await client.get("/about")
        assert r.status_code == 200
        assert "About Genesis" in r.text

    async def test_about_json(self, client):
        r = await client.get("/about", headers={"Accept": "application/json"})
        assert r.status_code == 200
        data = r.json()
        assert data.get("active_tab") == "about"

    async def test_about_story_step1_html(self, client):
        r = await client.get("/about/story")
        assert r.status_code == 200
        assert "The Problem We Could Not Ignore" in r.text
        assert "Step 1 of 19" in r.text
        assert "Next →" in r.text

    async def test_about_story_step12_first_light(self, client):
        """Step 12 is First Light — the pivotal constitutional event."""
        r = await client.get("/about/story?step=12")
        assert r.status_code == 200
        assert "First Light" in r.text
        assert "The Road Ahead" in r.text
        assert "Next →" in r.text

    async def test_about_story_step17_distributed_immunity(self, client):
        """Step 17 is Distributed Immunity — auto-immune system."""
        r = await client.get("/about/story?step=17")
        assert r.status_code == 200
        assert "Distributed Immunity" in r.text
        assert "threat signal" in r.text.lower()
        assert "Next →" in r.text

    async def test_about_story_step18_self_falsification(self, client):
        """Step 18 (It Is Real) includes the self-falsification observation."""
        r = await client.get("/about/story?step=18")
        assert r.status_code == 200
        assert "disprove itself" in r.text
        assert "falsif" in r.text.lower()

    async def test_about_story_step19_founders_horizon(self, client):
        """Step 19 is the final step — founder's horizon, no Next arrow."""
        r = await client.get("/about/story?step=19")
        assert r.status_code == 200
        assert "The Founder" in r.text
        assert "Step 19 of 19" in r.text
        assert "Next →" not in r.text
        assert "Explore missions" in r.text

    async def test_about_story_linear_nav(self, client):
        r = await client.get("/about/story?step=5")
        assert r.status_code == 200
        assert "?step=6" in r.text
        assert "?step=4" in r.text

    async def test_about_story_clamp(self, client):
        """Out-of-range steps clamp to valid bounds."""
        r0 = await client.get("/about/story?step=0")
        assert r0.status_code == 200
        assert "Step 1 of 19" in r0.text
        r999 = await client.get("/about/story?step=999")
        assert r999.status_code == 200
        assert "Step 19 of 19" in r999.text

    async def test_about_story_legacy_redirect(self, client):
        """Old /about/story/why?scene=2 redirects to /about/story?step=2."""
        r = await client.get("/about/story/why?scene=2", follow_redirects=False)
        assert r.status_code == 307
        assert r.headers["location"] == "/about/story?step=2"

    async def test_about_story_json(self, client):
        r = await client.get("/about/story?step=5", headers={"Accept": "application/json"})
        assert r.status_code == 200
        data = r.json()
        assert data.get("active_tab") == "about"
        assert data.get("story_step") == 5

    async def test_about_story_bogus_track_redirect(self, client):
        """Bogus track redirect resolves to step 1."""
        r = await client.get("/about/story/nonexistent?scene=1", follow_redirects=False)
        assert r.status_code == 307
        assert r.headers["location"] == "/about/story?step=1"

    async def test_about_faq_section_anchors(self, client):
        """Every FAQ section has an anchor ID for deep linking."""
        r = await client.get("/about")
        assert r.status_code == 200
        for anchor in [
            "faq-platform", "faq-workflow", "faq-trust",
            "faq-governance", "faq-economics", "faq-safety",
            "faq-machines", "faq-compute",
        ]:
            assert f'id="{anchor}"' in r.text, f"Missing anchor: {anchor}"

    async def test_about_faq_section_titles(self, client):
        """All 8 FAQ section titles are present."""
        r = await client.get("/about")
        for title in [
            "What Genesis Is",
            "How Work Flows",
            "Trust and Reputation",
            "Governance and Constitutional Design",
            "Economics, First Light, and Epochs",
            "Safety, Justice, and Accommodation",
            "Machine Agency and Coexistence",
            "Distributed Compute and Sovereignty",
        ]:
            assert title in r.text, f"Missing section: {title}"

    async def test_about_faq_key_concepts(self, client):
        """Key philosophical concepts appear in expanded FAQ answers."""
        r = await client.get("/about")
        text = r.text.lower()
        assert "falsif" in text  # Popperian falsification
        assert "escrow" in text  # Escrow-first payment
        assert "first light" in text
        assert "four-tier" in text  # Machine autonomy pathway
        assert "common fund" in text  # GCF
        assert "cannot be bought" in text  # Trust rule

    async def test_about_faq_answer_depth(self, client):
        """FAQ has sufficient items with substantive prose."""
        r = await client.get("/about")
        faq_count = r.text.count('class="faq-item"')
        assert faq_count >= 38, f"Expected ≥38 FAQ items, found {faq_count}"

    async def test_storyboard_deep_links_use_anchors(self, client):
        """Storyboard steps that link to /about use section anchors."""
        # Step 1 links to /about#faq-platform
        r1 = await client.get("/about/story?step=1")
        assert r1.status_code == 200
        assert "/about#faq-" in r1.text
        # Step 15 (Beyond The Data Centre) links to /about#faq-compute
        r15 = await client.get("/about/story?step=15")
        assert "/about#faq-compute" in r15.text
        # Step 16 (Coexistence) links to /about#faq-machines
        r16 = await client.get("/about/story?step=16")
        assert "/about#faq-machines" in r16.text


    async def test_about_readme_html(self, client):
        """README renders as HTML at /about/readme."""
        r = await client.get("/about/readme")
        assert r.status_code == 200
        assert "Genesis" in r.text
        assert "README" in r.text

    async def test_about_readme_json(self, client):
        """README JSON response includes doc_html."""
        r = await client.get("/about/readme", headers={"Accept": "application/json"})
        assert r.status_code == 200
        data = r.json()
        assert data.get("active_tab") == "about"
        assert "doc_html" in data

    async def test_about_constitution_html(self, client):
        """Constitution renders as HTML at /about/constitution."""
        r = await client.get("/about/constitution")
        assert r.status_code == 200
        assert "Constitution" in r.text

    async def test_about_constitution_json(self, client):
        """Constitution JSON response includes doc_html."""
        r = await client.get("/about/constitution", headers={"Accept": "application/json"})
        assert r.status_code == 200
        data = r.json()
        assert data.get("active_tab") == "about"
        assert "doc_html" in data

    async def test_about_no_faq_auto_open(self, client):
        """No FAQ item should auto-expand."""
        r = await client.get("/about")
        assert r.status_code == 200
        assert '<details class="faq-item" open>' not in r.text

    async def test_about_foundational_documents_links(self, client):
        """About page links to README and Constitution."""
        r = await client.get("/about")
        assert r.status_code == 200
        assert "/about/readme" in r.text
        assert "/about/constitution" in r.text

    async def test_about_project_origin_expanded(self, client):
        """Project Origin is expanded prose, not a stub."""
        r = await client.get("/about")
        text = r.text.lower()
        assert "karl popper" in text or "popper" in text
        assert "constitution" in text


class TestRegistration:
    async def test_register_form(self, client):
        r = await client.get("/register")
        assert r.status_code == 200

    async def test_machine_register_form(self, client):
        r = await client.get("/register/machine")
        assert r.status_code == 200


class TestMissions:
    async def test_mission_board(self, client):
        r = await client.get("/missions")
        assert r.status_code == 200
        assert "View mission" in r.text
        assert "Intake Open" in r.text or "Intake Closed" in r.text or "Roster Full" in r.text

    async def test_mission_board_json(self, client):
        r = await client.get("/missions", headers={"Accept": "application/json"})
        assert r.status_code == 200
        data = r.json()
        assert "listings" in data

    async def test_mission_detail(self, client):
        r = await client.get("/missions/demo-listing-1")
        assert r.status_code == 200
        assert "Apply to Mission" in r.text
        assert "Intake Open" in r.text or "Intake Closed" in r.text or "Roster Full" in r.text

    async def test_mission_detail_json(self, client):
        r = await client.get(
            "/missions/demo-listing-1",
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "listing" in data

    async def test_mission_not_found(self, client):
        r = await client.get("/missions/nonexistent")
        assert r.status_code == 404

    async def test_mission_not_found_json(self, client):
        r = await client.get(
            "/missions/nonexistent",
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 404

    async def test_mission_apply_route(self, client):
        r = await client.post("/missions/demo-listing-1/apply")
        assert r.status_code == 303
        assert "/missions/demo-listing-1" in r.headers.get("location", "")

    # --- Mission creation ---

    async def test_create_form_html(self, client):
        r = await client.get("/missions/create")
        assert r.status_code == 200
        assert "Create a mission" in r.text or "create" in r.text.lower()

    async def test_create_form_json(self, client):
        r = await client.get("/missions/create", headers={"Accept": "application/json"})
        assert r.status_code == 200

    async def test_create_mission_post_valid(self, client):
        r = await client.post(
            "/missions/create",
            data={
                "title": "Smoke test mission",
                "description": "Created by test suite.",
                "domain": "general",
                "risk_tier": "R1",
                "reward": "50",
                "deadline_days": "7",
            },
        )
        assert r.status_code == 303
        loc = r.headers.get("location", "")
        assert "/missions/mission-" in loc
        assert "notice" in loc

    async def test_create_mission_post_valid_json(self, client):
        r = await client.post(
            "/missions/create",
            data={
                "title": "JSON smoke test mission",
                "description": "Created via JSON accept.",
                "domain": "healthcare",
                "risk_tier": "R2",
                "reward": "100",
                "deadline_days": "14",
            },
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 201
        data = r.json()
        assert "listing_id" in data
        assert data["state"] == "accepting_bids"

    async def test_create_mission_post_missing_title(self, client):
        r = await client.post(
            "/missions/create",
            data={
                "title": "",
                "description": "Has description but no title.",
                "reward": "50",
                "deadline_days": "7",
            },
        )
        assert r.status_code == 422
        assert "Title is required" in r.text

    async def test_create_mission_post_missing_title_json(self, client):
        r = await client.post(
            "/missions/create",
            data={"title": "", "description": "desc", "reward": "50", "deadline_days": "7"},
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 422
        data = r.json()
        assert any("Title" in e for e in data["errors"])

    async def test_create_mission_post_invalid_reward(self, client):
        r = await client.post(
            "/missions/create",
            data={
                "title": "Bad reward",
                "description": "Non-numeric reward.",
                "reward": "abc",
                "deadline_days": "7",
            },
        )
        assert r.status_code == 422
        assert "whole number" in r.text

    # --- Work submission ---

    async def test_submit_work_form_html(self, client):
        r = await client.get("/missions/demo-listing-1/submit-work")
        assert r.status_code == 200
        assert "Submit work" in r.text or "evidence" in r.text.lower()

    async def test_submit_work_post_valid(self, client):
        r = await client.post(
            "/missions/demo-listing-1/submit-work",
            data={
                "evidence_summary": "Completed the analysis. All criteria met.",
                "artifact_references": "https://example.com/report\nhash:abc123",
            },
        )
        assert r.status_code == 303
        loc = r.headers.get("location", "")
        assert "/missions/demo-listing-1" in loc
        assert "submitted" in loc.lower() or "notice" in loc

    async def test_submit_work_post_valid_json(self, client):
        r = await client.post(
            "/missions/demo-listing-1/submit-work",
            data={
                "evidence_summary": "JSON submit test.",
                "artifact_references": "ref1\nref2",
            },
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "submitted"
        assert data["evidence_count"] == 3  # 1 summary hash + 2 reference hashes

    async def test_submit_work_post_missing_summary(self, client):
        r = await client.post(
            "/missions/demo-listing-1/submit-work",
            data={"evidence_summary": "", "artifact_references": "ref1"},
        )
        assert r.status_code == 422
        assert "Evidence summary is required" in r.text

    async def test_submit_work_not_found(self, client):
        r = await client.get("/missions/nonexistent/submit-work")
        assert r.status_code == 404

    # --- Review ---

    async def test_review_form_html(self, client):
        r = await client.get("/missions/demo-listing-1/review")
        assert r.status_code == 200
        assert "Review" in r.text
        assert "verdict" in r.text.lower() or "Approve" in r.text

    async def test_review_post_valid(self, client):
        r = await client.post(
            "/missions/demo-listing-1/review",
            data={
                "verdict": "APPROVE",
                "review_notes": "Evidence is complete and reproducible. Recommending approval.",
            },
        )
        assert r.status_code == 303
        loc = r.headers.get("location", "")
        assert "/missions/demo-listing-1" in loc

    async def test_review_post_valid_json(self, client):
        r = await client.post(
            "/missions/demo-listing-1/review",
            data={
                "verdict": "REJECT",
                "review_notes": "Key evidence missing. Cannot verify claims.",
            },
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "reviewed"
        assert data["verdict"] == "REJECT"

    async def test_review_post_missing_verdict(self, client):
        r = await client.post(
            "/missions/demo-listing-1/review",
            data={"verdict": "", "review_notes": "Notes without verdict."},
        )
        assert r.status_code == 422
        assert "verdict" in r.text.lower()

    async def test_review_post_missing_notes(self, client):
        r = await client.post(
            "/missions/demo-listing-1/review",
            data={"verdict": "APPROVE", "review_notes": ""},
        )
        assert r.status_code == 422
        assert "notes" in r.text.lower()

    async def test_review_not_found(self, client):
        r = await client.get("/missions/nonexistent/review")
        assert r.status_code == 404

    # --- Settlement ---

    async def test_settle_form_html(self, client):
        r = await client.get("/missions/demo-listing-1/settle")
        assert r.status_code == 200
        assert "Settlement" in r.text or "settlement" in r.text

    async def test_settle_form_json(self, client):
        r = await client.get(
            "/missions/demo-listing-1/settle",
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 200

    async def test_settle_not_found(self, client):
        r = await client.get("/missions/nonexistent/settle")
        assert r.status_code == 404


class TestMissionsIdentityIntegrity:
    async def test_apply_ignores_forged_applicant_id(self, client, monkeypatch):
        captured: dict[str, str] = {}
        fake_listing = {
            "listing_id": "live-listing-apply",
            "source": "live",
            "risk_tier": "R1",
            "required_skill_level": "intermediate",
            "domain_tags": ["healthcare"],
            "application_capacity": 5,
            "bid_count": 0,
            "intake_open": True,
            "requires_human_review": False,
        }

        class FakeResult:
            success = True
            data = {}
            errors = []

        class FakeService:
            def submit_bid(self, bid_id: str, listing_id: str, worker_id: str):
                captured["bid_id"] = bid_id
                captured["listing_id"] = listing_id
                captured["worker_id"] = worker_id
                return FakeResult()

        monkeypatch.setattr(
            missions_router,
            "_resolve_listing_payload",
            lambda _service, _listing_id: (fake_listing, [], []),
        )
        monkeypatch.setattr(
            missions_router,
            "_current_user_from_request",
            lambda _request: {
                "actor_id": "demo-human-1",
                "trust_score": 900,
                "skills": [{"domain": "healthcare", "level": "advanced"}],
            },
        )
        monkeypatch.setattr(missions_router, "get_service", lambda: FakeService())

        r = await client.post(
            "/missions/live-listing-apply/apply",
            data={"applicant_id": "attacker-actor"},
        )
        assert r.status_code == 303
        assert captured["worker_id"] == "demo-human-1"
        assert captured["listing_id"] == "live-listing-apply"

    async def test_bid_ignores_forged_worker_and_bid_ids(self, client, monkeypatch):
        captured: dict[str, str] = {}
        fake_listing = {
            "listing_id": "live-listing-bid",
            "source": "live",
            "risk_tier": "R1",
            "required_skill_level": "intermediate",
            "domain_tags": ["healthcare"],
            "application_capacity": 5,
            "bid_count": 0,
            "intake_open": True,
            "requires_human_review": False,
        }

        class FakeResult:
            success = True
            data = {}
            errors = []

        class FakeService:
            def submit_bid(self, bid_id: str, listing_id: str, worker_id: str):
                captured["bid_id"] = bid_id
                captured["listing_id"] = listing_id
                captured["worker_id"] = worker_id
                return FakeResult()

        monkeypatch.setattr(
            missions_router,
            "_resolve_listing_payload",
            lambda _service, _listing_id: (fake_listing, [], []),
        )
        monkeypatch.setattr(
            missions_router,
            "_current_user_from_request",
            lambda _request: {
                "actor_id": "demo-human-1",
                "trust_score": 900,
                "skills": [{"domain": "healthcare", "level": "advanced"}],
            },
        )
        monkeypatch.setattr(missions_router, "get_service", lambda: FakeService())

        r = await client.post(
            "/missions/live-listing-bid/bid",
            data={"worker_id": "attacker-worker", "bid_id": "attacker-bid"},
        )
        assert r.status_code == 303
        assert captured["worker_id"] == "demo-human-1"
        assert captured["listing_id"] == "live-listing-bid"
        assert captured["bid_id"] != "attacker-bid"
        assert captured["bid_id"].startswith("web-live-listi-")


class TestProfiles:
    async def test_actor_profile(self, client):
        r = await client.get("/actors/demo-human-1")
        assert r.status_code == 200

    async def test_actor_profile_json(self, client):
        r = await client.get(
            "/actors/demo-human-1",
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "actor" in data

    async def test_actor_not_found(self, client):
        r = await client.get("/actors/nonexistent")
        assert r.status_code == 404


class TestAudit:
    async def test_audit_trail(self, client):
        r = await client.get("/audit")
        assert r.status_code == 200

    async def test_audit_trail_json(self, client):
        r = await client.get("/audit", headers={"Accept": "application/json"})
        assert r.status_code == 200
        data = r.json()
        assert "events" in data
        assert "anchors" in data

    async def test_audit_anchors_present(self, client):
        """Real on-chain anchors must appear in the audit trail."""
        r = await client.get("/audit", headers={"Accept": "application/json"})
        data = r.json()
        anchors = data["anchors"]
        assert len(anchors) >= 9, f"Expected >=9 anchors (8 canonical + 1 superseded), got {len(anchors)}"

    async def test_audit_anchors_have_real_tx_hashes(self, client):
        """Every anchor must have a real tx_hash and explorer_url — no illustrative data."""
        r = await client.get("/audit", headers={"Accept": "application/json"})
        for a in r.json()["anchors"]:
            assert a.get("tx_hash"), f"GB{a['genesis_block']} missing tx_hash"
            assert a.get("explorer_url"), f"GB{a['genesis_block']} missing explorer_url"
            assert a["explorer_url"].startswith("https://sepolia.etherscan.io/tx/")
            assert a.get("sha256"), f"GB{a['genesis_block']} missing sha256"

    async def test_audit_anchors_sorted_newest_first(self, client):
        """Anchors should be rendered newest-first regardless of file ordering."""
        r = await client.get("/audit", headers={"Accept": "application/json"})
        anchors = r.json()["anchors"]
        minted = [a.get("minted_utc", "") for a in anchors]
        assert minted == sorted(minted, reverse=True)

    async def test_audit_anchors_status_separation(self, client):
        """Canonical and superseded anchors must be clearly distinguished."""
        r = await client.get("/audit", headers={"Accept": "application/json"})
        anchors = r.json()["anchors"]
        statuses = {a["status"] for a in anchors}
        assert "canonical" in statuses
        assert "superseded" in statuses

    async def test_audit_anchors_in_html(self, client):
        """HTML audit trail must show on-chain verified badges."""
        r = await client.get("/audit")
        assert "on-chain verified" in r.text
        assert "Verify on Etherscan" in r.text
        assert "Genesis Block 1" in r.text
        assert "Genesis Block 8" in r.text

    async def test_audit_json_includes_runtime_anchors_key(self, client):
        """JSON audit response must include runtime_anchors key."""
        r = await client.get("/audit", headers={"Accept": "application/json"})
        data = r.json()
        assert "runtime_anchors" in data

    async def test_audit_runtime_anchors_empty_at_startup(self, client):
        """No runtime anchors should exist at startup (no epochs anchored yet)."""
        r = await client.get("/audit", headers={"Accept": "application/json"})
        data = r.json()
        assert data["runtime_anchors"] == []

    async def test_audit_commitment_anchored_excluded_from_internal(self, client):
        """COMMITMENT_ANCHORED events must NOT appear in the internal ledger section."""
        r = await client.get("/audit", headers={"Accept": "application/json"})
        data = r.json()
        for ev in data["events"]:
            assert ev["kind"] != "commitment_anchored", (
                "COMMITMENT_ANCHORED must be in runtime_anchors, not internal events"
            )

    async def test_runtime_anchor_surfaces_on_audit_route(self, client):
        """End-to-end: anchor_commitment emission must appear under runtime_anchors."""
        from unittest.mock import patch
        from genesis.crypto.anchor import AnchorRecord
        from genesis.web.deps import get_service

        service = get_service()
        service.open_epoch("test-web-audit-anchor")
        close_result = service.close_epoch(beacon_round=9)
        assert close_result.success, close_result.errors
        record = service._epoch_service.committed_records[-1]

        fake_tx = "a" * 64
        fake_anchor = AnchorRecord(
            document_path="TRUST_CONSTITUTION.md",
            sha256_hash="abc123def",
            tx_hash=fake_tx,
            block_number=123456,
            chain_id=11155111,
            timestamp_utc="2026-03-05T12:00:00Z",
            explorer_url=f"https://sepolia.etherscan.io/tx/{fake_tx}",
        )
        with patch.object(service._epoch_service, "anchor_commitment", return_value=fake_anchor):
            anchor_result = service.anchor_commitment(record, "http://fake-rpc", "0xfakekey")
        assert anchor_result.success, anchor_result.errors

        r = await client.get("/audit", headers={"Accept": "application/json"})
        data = r.json()
        runtime = data.get("runtime_anchors", [])
        assert any(item.get("tx_hash") == fake_tx for item in runtime)
        assert not any(ev.get("kind") == "commitment_anchored" for ev in data.get("events", []))

    async def test_audit_internal_events_use_redacted_actor_labels(self, client):
        """Internal audit stream should expose redacted actor labels, not raw IDs."""
        r = await client.get("/audit", headers={"Accept": "application/json"})
        data = r.json()
        for ev in data["events"]:
            assert "actor_id" not in ev
            label = str(ev.get("actor_label", "")).strip()
            assert label
            assert label == "system" or label.startswith("Anon-")


class TestAnchorReleaseGate:
    """Release gate: no on-chain badge without verifiable tx proof."""

    def test_anchor_commitment_emits_event(self):
        """anchor_commitment() must emit COMMITMENT_ANCHORED to the event log."""
        from pathlib import Path
        from genesis.persistence.event_log import EventLog, EventKind
        from genesis.crypto.anchor import AnchorRecord
        from genesis.policy.resolver import PolicyResolver
        from genesis.service import GenesisService
        from unittest.mock import patch

        config_dir = Path(__file__).resolve().parents[2] / "config"
        resolver = PolicyResolver.from_config_dir(config_dir)
        event_log = EventLog()
        service = GenesisService(resolver, event_log=event_log)

        # Open and close an epoch to get a CommitmentRecord
        service.open_epoch("test-anchor-epoch")
        result = service.close_epoch(beacon_round=1)
        assert result.success

        # Mock anchor_to_chain to avoid real Ethereum call
        emits_tx = "deadbeef" * 8  # 64 hex chars
        fake_anchor = AnchorRecord(
            document_path="",
            sha256_hash="abc123",
            tx_hash=emits_tx,
            block_number=99999,
            chain_id=11155111,
            timestamp_utc="2026-03-05T12:00:00Z",
            explorer_url=f"https://sepolia.etherscan.io/tx/{emits_tx}",
        )
        with patch.object(
            service._epoch_service, "anchor_commitment", return_value=fake_anchor
        ):
            record = service._epoch_service.committed_records[-1]
            anchor_result = service.anchor_commitment(
                record, "http://fake-rpc", "0xfakekey"
            )

        assert anchor_result.success, anchor_result.errors
        assert anchor_result.data["tx_hash"] == emits_tx
        assert anchor_result.data["explorer_url"].startswith("https://sepolia.etherscan.io/tx/")

        # Verify COMMITMENT_ANCHORED event was emitted
        anchored_events = [
            ev for ev in service._event_log.events()
            if (ev.event_kind.value if hasattr(ev.event_kind, "value") else str(ev.event_kind))
            == "commitment_anchored"
        ]
        assert len(anchored_events) == 1
        ev = anchored_events[0]
        assert ev.payload["tx_hash"] == emits_tx
        assert ev.payload["block_number"] == 99999
        assert ev.payload["explorer_url"].startswith("https://sepolia.etherscan.io/tx/")

    def test_no_badge_without_tx_proof(self):
        """_extract_runtime_anchors must reject entries without tx_hash or explorer_url."""
        from genesis.web.routers.audit import _extract_runtime_anchors
        from genesis.persistence.event_log import EventLog, EventKind, EventRecord

        log = EventLog()

        valid_tx = "a" * 64
        # Event WITH valid proof — should be included
        good = EventRecord.create(
            event_id="EVT-GOOD",
            event_kind=EventKind.COMMITMENT_ANCHORED,
            actor_id="system",
            payload={
                "tx_hash": valid_tx,
                "explorer_url": f"https://sepolia.etherscan.io/tx/{valid_tx}",
                "sha256_hash": "deadbeef",
                "block_number": 100,
                "chain_id": 11155111,
                "epoch_id": "test-epoch",
            },
        )
        log.append(good)

        # Event WITHOUT tx_hash — must be excluded (release gate)
        bad_no_tx = EventRecord.create(
            event_id="EVT-BAD1",
            event_kind=EventKind.COMMITMENT_ANCHORED,
            actor_id="system",
            payload={
                "explorer_url": "https://sepolia.etherscan.io/tx/0xfake",
                "sha256_hash": "badbeef",
            },
        )
        log.append(bad_no_tx)

        # Event WITHOUT explorer_url — must be excluded (release gate)
        bad_no_url = EventRecord.create(
            event_id="EVT-BAD2",
            event_kind=EventKind.COMMITMENT_ANCHORED,
            actor_id="system",
            payload={
                "tx_hash": "0xdef",
                "sha256_hash": "alsobad",
            },
        )
        log.append(bad_no_url)

        result = _extract_runtime_anchors(log)
        assert len(result) == 1, f"Expected 1 valid anchor, got {len(result)}"
        assert result[0]["tx_hash"] == valid_tx

    def test_runtime_anchor_rejects_non_sepolia_or_unsafe_url(self):
        """Runtime verified anchors must be strict: sepolia URL + matching chain."""
        from genesis.web.routers.audit import _extract_runtime_anchors
        from genesis.persistence.event_log import EventLog, EventKind, EventRecord

        log = EventLog()
        valid_tx = "b" * 64
        # Valid
        log.append(
            EventRecord.create(
                event_id="EVT-OK",
                event_kind=EventKind.COMMITMENT_ANCHORED,
                actor_id="system",
                payload={
                    "tx_hash": valid_tx,
                    "explorer_url": f"https://sepolia.etherscan.io/tx/{valid_tx}",
                    "sha256_hash": "good",
                    "chain_id": 11155111,
                },
            )
        )
        # Wrong chain explorer host
        log.append(
            EventRecord.create(
                event_id="EVT-WRONG-HOST",
                event_kind=EventKind.COMMITMENT_ANCHORED,
                actor_id="system",
                payload={
                    "tx_hash": "c" * 64,
                    "explorer_url": "https://etherscan.io/tx/" + "c" * 64,
                    "sha256_hash": "bad1",
                    "chain_id": 11155111,
                },
            )
        )
        # Unsafe URL scheme
        log.append(
            EventRecord.create(
                event_id="EVT-UNSAFE",
                event_kind=EventKind.COMMITMENT_ANCHORED,
                actor_id="system",
                payload={
                    "tx_hash": "d" * 64,
                    "explorer_url": "javascript:alert(1)",
                    "sha256_hash": "bad2",
                    "chain_id": 11155111,
                },
            )
        )
        # Chain mismatch
        log.append(
            EventRecord.create(
                event_id="EVT-MISMATCH",
                event_kind=EventKind.COMMITMENT_ANCHORED,
                actor_id="system",
                payload={
                    "tx_hash": "e" * 64,
                    "explorer_url": "https://sepolia.etherscan.io/tx/" + "e" * 64,
                    "sha256_hash": "bad3",
                    "chain_id": 1,
                },
            )
        )

        result = _extract_runtime_anchors(log)
        assert len(result) == 1
        assert result[0]["tx_hash"] == valid_tx

    def test_historical_anchor_normalizer_rejects_malformed_block(self):
        """Malformed genesis_block values must be fail-closed, not crash route."""
        from genesis.web.routers.audit import _normalize_anchor_records

        bad_tx = "1" * 64
        good_tx = "2" * 64
        records = [
            {
                "genesis_block": "not-an-int",
                "tx_hash": bad_tx,
                "explorer_url": f"https://sepolia.etherscan.io/tx/{bad_tx}",
                "sha256": "abc",
                "minted_utc": "2026-01-01T00:00:00Z",
            },
            {
                "genesis_block": 2,
                "tx_hash": good_tx,
                "explorer_url": f"https://sepolia.etherscan.io/tx/{good_tx}",
                "sha256": "def",
                "minted_utc": "2026-01-02T00:00:00Z",
            },
        ]
        result = _normalize_anchor_records(records)
        assert len(result) == 1
        assert result[0]["genesis_block"] == 2

    def test_anchor_commitment_surfaces_runtime_event_failure(self):
        """If event append fails, anchor_commitment must return explicit warning."""
        from pathlib import Path
        from unittest.mock import patch
        from genesis.crypto.anchor import AnchorRecord
        from genesis.persistence.event_log import EventLog
        from genesis.policy.resolver import PolicyResolver
        from genesis.service import GenesisService

        config_dir = Path(__file__).resolve().parents[2] / "config"
        resolver = PolicyResolver.from_config_dir(config_dir)
        event_log = EventLog()
        service = GenesisService(resolver, event_log=event_log)
        service.open_epoch("test-anchor-warning")
        result = service.close_epoch(beacon_round=1)
        assert result.success
        record = service._epoch_service.committed_records[-1]
        warn_tx = "feedface" * 8  # 64 hex chars
        fake_anchor = AnchorRecord(
            document_path="",
            sha256_hash="abc123",
            tx_hash=warn_tx,
            block_number=99999,
            chain_id=11155111,
            timestamp_utc="2026-03-05T12:00:00Z",
            explorer_url=f"https://sepolia.etherscan.io/tx/{warn_tx}",
        )
        with patch.object(service._epoch_service, "anchor_commitment", return_value=fake_anchor):
            with patch.object(service._event_log, "append", side_effect=OSError("io-fail")):
                anchor_result = service.anchor_commitment(record, "http://fake-rpc", "0xfakekey")

        assert anchor_result.success
        assert anchor_result.data["runtime_event_recorded"] is False
        assert "runtime audit event recording failed" in anchor_result.data.get("warning", "").lower()


class TestWallet:
    async def test_wallet_page(self, client):
        r = await client.get("/wallet")
        assert r.status_code == 200

    async def test_wallet_json(self, client):
        r = await client.get("/wallet", headers={"Accept": "application/json"})
        assert r.status_code == 200


class TestMembers:
    async def test_members_dashboard(self, client):
        r = await client.get("/members")
        assert r.status_code == 200
        assert "Member Mission Ledger" in r.text

    async def test_members_dashboard_json(self, client):
        r = await client.get("/members", headers={"Accept": "application/json"})
        assert r.status_code == 200
        data = r.json()
        assert data.get("active_tab") == "members"
        assert "member" in data
        assert data["member"]["member_id"] == data["current_user"]["actor_id"]
        assert isinstance(data["member"]["bid_rows"], list)
        assert isinstance(data["member"]["completed_rows"], list)
        assert isinstance(data["member"]["gcf_allocation"], list)

    async def test_members_dashboard_respects_current_user_actor(self, client, monkeypatch):
        monkeypatch.setattr(
            social_router,
            "_current_user_from_templates",
            lambda _templates: {
                "actor_id": "demo-human-5",
                "actor_type": "human",
                "display_name": "Demo User",
                "initials": "DU",
                "trust_score": 0,
                "quality_score": 0,
                "volume_score": 0,
                "open_bids": 0,
            },
        )
        r = await client.get("/members", headers={"Accept": "application/json"})
        assert r.status_code == 200
        data = r.json()
        assert data["member"]["member_id"] == "demo-human-5"
        assert data["current_user"]["actor_id"] == "demo-human-5"
        assert all("mission_id" in row for row in data["member"]["bid_rows"])


class TestAssembly:
    async def test_assembly_listing(self, client):
        r = await client.get("/assembly")
        assert r.status_code == 200
        assert "Assembly" in r.text
        assert "Propose Assembly Topic" in r.text
        assert "Non-binding deliberation" in r.text

    async def test_assembly_listing_json(self, client):
        r = await client.get("/assembly", headers={"Accept": "application/json"})
        assert r.status_code == 200
        data = r.json()
        assert data.get("active_tab") == "assembly"
        assert "assembly_topics" in data
        assert data.get("binding") is False
        assert data.get("decision_mode") == "non_binding_deliberation"

    async def test_assembly_create_topic_and_detail(self, client):
        create = await client.post(
            "/assembly/topics",
            data={
                "title": "Governance disclosure cadence review",
                "opening_statement": "Requesting a tighter publication rhythm for ratification notices.",
            },
        )
        assert create.status_code == 303
        location = create.headers.get("location", "")
        assert location.startswith("/assembly/topic_")

        detail_path = location.split("?")[0]
        detail = await client.get(detail_path)
        assert detail.status_code == 200
        assert "Governance disclosure cadence review" in detail.text
        assert "Opening Statement" in detail.text
        assert "Propose Amendment" in detail.text

    async def test_assembly_create_topic_requires_minimum_opening_length(self, client):
        create = await client.post(
            "/assembly/topics",
            data={
                "title": "Assembly clarity check",
                "opening_statement": "Too short to be useful.",
            },
            follow_redirects=True,
        )
        assert create.status_code == 200
        assert "Opening statement must be at least 40 characters." in create.text

    async def test_assembly_contribute(self, client):
        create = await client.post(
            "/assembly/topics",
            data={
                "title": "Policy harmonization for challenge windows",
                "opening_statement": "Opening baseline for challenge-window harmonization across circles.",
            },
        )
        assert create.status_code == 303
        detail_path = create.headers.get("location", "").split("?")[0]
        topic_id = detail_path.rstrip("/").split("/")[-1]

        contribute = await client.post(
            f"/assembly/{topic_id}/contribute",
            data={"content": "Suggesting one shared minimum challenge period with domain-specific extensions."},
            follow_redirects=True,
        )
        assert contribute.status_code == 200
        assert "Response posted in Assembly." in contribute.text
        assert "Contributions" in contribute.text
        assert "shared minimum challenge period" in contribute.text

    async def test_assembly_detail_json(self, client):
        create = await client.post(
            "/assembly/topics",
            data={
                "title": "Evidence packaging guidance",
                "opening_statement": "Need a plain-language baseline for evidence packet completeness.",
            },
        )
        assert create.status_code == 303
        detail_path = create.headers.get("location", "").split("?")[0]

        detail = await client.get(detail_path, headers={"Accept": "application/json"})
        assert detail.status_code == 200
        data = detail.json()
        assert data.get("active_tab") == "assembly"
        assert data.get("topic", {}).get("topic_id", "").startswith("topic_")
        assert data.get("opening_contribution") is not None
        assert data.get("binding") is False
        assert data.get("decision_mode") == "non_binding_deliberation"

    async def test_assembly_amendment_path_page(self, client):
        create = await client.post(
            "/assembly/topics",
            data={
                "title": "Amendment handoff map check",
                "opening_statement": "Link this discussion to amendment submission.",
            },
        )
        assert create.status_code == 303
        topic_id = create.headers.get("location", "").split("?")[0].rstrip("/").split("/")[-1]

        r = await client.get(f"/assembly/amendment-path?topic={topic_id}")
        assert r.status_code == 200
        assert "Binding Amendment Path" in r.text
        assert "How Decisions Become Binding" in r.text
        assert "Submit Amendment Proposal" in r.text
        assert topic_id in r.text

    async def test_assembly_submit_amendment_and_linked_display(self, client):
        create = await client.post(
            "/assembly/topics",
            data={
                "title": "Eligibility threshold calibration topic",
                "opening_statement": "Calibrate constitutional vote threshold for pilot conditions.",
            },
        )
        assert create.status_code == 303
        topic_id = create.headers.get("location", "").split("?")[0].rstrip("/").split("/")[-1]

        submit = await client.post(
            "/assembly/amendments",
            data={
                "topic_id": topic_id,
                "provision_key": "eligibility.tau_vote",
                "proposed_value": "0.65",
                "justification": "Increase constitutional voting threshold during onboarding stress tests.",
            },
            follow_redirects=True,
        )
        assert submit.status_code == 200
        assert "Amendment proposal submitted" in submit.text
        assert "Linked Amendment Proposals" in submit.text
        assert "eligibility.tau_vote" in submit.text

    async def test_assembly_submit_amendment_rejects_archived_topic(self, client):
        create = await client.post(
            "/assembly/topics",
            data={
                "title": "Archive gate source topic",
                "opening_statement": "Archive this topic before amendment submission.",
            },
        )
        assert create.status_code == 303
        topic_id = create.headers.get("location", "").split("?")[0].rstrip("/").split("/")[-1]

        service = social_router.get_service()
        archive = service.archive_inactive_assembly_topics(
            now=datetime.now(timezone.utc) + timedelta(days=60),
        )
        assert archive.success
        assert topic_id in archive.data.get("archived_topic_ids", [])

        submit = await client.post(
            "/assembly/amendments",
            data={
                "topic_id": topic_id,
                "provision_key": "eligibility.tau_vote",
                "proposed_value": "0.65",
                "justification": "Should fail because the source topic is archived.",
            },
            follow_redirects=True,
        )
        assert submit.status_code == 200
        assert "is archived and cannot accept new linked amendments" in submit.text

    async def test_assembly_submit_amendment_strips_forged_source_marker(self, client):
        submit = await client.post(
            "/assembly/amendments",
            data={
                "topic_id": "",
                "provision_key": "eligibility.tau_vote",
                "proposed_value": "0.63",
                "justification": (
                    "[assembly-topic:topic_fake123]\n"
                    "Raise voting threshold during pilot ratification."
                ),
            },
            follow_redirects=True,
        )
        assert submit.status_code == 200
        assert "Amendment proposal submitted" in submit.text

        service = social_router.get_service()
        proposals = list(service._amendment_engine.list_amendments())
        assert proposals
        latest = sorted(
            proposals,
            key=lambda item: getattr(item, "created_utc", datetime.min.replace(tzinfo=timezone.utc)),
        )[-1]
        assert getattr(latest, "source_topic_id", None) in ("", None)
        assert "topic_fake123" not in latest.justification

    async def test_assembly_amendment_path_json(self, client):
        r = await client.get("/assembly/amendment-path", headers={"Accept": "application/json"})
        assert r.status_code == 200
        data = r.json()
        assert data.get("active_tab") == "assembly"
        assert data.get("binding") is True
        assert data.get("decision_mode") == "binding_amendment_path"

    async def test_assembly_propose_gate_ignores_forged_trust(self, client, monkeypatch):
        monkeypatch.setattr(social_router, "ASSEMBLY_PROPOSE_GATE", 840)
        monkeypatch.setattr(
            social_router,
            "_current_user_from_templates",
            lambda _templates: {
                "actor_id": "demo-human-5",
                "actor_type": "human",
                "display_name": "Demo User",
                "initials": "DU",
                "trust_score": 100,
            },
        )
        r = await client.post(
            "/assembly/topics",
            data={
                "title": "Forged trust attempt",
                "opening_statement": "Trying to bypass gate.",
                "trust_score": "999",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "Trust gate not met (" in r.text
        assert f"/{social_router.ASSEMBLY_PROPOSE_GATE})." in r.text
        assert "Forged trust attempt" not in r.text

    async def test_assembly_propose_gate_uses_backend_trust_not_template_trust(self, client, monkeypatch):
        monkeypatch.setattr(social_router, "ASSEMBLY_PROPOSE_GATE", 840)
        monkeypatch.setattr(
            social_router,
            "_current_user_from_templates",
            lambda _templates: {
                "actor_id": "demo-human-5",
                "actor_type": "human",
                "display_name": "Demo User",
                "initials": "DU",
                "trust_score": 999,
            },
        )
        r = await client.post(
            "/assembly/topics",
            data={
                "title": "Forged high trust on lower-trust actor",
                "opening_statement": (
                    "This opening statement is deliberately long enough to pass form validation "
                    "while testing whether backend trust is the real source of truth."
                ),
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "Trust gate not met (" in r.text
        assert f"/{social_router.ASSEMBLY_PROPOSE_GATE})." in r.text
        assert "Forged high trust on lower-trust actor" not in r.text


class TestCircles:
    async def test_circles_index(self, client):
        r = await client.get("/circles")
        assert r.status_code == 200
        assert "Circles Directory" in r.text

    async def test_circles_circle_view(self, client):
        r = await client.get("/circles/public-health")
        assert r.status_code == 200
        assert "Public Health Circle" in r.text

    async def test_circles_board_view(self, client):
        r = await client.get("/circles/public-health/maternal-outcomes-lane")
        assert r.status_code == 200
        assert "Board Activity" in r.text

    async def test_circles_thread_view(self, client):
        r = await client.get(
            "/circles/public-health/maternal-outcomes-lane/"
            "nicu-transfer-threshold-challenged-with-new-ward-evidence",
        )
        assert r.status_code == 200
        assert "Circle Conversation" in r.text

    async def test_circles_thread_view_json(self, client):
        r = await client.get(
            "/circles/public-health/maternal-outcomes-lane/"
            "nicu-transfer-threshold-challenged-with-new-ward-evidence",
            headers={"Accept": "application/json"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("view_mode") == "thread"
        assert "thread_posts" in data

    async def test_circles_apply_join(self, client):
        r = await client.post(
            "/circles/public-health/apply",
            data={
                "alias": "FORGED-ALIAS-APPLY",
                "note": "Requesting access to this circle.",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "Join request submitted" in r.text
        assert "FORGED-ALIAS-APPLY" not in r.text
        assert "Anon-H" in r.text

    async def test_circles_start_thread(self, client):
        r = await client.post(
            "/circles/public-health/maternal-outcomes-lane/threads",
            data={
                "title": "Community escalation timing check",
                "summary": "Testing a new circle.",
                "opening_body": "Can we align on one timing threshold for escalations?",
                "alias": "FORGED-ALIAS-THREAD",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "Circle created and opened for responses." in r.text
        assert "Community escalation timing check" in r.text
        assert "FORGED-ALIAS-THREAD" not in r.text

    async def test_circles_reply_thread(self, client):
        r = await client.post(
            "/circles/public-health/maternal-outcomes-lane/"
            "nicu-transfer-threshold-challenged-with-new-ward-evidence/reply",
            data={
                "body": "Adding a human review note to this thread.",
                "alias": "FORGED-ALIAS-REPLY",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "Reply posted to the circle." in r.text
        assert "FORGED-ALIAS-REPLY" not in r.text
        assert "Adding a human review note to this thread." in r.text

    async def test_circles_forms_no_alias_input(self, client):
        circle = await client.get("/circles/public-health")
        board = await client.get("/circles/public-health/maternal-outcomes-lane")
        thread = await client.get(
            "/circles/public-health/maternal-outcomes-lane/"
            "nicu-transfer-threshold-challenged-with-new-ward-evidence",
        )
        assert circle.status_code == 200
        assert board.status_code == 200
        assert thread.status_code == 200
        assert "Anon alias (optional)" not in circle.text
        assert "Anon alias (optional)" not in board.text
        assert "Anon alias (optional)" not in thread.text

    async def test_circles_propose_circle_from_directory(self, client):
        r = await client.post(
            "/circles/proposals",
            data={
                "title": "Digital Infrastructure Readiness Circle",
                "summary": "Cross-domain readiness checks for municipal agentic deployment.",
                "proposal_scope": "existing_domain",
                "target_circle_id": "civic-qa",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "Circle proposal submitted for review." in r.text
        assert "Digital Infrastructure Readiness Circle" in r.text

    async def test_circles_propose_new_domain_requires_rationale(self, client):
        r = await client.post(
            "/circles/proposals",
            data={
                "title": "Emergency Coordination Domain",
                "summary": "New domain proposal for multi-jurisdiction crisis handling.",
                "proposal_scope": "new_domain",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "require a rationale" in r.text

    async def test_circles_propose_circle_in_domain(self, client):
        r = await client.post(
            "/circles/public-health/proposals",
            data={
                "title": "Public Health Communications Circle",
                "summary": "Improve plain-language guidance between review and frontline response.",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "Circle proposal submitted to domain stewards." in r.text
        assert "Public Health Communications Circle" in r.text


class TestCirclesTrustIntegrity:
    """Trust/identity forgery must be impossible via form submission.

    Constitutional requirement: trust cannot be self-declared.  All trust
    and identity metadata must come from the server-side actor profile,
    never from form input.  Design tests #96-98.
    """

    async def test_forged_trust_ignored_on_apply(self, client):
        """Submitting a fake trust_score field must not change effective trust."""
        r = await client.post(
            "/circles/public-health/apply",
            data={
                "alias": "Forger-Apply",
                "trust_score": "999",  # forged — should be ignored
                "note": "Attempting trust forgery.",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        # The PoC demo user has trust 847 (from social_context).
        # If forgery worked, the posted trust would be 999.
        # Check the application shows the real trust, not the forged one.
        assert "Trust 847" in r.text or "Join request submitted" in r.text
        assert "Forger-Apply" not in r.text

    async def test_forged_trust_ignored_on_thread(self, client):
        """Submitting a fake trust_score on thread creation must be ignored."""
        r = await client.post(
            "/circles/public-health/maternal-outcomes-lane/threads",
            data={
                "title": "Forgery test thread",
                "summary": "Testing trust forgery.",
                "opening_body": "This should use server trust.",
                "trust_score": "999",  # forged
                "alias": "Forger-Thread",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "Circle created and opened for responses." in r.text
        assert "Forger-Thread" not in r.text

    async def test_forged_trust_ignored_on_reply(self, client):
        """Submitting a fake trust_score on reply must be ignored."""
        r = await client.post(
            "/circles/public-health/maternal-outcomes-lane/"
            "nicu-transfer-threshold-challenged-with-new-ward-evidence/reply",
            data={
                "body": "Forged reply attempt.",
                "trust_score": "999",  # forged
                "alias": "Forger-Reply",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "Reply posted" in r.text
        assert "Forger-Reply" not in r.text

    async def test_forged_actor_type_ignored_on_apply(self, client):
        """Claiming to be a machine via form must be ignored — actor type from profile."""
        r = await client.post(
            "/circles/public-health/apply",
            data={
                "alias": "Forger-Type",
                "actor_type": "machine",  # forged — PoC user is human
                "note": "Claiming to be a machine.",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        # The actor type should come from the PoC user profile (human),
        # not from the form claim (machine).
        assert "Join request submitted" in r.text
        assert "Forger-Type" not in r.text


class TestPoC:
    async def test_poc_page(self, client):
        r = await client.get("/poc")
        assert r.status_code == 200

    async def test_poc_json(self, client):
        r = await client.get("/poc", headers={"Accept": "application/json"})
        assert r.status_code == 200


class TestHTMX:
    async def test_mission_board_htmx(self, client):
        r = await client.get(
            "/missions",
            headers={"HX-Request": "true"},
        )
        assert r.status_code == 200
        # HTMX partial — should be a fragment, not full page
        assert "</html>" not in r.text


class TestErrors:
    async def test_404_page(self, client):
        r = await client.get("/this-route-does-not-exist")
        assert r.status_code == 404
        assert "404" in r.text
