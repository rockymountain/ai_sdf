Traceability Task: DEV-005
Traceability Level: T2

### Why?

FR-005 closes the validation runtime/dependency drift between local development and CI.

### What changed?

CMP-002 uses ADR-005's shared .python-version, fully pinned requirements-dev.txt,
standard isolated venv bootstrap, and deterministic environment verification.
CI consumes the same declarations and validation commands. Historical evidence
and existing quality-gate semantics remain intact.

### Evidence

TEST-005: fresh wheel-only install, actual-version/import checks, full regression
suite, canonical/QG-004 validation, AGENTS.md reproducibility, and real Git evidence.

- [x] I acknowledge this is a material design change and have linked the required design + decision/contract + verification evidence.
