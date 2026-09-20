---
id: PROB-002
kind: problem
title: Autonomous AI execution lacks bounded and attributable runtime control
status: accepted
version: 1
owner: factory-maintainer
---

# Problem

The repository has deterministic governance and human-operated AI workflows, but no
provider-neutral runtime boundary that can meter, attribute, and stop autonomous AI
work. Controlled invocations are not linked durably to a DEV task or execution
scope, attempt budgets and open-attempt state do not survive process restart, and no
circuit can prevent further spend after a bounded execution objective has failed.

Binding canonical policy or telemetry to one bootstrap SDK would also make runtime
replacement require redesign of SDF governance. Without an SDF-owned controlled
invocation boundary, exact or explicitly unknown per-invocation usage, explicit
aggregate completeness, restart-safe attempt accounting, and a finite watchdog,
Phase 1 cannot claim measurable cost, bounded retry, fail-closed autonomous
execution, or runtime portability.
