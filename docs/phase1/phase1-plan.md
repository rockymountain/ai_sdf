# Phase 1.0 — Architecture / Design Plan

**Status:** Working plan — non-canonical.

**Authority boundary:** Tài liệu này định hướng sequencing và design work của Phase 1. Nó **không** thay thế authority của `design/decisions/ADR-*`, `design/architecture/*`, `constitution/*` hoặc `knowledge/traceability.yaml`. Accepted architecture phải được khóa bằng ADR/CMP; executable governance nằm trong `constitution/*`; trace truth nằm trong `knowledge/traceability.yaml`.

**Immutable Phase-0 baseline:** `phase0-complete` @ `f8a1a0a71fca25caee80003f37250eb3b7d5ce4b`.

**Phase-1 working entry revision:** `main` @ `23e7898de325d0f602d9edc7a6c05d890b00e233`.

Phase 0 đã closed và immutable. DEV-006 là post-Phase-0 T0 housekeeping đã chuẩn hóa namespace `docs/phase0/` và `docs/reference/`; nó không thay đổi Phase-0 baseline nhưng là working revision để bắt đầu Phase 1.

Phase 1 bắt đầu theo thứ tự:

```text
cost telemetry
    ↓
runtime circuit breaker
    ↓
declared chat-heavy control baseline
    ↓
context optimization experiment
    ↓
model-tier / reasoning-effort optimization experiment
    ↓
combine only proven treatments
    ↓
bounded agent automation
```

**Verdict:** Phase 1.0 là **một T2 design increment** nhưng implementation nên chia thành hai small batches:

```text
DEV-007 — Cost Telemetry + Model Call Gateway
DEV-008 — Runtime Attempt Controller + Circuit Breaker
```

Không bắt đầu Graphify, Context Pack routing, multi-agent orchestration hay broad autonomous workflow trước khi telemetry và hard circuit breaker được chứng minh.

---

## 1. Phase 1 goal

Phase 1 phải chứng minh:

> **Bounded, measurable, cost-aware AI execution whose resource optimization does not weaken quality, governance, security or human accountability.**

“Cost-aware” không có nghĩa chỉ giảm token. Lean objective là:

```text
minimize AI resource cost per accepted DEV

subject to:

  deterministic-quality non-regression
  governance non-regression
  security non-regression
  acceptable task acceptance rate
  bounded retry policy
  preserved human accountability
```

Factory không mặc định dùng model mạnh nhất cho mọi task. Mục tiêu dài hạn là dùng **mức model/reasoning thấp nhất vẫn đáp ứng acceptance và risk constraints của loại công việc hiện tại**.

---

## 2. Invariants phải khóa trước implementation

| ID | Invariant |
|---|---|
| P1-I01 | Mọi autonomous model call thuộc Phase-1 controlled flow MUST đi qua **một runtime egress boundary duy nhất**. |
| P1-I02 | Không model call nào được phát hành nếu không biết `DEV task`, trace level, `execution_scope_id`, `run_id`, source revision và attempt hiện tại. |
| P1-I03 | Usage của implementation, retry và future review/orchestration calls đều charge vào cùng DEV task. |
| P1-I04 | `MAX_ATTEMPTS = 2` là **runtime policy**, không phải prompt convention. |
| P1-I05 | Sau failure của attempt 2, `CIRCUIT_OPEN` phải được persist **trước** khi call tiếp theo có thể được phát hành. |
| P1-I06 | Call bị circuit chặn không được chạm provider và không được tính là model call. |
| P1-I07 | Missing/unusable token telemetry không được silently tiếp tục autonomous execution và **MUST NOT** bị ghi thành `0`. |
| P1-I08 | Telemetry không trở thành design/canonical truth; canonical policy/design vẫn nằm trong Git. |
| P1-I09 | Raw prompt/response text không được lưu chỉ để tính cost; mặc định chỉ lưu accounting metadata/evidence cần thiết. |
| P1-I10 | Phase 1.0 không phụ thuộc Graphify, full ARI hay multi-agent orchestration. |
| P1-I11 | Attempt budget thuộc về `execution_scope_id`, không thuộc riêng process hay `run_id`; tạo run mới MUST NOT reset budget cho cùng scope. |
| P1-I12 | Sau `CIRCUIT_OPEN`, resume chỉ được xảy ra qua explicit human-authorized new execution scope hoặc governed reset event có reason/provenance; historical attempts và cost không được xóa. |

Các invariant này hiện thực hóa contract có sẵn: `MAX_ATTEMPTS=2`, circuit mở sau failure thứ hai, block subsequent calls, persist failure evidence, human không đóng vai trò circuit breaker, và historical usage unknown không được hiểu thành zero.

---

## 3. Component boundary

Không mở rộng `CMP-002`. Component đó tiếp tục chịu trách nhiệm deterministic artifact / traceability / provenance validation.

Đề xuất:

```text
CMP-003 — Bounded AI Execution Runtime

Execution request
      │
      ▼
Execution Scope Resolver
      │
      ├── DEV / trace level
      ├── execution_scope_id
      ├── run_id
      └── source revision
      │
      ▼
Attempt Controller
      │
      ├── read canonical runtime policy
      │       max_attempts = 2
      │
      ▼
Model Call Gateway        ← HARD ENFORCEMENT BOUNDARY
      │
      ├── authorize call
      ├── verify telemetry writable
      ├── persist call-start
      ├── invoke provider
      └── persist usage/result
      │
      ▼
Implementation / Test cycle
      │
      ▼
Deterministic result
      │
      ├── PASS ───────────────→ accepted/review path
      │
      └── FAIL
            │
            ├── attempt 1 → attempt 2
            │
            └── attempt 2
                    │
                    ▼
                CIRCUIT_OPEN
                    │
          ┌─────────┼─────────────┐
          ▼         ▼             ▼
      block AI   persist       human_attention
      calls      evidence       required
```

`CMP-003` chỉ là **bootstrap runtime control**, không phải full Agent Runtime Interface. Provider neutrality vẫn phải được giữ: Codex có thể là bootstrap provider/runtime path, nhưng không được trở thành control-plane authority.

---

## 4. Runtime enforcement point

Enforcement phải nằm **ngay trước provider invocation**, không nằm trong prompt và cũng không nằm sau khi call đã phát đi.

Interface khái niệm:

```text
request_model_call(call_context)
        │
        ▼
[ Execution Scope + Budget Guard ]
        │
        ├── valid DEV/scope/run/attempt ? → required
        ├── circuit_open ? → reject locally
        ├── attempt budget exhausted ? → reject locally
        ├── telemetry store writable ? → required
        │
        ▼
[ Model Call Gateway ]
        │
        ├── persist call-start
        ├── invoke provider
        ├── reconcile exact usage
        └── persist call result
        │
        ▼
[ Provider Adapter / Codex bootstrap ]
```

Property bắt buộc phải test:

> Sau hai failed implementation attempts trong cùng `execution_scope_id`, request implementation thứ ba phải bị reject local và **provider invocation count vẫn bằng 2**.

Manual Codex use của human không cần bị cấm toàn cục. Scope enforcement là autonomous Phase-1 controlled flow. Nhưng bất kỳ flow nào muốn claim là “bounded autonomous execution” đều phải đi qua boundary này.

---

## 5. Execution scope, run và attempt semantics

### 5.1 Execution scope

`execution_scope_id` là budget identity của một autonomous implementation objective cụ thể.

Nó không được đồng nhất với session/process/run.

```text
execution_scope_id
  = stable identity của một bounded implementation objective

run_id
  = một runtime/process invocation cụ thể bên trong scope
```

Tạo `run_id` mới **không** reset attempt counter.

### 5.2 Attempt

Giữ contract:

```text
attempt
= one autonomous implementation + test/validation cycle
  for the same execution scope
```

Reviewer / critic / orchestration model call không tự tăng implementation attempt counter nhưng usage vẫn charge vào DEV.

### 5.3 Attempt success

```text
model response success != attempt success

attempt success
= execution cycle reached its deterministic acceptance checkpoint successfully
```

Agent không được tự nói “done” rồi reset budget. Attempt transition do runtime và deterministic result quyết định.

### 5.4 Resume after circuit open

Sau `CIRCUIT_OPEN`, một trong hai việc mới có thể xảy ra:

```text
A. remain closed
   → no more autonomous model calls for this execution_scope_id

B. human-authorized resume
   → explicit reason/provenance
   → new execution_scope_id or governed reset event
   → old attempts and cost remain immutable historical evidence
```

Phase 1.0 không cần approval workflow phức tạp; nhưng reset semantics phải explicit và audit được.

### 5.5 Golden path

Phase 1.0 golden path chỉ cần **một executor model call trong mỗi attempt**.

`review_call` vẫn tồn tại trong telemetry để future-compatible, nhưng autonomous reviewer/critic không bật trong DEV-007/008.

---

## 6. Minimal telemetry contract

Phase-0 measurement contract tiếp tục là nền tảng. Phase 1.0 chỉ bổ sung identity và dimensions cần thiết để runtime enforcement và future Lean experiments không mơ hồ.

### 6.1 Required per-call dimensions

| Group | Field |
|---|---|
| Attribution | `dev_task`, `traceability_level` |
| Execution identity | `execution_scope_id`, `run_id`, `call_id` |
| Reproducibility | full `source_revision` |
| Agent/runtime | `agent_role`, `provider`, `model` |
| Model profile | `reasoning_effort`, `selection_strategy`, `routing_policy_version` |
| Treatment | `context_strategy` |
| Usage | `input_tokens`, `output_tokens`, `total_tokens`, `usage_status` |
| Budget | `attempt_number`, `review_call` |
| Timing | `started_at`, `finished_at` |
| Call result | `success / failure / cancelled / usage_unknown` |
| Optional reconciliation | provider request ID, exact monetary cost, exact platform credit usage when available |

`selection_strategy` vocabulary tối thiểu:

```text
fixed
manual
risk-routed
```

`context_strategy` giữ nguyên vocabulary:

```text
chat-heavy
manual-context-pack
graphify-context-pack
other
```

`routing_policy_version` MAY trống khi `selection_strategy != risk-routed`, nhưng field phải tồn tại trong schema để Phase 1.1 có thể đo model-tier routing mà không đổi measurement model.

### 6.2 Usage status

Không được biến missing provider usage thành zero.

```text
usage_status:
  exact
  unknown
```

Khi provider trả exact machine-readable usage:

```text
usage_status = exact
tokens = exact values
```

Khi provider call đã xảy ra nhưng usage không usable:

```text
usage_status = unknown
token values = absent / unknown
call result = usage_unknown
autonomous continuation = stop
human_attention_required = true
```

### 6.3 Before-call vs after-call failure semantics

```text
Before provider invocation:
  telemetry store unavailable
    → reject locally
    → provider invocation count unchanged

After provider invocation:
  provider returns no usable usage
    → credit may already have been spent
    → persist usage_status = unknown
    → NEVER record usage as zero
    → stop autonomous retry/continuation
```

### 6.4 DEV outcome

Không đổi Phase-0 normative meaning của:

```text
task_accepted: true|false
```

Trước khi final outcome biết được, operational store nên dùng separate state:

```text
outcome_finalized = false
task_accepted = absent
```

Khi acceptance gate hoàn tất:

```text
outcome_finalized = true
task_accepted = true|false
```

Không silently đổi contract thành nullable tri-state.

---

## 7. Cost Optimization model

### 7.1 Primary Graphify/context KPI

Giữ nguyên:

```text
Average input tokens per accepted DEV task
```

Đây là KPI chính để đánh giá context reduction / Graphify treatment.

Failed attempts và review calls trước acceptance vẫn nằm trong numerator.

### 7.2 Lean scorecard

Cost Optimization tổng thể không được dựa trên một metric duy nhất.

```text
Efficiency
  input tokens / accepted DEV
  total AI tokens / accepted DEV
  model calls / accepted DEV
  attempts / accepted DEV

Economic
  exact monetary cost / accepted DEV       when provider exposes it
  exact platform credits / accepted DEV    when measurable

Flow
  first-attempt acceptance rate
  overall acceptance rate
  human-attention rate

Quality guardrails
  deterministic validation result
  regression result
  semantic/human acceptance
  governance regression
  security regression
```

Không tạo composite “AI efficiency score” che mất trade-off.

### 7.3 Lean interpretation

Một treatment không được coi là optimization nếu nó chỉ giảm token nhưng làm tăng đáng kể:

```text
retry rate
rejected DEV rate
human intervention
semantic defects
governance defects
security defects
```

Model rẻ hơn nhưng tạo nhiều retry/rework hơn có thể là **Lean waste**, không phải cost saving.

---

## 8. Persistence boundary

Đề xuất **SQLite local operational evidence store** cho Phase 1.0.

Logical location:

```text
.sdf/runtime/ai-execution.sqlite3
```

File runtime phải ignored khỏi Git.

### 8.1 Why SQLite

SQLite phù hợp bootstrap vì:

```text
standard-library
no new service
transactional state + telemetry
crash-safe circuit transition
easy DEV aggregation
supports outcome backfill
survives process restart
```

### 8.2 Logical model

```text
ExecutionScope
  execution_scope_id
  DEV
  trace level
  source revision
  context strategy
  state
  created_by / reset_reason where applicable

ExecutionRun
  run_id
  execution_scope_id
  started_at
  finished_at
  result

Attempt
  execution_scope_id + attempt_number
  run_id
  start/end/result
  failure evidence reference

ModelCall
  call_id
  execution_scope_id
  run_id
  attempt_number
  role/provider/model
  reasoning effort
  selection strategy
  routing policy version
  token usage + usage_status
  timing/result

FailureEvidence
  execution_scope_id + attempt_number
  command / exit code
  log reference

DEVOutcome
  DEV
  outcome_finalized
  task_accepted
  finalized_at
```

### 8.3 Authority boundary

```text
Git canonical:
  policy
  schema
  ADR
  component
  DEV / TEST definitions

SQLite operational evidence:
  observed runtime calls
  attempts
  usage
  circuit state
  failure evidence references

Derived reports:
  experiment summaries
  Phase-1 baseline reports
  ROI analysis
```

Telemetry DB không được trở thành competing design authority.

### 8.4 Retention and reproducibility

Runtime store MUST survive process restart.

Cost experiment results MUST be reproducibly derivable từ retained raw telemetry của declared measurement window.

Có thể publish derived/versioned report như:

```text
docs/phase1/phase1-ai-cost-baseline.md
```

nhưng report không được thay raw observed evidence hoặc canonical governance.

Không lưu full prompt/response mặc định. Failure logs phải respect data classification/redaction để telemetry DB không trở thành secret dump.

---

## 9. Canonical runtime policy

`MAX_ATTEMPTS = 2` phải được promote từ Phase-0 measurement/runtime-safety contract vào **executable canonical governance**.

Logical shape:

```yaml
autonomous_execution:
  max_attempts: 2
```

Exact authority location **chưa khóa trong plan này**.

Trước ADR-006 phải inspect:

```text
constitution/agent-runtime.yaml
constitution/policies.yaml
```

Mục tiêu:

```text
one canonical declaration
runtime reads that declaration
no duplicated authority
no permissive fallback
no hardcoded "2" spread across implementation
```

`constitution/policies.yaml` hiện là candidate hợp lý, nhưng ADR-006 chỉ được chốt sau khi inspect `agent-runtime.yaml`.

---

## 10. Artifact / trace plan

Không thêm bureaucracy ngoài full T2 chain cần thiết.

| Artifact | Purpose |
|---|---|
| `PROB-002` | Autonomous AI execution thiếu measured cost + hard runtime stop |
| `FR-006` | Capture automatic per-call / per-DEV cost telemetry |
| `FR-007` | Enforce bounded execution / circuit breaker |
| `NFR-002` | No unmetered autonomy; durable execution/circuit/failure evidence |
| `CMP-003` | Bounded AI Execution Runtime boundary |
| `ADR-006` | Telemetry store + execution-scope semantics + model-call gateway + state machine |
| `DEV-007` | Cost telemetry + model-call gateway instrumentation |
| `TEST-007` | Telemetry correctness / attribution / aggregation / usage anomaly |
| `DEV-008` | Runtime attempt controller + circuit breaker |
| `TEST-008` | `MAX_ATTEMPTS`, persistence, anti-bypass, hard-stop enforcement |

Cả slice là **T2** vì nó thay đổi runtime governance / reliability và sẽ chạm architecture / ADR paths vốn thuộc T2-sensitive namespace.

Implementation order:

```text
runtime/provider discovery
        ↓
PROB-002 / FR-006 / FR-007 / NFR-002
        ↓
CMP-003 / ADR-006
        ↓
DEV-007 telemetry + gateway
        ↓
TEST-007
        ↓
prove no controlled autonomous call can be unmetered
        ↓
DEV-008 attempt controller + circuit breaker
        ↓
TEST-008
        ↓
prove hard stop + anti-bypass
        ↓
declare chat-heavy control window
        ↓
Phase 1.1 experiments
```

---

## 11. Required discovery before ADR-006

Trước khi viết ADR-006 final phải chứng minh reality của bootstrap path.

### 11.1 Runtime boundary discovery

Phải trả lời:

```text
Codex / current autonomous flow được invoke bằng path nào?
CLI wrapper?
SDK/API?
subprocess?
other?
```

Không được thiết kế gateway dựa trên assumption.

### 11.2 Usage availability

Chosen provider/runtime path phải expose exact machine-readable usage đủ để automatic telemetry hoạt động.

Nếu không expose exact usage:

```text
that path is NOT eligible
for bounded autonomous Phase-1 mode
```

Có thể vẫn dùng manual/human-assisted flow, nhưng không được claim measured autonomous execution.

### 11.3 Governance authority

Inspect `constitution/agent-runtime.yaml` và `constitution/policies.yaml` để khóa một source duy nhất cho `max_attempts`.

---

## 12. Acceptance tests required before coding

### 12.1 Telemetry / gateway

| Test | Expected result |
|---|---|
| One successful attempt | one call recorded, exact usage attributable to DEV, no retry |
| Missing DEV attribution | reject before provider |
| Missing `execution_scope_id` | reject before provider |
| Telemetry store unavailable before call | reject locally; provider invocation unchanged |
| Provider returns no usable usage | persist `usage_status=unknown`; never record zero; stop autonomous continuation |
| Failed attempt before eventual acceptance | failed-attempt usage remains in accepted DEV aggregate |
| DEV rejected/abandoned | usage retained in attempted-DEV metrics |
| Reviewer-call simulation | usage charged to DEV; implementation attempt count unchanged |
| Model profile capture | model, reasoning effort, selection strategy, routing policy version persisted |
| Context profile capture | declared context strategy persisted |

### 12.2 Circuit breaker

| Test | Expected result |
|---|---|
| Attempt 1 fails, attempt 2 succeeds | 2 attempts; both costs retained |
| Attempts 1 + 2 fail | persisted `CIRCUIT_OPEN`; human attention required |
| Third implementation request after open | rejected locally; provider invocation count unchanged |
| Process restart after circuit open | circuit remains open |
| New `run_id` for same scope | does not reset attempt count |
| New call after circuit open | blocked until explicit governed resume/new scope |
| Human-authorized new scope | new scope may start; old attempts/cost remain immutable |
| Baseline regression | all existing Phase-0/DEV-006 validator/environment/trace tests continue passing |

---

## 13. Chat-heavy baseline

Sau DEV-007 và DEV-008, declare một short measurement window trước mọi context/routing optimization.

Baseline phải cố định tối thiểu:

```text
task mix
trace-level mix
model
reasoning effort
model-selection strategy
routing policy
review policy
acceptance criteria
context_strategy = chat-heavy
```

Measurement window phải đủ để tính:

```text
input tokens / accepted DEV
total tokens / accepted DEV
attempts / accepted DEV
model calls / accepted DEV
first-attempt acceptance rate
overall acceptance rate
human-attention rate
```

Nếu exact monetary/credit usage khả dụng, capture thêm nhưng không block baseline nếu token telemetry đã exact và contract cho phép.

Historical DEV-001..006 usage remains **unknown**, not zero; không retro-estimate.

---

## 14. Phase 1.1 — Cost optimization experiments

### 14.1 Experiment A — Context / Graphify

So sánh:

```text
chat-heavy baseline
vs
declared Graphify / Context Pack treatment
```

Giữ cố định:

```text
model
reasoning effort
model selection/routing policy
task/eval mix
review policy
acceptance criteria
```

Primary gate:

```text
Average input tokens per accepted DEV task
```

Required treatment reduction:

```text
>= 70%
```

Nếu Graphify bundled với Context Pack, kết quả là ROI của **declared combined treatment**, không được claim là ROI riêng của Graphify.

Quality/governance/security regression override token savings.

### 14.2 Experiment B — Model-tier / reasoning-effort routing

Chỉ chạy sau khi context treatment effect đã được hiểu riêng.

Giữ cố định:

```text
context strategy
task/eval mix
acceptance policy
review policy
```

Treatment candidates có thể gồm:

```text
lower-cost model for bounded low-ambiguity work
higher reasoning only for T2 / ambiguity
manual tier selection
risk-routed tier selection
```

Đánh giá bằng Lean scorecard, không chỉ token count.

Một model tier rẻ hơn chỉ PASS nếu:

```text
economic/resource cost decreases
AND
quality/governance/security guardrails do not regress unacceptably
AND
retry/human-attention waste does not erase savings
```

### 14.3 Experiment C — Combine proven treatments

Chỉ combine Graphify/Context treatment và model-tier routing sau khi từng treatment đã có evidence riêng.

Không dùng experiment kiểu:

```text
GPT-X + chat-heavy
vs
GPT-Y + Graphify + Context Pack + routing
```

rồi gán toàn bộ saving cho một component.

---

## 15. Blockers vs non-blocking debt

### 15.1 Phase-1.0 blockers

**Blocker 1 — Controlled egress boundary**

Hiện chưa có runtime boundary nào được chứng minh là sở hữu mọi autonomous model call. Phase 1.0 phải tạo minimal gateway đó.

**Blocker 2 — Exact machine-readable usage**

Chosen runtime/provider path phải expose exact usage đủ cho automatic telemetry. Không có exact usage thì flow đó không đủ điều kiện bật measured autonomous Phase-1 mode.

**Blocker 3 — Scope anti-bypass semantics**

Execution-scope identity và reset/resume semantics phải khóa trước khi circuit breaker được claim là effective.

**Blocker 4 — Canonical max-attempt authority**

Phải có một source duy nhất cho `MAX_ATTEMPTS`; runtime không được hardcode hay đọc nhiều conflicting declarations.

### 15.2 Non-blocking debt

Không phải blocker cho Phase 1.0:

```text
remote telemetry backend
dashboards
full monetary-cost normalization
Graphify integration
Context Pack
full ARI
multi-agent concurrency
semantic critic
provider router
automatic model-tier routing
cross-machine telemetry service
full runtime feedback/evolution loop
```

Những thứ này tiếp tục deferred cho tới khi có measured need.

---

## 16. Definition of Done cho ADR-006

ADR-006 chỉ đủ để chuyển sang code khi trả lời không mơ hồ tám câu hỏi:

```text
1. Model call nào đi qua boundary nào?

2. Token / call / attempt được persist ở đâu
   và attributable về DEV như thế nào?

3. Event nào increment attempt và event nào mở circuit?

4. Test nào chứng minh provider không nhận call thứ ba?

5. execution_scope_id khác run_id như thế nào,
   và run mới không thể bypass circuit budget ra sao?

6. Provider usage nào được coi là exact;
   missing/unusable usage được xử lý thế nào
   mà không biến unknown thành zero?

7. Model / reasoning / context / routing dimensions nào
   phải capture để future Lean experiments isolate treatment?

8. Sau CIRCUIT_OPEN, human resume/reset semantics là gì
   mà vẫn giữ historical attempts/cost immutable?
```

Nếu bất kỳ câu nào chưa có answer deterministic/testable, chưa code.

---

## 17. Phase 1.0 Definition of Done

Phase 1.0 chỉ được coi là complete khi:

```text
[ ] every controlled autonomous model call passes through the gateway
[ ] every issued model call is attributable to DEV + scope + run + attempt
[ ] exact provider usage is automatically recorded when available
[ ] unknown usage is explicit and never converted to zero
[ ] runtime policy enforces MAX_ATTEMPTS = 2
[ ] third implementation call after two failures cannot reach provider
[ ] restart does not reset circuit state
[ ] new run_id cannot reset same-scope attempt budget
[ ] human resume/new-scope action preserves historical evidence
[ ] DEV-level aggregate metrics are reproducible from retained telemetry
[ ] model/reasoning/context/routing dimensions are captured
[ ] chat-heavy control baseline is declared
[ ] existing deterministic governance / CI / regression gates remain intact
```

Khi các điều kiện này PASS, Factory đã chứng minh capability cốt lõi:

> **bounded, measurable, cost-aware AI execution**

và mới đủ điều kiện bước sang Phase 1.1 Cost Optimization experiments.
