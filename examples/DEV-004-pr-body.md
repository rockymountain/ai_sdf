Traceability Task: DEV-004
Traceability Level: T2

### Why?

FR-004: canonical PR evidence settings must determine QG-004 behavior rather than
remain unused declarations beside hardcoded enforcement.

### What changed?

QG-004 now declares its PR scope and policy reference. CMP-002 validates and
executes base and proposed settings under ADR-004; TEST-004 covers the rule family.
The only legacy adapter is pinned to the merged DEV-003 commit. No existing gate
obligations or dependency pins are weakened.

### Evidence

Full canonical validation, regression suite, generated instructions, and real
Git evidence from 972774f18b879d023eb005d1af021699ed6b4ed5 to DEV-004 HEAD.

- [x] I acknowledge this is a material design change and have linked the required design + decision/contract + verification evidence.
