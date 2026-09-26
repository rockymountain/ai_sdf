---
id: TEST-020
kind: verification
title: Factory-learning disposition and applicability obligation verification
status: verified
version: 1
verification_type: integration
---

# Verification contract

TEST-020 proves, after ADR-014 acceptance and DEV-020 implementation, only
claims within the Owner-selected `MANUAL_PRESENCE_WITH_DETERMINISTIC_SHAPE`
verification boundary:

- canonical instruction projection: the three new role-conditioned duty
  invariants (correction/closure-actor disposition; executor applicability;
  independent-auditor reassessment) are authored in
  `constitution/agent-runtime.yaml` and correctly separate executor,
  correction/closure-actor, and independent-auditor obligations;
- `AGENTS.md` is reproducible from `constitution/agent-runtime.yaml` via the
  unmodified `tools/generate_agents.py`, and contains the three invariants
  verbatim;
- `knowledge/schemas/learning-disposition.schema.json` is itself a valid
  JSON Schema;
- a `learning_disposition` block with each of the three allowed values and a
  non-empty rationale validates successfully against that schema;
- a `learning_disposition` block fails closed when: the value is missing,
  the value is not one of the three allowed enum strings, the rationale is
  missing, the rationale is empty, or an unsupported extra field is present;
- the unmodified static traceability pipeline (`scan_artifacts` +
  `validate_traceability`) still passes against the unmodified repository,
  proving no historical control-decision record is required to carry
  `learning_disposition`.

# Evidence boundary

Verification is limited to deterministic shape/reproducibility/regression
properties, per the Owner-selected `MANUAL_PRESENCE_WITH_DETERMINISTIC_SHAPE`
boundary. It does not and cannot prove:

- that a recorded disposition value, its rationale, a lesson-applicability
  match, or a no-match rationale is substantively correct;
- that a `learning_disposition` was actually created, or actually attached
  to any real closure or terminal record — creating that disposition is an
  accountable actor duty (the correction/closure actor), not a deterministic
  property, and the shape schema/helper can validate structure only when
  disposition evidence is supplied to it;
- that required disposition evidence is present in any given real
  closure/terminal event — checking real-event presence is an accountable
  workflow/audit obligation for the independent auditor or another actor
  authorized by the applicable closure process, never a claim this
  deterministic verification makes.

A deterministic shape PASS from `validate_learning_disposition` must never be
reported, by TEST-020 or by any actor citing it, as proof that a real
closure/terminal event actually contains the required disposition. TEST-020
does not exercise, and DEV-020 does not introduce, any live prospective
enforcement gate that automatically blocks a closure/terminal event when
disposition evidence is absent; `control/project-control.yaml` is not read
by this verification or by the shape-validating helper it exercises.

# Closure evidence

`LearningDispositionTests` in
`tools/traceability/tests/test_learning_disposition.py` exercises every
assertion above against deterministic local fixtures: 9/9 passed. Exact
commands and counts are reported in the DEV-020 implementation handoff.

# Lifecycle boundary

TEST-020 does not authorize an M3 window, M4, gate promotion beyond the
accepted FR-012/ADR-014 scope, or CTRL-CHANGE-014 closure — closure requires
a separate Project Owner decision after independent audit.
