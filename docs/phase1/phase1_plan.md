# Phase 1.0 — Architecture / Design Plan

**Baseline chính thức:** `phase0-complete` @ `f8a1a0a71fca25caee80003f37250eb3b7d5ce4b`. Phase 0 đã closed và verified; Phase 1 bắt đầu bằng **cost telemetry → runtime circuit breaker → chat-heavy baseline**, trước Graphify hay bounded multi-agent automation.  

**Verdict:** Phase 1.0 nên là **một T2 design increment**, nhưng implementation sau này nên tách thành hai small batches: **DEV-006 Telemetry trước, DEV-007 Circuit Breaker sau**. Không code trong bước hiện tại.

## 1. Invariants cần khóa trước

| ID     | Invariant                                                                                                                  |
| ------ | -------------------------------------------------------------------------------------------------------------------------- |
| P1-I01 | Mọi autonomous model call thuộc Phase 1 flow MUST đi qua **một runtime egress boundary duy nhất**.                         |
| P1-I02 | Không model call nào được phát hành nếu không biết `DEV task`, trace level, `run_id`, source revision và attempt hiện tại. |
| P1-I03 | Usage của implementation, retry và future review/orchestration calls đều charge vào cùng DEV.                              |
| P1-I04 | `MAX_ATTEMPTS = 2` là **runtime policy**, không phải prompt convention.                                                    |
| P1-I05 | Sau attempt 2 failure, `CIRCUIT_OPEN` phải được persist **trước** khi call tiếp theo có thể được phát hành.                |
| P1-I06 | Call bị circuit chặn không được chạm provider và không được tính là model call.                                            |
| P1-I07 | Missing/unusable token telemetry không được silently tiếp tục autonomous execution.                                        |
| P1-I08 | Telemetry không trở thành design/canonical truth; canonical policy/design vẫn nằm trong Git.                               |
| P1-I09 | Raw prompt/response text không được lưu chỉ để tính cost; mặc định chỉ lưu accounting metadata/evidence cần thiết.         |
| P1-I10 | Phase 1.0 không phụ thuộc Graphify, ARI hoàn chỉnh hay multi-agent orchestration.                                          |

Những invariant này trực tiếp hiện thực hóa contract hiện có: `MAX_ATTEMPTS=2`, circuit mở sau failure thứ hai, block subsequent calls, persist failure evidence, và human không đóng vai trò circuit breaker.  

## 2. Component boundary

Không mở rộng `CMP-002`. Component đó hiện chịu trách nhiệm deterministic artifact/traceability/provenance validation. 

Đề xuất:

```text
CMP-003 — Bounded AI Execution Runtime

Execution request
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
      ├── persist call-start
      ├── invoke provider
      └── persist usage/result
      │
      ▼
Implementation/Test cycle
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

`CMP-003` chỉ là **bootstrap runtime control**, không phải ARI. Reference architecture vẫn coi ARI là target sau này và yêu cầu provider neutrality, không biến Codex thành control-plane authority. 

## 3. Runtime enforcement point

Enforcement phải nằm **ngay trước provider invocation**, không nằm trong agent prompt và cũng không nằm sau khi call đã phát đi.

Interface khái niệm:

```text
request_model_call(call_context)
        │
        ▼
[ Budget / Circuit Guard ]
        │
        ├── circuit_open ? → reject locally
        ├── valid DEV/run/attempt ? → required
        ├── telemetry writable ? → required
        │
        ▼
[ Provider Adapter / Codex bootstrap ]
```

Điểm này tạo một property có thể test rất mạnh:

> Sau hai failed implementation attempts, test thứ ba phải chứng minh **provider mock invocation count vẫn bằng 2**.

Reference architecture đã xác định đây là một agent eval case cần có: circuit breaker phải chặn model call thứ ba sau hai failed attempts. 

Quan trọng: **manual Codex use của human không cần bị “cấm” toàn cục**. Scope enforcement là autonomous Phase-1 execution path. Nhưng bất kỳ flow nào muốn claim là “bounded autonomous execution” đều bắt buộc đi qua gateway này.

## 4. Attempt semantics

Giữ nguyên contract hiện tại:

```text
attempt
= one autonomous implementation + test/validation cycle
  for the same execution scope
```

Reviewer/critic/orchestrator call không tăng attempt counter, nhưng usage vẫn charge vào DEV. 

Tôi đề nghị thêm một clarification quan trọng trong ADR:

```text
model response success != attempt success

attempt success
= execution cycle reached its deterministic acceptance checkpoint successfully
```

Agent không được tự nói “done” rồi reset budget. **Attempt transition do runtime/deterministic result quyết định.**

Phase 1.0 golden path ban đầu chỉ cần **một executor call trong mỗi attempt**. `review_call` vẫn có trong schema cho future compatibility, nhưng không bật autonomous reviewer trong batch này.

## 5. Minimal telemetry contract

Contract Phase 0 đã định nghĩa các field bắt buộc.  Tôi sẽ giữ chúng và chỉ thêm identity cần thiết để enforcement không mơ hồ:

| Group                   | Field                                                     |
| ----------------------- | --------------------------------------------------------- |
| Attribution             | `dev_task`, `traceability_level`                          |
| Execution identity      | `run_id`, `execution_scope_id`, `call_id`                 |
| Agent/runtime           | `agent_role`, `provider`, `model`                         |
| Reproducibility         | full `source_revision`                                    |
| Treatment               | `context_strategy`                                        |
| Usage                   | `input_tokens`, `output_tokens`, `total_tokens`           |
| Budget                  | `attempt_number`, `review_call`                           |
| Timing                  | `started_at`, `finished_at`                               |
| Call result             | `success / failure / cancelled`                           |
| DEV outcome             | `task_accepted = null/true/false`                         |
| Optional reconciliation | provider request ID, monetary cost when exact data exists |

`context_strategy` giữ nguyên vocabulary:

```text
chat-heavy
manual-context-pack
graphify-context-pack
other
```

Như vậy Phase 1.1 có thể so sánh treatment mà không đổi measurement semantics.

Primary KPI vẫn là:

```text
average input tokens per accepted DEV task
```

và failed attempts/reviews trước acceptance vẫn nằm trong numerator.  

## 6. Persistence boundary

Tôi đề xuất **SQLite local operational evidence store** cho Phase 1.0, thay vì YAML/Markdown/JSON canonical files.

Ví dụ logical location:

```text
.sdf/runtime/ai-execution.sqlite3
```

File runtime này phải ignored khỏi Git.

Lý do chọn SQLite cho bootstrap: standard-library, không cần service mới, transaction atomic, có thể giữ attempt/circuit state cùng telemetry, hỗ trợ final `task_accepted` update, dễ query DEV aggregates, và tránh việc crash giữa “attempt 2 failed” với “circuit opened”.

Logical model chỉ cần bốn concepts:

```text
ExecutionRun
  run_id
  DEV / trace level / revision / context strategy
  state
  task_accepted

Attempt
  run_id + attempt_number
  start/end/result
  failure evidence reference

ModelCall
  call_id
  run_id + attempt
  role/provider/model
  token usage
  timing/result

FailureEvidence
  run_id + attempt
  command / exit code
  log reference
```

Canonical Git giữ **policy, schema, ADR, component, task/test definitions**. SQLite giữ **observed runtime evidence**. Aggregates/reports được derive từ store; chúng không được quay lại trở thành competing source of truth. Authority separation này phù hợp với baseline hiện tại. 

Không lưu full prompt/response mặc định. Failure log phải được persist theo circuit-breaker contract, nhưng cần respect data classification/redaction thay vì biến telemetry DB thành secret dump.

## 7. Canonical policy

`MAX_ATTEMPTS = 2` nên được promote từ closure measurement contract vào **executable canonical governance**, ví dụ logical policy:

```yaml
autonomous_execution:
  max_attempts: 2
```

Tôi ưu tiên `constitution/policies.yaml`, vì đây là policy chứ không phải provider configuration hay prompt instruction. Chi tiết exact location nên được chốt trong ADR-006 sau khi inspect `constitution/agent-runtime.yaml`; không nên có hai declarations cùng authority.

Điểm quan trọng là runtime **đọc canonical value**, không hardcode `2` ở ba nơi.

Đây cũng tiếp tục pattern đã chứng minh ở ADR-004: canonical governance điều khiển evaluator thay vì Python sở hữu policy default. 

## 8. Artifact / trace plan

Không cần thêm bureaucracy ngoài full T2 chain tối thiểu:

| Artifact đề xuất | Mục đích                                                             |
| ---------------- | -------------------------------------------------------------------- |
| `PROB-002`       | Autonomous AI execution hiện thiếu measured cost + hard runtime stop |
| `FR-006`         | Capture automatic per-call/per-DEV cost telemetry                    |
| `FR-007`         | Enforce bounded execution / circuit breaker                          |
| `NFR-002`        | No unmetered autonomous execution; durable failure state/evidence    |
| `CMP-003`        | Bounded AI Execution Runtime boundary                                |
| `ADR-006`        | Telemetry store + model-call gateway + state-machine decision        |
| `DEV-006`        | Telemetry persistence + gateway instrumentation                      |
| `TEST-006`       | Telemetry correctness/aggregation                                    |
| `DEV-007`        | Runtime attempt controller + circuit breaker                         |
| `TEST-007`       | MAX_ATTEMPTS/circuit enforcement                                     |

Cả slice là **T2**: nó thay đổi reliability/runtime governance, và design/architecture/ADR paths vốn đã là T2-sensitive paths theo current policy. 

Implementation nên theo thứ tự:

```text
ADR-006 / CMP-003 design
        ↓
DEV-006 telemetry
        ↓
prove all calls metered
        ↓
DEV-007 circuit breaker
        ↓
prove hard stop
        ↓
chat-heavy measurement window
        ↓
Phase 1.1
```

## 9. Acceptance tests cần thiết trước khi code

| Test                                            | Expected result                                                         |
| ----------------------------------------------- | ----------------------------------------------------------------------- |
| One successful attempt                          | one call recorded, tokens attributable to DEV, no retry                 |
| Attempt 1 fails, attempt 2 succeeds             | 2 attempts; both costs included                                         |
| Attempts 1 + 2 fail                             | persisted `CIRCUIT_OPEN`, human attention required                      |
| Third implementation request after circuit open | rejected locally; provider invocation count unchanged                   |
| Process restart after circuit open              | circuit remains open                                                    |
| Reviewer-call simulation                        | usage charged to DEV, attempt count unchanged                           |
| Missing DEV attribution                         | model call rejected before provider                                     |
| Telemetry store unavailable                     | autonomous call fails closed rather than spending unmetered             |
| Provider returns no usable usage                | record anomaly and do not continue autonomous retry blindly             |
| DEV eventually accepted after failed attempt    | failed-attempt tokens included in accepted DEV aggregate                |
| DEV rejected/abandoned                          | cost retained; not dropped from attempted-DEV metrics                   |
| Baseline regression                             | all existing Phase-0 validator/environment/trace tests continue passing |

The existing Phase-1 entry checklist already demands automatic per-call telemetry, DEV attribution, DEV aggregation, runtime breaker, failure evidence and final accepted/rejected outcome. 

## 10. Blockers vs non-blocking debt

**Hai blockers thực sự** cần solve trong implementation design là: thứ nhất, hiện chưa có controlled runtime boundary nào được chứng minh là sở hữu mọi autonomous model call; Phase 1.0 phải tạo minimal gateway đó. Thứ hai, runtime/provider path được chọn phải expose **exact machine-readable usage** đủ để automatic telemetry hoạt động; nếu không có, flow đó không đủ điều kiện bật autonomous Phase-1 mode.

Không phải blocker cho Phase 1.0: monetary cost conversion, remote telemetry backend, dashboards, Graphify, full ARI, multi-agent concurrency, semantic critic, Context Pack, provider router. Những thứ này nên tiếp tục deferred.

### Definition of Done cho design phase hiện tại

Design được coi là đủ để chuyển sang code khi **ADR-006 có thể trả lời không mơ hồ bốn câu hỏi**:

```text
1. Model call nào đi qua boundary nào?
2. Token/call/attempt được persist ở đâu và attributable thế nào?
3. Chính xác event nào increment attempt / open circuit?
4. Test nào chứng minh provider không nhận call thứ ba?
```

Nếu bốn câu đó khóa được, Phase 1.0 đủ nhỏ để triển khai mà **không xây platform trước nhu cầu**, đồng thời vẫn đạt mục tiêu cốt lõi: **prove bounded, cost-aware AI execution**. 
