---
id: TEST-018
kind: verification
title: Observed Claude runtime-version provenance verification
status: verified
version: 1
verification_type: integration
---

# Verification contract

TEST-018 verifies DEV-018 with injected version runners, injected process fixtures,
a real `BoundedExecutionController`/`TelemetryStore` pair, and the real
`ControlledInvocationGateway`. It performs no live provider invocation and does not
mutate the governed operational database. Deterministic tests live in
`tools/traceability/tests/test_claude_runtime_version.py`, and one operator-wiring
assertion in `tools/traceability/tests/test_dual_runtime.py`.

# Required assertions

## Discovery and production ordering

- The Claude operator (`tools/ai_execution.py`) constructs `ClaudeRuntimeAdapter`
  without performing any version inspection itself.
- Version discovery runs inside `ClaudeRuntimeAdapter.start()`, after the gateway's
  governed invocation-start record (and, for implementation, reservation binding)
  already exists, and before any Claude inference process is created.
- On success, the observed single-line output is retained verbatim and persisted as
  terminal `runtime_version` through the existing gateway/store path.
- Timeout, non-zero exit, empty, whitespace-only, multi-line, and non-text version
  output fail closed (`resolve_runtime_version`).
- `ClaudeRuntimeAdapter` accepts an optional non-blank pinned `runtime_version`
  override for tests; a blank override is rejected. No version inspection occurs at
  construction time.

## Implementation-reservation regression (FR-007)

- For an `implementation` invocation with an existing `RESERVED` candidate,
  definitive version-discovery failure (missing executable) travels through the
  real gateway/controller: the invocation row exists with
  `terminal_status=failure`, `terminal_reason=runtime_error`.
- Exactly one `reservation_released` evidence record exists; the reservation
  transitions `RESERVED -> RELEASED`; no attempt is consumed (the `attempts` table
  stays empty for that scope).
- The candidate attempt number is reusable: a new reservation for the same scope
  claims the same `candidate_attempt_number` with a new `reservation_id`.
- The original released reservation and its release evidence remain unchanged after
  the replacement reservation is created.
- No Claude inference process is ever created when discovery fails (`process_factory`
  raises if invoked).

## Non-implementation failure behavior

- For `review` (representative of `review`/`acceptance_validation`/`orchestration`),
  version-discovery failure travels through the same governed gateway path: the
  invocation row exists with terminal failure evidence, and no reservation or
  attempt is created for that scope.

## Regression

- Codex selection performs no Claude version inspection.
- `AIRuntimePort` members and method signatures are unchanged.
- The Claude adapter and operator source contain no hard-coded version literal or
  version-specific extension path.
- TEST-017 dual-runtime, controlled-execution, bounded-execution, cost-baseline,
  traceability, environment, and generated-governance checks remain passing.

# Acceptance boundary

TEST-018 is deterministic evidence only. It does not rewrite historical telemetry,
start M3, declare a fixed M3 set, prove the baseline, make exact token KPIs
decision-eligible, or authorize M4.

# Closure evidence

`tools/traceability/tests/test_claude_runtime_version.py` contains 11 deterministic
test methods; all 11 pass. The independent Codex re-audit ran the same 11 plus 113
related-regression tests and returned `ACCEPTED_WITH_NONBLOCKING_OBSERVATIONS` with
no remaining blockers. Closure additionally reran the full deterministic suite
(218 tests), the traceability validator (65 artifacts), the environment check, and
`generate_agents.py --check`, all passing.
