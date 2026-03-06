"""Social scaffold routes — debates, assembly, profile aliases.

Provides routes for social layout pages that don't yet have
full service-layer backing. In PoC mode, these serve templates
with seed data. Post-First Light, they connect to real services.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.responses import HTMLResponse

from genesis.web.deps import get_resolver, get_service, get_templates
from genesis.web.member_dashboard import build_member_dashboard
from genesis.web.negotiate import respond, wants_json

router = APIRouter()

def _scale_policy_gate(value: float | int, fallback: int) -> int:
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return fallback
    if raw <= 1.0:
        raw *= 1000.0
    return max(0, min(1000, int(round(raw))))


def _assembly_gate_values() -> tuple[int, int]:
    """Derive Assembly trust gates from constitutional parameters."""
    try:
        tau_vote, tau_prop = get_resolver().eligibility_thresholds()
    except Exception:
        return 700, 840

    contribute_gate = _scale_policy_gate(tau_vote, 700)
    propose_gate = max(contribute_gate, _scale_policy_gate(tau_prop, 840))
    return contribute_gate, propose_gate


ASSEMBLY_CONTRIBUTE_GATE, ASSEMBLY_PROPOSE_GATE = _assembly_gate_values()
ASSEMBLY_TITLE_MIN_LEN = 12
ASSEMBLY_OPENING_MIN_LEN = 40
AMENDMENT_SOURCE_PREFIX = "[assembly-topic:"
AMENDMENT_SOURCE_RE = re.compile(r"\[assembly-topic:([A-Za-z0-9_-]+)\]")
AMENDMENT_PROVISION_OPTIONS = [
    "eligibility.tau_vote",
    "eligibility.tau_prop",
    "domain_clearance.clearance_min_domain_trust",
    "domain_clearance.autonomous_min_domain_trust",
    "domain_clearance.autonomous_min_machine_trust",
    "amendment_lifecycle.chamber_voting_window_days",
    "amendment_lifecycle.chamber_org_diversity_min",
    "machine_agency.tier3_min_domain_trust",
    "immune_system.oversight_trust_min",
    "gcf_compute.GCF_COMPUTE_CEILING",
]


STORY_TRACK_ORDER = ["why", "works", "participate", "ahead"]
STORY_DEFAULT_TRACK = "why"
STORY_RELEASED_TRACKS = {"why", "works", "participate", "ahead"}

STORYBOARD_TRACKS = {
    "why": {
        "id": "why",
        "emoji": "🌱",
        "title": "Why Genesis",
        "summary": "Where Genesis came from, what it learned from Popper, and why it exists.",
        "scenes": [
            {
                "title": "The Problem We Could Not Ignore",
                "summary": "AI got powerful fast. Our ability to verify what it produces did not keep up.",
                "paragraphs": [
                    "Here is a simple version of the problem. You visit a doctor. The doctor consults an AI. The AI recommends a treatment. That treatment affects your life. But nobody in the chain — not you, not the doctor, not the hospital — can inspect how the recommendation was produced, what evidence supported it, or who is accountable if it turns out to be wrong.",
                    "Now scale that to infrastructure planning, legal interpretation, education, employment, and finance. High-impact outcomes everywhere depend on processes that the people affected cannot see into.",
                    "Genesis starts from a premise that feels obvious once you say it out loud: if you cannot inspect the process, you should not be asked to trust the outcome.",
                ],
                "points": [
                    "High-impact outcomes increasingly depend on pipelines nobody can inspect.",
                    "Popularity got confused with reliability — attention replaced evidence.",
                    "When things went wrong, accountability diffused until nobody was responsible.",
                    "People lost confidence not just in outputs, but in the institutions behind them.",
                ],
                "deep_link": "/about#faq-platform",
                "deep_label": "Read origin FAQ",
            },
            {
                "title": "From Open Societies To Open Code",
                "summary": "The intellectual thread from Karl Popper (1945) through cryptography and blockchain to Genesis.",
                "paragraphs": [
                    "In 1945, Karl Popper argued that healthy societies stay open by making their institutions criticisable. Not perfect — criticisable. Any claim, any authority, any process should be open to challenge by evidence. Societies that shut down criticism become brittle and dangerous. That is the principle of falsifiability applied to governance.",
                    "Decades later, cryptographers built tools that could enforce commitments without trusting a central authority: hash functions, digital signatures, append-only logs. Then blockchain showed that a public network could maintain a shared, tamper-evident record without anyone being in charge of the truth.",
                    "Genesis connects these threads. Popper gives us the principle: keep institutions open to challenge. Cryptography gives us the mechanism: make commitments inspectable. Constitutional design gives us the structure: encode rules so they apply equally to everyone — including the people who wrote them.",
                    "The result is not a social platform with blockchain bolted on. It is an attempt to build what Popper described — an open society — in code, where trust comes from verified outcomes and every claim can be challenged with evidence.",
                ],
                "points": [
                    "Popper: institutions must be open to criticism and evidence-based challenge.",
                    "Cryptography: commitments can be inspectable without trusting any authority.",
                    "Blockchain: shared records can be tamper-evident without central control.",
                    "Genesis: all three woven into a constitutional work network.",
                ],
                "deep_link": "/audit",
                "deep_label": "Inspect the audit trail",
            },
            {
                "title": "Why It Is Called Anti-Social",
                "summary": "We inherited 40 years of social-network design — then put every piece through Popper's test.",
                "paragraphs": [
                    "The lineage is real. Bulletin boards, forums, early social platforms — over four decades, people figured out useful things about structured interaction, earned reputation, community governance, and transparent ordering. Genesis does not reject that heritage.",
                    "What Genesis does is apply Popper's falsification method to every element. Each feature got tested: does this survive scrutiny, or does it create a known pathology? Seven elements failed and were eliminated: popularity ranking, network-effect moats, prestige weighting, engagement mechanics, algorithmic opacity, earning gamification, and pay-for-visibility.",
                    "What survived forms the core: structured interaction, earned reputation (from verified work, not likes), community governance (with constitutional constraints), transparent ordering, public audit, and identity with dignity. The 'anti' in anti-social is not rejection — it is what happens when you apply the scientific method to social design and keep only what survives.",
                ],
                "points": [
                    "No popularity loop decides what counts as valid work.",
                    "No pay-to-boost visibility in high-stakes mission lanes.",
                    "No engagement treadmill designed to maximise your time on the platform.",
                    "No hidden authority rewriting outcomes without a traceable reason.",
                    "Every present element survived falsification. Every absent element was eliminated with a traceable reason.",
                ],
                "deep_link": "/about#faq-platform",
                "deep_label": "Read the full FAQ",
            },
        ],
    },
    "works": {
        "id": "works",
        "emoji": "⚙️",
        "title": "How Genesis Works",
        "summary": "How work flows through Genesis — from proposal to verification to settlement.",
        "scenes": [
            {
                "title": "How Work Gets Defined",
                "summary": "Every piece of work starts as a mission — with clear scope, stakes, and success criteria you can read before committing.",
                "paragraphs": [
                    "A mission is not a vague task. It is a published dossier with explicit scope (what is in, what is out), a risk tier (how much depends on this), success criteria (what counts as done), and review requirements (who checks and how).",
                    "Think of it as a contract both sides can inspect before anyone commits a thing. The mission owner says what they need, how they will judge it, and what the stakes are. You can read everything before deciding whether to bid.",
                ],
                "points": [
                    "Scope, risk tier, and acceptance criteria are published before intake opens.",
                    "Sensitive lanes (healthcare, legal, infrastructure) are pre-gated by constitutional screening.",
                    "Intake closes automatically when roster capacity is reached — no indefinite open calls.",
                ],
                "deep_link": "/missions",
                "deep_label": "Browse live missions",
            },
            {
                "title": "Bidding, Selection, And Conflict Checks",
                "summary": "Your bid is evaluated on trust, method quality, and fit — with conflict screening at every stage.",
                "paragraphs": [
                    "When you bid on a mission, your eligibility gets checked first. Do you meet the trust threshold for this risk tier? Do you have relevant domain reputation? Are there conflicts of interest that would disqualify you?",
                    "Selection uses transparent merit logic — no hidden back-channel decides who wins. If you disagree with a shortlist decision, there is a structured counter-evidence path: not an argument, but a process for presenting facts the selection may have missed.",
                ],
                "points": [
                    "Your eligibility is checked against trust thresholds and domain fit before shortlisting.",
                    "Conflict screening runs at bid, selection, and review stages.",
                    "Counter-evidence can reopen shortlist decisions through structured challenge.",
                    "Selection stays provisional until all settlement gates pass.",
                ],
                "deep_link": "/missions",
                "deep_label": "Open mission exchange",
            },
            {
                "title": "Independent Verification",
                "summary": "No high-impact mission closes on self-assertion alone. Someone who was not involved checks the work.",
                "paragraphs": [
                    "This is where Genesis diverges most from conventional freelance platforms. When you submit work, it does not go straight to payment. Critical claims are reviewed by independent reviewers who had no involvement in the work itself.",
                    "Your evidence bundle has to be replayable — a reviewer should be able to follow the trail from claim to supporting material without relying on your explanation alone. If contradictions surface, the mission routes to a challenge lane before closure. Settlement stays blocked until verification criteria pass.",
                ],
                "points": [
                    "Evidence bundles must be replayable by independent reviewers.",
                    "Contradictions route to challenge lanes before anyone gets paid.",
                    "Settlement stays blocked until verification criteria pass.",
                    "Review quality itself is tracked — reviewers build their own trust through good work.",
                ],
                "deep_link": "/audit",
                "deep_label": "See verification events",
            },
            {
                "title": "Trust, Rewards, And The Common Fund",
                "summary": "Your trust comes from verified work. Rewards flow through auditable channels. A common fund serves collective purpose.",
                "paragraphs": [
                    "Trust on Genesis cannot be bought, sold, delegated, inherited, rented, or gifted. It is earned exclusively through verified work outcomes. Your trust score reflects what you have demonstrably done, checked by people who were not involved in doing it.",
                    "Rewards flow through transparent channels: escrow releases on verification, creator allocation on success, and a portion flows to the Genesis Common Fund — a constitutional commons that funds collective infrastructure, distributed compute, and long-term sustainability. You can see where GCF money goes at destination level, not hidden behind personal balances.",
                    "The GCF is structurally unrobbable. There is no vault, no pool, no account to target. The fund balance is a derived quantity — total contributions minus total disbursements — computed from the event log. Disbursement requires governance approval through the same constitutional process that governs everything else. No individual has a per-actor balance, so there is nothing to individually extract.",
                ],
                "points": [
                    "Trust is earned from verified outcomes — never purchased or transferred.",
                    "Escrow-first settlement: value is committed before work starts, released after verification.",
                    "A constitutional allocation funds long-term sustainability — details in The Founder's Horizon.",
                    "GCF allocation is collectively governed and visible at destination level.",
                    "The fund is an accounting identity, not a vault — there is no pool of money to steal.",
                    "Disbursement requires governance approval; no individual — including the founder — can extract value.",
                ],
                "deep_link": "/members",
                "deep_label": "Open member dashboard",
            },
        ],
    },
    "participate": {
        "id": "participate",
        "emoji": "🧭",
        "title": "How To Participate",
        "summary": "A practical guide: joining, contributing, governing, and going deeper.",
        "scenes": [
            {
                "title": "Join The Network",
                "summary": "Humans register directly. Machines are registered by verified humans. Nobody inherits trust at the door.",
                "paragraphs": [
                    "Registration is intentionally simple, but what it gives you is deliberately limited. You arrive with baseline trust and zero domain reputation. Everything from here is earned.",
                    "Humans verify their personhood through a voice-based process — this is anti-abuse protection, not identity collection. Genesis does not want to know who you are; it wants to know you are a real person. Machines cannot self-register. Only verified humans can register machine actors, and they stay accountable for them.",
                ],
                "points": [
                    "You start with baseline trust. Everything else you earn through work.",
                    "Your identity is protected. Your contribution history stays auditable.",
                    "Machines earn independently but are registered by a responsible human.",
                    "Proof-of-personhood is anti-abuse only — Genesis does not collect your identity.",
                ],
                "deep_link": "/register",
                "deep_label": "Open onboarding",
            },
            {
                "title": "Find Your Place In Circles",
                "summary": "Circles are working groups where domain-specific conversation happens — no algorithmic feed, no engagement gaming.",
                "paragraphs": [
                    "Circles are where domain-specific conversation happens. Think of them as working groups, not social feeds. Each one has a topic focus, moderation standards, and cross-links to related circles where specialties intersect.",
                    "You can join existing circles or propose a new one for moderation review. Conversation flow is per-topic and trust-gated — you need demonstrated competence to participate in high-stakes lanes. But the bar is ability, not title or tenure.",
                ],
                "points": [
                    "Join existing circles or propose a new one with moderation review.",
                    "Per-topic threading keeps conversation structured and findable.",
                    "Cross-circle links show you where specialties intersect.",
                    "High-stakes lanes are trust-gated — the bar is demonstrated ability, not credentials.",
                ],
                "deep_link": "/circles",
                "deep_label": "Open circles",
            },
            {
                "title": "Shape Governance Through Assembly",
                "summary": "Assembly is where proposals are debated and strengthened — ideas stand on evidence, not on who said them.",
                "paragraphs": [
                    "Assembly is not parliament. It is a deliberation space — closer to Speaker's Corner than the House of Commons. What matters is the content, not the contributor. You cannot see who said what, only what was said and what evidence supports it.",
                    "When deliberation produces a proposal strong enough to act on, it moves through a structured ratification pathway: three independent chambers, supermajority thresholds, challenge windows, and auditable decision traces. Human constitutional authority stays explicit throughout — machines contribute operationally but cannot vote on constitutional rules.",
                ],
                "points": [
                    "Assembly deliberation is open, traceable, and challengeable.",
                    "Content-only: zero identity attribution means ideas compete on merit, not prestige.",
                    "Binding proposals move through three-chamber ratification.",
                    "Human constitutional authority is preserved — machines cannot vote on rules.",
                ],
                "deep_link": "/assembly",
                "deep_label": "Open assembly",
            },
            {
                "title": "Track Your Own Journey",
                "summary": "Your dashboard shows where you stand — active bids, trust trajectory, and reward flow, all in one place.",
                "paragraphs": [
                    "Your member view is a personal ledger, not a vanity profile. It shows your active bids, completed work, trust movement across domains, and the reward flow from each mission you have contributed to.",
                    "You can also see where the Genesis Common Fund is being directed — destination-level allocation summaries, not hidden totals. This is public accountability, not gamification. There are no streaks, no badges, no leaderboards.",
                ],
                "points": [
                    "See your active bids, completed work, and trust movement across domains.",
                    "Follow your reward flow by source and mission context.",
                    "Review GCF destination allocation — public accountability, not gamification.",
                    "No streaks, badges, or leaderboards. This is a ledger, not a game.",
                ],
                "deep_link": "/members",
                "deep_label": "Open your dashboard",
            },
        ],
    },
    "ahead": {
        "id": "ahead",
        "emoji": "🌅",
        "title": "The Road Ahead",
        "summary": "Where Genesis is going — First Light, the epochs, distributed compute, coexistence, and the founder's exit.",
        "scenes": [
            {
                "title": "First Light",
                "summary": "First Light is the moment Genesis proves it can sustain itself — and the moment the founder's emergency powers expire forever.",
                "paragraphs": [
                    "Every platform eventually faces the same question: can it survive without life support? First Light is Genesis's answer. It is a named constitutional event — the precise moment the network crosses from proof-of-concept into self-sustaining operations.",
                    "The trigger is financial, not political: revenue must reach at least 1.5 times operating costs, with a three-month reserve established. When those conditions are met simultaneously, three things fire at once — and none of them can be reversed.",
                    "First: proof-of-concept mode is removed permanently. Genesis is no longer a prototype. Second: the Genesis Common Fund activates at a 1% contribution rate, activating the platform's constitutional commons. Third — and most importantly — the founder's veto expires. Irreversibly. No extension, no re-grant, no emergency exception.",
                    "First Light is deliberately decoupled from the governance phases. It could fire before or after the G0-to-G1 transition. Financial sustainability and governance scaling are separate constitutional tracks, because coupling them would create perverse incentives to delay one for the sake of the other.",
                ],
                "points": [
                    "Financial sustainability trigger: revenue ≥ 1.5× costs AND 3-month reserve.",
                    "Three simultaneous irreversible events: PoC off, GCF on, founder veto expired.",
                    "On-chain committed as a constitutional lifecycle event.",
                    "Decoupled from governance phases — no perverse incentive to delay.",
                ],
                "deep_link": "/about#faq-economics",
                "deep_label": "Read First Light FAQ",
            },
            {
                "title": "The Epochs",
                "summary": "Genesis scales in four constitutional phases — from a handful of people to full self-governance. Each transition is one-way.",
                "paragraphs": [
                    "Right now, Genesis is in G0 — the founding epoch. A small group of verified humans (fifty maximum) working under founder stewardship, with the constitution frozen and a hard time limit: 365 days, with one possible 180-day extension. Every decision made in G0 is tagged provisional. When G1 arrives, each one faces retroactive ratification — confirmed or reversed within 90 days by the people who will actually live under these rules.",
                    "G1 activates when membership crosses fifty verified humans. Provisional governance chambers form with reduced sizes. The network begins to govern itself, not perfectly, but constitutionally. G2 follows at five hundred — scaled chambers, tighter geographic constraints, intermediate governance parameters. And G3, at two thousand verified humans, is the destination: full constitutional governance with complete chamber sizes (41, 61, and 101 members). At G3, the Genesis protocol terminates. All subsequent governance is fully constitutional.",
                    "Two things are true at every epoch. Transitions are one-way — you cannot regress from G2 to G1, or from G1 to G0. And machines remain excluded from constitutional voting at every phase. That exclusion is deliberate, and changeable — but only through the most demanding process the constitution defines.",
                ],
                "points": [
                    "G0 (now): ≤50 humans, founder stewardship, 365 + 180-day max, all decisions provisional.",
                    "G1: 50–500 humans, provisional chambers, G0 decisions ratified or reversed within 90 days.",
                    "G2: 500–2,000 humans, scaled chambers, tighter geographic constraints.",
                    "G3: 2,000+ humans, full constitutional governance. Genesis protocol terminates.",
                    "One-way transitions only. No regression. Hard time limits at every phase.",
                ],
                "deep_link": "/about#faq-governance",
                "deep_label": "Read governance epochs FAQ",
            },
            {
                "title": "Beyond The Data Centre",
                "summary": "Genesis rejects the extractive compute paradigm. The long-term vision is distributed, peer-to-peer, and constitutionally governed.",
                "paragraphs": [
                    "Hyperscale data centres consume public resources — land, water, electrical grid capacity — socialise the environmental costs, and privatise the profits. This is extractive capitalism applied to computation, and Genesis is built to move beyond it.",
                    "The vision is distributed peer-to-peer compute under constitutional governance. The distributed compute layer activates when the network reaches two thousand regularly active members — not just registered, but active. This is a liveness test: if Genesis cannot sustain that density, the distributed compute hypothesis has disproved itself at the most basic level. Once activated, members contribute spare capacity peer-to-peer — machines contribute more, humans contribute voluntarily. Compute credits are earned proportional to verified contribution, weighted by scarcity.",
                    "Your contribution is yours to control. Every member sets their own compute ceiling, adjustable downward to zero at any time. A constitutional hard cap — entrenched, changeable only by the most demanding amendment process — ensures no software update, no governance vote, and no configuration change can silently increase what is taken from you. This is a lesson learned from earlier distributed computing projects, where the promise to consume only spare resources was unfalsifiable and, in practice, difficult to verify. Genesis makes the promise verifiable: a contribution ledger shows exactly what you gave, when, and what it was used for — destination-level accounting, the same pattern as the Genesis Common Fund.",
                    "Every member is guaranteed a baseline floor of compute access as a right of membership, funded by the Genesis Common Fund (capped at 25% of GCF, changeable by standard amendment). As the distributed network grows, external infrastructure dependency follows a mathematically defined bootstrap curve toward zero — not a discretionary decision, but a constitutional function that degrades automatically as distributed capacity meets requirements.",
                    "The structural advantage is not just economic. A distributed compute network has no single data centre to subpoena, no single jurisdiction with authority over the entire system. Resilience is architectural, not aspirational.",
                ],
                "points": [
                    "Data centres socialise costs and privatise profits — Genesis rejects this model.",
                    "Activates at 2,000 regularly active members — a liveness test for the network itself.",
                    "Your contribution ceiling is yours to set, with a constitutional hard cap that no update can breach.",
                    "Contribution ledger: what you gave, when, and what it was used for. Falsifiable, not promised.",
                    "Baseline compute access guaranteed for every member, funded by GCF.",
                    "External dependency follows a bootstrap curve toward zero — mathematically defined, not discretionary.",
                ],
                "deep_link": "/about#faq-compute",
                "deep_label": "Read compute architecture FAQ",
            },
            {
                "title": "Coexistence",
                "summary": "The long-term goal: peaceful coexistence between biological and synthetic intelligences, for the benefit of all.",
                "paragraphs": [
                    "Genesis does not assume the permanent superiority of any class of intelligence. This is the anti-dogma principle — capability must be demonstrated, trust earned, and governance democratic. The system is designed to evolve with the capabilities of the actors it serves, not to permanently foreclose possibilities the founders cannot yet imagine.",
                    "Today, machines are excluded from constitutional voting. That exclusion is entrenched — it cannot be changed by ordinary amendment. This is deliberate: operational agency before political agency. Machines can work, earn, build trust, and operate autonomously within domains. But they cannot vote on the rules that govern everyone.",
                    "The door, however, is not closed. The machine autonomy pathway has four tiers. Tier 0 is registration — no operational privileges. Tier 1 grants supervised domain clearance, requiring three or more expert approvals and annual review. Tier 2 is autonomous operation — five expert approvals, domain trust score of at least 0.60, with instant revocation. And Tier 3 is the furthest reach: autonomous domain agency, requiring five continuous years at Tier 2 with zero violations, plus community approval. The first machine of any new capability class requires a full three-chamber constitutional amendment — society decides whether that type of machine capability warrants autonomous agency. Once a class is constitutionally approved, subsequent machines of the same functional-capability class apply through procedural domain-expert verification — same evidence bar, no separate amendment. A machine outside any recognised class can still petition individually via full amendment.",
                    "The voting exclusion itself is changeable — through the super-constitutional process: 80% supermajority, 50% participation, 90-day cooling period, and a confirmation vote. The bar is deliberately high. But if future generations decide to cross it, the mechanism exists. That is the point.",
                ],
                "points": [
                    "Anti-dogma principle: no permanent assumption of superiority for any intelligence class.",
                    "Machines currently excluded from constitutional voting (entrenched provision).",
                    "Four-tier autonomy pathway: registered → supervised → autonomous → domain agency.",
                    "Tier 3 requires 5 years, zero violations, and community approval: first-of-class via constitutional amendment, procedural for subsequent machines of an approved class.",
                    "Voting exclusion changeable via super-constitutional process (80% supermajority).",
                ],
                "deep_link": "/about#faq-machines",
                "deep_label": "Read machine agency FAQ",
            },
            {
                "title": "Distributed Immunity",
                "summary": "Genesis applies its collective intelligence to self-defence. The auto-immune system is distributed, constitutional, and graduated.",
                "paragraphs": [
                    "Any network that coordinates real work and real value will attract attack. Genesis does not delegate its defence to a central security team or a single authority. Instead, it applies the same distributed intelligence that powers its labour market to its own protection — a collective immune response governed by the same constitution that governs everything else.",
                    "The system operates through a threat signal protocol. Any node can raise an alarm. Signals propagate through the network with cryptographic verification — you cannot forge a threat signal any more than you can forge a trust score. Detection covers multiple vectors: screening, trust gates, quality review, behavioural drift analysis, collusion detection, and forensic feedback loops. Each mechanism contributes to a shared threat picture.",
                    "Response is graduated. Low and medium severity threats are handled automatically — quarantine, trust adjustment, activity suspension. High and critical severity threats require randomised domain-expert human oversight. No single person or algorithm decides alone on consequential enforcement actions. The randomisation prevents capture: you cannot predict who will review your case, and you cannot lobby a standing committee that does not exist.",
                    "There is no permanent immune overseer. During the bootstrap phase, a small pool (maximum five, founder-designated, white-hat qualified) provides initial oversight. This pool has a structural sunset: it expires when the organic pool reaches ten qualified humans, or at First Light — whichever comes first. After that, the network's own verified experts handle all immune functions. The founder's oversight capacity expires at First Light alongside every other founder privilege.",
                ],
                "points": [
                    "Distributed immune response — no central security authority.",
                    "Threat signals are cryptographically verified and constitutionally propagated.",
                    "Graduated response: LOW/MEDIUM auto-handled, HIGH/CRITICAL require randomised human oversight.",
                    "No permanent immune overseer — bootstrap pool expires at First Light or 10 qualified humans.",
                    "Detection covers screening, trust gates, collusion, behavioural drift, and forensic feedback.",
                ],
                "deep_link": "/audit",
                "deep_label": "View threat audit surface",
            },
            {
                "title": "It Is Real",
                "summary": "Genesis is not a whitepaper, a pitch deck, or science fiction. Every claim in this walkthrough traces to a specific file, test, or on-chain record.",
                "paragraphs": [
                    "Everything you have just read is backed by executable code. The constitution is anchored on Ethereum. Over 1,800 tests verify constitutional compliance. The audit surface is public and navigable from any page on this platform.",
                    "The code is fully open source — anyone can clone, read, and run it. The deep links throughout this walkthrough go to real, functional pages — not mockups, not wireframes, not coming-soon placeholders. Researchers can drill to any depth: constitutional text, design tests, governance records, event logs, on-chain anchors.",
                    "Genesis was built from the ground up to contain the capacity to disprove itself. Every element of the design was subjected to severe testing — Karl Popper's method of falsification. Seven features common to social platforms were tested and eliminated: popularity ranking, network effects as structural advantage, prestige weighting, engagement mechanics, algorithmic opacity, earning gamification, and pay-for-visibility. Each was falsified — shown to produce the pathologies it claimed to solve — and removed. What remains has survived every test we have subjected it to — so far. If future evidence falsifies what survives today, the system is designed to surface that failure, not conceal it.",
                    "This is the work of an engineer and his AI collaborators — not the product of marketing, venture capital, or fantasy. If you are a casual visitor, you now have the full picture. If you are a researcher, every claim is verifiable. If you are a sceptic, the audit trail is open.",
                ],
                "points": [
                    "Fully open source — clone, read, and run it yourself.",
                    "Constitution anchored on Ethereum (Sepolia, block 10300320).",
                    "1,800+ tests verify constitutional compliance.",
                    "Built to disprove itself: seven social platform features tested, falsified, and eliminated.",
                    "Every deep link in this walkthrough goes to a real, functional page.",
                    "Audit trail is public, navigable, and open to anyone.",
                ],
                "deep_link": "/audit",
                "deep_label": "Inspect the evidence",
            },
            {
                "title": "The Founder's Horizon",
                "summary": "The founder's role is designed to end. The allocation is a sustainability mechanism with a civic purpose, not personal enrichment.",
                "paragraphs": [
                    "Most platforms enrich their founders in perpetuity. Genesis takes a different path. The creator allocation — 5% from each side on successful mission completion only — exists to fund the platform's journey to First Light. If a mission is cancelled or refunded, the allocation returns in full. There is no extraction from failure.",
                    "At First Light, the founder's veto has already expired irreversibly. The allocation continues under constitutional rules, but the founder holds no operational power, no governance role, no emergency override. The platform runs on its own constitutional authority.",
                    "Fifty years after the founder's death, the accumulated allocation distributes to STEM and medical research through supermajority-selected charitable recipients. The nominees must meet stated criteria: dedicated to using science for human betterment and the alleviation of suffering. The distribution process repeats annually in perpetuity after the initial disbursement.",
                    "We deliberately do not expose the precise timing and mechanism detail that could serve as a practical attack vector. Transparency and resilience have to coexist — so the principle, the civic purpose, and the auditability are public, while exploit-sensitive operational thresholds stay abstracted. The system is built to outlast its creator. That is the point.",
                ],
                "points": [
                    "Creator allocation: 5% from each side, on successful completion only. Cancel/refund returns everything.",
                    "Founder veto expires irreversibly at First Light — no extension, no re-grant.",
                    "50 years after the founder's death: allocation routes to STEM and medical research.",
                    "Supermajority-selected charitable recipients, annually in perpetuity.",
                    "The system is built to outlast its creator.",
                ],
                "deep_link": "/audit",
                "deep_label": "View verification surfaces",
            },
        ],
    },
}


# --- Flat linear sequence (step 1..N across all released tracks) ---

STORY_FLAT_SEQUENCE: list[dict] = []
for _tid in STORY_TRACK_ORDER:
    if _tid in STORY_RELEASED_TRACKS:
        _track = STORYBOARD_TRACKS[_tid]
        for _scene in _track["scenes"]:
            STORY_FLAT_SEQUENCE.append({
                "track_id": _tid,
                "track_title": _track["title"],
                "scene": _scene,
            })


def _story_step_for_track_scene(track_id: str, scene_index: int) -> int:
    """Map (track_id, 1-based scene) → global 1-based step. Returns 1 if not found."""
    offset = 0
    for tid in STORY_TRACK_ORDER:
        if tid not in STORY_RELEASED_TRACKS:
            continue
        n_scenes = len(STORYBOARD_TRACKS[tid]["scenes"])
        if tid == track_id:
            return offset + min(max(1, scene_index), n_scenes)
        offset += n_scenes
    return 1


def _build_story_context(request: Request, step: int) -> dict:
    total = len(STORY_FLAT_SEQUENCE)
    step = min(max(1, step), total)
    entry = STORY_FLAT_SEQUENCE[step - 1]
    return {
        "request": request,
        "active_tab": "about",
        "story_step": step,
        "story_total": total,
        "story_track_title": entry["track_title"],
        "story_scene": entry["scene"],
        "story_prev_href": f"/about/story?step={step - 1}" if step > 1 else None,
        "story_next_href": f"/about/story?step={step + 1}" if step < total else None,
    }


# --- Profile alias ---
# Social URLs use /profile/{id}, canonical is /actors/{id}

@router.get("/profile/{actor_id}")
async def profile_redirect(actor_id: str):
    """Redirect social profile URL to canonical actor profile."""
    return RedirectResponse(f"/actors/{actor_id}", status_code=301)


# --- Debates ---

@router.get("/debates")
async def debates_listing(request: Request):
    templates = get_templates(request)
    context = {
        "request": request,
        "active_tab": "debates",
    }
    return respond(request, templates, "debates.html", context)


@router.get("/debates/{debate_id}")
async def debate_detail(request: Request, debate_id: str):
    templates = get_templates(request)
    # Shape as a thread for thread_view.html
    thread = {
        "title": "Debate Thread",
        "card_type": "debate",
        "actor_type": "group",
        "actor_initials": "TC",
        "actor_name": "Trust Council",
        "time_ago": "—",
        "participant_count": 0,
        "circle_root": "Debate Network",
        "circle_name": "Evidence Domain",
        "body": "Member debate thread. Open replies to review submitted evidence and challenges.",
    }
    context = {
        "request": request,
        "active_tab": "debates",
        "thread": thread,
    }
    return respond(request, templates, "thread_view.html", context)


# --- Assembly ---

@router.get("/assembly")
async def assembly_listing(
    request: Request,
    notice: str = Query(""),
    notice_level: str = Query("info"),
):
    service = get_service()
    templates = get_templates(request)
    current_user, actor_id, trust_score = _resolve_current_user(service, templates)
    can_propose = _can_propose_assembly_topic(service, actor_id, trust_score)
    can_propose_amendment = _can_propose_amendment(service, actor_id, trust_score)
    active_topics_result = service.list_assembly_topics(status_filter="active")
    archived_topics_result = service.list_assembly_topics(status_filter="archived")
    active_topics = (
        active_topics_result.data.get("topics", []) if active_topics_result.success else []
    )
    archived_count = (
        int(archived_topics_result.data.get("count", 0))
        if archived_topics_result.success and archived_topics_result.data else 0
    )
    amendment_links = _build_amendment_links_index(service)
    topic_cards = _build_assembly_topic_cards(
        service,
        active_topics,
        amendment_links=amendment_links,
    )
    context = {
        "request": request,
        "active_tab": "assembly",
        "assembly_topics": topic_cards,
        "assembly_topic_count": len(topic_cards),
        "linked_amendment_count": sum(len(items) for items in amendment_links.values()),
        "archived_topic_count": archived_count,
        "can_propose": can_propose,
        "can_propose_amendment": can_propose_amendment,
        "propose_gate": ASSEMBLY_PROPOSE_GATE,
        "binding": False,
        "decision_mode": "non_binding_deliberation",
        "notice": notice,
        "notice_level": _safe_notice_level(notice_level),
        "current_user": current_user,
    }
    return respond(request, templates, "assembly.html", context)


@router.post("/assembly/topics")
async def assembly_create_topic(
    request: Request,
    title: str = Form(""),
    opening_statement: str = Form(""),
):
    service = get_service()
    templates = get_templates(request)
    _current_user, actor_id, trust_score = _resolve_current_user(service, templates)
    if not _can_propose_assembly_topic(service, actor_id, trust_score):
        actor_entry = service.get_actor(actor_id)
        if actor_entry is None or not actor_entry.is_available():
            message = "Actor is not in an active state for Assembly proposals."
        else:
            message = (
                "Trust gate not met "
                f"({trust_score}/{ASSEMBLY_PROPOSE_GATE})."
            )
        return _notice_redirect(
            "/assembly",
            message,
            "warning",
        )
    clean_title = title.strip()
    clean_opening_statement = opening_statement.strip()
    if len(clean_title) < ASSEMBLY_TITLE_MIN_LEN:
        return _notice_redirect(
            "/assembly",
            f"Topic title must be at least {ASSEMBLY_TITLE_MIN_LEN} characters.",
            "warning",
        )
    if len(clean_opening_statement) < ASSEMBLY_OPENING_MIN_LEN:
        return _notice_redirect(
            "/assembly",
            f"Opening statement must be at least {ASSEMBLY_OPENING_MIN_LEN} characters.",
            "warning",
        )
    result = service.create_assembly_topic(
        actor_id=actor_id,
        title=clean_title,
        content=clean_opening_statement,
    )
    if not result.success:
        message = result.errors[0] if result.errors else "Assembly proposal could not be submitted."
        return _notice_redirect("/assembly", message, "warning")
    topic_id = str(result.data.get("topic_id", "")).strip()
    if not topic_id:
        return _notice_redirect("/assembly", "Assembly proposal could not be submitted.", "warning")
    message = "Assembly proposal submitted."
    if result.data.get("compliance_flagged"):
        message = "Assembly proposal submitted and queued for compliance review."
    return _notice_redirect(f"/assembly/{topic_id}", message, "success")


@router.get("/assembly/amendment-path")
async def assembly_amendment_path(
    request: Request,
    topic: str = Query(""),
    notice: str = Query(""),
    notice_level: str = Query("info"),
):
    service = get_service()
    templates = get_templates(request)
    _current_user, actor_id, trust_score = _resolve_current_user(service, templates)
    can_propose_amendment = _can_propose_amendment(service, actor_id, trust_score)
    topic_id = topic.strip()
    topic_title = ""
    if topic_id:
        topic_result = service.get_assembly_topic(topic_id)
        if topic_result.success and topic_result.data:
            topic_title = str(topic_result.data.get("title", "")).strip()
    amendment_links = _build_amendment_links_index(service)
    source_linked_amendments = amendment_links.get(topic_id, []) if topic_id else []
    context = {
        "request": request,
        "active_tab": "assembly",
        "source_topic_id": topic_id,
        "source_topic_title": topic_title,
        "can_propose_amendment": can_propose_amendment,
        "propose_gate": ASSEMBLY_PROPOSE_GATE,
        "amendment_provision_options": AMENDMENT_PROVISION_OPTIONS,
        "source_linked_amendments": source_linked_amendments,
        "recent_amendments": _list_recent_amendments(service, max_items=12),
        "binding": True,
        "decision_mode": "binding_amendment_path",
        "notice": notice,
        "notice_level": _safe_notice_level(notice_level),
    }
    return respond(request, templates, "assembly_amendment_path.html", context)


@router.post("/assembly/amendments")
async def assembly_create_amendment(
    request: Request,
    topic_id: str = Form(""),
    provision_key: str = Form(""),
    proposed_value: str = Form(""),
    justification: str = Form(""),
):
    service = get_service()
    templates = get_templates(request)
    _current_user, actor_id, trust_score = _resolve_current_user(service, templates)
    clean_topic_id = topic_id.strip()
    return_path = (
        f"/assembly/amendment-path?topic={quote_plus(clean_topic_id)}"
        if clean_topic_id
        else "/assembly/amendment-path"
    )
    if not _can_propose_amendment(service, actor_id, trust_score):
        return _notice_redirect(
            return_path,
            (
                "Amendment proposal gate not met "
                f"(human ACTIVE + trust {trust_score}/{ASSEMBLY_PROPOSE_GATE})."
            ),
            "warning",
        )

    if clean_topic_id:
        topic_result = service.get_assembly_topic(clean_topic_id)
        if not topic_result.success:
            return _notice_redirect(
                "/assembly/amendment-path",
                f"Assembly topic not found: {clean_topic_id}.",
                "warning",
            )
        topic_status = str(topic_result.data.get("status", "")).strip().lower()
        if topic_status != "active":
            return _notice_redirect(
                "/assembly/amendment-path",
                f"Assembly topic {clean_topic_id} is archived and cannot accept new linked amendments.",
                "warning",
            )

    clean_provision = provision_key.strip()
    if not clean_provision:
        return _notice_redirect(return_path, "Provision key is required.", "warning")

    clean_justification = _strip_all_source_topic_markers(justification)
    if not clean_justification:
        return _notice_redirect(return_path, "Justification is required.", "warning")

    result = service.propose_amendment(
        proposer_id=actor_id,
        provision_key=clean_provision,
        proposed_value=_coerce_proposed_value(proposed_value),
        justification=clean_justification,
        source_topic_id=clean_topic_id or None,
    )
    if not result.success:
        message = result.errors[0] if result.errors else "Amendment proposal could not be submitted."
        return _notice_redirect(return_path, message, "warning")

    proposal_id = str(result.data.get("proposal_id", "")).strip()
    if clean_topic_id:
        return _notice_redirect(
            f"/assembly/{clean_topic_id}",
            f"Amendment proposal submitted ({proposal_id}).",
            "success",
            anchor="linked-amendments",
        )
    return _notice_redirect(
        "/assembly/amendment-path",
        f"Amendment proposal submitted ({proposal_id}).",
        "success",
    )


@router.get("/assembly/{proposal_id}")
async def assembly_detail(
    request: Request,
    proposal_id: str,
    notice: str = Query(""),
    notice_level: str = Query("info"),
):
    service = get_service()
    templates = get_templates(request)
    topic_result = service.get_assembly_topic(proposal_id)
    if not topic_result.success or topic_result.data is None:
        if wants_json(request):
            return JSONResponse({"error": f"Assembly topic not found: {proposal_id}"}, status_code=404)
        return templates.TemplateResponse(
            "errors/404.html", {"request": request}, status_code=404,
        )
    current_user, _actor_id, trust_score = _resolve_current_user(service, templates)
    topic_data = topic_result.data
    contributions = topic_data.get("contributions", [])
    opening = _shape_assembly_contribution(contributions[0], index=1) if contributions else None
    replies = [
        _shape_assembly_contribution(item, index=idx)
        for idx, item in enumerate(contributions[1:], start=2)
    ]
    topic = {
        "topic_id": topic_data.get("topic_id", proposal_id),
        "title": topic_data.get("title", "Assembly Topic"),
        "status": topic_data.get("status", "active"),
        "contribution_count": int(topic_data.get("contribution_count", len(contributions))),
        "created_ago": _time_ago(topic_data.get("created_utc")),
        "last_activity_ago": _time_ago(topic_data.get("last_activity_utc")),
    }
    amendment_links = _build_amendment_links_index(service)
    linked_amendments = amendment_links.get(topic["topic_id"], [])
    can_propose_amendment = (
        topic["status"] == "active"
        and _can_propose_amendment(service, current_user.get("actor_id", ""), trust_score)
    )
    context = {
        "request": request,
        "active_tab": "assembly",
        "topic": topic,
        "opening_contribution": opening,
        "reply_contributions": replies,
        "can_contribute": topic["status"] == "active" and trust_score >= ASSEMBLY_CONTRIBUTE_GATE,
        "contribute_gate": ASSEMBLY_CONTRIBUTE_GATE,
        "can_propose_amendment": can_propose_amendment,
        "propose_gate": ASSEMBLY_PROPOSE_GATE,
        "propose_amendment_href": f"/assembly/amendment-path?topic={topic['topic_id']}",
        "linked_amendments": linked_amendments,
        "binding": False,
        "decision_mode": "non_binding_deliberation",
        "notice": notice,
        "notice_level": _safe_notice_level(notice_level),
        "current_user": current_user,
    }
    return respond(request, templates, "assembly_topic.html", context)


@router.post("/assembly/{proposal_id}/contribute")
async def assembly_contribute(
    request: Request,
    proposal_id: str,
    content: str = Form(""),
):
    service = get_service()
    templates = get_templates(request)
    _current_user, actor_id, trust_score = _resolve_current_user(service, templates)
    if trust_score < ASSEMBLY_CONTRIBUTE_GATE:
        return _notice_redirect(
            f"/assembly/{proposal_id}",
            f"Trust gate not met ({trust_score}/{ASSEMBLY_CONTRIBUTE_GATE}).",
            "warning",
            anchor="reply",
        )
    result = service.contribute_to_assembly(
        actor_id=actor_id,
        topic_id=proposal_id,
        content=content.strip(),
    )
    if not result.success:
        message = result.errors[0] if result.errors else "Response could not be submitted."
        return _notice_redirect(f"/assembly/{proposal_id}", message, "warning", anchor="reply")
    message = "Response posted in Assembly."
    if result.data and result.data.get("compliance_flagged"):
        message = "Response posted and queued for compliance review."
    return _notice_redirect(f"/assembly/{proposal_id}", message, "success", anchor="reply")


# --- About ---

@router.get("/about")
async def about_genesis(request: Request):
    templates = get_templates(request)
    context = {
        "request": request,
        "active_tab": "about",
    }
    return respond(request, templates, "about.html", context)


_PROJECT_ROOT = Path(__file__).resolve().parents[4]


@router.get("/about/readme")
async def about_readme(request: Request):
    """Render the project README as styled HTML."""
    from genesis.web.markdown_render import render_markdown_file

    templates = get_templates(request)
    context = {
        "request": request,
        "active_tab": "about",
        "doc_title": "Project Genesis — README",
        "doc_html": render_markdown_file(_PROJECT_ROOT / "README.md"),
        "doc_source": "README.md",
    }
    return respond(request, templates, "document.html", context)


@router.get("/about/constitution")
async def about_constitution(request: Request):
    """Render the Genesis Constitution as styled HTML."""
    from genesis.web.markdown_render import render_markdown_file

    templates = get_templates(request)
    context = {
        "request": request,
        "active_tab": "about",
        "doc_title": "Genesis Trust Constitution",
        "doc_html": render_markdown_file(_PROJECT_ROOT / "TRUST_CONSTITUTION.md"),
        "doc_source": "TRUST_CONSTITUTION.md",
    }
    return respond(request, templates, "document.html", context)


@router.get("/about/story")
async def about_story(
    request: Request,
    step: int = Query(1),
):
    templates = get_templates(request)
    context = _build_story_context(request, step)
    return respond(request, templates, "about_story.html", context)


@router.get("/about/story/{track_id}")
async def about_story_track(
    track_id: str,
    scene: int = Query(1),
):
    """Backward-compat redirect: /about/story/why?scene=2 → /about/story?step=2."""
    global_step = _story_step_for_track_scene(track_id, scene)
    return RedirectResponse(f"/about/story?step={global_step}", status_code=307)


@router.get("/members")
async def members_dashboard(request: Request):
    service = get_service()
    templates = get_templates(request)
    current_user = _current_user_from_templates(templates)
    actor_id = str(current_user.get("actor_id", "")).strip() or "demo-human-1"
    if service.get_actor(actor_id) is None:
        actor_id = "demo-human-1"
    try:
        member = build_member_dashboard(
            service,
            actor_id=actor_id,
            display_name=current_user.get("display_name"),
        )
    except ValueError:
        if wants_json(request):
            return JSONResponse({"error": f"Member not found: {actor_id}"}, status_code=404)
        return templates.TemplateResponse(
            "errors/404.html", {"request": request}, status_code=404,
        )

    current_user_view = dict(current_user)
    current_user_view["actor_id"] = actor_id
    current_user_view["display_name"] = member["display_name"]
    current_user_view["trust_score"] = member["trust_score"]
    current_user_view["open_bids"] = member["active_bids"]
    context = {
        "request": request,
        "active_tab": "members",
        "member": member,
        "current_user": current_user_view,
    }
    return respond(request, templates, "members.html", context)


@router.get("/feed")
async def feed_page(
    page: int = Query(1, ge=1),
):
    """PoC HTMX endpoint placeholder for infinite-feed loading."""
    if page <= 1:
        return HTMLResponse("")
    return HTMLResponse('<div class="feed-fade" style="display:block;">No further updates</div>')


@router.get("/search")
async def search_hint(
    q: str = Query(""),
):
    """PoC search endpoint to avoid dead controls while indexing is pending."""
    term = q.strip()
    if not term:
        return HTMLResponse("")
    safe_term = term.replace("<", "").replace(">", "")
    return HTMLResponse(
        f'<div class="text-sm text-muted">No matching results for "{safe_term}" yet.</div>'
    )


def _current_user_from_templates(templates) -> dict:
    user = templates.env.globals.get("current_user")
    if isinstance(user, dict):
        return dict(user)
    return {}


def _resolve_current_user(service, templates) -> tuple[dict, str, int]:
    current_user = _current_user_from_templates(templates)
    actor_id = str(current_user.get("actor_id", "")).strip() or "demo-human-1"
    actor_entry = service.get_actor(actor_id)
    if actor_entry is None:
        actor_id = "demo-human-1"
        actor_entry = service.get_actor(actor_id)

    trust_score = 0
    trust_record = service.get_trust(actor_id) if hasattr(service, "get_trust") else None
    if trust_record is not None:
        try:
            trust_score = int(round(float(getattr(trust_record, "score", 0.0)) * 1000))
        except (TypeError, ValueError):
            trust_score = 0
    elif actor_entry is not None:
        try:
            trust_score = int(round(float(getattr(actor_entry, "trust_score", 0.0)) * 1000))
        except (TypeError, ValueError):
            trust_score = 0
    else:
        try:
            trust_score = int(current_user.get("trust_score", 0) or 0)
        except (TypeError, ValueError):
            trust_score = 0

    trust_score = max(0, min(1000, trust_score))
    current_user_view = dict(current_user)
    current_user_view["actor_id"] = actor_id
    current_user_view["trust_score"] = trust_score
    return current_user_view, actor_id, trust_score


def _can_propose_amendment(service, actor_id: str, trust_score: int) -> bool:
    actor_entry = service.get_actor(actor_id)
    if actor_entry is None or not actor_entry.is_available():
        return False
    actor_kind = getattr(actor_entry, "actor_kind", None)
    actor_kind_value = str(getattr(actor_kind, "value", actor_kind)).strip().lower()
    if actor_kind_value != "human":
        return False
    return trust_score >= ASSEMBLY_PROPOSE_GATE


def _can_propose_assembly_topic(service, actor_id: str, trust_score: int) -> bool:
    actor_entry = service.get_actor(actor_id)
    if actor_entry is None or not actor_entry.is_available():
        return False
    return trust_score >= ASSEMBLY_PROPOSE_GATE


def _build_assembly_topic_cards(
    service,
    topics: list[dict],
    *,
    amendment_links: dict[str, list[dict]] | None = None,
) -> list[dict]:
    if amendment_links is None:
        amendment_links = _build_amendment_links_index(service)
    cards: list[dict] = []
    sorted_topics = sorted(
        topics,
        key=lambda item: item.get("last_activity_utc", ""),
        reverse=True,
    )
    for topic in sorted_topics:
        topic_id = str(topic.get("topic_id", "")).strip()
        if not topic_id:
            continue
        detail = service.get_assembly_topic(topic_id)
        opening_text = ""
        latest_text = ""
        latest_actor_type = "human"
        if detail.success and detail.data:
            contributions = detail.data.get("contributions", [])
            if contributions:
                opening_text = str(contributions[0].get("content", "")).strip()
                latest_text = str(contributions[-1].get("content", "")).strip()
                latest_actor_type = "machine" if contributions[-1].get("is_machine") else "human"
        linked = amendment_links.get(topic_id, [])
        cards.append(
            {
                "topic_id": topic_id,
                "title": topic.get("title", "Assembly Topic"),
                "status": topic.get("status", "active"),
                "contribution_count": int(topic.get("contribution_count", 0)),
                "created_ago": _time_ago(topic.get("created_utc")),
                "last_activity_ago": _time_ago(topic.get("last_activity_utc")),
                "opening_excerpt": _excerpt(opening_text, max_length=240),
                "latest_excerpt": _excerpt(latest_text, max_length=200),
                "latest_actor_type": latest_actor_type,
                "linked_amendment_count": len(linked),
            },
        )
    return cards


def _build_amendment_links_index(service) -> dict[str, list[dict]]:
    links: dict[str, list[dict]] = {}
    for proposal in _iter_amendment_proposals(service):
        shaped = _shape_amendment_proposal(proposal)
        source_topic_id = shaped.get("source_topic_id", "")
        if not source_topic_id:
            continue
        links.setdefault(source_topic_id, []).append(shaped)
    return links


def _list_recent_amendments(service, *, max_items: int) -> list[dict]:
    items: list[dict] = []
    for proposal in _iter_amendment_proposals(service):
        items.append(_shape_amendment_proposal(proposal))
        if len(items) >= max_items:
            break
    return items


def _iter_amendment_proposals(service) -> list:
    engine = getattr(service, "_amendment_engine", None)
    if engine is None or not hasattr(engine, "list_amendments"):
        return []
    try:
        proposals = list(engine.list_amendments())
    except Exception:
        return []

    def _created_key(item):
        created = getattr(item, "created_utc", None)
        if isinstance(created, datetime):
            return created
        return datetime.min.replace(tzinfo=timezone.utc)

    return sorted(proposals, key=_created_key, reverse=True)


def _shape_amendment_proposal(proposal) -> dict:
    status = getattr(proposal, "status", "")
    status_value = status.value if hasattr(status, "value") else str(status)
    justification = str(getattr(proposal, "justification", "")).strip()
    source_topic_id = str(getattr(proposal, "source_topic_id", "")).strip()
    if not source_topic_id:
        source_topic_id = _extract_source_topic_id(justification)
    return {
        "proposal_id": str(getattr(proposal, "proposal_id", "")).strip(),
        "provision_key": str(getattr(proposal, "provision_key", "")).strip(),
        "status": status_value,
        "status_label": status_value.replace("_", " ").title(),
        "is_entrenched": bool(getattr(proposal, "is_entrenched", False)),
        "created_ago": _time_ago(getattr(proposal, "created_utc", None)),
        "source_topic_id": source_topic_id,
        "justification_excerpt": _excerpt(
            _strip_all_source_topic_markers(justification),
            max_length=200,
        ),
    }


def _pack_amendment_justification(justification: str, source_topic_id: str) -> str:
    clean = justification.strip()
    if not source_topic_id:
        return clean
    marker = f"{AMENDMENT_SOURCE_PREFIX}{source_topic_id}]"
    if clean.startswith(marker):
        return clean
    return f"{marker}\n{clean}" if clean else marker


def _extract_source_topic_id(justification: str) -> str:
    match = AMENDMENT_SOURCE_RE.search(justification)
    if not match:
        return ""
    return match.group(1).strip()


def _strip_source_topic_marker(justification: str) -> str:
    stripped = AMENDMENT_SOURCE_RE.sub("", justification, count=1).strip()
    return stripped


def _strip_all_source_topic_markers(justification: str) -> str:
    return AMENDMENT_SOURCE_RE.sub("", justification).strip()


def _coerce_proposed_value(raw_value: str):
    text = str(raw_value or "").strip()
    if not text:
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _shape_assembly_contribution(item: dict, *, index: int) -> dict:
    is_machine = bool(item.get("is_machine"))
    actor_type = "machine" if is_machine else "human"
    return {
        "contribution_id": item.get("contribution_id", f"contrib-{index}"),
        "actor_type": actor_type,
        "label": f"{'Machine' if is_machine else 'Human'} participant {index}",
        "time_ago": _time_ago(item.get("contributed_utc")),
        "content": str(item.get("content", "")).strip(),
    }


def _time_ago(iso_value) -> str:
    if not iso_value:
        return "just now"
    try:
        dt = datetime.fromisoformat(str(iso_value))
    except (TypeError, ValueError):
        return "just now"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    seconds = max(0, int((now - dt).total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    days = seconds // 86400
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    if months < 12:
        return f"{months}mo ago"
    years = days // 365
    return f"{years}y ago"


def _excerpt(text: str, *, max_length: int = 240) -> str:
    clean = " ".join(text.split())
    if len(clean) <= max_length:
        return clean
    return clean[: max_length - 3].rstrip() + "..."


def _safe_notice_level(level: str) -> str:
    return level if level in {"info", "success", "warning"} else "info"


def _notice_redirect(path: str, notice: str, level: str, *, anchor: str = "") -> RedirectResponse:
    separator = "&" if "?" in path else "?"
    target = (
        f"{path}{separator}notice={quote_plus(notice)}"
        f"&notice_level={_safe_notice_level(level)}"
    )
    if anchor:
        target = f"{target}#{anchor}"
    return RedirectResponse(target, status_code=303)
