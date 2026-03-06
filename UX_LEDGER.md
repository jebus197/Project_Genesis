# UX Ledger

Last updated: 2026-03-04

## Decisions Implemented
- Home: removed `Compose` from the front page.
- Missions: added `Compose` at the top of the mission workflow area.
- Home: promoted the core hook to a dedicated hero section above all feed cards.
- Header: replaced wide always-on search input with a compact clickable `Search` control.
- UX cleanup: removed mechanics-explainer callouts from front-facing sections and kept mechanics in About/FAQ/docs.
- Members: switched dashboard from static PoC snapshot to backend-derived service shaping.
- Members: replaced misleading empty-state `100%` fallback percentages with explicit `N/A` zero-flow states.
- Members: aligned Mission Ledger section labels with the same blue pill/chip style used elsewhere.
- Assembly: replaced static scaffold cards with backend-driven Assembly topic listing.
- Assembly: added real proposal creation and response submission routes with trust-gated controls.
- Assembly: replaced dead `Add evidence` placeholders with routed `Open proposal` / `Respond` actions.
- Assembly: added dedicated topic detail view rendering opening statement and contribution stream.
- Assembly: added explicit `NON-BINDING` markers and a visible `How decisions happen` flow in-page.
- Assembly: added trust-gated `Propose Amendment` path links from Assembly topics to binding-workflow explainer.
- Assembly: added binding markers in assembly JSON payloads (`binding`, `decision_mode`) for UI/API clarity.
- Assembly: wired real amendment submission (`POST /assembly/amendments`) into backend `propose_amendment` flow.
- Assembly: linked amendment proposals to source Assembly topics and surfaced linked cards in topic/detail views.
- Governance walkthrough: expanded with panel-composition and domain-expertise section (in-app path page + standalone walkthrough artifact).
- Assembly: replaced small dropdown-only proposal entry with a full-width proposal composer card on `/assembly`.
- Assembly: added lightweight writing controls (`Bold`, `Italic`, `List`, `Quote`, `Link`) for assembly proposal, response, and amendment forms.
- Assembly: added minimum-length validation for topic titles/opening statements to block low-signal one-line proposal spam.
- Assembly: seeded realistic multi-topic Assembly PoC content so the section remains substantive after server restart.
- Assembly: restored dropdown compose paradigm with a larger high-readability proposal panel instead of always-open compose.
- Assembly: rewrote Assembly PoC topic/reply prose to plain-language, human-first tone with broader narrative variation.
- PoC lifecycle: app startup now reads runtime `poc_mode.active`; demo seeding only runs in PoC and only on empty state.
- Assembly p-pass: trust-gate source of truth corrected to backend trust records (template trust values no longer control route authorization).
- Assembly p-pass: added falsification tests for forged trust scenarios (form and template spoof attempts).
- Assembly p-pass: amendment proposal controls now require backend-eligible actor state (human + ACTIVE + trust gate) for UI and POST route behavior.

## Work To Be Completed
- Assembly: implement chamber lifecycle operational views (open chamber, cast vote, close chamber, challenge, confirmation) on top of existing backend AmendmentEngine routes.
- Assembly: add moderation-status indicators once assembly compliance queue state is exposed in the read API.
- Assembly: expand proposal card depth with optional policy-domain tags when service payload includes them.
- Assembly: evaluate full rich-text editor only after PoC UX falsification; keep current lightweight markdown controls unless user testing proves insufficient.
- Storyboard pack: create external click-through storyboard deck for outreach and onboarding (human-first), separate from in-product navigation.
- Demo profile artifact: create one clearly synthetic `Demonstration profile (PoC only)` graphic and mark for deletion before First Light.
- Guided onboarding placement: evaluate `About -> Getting Started` for human walkthrough integration after UX falsification pass.
- Machine onboarding: draft a non-executable machine integration spec first; defer executable onboarding scripts until post-falsification stabilization.
- Search: add a dedicated full search page with filter chips and recent queries.
- Feed controls: add a feed density toggle (`Compact` / `Standard`) for UX review and production tuning.
- Mobile clarity: add stronger visual distinction between story categories at a glance on mobile.
- Front-page status rail: add an optional concise `Front Page Briefing` strip for epoch/First Light/governance state.
- Accessibility pass: complete keyboard, contrast, and reduced-motion coverage.
- Content rhythm: add anti-clustering rules so very similar story types do not stack together.
- Label consistency: standardize action labels (`Open story`, `Open mission`, `Audit trace`) across all sections.

## Deferred Integration (Until Post-UX Falsification)
- Do not wire storyboard/deck into production navigation yet.
- Do not add machine auto-integration scripts yet.
- Do not lock onboarding IA (information architecture) until assembly/circles/missions passes are complete.

## Protocol Note
- All incomplete UX items remain in `Work To Be Completed` until implemented and falsification-tested.
