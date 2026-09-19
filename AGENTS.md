# AI-Native SDF Phase 0 — Agent Instructions

> Generated from canonical governance. Do not edit AGENTS.md by hand.

## Canonical principles

- **SDF-P-001** — Canonical truth precedes automation.
- **SDF-P-002** — Everything derived must be reproducible from canonical artifacts and code.
- **SDF-P-003** — Deterministic validation runs before AI semantic review.
- **SDF-P-004** — Every meaningful software change must be traceable to intent.
- **SDF-P-005** — Irreversible or material risk decisions require explicit human accountability.
- **SDF-P-006** — Agent runtime is replaceable; factory knowledge and policy are provider-neutral.

## Runtime invariants

1. Never invent or silently renumber IDs.
2. Read YAML frontmatter for artifact identity; filenames are not identity.
3. Every meaningful implementation change must declare a DEV-* task and traceability level.
4. T1/T2 changes must have upstream intent and verification evidence.
5. T2 changes must include design plus decision/contract evidence.
6. Do not downgrade T2-worthy changes to T1. Architecture, NFR, security, data model, external contract, reliability, compliance, or migration impact is T2.
7. Never modify canonical governance merely to make a failing change pass without explicit human approval.
8. Deterministic validation runs before semantic or LLM review.
9. Human approval is required for architecture tradeoffs, risk acceptance, security exceptions, irreversible migration, or policy changes.
10. Prefer small, explicit, reversible changes.

## Before proposing a change

Read:
- `constitution/principles.yaml`
- `constitution/policies.yaml`
- `constitution/quality-gates.yaml`
- `knowledge/traceability.yaml`

Run:

```bash
python tools/traceability/validate.py --repo .
```
