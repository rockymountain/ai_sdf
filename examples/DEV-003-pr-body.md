## Change declaration

Traceability Task: DEV-003
Traceability Level: T2

### Why?

FR-003: every significant PR path needs declared provenance; one covered source
file must not hide unrelated implementation or sensitive design changes.

### What changed?

CMP-002 implements ADR-003's per-path coverage, repeated task declarations, and
base-governed exempt/generated classifications. DEV-003 declares all bootstrap
paths, including its policy and documentation, because the base has no exclusions.

### Evidence

TEST-003, the complete DEV-001/DEV-002 suite, AGENTS.md reproducibility, and real
baseline-to-DEV-003 commit/PR evidence validation.

### Risk classification attestation

- [x] I acknowledge this is a material design change and have linked the required design + decision/contract + verification evidence.

T2 reflects the governance and validator contract changes authorized by the user.
The single-task syntax remains valid. Exemptions cannot apply to their own PR.
