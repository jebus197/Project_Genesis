# Worked Examples (Executable Evidence Bundles)

This folder contains two reference bundles used to validate core Genesis controls:

1. `low_risk_mission.json` (`R0`): single-review low-risk path.
2. `high_risk_mission.json` (`R2`): quorum-review high-risk path with mandatory human final approval.

## Validation commands

Run from repository root:

```bash
python3 tools/check_invariants.py
python3 tools/verify_examples.py
```

Expected result:

1. Invariant check passes.
2. Example verification passes.

If either command fails, the policy artifacts or example bundles violate current constitutional controls and must be corrected before use.
