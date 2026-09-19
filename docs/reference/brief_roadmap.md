# BRIEF ROADMAP

## Tổng quan

```text
PHASE 0 — CLOSED
Deterministic, traceable, governed, reproducible foundation
        ↓
PHASE 1 — Prove bounded, cost-aware AI execution
        ↓
PHASE 2 — Governed agentic flow
        ↓
PHASE 3 — Factory Control Plane
```

---

## Phase 1 — Prove bounded, cost-aware AI execution

### WHAT — Làm gì?

Mục tiêu của Phase 1 không phải “xây multi-agent platform”, mà là chứng minh:

> AI có thể tham gia execution một cách **bounded, measurable, cost-aware và governed**.

Thứ tự đã khóa:

```text
Phase 1.0
Cost Telemetry
    ↓
Runtime Circuit Breaker
    ↓
Chat-heavy Baseline
    ↓
Phase 1.1
Graphify / Context treatment experiment
    ↓
≥70% input-token reduction gate
    ↓
Context Pack
    ↓
Risk / Cost Routing
    ↓
Bounded Agent Automation
```

Các capability chính:

* per-call AI usage telemetry;
* DEV-level cost aggregation;
* `MAX_ATTEMPTS = 2`;
* circuit breaker thật sự ở runtime;
* context strategy tracking;
* chat-heavy baseline;
* Graphify experiment;
* Context Pack;
* risk/cost router;
* bounded Orchestrator / Designer / Reviewer / Executor flow.

---

### WHY — Tại sao?

Phase 0 đã chứng minh governance/determinism, nhưng chưa chứng minh:

```text
AI execution
    +
cost control
    +
runtime safety
    +
context efficiency
```

Nếu nhảy thẳng sang multi-agent automation, rủi ro là:

* token explosion;
* retry loop;
* context reread;
* agent coordination waste;
* provider lock-in;
* khó biết AI có thực sự tạo value hay không.

Phase 1 phải trả lời:

> “AI có giảm cost/lead-time hoặc tăng quality đủ để đáng tồn tại trong Factory hay không?”

---

### WHO — Ai chịu trách nhiệm?

Human:

* Architect / Factory owner;
* Developer;
* Reviewer;
* người chịu accountability cho T2;
* operator kiểm cost/telemetry.

AI roles ban đầu chỉ nên tối thiểu:

```text
Orchestrator
Designer / Executor
Reviewer / Critic
```

Không bật tất cả specialist agents.

Governance vẫn ở trên agents.

---

### WHEN — Khi nào?

**Bắt đầu ngay sau `phase0-complete`.**

Nhưng phải theo sequence:

```text
1. telemetry
2. circuit breaker
3. baseline
4. Graphify experiment
5. routing
6. bounded automation
```

Không được đảo thứ tự để “demo agent” trước rồi mới đo cost sau.

#### Exit condition Phase 1

Phase 1 chỉ nên kết thúc khi chứng minh được:

* AI usage được attribution tới `[DEV-*]`;
* `MAX_ATTEMPTS = 2` enforce bằng runtime;
* không có model call thứ ba sau second failure;
* cost/tokens per accepted DEV đo được;
* Context strategy đo được;
* Graphify treatment đạt ROI hoặc bị reject;
* bounded T1/T2 workflow chạy được mà không phá Phase 0 gates;
* human authority vẫn giữ nguyên.

---

### WHERE — Capability nằm ở đâu?

Control Plane:

```text
cost telemetry
circuit breaker
budget enforcement
routing
evaluation
```

Runtime/orchestrator:

```text
attempt lifecycle
model-call blocking
failure persistence
human_attention_required
```

Repository:

```text
canonical telemetry schema
runtime policy/spec
tests
eval cases
```

Graphify:

```text
Reality / Context layer
```

không nằm trên canonical authority path.

---

### HOW — Làm thế nào?

#### Phase 1.0 — Cost Telemetry + Circuit Breaker

Thiết kế trước:

```text
Telemetry Schema
Persistence Boundary
Attempt State Machine
Budget Check
Failure Evidence
Acceptance Tests
```

Circuit breaker:

```text
ATTEMPT_1
  ├─ success
  └─ failure → ATTEMPT_2

ATTEMPT_2
  ├─ success
  └─ failure → CIRCUIT_OPEN

CIRCUIT_OPEN
  → no more model calls
  → persist evidence
  → human queue
  → failure
```

Primary KPI:

```text
Average input tokens per accepted DEV task
```

#### Phase 1.1 — Context optimization

Baseline:

```text
chat-heavy
```

Treatments:

```text
manual-context-pack
graphify-context-pack
other
```

Graphify acceptance:

```text
reduction >= 70%
```

Nếu không đạt:

```text
remove
or redesign
or reject
```

#### Phase 1.2 — Risk/cost routing

Ví dụ:

```text
T0
→ deterministic / no AI

small T1
→ bounded implementation agent

complex T1
→ implementation + critic

T2
→ stronger reasoning + independent review + human gate
```

---

## Phase 2 — Governed Agentic Flow

### WHAT

Phase 2 biến các bounded workflows đã chứng minh ở Phase 1 thành một **governed agentic operating model**.

Bổ sung dần:

* explicit Intent/Reality/Evolution query services;
* MCP tool layer theo capability;
* impact analysis;
* specialist agents:

  * Architecture
  * Security
  * Data
  * Reliability
  * API/Integration
  * Deployment/Ops;
* more executable fitness functions;
* agent evaluation pipeline;
* Factory metrics;
* technical debt / incident learning integration.

---

### WHY

Phase 1 chỉ chứng minh:

> “AI execution có thể bounded và economic.”

Phase 2 cần chứng minh:

> “Nhiều AI capabilities có thể phối hợp mà vẫn giữ governance, traceability và quality.”

Đây là lúc SDF chuyển từ:

```text
AI-assisted
```

sang:

```text
governed agentic
```

---

### WHO

Logical roles:

```text
Orchestrator
Knowledge / Context
Specialist Agents
Design Integrator
Independent Critics
Execution Agents
```

Human roles:

* Product/intent owner;
* Architect;
* Security/SRE/Data owner khi cần;
* PR reviewer;
* accountable approver.

Important:

```text
Architecture Agent ≠ Architecture Approver
Security Agent ≠ Risk Waiver Authority
Orchestrator ≠ Requirement Owner
```

---

### WHEN

Chỉ bắt đầu Phase 2 khi Phase 1 đã chứng minh:

```text
cost telemetry works
circuit breaker works
routing works
context optimization has evidence
bounded automation works
```

Không promote specialist agents chỉ vì “có thể”.

---

### WHERE

Architecture phân lớp:

```text
                    HUMAN
                      │
                 Orchestrator
                      │
              Context / Knowledge
          ┌───────────┼───────────┐
          ▼           ▼           ▼
     Architecture  Security     Data...
          │           │
          └──────┬────┘
                 ▼
             Integrator
                 │
               Critics
                 │
             Human Gate
                 │
             Execution
```

Control Plane cross-cutting:

```text
Policy
Permissions
Budget
Evaluation
Traceability
Audit
Human Approval
```

---

### HOW

Không dùng một generic “multi-agent swarm”.

Dùng capability-on-demand:

```text
change
→ deterministic classification
→ context pack
→ risk analysis
→ invoke only required specialists
→ integration
→ independent critic
→ human gate when required
```

Các outputs phải structured và versioned.

Mỗi agent phải có:

```text
identity
version
permissions
allowed actions
forbidden actions
input contract
output schema
evaluation suite
```

Agent changes cũng phải qua:

```text
candidate
→ eval
→ comparison/shadow
→ limited rollout
→ promote / rollback
```

---

## Phase 3 — Factory Control Plane

### WHAT

Phase 3 tách SDF khỏi workstation/repository-local workflow thành một **Factory Control Plane** có thể phục vụ nhiều repository/team/runtime.

Target capabilities:

* Agent Runtime Interface — ARI;
* provider/runtime adapters;
* capability router;
* centralized policy/evaluation services;
* shared graph services;
* audit/observability;
* cost governance;
* cross-repo Evolution Graph;
* organization-level standards;
* ownership;
* multi-client access:

  * VS Code
  * CLI
  * CI/CD
  * Web
  * other IDE/runtime.

---

### WHY

Phase 1–2 tối ưu cho một repo/team.

Khi scale tăng:

```text
repo-local scripts
provider-specific configs
local graphs
manual ownership
```

sẽ không còn đủ.

Phase 3 giải bài toán:

> “Làm sao vận hành cùng governance model trên nhiều repo, nhiều team và nhiều AI provider?”

---

### WHO

Ngoài engineering teams sẽ cần:

* Platform Engineering;
* Architecture Governance;
* Security;
* SRE;
* AI/Agent platform owners;
* central policy owners;
* organization-level reviewers.

Agent runtime/provider trở thành replaceable infrastructure.

---

### WHEN

Chỉ làm khi scale thực sự yêu cầu.

Không xây Control Plane enterprise trước khi Phase 1/2 chứng minh:

```text
workflow
artifacts
metrics
agent roles
cost model
governance model
```

ổn định.

Đây là Lean gate cực kỳ quan trọng.

---

### WHERE

Target architecture:

```text
                     HUMAN / BUSINESS
                           │
                           ▼
                   Factory Control Plane
                           │
       ┌───────────────────┼──────────────────┐
       │                   │                  │
       ▼                   ▼                  ▼
   Policy/Eval          Context/Graph      Runtime Router
                                               │
                                    ┌──────────┼──────────┐
                                    ▼          ▼          ▼
                                  Codex      Runtime B  Runtime C

       ┌─────────────────────────────────────────────┐
       │                  Clients                    │
       │ VS Code | CLI | CI | Web | Other IDE       │
       └─────────────────────────────────────────────┘
```

Canonical truth vẫn ở Git/artifacts.

Control Plane không trở thành source of truth mới.

---

### HOW

Thông qua abstraction rõ:

```text
Factory
    ↓
Agent Runtime Interface
    ↓
Runtime Adapter
    ↓
Codex / Provider B / Provider C
```

Không khóa vào:

```text
Knowledge
Workflow
Policies
Tools
Evaluations
```

ARI tối thiểu về concept:

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

Sau đó capability routing có thể dựa vào:

```text
risk
cost
latency
privacy
tool support
quality
model capability
```

---

## Maturity trajectory

Các phase không hoàn toàn đồng nghĩa với maturity level, nhưng có thể nhìn gần đúng:

```text
Phase 0
→ Level 2 Structured
  + một số vertical capability Level 4

Phase 1
→ bounded / measurable AI Assisted
  tiến tới Agentic có kiểm soát

Phase 2
→ Level 3 Agentic
  + Level 4 Governed

Phase 3
→ Level 4 Governed ở organization scale
  → Level 5 Living
```

Sau đó mới có thể tiến tới:

```text
Level 5 — Living
Intent ↔ Reality ↔ Evolution

Level 6 — Adaptive
runtime evidence
→ learning
→ Factory meta-PDCA
```

---

## Toàn roadmap dưới dạng 5W1H cô đọng

| Phase | What                                                                  | Why                                                  | Who                                        | When                         | Where                          | How                                                          |
| ----- | --------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------ | ---------------------------- | ------------------------------ | ------------------------------------------------------------ |
| **1** | Cost telemetry, circuit breaker, context optimization, bounded agents | Chứng minh AI tạo value với cost/risk kiểm soát được | Architect, Dev, minimal agents, Reviewer   | Ngay sau Phase 0             | Repo + Control Plane + runtime | Deterministic-first, `MAX_ATTEMPTS=2`, ≥70% context ROI      |
| **2** | Governed specialist-agent workflows                                   | Scale AI capability mà không mất governance          | Orchestrator, specialists, critics, humans | Sau Phase 1 evidence         | Agent layer + graph/query + CI | Capability-on-demand, structured outputs, evals, human gates |
| **3** | Organization-scale Factory Control Plane                              | Multi-repo, multi-team, multi-provider portability   | Platform, Architecture, Security, SRE      | Khi scale chứng minh nhu cầu | Shared Control Plane           | ARI, adapters, shared policy/eval/graph/audit services       |

---

## Các nguyên tắc xuyên suốt tất cả phase

Bất kể Phase 1, 2 hay 3, các invariants này **không được phá**:

```text
1. Git + canonical artifacts remain authority.

2. Derived knowledge must remain reproducible.

3. Material changes remain traceable.

4. Deterministic computation happens before AI judgment.

5. AI cannot silently change intent.

6. Human remains accountable for irreversible/high-risk decisions.

7. AI cost is measured per accepted change.

8. Autonomous execution is bounded.

9. Provider/runtime remains replaceable.

10. New infrastructure must prove value before promotion.
```

Và roadmap có thể được tóm lại bằng một câu:

> **Phase 1 chứng minh AI execution có kinh tế và an toàn; Phase 2 chứng minh agent collaboration có thể được governance; Phase 3 biến những gì đã chứng minh thành một Factory Control Plane có thể scale và thay thế provider.**
