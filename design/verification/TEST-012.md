---
id: TEST-012
kind: verification
title: Durable nonimplementation authorization and operator adoption verification
status: verified
version: 1
verification_type: integration
---

# Verification contract

After ADR-007 approval and DEV-012 implementation, deterministic fixtures and fake
runtime ports must prove the authorization and operator contract before any live
provider proof.

# Required assertions

## Authorization

- Missing required `HumanAuthorization` fails before provider start.
- Malformed authorization fails before provider start.
- The exact canonical actor, timezone-qualified timestamp, reason, and disposition
  survive persistence and store restart.
- Exactly one authoritative `nonimplementation_authorized` event links to the
  correct invocation and scope for each required purpose.
- Prompt text, provider metadata, logs, and boolean approval flags cannot substitute
  for structured authorization.

## Atomicity and failure

- Authorization validation, invocation-start persistence, and authorization-event
  persistence are atomic and commit before the runtime port is called.
- Injected authorization-evidence persistence failure rolls back the start and the
  runtime port is not called.
- Definite non-start retains authorization-as-permission plus distinct non-start
  evidence; uncertain and accepted starts retain their existing classifications.
- Timeout and terminal failure preserve the authorization evidence without creating
  retries or capacity.
- Restart preserves queryability. Duplicate/replayed invocation identity is rejected,
  and zero or multiple authoritative events fail verification.

## Capability and accounting

- `acceptance_validation`, `review`, and `orchestration` are read-only.
- None reserves, consumes, replenishes, or reopens implementation attempt capacity.
- Their usage remains attributable to the declared DEV task.

## Regression

- Continuation authorization and lineage remain correct.
- Implementation reservation, checkpoint, circuit, and watchdog behavior is
  unchanged.
- Existing DEV-007 historical evidence remains valid without invented backfill.
- Schema-v1/v2-to-v3 and existing schema-v3 behavior remain passing; no schema
  version change occurs.
- Existing `live-proof` behavior remains compatible with the prospective structured
  authorization requirement.
- Exact/unknown usage and requested-versus-observed model semantics are unchanged.

## Operator interface

- DEV task, traceability level, scope, objective when applicable, run, invocation,
  canonical source revision, purpose, requested model/reasoning, model-selection
  strategy, explicit routing-policy absence, context strategy, and structured
  authorization are explicit or generated only where existing contracts permit.
- Implementation cannot reach the runtime without reservation; runtime success alone
  does not close an attempt; deterministic checkpoint closure retains existing rules.

# Live adoption proof

After implementation authorization and all deterministic gates passed, one
separately authorized PRE-WINDOW controlled Codex `acceptance_validation` call used:

```yaml
requested_model: gpt-5.6-sol
requested_reasoning_effort: medium
model_selection_strategy: fixed
routing_policy_version: null
context_strategy: chat-heavy
```

The proof used the operator-facing entry point, structured authorization, and a
runtime-enforced read-only capability. It preserved repository state, created no
implementation attempt or DEV outcome, and verified the requested profile and exact
telemetry in the operational store. It is not M3 baseline evidence and did not start
the measurement window.

Retained operational evidence identifies the accepted proof as:

```yaml
execution_scope_id: DEV-012-live-controlled-adoption-proof-214d9a0655ca
run_id: 2f4191bd-9ae3-468a-8465-03957039d5a2
invocation_id: 1b173427-69e3-41f3-8f87-c63b8306f75f
schema_version: 3
authorization_event:
  kind: nonimplementation_authorized
  count: 1
  valid: true
terminal_status: success
usage_status: exact
input_tokens: 14334
output_tokens: 194
total_tokens: 14528
reservations: 0
attempts: 0
invocation_attempts: 0
DEV_012_finalized_outcomes: 0
```

Historical DEV-007 evidence remains present without invented backfill. Together
with the deterministic suites, this proves generic operator adoption for the
approved boundary. The actual M3 measurement window has not started.

# Acceptance boundary

Passing TEST-012 verifies the approved implementation. It does not approve ADR-007,
mark M3 complete, prove the cost-control baseline, make the exact token KPI
decision-eligible, or authorize M4.
