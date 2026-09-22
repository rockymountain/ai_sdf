---
id: CTRL-LEARNING-README-001
kind: factory-learning-definition
status: active
version: 1
owner: factory-maintainer
last_updated: 2026-09-22
change_owner: CTRL-CHANGE-004
---

# Factory Learning Capture

## Purpose

`control/learning/` preserves compact, evidence-linked Factory learning that can
justify a rule, profile, control, or experiment correction.

Learning records are provenance for rules. They are not execution authority,
project baselines, architecture decisions, policy exceptions, implementation
approval, or runtime evidence.

## Lifecycle

```text
observed -> validated -> promoted -> superseded
```

- `observed`: a bounded event or recurring pattern is recorded without claiming
  a general rule.
- `validated`: evidence and applicability have been reviewed, unknowns remain
  explicit, and the root cause is sufficiently supported for action.
- `promoted`: an approved rule/control change identifies the learning record as
  provenance and names the promoted result.
- `superseded`: later evidence replaces the lesson or narrows its applicability;
  the old record remains for history.

Skipping directly from `observed` to `promoted` is not permitted. A single
approved change MAY record validation and promotion together when the approval
explicitly covers the evidence, root cause, applicability, and resulting rule.

## Minimal record contract

A learning record SHOULD contain only decision-useful fields:

```yaml
id: LSN-NNN
kind: factory-learning
lifecycle_state: observed | validated | promoted | superseded
change_owner: <CTRL-CHANGE-NNN-or-other-governed-owner>
source_revision: <full-sha-or-unknown>
observation: {}
evidence_provenance: {}
root_cause: []
applicability: []
promoted_result: []
does_not_imply: []
unknowns: []
```

Exact timestamps, token usage, duration, runtime output, and Receiver evidence
MUST remain `unknown` when unavailable. Missing values MUST NOT become zero.

## Lean capture rules

- Create a record only when evidence can change a rule, control, experiment, or
  decision.
- Prefer structured facts and links over narrative retrospectives.
- Do not duplicate canonical rules; reference the promoted rule.
- Do not use this namespace as a session diary, generic lesson log, backlog, or
  documentation graveyard.
- Supersede records instead of silently rewriting accepted historical learning.
- Review stale `observed` records and either validate, supersede, or remove them
  when no durable decision depends on them.

## Current automation boundary

This initial learning capture is intentionally manual and minimal. It introduces
no schema, validator, generator, CI gate, or automation. Repeated stable patterns
may justify later automation through a separately governed change.
