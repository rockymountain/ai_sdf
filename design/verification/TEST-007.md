---
id: TEST-007
kind: verification
title: Controlled AI runtime telemetry and bounded live invocation verification
status: verified
version: 1
verification_type: runtime
---

# Verification contract

Deterministic tests verify mandatory invocation identity, fail-closed telemetry and
policy handling, canonical watchdog loading, finite interruption, absence of fake
attempt capacity for a non-attempt timeout, exact/unknown usage mapping, optional
breakdown and runtime-identity behavior, requested/observed model separation,
purpose persistence, read-only capability enforcement, restart persistence, and
reproducible export. Existing validator behavior and the full regression suite must
remain passing.

After those gates pass, run exactly one human-authorized, tool-bearing Codex
`acceptance_validation` invocation for DEV-007 with the canonical 600-second
watchdog and `Sandbox.read_only`. The action must be harmless repository inspection.
Capture the complete governed workspace state immediately before and after, and
require equality. `ThreadTokenUsage.last` must produce exact current-invocation
evidence and `ThreadTokenUsage.total` must be retained only as cumulative thread
reconciliation evidence. Runtime-native IDs and observed model identity are recorded
only when the SDK exposes affirmative evidence.

# Results

Verified on 2026-09-21 with Python 3.14.6 and the pinned isolated development
environment. Dependency integrity (`pip check`), environment validation,
deterministic traceability for 34 artifacts, QG-004, AGENTS.md reproducibility,
compilation, and `git diff --check` passed. The complete traceability regression
suite passed 76 of 76 tests; the focused DEV-007 suite passed 18 of 18 tests after
the final workspace-fingerprint correction.

The single authorized live invocation passed with:

- invocation ID `93b84286-888c-4097-8b9c-9ebac37e940b`;
- `dev_task = DEV-007`, `traceability_level = T2`, and
  `invocation_purpose = acceptance_validation`;
- source revision `3224e8d1443b8db2733a43c1b1ee1a4b977b0a34`;
- `CodexRuntimeAdapter` and runtime version 0.155.1 under the `read_only`
  capability profile;
- canonical watchdog duration 600 seconds;
- terminal status `success` with one `CommandExecutionThreadItem` used to run
  `git rev-parse HEAD`;
- exact current usage of 15,183 input, 44 output, and 15,227 total tokens, with
  14,848 cached input and 0 reasoning output tokens;
- exact cumulative thread reconciliation evidence of 30,244 input, 114 output,
  and 30,358 total tokens, with 14,848 cached input and 0 reasoning output tokens;
- runtime session ID `01a0bfe4-935e-7c90-ae76-d960d83db0a6` and runtime
  invocation ID `01a0bfe4-94b5-7b33-9d95-53e0158a069b` as exposed by Codex;
- no requested model, requested reasoning effort, or affirmatively observed model;
- identical pre/post status, tracked worktree diff, index diff, changed-path list,
  and changed-file content hashes (`workspace_unchanged = true`).

The invocation ran from 2026-09-20T17:37:01.205Z to
2026-09-20T17:37:15.003Z. No retry, implementation-attempt capacity, or autonomous
follow-on invocation was used.

## Post-commit conformance correction

Deterministic correction verification on 2026-09-21 reproduced the original
whole-invocation watchdog defect before the fix: a fake spend-capable `start()`
operation remained active beyond the governed deadline because interruption could
not occur until a handle was returned. The corrected gateway now starts the port
under a per-invocation abort control, revokes start authorization at the same
whole-invocation deadline, and waits for start or observe work to become quiescent
before persisting a timeout. The Codex adapter registers the pinned SDK's public
`close()` operation before thread/turn start so a blocked start request terminates
the app-server transport and unblocks pending SDK waiters; an available turn handle
continues to use `TurnHandle.interrupt()`.

SQLite schema version 2 adds immutable finalized DEV outcomes without changing raw
invocation evidence. Absence of an outcome row exports as
`outcome_finalized=false` with no `task_accepted`; finalization records
`outcome_finalized=true` and boolean `task_accepted`. DEV aggregation includes every
retained invocation, emits exact known subtotals, marks completeness `complete` only
when every contribution is exact, and omits an exact total when any contribution is
unknown. The retained schema-1 DEV-007 store upgraded without losing its live row;
before backfill it exported no outcome, and after accepted-outcome backfill it
exported one exact invocation, a 15,227-token complete aggregate, and
`task_accepted=true`.

The governed default store is restricted to `.sdf/runtime/ai-execution.sqlite3`
under the resolved repository path; tests and CLI calls may use an explicit database
override. Initialization proves database read access and a write transaction before
runtime start, and deterministic validation requires `.sdf/runtime/` Git exclusion.
Phase 1.0 relies on inherited workspace/OS ACLs and claims no private-mode or
confidentiality property that default Python, SQLite, Windows, or POSIX permissions
do not prove.

The focused DEV-007 correction suite passed 27 of 27 tests and the complete suite
passed 86 of 86 tests. Environment validation, dependency integrity, deterministic
traceability for 34 artifacts, QG-004, AGENTS.md reproducibility, compilation, and
`git diff --check` passed. No real runtime invocation occurred during correction.
The prior live evidence remains applicable because the Codex thread/turn/stream,
read-only capability, telemetry mapping, and workspace path are materially
unchanged; the added control wraps and can abort start without changing the
successful adapter path. `live_recertification_required = false`.

A final deterministic semantic correction prevents a successful DEV-007 invocation
from granting autonomous follow-on execution. Successful acceptance validation now
retains `human_attention_required=false` while returning and persisting
`autonomous_follow_on_allowed=false`; deterministic coverage also confirms that
failure and timeout outcomes continue to persist the same follow-on prohibition.
No live invocation was rerun, and `live_recertification_required = false`.
