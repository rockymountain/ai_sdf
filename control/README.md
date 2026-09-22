---
id: CTRL-README-001
kind: control-definition
title: AI-Native SDF Project Control Plane Operating Contract
status: active
version: 1
owner: factory-maintainer
last_updated: 2026-09-22
change_owner: CTRL-CHANGE-004
---

# AI-Native SDF Project Control Plane Operating Contract

## 1. Purpose

`control/` là project delivery control plane của repository `ai_sdf`.

Nó duy trì trạng thái và forecast của dự án qua sáu dimension:

- scope;
- budget;
- timeline;
- outcome/value;
- quality;
- risk/governance.

Control Plane trả lời:

> Chúng ta dự định đạt outcome nào, đã hoàn thành gì, còn lại gì, đã tiêu bao
> nhiêu, forecast hiện tại là gì, variance ở đâu và có cần human decision hay
> rebaseline không?

Nó không thay thế architecture, requirements, decisions, governance hoặc
traceability.

---

## 2. Authority boundary

Authority vẫn thuộc về các nguồn canonical hiện hữu:

| Concern | Authority |
|---|---|
| Problem / requirements | `design/problems/*`, `design/requirements/*` |
| Architecture | `design/architecture/*` |
| Decisions | `design/decisions/*` |
| Executable governance | `constitution/*` |
| Trace truth | `knowledge/traceability.yaml` |
| Implementation / tests | source, test, IaC and migration files |
| Runtime observations | governed operational evidence |
| Project delivery control | `control/*` |

`control/*` MAY summarize, reference and aggregate canonical or operational
evidence.

`control/*` MUST NOT override semantic truth owned by another authority.

Example:

- roadmap MAY say `ADR-006` enables milestone M1;
- roadmap MUST NOT redefine the decision made by `ADR-006`.

---

## 3. Control artifacts

Initial Project Control Plane:

```text
control/
├── README.md
├── roadmap.md
├── project-control.yaml
├── handoff/
│   └── README.md
├── learning/
│   ├── README.md
│   └── LSN-001.yaml
└── history/
    ├── README.md
    └── CTRL-BASELINE-001.md
```

### `README.md`

Defines control semantics, authority boundaries and update rules.

### `roadmap.md`

Defines outcome-oriented phases, milestones, dependencies and exit criteria.

### `project-control.yaml`

Stores current baseline, actuals, forecast, variance, health and active project
position.

### `history/`

Stores explicit project-control snapshots or accepted rebaseline records when
a historical control state needs a durable named artifact beyond Git history.

Do not create snapshots on every trivial update.

Stores accepted baselines, material rebaselines, exceptions and explicitly
required handoff/audit snapshots.

The namespace operating contract is
[`history/README.md`](history/README.md).

### `handoff/README.md`

Defines the cross-platform handoff contract, receiver boot sequence,
verification gates, authority boundary, bounded verification circuit breaker,
clean durable-state requirements, and durable handoff-snapshot rules.

Handoff transfers context; it does not transfer or create execution authority.

See [`handoff/README.md`](handoff/README.md).

### `learning/`

Stores compact, evidence-linked Factory learning that provides provenance for
promoted rules and controls. Learning records do not create execution authority,
replace canonical design/governance, or act as runtime evidence.

See [`learning/README.md`](learning/README.md).

---

## 4. Core control invariant

For all material project-control dimensions:

```text
baseline
   ↓
actual
   ↓
forecast
   ↓
variance
```

These concepts MUST remain distinct.

Actual MUST NOT overwrite baseline.

Forecast MUST NOT be presented as commitment unless explicitly approved.

A rebaseline MUST NOT erase the previous baseline.

Git history remains the final historical record.

---

## 5. Baseline semantics

Three primary delivery controls require explicit baseline state:

```text
scope
budget
timeline
```

Each control SHALL expose:

```text
baseline_status
baseline
actual
forecast
variance
confidence
```

Allowed `baseline_status`:

```text
not_set
proposed
active
superseded
```

`not_set` is valid and preferable to invented estimates.

---

## 6. Unknown evidence

Unknown is first-class state.

The Control Plane MUST NOT transform:

```text
unknown
missing
not measured
not yet baselined
```

into zero.

Examples:

* unknown historical token usage is not `0`;
* unknown human effort is not `0 hours`;
* missing monetary provider cost is not `$0`;
* an unestimated finish date is not assumed to equal the desired date.

---

## 7. Scope control

Roadmap milestones define the current outcome-oriented scope spine.

Scope changes SHALL be classified as one of:

```text
discovery
clarification
approved_addition
approved_removal
deferred
cancelled
```

Material scope change SHOULD record:

* affected milestone;
* rationale;
* expected outcome effect;
* dependency effect;
* budget effect;
* timeline effect;
* risk effect;
* accountable approval when required.

Completed historical scope MUST NOT be rewritten.

---

## 8. Budget control

Budget is multi-dimensional.

The minimum model is:

```text
AI resource
Human effort
Infrastructure/tooling
Rework
```

AI resource SHOULD progressively measure:

* input tokens;
* output tokens;
* total tokens;
* model calls;
* implementation attempts;
* review/orchestration calls;
* monetary provider cost when exact evidence exists.

Human effort MAY measure:

* architecture/design effort;
* review effort;
* operational intervention;
* acceptance/governance effort.

Do not estimate historical AI usage merely to fill a dashboard.

---

## 9. Timeline control

Timeline SHALL distinguish:

```text
baseline window
actual dates
forecast window
variance
confidence
```

Early forecasts SHOULD use ranges rather than false precision.

Example:

```yaml
forecast:
  earliest: 2026-10-01
  latest: 2026-10-15
  confidence: low
```

A single deterministic finish date SHOULD only be used when planning evidence
justifies that precision.

---

## 10. Outcome and quality control

Delivery is not successful merely because scope, budget and timeline match a
plan.

Project success also considers:

* delivered user/system outcome;
* quality;
* reliability;
* traceability;
* governance;
* security;
* sustainability of lifecycle evolution.

A milestone cannot be marked `complete` solely because implementation files
exist.

Its roadmap exit criteria require evidence.

---

## 11. Milestone status

Allowed roadmap/control status:

```text
planned
ready
in_progress
blocked
complete
deferred
cancelled
```

Do not use arbitrary percentage completion unless a separate weighting model is
explicitly defined and approved.

`7/10 tasks complete` is evidence about task count, not proof that a milestone
is 70% complete.

---

## 12. Evidence precedence

When control state disagrees with source evidence:

```text
canonical / runtime evidence wins
```

Examples:

* merged Git state overrides a stale manual milestone status;
* deterministic tests override prose claiming verification passed;
* runtime telemetry overrides manually typed token totals;
* accepted ADR overrides a roadmap summary of the decision.

The stale control artifact should then be corrected.

---

## 13. Derived vs human-controlled fields

Prefer derivation where deterministic evidence exists.

Potentially derived:

* current Git revision;
* merged DEV list;
* test counts;
* traceability status;
* telemetry aggregates;
* model call/token usage;
* milestone evidence references.

Human-controlled:

* approved scope baseline;
* budget envelope;
* delivery commitment;
* forecast interpretation;
* risk acceptance;
* milestone outcome judgment;
* rebaseline authorization.

Automation MUST NOT silently turn a forecast into an approved baseline.

---

## 14. Update triggers

Project Control Plane SHOULD be reviewed after:

```text
material DEV merge
milestone exit
material blocker
material scope discovery
budget exception
timeline forecast change
risk/governance escalation
approved rebaseline
```

Routine code commits do not individually require control-plane edits unless
they materially change project control state.

---

## 15. Review cadence

### Continuous

* CI;
* traceability;
* runtime safety;
* telemetry;
* deterministic quality gates.

### Lightweight periodic review

* blockers;
* milestone state;
* risk;
* current forecast.

### Monthly / quarterly

* project roadmap;
* scope baseline;
* budget trend;
* timeline forecast;
* architecture health;
* policy/constitution;
* milestone relevance.

---

## 16. Rebaseline

A material rebaseline records at least:

```text
what changed
why it changed
previous baseline
new baseline
scope impact
budget impact
timeline impact
risk impact
approval
effective date
```

Never silently edit the original numbers and call them the original plan.

---

## 17. Lean rule

Do not create control data merely because a PM framework says it should exist.

A metric or artifact SHOULD exist only when it supports:

* a decision;
* a forecast;
* an acceptance gate;
* a risk control;
* a learning loop.

The Project Control Plane itself is subject to Lean waste elimination.
