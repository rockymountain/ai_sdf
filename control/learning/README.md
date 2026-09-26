---
id: CTRL-LEARNING-README-001
kind: factory-learning-definition
status: active
version: 2
owner: factory-maintainer
last_updated: 2026-09-25
change_owner: CTRL-CHANGE-014
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

This describes the historical initial-capture mechanism as originally
established: it was intentionally manual and minimal, and introduced no
schema, validator, generator, CI gate, or automation for learning records
themselves. Repeated stable patterns may justify later automation of learning
*records* through a separately governed change. See the following section for
the narrower, bounded schema/helper `ADR-014` subsequently added for
disposition shape only — that addition does not describe or change this
section's account of the original LSN-record capture mechanism, which remains
manual and minimal.

## Disposition vs. operative authority (ADR-014)

`ADR-014` adds a bounded, manual disposition/applicability obligation for
implementation executors, Owner-authorized correction/closure actors, and the
independent auditor; see `constitution/agent-runtime.yaml` and generated
`AGENTS.md` for its exact canonical text.

A recorded `learning_disposition` (`NEW_LEARNING_CANDIDATE`,
`EXISTING_LEARNING_REINFORCED`, or `NO_REUSABLE_LEARNING`) is tracking, not a
learning record and not execution authority. It does not skip this
namespace's `observed -> validated -> promoted -> superseded` lifecycle, and a
`NEW_LEARNING_CANDIDATE` disposition still requires this README's existing
"create a record only when evidence can change a rule, control, experiment, or
decision" bar to be separately met before an LSN is created.

For an applicable `promoted` lesson, its `promoted_result` field identifies
the actual operative rule/control — the accepted artifact that carries
authority. A lesson's `applicability` field is a discovery aid only. A
lesson's `observation`, `root_cause`, and any narrative or
`preventive_heuristic` field are supporting evidence for that promoted
result; they are never themselves an operative rule, and do not become one
merely because the LSN that contains them is `promoted`.

`ADR-014`/`DEV-020` add one narrow, governed exception to the automation
boundary above: `knowledge/schemas/learning-disposition.schema.json` and
`tools/traceability/validate.py:validate_learning_disposition()` now
deterministically validate the *shape* of a `learning_disposition` block
(its `value` enum and non-empty `rationale`) **when disposition evidence is
supplied to them**. This narrow schema/helper does not establish, and cannot
be used to claim, that a real closure or terminal event actually contains the
required disposition — it validates shape only, never presence. `DEV-020`
adds no live closure/terminal presence gate: `control/project-control.yaml`
is not read by this schema/helper, and no decision record is required to
carry `learning_disposition` merely because this schema/helper exists.
Whether required disposition evidence is actually present in a given real
closure/terminal event remains an accountable workflow/audit obligation for
the authorized closure actor and the independent auditor, not a deterministic
property this schema/helper proves.
