---
id: TEST-008
kind: verification
title: Bounded autonomous execution deterministic verification
status: verified
version: 2
verification_type: runtime
---

# Evidence

Baseline at `f269bb29d5f7bc91a677b6ec4d46dedbffc877dd` passed 86 tests with the
repository's pinned Python 3.14.6 virtual environment. The system interpreter was
rejected by the environment gate; sandbox temp-directory access errors were
resolved by running the unchanged tests with their required filesystem access.

Final deterministic verification on 2026-09-21 passed:

- Focused DEV-008 suite: 34 tests in 8.600 seconds.
- Complete suite: 121 tests in 91.652 seconds, including all DEV-007 telemetry and
  watchdog regressions. A separate DEV-007 regression run passed 27 tests.
- Environment: Python 3.14.6 and all pinned packages in the isolated `.venv`.
- Static traceability: 36 artifacts; QG-004 canonical configuration valid.
- AGENTS.md reproducibility and `git diff --check`: passed.
- Provenance path audit: all 17 DEV-008 implementation paths exist and exactly
  cover the owned change set. The unrelated DOCX/PDF deletions are excluded.

Local command transcripts are retained at `.sdf/runtime/dev008-baseline.log`,
`.sdf/runtime/dev008-focused.log`, `.sdf/runtime/dev008-full-suite.log`, and
`.sdf/runtime/dev008-telemetry-regression.log`. The tests below reproduce the
evidence without a live provider. No existing test assertion, QG-004 obligation,
or canonical design semantics were weakened.

Schema 3 is added in one `BEGIN IMMEDIATE` transaction, including the v1-to-v2
upgrade when needed. It leaves existing invocation columns and finalized DEV
outcomes intact. New attempt identities are stored separately and exported only
when present, so historical non-attempt evidence acquires no invented attempt.

## Attempt-2 audit correction

The correction audit found two implementation defects in commit
`b459068608ea599bf20a8107ae4c3fbe6e4cb72f`:

1. resolving one STOP condition could assign `ACTIVE` even while independent
   unknown-usage or terminal evidence still blocked autonomy;
2. a scope created implicitly for nonimplementation telemetry could later reserve
   implementation capacity without trusted workflow registration.

The correction derives all currently applicable blockers from durable reservation,
attempt, invocation, and execution-evidence rows inside the same `BEGIN IMMEDIATE`
transaction used by each transition. `ACTIVE` is restored only when that complete
set is empty. The P1-I16 exception is limited to the affirmatively evidenced
`interrupted/usage_limit` predecessor chain for the same authorized continuation;
it does not exempt an unrelated review or other invocation.

Trusted `create_scope` now appends `objective_registered` evidence. Authorized
successors retain their existing `successor_authorized` evidence. `reserve` and the
gateway require one of those durable authorities. Compatibility scopes created by
review, orchestration, or acceptance validation remain valid for telemetry and
lifecycle enforcement, but cannot reserve capacity until `create_scope` explicitly
registers the same unchanged identity. Pre-correction schema-3 roots without either
authority fail closed; no prompt or provider metadata is used to infer authority.

Fresh correction verification on 2026-09-21 passed:

- Correction-specific adversarial suite: 9 tests.
- Focused DEV-008 suite: 43 tests in 9.464 seconds.
- Complete suite: 130 tests in 90.286 seconds.
- DEV-007 telemetry/watchdog regressions: 27 tests in 4.893 seconds.
- Environment, static traceability, QG-004 committed-change evidence, AGENTS.md
  reproducibility, and `git diff --check`: passed.

The correction-specific evidence proves that releasing an unresolved reservation
does not clear an unrelated unknown-usage review blocker; continuation of a
suspended usage-limit attempt is rejected before the runtime port while that
independent blocker remains; and an implicitly created nonimplementation scope
cannot reserve or start implementation work. Separate positive cases prove that
legal resolution of the only blocker restores the applicable state, explicit
`create_scope` registration permits reservation, and a human-authorized successor
retains reservation authority across store restart.

# Reproduction

Use the isolated environment from `.python-version` and `requirements-dev.txt`:

```text
python tools/check_environment.py
python -m unittest discover -s tools/traceability/tests -p test_bounded_execution.py -v
python -m unittest discover -s tools/traceability/tests -v
python tools/traceability/validate.py --repo .
python tools/generate_agents.py --check
git diff --check
```

# Assertions

- Canonical budget and watchdog are 2 and 600; readers and static validation reject
  missing, malformed, boolean, fractional, zero, negative, and string budget values.
- Reservation does not bind an attempt. Released candidates reuse their number
  under a new UUID while retaining old evidence. Accepted/non-start/uncertain
  start evidence maps to consumed/released/unresolved with no exception inference.
- Reserved, unresolved, and unclosed consumed attempts exclude further work.
  Scope and reservation state survive reopening the SQLite store.
- Six independent processes compete for candidate 2: exactly one owns it and five
  are rejected. Reusing a reservation for a second active invocation reaches the
  port only once. Checkpoint closure is rejected while an invocation is live.
- A passed first checkpoint closes the scope; a failed one permits candidate 2.
  The two-failure test counts exactly two port starts even after restart, a new
  run ID, and rejected post-circuit calls for every invocation purpose.
- A database trigger aborting the final scope update rolls back the checkpoint
  evidence and attempt failure too; removing it permits the atomic FAILED plus
  CIRCUIT_OPEN transition.
- Consumed timeout enters reconciliation while preserving observed exact usage;
  pre-consumption timeout retains unresolved capacity without inventing an attempt.
- Human-authorized usage-limit continuation retains the same attempt and an open
  checkpoint. Four invocations can belong to attempt 1; attempt 2 remains the
  final capacity. Unknown predecessor usage stays unknown in invocation, attempt,
  and DEV aggregates. Runtime failure, timeout, cancellation, and unknown outcomes
  cannot auto-resume or manufacture a free retry.
- Reconciliation closes only from retained deterministic checkpoint evidence, or
  suspends on affirmative recovered interrupted/usage_limit evidence. Immutable
  terminal records remain unchanged.
- Permanently unresolved, reconciliation, and circuit-open predecessors require
  a linked human-authorized successor. Snapshot and raw invocation comparisons
  prove predecessor evidence stays unchanged. Duplicate successors and unlinked
  roots for an existing objective are rejected.
- Schema-1 and schema-2 fixture upgrades preserve every original invocation
  column/value and schema-2 DEV outcomes; schema 1 acquires an empty outcome table.
  Legacy unknown-usage evidence remains a stop condition after migration.
- Codex conformance fakes verify accepted, local non-start, and uncertain request
  mappings and capability restrictions without invoking a live provider.
