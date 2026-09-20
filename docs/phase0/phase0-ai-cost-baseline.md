---
id: CP-AI-COST-BASELINE
type: closure-artifact
phase: 0
status: final
author: SDF-Orchestrator
title: "Phase 0 AI Cost Baseline & Circuit Breaker Contract"
version: "1.0"
date: "19/09/2026"
lang: vi-VN
---

# Phase 0 AI Cost Baseline & Circuit Breaker Contract

Đây là **measurement + runtime safety contract** cho entry vào Phase 1. Architecture/routing authority nằm tại [CP-REFERENCE-ARCHITECTURE](../reference/ai-native-sdf-reference-architecture.md), đặc biệt Sections 9, 20 và 23.

## Authority boundary

Closure Pack artifacts summarize, index, measure hoặc attest evidence. Chúng **MUST NOT** trở thành competing canonical source cho decisions, executable governance hoặc trace truth.

- Architecture/operating model authority: [CP-REFERENCE-ARCHITECTURE](../reference/ai-native-sdf-reference-architecture.md)
- Accepted decisions: `design/decisions/ADR-*`
- Executable governance: `constitution/*`
- Trace truth: `knowledge/traceability.yaml`

## 1. Normative rules

- Autonomous runtime MUST enforce `MAX_ATTEMPTS = 2`.
- Sau failed attempt thứ hai, circuit MUST open **trước** model call tiếp theo.
- Runtime MUST block further model calls, persist failure evidence/attempt summaries và return failure/human-attention event.
- Human MUST NOT phải ngồi canh terminal để cắt credit flow.
- Cost telemetry MUST có trước khi bounded autonomous Phase 1 operation được enable.
- Một **attempt** là một autonomous implementation/test cycle cho cùng execution scope. Reviewer, critic hoặc orchestration model call không tự tạo thêm implementation attempt, nhưng usage của chúng MUST vẫn được charge vào DEV task.

## 2. Historical Phase 0 baseline status

[DEV-001]–[DEV-005] được thực hiện trước khi automatic per-call token telemetry tồn tại. Historical token values vì vậy là **unknown**, không phải `0`. Tài liệu MUST NOT retroactively estimate số liệu thiếu.

Known execution facts:

- Phase 0 workflow tương đối chat-heavy và có repeated context/review;
- [DEV-005] dùng Minimal Execution Prompt và implementation/test attempt 1 thành công;
- deterministic validation đã chứng minh có thể loại nhiều work khỏi AI path.

Nếu provider logs sau này recover được exact historical usage, dữ liệu MAY được import với provenance rõ.

## 3. Mandatory per-call telemetry

```yaml
dev_task: DEV-###
traceability_level: T0|T1|T2
run_id: ...
agent_role: ...
provider: ...
model: ...
source_revision: ...
context_strategy: chat-heavy|manual-context-pack|graphify-context-pack|other
usage:
  input_tokens: ...
  output_tokens: ...
  total_tokens: ...
execution:
  attempt_number: 1|2
  review_call: true|false
  started_at: ...
  finished_at: ...
  result: success|failure|cancelled|circuit_open
outcome:
  task_accepted: true|false
```

`task_accepted` là final DEV-level outcome và MAY được backfill/update sau khi acceptance gate hoàn tất; nó không phải result của riêng model call hiện tại.

## 4. DEV-level aggregation

For one accepted [DEV-*] task:

```text
DEV input tokens = Σ input tokens của mọi implementation/review/retry/orchestration call gắn với task
DEV output tokens = Σ output tokens của mọi call gắn với task
DEV total AI tokens = DEV input tokens + DEV output tokens
DEV attempts = số bounded execution attempts
DEV model calls = tất cả model calls charge vào task
```

Failed attempts trước khi task được accept MUST vẫn nằm trong numerator. Rejected/abandoned task MUST giữ usage record riêng.

## 5. Cost per accepted DEV task

Nếu provider monetary cost khả dụng:

```text
Cost per accepted DEV task
= Σ monetary AI cost attributable to accepted DEV tasks in window
  / number of accepted DEV tasks in window
```

Primary model-independent KPI:

```text
Average input tokens per accepted DEV task
= Σ input tokens attributable to accepted DEV tasks in window
  / number of accepted DEV tasks in window
```

MUST report separately cho T0, T1, T2 và aggregate all-level.

Additional MUST metrics:

- total AI tokens / accepted DEV;
- attempts / accepted DEV;
- model calls / accepted DEV;
- input tokens / attempted DEV;
- acceptance rate.

## 6. Circuit breaker state machine

```text
ATTEMPT_1
  ├─ success → validation/review
  └─ failure → ATTEMPT_2

ATTEMPT_2
  ├─ success → validation/review
  └─ failure → CIRCUIT_OPEN

CIRCUIT_OPEN
  → block model calls
  → persist failing command/log
  → persist attempt summaries
  → mark human_attention_required
  → exit/return failure
```

Prompt text MAY remind the agent about budget but MUST NOT be the enforcement mechanism.

## 7. Graphify Lean ROI gate

Graphify/context-pack experiment uses:

> **Average input tokens per accepted DEV task**

Baseline MUST được declared trước experiment. Nếu historical Phase 0 telemetry không đủ, Factory SHOULD chạy một short chat-heavy control window với automatic telemetry trước khi bật Graphify.

```text
reduction = 1 - (graphify_avg_input_tokens / baseline_avg_input_tokens)
```

Acceptance:

```text
reduction >= 70%  → ROI PASS
reduction < 70%   → Lean waste for tested use case
```

Nếu fail threshold, integration MUST be removed, redesigned hoặc rejected. Token reduction MUST NOT override quality, traceability, security hoặc governance regression.

Experiment boundary MUST được declared trước measurement.

Nếu Graphify được test như một phần của `graphify-context-pack`, threshold ≥70% áp dụng cho toàn bộ treatment đã declared; kết quả MUST NOT được diễn giải là ROI riêng của Graphify nếu Context Pack hoặc routing thay đổi đồng thời.

Baseline và treatment SHOULD giữ comparable task mix, trace-level mix, model/reasoning policy, review policy và acceptance criteria. Những optimization khác SHOULD được giữ cố định hoặc đo như experiment riêng.

## 8. Phase 1 entry checklist

- [ ] per-call usage telemetry tự động;
- [ ] every model call attributable to [DEV-*] + trace level;
- [ ] DEV-level aggregates;
- [ ] runtime circuit breaker `MAX_ATTEMPTS = 2`;
- [ ] failure evidence persisted automatically;
- [ ] accepted/rejected outcome recorded;
- [ ] chat-heavy baseline strategy declared;
- [ ] Graphify experiment measured against ≥70% threshold before promotion.
