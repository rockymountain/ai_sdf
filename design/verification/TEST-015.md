---
id: TEST-015
kind: verification
title: Authoritative traceability and risk-attestation policy verification
status: verified
version: 4
verification_type: integration
---

# Verification contract

`tools/traceability/tests/test_quality_gate.py:TraceabilityRiskGateTests` exercises
the real `load_traceability_and_risk_gates`, `validate_traceability`, and
`validate_change_evidence` paths against real governed artifacts (helper-level
`attestation_satisfied` assertions in `test_validator.py` are supplementary only)
and proves:

- QG-003/QG-005 declaration failures (missing, duplicate, wrong name/policy/event,
  disabled, unsupported field) fail closed;
- every mandatory trace-policy field (levels, description, `requires.*`,
  escalation_triggers exact eight-value set, non-empty t2_path_triggers) fails
  closed when missing or malformed;
- malformed or unsupported risk-attestation policy fields fail closed;
- `requires.risk_attestation` is the sole applicability authority: a loader-level
  T0 fixture proves policy-driven applicability, and a real `validate_change_evidence`
  T0 transition independently proves the PR enforcement path itself rejects a
  declaration missing the required checked T0 evidence and accepts it once
  supplied, with no hidden T0 special case; an applicable level with an empty
  evidence contract fails closed; a non-applicable level may carry a dormant
  contract;
- distinct base and proposed applicable QG-005 evidence contracts (different
  required strings for the same level) are independently enforced against the
  same PR task block through the real `validate_change_evidence` path: supplying
  only one side's string fails the other side's obligation by name, and
  supplying both passes, without collapsing base/proposed into one opaque
  merged contract;
- a base schema/policy is read from the base revision and is immune to a
  corrupted or weakened workspace schema;
- the pinned bootstrap adapter accepts only the exact legacy base and exact
  legacy QG-003/QG-005 shape, rejects every other base and the workspace, and
  never consults a proposed schema or proposed risk policy. Both legacy gates
  independently fail closed at the pinned base for: missing, duplicate, wrong
  name, `deterministic`/`blocks_merge` false, wrong-typed (including the
  integer/bool equality edge case `1` vs. `True`, and a string), extra field,
  and non-mapping declarations; a proposed/workspace schema made maximally
  permissive cannot rescue a malformed legacy base gate, because the bootstrap
  path never consults it. The legacy-gate match uses a strict
  `type(...) is bool` comparison (`_matches_legacy_gate()`), not plain dict
  equality, precisely because Python's `1 == True` would otherwise let a
  wrong-typed value satisfy the exact-boolean precondition — an actual
  enforcement defect found and corrected by this verification round, not
  merely a coverage gap;
- an existing task's T2→T1 downgrade cannot delete base-required evidence, and
  passes when that evidence survives; a T1→T2 upgrade enforces the additional
  proposed requirement;
- a new task cannot use a proposed policy weakening to escape a true base
  risk-attestation requirement;
- a base task that remains PR-relevant (declared, or path-matched) but is
  absent from proposed traceability fails closed;
- removing a base T2 path trigger from proposed policy cannot disable base T2
  path-coverage protection;
- QG-001, QG-002, QG-004, and FR-003/ADR-003 change-provenance behavior remain
  correct and unchanged (`test_quality_gate.py`, `test_change_provenance.py`,
  `test_validator.py` full regression).

# Human boundary

The tests validate policy structure, applicability, evidence shape, and failure
semantics. They do not claim that deterministic code can decide semantic risk or
the correct human-assigned traceability level.

# Lifecycle boundary

Verified under Owner Gate B-A implementation authority
(`OWNER-ACCEPT-CTRL-CHANGE-015-INCREMENT-B-2026-09-26`). This verification result
does not itself close Increment B; closure requires a separate Owner Gate B-B
after independent implementation audit.
