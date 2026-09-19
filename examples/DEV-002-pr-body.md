## Change declaration

Traceability Task: DEV-002
Traceability Level: T2

### Why?

FR-002: every implementation-path entry for a current T1/T2 task must resolve to
an existing repository file; unresolved globs must not count as evidence.

### What changed?

CMP-002 implements ADR-002's filesystem resolution check. Every entry is checked
independently. Current means all supported statuses except deprecated, superseded,
and retired. Previous literal-existence checks remain in force for all tasks.

### Evidence

TEST-002 covers literal/glob success and failure, directory/external-file rejection,
per-entry checks, and lifecycle compatibility. Full validation and tests include
unchanged DEV-001 behavior and generated AGENTS.md reproducibility.

### Risk classification attestation

- [x] I acknowledge this is a material design change and have linked the required design + decision/contract + verification evidence.

T2 reflects the stricter validator acceptance contract. No schema or constitution
changes. The user authorized this invariant; existing human review gates remain.
