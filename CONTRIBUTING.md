# Contributing to Project Genesis

Status: Repository governance process  
Date: February 13, 2026  
Owner: George Jackson

## 1) Purpose

This file defines how changes are proposed, reviewed, and accepted so project governance in the repository matches project governance in the specification.

## 2) Scope of changes

All changes fall into one of three classes:

1. Constitutional changes:
- Changes to trust rules, voting rules, governance thresholds, or constitutional authority boundaries.

2. Operational changes:
- Changes to workflows, review topology, evidence schema, incident handling, or system controls.

3. Documentation changes:
- Clarifications, examples, and non-constitutional wording updates.

## 3) Required contents for every pull request

Every pull request must include:

1. Change summary in plain language.
2. Risk impact statement:
- what new risk is introduced,
- what risk is reduced,
- what remains unresolved.
3. Invariant impact statement:
- list affected invariants from `THREAT_MODEL_AND_INVARIANTS.md`.
4. Test/evidence statement:
- what was validated,
- what was not validated,
- why.
5. Validation command output:
- `python3 tools/check_invariants.py`
- `python3 tools/verify_examples.py`

## 4) Additional requirements by change class

1. Constitutional changes:
- Must update `TRUST_CONSTITUTION.md` directly.
- Must update the parameter matrix and design tests where relevant.
- Must include explicit migration/rollback logic.
- Must include calibration impact summary for affected thresholds.

2. Operational changes:
- Must update `GENESIS_SYSTEM_BLUEPRINT.md` and/or `GENESIS_ROADMAP.md` if behavior changes.
- Must include fail-closed behavior notes.
- Must update `config/runtime_policy.json` when risk-tier mapping behavior changes.

3. Documentation changes:
- Must not contradict constitutional and blueprint documents.
- Must avoid absolute claims ("bulletproof", "impossible", "guaranteed truth").

## 5) Style and claim discipline

1. Use measured language.
2. Distinguish evidence from inference.
3. Do not present mitigations as guarantees.
4. Keep human constitutional authority explicit where relevant.

## 6) Fast rejection conditions

A contribution must be rejected if it:

1. enables machine constitutional voting directly or indirectly,
2. allows trust minting without quality-gated proof-of-trust evidence,
3. weakens or bypasses quarantine/re-certification/decommission controls,
4. introduces governance changes without constitutional traceability,
5. adds hype claims not backed by enforceable controls.
