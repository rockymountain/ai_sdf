---
id: SDF-ROADMAP
type: reference-roadmap
status: proposed
author: SDF-Orchestrator
title: "AI-Native Software Design Factory — Full Roadmap"
subtitle: "From Raw Idea to Development-Ready Design, Living Engineering System, and Adaptive Factory"
version: "1.0"
date: "19/09/2026"
lang: vi-VN
baseline_tag: phase0-complete
baseline_sha: f8a1a0a71fca25caee80003f37250eb3b7d5ce4b
architecture_authority: docs/reference/ai-native-sdf-reference-architecture.md
---

# AI-Native Software Design Factory — Full Roadmap

## Thông tin tài liệu

| Thuộc tính | Giá trị |
|---|---|
| ID | `SDF-ROADMAP` |
| Vai trò | Execution roadmap companion |
| Baseline | `phase0-complete` |
| Baseline SHA | `f8a1a0a71fca25caee80003f37250eb3b7d5ce4b` |
| Architecture authority | `docs/reference/ai-native-sdf-reference-architecture.md` |
| Decision authority | `design/decisions/ADR-*` |
| Executable governance authority | `constitution/*` |
| Trace truth | `knowledge/traceability.yaml` |
| Trạng thái | Proposed roadmap after Phase 0 closure |

## Quy ước chuẩn tắc

Trong tài liệu này:

- **MUST**: bắt buộc để duy trì invariant, safety hoặc governance.
- **SHOULD**: mặc định nên thực hiện; deviation cần lý do rõ ràng.
- **MAY**: tùy chọn theo evidence/context.

Tài liệu này mô tả **thứ tự tiến hóa và acceptance gates**. Nó MUST NOT thay thế Reference Architecture, ADR, executable governance hoặc trace truth.

---

# 1. Executive Summary

AI-Native Software Design Factory (SDF) được xây để biến software engineering từ một chuỗi hoạt động rời rạc thành một **living engineering system**:

```text
Raw Idea
   ↓
Problem / Outcome
   ↓
Requirement / NFR
   ↓
Architecture / Design
   ↓
Decision / Contract / Threat
   ↓
Verified Design Baseline
   ↓
DEV Task Decomposition
   ↓
Development-Ready Handoff
   ↓
Implementation
   ↓
Runtime Evidence
   ↓
Learning
   ↓
Evolution
```

Mục tiêu dài hạn không phải để AI “tự thiết kế software”, mà để Factory:

1. duy trì canonical truth và traceability xuyên suốt vòng đời;
2. dùng deterministic computation trước AI judgment;
3. sử dụng AI có budget, telemetry, permissions và evaluation;
4. giữ human accountability ở các decision irreversible/high-risk;
5. tạo ra design increment đủ rõ, đủ kiểm chứng và đủ trace để Development có thể bắt đầu;
6. đưa runtime evidence trở lại design process;
7. tự cải tiến Factory bằng Lean + PDCA mà không biến automation thành source of truth.

Roadmap được chia thành:

```text
Origin / Idea
    ↓
Phase -1 — Vision & Architecture Framing
    ↓
Phase 0 — Deterministic Foundation                 [CLOSED]
    ↓
Phase 1 — Bounded, Cost-Aware AI Execution
    ↓
Phase 2 — Governed Agentic Flow
    ↓
Phase 3 — Factory Control Plane
    ↓
Phase 4 — Living Engineering System               [Post-Phase-3 horizon]
    ↓
Phase 5 — Adaptive Factory                         [Long-term horizon]
```

Phase 0 đã được đóng tại:

```text
tag: phase0-complete
SHA: f8a1a0a71fca25caee80003f37250eb3b7d5ce4b
```

---

# 2. North Star

North Star của SDF là:

> **Một raw idea có thể đi qua một governed, traceable, evidence-driven flow và trở thành một approved design increment sẵn sàng để Development triển khai, sau đó tiếp tục sống cùng runtime evidence và system evolution.**

## 2.1 Definition of Development-Ready Design

Một design increment được coi là `DESIGN_READY` khi:

```text
Problem / Outcome rõ
AND scope rõ
AND assumptions / unknowns được ghi nhận
AND FR/NFR testable
AND architecture model cập nhật
AND required ADR accepted
AND required API/Event/Data contracts valid
AND required security/reliability analysis complete
AND migration/rollback defined khi applicable
AND observability/runtime verification intent defined
AND DEV tasks decomposed
AND tests/verification mapped
AND traceability valid
AND deterministic gates pass
AND mandatory human gates approved
```

`DESIGN_READY` không có nghĩa thiết kế “hoàn hảo” hoặc frozen. Nó có nghĩa design increment đủ bounded, accountable và verifiable để downstream development bắt đầu.

---

# 3. Roadmap operating model

## 3.1 Evidence-gated, không calendar-gated

Roadmap SHOULD dùng evidence/exit gates thay vì fixed dates.

Không promote phase chỉ vì đã hết quý hoặc vì tooling đã được cài đặt.

```text
Capability implemented
    ≠
Capability proven
    ≠
Capability promoted
```

Promotion cần:

```text
implementation
+ deterministic verification
+ eval/evidence
+ measured value
+ governance
+ human acceptance khi required
```

## 3.2 Lean rule

> Không xây platform/capability trước khi biết consumer, decision hoặc validation nào phụ thuộc vào nó.

## 3.3 Invariants xuyên suốt

Mọi phase MUST giữ:

1. Git + canonical structured artifacts là authority.
2. Derived outputs phải reproducible.
3. Material changes phải traceable.
4. Deterministic computation trước probabilistic AI.
5. AI không được silently change intent.
6. Human giữ accountability cho irreversible/high-risk decisions.
7. AI cost được đo theo accepted change.
8. Autonomous execution phải bounded.
9. Runtime/provider phải replaceable về mặt kiến trúc.
10. Infrastructure/capability mới phải chứng minh value trước promotion.

---

# 4. Origin — Raw Idea

## WHAT

Ý tưởng ban đầu:

> Xây một AI-Native Software Design Factory có thể quản lý engineering intent từ idea tới design, implementation, runtime evidence và continuous evolution.

## WHY

Các vấn đề cần giải:

- design knowledge phân tán;
- traceability dễ mất giữa requirement, architecture, task và code;
- AI có thể tạo tốc độ nhưng cũng tạo hallucination, cost và governance risk;
- architecture docs dễ drift khỏi code/runtime;
- tool/vendor có thể thay đổi;
- repeated engineering failures không tự trở thành process controls.

## WHO

Initial accountable roles:

- Software Architect / Factory owner;
- Product/Engineering owner;
- Developer;
- Security/SRE/Data representatives khi cần.

AI ở giai đoạn này chỉ là analysis/design assistant.

## WHEN

Trước khi code Factory.

Exit khi vision, non-goals, invariants và target lifecycle đủ rõ để lập Reference Architecture.

## WHERE

Artifacts:

```text
Reference Architecture baseline
initial decision log
principles
roadmap hypothesis
```

## HOW

Dùng architecture-first analysis:

```text
Idea
→ problem framing
→ target operating model
→ canonical truth model
→ traceability model
→ governance model
→ agent/runtime abstraction
→ phased roadmap
```

---

# 5. Phase -1 — Vision & Architecture Framing

> Đây là logical phase dùng để mô tả phần đã xảy ra trước Phase 0; không cần retroactively tạo DEV artifacts chỉ để hợp thức hóa lịch sử.

## WHAT

Xác lập kiến trúc tham chiếu và operating model:

- Lean + PDCA + continuous flow;
- canonical truth;
- Intent / Reality / Evolution Graph;
- traceability T0/T1/T2;
- agent logical layers;
- governance above agents;
- Codex-first, not Codex-dependent;
- VS Code as replaceable cockpit;
- MCP/tool boundary;
- target ARI;
- fitness functions;
- debt/incidents/runtime feedback;
- maturity model.

## WHY

Nếu không có architecture baseline, Factory dễ trở thành:

```text
prompts
+ extensions
+ model-specific scripts
+ undocumented automation
```

thay vì một software engineering system có governance.

## WHO

- Architect / Factory owner — accountable;
- AI assistant — analysis/synthesis;
- Engineering stakeholders — review.

## WHEN

Hoàn tất trước Phase 0 implementation.

## WHERE

Authority:

```text
docs/reference/ai-native-sdf-reference-architecture.md
```

Accepted implementation decisions sau đó đi vào `ADR-*`.

## HOW

Architectural decomposition + explicit invariants + target maturity.

## EXIT GATE

- target lifecycle defined;
- canonical/derived boundary defined;
- traceability policy defined;
- governance/human boundary defined;
- roadmap có small-batch Phase 0.

---

# 6. Phase 0 — Deterministic Foundation — CLOSED

## WHAT

Xây minimum viable foundation có thể chứng minh end-to-end.

Capability progression:

```text
DEV-001 — governed vertical slice / Patient Zero
    ↓
DEV-002 — implementation evidence resolves
    ↓
DEV-003 — changed-file provenance
    ↓
DEV-004 — executable canonical QG-004
    ↓
DEV-005 — reproducible validation environment
```

## WHY

Trước AI automation, Factory phải chứng minh:

- canonical truth rõ;
- traceability thực thi được;
- governance có thể executable;
- CI có thể fail closed;
- environment có thể reproduce;
- human/deterministic boundary rõ.

## WHO

- Human Architect/Reviewer;
- Developer/Codex-assisted execution;
- deterministic validator/CI.

## WHEN

Đã hoàn tất ngày 2026-09-19.

## WHERE

Repo-local Control Plane:

```text
constitution/
design/
knowledge/
tools/
.github/workflows/
AGENTS.md
.python-version
requirements-dev.txt
```

## HOW

Walking skeleton + small hardening batches + deterministic tests.

## VERIFIED EXIT

```text
tag: phase0-complete
SHA: f8a1a0a71fca25caee80003f37250eb3b7d5ce4b

Python 3.14.6                     PASS
isolated validation environment  PASS
25 canonical artifacts           PASS
QG-004                            PASS
57 tests                          PASS
AGENTS reproducibility            PASS
working tree                      CLEAN
GitHub deterministic-validation  PASS
```

## PHASE 0 RESULT

> **Deterministic, traceable, governed, reproducible foundation established.**

## NON-GOALS CARRIED FORWARD

- no broad multi-agent orchestration;
- no Graphify dependency;
- no ARI implementation;
- no runtime learning loop;
- no semantic autonomous approval.

---

# 7. Phase 1 — Prove Bounded, Cost-Aware AI Execution

## 7.1 Phase objective

> Chứng minh AI execution có thể **bounded, measurable, cost-aware và governed** trước khi mở rộng thành agentic system.

Mandatory sequence:

```text
Phase 1.0
Cost Telemetry
    ↓
Runtime Circuit Breaker
    ↓
Chat-Heavy Baseline
    ↓
Phase 1.1
Context / Graphify Treatment Experiment
    ↓
≥70% Input-Token Reduction Gate
    ↓
Phase 1.2
Context Pack + Risk/Cost Routing
    ↓
Phase 1.3
Bounded Agent Automation
```

## 7.2 Phase 1 — 5W1H

### WHAT

Build:

- per-call telemetry;
- DEV-level usage aggregation;
- persistence boundary;
- execution attempt state machine;
- runtime circuit breaker;
- chat-heavy baseline;
- context strategy measurement;
- Graphify/context treatment experiment;
- risk/cost routing;
- minimal bounded agent flow.

### WHY

Phase 0 không trả lời:

- một accepted DEV tiêu bao nhiêu AI tokens?;
- retry waste bao nhiêu?;
- whole-repo context có lãng phí không?;
- Graphify có ROI thật không?;
- agent có thể tự dừng sau failure không?;
- task nào thực sự cần strong model/critic?

### WHO

Human:

- Factory Architect;
- Developer;
- Reviewer;
- accountable T2 owner.

Minimal AI roles:

```text
Orchestrator
Executor/Designer
Reviewer/Critic
```

Specialist agents chưa mặc định enabled.

### WHEN

Ngay sau `phase0-complete`.

Promotion chỉ khi telemetry + circuit breaker đã proven.

### WHERE

Control Plane:

```text
telemetry schema
usage store
budget policy
circuit state
evals
```

Runtime:

```text
model-call wrapper
attempt lifecycle
failure persistence
human_attention_required
```

Repository:

```text
schemas
tests
runtime specs
evaluation cases
```

### HOW

Deterministic-first + bounded experiment + measurement.

---

# 8. Phase 1.0 — Cost Telemetry & Circuit Breaker

## WHAT

Thiết kế và triển khai:

```text
AI Usage Event
DEV Aggregate
Execution Attempt
Circuit State
Failure Evidence
```

Minimal per-call telemetry:

```yaml
dev_task: DEV-###
traceability_level: T0|T1|T2
run_id: ...
agent_role: ...
provider: ...
model: ...
source_revision: ...
context_strategy: ...
usage:
  input_tokens: ...
  output_tokens: ...
  total_tokens: ...
execution:
  attempt_number: 1|2
  review_call: true|false
  result: success|failure|cancelled|circuit_open
outcome:
  task_accepted: true|false
```

## WHY

Không có telemetry thì không thể quản trị AI cost hoặc chứng minh ROI.

## WHO

- Runtime owner implements;
- Factory owner defines metrics;
- Reviewer verifies failure behavior.

## WHEN

**First implementation work of Phase 1.**

Graphify/Multi-agent MUST NOT precede this.

## WHERE

Runtime boundary quanh model calls + append-only/equivalent usage persistence.

## HOW

Hard runtime rule:

```text
MAX_ATTEMPTS = 2
```

Attempt:

```text
one autonomous implementation/test cycle
```

Reviewer/critic/orchestration calls không phải implementation attempt nhưng usage MUST charge vào DEV.

State machine:

```text
ATTEMPT_1
  ├─ success → validation/review
  └─ failure → ATTEMPT_2

ATTEMPT_2
  ├─ success → validation/review
  └─ failure → CIRCUIT_OPEN

CIRCUIT_OPEN
  → block further model calls
  → persist command/log
  → persist attempt summaries
  → mark human_attention_required
  → return failure
```

## METRICS

Primary:

```text
Average input tokens per accepted DEV task
```

Mandatory:

```text
total AI tokens / accepted DEV
attempts / accepted DEV
model calls / accepted DEV
input tokens / attempted DEV
acceptance rate
```

Breakdown:

```text
T0 / T1 / T2 / aggregate
```

## EXIT GATE

- every model call attributable to DEV/run;
- accepted/rejected outcome recorded;
- third implementation attempt impossible after two failures;
- failure evidence persisted;
- telemetry survives process failure as required by design;
- cost aggregation deterministic/reproducible;
- existing Phase 0 regressions remain green.

---

# 9. Phase 1.1 — Baseline & Context Optimization Experiment

## WHAT

Lock a measurable chat-heavy baseline, then test context treatments:

```text
chat-heavy
manual-context-pack
graphify-context-pack
other
```

Graphify remains:

```text
candidate Reality/Context adapter
```

not:

```text
canonical truth
mandatory dependency
AI brain
```

## WHY

Context rereading is expected to be one of the largest controllable AI costs.

## WHO

- Factory owner defines experiment;
- Runtime captures usage;
- Developer/Reviewer execute comparable DEV tasks.

## WHEN

Only after Phase 1.0 telemetry is trustworthy.

## WHERE

Derived Context/Reality layer.

No canonical design moves into Graphify.

## HOW

Primary metric:

```text
Average input tokens per accepted DEV task
```

Formula:

```text
reduction =
1 - (treatment_avg_input_tokens / baseline_avg_input_tokens)
```

Acceptance:

```text
reduction >= 70% → ROI PASS
reduction < 70%  → remove / redesign / reject
```

If Graphify is bundled with Context Pack/routing, result is ROI of the **declared treatment**, not necessarily Graphify alone.

Baseline/treatment SHOULD keep comparable:

- task mix;
- trace-level mix;
- model/reasoning policy;
- review policy;
- acceptance criteria.

## EXIT GATE

Either:

```text
A. treatment passes ≥70% with no quality/governance regression
```

or:

```text
B. treatment fails and is explicitly removed/redesigned
```

Failure of Graphify experiment MUST NOT block the Factory itself.

---

# 10. Phase 1.2 — Context Pack + Risk/Cost Routing

## WHAT

Create bounded context selection and route capability by risk/cost.

Example:

```text
T0/simple
→ deterministic / no AI

small T1
→ bounded executor

complex T1
→ executor + critic if justified

T2
→ stronger reasoning + independent review + human gate
```

## WHY

One expensive workflow for every task is Lean waste.

## WHO

- Orchestrator/router;
- policy/eval;
- human accountable owner.

## WHEN

After telemetry and context measurement.

## WHERE

Control Plane routing policy + runtime capability registry.

## HOW

Route using:

```text
trace level
changed paths
risk flags
required capabilities
context size
budget
model quality requirement
security/data classification
```

## EXIT GATE

- trivial work can avoid AI;
- T1/T2 routing deterministic where rules exist;
- model/call budget visible before execution;
- human gate cannot be bypassed by router;
- routing decisions auditable.

---

# 11. Phase 1.3 — Bounded Agent Automation

## WHAT

Enable minimal production-like agent flow:

```text
Request/DEV
→ classify
→ build context
→ budget check
→ execute
→ deterministic validation
→ optional independent critic
→ human gate if required
```

## WHY

Prove AI execution can participate in Factory flow without becoming the Factory.

## WHO

Minimal logical roles:

- Orchestrator;
- Executor/Designer;
- Reviewer/Critic.

## WHEN

Only after Phase 1.0–1.2 gates pass.

## WHERE

Runtime layer behind existing canonical repo/governance.

## HOW

Use structured inputs/outputs, permissions, bounded calls, deterministic gates.

## EXIT GATE — PHASE 1

Phase 1 is complete only when:

- cost telemetry works end-to-end;
- circuit breaker proven;
- cost per accepted DEV measurable;
- context strategy measurable;
- Graphify/context experiment has explicit disposition;
- risk/cost routing works;
- bounded agent execution works for representative T1 and T2;
- no Phase 0 invariant is weakened;
- human authority remains intact.

---

# 12. Phase 2 — Governed Agentic Flow

## PHASE OBJECTIVE

> Scale from bounded AI execution to **governed collaboration among specialized capabilities**.

## WHAT

Add as evidence justifies:

- Intent/Reality/Evolution query services;
- capability-oriented MCP/tool layer;
- impact analysis;
- specialist agents:
  - Requirements/Domain;
  - Architecture;
  - API/Integration;
  - Data;
  - Security;
  - Reliability;
  - Deployment/Ops;
- Design Integrator;
- independent critics;
- more executable fitness functions;
- agent eval pipeline;
- debt/incident learning artifacts;
- Factory quality/cost metrics.

## WHY

Complex design changes need multi-domain reasoning, but uncontrolled multi-agent chains create coordination and cost waste.

## WHO

AI logical roles:

```text
Orchestrator
Knowledge/Context
Specialists
Integrator
Critics
Execution
```

Human:

```text
Intent owner
Architect
Security/Data/SRE owners as required
Accountable approver
PR reviewer
```

Trust boundaries:

```text
Architecture Agent proposes; does not approve.
Security Agent finds; does not waive.
Integrator surfaces conflict; does not silently resolve material conflict.
Orchestrator routes; does not change requirement.
```

## WHEN

Only after Phase 1 proves:

- measured cost;
- bounded execution;
- context efficiency;
- routing;
- useful AI workflow.

## WHERE

Agent layer + query/context services + CI/evaluation.

## HOW

Capability-on-demand:

```text
change
→ deterministic classification
→ context pack
→ invoke only required specialists
→ integrate
→ independent critique
→ human gate where required
→ execution
```

Agent specs SHOULD include:

```text
id
version
purpose
required capabilities
permissions
allowed actions
forbidden actions
input schema
output schema
evaluation suite
```

## Phase 2 sub-phases

### 2.0 — Queryable Knowledge Services

- Intent Graph query;
- Reality/Context query;
- Evolution query;
- provenance-aware edges;
- temporal semantics.

### 2.1 — Specialist Agents

Enable one specialist at a time based on real work.

No “swarm by default”.

### 2.2 — Design Integration & Independent Critique

Conflict object becomes first-class.

Critics SHOULD remain read-only during review pass.

### 2.3 — Executable Fitness Expansion

Examples:

```text
service ownership / DB boundary
public API security controls
external dependency timeout/retry/observability
contract compatibility
migration safety
```

### 2.4 — Agent Evaluation Pipeline

```text
candidate
→ eval suite
→ shadow/comparison
→ limited rollout
→ promote / rollback
```

## EXIT GATE — PHASE 2

- multi-domain design task can be completed with explicit conflicts;
- specialist activation is evidence/risk driven;
- agent permissions enforced;
- agent changes evaluated before promotion;
- more than QG-004 governance is executable;
- cost/quality trends show agentic flow creates net value;
- material decisions still have human accountability.

---

# 13. Phase 3 — Factory Control Plane

## PHASE OBJECTIVE

> Turn proven repo/team-local capabilities into a scalable, replaceable, multi-client/multi-runtime Factory Control Plane.

## WHAT

Build:

- Agent Runtime Interface (ARI);
- runtime/provider adapters;
- capability router;
- shared policy/evaluation services;
- shared graph/query services;
- centralized audit/observability;
- cost governance;
- cross-repo Evolution Graph;
- organizational ownership/standards;
- multi-client interfaces:
  - VS Code;
  - CLI;
  - CI/CD;
  - Web;
  - other IDE/runtime.

## WHY

At scale, repo-local scripts and provider-specific configuration create:

- duplication;
- inconsistent governance;
- fragmented cost data;
- runtime/provider lock-in;
- cross-repo visibility gaps.

## WHO

- Platform Engineering;
- Architecture Governance;
- Security;
- SRE;
- AI/Agent platform owners;
- engineering teams.

## WHEN

Only when Phase 1/2 have stabilized:

```text
workflow
artifact set
metrics
agent roles
permissions
evaluation model
cost model
```

Do NOT build enterprise control plane merely because scale may exist someday.

## WHERE

```text
                 HUMAN / BUSINESS
                        │
                        ▼
                Factory Control Plane
                        │
      ┌─────────────────┼──────────────────┐
      ▼                 ▼                  ▼
 Policy/Eval       Context/Graph       Runtime Router
                                            │
                                ┌───────────┼───────────┐
                                ▼           ▼           ▼
                              Codex      Runtime B   Runtime C

Clients:
VS Code | CLI | CI/CD | Web | Other IDE
```

Canonical truth remains in repositories/artifacts.

## HOW

Define ARI conceptually as:

```text
run(
    task,
    role,
    context,
    tools,
    permissions,
    expected_schema
) -> canonical_result
```

Provider-specific configuration becomes adapter/deployment artifact.

Factory MUST NOT lock these into one provider:

```text
Knowledge
Workflow
Policies
Tools
Evaluations
```

## Phase 3 sub-phases

### 3.0 — Runtime Abstraction

- provider-neutral agent specs;
- ARI contract;
- Codex adapter;
- exit test against alternate/mock adapter.

### 3.1 — Shared Governance/Evaluation Services

- policy distribution;
- permissions;
- evaluation registry;
- agent promotion/rollback;
- audit.

### 3.2 — Shared Graph/Context Services

- repository federation;
- provenance;
- temporal semantics;
- organization-level queries.

### 3.3 — Multi-Repo / Multi-Client Operation

Prove same Factory rules from:

```text
IDE
CLI
CI
Web
```

### 3.4 — Raw Idea → Development-Ready Design Flow

At this point SDF should support:

```text
Raw Idea
→ Frame
→ Specify
→ Model
→ Decide
→ Detailed Design
→ Verify
→ Approve
→ DEV Decomposition
→ DESIGN_READY
```

with:

- canonical artifacts;
- traceability;
- automated deterministic checks;
- governed specialist AI;
- cost/risk routing;
- human gates;
- handoff package ready for Development.

## EXIT GATE — PHASE 3

Demonstrate at least one real idea flowing end-to-end to `DESIGN_READY` where:

1. problem/outcome captured;
2. FR/NFR testable;
3. domain/system model produced;
4. required decisions accepted;
5. contracts valid;
6. relevant security/reliability/data/ops analysis complete;
7. critics surface seeded conflict/risk;
8. human gate resolves material issues;
9. DEV tasks generated/decomposed;
10. verification intent mapped;
11. trace graph complete;
12. design package is reproducible;
13. runtime/provider-specific implementation can be swapped without changing canonical artifacts;
14. cost/evaluation evidence exists for AI participation.

---

# 14. Phase 4 — Living Engineering System — Post-Phase-3 Horizon

> Phase 4 là logical extension của maturity Level 5; promotion cần ADR/roadmap revision khi Phase 3 gần hoàn tất.

## OBJECTIVE

Close the loop:

```text
Intent
↔ Reality
↔ Evolution
```

## WHAT

- runtime evidence ingestion;
- SLO/NFR evidence mapping;
- Reality Graph updates;
- automatic drift detection;
- incidents linked to design assumptions;
- technical debt evolution;
- deprecation/migration lifecycle;
- Change Proposals generated from signals.

## WHY

Design that stops at development handoff eventually drifts from reality.

## WHO

- SRE/Operations;
- Architecture;
- Product;
- Evolution agents;
- human decision owners.

## WHEN

After Phase 3 Control Plane and runtime integration are stable.

## WHERE

Runtime telemetry + Reality/Evolution services.

## HOW

```text
Runtime Signal
→ Evidence
→ Intent vs Reality comparison
→ Drift / Incident / Debt
→ Change Proposal
→ Impact Analysis
→ Decision
→ Design Delta
→ DEV
```

## EXIT GATE

- runtime evidence traceable to NFR/design assumptions;
- intentional drift produces governed finding;
- incident learning can create rule/eval/fitness proposal;
- historical decisions distinguished from current truth;
- AI does not auto-accept architecture evolution.

---

# 15. Phase 5 — Adaptive Factory — Long-Term Horizon

> Phase 5 corresponds to maturity Level 6 and is intentionally not an early implementation commitment.

## OBJECTIVE

Use evidence to improve the Factory itself.

## WHAT

Meta-PDCA:

```text
Factory policy/workflow
→ usage
→ quality/cost/override evidence
→ analysis
→ improvement proposal
→ eval
→ human-governed promotion
```

Potential capabilities:

- routing policy optimization;
- context strategy optimization;
- eval-driven agent upgrades;
- policy effectiveness analysis;
- repeated failure → proposed fitness function;
- cost-quality frontier monitoring;
- provider/runtime portfolio optimization.

## WHY

A living software system needs a living engineering process.

## WHO

- Factory governance owners;
- platform/architecture;
- evaluation agents;
- accountable human approvers.

## WHEN

Only when data quality, evaluation harness and governance are mature.

## WHERE

Factory Control Plane meta-layer.

## HOW

Never allow self-modification without governance:

```text
Observed pattern
→ Improvement Proposal
→ Eval/Simulation
→ Human approval
→ Limited rollout
→ Evidence
→ Promote/Rollback
```

## EXIT GATE

An adaptive capability is acceptable only if Factory can prove:

- proposal provenance;
- evaluation coverage;
- no silent policy weakening;
- bounded rollout;
- rollback path;
- human approval for material governance change.

---

# 16. End-to-End Product Design Flow after Phase 3

Once Phase 3 is complete, target workflow for a new product/capability is:

## Stage 1 — Idea Capture

Input:

```text
raw idea
hypothesis
business context
```

Output:

```text
Idea Brief
assumptions
initial owner
```

Human gate: Product/Business owner.

## Stage 2 — Evidence & Framing

Output:

```text
PROB-*
OUT-*
users/stakeholders
scope
constraints
unknowns
evidence
```

## Stage 3 — Specification

Output:

```text
FR-*
NFR-*
acceptance criteria
trace level / risk
```

## Stage 4 — System Modeling

Output:

```text
domain concepts
system context
architecture components
dependencies
```

## Stage 5 — Decision

Output:

```text
options
trade-offs
ADR-*
```

Human gate for material decisions.

## Stage 6 — Detailed Design

As applicable:

```text
API contracts
event contracts
data model
security/threats
reliability
deployment
operations
migration/rollback
observability
```

## Stage 7 — Verification

```text
schema checks
traceability
fitness functions
specialist critics
consistency findings
security/reliability findings
```

## Stage 8 — Approval

Accountable owner accepts design baseline/risk.

## Stage 9 — DEV Decomposition

Output:

```text
DEV-*
implementation.paths
upstream trace
verification mapping
rollout/runtime evidence expectation
```

## Stage 10 — DESIGN_READY Gate

If pass:

```text
Development may begin
```

If fail:

```text
finding
→ responsible owner
→ revise design
→ reverify
```

---

# 17. Roadmap 5W1H Summary Matrix

| Phase | WHAT | WHY | WHO | WHEN | WHERE | HOW |
|---|---|---|---|---|---|---|
| Origin | Define SDF idea | Solve fragmented design/AI governance problem | Architect + stakeholders | Before implementation | Architecture docs | Problem framing |
| -1 | Reference architecture | Avoid tool/prompt-driven architecture | Architect + AI assistant | Before Phase 0 | Reference docs | Invariants + target model |
| 0 | Deterministic foundation | Trust before autonomy | Human + CI + Codex assist | Completed | Repo Control Plane | Walking skeleton + deterministic gates |
| 1 | Cost-aware bounded AI | Prove AI value/safety | Architect, Dev, minimal agents, Reviewer | After Phase 0 | Runtime + repo Control Plane | Telemetry, circuit breaker, experiment, routing |
| 2 | Governed agentic flow | Scale AI capability across domains | Specialists + critics + humans | After Phase 1 evidence | Agent/query/eval layer | Capability-on-demand + evals |
| 3 | Factory Control Plane | Scale across repo/team/provider | Platform + Architecture + Security | When workflows stabilize | Shared Control Plane | ARI + shared policy/graph/eval |
| 4 | Living system | Close runtime/design loop | SRE + Architecture + Evolution agents | After Phase 3 | Runtime + Reality/Evolution | Drift/incidents/evidence → changes |
| 5 | Adaptive Factory | Improve Factory from evidence | Governance owners | Long-term | Meta-Control Plane | Eval-governed meta-PDCA |

---

# 18. KPI Evolution by Phase

## Phase 0

```text
trace validity
test pass
QG pass
reproducibility
orphan change count
```

## Phase 1

```text
input tokens / accepted DEV
total AI tokens / accepted DEV
attempts / accepted DEV
model calls / accepted DEV
acceptance rate
circuit-open count
context-treatment ROI
```

## Phase 2

```text
design lead time
review effort
critic precision/false positives
agent override rate
escaped design defects
policy violation rate
agent eval pass/regression
cost by capability
```

## Phase 3

```text
idea → DESIGN_READY lead time
cross-repo policy consistency
runtime/provider portability
cost per approved design increment
human approval latency
rework before implementation
```

## Phase 4

```text
drift count/age
time-to-detect drift
incident-to-rule lead time
NFR intent vs runtime reality
debt age/concentration
```

## Phase 5

```text
Factory improvement lead time
policy/eval effectiveness
cost-quality frontier
rollback rate of Factory changes
repeated failure recurrence
```

---

# 19. Human Accountability Gates

Minimum conceptual gates:

```text
Gate A — Problem / Scope acceptance
Gate B — Major architecture / ADR / risk acceptance
Gate C — Design release / DESIGN_READY approval
Gate D — Critical migration/security exception/deployment as applicable
```

Automation MAY prepare evidence and recommendation.

Automation MUST NOT silently approve irreversible/high-risk decisions.

---

# 20. Anti-Roadmap — Things We Intentionally Do Not Build Early

Do not prematurely build:

- universal multi-agent scheduler;
- enterprise graph database;
- autonomous production deployment;
- universal provider router;
- complex long-term memory platform;
- dozens of specialist agents;
- centralized Control Plane before repo-local workflow proves value;
- Graphify as canonical source;
- AI self-modifying governance.

Lean principle:

> Prove a capability with the smallest reversible implementation before promoting it into platform architecture.

---

# 21. Phase Promotion Checklist

Before moving from one phase to the next:

```text
[ ] previous exit gates pass
[ ] canonical artifacts updated
[ ] decisions captured in ADR where material
[ ] deterministic regressions green
[ ] metrics/evidence captured
[ ] known debt explicitly carried forward
[ ] new phase does not weaken prior invariants
[ ] rollback/degraded mode understood
[ ] human accountable owner approves promotion
```

---

# 22. Immediate Next Step

Current state:

```text
Phase 0 = CLOSED
baseline tag = phase0-complete
baseline SHA = f8a1a0a71fca25caee80003f37250eb3b7d5ce4b
```

Therefore next work MUST be:

```text
Phase 1.0 — Cost Telemetry + Circuit Breaker
```

First design increment should define only:

1. minimal telemetry schema;
2. telemetry persistence boundary;
3. model-call/runtime enforcement boundary;
4. `MAX_ATTEMPTS = 2` state machine;
5. failure evidence contract;
6. deterministic acceptance tests;
7. traceability/ADR needs for the Phase 1 change.

It SHOULD NOT introduce:

```text
Graphify
multi-agent orchestration
ARI
shared Control Plane
specialist agents
```

until Phase 1.0 evidence exists.

---

# 23. Roadmap Completion Definition

SDF roadmap is not “complete” when all planned components exist.

It is successful when the Factory can repeatedly demonstrate:

```text
raw idea
→ governed design
→ development-ready handoff
→ implementation
→ runtime evidence
→ learning
→ evolution
```

while preserving:

```text
canonical truth
traceability
reproducibility
human accountability
cost control
provider portability
continuous improvement
```

The long-term destination is therefore not a static platform, but a **living, governed engineering system**.
