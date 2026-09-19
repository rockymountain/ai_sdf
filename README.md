# AI-Native SDF — Phase 0 Walking Skeleton

Phase 0 proves one invariant before any platform investment:

> A meaningful software change cannot merge without machine-verifiable traceability from intent to design/task, implementation evidence, and verification.

## First heartbeat

Patient Zero is `DEV-001` (T2-lite): **Add asynchronous document indexing**.

Trace chain:

`PROB-001 → FR-001 / NFR-001 → ADR-001 → CMP-001 / EVT-001 → DEV-001 → code diff + [DEV-001] commit → TEST-001`

## Local validation

```bash
python -m pip install -r requirements-dev.txt
python tools/traceability/validate.py --repo .
python -m unittest discover -s tools/traceability/tests -v
```

PR/commit validation can be exercised locally:

```bash
python tools/traceability/validate.py --repo . \
  --base-ref HEAD~1 --head-ref HEAD \
  --pr-body-file examples/DEV-001-pr-body.md
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
