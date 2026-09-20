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
