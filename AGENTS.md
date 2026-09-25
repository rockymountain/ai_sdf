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
11. When acting as the Owner-authorized correction or closure actor, at a material correction round record a provisional learning disposition (NEW_LEARNING_CANDIDATE, EXISTING_LEARNING_REINFORCED, or NO_REUSABLE_LEARNING) with a short evidence-based rationale in that round's existing handoff; at CTRL-CHANGE delivery closure, or an Owner-issued non-delivery terminal outcome such as deferred or cancelled, record a durable learning disposition with rationale in that governed control-decision record. An independent-audit verdict is evidence for this disposition, not itself a disposition. Blocked or merely paused work without an Owner-issued terminal decision remains open, and its correction-handoff disposition stays provisional. A disposition does not create, validate, or promote a learning record, and grants no implementation or closure authority. Do not mark work complete or delivered merely to record a disposition.
12. When acting as implementation executor, before material T1/T2 design or implementation work, or material CTRL-CHANGE decision work, excluding T0 housekeeping and routine work, check control/learning/ for promoted lessons whose applicability field matches the work, as a discovery aid. For each match, record the lesson and the concrete check derived only from the accepted rule/control named by its promoted_result, never from its observation, root_cause, narrative, or preventive_heuristic fields; when no promoted lesson matches, record a concise no-match rationale instead of a per-lesson list. Checking a lesson grants no authority to perform the work.
13. When acting as independent auditor, independently derive which promoted lessons' accepted rule/control artifacts apply to the work under review from control/learning/ and their promoted_result, rather than accepting the executor's table, and verify whether the resulting required concrete checks were actually performed. The auditor remains read-only, does not edit any disposition record, and is granted no authority by this invariant.

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
