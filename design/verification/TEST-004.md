---
id: TEST-004
kind: verification
title: Executable QG-004 regression verification
status: verified
version: 1
verification_type: integration
---

# Verification

test_quality_gate.py verifies valid configuration, fail-closed missing/malformed
configuration, policy-controlled scope/flags/template, same-PR weakening protection,
and the narrowly pinned bootstrap. Run all existing regressions and generated
instruction validation alongside these cases.

```bash
python tools/traceability/validate.py --repo .
python -m unittest discover -s tools/traceability/tests -v
python tools/generate_agents.py --repo . --check
python tools/traceability/validate.py --repo . --base-ref 972774f18b879d023eb005d1af021699ed6b4ed5 --head-ref HEAD --pr-body-file examples/DEV-004-pr-body.md
```

Local environment for this batch: Python 3.14.6, PyYAML 6.0.3, jsonschema 4.25.1.
CI declares Python 3.13 and requirements-dev.txt pins PyYAML 6.0.2. This difference
is tracked explicitly in docs/phase0-policy-follow-up.md; local success is not a
claim of identical CI environment reproduction.

On 2026-09-19, canonical validation passed with 21 artifacts and a valid QG-004
configuration, all 50 tests passed, and AGENTS.md reproducibility passed. The
new malformed-template regression initially exposed acceptance of a trailing
newline; the schema was tightened and the full suite rerun successfully.
CI uses the same validation commands, with explicit QG-004 step/output labels.
