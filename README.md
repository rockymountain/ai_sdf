# AI-Native SDF — Phase 0 Walking Skeleton

Phase 0 proves one invariant before any platform investment:

> A meaningful software change cannot merge without machine-verifiable traceability from intent to design/task, implementation evidence, and verification.

## First heartbeat

Patient Zero is `DEV-001` (T2-lite): **Add asynchronous document indexing**.

Trace chain:

`PROB-001 → FR-001 / NFR-001 → ADR-001 → CMP-001 / EVT-001 → DEV-001 → code diff + [DEV-001] commit → TEST-001`

## Local validation

Install CPython at the exact version in `.python-version` and make it available
as `python` (`python3` on POSIX). Git must also be installed for the regression
suite and PR evidence checks. Start with a fresh `.venv`; activation is optional.
Both local development and CI install the same complete pins from
`requirements-dev.txt`, including transitive validation dependencies. Wheel-only
installation avoids native compiler requirements on supported Windows setups.

PowerShell:

```powershell
python tools/check_environment.py --python-only
if ($LASTEXITCODE -ne 0) { throw 'Select the repository-declared Python first.' }
python -m venv .venv
$sdfPython = '.\.venv\Scripts\python.exe'
& $sdfPython -m pip --isolated install --only-binary=:all: -r requirements-dev.txt
& $sdfPython -m pip check
& $sdfPython tools/check_environment.py
& $sdfPython tools/traceability/validate.py --repo .
& $sdfPython -m unittest discover -s tools/traceability/tests -v
& $sdfPython tools/generate_agents.py --repo . --check
```

POSIX shell (the same interpreter paths and validation commands used by CI):

```bash
python3 tools/check_environment.py --python-only && python3 -m venv .venv
.venv/bin/python -m pip --isolated install --only-binary=:all: -r requirements-dev.txt
.venv/bin/python -m pip check
.venv/bin/python tools/check_environment.py
.venv/bin/python tools/traceability/validate.py --repo .
.venv/bin/python -m unittest discover -s tools/traceability/tests -v
.venv/bin/python tools/generate_agents.py --repo . --check
```

Stop if any command fails. The environment check reports actual Python and pinned
package versions and rejects global/system-package environments. Do not substitute
global packages if installation fails. `pip list` in the venv also exposes the
installer version bundled with the selected Python; pip is not a validator dependency.

PR/commit validation uses the same venv and the actual PR base/head refs, for example
on the DEV-005 branch (use `.venv/Scripts/python.exe` on Windows):

```bash
.venv/bin/python tools/traceability/validate.py --repo . \
  --base-ref 01243aaeb454e798427087cbca6d5ca12e222a2a --head-ref HEAD \
  --pr-body-file examples/DEV-005-pr-body.md
```

## Canonical truth

- `constitution/*.yaml`: canonical governance source.
- `design/**/*.md`: canonical design artifacts. IDs come from YAML frontmatter, never filenames or grep.
- `knowledge/traceability.yaml`: explicit many-to-many trace graph and implementation path evidence.
- `knowledge/schemas/*.schema.json`: machine contracts.
- `tools/traceability/validate.py`: deterministic enforcement.

`AGENTS.md` is a runtime projection for Codex in Phase 0, not the canonical constitution.

## Expected failures

The validator fails on:

- duplicate artifact IDs;
- malformed or schema-invalid frontmatter;
- references to non-existent IDs;
- wrong relationship kinds;
- insufficient T0/T1/T2 evidence;
- orphan artifacts that policy requires to be linked;
- PR task/level mismatch;
- missing `[DEV-n]` commit marker for T1/T2;
- code diff that does not touch declared `implementation.paths`;
- missing PR risk attestation for T1/T2.
