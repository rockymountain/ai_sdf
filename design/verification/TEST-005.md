---
id: TEST-005
kind: verification
title: Fresh isolated validation environment verification
status: verified
version: 1
verification_type: integration
---

# Verification

From a fresh .venv created by the interpreter selected in .python-version, install
requirements-dev.txt with pip --isolated and --only-binary=:all:. Run pip check and
tools/check_environment.py to verify Python, isolation, all pinned package versions,
and imports. Then run canonical validation, the complete suite, and AGENTS.md check.
test_environment.py covers missing/malformed declarations, mismatched actual versions,
global environment rejection, and shared CI runtime/dependency consumption.

Real evidence command (Windows interpreter shown):

```powershell
.\.venv\Scripts\python.exe tools/traceability/validate.py --repo . --base-ref 01243aaeb454e798427087cbca6d5ca12e222a2a --head-ref HEAD --pr-body-file examples/DEV-005-pr-body.md
```

Historical TEST-001 through TEST-004 are retained exactly as recorded.

# Results

Attempt 1 succeeded on 2026-09-19 in a fresh Windows venv with
include-system-site-packages=false. Python 3.14.6 installed wheels for PyYAML 6.0.3,
jsonschema 4.25.1, attrs 26.1.0, jsonschema-specifications 2025.9.1,
referencing 0.37.0, and rpds-py 2026.6.3. Bootstrap pip was 26.1.2.
pip check reported no broken requirements; package versions and imports matched
the isolated environment. Canonical validation passed with 25 artifacts, QG-004
passed, all 57 tests passed, and AGENTS.md reproduced exactly. The CI configuration
regression confirms shared version/dependency declarations; remote CI execution
is separate from this local evidence.

The real Git/PR command above validates the committed DEV-005 change against the
merged DEV-004 baseline. Attempt transcript: sdf-dev005-attempt-1-01243aa.log in
the local temporary directory; repository evidence and commands remain portable.
