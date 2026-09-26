---
id: TEST-019
kind: verification
title: M4 context-effect KPI measurement verification
status: verified
version: 1
verification_type: integration
---

# Verification contract

TEST-019 verifies DEV-019 with synthetic fixture rows written directly into a
temporary SQLite evidence database, read back only through
`context_effect.build_context_effect_report`'s read-only connection. It performs
no live provider invocation, uses no governed runtime operator, creates no
reservation or attempt, and does not mutate any governed operational database.
Deterministic tests live in `tools/traceability/tests/test_context_effect.py`.

# Required assertions

1. Existing `cost_baseline.build_report` delivery-accounting fields
   (`input_tokens_per_accepted_dev`, `total_tokens_per_accepted_dev`) retain their
   all-attributable, mixed-provider meaning; `cost_baseline.py` is unmodified.
2. A Claude implementation plus Codex review DEV still reconciles to one exact
   mixed-provider delivery total via `build_report`; that total is never asserted
   or reported as a provider-independent comparison scalar.
3. A Claude implementation/continuation observation set is assessed independently
   of delivery accounting via `build_context_effect_report`.
4. Failed, retried, and continuation invocations remain in the context-effect
   numerator for accepted DEV tasks.
5. Review usage is excluded from that numerator but remains visible in delivery
   accounting (`build_report`) and is not required to have known usage for the
   context-effect result to be calculable.
6. The denominator is the predeclared accepted-DEV cohort count, not the count of
   tasks with usable rows.
7. A cohort task missing invocation coverage makes the whole cohort's observation
   set `missing_invocation_coverage`; it is never silently omitted to shrink the
   denominator.
8. A row's `requested_model` equaling a compatible name does not substitute for a
   conflicting or missing `observed_model`; such a row is `not_comparable`.
9. An unknown or uncovered `runtime_version`, and the absence of any declared
   `CompatibilityRule`, both fail closed (`not_comparable` /
   `no_compatibility_rule_declared`).
10. A synthetic, clearly fixture-only `CompatibilityRule` (non-real version
    strings) exercises the full positive mechanism end to end and asserts no real-
    version equivalence.
11. The M4 comparison direction is fixed: baseline `context_strategy` must be
    `chat-heavy` and treatment `context_strategy` must be an already-governed
    named treatment (`manual-context-pack` or `graphify-context-pack`). A
    reversed pairing, a same-strategy pairing, and an undeclared `other`
    treatment all leave the KPI unavailable and can never pass the gate on
    token-count differences alone. A contributing invocation whose retained
    `context_strategy` mismatches its own cohort's declared value makes that
    cohort's observation set unavailable.
12. Unknown usage on a contributing implementation/continuation row makes the
    cohort `unknown_usage_present`; unknown usage on an unrelated review row does
    not affect context-effect calculability. A contributing invocation that is
    non-terminal (no `completed_at`) makes the cohort
    `non_terminal_contributing_invocation` and stays visible in coverage
    diagnostics rather than disappearing; a contributing invocation that
    completes at or after `end_exclusive` makes the cohort
    `boundary_spill_contributing_invocation`, stays visible, and never borrows
    that later terminal evidence into the closed window; a contributing
    invocation that completes strictly before `end_exclusive` remains
    admissible. `cost_baseline.build_report`'s own existing non-terminal/boundary
    handling is unchanged. An `exact`-status row with
    missing `output_tokens`, missing `total_tokens`, or an inconsistent
    `total_tokens != input_tokens + output_tokens` is never treated as usable
    evidence, never zeroed, and never silently dropped — it makes the cohort
    `malformed_exact_usage` and remains listed in diagnostics. An absent
    `GuardrailContract` and an explicitly empty one both yield
    `treatment_decision_eligible=false`, even against a passing effect gate; only
    a non-empty declared contract with sufficient evidence can make it true.
13. A missing declared-task acceptance record, and a zero baseline token sum, both
    yield `effect_metric_calculable=false` and `effect_gate_result="unavailable"`.
13a. Reasoning effort is a fixed comparison condition: `requested_reasoning_effort`
    is a required, explicitly supplied `ContextEffectCohort` field (omission
    raises); baseline and treatment must declare the identical value including
    both null; a contributing invocation drifting from its own cohort's declared
    value makes that cohort `requested_reasoning_effort_mismatch`; and a
    `CompatibilityRule` declaring more than one permitted reasoning-effort value
    fails closed at construction.
13b. Diagnostic collection is complete, not first-match: an eligibility failure
    in one coverage category never truncates collection of the others.
    Non-terminal + boundary-spill, boundary-spill + missing DEV coverage, and
    boundary-spill + missing outcome evidence each retain every applicable
    diagnostic list simultaneously (deterministically ordered, duplicate-free),
    while a single primary `reason` is still selected from a fixed priority
    order and the result remains `effect_metric_calculable=false` /
    `effect_gate_result="unavailable"` / `treatment_decision_eligible=false`.
14. Exact-arithmetic boundary proof: a reduction of exactly 70% passes; strictly
    below 70% fails; strictly above 70% passes; verified via integer cross-
    multiplication, not floating point.
15. A calculable `>=70%` reduction with no declared `GuardrailContract` remains
    measured (`effect_gate_result="pass"`) but `treatment_decision_eligible=false`.
16. A calculable `<70%` reduction with a sufficient declared `GuardrailContract`
    remains a measured `fail` and is `treatment_decision_eligible=true`; this does
    not accept the treatment.
17. No declared `GuardrailContract` yields `treatment_decision_eligible=false`
    regardless of a passing synthetic effect gate.
18. Rejected DEV tasks and review/rework evidence remain visible through the
    unmodified `build_report`.
19. `AIRuntimePort`'s members and method signatures are unchanged; the M3/M4
    control-state fields in `control/project-control.yaml` are unmodified by this
    task.
20. When the context-effect KPI is `not_comparable`/unavailable, existing
    `cost_baseline` delivery-accounting metrics remain independently exact when
    their own existing eligibility conditions are satisfied.

# Acceptance boundary

TEST-019 is deterministic evidence only. It does not declare an M3 measurement
window or fixed task set, execute a baseline task, activate DEV-014/015/016,
authorize M4, or make any treatment-acceptance decision.
