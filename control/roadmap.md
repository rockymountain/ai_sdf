---
id: CTRL-ROADMAP-001
kind: project-roadmap
title: AI-Native Software Design Factory Delivery Roadmap
status: active
version: 2
owner: factory-maintainer
last_updated: 2026-09-23
change_owner: CTRL-CHANGE-007
---

# AI-Native Software Design Factory Delivery Roadmap

## 1. Purpose

Tài liệu này là delivery roadmap cấp dự án cho `ai_sdf`.

Nó trả lời liên tục các câu hỏi:

- dự án đang hướng tới outcome cuối nào;
- các delivery milestone là gì;
- milestone nào đã hoàn thành;
- milestone nào đang thực hiện;
- còn lại những capability/outcome nào;
- milestone nào phụ thuộc milestone nào;
- mỗi milestone được xem là hoàn thành bằng evidence nào;
- milestone ánh xạ vào Phase kiến trúc nào;
- scope, budget, timeline và forecast của dự án đang thay đổi như thế nào.

Roadmap này là một phần của Project Control Plane.

Nó MUST NOT trở thành nguồn authority cạnh tranh với:

- `design/problems/*`
- `design/requirements/*`
- `design/architecture/*`
- `design/decisions/*`
- `constitution/*`
- `knowledge/traceability.yaml`

Roadmap MAY tổng hợp trạng thái từ các nguồn trên nhưng MUST NOT thay đổi
semantic truth của chúng.

---

# 2. Project mission

Mục tiêu của `ai_sdf` là xây dựng một AI-Native Software Design Factory có khả
năng:

> Biến một idea phần mềm thô thành một software design hoàn chỉnh, governed,
> verified và development-ready; sau đó tiếp tục duy trì liên kết giữa intent,
> implementation, runtime evidence, learning và evolution trong toàn bộ vòng đời
> sản phẩm.

Target lifecycle:

```text
Idea
  ↓
Frame
  ↓
Specify
  ↓
Model
  ↓
Decide
  ↓
Design
  ↓
Verify
  ↓
Approve
  ↓
Implement
  ↓
Observe
  ↓
Learn
  ↓
Evolve
```

Factory không được tối ưu riêng cho code generation.

Success cuối cùng đòi hỏi hệ thống duy trì được vòng kín:

```text
Intent
  ↓
Design
  ↓
Implementation
  ↓
Runtime Reality
  ↓
Evidence / Learning
  ↓
Evolution
  └──────────────→ Intent
```

---

# 3. Project-control model

Delivery được kiểm soát tối thiểu qua ba trục:

```text
Scope
Budget
Timeline
```

Nhưng project success không được đánh giá chỉ bằng ba trục đó.

Project health còn phải xem tối thiểu:

```text
Outcome / Value
Quality
Risk / Governance
```

Do đó Project Control Plane sử dụng sáu dimension:

| Dimension         | Câu hỏi kiểm soát                                                      |
| ----------------- | ---------------------------------------------------------------------- |
| Scope             | Chúng ta đã cam kết build những outcome nào và còn lại gì?             |
| Budget            | Đã tiêu bao nhiêu resource và forecast còn bao nhiêu?                  |
| Timeline          | Đã mất bao lâu và forecast completion hiện tại là gì?                  |
| Outcome           | Capability được giao có thực sự giải quyết mục tiêu dự án không?       |
| Quality           | Evidence có chứng minh correctness/reliability đủ mức yêu cầu không?   |
| Risk / Governance | Có violation, unresolved risk hoặc human decision nào chưa đóng không? |

Mỗi dimension SHOULD phân biệt:

```text
baseline
actual
forecast
variance
```

Roadmap không rewrite lịch sử để làm cho actual trông giống plan.

---

# 4. Control states

Milestone status sử dụng vocabulary:

```text
planned
ready
in_progress
blocked
complete
deferred
cancelled
```

Ý nghĩa:

* `planned`: nằm trong roadmap nhưng chưa đủ Ready;
* `ready`: dependencies và exit intent đủ rõ để bắt đầu;
* `in_progress`: delivery đang diễn ra;
* `blocked`: không thể tiếp tục nếu chưa có resolution;
* `complete`: exit criteria đã có evidence;
* `deferred`: intentionally moved beyond current planning horizon;
* `cancelled`: outcome không còn được theo đuổi.

Không dùng percentage-complete giả precision cho milestone.

---

# 5. Current project position

Current repository state is derived from Git at verification/use time:

```text
branch:
  git branch --show-current

revision:
  git rev-parse HEAD
```

Current project position:

```text
Phase 0:
  complete

Phase 1:
  in_progress

Latest completed milestone:
  M2 — Bounded Autonomous Execution

Current milestone:
  M3 — AI Cost Control Baseline
  status: in_progress
  actual measurement window: not_started
```

Current measurement maturity:

```text
scope:
  baseline active — CTRL-BASELINE-001

budget:
  baseline active; actual project-wide coverage remains incomplete

timeline:
  baseline active

quality:
  deterministic baseline available

governance:
  deterministic + human gates available
```

Historical AI usage before automatic telemetry remains incomplete and MUST NOT
be retroactively estimated as zero.

---

# 6. Delivery roadmap overview

| ID  | Milestone                          | Phase     | Status   | Primary delivery outcome                                                                         |
| --- | ---------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------ |
| M0  | Governed Foundation                | Phase 0   | complete | Canonical, traceable, reproducible and human-governed engineering foundation                     |
| M1  | Metered AI Runtime                 | Phase 1.0 | complete | Every controlled AI invocation can be bounded, attributed and measured                           |
| M2  | Bounded Autonomous Execution       | Phase 1.0 | complete | Autonomous implementation cannot exceed governed attempt/circuit limits |
| M3  | AI Cost Control Baseline           | Phase 1.1 | in_progress | Reliable chat-heavy control window establishes cost/quality baseline                          |
| M4  | Efficient Context                  | Phase 1.1 | planned  | Context optimization is accepted or rejected using measured ROI                                  |
| M5  | Efficient Model / Reasoning        | Phase 1.1 | planned  | Model/reasoning optimization is independently measured                                           |
| M6  | Proven Bounded Automation          | Phase 1   | planned  | Independently proven treatments combine into bounded AI-assisted execution                       |
| M7  | Idea → Design-Ready Factory        | Phase 2   | planned  | Raw idea can become a governed, controllable, handoff-reconstructable project and reach Design Done |
| M8  | Governed Engineering Intelligence  | Phase 2   | planned  | Impact analysis, evaluators and specialist capabilities operate under evidence-driven governance |
| M9  | Reality & Runtime Feedback         | Phase 2   | planned  | Implementation/runtime reality is linked back to design intent                                   |
| M10 | Closed Evolution Loop              | Phase 2/3 | planned  | Runtime evidence can trigger governed design evolution                                           |
| M11 | Factory Control Plane              | Phase 3   | planned  | Runtime, policy, evaluation, graph, audit and control services operate beyond one workstation    |
| M12 | Multi-Project / Organization Scale | Phase 3   | planned  | Factory supports cross-repo ownership, policy and evolution                                      |
| H1  | Living Software Design System      | Horizon   | planned  | Intent, Reality and Evolution remain continuously synchronized                                   |
| H2  | Adaptive Factory                   | Horizon   | planned  | Factory improves its own governed process based on measured evidence                             |

---

# 7. Milestone definitions

## M0 — Governed Foundation

**Phase:** Phase 0
**Status:** complete

### Outcome

Establish a deterministic and traceable foundation on which later AI autonomy
can safely operate.

### Delivered capabilities

* canonical structured artifacts;
* stable artifact identities and lifecycle status;
* T0/T1/T2 risk classification;
* forward/backward traceability;
* implementation-path validation;
* reverse PR provenance;
* executable QG-004;
* deterministic CI;
* human PR gate;
* reproducible validation environment;
* derived `AGENTS.md` reproducibility.

### Exit evidence

Phase 0 closure evidence accepted and immutable.

### Dependencies

None.

---

## M1 — Metered AI Runtime

**Phase:** Phase 1.0
**Status:** complete

### Outcome

Create a single controlled AI runtime boundary where every governed invocation
can be measured and finitely bounded.

### Delivered capabilities

* `ControlledAIInvocation`;
* `AIRuntimePort`;
* `CodexRuntimeAdapter`;
* provider-neutral runtime boundary;
* canonical finite watchdog;
* `max_invocation_seconds = 600`;
* exact-or-unknown token evidence;
* runtime identity correlation;
* read-only non-attempt execution;
* SQLite operational evidence;
* deterministic DEV aggregation;
* immutable DEV outcome finalization;
* reproducible telemetry export;
* live tool-bearing acceptance evidence.

### Exit evidence

`DEV-007` implemented, verified and merged.

Merged baseline:

```text
f269bb29d5f7bc91a677b6ec4d46dedbffc877dd
```

### Dependencies

M0.

---

## M2 — Bounded Autonomous Execution

**Phase:** Phase 1.0
**Status:** complete

### Outcome

Ensure autonomous implementation work cannot exceed a deterministic execution
budget.

### Required capabilities

* canonical `MAX_ATTEMPTS = 2`;
* execution-scope attempt budget;
* reservation lifecycle;
* `RESERVED → CONSUMED`;
* attempt lifecycle;
* one-open-attempt invariant;
* restart-safe state;
* concurrency-safe reservation;
* second-failure circuit opening;
* circuit persistence before new implementation work;
* blocked invocation must never reach runtime;
* reconciliation state for uncertain execution;
* governed human-authorized continuation;
* successor-scope anti-bypass;
* immutable predecessor evidence.

### Exit criteria

M2 is complete only when deterministic evidence proves:

```text
attempt 1 failure
        ↓
attempt 2 allowed

attempt 2 failure
        ↓
CIRCUIT_OPEN persisted

CIRCUIT_OPEN
        ↓
next autonomous implementation invocation blocked
        ↓
AIRuntimePort invocation count unchanged
```

and restart/concurrency cannot bypass the same execution-scope budget.

### Exit evidence

`DEV-008` implemented, verified and merged via PR #11.

Merged revision:

```text
b2339e15c7f367570c6b9e420359772739c0d50f
```

### Intended implementation mapping

```text
DEV-008
```

### Dependencies

M1.

---

## M3 — AI Cost Control Baseline

**Phase:** Phase 1.1
**Status:** in_progress

### Outcome

Create a decision-grade control baseline for current chat-heavy AI-assisted work.

### Required capabilities

* declared measurement window;
* comparable task mix;
* accepted/rejected DEV outcomes;
* complete usage coverage;
* input tokens / accepted DEV;
* total tokens / accepted DEV;
* model calls / accepted DEV;
* attempts / accepted DEV;
* acceptance rate;
* breakdown by T0/T1/T2;
* quality/governance observations;
* baseline model/reasoning/context strategy recorded.

### Exit criteria

A baseline measurement window is complete and reproducible.

Exact token KPI is decision-eligible only when all contributing accepted DEV
tasks have complete usage.

### Dependencies

M2.

---

## M4 — Efficient Context

**Phase:** Phase 1.1
**Status:** planned

### Outcome

Determine whether a structured context strategy materially reduces AI resource
cost without degrading engineering quality or governance.

### Candidate treatments

* manual context pack;
* Graphify context pack;
* other explicitly declared context treatment.

### Acceptance constraint

For the declared Graphify/context treatment:

```text
average input-token reduction >= 70%
```

against comparable chat-heavy baseline.

Savings MUST NOT override:

* quality;
* security;
* governance;
* acceptance rate;
* escaped defects.

### Decision outcomes

```text
promote
redesign
reject/remove
```

### Dependencies

M3.

---

## M5 — Efficient Model / Reasoning

**Phase:** Phase 1.1
**Status:** planned

### Outcome

Determine the least expensive model/reasoning profile capable of satisfying
quality and risk constraints for a class of work.

### Experiment rule

Context strategy MUST remain fixed while model/reasoning treatment changes.

### Measures

* input/output tokens;
* task acceptance;
* retries;
* deterministic-gate failure;
* human review effort;
* quality/governance regression;
* monetary cost where available.

### Dependencies

M3.

Independent from M4 treatment evaluation.

---

## M6 — Proven Bounded Automation

**Phase:** Phase 1
**Status:** planned

### Outcome

Combine only independently proven runtime, context and model treatments into a
bounded AI-assisted delivery flow.

### Required capabilities

* deterministic attempt/circuit protection;
* cost attribution;
* accepted context treatment;
* accepted model/reasoning treatment;
* deterministic gates;
* human accountability;
* no unlimited retry;
* no hidden provider dependency.

### Non-goal

Broad multi-agent orchestration without measured need.

### Dependencies

M2 plus accepted results from M3–M5 as applicable.

---

## M7 — Idea → Design-Ready Factory

**Phase:** Phase 2  
**Status:** planned

### Outcome

Prove that a raw software idea can become a governed, controllable,
handoff-reconstructable project and progress through the SDF lifecycle to
Design Done.

M7 MUST establish that project governance begins at project initialization,
not only after requirements, design, or implementation artifacts already
exist.

### Deferred evolution inputs

The following lessons learned from `ai_sdf` dogfooding are intentionally
deferred to M7 for formal requirements, architecture, decision, implementation,
and verification work:

- `SDF-PC-I01` — Every governed SDF project MUST establish a Project Control
  surface at project initialization. The control surface MUST represent current
  scope, budget, timeline, outcome, quality, and risk state without inventing
  unknown values.

- `SDF-PC-I02` — Project Control MUST exist before autonomous delivery work is
  authorized.

- `SDF-PC-I03` — A governed SDF project MUST be handoff-reconstructable without
  relying on chat history or provider-specific memory.

These entries are `deferred_evolution_inputs`, not current executable policy,
template, schema, or implementation requirements.

### Required capabilities

M7 MUST prove the capability to:

- bootstrap Project Control from a raw project idea;
- represent scope, budget, and timeline honestly, including `not_set` and
  `unknown` states;
- establish outcome, quality, and risk control from project initialization;
- prevent autonomous delivery from starting before required project-control
  state exists;
- support project handoff/reconstruction without dependency on prior chat
  history, one AI provider, one model session, or one workstation;
- progressively elaborate project-control state without fabricating precision;
- continue from governed project initialization through the existing SDF
  lifecycle to Design Done.

`ai_sdf/control/*` is the current dogfood/reference implementation that informs
this milestone. M7 MUST NOT assume that its exact current directory layout or
file structure is already the universal SDF project-bootstrap contract.

### Exit criteria

M7 is not complete until evidence demonstrates that:

1. a raw idea can initialize a governed project-control surface;
2. scope, budget, and timeline can begin as `not_set` or `unknown` without
   fabricated values;
3. an accountable human can establish and approve the initial delivery
   baseline;
4. autonomous delivery cannot begin before the required control state and
   authorization exist;
5. a new human/agent/session can reconstruct material project context without
   previous chat history or provider-specific memory;
6. the project can progress from that governed bootstrap state through
   requirements, design, decision, verification, and approval to Design Done;
7. the generic bootstrap contract is extracted from observed project evidence
   rather than copied mechanically from the current `ai_sdf/control/`
   implementation.

### Acceptance test

Use at least one representative raw product idea as a governed end-to-end
Patient Zero.

### Dependencies

M6.

---

## M8 — Governed Engineering Intelligence

**Phase:** Phase 2
**Status:** planned

### Outcome

Add higher-level engineering intelligence only where evidence shows value.

### Candidate capabilities

* semantic impact analysis;
* architecture critic;
* security critic;
* data/reliability specialist;
* agent evaluation harness;
* additional executable fitness functions;
* requirement/design consistency checks.

### Constraint

Specialist agents MUST NOT be added merely for role richness.

Each capability requires measurable value or risk reduction.

### Dependencies

M7 foundation and measured demand.

---

## M9 — Reality & Runtime Feedback

**Phase:** Phase 2
**Status:** planned

### Outcome

Connect design intent to the software that actually exists and runs.

### Required capabilities

Reality observations MAY include:

* repository structure;
* implementation dependencies;
* DB/schema/migrations;
* deployed infrastructure;
* runtime topology;
* telemetry;
* SLOs;
* incidents;
* drift observations.

### Required questions

Factory must increasingly answer:

```text
What was intended?
What was built?
What is running?
Where do they differ?
```

### Constraint

Reality/Context Graph is derived evidence.

It MUST NOT replace canonical design intent.

### Dependencies

M7.

---

## M10 — Closed Evolution Loop

**Phase:** Phase 2 / Phase 3
**Status:** planned

### Outcome

Runtime evidence can trigger governed changes to software design without losing
history or accountability.

### Target loop

```text
Intent
  ↓
Implementation
  ↓
Runtime evidence
  ↓
Drift / incident / learning
  ↓
Change proposal
  ↓
Design evolution
  ↓
new governed implementation
```

### Required capabilities

* drift findings;
* debt findings;
* runtime feedback;
* change proposals;
* impact analysis;
* evolution provenance;
* preserved predecessor history;
* human authorization for material decisions.

### Dependencies

M9.

---

## M11 — Factory Control Plane

**Phase:** Phase 3
**Status:** planned

### Outcome

Move factory control capabilities beyond one developer workstation when scale
actually requires it.

### Candidate services

* Agent Runtime Interface/adapters;
* capability/runtime routing;
* policy evaluation;
* agent evaluation;
* context/reality graph services;
* audit/observability;
* project-control reporting;
* experiment measurement;
* multi-client interfaces.

### Clients MAY include

* VS Code;
* CI;
* CLI;
* web;
* other IDEs.

### Constraint

Do not centralize prematurely.

Extraction must be justified by scaling or operational evidence.

### Dependencies

M6–M10 as applicable.

---

## M12 — Multi-Project / Organization Scale

**Phase:** Phase 3
**Status:** planned

### Outcome

Apply governed SDF capabilities across multiple repositories/products without
losing local product ownership.

### Candidate capabilities

* cross-repo dependency/evolution graph;
* organization policy;
* shared standards;
* ownership model;
* reusable contracts;
* cross-project impact analysis;
* portfolio-level cost/quality metrics.

### Dependencies

M11.

---

# 8. Long-term horizons

## H1 — Living Software Design System

**Status:** planned

### Outcome

Intent, implementation reality and evolution knowledge remain continuously
connected over the software lifecycle.

Target conceptual model:

```text
Intent Graph
     ↕
Reality Graph
     ↕
Evolution Graph
```

This is not considered complete merely because a graph database exists.

Success requires trusted traceability and actionable lifecycle feedback.

---

## H2 — Adaptive Factory

**Status:** planned

### Outcome

The Factory can improve its own engineering workflow based on measured
evidence without violating human authority.

Examples:

* identify expensive context strategies;
* identify recurring design defects;
* propose deterministic checks;
* retire low-value agent workflows;
* adapt routing policy;
* detect process bottlenecks;
* recommend experiment candidates.

Material changes to governance remain human-approved.

---

# 9. Cross-milestone success measures

Roadmap success is not measured by number of artifacts, prompts or agents.

Project-level indicators SHOULD progressively include:

## Delivery

* idea-to-design lead time;
* design-to-implementation lead time;
* milestone throughput;
* forecast variance.

## Quality

* rework rate;
* escaped design defects;
* change failure rate;
* acceptance rate.

## Traceability / Governance

* orphan material changes;
* policy violations;
* architecture drift;
* unresolved exceptions;
* human override rate.

## AI economics

* input tokens / accepted DEV;
* total tokens / accepted DEV;
* model calls / accepted DEV;
* attempts / accepted DEV;
* cost / accepted DEV when monetary evidence exists.

## Human economics

* human review effort;
* operator interventions;
* architecture decision effort.

## Lifecycle health

* drift count and age;
* debt age/concentration;
* runtime-feedback-to-change lead time;
* design freshness against running reality.

Metric introduction SHOULD follow actual measurement capability.

Unknown values MUST remain unknown rather than being manufactured.

---

# 10. Scope-control rules

Roadmap scope can evolve.

A scope change MUST distinguish:

```text
discovery
clarification
approved scope addition
approved scope removal
deferment
cancellation
```

Material scope changes MUST update:

* affected milestone;
* reason;
* expected outcome;
* dependencies;
* budget forecast;
* timeline forecast;
* risk;
* approval when required.

Completed historical scope MUST NOT be rewritten.

---

# 11. Budget-control rules

Budget is multi-dimensional.

Minimum future control model:

```text
AI resource:
  input tokens
  output tokens
  model calls
  attempts

Human resource:
  review effort
  architecture/operator effort

Infrastructure/tooling:
  monetary spend when observable

Rework:
  failed/rejected work
  retries
  correction effort
```

Initial state:

```text
Phase 0:
  AI usage coverage = incomplete

DEV-007 onward:
  automatic AI usage evidence = available
```

No historical token values are to be retroactively estimated.

---

# 12. Timeline-control rules

Timeline must distinguish:

```text
baseline
actual
forecast
variance
confidence
```

Early-stage estimates SHOULD use ranges rather than invented precision.

Example:

```yaml
baseline_window:
  earliest: null
  latest: null

forecast_window:
  earliest: null
  latest: null

confidence: low
```

Forecast quality SHOULD improve as milestone throughput evidence accumulates.

---

# 13. Update cadence

Project Control Plane SHOULD be updated at natural control points rather than
through heavy PM ceremony.

Mandatory update triggers:

```text
accepted/merged material DEV
milestone completion
material blocker
material scope change
approved rebaseline
```

Review cadence:

```text
continuous:
  CI
  traceability
  runtime safety
  telemetry

weekly/lightweight:
  delivery risk
  blockers
  forecast

monthly/quarterly:
  roadmap
  architecture health
  budget trend
  policy/constitution
  milestone reforecast
```

---

# 14. Baseline and rebaseline policy

Never silently overwrite a baseline.

Maintain conceptually:

```text
original_baseline
current_approved_baseline
actual
current_forecast
variance
```

A rebaseline MUST state:

* what changed;
* why;
* approving actor;
* date;
* affected scope;
* affected budget;
* affected timeline.

The previous baseline remains historically recoverable through Git.

---

# 15. Current next decision

Current roadmap position:

```text
M0  COMPLETE
M1  COMPLETE
M2  COMPLETE
M3  IN_PROGRESS
```

Delivered under CTRL-CHANGE-007:

```text
DEV-012 — durable controlled-runtime operator authorization and adoption
status: IMPLEMENTED
verification: TEST-012 VERIFIED
live adoption gate: PASSED as a separately authorized PRE-WINDOW proof
```

Current next decision:

```text
prospective M3 measurement-window declaration and fixed task-set selection
concrete next DEV: not yet selected
```

The initial Project Control Baseline remains established and active:

```text
CTRL-BASELINE-001
```

M2 / DEV-008 completed under CTRL-BASELINE-001.

DEV-009 subsequently generalized repository change provenance and merged via
PR #12 at:

```text
63fc3f2de53631dc1d6e32f3e1600a3cd9623afc
```

CTRL-CHANGE-006 activates M3 delivery without marking the cost-control baseline
proven or complete. It does not rebaseline the project and does not start M4.

CTRL-CHANGE-007 approves ADR-007 and delivers the bounded DEV-012 implementation
while closing the already delivered DEV-011 capability. The separately authorized
PRE-WINDOW live provider adoption proof passed and proves generic controlled-runtime
operator adoption; it is not M3 baseline evidence. The actual M3 measurement window
has not started, the cost-control baseline is not yet proven, the exact M3 token KPI
is not decision-eligible, and M4 remains planned and unauthorized.
