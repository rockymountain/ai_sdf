---
id: TEST-011
kind: verification
title: M3 AI Cost Control Baseline measurement and report verification
status: verified
version: 1
verification_type: integration
---

# Verification contract

TEST-011 will verify the bounded DEV-011 implementation through deterministic,
reproducible fixtures and repository-controlled commands. No live provider call
is required for the initial M3 reporting capability.

The verification must prove that a declared measurement window is reproducible
and that its fixed baseline configuration explicitly records:

- `context_strategy: chat-heavy`;
- the included task mix and T0/T1/T2 trace-level mix;
- `requested_model: gpt-5.6-sol`;
- `requested_reasoning_effort: medium`;
- `model_selection_strategy: fixed`;
- `routing_policy_version: null`;
- `automatic_model_routing: false`;
- `context_optimization: false`;
- review and acceptance policy;
- the source evidence range and accepted/rejected DEV inclusion rules.

Every locked treatment field, including explicit `null` for
`routing_policy_version`, must be present in the input declaration. The evidence
boundary must be a machine-readable half-open UTC interval applied to terminal
invocations and finalized outcomes. Appending evidence outside that interval
must not change canonical report bytes, and bounded attempt membership must be
derived through authoritative links to included invocations.

Requested model/reasoning values must not be replaced by observed identity.
Observed provider/runtime identity may remain `unknown` when it is not
affirmatively exposed. Context optimization remains disabled for this M3
control treatment.

# Required assertions

- Exact and unknown invocation usage remain distinct.
- Historical missing usage remains unknown and is never normalized to zero.
- Any incomplete contribution produces an incomplete DEV/window aggregate while
  preserving exact known subtotals.
- An exact token KPI is absent or not decision-eligible unless every
  contributing accepted DEV has complete usage.
- Accepted and rejected DEV outcomes remain visible in the declared window.
- Failed attempts, retries, review calls, and orchestration calls remain in cost
  accounting and are not filtered out to improve the baseline.
- Deterministic metrics remain distinguishable for T0, T1, T2, and the aggregate
  window.
- Input tokens, output tokens, total tokens, calls, attempts, acceptance rate,
  and completeness are derived only from existing governed evidence.
- File counts are not accepted as token or cost measurements.
- Repeated execution against the same fixed evidence and configuration produces
  the same report/export.
- The report makes no M4 treatment, context-efficiency, savings, acceptance, or
  ROI claim.
- Existing telemetry, bounded-attempt, circuit-breaker, traceability, and full
  regression behavior remain passing.

# Acceptance boundary

Passing TEST-011 may provide the verification evidence needed to evaluate M3
exit criteria. It does not itself mark M3 complete, prove the cost-control
baseline, make incomplete token KPIs decision-eligible, start M4, or authorize a
context/routing optimization.

The implementation and this verification must escalate before any architecture,
NFR, security, data-model/schema, external-contract, reliability, compliance, or
migration change.
