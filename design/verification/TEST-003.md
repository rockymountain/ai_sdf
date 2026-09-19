---
id: TEST-003
kind: verification
title: Git diff provenance regression verification
status: verified
version: 1
verification_type: integration
---

# Verification

tools/traceability/tests/test_change_provenance.py uses real temporary Git histories
to check full coverage, uncovered files, collective task coverage, base-governed
exempt/generated paths, sensitive-path T2 ownership, and per-task evidence.
It also checks documentation-only PRs, attempted self-exemptions, and rename/deletion
evidence. The complete suite retains DEV-001 and DEV-002 regression coverage.

```bash
python tools/traceability/validate.py --repo .
python -m unittest discover -s tools/traceability/tests -v
python tools/generate_agents.py --repo . --check
python tools/traceability/validate.py --repo . --base-ref f8eed188f7826e565fe66fce7081d882027a8428 --head-ref HEAD --pr-body-file examples/DEV-003-pr-body.md
```

# Local results

On 2026-09-19, canonical validation passed with 17 artifacts, the complete suite
passed all 37 tests, and AGENTS.md reproducibility passed. Validation ran on Python
3.14.6 with the pinned PyYAML 6.0.2 and jsonschema 4.25.1 dependencies. CI remains
configured for Python 3.13. The last command exercises the actual DEV-003 commit
against the clean merged main baseline; temporary Git tests do not replace it.
