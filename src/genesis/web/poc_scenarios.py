"""PoC scenario catalogue for rich social UX examples.

Provides deterministic hypothetical mission, bidding, member, and story data
used by social templates in demonstration mode.
"""

from __future__ import annotations

from functools import lru_cache


MISSION_SEEDS: list[dict] = [
    {
        "listing_id": "demo-maternal-health",
        "title": "Maternal Health Data Consistency Review",
        "summary": "Cross-hospital anomaly review for maternal outcomes with reproducibility checks.",
        "creator_id": "city-health-network",
        "domain_tags": ["healthcare", "audit"],
        "circle_name": "Public Health Circle",
        "bridge": "Public Health x Civic QA",
        "risk_tier": "R2",
        "stage_key": "shortlisting",
        "bid_count": 7,
        "due_window": "11 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-water-grid",
        "title": "Water Grid Sensor Calibration Replay",
        "summary": "Validate calibration replay logs and isolate one unresolved outlier array.",
        "creator_id": "water-infra-squad",
        "domain_tags": ["environment", "audit"],
        "circle_name": "Water Infrastructure Circle",
        "bridge": "Water Infrastructure x Enviro Analytics",
        "risk_tier": "R1",
        "stage_key": "counter_example_review",
        "bid_count": 6,
        "due_window": "5 days",
        "stake_band": "mission band M1",
    },
    {
        "listing_id": "demo-air-quality",
        "title": "Regional Air Quality Sensor Drift Audit",
        "summary": "Review drift correction quality across four municipal sensor networks.",
        "creator_id": "civic-qa-lab",
        "domain_tags": ["environment", "transport"],
        "circle_name": "Civic QA Lab",
        "bridge": "Civic QA x Public Health",
        "risk_tier": "R2",
        "stage_key": "packet_review",
        "bid_count": 9,
        "due_window": "10 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-school-ventilation",
        "title": "School Ventilation Risk Map",
        "summary": "Cross-domain ventilation evidence review for winter compliance windows.",
        "creator_id": "education-skills-circle",
        "domain_tags": ["education", "healthcare"],
        "circle_name": "Education and Skills Circle",
        "bridge": "Education x Public Health",
        "risk_tier": "R3",
        "stage_key": "selection_pending_escrow",
        "bid_count": 8,
        "due_window": "12 days",
        "stake_band": "mission band M3",
    },
    {
        "listing_id": "demo-maternal-outcomes",
        "title": "Maternal Outcomes Anomaly Triage",
        "summary": "Adjudicate unresolved outcome records with independent peer corroboration.",
        "creator_id": "public-health-circle",
        "domain_tags": ["healthcare"],
        "circle_name": "Public Health Circle",
        "bridge": "Public Health x Governance and Justice",
        "risk_tier": "R2",
        "stage_key": "eligibility_gate",
        "bid_count": 5,
        "due_window": "9 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-pipe-forecast",
        "title": "Pipe Failure Forecast Calibration",
        "summary": "Replay preventive forecast model and annotate confidence intervals by district.",
        "creator_id": "water-ops-team",
        "domain_tags": ["environment", "audit"],
        "circle_name": "Water Infrastructure Circle",
        "bridge": "Water Infrastructure x Civic QA",
        "risk_tier": "R1",
        "stage_key": "delivery_active",
        "bid_count": 4,
        "due_window": "6 days",
        "stake_band": "mission band M1",
    },
    {
        "listing_id": "demo-procurement-replay",
        "title": "Municipal Procurement Replay Audit",
        "summary": "Distinguish collusion-like signals from seasonality artifacts in contract data.",
        "creator_id": "civic-qa-lab",
        "domain_tags": ["audit", "transport"],
        "circle_name": "Civic QA Lab",
        "bridge": "Civic QA x Governance and Justice",
        "risk_tier": "R2",
        "stage_key": "counter_example_review",
        "bid_count": 10,
        "due_window": "11 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-floodplain-retune",
        "title": "Floodplain Retune Under Snowmelt Variance",
        "summary": "Stress-test deployment assumptions for mixed snowmelt and rainfall scenarios.",
        "creator_id": "enviro-analytics-circle",
        "domain_tags": ["environment"],
        "circle_name": "Enviro Analytics Circle",
        "bridge": "Enviro Analytics x Water Infrastructure",
        "risk_tier": "R3",
        "stage_key": "shortlisting",
        "bid_count": 12,
        "due_window": "14 days",
        "stake_band": "mission band M3",
    },
    {
        "listing_id": "demo-appeals-audit",
        "title": "Appeals Fairness Audit (Q1)",
        "summary": "Evaluate appeal process consistency, response timing, and disclosure integrity.",
        "creator_id": "governance-justice-circle",
        "domain_tags": ["audit"],
        "circle_name": "Governance and Justice Circle",
        "bridge": "Governance and Justice x Assembly",
        "risk_tier": "R2",
        "stage_key": "packet_review",
        "bid_count": 6,
        "due_window": "8 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "evidence",
        "title": "Evidence Bundle Validation Sprint",
        "summary": "Rapid review lane for contested evidence packets before final shortlisting.",
        "creator_id": "trust-council-gh21",
        "domain_tags": ["audit", "healthcare"],
        "circle_name": "Cross-Domain Evidence Cell",
        "bridge": "All Domains x Governance and Justice",
        "risk_tier": "R2",
        "stage_key": "packet_review",
        "bid_count": 11,
        "due_window": "3 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-triage-escalation",
        "title": "Triage Escalation Threshold Review",
        "summary": "Compare 48-hour vs 72-hour escalation policy outcomes in real caseload data.",
        "creator_id": "public-health-circle",
        "domain_tags": ["healthcare"],
        "circle_name": "Public Health Circle",
        "bridge": "Public Health x Assembly",
        "risk_tier": "R3",
        "stage_key": "counter_example_review",
        "bid_count": 9,
        "due_window": "13 days",
        "stake_band": "mission band M3",
    },
    {
        "listing_id": "demo-vaccine-signal",
        "title": "Vaccine Adverse Signal Corroboration",
        "summary": "Corroborate high-sensitivity adverse signal packet with regional reviewer mix.",
        "creator_id": "public-health-circle",
        "domain_tags": ["healthcare", "audit"],
        "circle_name": "Public Health Circle",
        "bridge": "Public Health x Civic QA",
        "risk_tier": "R3",
        "stage_key": "eligibility_gate",
        "bid_count": 5,
        "due_window": "7 days",
        "stake_band": "mission band M3",
    },
    {
        "listing_id": "demo-hospital-drift",
        "title": "Hospital Data Schema Drift Audit",
        "summary": "Detect schema drift and harmonize anomaly semantics across hospitals.",
        "creator_id": "clinical-qc-coalition",
        "domain_tags": ["healthcare", "audit"],
        "circle_name": "Public Health Circle",
        "bridge": "Public Health x Data Governance",
        "risk_tier": "R2",
        "stage_key": "selection_pending_escrow",
        "bid_count": 6,
        "due_window": "10 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-service-delivery-audit",
        "title": "Service Delivery Quality Floor Check",
        "summary": "Validate municipality service floor metrics against mission acceptance claims.",
        "creator_id": "civic-qa-lab",
        "domain_tags": ["audit", "transport"],
        "circle_name": "Civic QA Lab",
        "bridge": "Civic QA x Assembly",
        "risk_tier": "R2",
        "stage_key": "shortlisting",
        "bid_count": 8,
        "due_window": "9 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-transit-incident-replay",
        "title": "Transit Incident Replay and Root-Cause Trace",
        "summary": "Replay incident logs and classify unresolved causality claims with evidence links.",
        "creator_id": "transit-safety-cell",
        "domain_tags": ["transport", "audit"],
        "circle_name": "Civic QA Lab",
        "bridge": "Civic QA x Governance and Justice",
        "risk_tier": "R3",
        "stage_key": "counter_example_review",
        "bid_count": 7,
        "due_window": "6 days",
        "stake_band": "mission band M3",
    },
    {
        "listing_id": "demo-reservoir-risk",
        "title": "Reservoir Risk Scenario Validation",
        "summary": "Validate reservoir stress assumptions under multi-model drought projections.",
        "creator_id": "water-infra-squad",
        "domain_tags": ["environment"],
        "circle_name": "Water Infrastructure Circle",
        "bridge": "Water Infrastructure x Enviro Analytics",
        "risk_tier": "R3",
        "stage_key": "packet_review",
        "bid_count": 8,
        "due_window": "15 days",
        "stake_band": "mission band M3",
    },
    {
        "listing_id": "demo-treatment-compliance",
        "title": "Treatment Compliance Outlier Adjudication",
        "summary": "Resolve contested treatment compliance outliers with replay-backed evidence.",
        "creator_id": "water-compliance-team",
        "domain_tags": ["environment", "audit"],
        "circle_name": "Water Infrastructure Circle",
        "bridge": "Water Infrastructure x Governance and Justice",
        "risk_tier": "R2",
        "stage_key": "delivery_active",
        "bid_count": 4,
        "due_window": "7 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-carbon-accounting",
        "title": "Carbon Accounting Method Audit",
        "summary": "Audit carbon estimate methodology and challenge unsupported disclosure claims.",
        "creator_id": "enviro-analytics-circle",
        "domain_tags": ["environment", "audit"],
        "circle_name": "Enviro Analytics Circle",
        "bridge": "Enviro Analytics x Assembly",
        "risk_tier": "R2",
        "stage_key": "selection_pending_escrow",
        "bid_count": 7,
        "due_window": "12 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-heatwave-response",
        "title": "Heatwave Response Trigger Validation",
        "summary": "Test response trigger thresholds against retrospective heatwave evidence.",
        "creator_id": "enviro-analytics-circle",
        "domain_tags": ["environment", "healthcare"],
        "circle_name": "Enviro Analytics Circle",
        "bridge": "Enviro Analytics x Public Health",
        "risk_tier": "R3",
        "stage_key": "shortlisting",
        "bid_count": 9,
        "due_window": "10 days",
        "stake_band": "mission band M3",
    },
    {
        "listing_id": "demo-biodiversity-anomaly",
        "title": "Biodiversity Anomaly Trace Review",
        "summary": "Corroborate habitat signal anomalies across mixed sensing and survey data.",
        "creator_id": "enviro-analytics-circle",
        "domain_tags": ["environment"],
        "circle_name": "Enviro Analytics Circle",
        "bridge": "Enviro Analytics x Civic QA",
        "risk_tier": "R2",
        "stage_key": "packet_review",
        "bid_count": 5,
        "due_window": "13 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-literacy-outcomes",
        "title": "Literacy Outcomes Corroboration",
        "summary": "Validate literacy intervention claims using controlled cohort evidence.",
        "creator_id": "education-skills-circle",
        "domain_tags": ["education", "audit"],
        "circle_name": "Education and Skills Circle",
        "bridge": "Education x Civic QA",
        "risk_tier": "R2",
        "stage_key": "eligibility_gate",
        "bid_count": 6,
        "due_window": "9 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-vocational-placement",
        "title": "Vocational Placement Quality Audit",
        "summary": "Check placement quality durability and verify long-tail outcomes.",
        "creator_id": "education-skills-circle",
        "domain_tags": ["education"],
        "circle_name": "Education and Skills Circle",
        "bridge": "Education x Governance and Justice",
        "risk_tier": "R2",
        "stage_key": "counter_example_review",
        "bid_count": 7,
        "due_window": "11 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-student-support-equity",
        "title": "Student Support Equity Verification",
        "summary": "Audit support allocation fairness and identify underserved cohorts.",
        "creator_id": "education-equity-panel",
        "domain_tags": ["education", "audit"],
        "circle_name": "Education and Skills Circle",
        "bridge": "Education x Public Health",
        "risk_tier": "R2",
        "stage_key": "selection_pending_escrow",
        "bid_count": 8,
        "due_window": "14 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-resource-allocation-audit",
        "title": "Classroom Resource Allocation Audit",
        "summary": "Validate classroom resource distribution against policy commitments.",
        "creator_id": "education-skills-circle",
        "domain_tags": ["education", "audit"],
        "circle_name": "Education and Skills Circle",
        "bridge": "Education x Assembly",
        "risk_tier": "R1",
        "stage_key": "delivery_active",
        "bid_count": 3,
        "due_window": "8 days",
        "stake_band": "mission band M1",
    },
    {
        "listing_id": "demo-domain-vetting",
        "title": "Domain Expert Conflict Vetting",
        "summary": "Review conflict-of-interest declarations for expert pool nominations.",
        "creator_id": "governance-justice-circle",
        "domain_tags": ["audit"],
        "circle_name": "Governance and Justice Circle",
        "bridge": "Governance and Justice x Assembly",
        "risk_tier": "R2",
        "stage_key": "packet_review",
        "bid_count": 4,
        "due_window": "5 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-ratification-readiness",
        "title": "Ratification Readiness Proof Pack",
        "summary": "Compile and verify proof pack before multi-chamber ratification vote.",
        "creator_id": "assembly-speaker",
        "domain_tags": ["audit", "education"],
        "circle_name": "Assembly Circle",
        "bridge": "Assembly x Governance and Justice",
        "risk_tier": "R3",
        "stage_key": "shortlisting",
        "bid_count": 9,
        "due_window": "4 days",
        "stake_band": "mission band M3",
    },
    {
        "listing_id": "demo-compliance-adjudication",
        "title": "Compliance Adjudication Case Review",
        "summary": "Independent adjudication review for contested compliance outcomes.",
        "creator_id": "legal-compliance-quorum",
        "domain_tags": ["audit", "healthcare"],
        "circle_name": "Governance and Justice Circle",
        "bridge": "Governance and Justice x Public Health",
        "risk_tier": "R3",
        "stage_key": "counter_example_review",
        "bid_count": 6,
        "due_window": "6 days",
        "stake_band": "mission band M3",
    },
    {
        "listing_id": "demo-trust-appeals-latency",
        "title": "Trust Appeals Latency Reduction Design",
        "summary": "Model process changes to reduce appeals queue latency without fairness loss.",
        "creator_id": "governance-justice-circle",
        "domain_tags": ["audit", "transport"],
        "circle_name": "Governance and Justice Circle",
        "bridge": "Governance and Justice x Civic QA",
        "risk_tier": "R2",
        "stage_key": "selection_pending_escrow",
        "bid_count": 5,
        "due_window": "10 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-reviewer-diversity",
        "title": "Reviewer Diversity Floor Impact Study",
        "summary": "Quantify correlated error reduction from 3-organization reviewer minimum.",
        "creator_id": "assembly-speaker",
        "domain_tags": ["audit", "environment"],
        "circle_name": "Assembly Circle",
        "bridge": "Assembly x All Operational Circles",
        "risk_tier": "R2",
        "stage_key": "delivery_active",
        "bid_count": 7,
        "due_window": "9 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-anchor-cadence",
        "title": "Anchor Cadence Stress Simulation",
        "summary": "Simulate 30-minute anchoring under dispute-heavy operational conditions.",
        "creator_id": "trust-protocol-lab",
        "domain_tags": ["audit", "environment"],
        "circle_name": "Assembly Circle",
        "bridge": "Assembly x Audit Circle",
        "risk_tier": "R2",
        "stage_key": "packet_review",
        "bid_count": 6,
        "due_window": "7 days",
        "stake_band": "mission band M2",
    },
    {
        "listing_id": "demo-machine-recert-lane",
        "title": "Machine Recertification Lane Design",
        "summary": "Design supervised re-entry lane for repeated machine verification failures.",
        "creator_id": "governance-justice-circle",
        "domain_tags": ["audit", "education"],
        "circle_name": "Governance and Justice Circle",
        "bridge": "Governance and Justice x Assembly",
        "risk_tier": "R3",
        "stage_key": "shortlisting",
        "bid_count": 8,
        "due_window": "8 days",
        "stake_band": "mission band M3",
    },
]


BIDDER_POOL: list[dict] = [
    {"actor_name": "Rina K.", "actor_id": "rina-k", "actor_type": "human", "org": "City Health Network"},
    {"actor_name": "Hydra-A7", "actor_id": "hydra-a7", "actor_type": "machine", "org": "Registered by Omar P."},
    {"actor_name": "Alex M.", "actor_id": "alex-m", "actor_type": "human", "org": "Civic QA Lab"},
    {"actor_name": "Hydra-B3", "actor_id": "hydra-b3", "actor_type": "machine", "org": "Registered by Lian T."},
    {"actor_name": "Jamie Liu", "actor_id": "jamie-liu", "actor_type": "human", "org": "Enviro Analytics Circle"},
    {"actor_name": "M. Cole", "actor_id": "m-cole", "actor_type": "human", "org": "Facilitator Pool"},
    {"actor_name": "Aster-4", "actor_id": "aster-4", "actor_type": "machine", "org": "Registered by S. Vora"},
    {"actor_name": "Nadia P.", "actor_id": "nadia-p", "actor_type": "human", "org": "Assembly Evidence Desk"},
]


STAGE_ORDER = [
    "eligibility_gate",
    "packet_review",
    "shortlisting",
    "counter_example_review",
    "selection_pending_escrow",
    "delivery_active",
]


STAGE_LABELS = {
    "eligibility_gate": "Eligibility Gate",
    "packet_review": "Bid Proposal Review",
    "shortlisting": "Shortlisting",
    "counter_example_review": "Counter-Example Review",
    "selection_pending_escrow": "Selection Pending Escrow Lock",
    "delivery_active": "Delivery and Review Active",
}

DOMAIN_DOSSIER_LIBRARY = {
    "healthcare": {
        "evidence_inputs": [
            "Hospital event records and triage logs",
            "Anonymized outcome summaries with audit references",
            "Clinical threshold documentation",
        ],
        "scope_out": [
            "No direct clinical intervention recommendations",
            "No patient-level identity resolution",
        ],
        "risks": [
            "False confidence from incomplete records",
            "Delayed escalation for vulnerable cohorts",
        ],
        "safeguards": [
            "Independent replay by mixed reviewer pool",
            "Mandatory human sign-off for high-impact changes",
        ],
        "human_stakes": "Patient safety, escalation speed, and equitable treatment quality.",
        "decision_focus": "whether the current clinical logic can remain active or must be retuned",
    },
    "environment": {
        "evidence_inputs": [
            "Sensor telemetry and calibration history",
            "Historical event windows for replay",
            "Model assumptions and boundary conditions",
        ],
        "scope_out": [
            "No irreversible infrastructure decisions in this lane",
            "No suppression of unresolved anomaly traces",
        ],
        "risks": [
            "Model drift hidden by averaged outputs",
            "Seasonality artifacts misread as structural change",
        ],
        "safeguards": [
            "Counter-example replay requirement for edge cases",
            "Cross-domain corroboration before settlement",
        ],
        "human_stakes": "Infrastructure resilience, service continuity, and public safety under stress events.",
        "decision_focus": "whether risk models are reliable enough for operational planning",
    },
    "education": {
        "evidence_inputs": [
            "Programme outcome datasets",
            "Support allocation records and policy baselines",
            "Longitudinal cohort quality checks",
        ],
        "scope_out": [
            "No unilateral policy ratification from this mission",
            "No exclusion of low-volume cohorts from analysis",
        ],
        "risks": [
            "Short-term gains masking long-term regression",
            "Support inequity hidden by aggregate averages",
        ],
        "safeguards": [
            "Cohort-level fairness checks before closure",
            "Plain-language evidence summary for public review",
        ],
        "human_stakes": "Learner outcomes, fairness of support access, and long-term opportunity.",
        "decision_focus": "whether outcomes are real, durable, and equitably distributed",
    },
    "transport": {
        "evidence_inputs": [
            "Incident and routing logs",
            "Operational timing and reliability records",
            "Safety escalation traces",
        ],
        "scope_out": [
            "No live-operations routing override in this lane",
            "No closure while unresolved severe incidents remain",
        ],
        "risks": [
            "False negatives in safety incident classification",
            "Bias toward high-volume routes only",
        ],
        "safeguards": [
            "Independent incident replay before closeout",
            "Escalation triggers bound to confidence thresholds",
        ],
        "human_stakes": "Commute reliability, incident response quality, and network safety.",
        "decision_focus": "whether routing and incident controls are reducing risk without hidden regressions",
    },
    "audit": {
        "evidence_inputs": [
            "Audit trail records and event hashes",
            "Evidence packet references and replay outputs",
            "Conflict-of-interest disclosures",
        ],
        "scope_out": [
            "No hidden decision paths or private settlement rules",
            "No bypass of independence checks",
        ],
        "risks": [
            "Procedural drift between stated and actual flow",
            "Unchallenged assumptions in high-speed review lanes",
        ],
        "safeguards": [
            "Deterministic workflow checkpoints",
            "Challenge window before final selection where required",
        ],
        "human_stakes": "Public trust in decisions, fairness of process, and verifiable accountability.",
        "decision_focus": "whether evidence quality is strong enough for a defensible closeout",
    },
}

RISK_QUORUM_RULE = {
    "R1": "1 independent reviewer before settlement",
    "R2": "2 independent reviewers before settlement",
    "R3": "2 human plus 1 machine reviewer, with human sign-off",
}

RISK_CAPACITY = {"R1": 8, "R2": 10, "R3": 12}

STAGE_PRESSURE = {
    "eligibility_gate": "High screening pressure",
    "packet_review": "Evidence quality pressure",
    "shortlisting": "Selection pressure",
    "counter_example_review": "Challenge pressure",
    "selection_pending_escrow": "Commitment pressure",
    "delivery_active": "Execution pressure",
}

LIFECYCLE_LABELS = {
    "active_operations": "Current Community Missions",
    "org_submitted": "Domain Org Proposals",
    "ratification_queue": "Ratification Queue",
    "ratified_in_force": "Ratified and In Force",
    "validated_archive": "Validated Outcomes",
}

LIFECYCLE_DESCRIPTIONS = {
    "active_operations": "Missions currently being executed and reviewed by the Genesis community.",
    "org_submitted": "Significant proposals submitted by domain expert organisations and under initial checks.",
    "ratification_queue": "Decisions requiring chamber-level ratification before platform-wide rollout.",
    "ratified_in_force": "Decisions that passed ratification and are now live in operational policy lanes.",
    "validated_archive": "Completed missions with validated outcomes and auditable closure records.",
}

EDITORIAL_LEDE_OVERRIDES = {
    "demo-maternal-health": "Three hospital trusts flagged conflicting maternal-outcome records this week, and frontline teams need one coherent evidence position before the next escalation window.",
    "demo-water-grid": "Water operators narrowed instability to one outlier array, but they still need an independent replay before changing calibration in production.",
    "demo-air-quality": "Regional air-quality alerts are drifting apart between municipalities, creating public confusion and inconsistent local responses.",
    "demo-triage-escalation": "Clinical teams are split on 48h versus 72h escalation thresholds, with real consequences for waiting-time safety.",
    "demo-domain-vetting": "A high-impact expert pool is ready for activation, but conflict declarations must be cleared first to avoid trust damage later.",
    "demo-ratification-readiness": "A constitutional amendment package is approaching chamber vote, and one weak proof segment could stall ratification.",
    "demo-machine-recert-lane": "Repeated machine verification failures exposed a policy gap, and operators are waiting for a safe recertification lane.",
}

MISSION_STORY_PARAGRAPH_OVERRIDES = {
    "demo-maternal-health": [
        "Midwives across three hospitals are logging similar complications in different ways, and families are receiving different explanations for comparable cases.",
        "This mission brings records teams and frontline clinicians into one review room to reconcile the trail, challenge weak assumptions, and publish one shared maternal-outcome standard.",
        "If this lands well, escalation decisions become more consistent, clinicians recover time for care, and families get clearer answers at critical moments.",
        "If we miss this window, uneven triage will continue and avoidable risk remains on patients. Apply if you can handle sensitive health evidence with care and plain-language clarity.",
    ],
    "demo-water-grid": [
        "One outlier sensor array is producing readings that conflict with nearby stations, and local crews are unsure whether they are seeing drift or a real warning.",
        "Contributors will replay calibration history, compare seasonal patterns, and identify the point where signal quality diverged from reliable baselines.",
        "Success means utility teams can issue one clear advisory path instead of mixed local responses, and residents can trust what they are told.",
        "If unresolved, warning fatigue grows and confidence in public alerts drops. Apply if you can connect environmental evidence to practical operations decisions.",
    ],
    "demo-air-quality": [
        "Neighbouring municipalities are posting different air-quality guidance for the same weather window, leaving families and schools unsure which advice is safe to follow.",
        "This mission will reconcile correction methods across the sensor network, test competing interpretations, and produce one evidence-backed guidance line for local responders.",
        "A good outcome gives communities clearer risk communication, helps services intervene earlier, and reduces false alarms without hiding real hazards.",
        "If we fail here, confusion persists and vulnerable groups absorb the cost. Apply if you can turn contested environmental data into decisions ordinary people can use.",
    ],
    "demo-school-ventilation": [
        "Schools in the same district are using different ventilation thresholds, so pupils and staff are seeing uneven protection in similar winter conditions.",
        "The mission team will review building data, attendance patterns, and health signals to agree one practical risk map that schools can implement quickly.",
        "Success means classroom decisions stop depending on guesswork and support teams can target high-risk sites before conditions worsen.",
        "If this stalls, inequity in school safety remains baked in. Apply if you can bridge education operations and public-health evidence without losing human context.",
    ],
    "demo-maternal-outcomes": [
        "Several high-risk maternity cases were escalated on different timelines despite near-identical indicators, raising concern among staff and families.",
        "This mission reviews those edge cases end to end, tests whether current trigger logic is fair, and proposes one defensible path for future triage.",
        "If done properly, clinicians gain a clearer escalation rule and families gain confidence that comparable situations are treated comparably.",
        "If not, inconsistency becomes normalised in a high-stakes setting. Apply if you can handle difficult case evidence and communicate decisions responsibly.",
    ],
    "demo-pipe-forecast": [
        "Maintenance teams are receiving conflicting pipe-failure forecasts, and crews cannot tell which warnings justify immediate intervention.",
        "Contributors will replay model assumptions against real outage history and identify where confidence bands are overstated or underpowered.",
        "Success means fewer surprise failures, smarter maintenance windows, and better continuity for households and businesses.",
        "If this misses, avoidable breaks and emergency repairs remain the default pattern. Apply if you can pair infrastructure judgment with evidence discipline.",
    ],
    "demo-procurement-replay": [
        "Procurement anomalies are being interpreted as misconduct in some reviews and as normal seasonality in others, creating reputational and legal risk.",
        "This mission replays contract data with independent challenge to separate true concern signals from predictable purchasing noise.",
        "A strong result protects fair suppliers, sharpens enforcement where needed, and gives the public a clearer account of how decisions were made.",
        "If we leave it vague, both trust and due process suffer. Apply if you can work carefully at the boundary of audit evidence and public accountability.",
    ],
    "demo-floodplain-retune": [
        "Recent snowmelt patterns exposed gaps between flood predictions and what local responders saw on the ground.",
        "The mission will stress-test current assumptions with mixed rain-and-snow scenarios and recalibrate thresholds for practical emergency planning.",
        "Success gives communities earlier, more reliable warning windows and helps responders allocate resources before peak pressure hits.",
        "If unresolved, false confidence in flood models becomes a real safety risk. Apply if you can combine climate evidence with operational realism.",
    ],
    "demo-appeals-audit": [
        "People filing similar appeals are getting decisions at very different speeds, and trust in fairness is starting to fracture.",
        "This mission traces appeal pathways quarter-wide, identifies avoidable bottlenecks, and tests where process design is producing inconsistent outcomes.",
        "When successful, outcomes become more predictable, timelines more transparent, and reviewers can explain decisions without defensive language.",
        "If we miss, the perception of arbitrary justice hardens. Apply if you can analyse procedural evidence and still keep the human stakes in view.",
    ],
    "evidence": [
        "A surge of contested evidence packets is slowing mission decisions across multiple domains, and teams are waiting for trusted validation.",
        "This sprint creates a rapid verification lane: check provenance, replay key claims, and flag weak submissions before they contaminate live decisions.",
        "Success keeps high-quality missions moving while preserving challenge rights for strong dissenting evidence.",
        "If this backlog grows, good missions stall and weak claims gain airtime. Apply if you can review quickly without compromising judgment.",
    ],
    "demo-triage-escalation": [
        "Frontline teams remain split on whether to escalate high-risk cases at 48 or 72 hours, and that gap is affecting patient safety decisions.",
        "Contributors will compare real outcomes under both thresholds and produce a recommendation that clinicians can apply under pressure.",
        "A good outcome reduces avoidable delay and gives teams a clear escalation anchor they can defend publicly.",
        "If unresolved, time-critical decisions keep drifting by unit rather than by evidence. Apply if you can reason clearly where minutes matter.",
    ],
    "demo-vaccine-signal": [
        "A sensitive adverse-event signal is being interpreted differently across regions, creating avoidable public anxiety and uneven response.",
        "This mission corroborates the signal with independent reviewers, checks methodological drift, and clarifies what can and cannot be inferred.",
        "Success protects safety vigilance without amplifying noise, and helps clinicians and communities act on the same facts.",
        "If we miss this, both overreaction and underreaction become more likely. Apply if you can work with high-sensitivity evidence responsibly.",
    ],
    "demo-hospital-drift": [
        "Hospital systems are labelling equivalent fields differently, so shared analytics are producing conflicting conclusions.",
        "The mission aligns schema logic, validates transformation rules, and documents where interpretation must remain explicit rather than assumed.",
        "When successful, cross-site quality reviews become comparable and clinical teams stop arguing over formatting artefacts.",
        "If unresolved, decision quality keeps leaking through technical inconsistency. Apply if you can bridge data governance and frontline impact.",
    ],
    "demo-service-delivery-audit": [
        "Service quality claims in municipal reports are not consistently matching resident-facing outcomes.",
        "This mission checks the stated quality floor against operational records and identifies where policy commitments are drifting in practice.",
        "Success gives councils a credible correction path and communities a clearer view of what is improving and what is not.",
        "If left vague, trust erodes even where good work exists. Apply if you can test claims rigorously and communicate findings without jargon.",
    ],
    "demo-transit-incident-replay": [
        "Recent transit incidents share similar signatures but are being closed under different root-cause labels.",
        "Contributors will replay event logs, map decision points, and separate genuine causality from convenient post-hoc narratives.",
        "A strong result improves incident prevention, clarifies accountability, and helps control rooms respond with less hesitation.",
        "If this stays unresolved, preventable failures repeat under new names. Apply if you can trace complex incidents into plain operational lessons.",
    ],
    "demo-reservoir-risk": [
        "Reservoir planning assumptions are being challenged by new drought patterns, and operators need a clearer risk baseline before the next season.",
        "This mission tests stress scenarios against historical extremes and current constraints to identify where present safeguards are too thin.",
        "Success supports earlier mitigation choices and more transparent public communication around water security.",
        "If we miss, tail-risk exposure remains hidden until it is expensive to fix. Apply if you can reason carefully under uncertainty.",
    ],
    "demo-treatment-compliance": [
        "Compliance outliers are being dismissed by some reviewers and escalated by others, creating uneven enforcement pressure.",
        "The mission will adjudicate disputed cases with replay-backed evidence and produce one defensible interpretation path.",
        "When successful, enforcement becomes fairer, more predictable, and easier to explain to affected teams.",
        "If unresolved, both false positives and missed violations will keep undermining confidence. Apply if you can make hard calls with balanced judgment.",
    ],
    "demo-carbon-accounting": [
        "Carbon reporting methods currently differ across contributors, making headline claims difficult to compare or trust.",
        "This mission audits the underlying method choices, checks evidence quality, and clarifies which claims are robust enough for disclosure.",
        "Success improves transparency for the public and gives organisations a clearer route to credible reporting.",
        "If this remains loose, performative numbers will crowd out serious work. Apply if you can challenge methods without defaulting to cynicism.",
    ],
    "demo-heatwave-response": [
        "Heatwave triggers are being activated at different thresholds across districts, causing uneven protection for similar risk conditions.",
        "Contributors will test trigger performance against retrospective outcomes and propose one practical threshold policy for coordinated response.",
        "A good outcome means earlier support where needed and fewer unnecessary service disruptions elsewhere.",
        "If unresolved, vulnerable groups will continue to face postcode-dependent protection. Apply if you can balance caution, evidence, and operational feasibility.",
    ],
    "demo-biodiversity-anomaly": [
        "Habitat anomaly reports are rising, but teams disagree on whether the pattern reflects ecosystem change or measurement noise.",
        "This mission aligns sensing and survey evidence to determine which anomalies are actionable and which require further observation.",
        "Success improves conservation prioritisation and avoids reactive interventions based on weak signals.",
        "If we miss, scarce ecological resources are misdirected while genuine risks grow. Apply if you can combine ecological context with data rigor.",
    ],
    "demo-literacy-outcomes": [
        "Literacy improvement claims are strong on paper but inconsistent across learner groups, and educators are asking what is genuinely transferable.",
        "The mission will test intervention evidence across cohorts and identify which elements drive durable gains versus short-term artefacts.",
        "Success gives schools clearer guidance on what to scale and what to redesign before another term is lost.",
        "If unresolved, effort continues but outcomes stay uneven. Apply if you can evaluate education evidence with both empathy and precision.",
    ],
    "demo-vocational-placement": [
        "Placement numbers look healthy at first glance, yet durability after six months varies sharply across programmes.",
        "Contributors will audit placement quality, retention evidence, and support pathways to distinguish true success from short-lived placements.",
        "A strong outcome helps learners choose better pathways and helps providers improve support where drop-off risk is highest.",
        "If left unclear, headline metrics will keep masking fragile outcomes. Apply if you can surface the long-term picture behind short-term wins.",
    ],
    "demo-student-support-equity": [
        "Support services are reaching many students, but similar needs are still receiving uneven responses between institutions.",
        "This mission maps allocation patterns, tests fairness assumptions, and proposes adjustments that protect high-need learners first.",
        "Success means support decisions become more transparent and more consistent for students and families.",
        "If unresolved, structural inequity keeps reproducing itself quietly each cycle. Apply if you can combine fairness analysis with practical implementation sense.",
    ],
    "demo-resource-allocation-audit": [
        "Classroom resource commitments and actual delivery are drifting apart in ways staff can feel but cannot yet evidence clearly.",
        "Contributors will reconcile allocation records with local delivery logs and identify where commitments are being diluted in practice.",
        "Success gives school leaders and communities one honest map of what arrived, where, and with what effect.",
        "If we miss, confidence in allocation fairness keeps weakening. Apply if you can track operational detail without losing the bigger human picture.",
    ],
    "demo-domain-vetting": [
        "A new expert pool is ready to start, but conflict-of-interest declarations are incomplete and confidence could unravel later if ignored now.",
        "This mission verifies disclosures, checks organisational overlap risk, and sets a clean eligibility baseline before appointments are finalised.",
        "A good outcome protects both legitimacy and speed: qualified experts can start quickly under trusted guardrails.",
        "If rushed badly, future decisions may be challenged on process before substance. Apply if you can handle sensitive governance checks with discretion.",
    ],
    "demo-ratification-readiness": [
        "A high-impact amendment package is nearing chamber vote, but several proof links remain too fragile for confident ratification.",
        "Contributors will harden the evidence pack, close weak references, and present a clear rationale that each chamber can interrogate fairly.",
        "Success means ratification debates focus on substance, not avoidable documentation gaps.",
        "If this slips, reform momentum stalls and trust in the ratification process drops. Apply if you can produce high-stakes evidence writing under deadline.",
    ],
    "demo-compliance-adjudication": [
        "Contested compliance cases are producing mixed outcomes for similar fact patterns, increasing legal and operational uncertainty.",
        "This mission re-evaluates representative cases with independent adjudication and sets a clearer standard for future rulings.",
        "A strong result improves fairness for affected parties and reduces avoidable appeal churn.",
        "If unresolved, confidence in compliance decisions will continue to erode. Apply if you can weigh evidence carefully without overreach.",
    ],
    "demo-trust-appeals-latency": [
        "Appeals are being filed faster than they are closed, and delay itself is becoming a fairness issue for contributors awaiting decisions.",
        "Contributors will model queue changes, test policy options, and identify which interventions cut delay without weakening review quality.",
        "Success gives users quicker, clearer outcomes and frees reviewers to focus on genuinely complex cases.",
        "If this drifts, backlog pressure will keep distorting trust outcomes. Apply if you can design for speed and fairness at the same time.",
    ],
    "demo-reviewer-diversity": [
        "Reviewer composition has narrowed in several high-impact lanes, increasing correlated error risk even when intentions are good.",
        "This mission tests diversity floor proposals against historical outcomes and measures whether broader reviewer mix improves decision quality.",
        "If successful, review quality improves in ways both experts and newcomers can see in the evidence trail.",
        "If ignored, avoidable blind spots will persist across mission cycles. Apply if you can evaluate quality outcomes without reducing people to quotas.",
    ],
    "demo-anchor-cadence": [
        "Audit anchors are currently posted on a cadence that may be too slow for peak activity windows and too expensive for quiet periods.",
        "Contributors will simulate alternative cadences, stress test integrity guarantees, and identify the practical sweet spot for reliability and cost.",
        "Success keeps audit visibility strong while protecting resources for mission work that directly affects communities.",
        "If unresolved, either transparency or efficiency takes the hit. Apply if you can balance infrastructure pragmatism with accountability needs.",
    ],
    "demo-machine-recert-lane": [
        "Several machine contributors have fallen into repeated verification failure loops, and operators need a safe route back to trusted participation.",
        "This mission designs a recertification lane with clear thresholds, supervised checkpoints, and transparent conditions for reactivation.",
        "A good outcome protects public safety while still giving high-value machine contributors a fair path to return.",
        "If we miss this, unsafe behaviour risk rises or capable contributors remain sidelined unnecessarily. Apply if you can design safeguards that are strict and humane.",
    ],
}


@lru_cache(maxsize=1)
def mission_catalog() -> tuple[dict, ...]:
    """Mission catalogue with 30 concrete hypothetical examples."""
    missions: list[dict] = []
    for idx, seed in enumerate(MISSION_SEEDS):
        mission = dict(seed)
        mission["state"] = _state_from_stage(seed["stage_key"])
        mission["state_label"] = STAGE_LABELS[seed["stage_key"]]
        mission["why_reason"] = (
            "Ordered by transparent composite fit (trust 40%, skill 35%, domain relevance 25%), "
            "then passed through independence and conflict checks. No popularity ranking."
        )
        mission["next_gate"] = _next_gate(seed["stage_key"])
        mission["application_capacity"] = _application_capacity(seed["risk_tier"], seed["stage_key"])
        mission["intake_open"] = seed["stage_key"] != "delivery_active"
        mission["requires_human_review"] = _requires_human_review(seed["risk_tier"], seed["domain_tags"])
        lifecycle_key = _classify_lifecycle_key(mission)
        mission["lifecycle_key"] = lifecycle_key
        mission["lifecycle_label"] = LIFECYCLE_LABELS[lifecycle_key]
        mission["lifecycle_description"] = LIFECYCLE_DESCRIPTIONS[lifecycle_key]
        mission["mandate"] = _build_mandate_snapshot(mission, lifecycle_key)
        mission["story"] = _build_editorial_story(mission, lifecycle_key)
        mission["bid_packets"] = _build_bid_packets(idx, seed["risk_tier"], seed["stage_key"])
        mission["bid_workflow"] = _build_bid_workflow(seed["stage_key"], seed["risk_tier"])
        mission["dossier"] = _build_mission_dossier(mission)
        missions.append(mission)
    return tuple(missions)


def mission_catalog_list() -> list[dict]:
    """List copy for template safety."""
    return [dict(item) for item in mission_catalog()]


def mission_by_id(listing_id: str) -> dict | None:
    """Get one hypothetical mission by id."""
    for mission in mission_catalog():
        if mission["listing_id"] == listing_id:
            return dict(mission)
    return None


def related_missions(circle_name: str, listing_id: str, limit: int = 4) -> list[dict]:
    """Related missions by circle or bridge overlap."""
    matches: list[dict] = []
    for mission in mission_catalog():
        if mission["listing_id"] == listing_id:
            continue
        if mission["circle_name"] == circle_name or circle_name.split(" ")[0] in mission["bridge"]:
            matches.append({
                "listing_id": mission["listing_id"],
                "title": mission["title"],
                "circle_name": mission["circle_name"],
                "state_label": mission["state_label"],
            })
        if len(matches) >= limit:
            break
    return matches


def members_snapshot() -> dict:
    """Hypothetical member dashboard data.

    Uses allocation percentages and policy channels, not personal currency values.
    """
    missions = list(mission_catalog())
    bid_rows = []
    for mission in missions[:12]:
        bid_rows.append({
            "mission_id": mission["listing_id"],
            "mission_title": mission["title"],
            "circle_name": mission["circle_name"],
            "bid_status": mission["state_label"],
            "next_gate": mission["next_gate"],
        })

    completed_rows = []
    for mission in missions[12:20]:
        completed_rows.append({
            "mission_title": mission["title"],
            "circle_name": mission["circle_name"],
            "completion_note": "Independent review complete, settlement released, audit anchor recorded.",
            "evidence_ref": f"proof-{mission['listing_id'][:12]}",
        })

    trust_history = [
        {"period": "2025-06", "score": 702, "reason": "Completed first cross-domain QA mission."},
        {"period": "2025-08", "score": 741, "reason": "Corroborated replay evidence in two R2 missions."},
        {"period": "2025-10", "score": 776, "reason": "Mentored newcomer reviewers in low-risk lane."},
        {"period": "2025-12", "score": 811, "reason": "Completed three adjudication reviews with zero reversals."},
        {"period": "2026-01", "score": 832, "reason": "Passed independent conflict-of-interest review."},
        {"period": "2026-02", "score": 847, "reason": "Cross-domain mission outcomes remained within quality thresholds."},
    ]

    gcf_allocation = [
        {"channel": "Legal Compliance Quorums", "share": 26, "purpose": "Blind quorum legal review for edge-case mission screening."},
        {"channel": "Appeals and Adjudication", "share": 18, "purpose": "Appeal panel operations and fairness safeguards."},
        {"channel": "Audit Anchoring", "share": 16, "purpose": "Merkle commitment publication and chain anchoring operations."},
        {"channel": "Accessibility Support", "share": 14, "purpose": "Facilitated verification pathways and accommodation support."},
        {"channel": "Safety Research Missions", "share": 13, "purpose": "High-impact public-benefit mission underwriting."},
        {"channel": "Protocol Reliability Reserve", "share": 13, "purpose": "Resilience reserve for operational continuity."},
    ]

    reward_flow = [
        {"channel": "Mission settlements", "share": 61, "note": "Released from escrow only after independent review pass."},
        {"channel": "Evidence review stipends", "share": 21, "note": "Credited for corroborated reviews and replay validation."},
        {"channel": "Facilitation lane work", "share": 11, "note": "Newcomer support and plain-language review assistance."},
        {"channel": "Governance evidence grants", "share": 7, "note": "Assembly evidence packets tied to constitutional proposals."},
    ]

    return {
        "member_id": "demo-human-1",
        "display_name": "Demo User",
        "trust_score": 847,
        "missions_completed": len(completed_rows),
        "active_bids": len([row for row in bid_rows if "Delivery" not in row["bid_status"]]),
        "bid_rows": bid_rows,
        "completed_rows": completed_rows,
        "trust_history": trust_history,
        "reward_flow": reward_flow,
        "gcf_allocation": gcf_allocation,
        "gcf_epoch": "2026-Q1",
        "gcf_allocation_index": 100,
    }


def _state_from_stage(stage_key: str) -> str:
    mapping = {
        "eligibility_gate": "OPEN",
        "packet_review": "OPEN",
        "shortlisting": "IN_REVIEW",
        "counter_example_review": "IN_REVIEW",
        "selection_pending_escrow": "PENDING_SELECTION",
        "delivery_active": "ACTIVE",
    }
    return mapping.get(stage_key, "OPEN")


def _next_gate(stage_key: str) -> str:
    gate = {
        "eligibility_gate": "Bid proposal integrity check",
        "packet_review": "Composite scoring + conflict screening",
        "shortlisting": "Independent counter-example challenge window",
        "counter_example_review": "Final selection and escrow lock",
        "selection_pending_escrow": "Escrow confirmation then work allocation",
        "delivery_active": "Independent completion review and settlement",
    }
    return gate.get(stage_key, "Independent review")


def _classify_lifecycle_key(mission: dict) -> str:
    stage_key = str(mission.get("stage_key", "packet_review"))
    circle = str(mission.get("circle_name", "")).lower()
    bridge = str(mission.get("bridge", "")).lower()
    governance_lane = "assembly" in circle or "governance" in circle or "assembly" in bridge or "governance" in bridge

    if stage_key == "delivery_active":
        if governance_lane:
            return "ratified_in_force"
        return "active_operations"
    if governance_lane and stage_key in {"shortlisting", "counter_example_review", "selection_pending_escrow"}:
        return "ratification_queue"
    if stage_key in {"eligibility_gate", "packet_review"}:
        return "org_submitted"
    if stage_key == "selection_pending_escrow":
        return "ratified_in_force"
    return "active_operations"


def _build_mandate_snapshot(mission: dict, lifecycle_key: str) -> dict:
    risk_tier = str(mission.get("risk_tier", "R2")).upper()
    stage_label = STAGE_LABELS.get(mission.get("stage_key", "packet_review"), "Bid Proposal Review")
    bridge = mission.get("bridge", "Cross-domain lane")

    requires_chamber = lifecycle_key in {"ratification_queue", "ratified_in_force"}
    if lifecycle_key == "org_submitted":
        status = "Submitted by domain expert orgs"
    elif lifecycle_key == "ratification_queue":
        status = "In chamber ratification flow"
    elif lifecycle_key == "ratified_in_force":
        status = "Ratified and operational"
    elif lifecycle_key == "active_operations":
        status = "Community execution in progress"
    else:
        status = "Validated and archived"

    return {
        "status": status,
        "stage": stage_label,
        "bridge_lane": bridge,
        "requires_chamber": requires_chamber,
        "ratification_note": (
            "Requires formal chamber ratification before policy lock."
            if requires_chamber and lifecycle_key == "ratification_queue"
            else "Ratification complete; operating under current constitutional mandate."
            if requires_chamber and lifecycle_key == "ratified_in_force"
            else "Domain-org mandate path; chamber ratification not required at this stage."
        ),
        "org_submission_note": (
            f"Risk tier {risk_tier} mission submitted through {mission.get('circle_name', 'domain lane')}."
        ),
    }


def _build_editorial_story(mission: dict, lifecycle_key: str) -> dict:
    title = mission.get("title", "Mission")
    listing_id = mission.get("listing_id", "")
    stage_key = mission.get("stage_key", "packet_review")
    stage_label = STAGE_LABELS.get(stage_key, "review")
    due_window = mission.get("due_window", "the current review window")
    primary_domain = _normalize_domain_tag(mission.get("domain_tags", ["audit"])[0])
    primary_pack = DOMAIN_DOSSIER_LIBRARY.get(primary_domain, DOMAIN_DOSSIER_LIBRARY["audit"])
    story_override = MISSION_STORY_PARAGRAPH_OVERRIDES.get(listing_id)

    lede = _story_lede(story_override) if story_override else EDITORIAL_LEDE_OVERRIDES.get(listing_id)
    if not lede:
        if stage_key in {"eligibility_gate", "packet_review"}:
            lede = (
                f"{title} has entered first-pass review, and teams have {due_window} "
                "to test whether the opening evidence can carry this mission forward."
            )
        elif stage_key in {"shortlisting", "counter_example_review"}:
            lede = (
                f"{title} is now in challenge review, where competing explanations are tested "
                "side by side before any final selection is made."
            )
        elif stage_key == "selection_pending_escrow":
            lede = (
                f"{title} has a provisional lead team, but confirmation still depends on final checks "
                "and escrow readiness."
            )
        else:
            lede = (
                f"{title} is in active delivery, with progress visible to independent reviewers "
                "before closure can be signed."
            )

    domain_focus = ", ".join(_domain_label(_normalize_domain_tag(tag)) for tag in mission.get("domain_tags", [])) or "General"
    apply_reason = {
        "ratification_queue": (
            "Clear evidence writing and strong rebuttals can still change the final ratification outcome."
        ),
        "ratified_in_force": (
            "This is where policy meets reality; careful implementation and verification now matter most."
        ),
        "org_submitted": (
            "Early high-quality analysis can shape scope, protect quality, and prevent weak mandates from hardening."
        ),
        "validated_archive": (
            "Reviewing closed missions helps strengthen future methods and prevents repeated mistakes."
        ),
    }.get(
        lifecycle_key,
        "Solid execution and reproducible checks are needed now to keep outcomes trustworthy.",
    )

    return {
        "lede": lede,
        "human_frame": (
            f"{primary_pack['human_stakes']} This cycle, the key call is {primary_pack['decision_focus']}."
        ),
        "governance_frame": (
            f"Mandate status: {mission.get('mandate', {}).get('status', stage_label)}. "
            f"Bridge lane: {mission.get('bridge', 'Cross-domain lane')}."
        ),
        "apply_reason": apply_reason,
        "domain_focus": domain_focus,
    }


def _build_mission_dossier(mission: dict) -> dict:
    primary = _normalize_domain_tag(mission.get("domain_tags", ["audit"])[0])
    secondary = ""
    if len(mission.get("domain_tags", [])) > 1:
        secondary = _normalize_domain_tag(mission["domain_tags"][1])
    primary_pack = DOMAIN_DOSSIER_LIBRARY.get(primary, DOMAIN_DOSSIER_LIBRARY["audit"])
    secondary_pack = DOMAIN_DOSSIER_LIBRARY.get(secondary) if secondary else None
    topic = _mission_topic(mission)
    stage_key = mission.get("stage_key", "packet_review")
    stage_label = mission.get("state_label", STAGE_LABELS.get(stage_key, "Bid Proposal Review"))

    due_window = mission.get("due_window", "the current review window")
    primary_frame = _human_domain_frame(primary)
    secondary_frame = _human_domain_frame(secondary) if secondary else None

    objective = (
        f"Within {due_window}, publish one clear decision brief on {topic} that people on the ground can use, "
        "and that independent reviewers can verify without private context."
    )
    if secondary:
        objective = (
            f"Within {due_window}, produce a joint decision brief for {mission['title']} so "
            f"{_domain_label(primary)} and {_domain_label(secondary)} teams can act on the same evidence standard."
        )

    what_happening_now = (
        f"{mission['summary']} In the latest review cycle, teams reported evidence that still pulls in different directions "
        f"across {mission['circle_name']}."
    )
    if secondary:
        what_happening_now += (
            f" The main disagreement now sits between {_domain_label(primary)} and {_domain_label(secondary)} interpretations."
        )

    why_it_matters = (
        f"This work affects {primary_frame['people']}. If this remains unresolved, {primary_frame['harm']} "
        "and confidence in public decisions will keep dropping."
    )

    mission_actions = [
        "Establish one shared baseline from all credible evidence already submitted.",
        "Test competing explanations side by side, including counter-examples from independent reviewers.",
        "Publish a plain-language decision brief that operators and community members can act on immediately.",
    ]
    if secondary:
        mission_actions.append(
            f"Resolve cross-domain disagreements so {_domain_label(primary)} and {_domain_label(secondary)} teams leave with one common operating picture."
        )

    success_outcomes = list(primary_frame["success_outcomes"])
    success_outcomes.append(
        "A reviewer who did not work on the mission can follow the chain of reasoning and reproduce the conclusion."
    )
    if secondary_frame:
        success_outcomes.append(
            f"Joint handover from {_domain_label(primary)} to {_domain_label(secondary)} teams happens without contradictory guidance."
        )

    who_should_apply = _who_should_apply_text(primary, secondary, mission.get("risk_tier", "R2"))

    plan_paragraph = (
        f"Over the next {due_window}, contributors will review the full evidence record together, "
        "test the strongest competing explanations under independent challenge, and draft one decision brief "
        "that frontline teams can apply without ambiguity."
    )
    if secondary:
        plan_paragraph += (
            f" A core goal is to bring {_domain_label(primary)} and {_domain_label(secondary)} reviewers "
            "to one shared operating picture."
        )

    success_paragraph = (
        "If this mission lands well, guidance becomes clearer for the people affected, service teams can act "
        "earlier with fewer avoidable errors, and an independent reviewer can retrace the final conclusion "
        "from evidence to decision without insider context."
    )
    if secondary_frame:
        success_paragraph += (
            f" It should also allow clean handover between {_domain_label(primary)} and {_domain_label(secondary)} teams."
        )

    story_paragraphs = [
        f"{what_happening_now} {why_it_matters}",
        plan_paragraph,
        success_paragraph,
        primary_frame["risk_if_miss"],
        who_should_apply,
    ]
    story_override = MISSION_STORY_PARAGRAPH_OVERRIDES.get(mission.get("listing_id", ""))
    if story_override:
        story_paragraphs = list(story_override)

    scope_in = [
        f"Test the core mission claim stated in the brief: {mission['summary']}",
        f"Run independent replay against { _domain_label(primary) } source evidence.",
        "Escalate unresolved high-severity conflicts before final sign-off.",
    ]
    if secondary:
        scope_in.append(
            f"Reconcile disagreements between { _domain_label(primary) } and { _domain_label(secondary) } findings."
        )

    scope_out = list(primary_pack["scope_out"])
    if secondary_pack:
        scope_out.extend(secondary_pack["scope_out"][:1])

    deliverables = [
        "A concise methods note explaining what was tested, how, and why.",
        "A decision brief linking each key claim to a verifiable evidence reference.",
        f"A recommendation for next action, aligned to {mission['risk_tier']} safeguards.",
    ]
    if mission.get("stage_key") in {"shortlisting", "counter_example_review"}:
        deliverables.append("A challenge-response note covering every material counter-example.")

    acceptance = [
        f"Reviewer quorum met: {RISK_QUORUM_RULE.get(mission['risk_tier'], RISK_QUORUM_RULE['R2'])}.",
        "Independent replay reaches the same core conclusion.",
        "No unresolved severe contradiction remains at closeout.",
    ]

    evidence_inputs = list(primary_pack["evidence_inputs"])
    if secondary_pack:
        evidence_inputs.extend(secondary_pack["evidence_inputs"][:2])

    risks = list(primary_pack["risks"])
    if secondary_pack:
        risks.extend(secondary_pack["risks"][:1])
    if mission.get("risk_tier") == "R3":
        risks.append("High-impact decision risk if reviewer diversity is insufficient.")

    safeguards = list(primary_pack["safeguards"])
    if secondary_pack:
        safeguards.extend(secondary_pack["safeguards"][:1])
    safeguards.append(
        f"Intake policy: { 'open' if mission.get('intake_open') else 'owner-closed' } with capacity cap."
    )

    timeline = [
        {"label": "Scoping", "window": "24h"},
        {"label": "Replay and evidence synthesis", "window": "2-5 days"},
        {"label": "Independent review", "window": "1-3 days"},
        {"label": "Settlement and audit linkage", "window": mission.get("due_window", "TBD")},
    ]

    dependencies = [
        f"Bridge lane dependency: {mission.get('bridge', 'Cross-domain lane')}.",
        f"Current stage completion required: {mission.get('state_label', 'Bid Proposal Review')}.",
    ]

    intake_policy = {
        "owner_mode": "Open intake" if mission.get("intake_open") else "Owner-closed intake",
        "capacity": mission.get("application_capacity", RISK_CAPACITY.get(mission.get("risk_tier", "R2"), 10)),
        "human_review_required": bool(mission.get("requires_human_review")),
        "note": (
            "Applications are accepted until capacity is met; additional applicants are held in reserve queue."
            if mission.get("intake_open")
            else "Owner has paused intake to control review load and compute spend."
        ),
    }

    brief_constraints = [
        f"Deadline: {mission.get('due_window', 'TBD')}.",
        f"Risk tier: {mission.get('risk_tier', 'R2')} ({RISK_QUORUM_RULE.get(mission.get('risk_tier', 'R2'), RISK_QUORUM_RULE['R2'])}).",
        f"Intake capacity: {intake_policy['capacity']} applicants ({'open' if mission.get('intake_open') else 'owner-closed'}).",
    ]
    if mission.get("requires_human_review"):
        brief_constraints.append("Human review required before activation.")

    brief = {
        "problem_signal": _problem_signal_for_topic(topic, mission),
        "decision_required": (
            f"Before this window closes, decide whether {topic} can move beyond {stage_label.lower()} "
            "or whether the current approach must be revised."
        ),
        "human_impact": primary_pack["human_stakes"],
        "success_definition": (
            "A reviewer unfamiliar with this mission can reproduce the process, reach the same finding, "
            "and defend the final decision in plain language."
        ),
        "constraints": brief_constraints,
    }

    return {
        "context": (
            f"{mission['summary']} The immediate task is to move from competing interpretations to one defensible decision "
            f"that protects people and can be explained openly. Coordination runs through {mission['bridge']}."
        ),
        "human_description": {
            "whats_happening_now": what_happening_now,
            "why_it_matters": why_it_matters,
            "what_we_will_do": mission_actions,
            "success_looks_like": success_outcomes,
            "if_we_miss": primary_frame["risk_if_miss"],
            "who_should_apply": who_should_apply,
            "story_paragraphs": story_paragraphs,
        },
        "brief": brief,
        "objective": objective,
        "scope_in": scope_in,
        "scope_out": scope_out,
        "deliverables": deliverables,
        "acceptance_criteria": acceptance,
        "evidence_inputs": evidence_inputs,
        "risk_watchpoints": risks,
        "safeguards": safeguards,
        "dependencies": dependencies,
        "timeline": timeline,
        "intake_policy": intake_policy,
    }


def _application_capacity(risk_tier: str, stage_key: str) -> int:
    base = RISK_CAPACITY.get(risk_tier, 10)
    if stage_key == "delivery_active":
        return max(3, base - 5)
    if stage_key in {"shortlisting", "counter_example_review"}:
        return max(4, base - 2)
    return base


def _requires_human_review(risk_tier: str, domain_tags: list[str]) -> bool:
    if risk_tier == "R3":
        return True
    sensitive = {"healthcare", "governance", "justice"}
    return any(_normalize_domain_tag(tag) in sensitive for tag in domain_tags)


def _normalize_domain_tag(domain: str) -> str:
    return str(domain).strip().lower().replace("_", "-")


def _domain_label(domain: str) -> str:
    return domain.replace("-", " ").title()


def _story_lede(paragraphs: list[str] | None) -> str | None:
    if not paragraphs:
        return None
    first = str(paragraphs[0]).strip()
    if not first:
        return None
    if "." in first:
        head = first.split(".", 1)[0].strip()
        if head:
            return f"{head}."
    return first


def _human_domain_frame(domain: str) -> dict:
    frames = {
        "healthcare": {
            "people": "patients, carers, and frontline clinical teams",
            "harm": "care teams lose time, triage quality drops, and vulnerable patients carry the risk",
            "success_outcomes": [
                "Clinical teams receive one consistent decision baseline they can trust across sites.",
                "Families get clearer explanations for care pathways and escalation choices.",
            ],
            "risk_if_miss": (
                "If this mission stalls, inconsistent decisions will continue between comparable cases, "
                "placing pressure on frontline staff and increasing avoidable harm."
            ),
        },
        "education": {
            "people": "students, families, educators, and local support staff",
            "harm": "support is allocated unevenly and the learners who need help most are missed",
            "success_outcomes": [
                "Schools and support teams can apply one fair, evidence-backed standard.",
                "Families can understand why decisions were made and what happens next.",
            ],
            "risk_if_miss": (
                "If we miss this cycle, uneven support patterns will harden and trust in school-level decisions will erode."
            ),
        },
        "transport": {
            "people": "commuters, incident responders, and network operations teams",
            "harm": "safety responses diverge, delays increase, and preventable disruptions spread",
            "success_outcomes": [
                "Control rooms and responders can act on one validated incident picture.",
                "Passengers receive more predictable service and clearer safety communication.",
            ],
            "risk_if_miss": (
                "If unresolved, conflicting operational rules will continue to increase incident risk and reliability failures."
            ),
        },
        "environment": {
            "people": "households, public-health teams, and local infrastructure operators",
            "harm": "communities face unclear risk signals and delayed protective action",
            "success_outcomes": [
                "Communities and services receive clearer, more consistent risk guidance.",
                "Operators can intervene earlier with fewer false alarms and fewer missed hazards.",
            ],
            "risk_if_miss": (
                "If this remains unresolved, warning quality will stay inconsistent and communities will absorb avoidable exposure."
            ),
        },
        "audit": {
            "people": "community members, reviewers, and teams accountable for outcomes",
            "harm": "decisions become harder to trust because evidence quality is uneven",
            "success_outcomes": [
                "Key decisions can be traced end-to-end without private interpretation.",
                "Independent reviewers can challenge and confirm outcomes quickly.",
            ],
            "risk_if_miss": (
                "If audit quality remains weak, low-confidence decisions will continue to pass as settled outcomes."
            ),
        },
    }
    return frames.get(
        domain,
        {
            "people": "community members and frontline service teams",
            "harm": "decisions drift apart and confidence in outcomes drops",
            "success_outcomes": [
                "Teams can work from one transparent decision baseline.",
                "People affected by decisions can understand the rationale in plain language.",
            ],
            "risk_if_miss": (
                "If this mission is delayed, inconsistent decisions will persist and corrective action will cost more later."
            ),
        },
    )


def _who_should_apply_text(primary: str, secondary: str, risk_tier: str) -> str:
    primary_label = _domain_label(primary) if primary else "relevant domain"
    if secondary:
        combined = f"{primary_label} + {_domain_label(secondary)}"
    else:
        combined = primary_label

    risk_note = {
        "R1": "This lane is suitable for contributors building mission experience under clear guardrails.",
        "R2": "This lane needs contributors who can manage contested evidence and explain trade-offs clearly.",
        "R3": "This lane needs highly trusted contributors who stay calm under scrutiny and can defend decisions publicly.",
    }.get(str(risk_tier).upper(), "This lane needs contributors with strong evidence discipline.")

    return (
        f"Apply if you can turn complex evidence into clear operational choices for {combined} teams. "
        f"{risk_note}"
    )


def _mission_topic(mission: dict) -> str:
    listing_id = mission.get("listing_id", "")
    title = str(mission.get("title", "")).strip()
    overrides = {
        "demo-maternal-health": "maternal outcome consistency checks",
        "demo-water-grid": "water grid calibration reliability",
        "demo-air-quality": "air-quality drift correction decisions",
        "demo-school-ventilation": "school ventilation risk controls",
        "demo-maternal-outcomes": "maternal triage anomaly adjudication",
        "demo-pipe-forecast": "pipe-failure forecast calibration",
        "demo-procurement-replay": "procurement anomaly replay quality",
        "demo-floodplain-retune": "floodplain stress-model retuning",
        "demo-appeals-audit": "appeals process fairness consistency",
        "evidence": "contested evidence packet validation",
        "demo-triage-escalation": "triage escalation threshold policy",
        "demo-vaccine-signal": "vaccine adverse-signal corroboration",
        "demo-hospital-drift": "hospital schema-drift harmonisation",
        "demo-service-delivery-audit": "service-floor quality verification",
        "demo-transit-incident-replay": "transit incident root-cause replay",
        "demo-reservoir-risk": "reservoir stress-scenario assumptions",
        "demo-treatment-compliance": "treatment compliance outlier decisions",
        "demo-carbon-accounting": "carbon accounting method validity",
        "demo-heatwave-response": "heatwave trigger decision thresholds",
        "demo-biodiversity-anomaly": "biodiversity anomaly attribution",
        "demo-literacy-outcomes": "literacy outcome claim corroboration",
        "demo-vocational-placement": "vocational placement durability",
        "demo-student-support-equity": "student support allocation fairness",
        "demo-resource-allocation-audit": "classroom resource distribution fidelity",
        "demo-domain-vetting": "domain expert conflict screening",
        "demo-ratification-readiness": "ratification packet readiness",
        "demo-compliance-adjudication": "compliance adjudication consistency",
        "demo-trust-appeals-latency": "trust appeals latency reduction",
        "demo-reviewer-diversity": "reviewer diversity floor impact",
        "demo-anchor-cadence": "anchor cadence stress tolerance",
        "demo-machine-recert-lane": "machine recertification safety lane",
    }
    if listing_id in overrides:
        return overrides[listing_id]
    return title.lower() if title else "mission outcome integrity"


def _problem_signal_for_topic(topic: str, mission: dict) -> str:
    title = str(mission.get("title", "")).lower()
    if "drift" in title:
        return "Field signals are drifting apart across sources, and teams no longer trust a single correction path."
    if "triage" in title:
        return "Similar cases are landing in different escalation paths, and frontline teams need one consistent rule."
    if "replay" in title or "retune" in title:
        return "Replay results are still unstable under challenge, so no one can sign off with confidence yet."
    if "audit" in title:
        return "What the process claims and what the records show are still not fully aligned."
    if "risk" in title or "stress" in title:
        return "Current assumptions may underestimate worst-case exposure in real operating conditions."
    if "equity" in title or "fairness" in title:
        return "Outcomes look uneven across similar cohorts, and the current explanation is incomplete."
    if "appeal" in title:
        return "Comparable appeals are closing at different speeds and with uneven consistency."
    return f"Evidence on {topic} is still too fragmented for a confident closeout."


def _build_bid_packets(index: int, risk_tier: str, stage_key: str) -> list[dict]:
    bids: list[dict] = []
    for offset in range(4):
        bidder = BIDDER_POOL[(index + offset) % len(BIDDER_POOL)]
        trust_points = 25 + ((index * 3 + offset * 4) % 16)
        skill_points = 19 + ((index * 5 + offset * 3) % 17)
        domain_points = 14 + ((index * 7 + offset * 2) % 12)
        composite = trust_points + skill_points + domain_points
        status = _bid_status_for_offset(offset, stage_key)
        bids.append({
            "actor_name": bidder["actor_name"],
            "actor_id": bidder["actor_id"],
            "actor_type": bidder["actor_type"],
            "org": bidder["org"],
            "trust_points": trust_points,
            "skill_points": skill_points,
            "domain_points": domain_points,
            "composite_score": composite,
            "packet_ref": f"pkt-{index + 1:02d}-{offset + 1}",
            "independence_check": _independence_note(risk_tier, offset),
            "status": status,
        })
    return bids


def _build_bid_workflow(stage_key: str, risk_tier: str) -> list[dict]:
    risk_note = {
        "R1": "Single independent reviewer required before selection.",
        "R2": "Two independent reviewers required before selection.",
        "R3": "Two human + one machine replay reviewer required; human sign-off mandatory.",
    }[risk_tier]

    steps = [
        {
            "key": "eligibility_gate",
            "title": "Eligibility Gate",
            "detail": "Domain clearance, trust floor, and conflict-of-interest checks.",
        },
        {
            "key": "packet_review",
            "title": "Bid Proposal Review",
            "detail": "Bid proposal must include methods, evidence plan, and replay commitments.",
        },
        {
            "key": "shortlisting",
            "title": "Composite Shortlisting",
            "detail": "Transparent scoring: trust 40%, skill 35%, domain relevance 25%.",
        },
        {
            "key": "counter_example_review",
            "title": "Counter-Example Window",
            "detail": "Shortlisted packets can be challenged by independent counter-example evidence.",
        },
        {
            "key": "selection_pending_escrow",
            "title": "Selection + Escrow Lock",
            "detail": "Selected bidder is provisional until escrow and policy checks are confirmed.",
        },
        {
            "key": "delivery_active",
            "title": "Delivery, Review, and Settlement",
            "detail": f"Work executes under audit. {risk_note}",
        },
    ]

    stage_index = STAGE_ORDER.index(stage_key)
    for idx, step in enumerate(steps):
        if idx < stage_index:
            step["status"] = "complete"
        elif idx == stage_index:
            step["status"] = "active"
        else:
            step["status"] = "pending"
    return steps


def _bid_status_for_offset(offset: int, stage_key: str) -> str:
    if stage_key in {"selection_pending_escrow", "delivery_active"}:
        return ["selected", "shortlisted", "reserve", "not-selected"][offset]
    if stage_key in {"counter_example_review", "shortlisting"}:
        return ["shortlisted", "shortlisted", "under-challenge", "reserve"][offset]
    if stage_key in {"packet_review", "eligibility_gate"}:
        return ["packet-review", "eligibility-check", "packet-review", "eligibility-check"][offset]
    return "packet-review"


def _independence_note(risk_tier: str, offset: int) -> str:
    if risk_tier == "R3":
        notes = [
            "Pending 2 human + 1 machine replay corroboration.",
            "Human verifier pool assigned; replay pending.",
            "Counter-example window open for 24h.",
            "Reserve lane; can activate on challenge success.",
        ]
        return notes[offset]
    if risk_tier == "R2":
        notes = [
            "Two independent reviewers assigned.",
            "Conflict screen passed.",
            "Replay reproducibility packet requested.",
            "Reserve lane for alternate method diversity.",
        ]
        return notes[offset]
    notes = [
        "Single independent reviewer assigned.",
        "Conflict screen passed.",
        "Proposal ready for fast-lane replay.",
        "Reserve lane only.",
    ]
    return notes[offset]
