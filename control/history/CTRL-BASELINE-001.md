---
id: CTRL-BASELINE-001
kind: project-baseline
title: AI-Native SDF Initial Delivery Baseline
status: accepted
version: 1
owner: factory-maintainer
effective_date: 2026-09-21
approving_actor: project-owner
---

# AI-Native SDF Initial Delivery Baseline

## 1. Purpose

Thiết lập project-control baseline đầu tiên cho `ai_sdf`.

Baseline này khóa các giả định delivery hiện tại về:

- scope;
- human delivery capacity;
- resource/budget model;
- M2 / DEV-008 effort và timeline;
- Remaining Phase 1 effort và timeline;
- quality/governance constraints;
- uncertainty và risk.

Baseline này không thay thế architecture, requirements, ADR, executable
governance hoặc traceability authority.

## 2. Baseline basis

Repository baseline:

```text
main
f269bb29d5f7bc91a677b6ec4d46dedbffc877dd
```

Delivery state tại thời điểm baseline:

```text
M0 — Governed Foundation             COMPLETE
M1 — Metered AI Runtime              COMPLETE
M2 — Bounded Autonomous Execution    READY
```

Roadmap:

```text
control/roadmap.md
CTRL-ROADMAP-001
```

Current project-control state:

```text
control/project-control.yaml
CTRL-PROJECT-001
```

## 3. Scope baseline

### Completed

- M0 — Governed Foundation
- M1 — Metered AI Runtime

### Committed near-term

- M2 — Bounded Autonomous Execution

### Planned Phase 1

- M3 — AI Cost Control Baseline
- M4 — Efficient Context
- M5 — Efficient Model / Reasoning
- M6 — Proven Bounded Automation

### Product roadmap

- M7 — Idea → Design-Ready Factory
- M8 — Governed Engineering Intelligence
- M9 — Reality & Runtime Feedback
- M10 — Closed Evolution Loop
- M11 — Factory Control Plane
- M12 — Multi-Project / Organization Scale

### Strategic horizon

- H1 — Living Software Design System
- H2 — Adaptive Factory

M7–M12 thuộc project roadmap scope nhưng không phải current budget/date
commitment.

H1/H2 là strategic horizons và không mang delivery commitment trong baseline
này.

## 4. Human delivery capacity

Project owner xác nhận near-term focused capacity:

```text
minimum committed:
  6 focused hours/day
  7 days/week
  = 42 focused hours/week

target operating level:
  average 8 focused hours/day
  7 days/week
  = 56 focused hours/week
```

Planning basis:

```text
committed planning capacity:
  42 focused hours/week

target operating capacity:
  56 focused hours/week
```

Forecast chính thức MUST dùng committed capacity làm planning basis. Target
capacity là upside capacity và MUST NOT được coi là guaranteed.

## 5. Resource accounting model

Delivery resource accounting phân biệt năm resource classes.

### Human accountable effort

Bao gồm:

- problem framing;
- architecture judgment;
- material trade-off decisions;
- risk acceptance;
- governance decisions;
- review/audit;
- acceptance;
- Git/operator work.

### Interactive AI reasoning

Bao gồm human-AI collaboration dùng cho:

- framing;
- invariant discovery;
- architecture reasoning;
- synthesis;
- review;
- audit;
- control design.

Interactive AI reasoning không được gộp vào human effort và cũng không được
đồng nhất với execution-agent cost.

### AI agent execution

Bao gồm execution-oriented AI activity như:

- implementation;
- test generation/execution;
- bounded correction;
- execution review;
- orchestration.

### Infrastructure/tooling

Bao gồm measurable repository/runtime/cloud/tool resource hoặc monetary cost.

### Rework

Theo dõi correction effort attributable to failed, rejected hoặc incomplete
work, bao gồm human, interactive-AI và execution-agent resource khi đo được.

## 6. Historical resource observations

### Phase 0 through DEV-006

Human accountable effort:

```text
measurement_status: not_measured
qualitative_observation: high
```

Project-owner observation:

> Significant human architecture, reasoning, review and decision effort was
> required before relatively bounded execution could be delegated to the AI
> execution agent.

Interactive AI reasoning:

```text
measurement_status: not_measured
qualitative_observation: high
```

AI execution-agent usage:

```text
measurement_status: incomplete
```

Historical missing usage MUST remain unknown and MUST NOT be inferred as zero.

### DEV-007

Human accountable effort:

```text
measurement_status: not_measured
qualitative_observation: high
```

Interactive AI reasoning:

```text
measurement_status: not_measured
qualitative_observation: high
```

Controlled runtime evidence exists for one governed live invocation. That
evidence MUST NOT be interpreted as total DEV-007 AI delivery cost.

## 7. M2 / DEV-008 planning baseline

Milestone:

```text
M2 — Bounded Autonomous Execution
DEV-008
```

### Human-effort envelope

| Work class | Accepted planning range |
|---|---:|
| Architecture / decision refinement | 2–4 focused hours |
| Review / audit / acceptance | 4–8 focused hours |
| Git / operator / PR | 1–2 focused hours |
| **Total human accountable effort** | **7–14 focused hours** |

Confidence: `medium-low`.

### AI execution planning guardrail

```text
maximum autonomous implementation cycles:
  2
```

This is a project-level planning guardrail until M2 itself proves runtime
enforcement.

### Interactive AI reasoning

```text
measurement_mode: prospective
numeric_budget: not_set
```

Prospective control SHOULD record at least reasoning/review sessions and major
design-review cycles per accepted DEV until exact usage/cost telemetry is
available for this resource class.

### Calendar forecast

Accepted forecast window:

```text
earliest completion:
  2026-09-23

latest completion:
  2026-09-25

confidence:
  medium
```

This is a forecast window, not a single-date deadline.

## 8. Remaining Phase 1 planning baseline

Remaining milestones:

```text
M2
M3
M4
M5
M6
```

Accepted human engineering-effort envelope:

```text
45–90 focused hours
```

Confidence: `low`.

Accepted calendar forecast:

```text
earliest:
  2026-10-05

latest:
  2026-10-19

confidence:
  low
```

Primary uncertainty drivers:

- M2 T2 correctness;
- M3 measurement-window design;
- comparable accepted DEV throughput;
- context/Graphify experiment result;
- model/reasoning experiment result;
- T2 rework;
- current human review/cognitive load.

The Phase 1 forecast is not a delivery commitment.

## 9. M3–M6 estimation policy

### M3 — AI Cost Control Baseline

```text
estimate_status: dependency_bound
primary_driver: comparable accepted DEV measurement window
```

### M4 — Efficient Context

```text
estimate_status: pending_M3
```

Outcome may be `promote`, `redesign`, or `reject/remove`.

### M5 — Efficient Model / Reasoning

```text
estimate_status: pending_M3
```

Model/reasoning treatment must be evaluated independently from context treatment
where the experiment claims independent effect.

### M6 — Proven Bounded Automation

```text
estimate_status: pending_M4_M5_evidence
```

Do not elaborate broad orchestration scope before treatment evidence is known.

## 10. Beyond Phase 1

M7–M12 remain roadmap scope with progressive elaboration:

```text
numeric_effort_baseline: not_set
timeline_commitment: not_set
```

H1/H2 remain strategic horizons:

```text
delivery_commitment: none
```

No whole-project completion date is established by this baseline.

## 11. Budget baseline

### Human accountable effort

```text
M2:
  7–14 focused hours

remaining Phase 1:
  45–90 focused hours
```

### Interactive AI reasoning

```text
historical_coverage: incomplete
prospective_measurement: active
token_budget: not_set
monetary_budget: not_set
```

### AI agent execution

```text
M2 autonomous implementation cycles:
  maximum 2

token budget:
  not_set

monetary budget:
  not_set
```

`not_set` means insufficient evidence for a useful numeric envelope. It does
not mean unlimited.

### Infrastructure/tooling

```text
monetary baseline:
  not_set
```

## 12. Timeline baseline

```text
planning capacity:
  committed: 42 focused hours/week
  target: 56 focused hours/week

M2:
  2026-09-23 → 2026-09-25
  confidence: medium

remaining Phase 1:
  2026-10-05 → 2026-10-19
  confidence: low

whole project:
  no completion-date commitment
```

## 13. Quality and governance constraints

Budget or schedule savings MUST NOT weaken:

- deterministic quality;
- traceability;
- required governance;
- security;
- human accountability;
- bounded autonomous execution;
- acceptance evidence.

A milestone that finishes early by bypassing required evidence is not a
successful delivery.

Current accepted quality baseline at the repository revision above:

```text
traceability:
  34 artifacts PASS

deterministic tests:
  86 passed
  0 failed

QG-004:
  PASS

AGENTS reproducibility:
  PASS
```

## 14. Initial material risks

### RISK-CTRL-001 — Human cognitive load

Severity: `high`.

Factory currently depends heavily on human + interactive AI reasoning for
invariant discovery, architecture synthesis and semantic audit.

### RISK-CTRL-002 — Interactive AI cost visibility

Severity: `medium`.

Interactive reasoning resource is not yet fully metered.

### RISK-CTRL-003 — Experimental Phase-1 duration

Severity: `medium`.

M3–M5 depend on measurement windows and experiment outcomes.

### RISK-CTRL-004 — Historical cost incompleteness

Severity: `low`.

Reliable project-wide Phase-0 cost reconstruction is unavailable. Preserve
unknown rather than inventing historical totals.

### RISK-CTRL-005 — Executor-only optimization

Severity: `high`.

Optimizing execution-agent tokens alone may reduce visible executor cost while
leaving total human/reasoning delivery cost high.

## 15. Success measures beginning with DEV-008

### Human economics

- human accountable hours / accepted DEV;
- review + audit hours / accepted DEV;
- operator hours / accepted DEV;
- human low-leverage effort / accepted DEV.

### Interactive AI economics

- reasoning/review sessions / accepted DEV;
- exact usage/cost when measurable.

### Execution-agent economics

- input tokens / accepted DEV;
- total tokens / accepted DEV;
- calls / accepted DEV;
- attempts / accepted DEV;
- acceptance rate.

### Rework

- human correction effort;
- interactive AI correction cycles where measurable;
- failed agent-attempt resource.

### Delivery

- DEV elapsed lead time;
- milestone elapsed lead time;
- forecast variance.

## 16. Factory learning objective

A mature SDF SHOULD progressively shift resource use from repeated manual
synthesis, consistency checking, context reconstruction, evidence gathering and
routine orchestration toward:

- human intent;
- material trade-offs;
- risk acceptance;
- accountability.

Success does not mean eliminating human involvement.

Success means increasing the ratio of high-value human judgment while reducing
low-leverage human coordination and repetitive reasoning effort.

## 17. Rebaseline policy

Variance does not automatically create a rebaseline.

A material rebaseline is required when an underlying baseline assumption
changes materially, including:

- material scope expansion/reduction;
- new mandatory milestone;
- material capacity change;
- experiment architecture change;
- material newly discovered risk;
- material resource/budget-model change.

The next material rebaseline artifact will use the `CTRL-REBASELINE-NNN`
namespace and preserve this accepted baseline through Git/history.

## 18. Approval record

Decision: `APPROVED`.

Effective date: `2026-09-21`.

Approving actor role: `project-owner`.

Accepted ranges:

```text
M2 Human Effort:
  7–14 focused hours

M2 Timeline Forecast:
  2026-09-23 → 2026-09-25

Remaining Phase 1 Human Effort:
  45–90 focused hours

Remaining Phase 1 Timeline Forecast:
  2026-10-05 → 2026-10-19
```

This accepted baseline is the active control reference until superseded by an
explicit governed rebaseline.
