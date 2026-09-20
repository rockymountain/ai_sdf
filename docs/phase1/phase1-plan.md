# Phase 1.0 — Architecture / Design Plan

**Status:** Working plan — non-canonical.

**Authority boundary:** Tài liệu này định hướng sequencing và design work của Phase 1. Nó **không** thay thế authority của `design/decisions/ADR-*`, `design/architecture/*`, `constitution/*` hoặc `knowledge/traceability.yaml`. Accepted architecture phải được khóa bằng ADR/CMP; executable governance nằm trong `constitution/*`; trace truth nằm trong `knowledge/traceability.yaml`.

**Immutable Phase-0 baseline:** `phase0-complete` @ `f8a1a0a71fca25caee80003f37250eb3b7d5ce4b`.

**Phase-1 plan baseline:** `main` @ `5fa08dbdb9870a0907d8f9aac7fa7b4c5cf928a8`. This is the baseline from which the Phase-1 design plan was introduced and reviewed; it need not track later `main` commits.

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
DEV-007 — AIRuntimePort + CodexRuntimeAdapter + telemetry + finite watchdog
DEV-008 — MAX_ATTEMPTS policy + Attempt Controller + Circuit Breaker
```

DEV-007 owns the canonical `autonomous_execution.max_invocation_seconds` policy/read,
exact-or-unknown evidence, and the tool-bearing live runtime acceptance proof. Its
schema requires a positive integer, and a human-approved value is required before
that live test. DEV-008 owns `max_attempts=2`, attempt/circuit state,
successor-scope provenance, and anti-bypass behavior.

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

## 2. Invariants required before implementation

| ID | Invariant |
|---|---|
| P1-I01 | Every Phase-1 `ControlledAIInvocation` MUST pass through the single controlled runtime egress boundary. |
| P1-I02 | Every `ControlledAIInvocation` has mandatory SDF identities and `invocation_purpose`. Implementation requires `reservation_id` and `candidate_attempt_number`; continuation requires existing consumed-attempt lineage; `acceptance_validation`, review, and orchestration may omit implementation-attempt identity only under governed non-mutating capability restrictions. `attempt_number` exists only after `RESERVED -> CONSUMED`. |
| P1-I03 | Usage from every `ControlledAIInvocation` is charged to its DEV, including implementation, continuation, `acceptance_validation`, review, and orchestration. |
| P1-I04 | `MAX_ATTEMPTS = 2` is runtime policy, not a prompt convention. |
| P1-I05 | Failure of consumed attempt 2 and `CIRCUIT_OPEN` MUST persist atomically before new implementation work is authorized. |
| P1-I06 | A blocked invocation MUST NOT reach `AIRuntimePort`. |
| P1-I07 | Missing usage is `unknown`, never zero, and stops autonomy unless a governed continuation rule applies. |
| P1-I08 | Telemetry is operational evidence; canonical policy/design remain in Git. |
| P1-I09 | Raw prompts/responses are not retained solely for accounting. |
| P1-I10 | Phase 1.0 does not depend on Graphify, full ARI, or multi-agent orchestration. |
| P1-I11 | Attempt budget belongs to `execution_scope_id`; process, run, and runtime session cannot reset it. |
| P1-I12 | After `CIRCUIT_OPEN` the scope remains closed. Further work requires a human-authorized successor scope with predecessor, actor, timestamp, reason, and disposition; old evidence remains immutable. |
| P1-I13 | Reservation, budget evaluation, reservation transitions, consumed-attempt binding, and circuit transition MUST be atomic for one scope. Concurrent processes cannot obtain the same active candidate slot. |
| P1-I14 | Every controlled invocation has a finite watchdog. Expiry interrupts through `AIRuntimePort`, records terminal evidence, preserves exact usage or records unknown usage, and requires reconciliation. |
| P1-I15 | Canonical policy, state, telemetry, and acceptance logic depend on SDF concepts and `AIRuntimePort`, not Codex SDK types. |
| P1-I16 | A consumed attempt may continue only after a governed resumable external condition. Phase 1.0 permits only `usage_limit`, requires human authorization, preserves scope/objective/attempt, and links a new invocation with `resume_of_invocation_id`. Automatic resume is disabled. |
| P1-I17 | At most one implementation attempt is open for an `execution_scope_id`. Active `RESERVED`, `UNRESOLVED`, or an unclosed consumed attempt blocks every new reservation across restart and concurrency. |

P1-I13 separates reservation from consumption. `RELEASED` retains evidence and
frees its candidate slot; reservation `UNRESOLVED` keeps the slot unavailable.
P1-I16 concerns interruption after consumption and is distinct from reservation
uncertainty and post-circuit successor-scope authorization.

P1-I14 applies to every invocation. Timeout always interrupts through
`AIRuntimePort`, records `terminal_status=timeout`, preserves exact usage or records
unknown usage, never zero, and requires human attention. Only a timeout linked to a
consumed attempt enters `RECONCILIATION_REQUIRED`; a non-attempt timeout creates no
attempt state or capacity and stops scope follow-on pending governed disposition.

---

## 3. Component boundary

The final Phase-1.0 topology is:

```text
SDF workflow
  -> Execution Scope / Budget Guard
  -> Attempt Controller
  -> ControlledAIInvocation Gateway
  -> AIRuntimePort
  -> replaceable runtime adapter
  -> opaque 0..N provider-internal requests
```

`AIRuntimePort` is the hard boundary and exposes start/invoke, observe/stream
evidence, and interrupt. SDK semantics remain inside `CodexRuntimeAdapter`.

DEV-007 implements the gateway, port, adapter, telemetry, canonical
`max_invocation_seconds` read, watchdog, and live tool-bearing acceptance proof.
That live invocation is explicitly human-authorized `acceptance_validation`, omits
attempt identity, performs no autonomous implementation work, and does not enable
autonomous multi-attempt retry. DEV-008 adds `max_attempts=2`, the Attempt Controller,
reservation/consumption state, circuit, one-open-attempt enforcement, and
successor-scope anti-bypass. Retry may be enabled only after DEV-008.

---

## 4. Runtime enforcement point

Enforcement occurs immediately before `AIRuntimePort` starts a
`ControlledAIInvocation`.

```text
require DEV / trace / scope / run / invocation / source revision
reject closed or unreconciled scope
for implementation work:
  atomically reserve reservation_id + candidate_attempt_number
  reject if another reservation or consumed attempt is open
verify telemetry writable
persist invocation start + finite watchdog
start through AIRuntimePort
```

Every invocation declares `invocation_purpose`: `implementation`, `continuation`,
`acceptance_validation`, `review`, or `orchestration`. Implementation reserves
capacity; continuation requires an existing consumed attempt and P1-I16 lineage.
Human-authorized `acceptance_validation`, review, and orchestration may omit attempt
identity. Acceptance validation performs no autonomous implementation work and
creates or replenishes no budget. All purposes retain mandatory SDF identities, and
purpose classification cannot bypass attempt governance. Any invocation without
implementation-attempt identity is prohibited from repository/workspace
implementation mutation. Mutation requires `implementation` or P1-I16
`continuation`; an adapter may enforce this with a read-only sandbox or equivalent
provider-neutral capability restriction.

Anti-bypass counts consumed attempts, not adapter invocations. After two consumed
attempts fail, candidate attempt 3 cannot become consumed and no invocation belonging
to attempt 3 can reach `AIRuntimePort`. Continuations inside an existing attempt do
not alter `MAX_ATTEMPTS`.

---

## 5. Execution scope, reservation, attempt, and continuation semantics

### 5.1 Execution scope

`execution_scope_id` is the stable governed execution-objective identity. It owns
implementation-attempt budget when implementation applies. Non-implementation
invocations still use it for attribution, provenance, lifecycle, and circuit
enforcement without creating attempt capacity. `run_id` is one workflow/process
execution instance; new runs or runtime sessions do not reset scope budget.

`source_revision` identifies the canonical Git base revision associated with the
governed objective/invocation. It does not imply a clean tree, absence of partial
edits, or a complete input snapshot. P1-I16 continuation may retain the same base
revision while resuming partial workspace changes. Phase 1.0 adds no workspace
fingerprint, checkpoint, or exact replay subsystem.

### 5.2 Reservation lifecycle

```text
new transaction -> reservation_id + candidate_attempt_number -> RESERVED
proven pre-start failure -> RELEASED; retain evidence; free slot; consume no budget
affirmative runtime/provider acceptance -> CONSUMED; candidate_attempt_number -> attempt_number
affirmative evidence runtime definitely did not start -> RELEASED; retain evidence; free slot
insufficient evidence for either -> UNRESOLVED; keep slot; stop; human resolution
```

Released evidence is immutable. A later reservation may reuse the candidate number
with a new reservation ID. From `UNRESOLVED`, later affirmative non-start evidence
moves to `RELEASED`, affirmative accepted-execution evidence moves to `CONSUMED`, and
insufficient evidence remains `UNRESOLVED`. Each adapter defines its concrete
evidence mapping in conformance specifications.

If evidence remains permanently insufficient, the reservation stays immutable and
`UNRESOLVED`, its scope stays stopped, and budget remains unavailable. Continued work
requires a linked, human-authorized successor scope recording predecessor, actor,
timestamp, reason, and disposition. An unlinked new scope is prohibited.

### 5.3 Consumed-attempt lifecycle

```text
OPEN
  -> deterministic PASS -> PASSED
  -> deterministic FAIL -> FAILED
  -> usage_limit -> SUSPENDED -> human-authorized continuation -> OPEN
  -> uncertain non-resumable terminal evidence -> RECONCILIATION_REQUIRED
```

Only deterministic acceptance closes an attempt. Timeout, runtime failure, network
error, cancellation, and unknown terminal state are not automatically resumable.

### 5.4 Interruption-aware continuation

Only affirmative `terminal_status=interrupted` and `terminal_reason=usage_limit` is initially resumable. Continuation requires explicit human
authorization, a new `invocation_id`, `resume_of_invocation_id`, unchanged scope
and objective, the same consumed attempt, and an unclosed checkpoint. It creates no
attempt, replenishes no budget, and decides neither success nor failure. Deterministic
failure cannot be relabeled as resume. Automatic resume is disabled.

From `RECONCILIATION_REQUIRED`, recovered affirmative `interrupted/usage_limit`
evidence moves the attempt to `SUSPENDED`; recovered deterministic checkpoint
evidence determines `PASSED` or `FAILED`; otherwise record human disposition, keep
the scope stopped, and require a successor scope. Human resolution cannot manufacture
a checkpoint result, free consumed budget, or create a retry.

### 5.5 Single open implementation attempt

Active `RESERVED`, reservation `UNRESOLVED`, or an unclosed consumed attempt
blocks a new reservation. The rule survives restart and concurrency. A passed attempt
accepts the scope; only a failed attempt with remaining budget permits the next.

### 5.6 After circuit open

The existing scope remains closed. Further work requires a human-authorized successor
scope recording `predecessor_scope_id`, actor, timestamp, reason, and disposition.
Old reservations, attempts, invocations, and usage remain immutable. Phase 1.0 has no
same-scope budget reset.

### 5.7 Golden path

The golden path is one primary `ControlledAIInvocation` per attempt plus
deterministic validation. Governed continuation invocations may remain in that same
attempt.

---

## 6. Minimal telemetry contract

### 6.1 Required per-invocation dimensions

| Group | Field |
|---|---|
| Attribution | `dev_task`, `traceability_level` |
| Mandatory identity | `execution_scope_id`, `run_id`, `invocation_id`, `source_revision` |
| Purpose | `invocation_purpose`: `implementation`, `continuation`, `acceptance_validation`, `review`, or `orchestration` |
| Implementation reservation | `reservation_id`, `candidate_attempt_number` |
| Consumed attempt | `attempt_number` only after consumption |
| Continuation | `resume_of_invocation_id` and human authorization |
| Optional runtime evidence | session, invocation, and native metadata only when exposed |
| Runtime/profile/treatment | adapter/runtime versions; requested/observed model distinction; capability-aware requested reasoning effort; `model_selection_strategy`; `routing_policy_version`; `context_strategy` |
| Usage | core `input_tokens`, `output_tokens`, `total_tokens`; optional cached-input/reasoning-output; `usage_status=exact|unknown` |
| Lifecycle | `terminal_status` and optional `terminal_reason` |
| Timing/outcome | timestamps and final DEV outcome |

Acceptance-validation, review, and orchestration invocations may omit reservation
and attempt fields. Adapters never invent runtime IDs or unsupported reasoning
effort. Missing optional usage breakdowns are unsupported/absent, never zero, and do
not invalidate otherwise exact core usage. `CodexRuntimeAdapter` captures cached-input
and reasoning-output tokens because Codex exposes them.

`model_selection_strategy` uses `fixed|manual|risk_routed|other`.
`routing_policy_version` may be absent when routing is inactive and must identify the
governed policy if risk-routed or automatic routing is later enabled. Phase 1.0 does
not enable automatic model routing; these fields provide measurement readiness and
permit Phase-1.1 treatments to hold model-selection conditions constant.

`context_strategy` uses `chat-heavy|manual-context-pack|graphify-context-pack|other`.
It is measurement metadata only. Phase 1.0 does not implement Graphify, Context Pack
routing, or automatic context optimization.

### 6.2 Separate vocabularies

```text
terminal_status: success | failure | interrupted | timeout | cancelled | unknown
usage_status: exact | unknown
terminal_reason: usage_limit | watchdog_timeout | runtime_error | user_cancelled | other | unknown
```

`usage_unknown` is not a terminal status. Only affirmative
`terminal_status=interrupted` plus `terminal_reason=usage_limit` is initially
resumable.

### 6.3 Aggregate completeness

Attempt, DEV, and experiment/window aggregates record
`usage_completeness=complete|incomplete`. Complete requires exact usage from every
contributing invocation. Any unknown contribution makes the aggregate incomplete;
known values remain `known_subtotal` and MUST NOT be represented as an exact total.
Unknown is never zero. Unknown usage normally stops autonomy. The sole exception is
human-authorized P1-I16 continuation with affirmative `interrupted/usage_limit`
terminal evidence. Prior unknown usage remains unknown unless machine-readable
evidence is recovered; exact usage is not required before continuation, and enclosing
aggregates remain incomplete until every contribution is exact.

Measurement coverage is `usage-complete accepted DEV / all accepted DEV`.
Incomplete DEV/windows remain visible and cannot be excluded to manufacture exact
KPIs. Exact primary token KPIs and the Phase-1.1 context-treatment gate are
decision-eligible only when every contributing accepted DEV has complete usage.
Otherwise report incomplete coverage and known subtotals without claiming exact
reduction. Future imputation requires separate governed approval and never imputes
zero.

### 6.4 Failure semantics

Before runtime start, failure is local and a reservation may release only when
non-start is proven. After actual or potential start, unknown usage cannot create a
free retry. Reservation-start uncertainty uses reservation `UNRESOLVED`;
interruption after consumption uses consumed-attempt state and reconciliation.

### 6.5 DEV outcome

Phase-0 `task_accepted: true|false` remains unchanged. Until final acceptance,
operational evidence records `outcome_finalized=false` without inventing a result.

---

## 7. Cost Optimization model

### 7.1 Primary Graphify/context KPI

Giữ nguyên:

```text
Average input tokens per accepted DEV task
```

Đây là KPI chính để đánh giá context reduction / Graphify treatment.

Failed attempts và controlled review invocations trước acceptance vẫn nằm trong numerator.

Continuation resource use is real AI cost and remains in DEV and aggregate measurements.

### 7.2 Lean scorecard

Cost Optimization tổng thể không được dựa trên một metric duy nhất.

```text
Efficiency
  input tokens / accepted DEV
  total AI tokens / accepted DEV
  controlled invocations / accepted DEV
  attempts / accepted DEV

Economic
  exact monetary cost / accepted DEV       when provider exposes it
  exact platform credits / accepted DEV    when measurable

Flow
  first-attempt acceptance rate
  overall acceptance rate
  human-attention rate
usage-limit interruptions / DEV
continuation invocations / accepted DEV
input tokens in continuation invocations / accepted DEV
human continuation actions / DEV

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
  DEV / traceability_level / source_revision
  state
  predecessor_scope_id + authorization provenance when applicable

ExecutionRun
  run_id + execution_scope_id
  timing/result

AttemptReservation
  reservation_id
  execution_scope_id
  candidate_attempt_number
  state: RESERVED | RELEASED | CONSUMED | UNRESOLVED
  evidence reference

ConsumedAttempt
  execution_scope_id + attempt_number (unique)
  reservation_id
  state: OPEN | SUSPENDED | PASSED | FAILED | RECONCILIATION_REQUIRED
  deterministic checkpoint evidence

ControlledAIInvocation
  mandatory DEV / trace / scope / run / invocation / source identities
  invocation_purpose
  reservation_id + candidate_attempt_number when reserving implementation capacity
  attempt_number after consumption
  resume_of_invocation_id + human authorization when continuing
  optional runtime correlation
  requested/observed model evidence
  model_selection_strategy + routing_policy_version
  context_strategy
  usage_status + token values
  terminal_status + terminal_reason
  timing/result

UsageAggregate
  subject: attempt | DEV | experiment/window
  known_subtotal
  usage_completeness: complete | incomplete

FailureEvidence
  reservation_id when applicable
  execution_scope_id
  attempt_number only when consumed
  command / exit code / log reference
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
  observed controlled invocations
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

Storage permissions, schema/version handling, Git exclusion và declared retention
policy MUST được xác định trước evidence collection. Query/export dùng để tạo
experiment evidence MUST reproducible từ retained observations trong declared
measurement window.

Phase 1.0 retains observations trong toàn bộ declared measurement window và cho tới
khi associated experiment report được accept và reproducibility check PASS. Mọi
deletion sau đó cần recorded disposition gắn với measurement window; Phase 1.0 không
automatic time-based deletion.

Remote/off-device backup subsystem được defer cho tới khi risk evidence hoặc
measurement-window durability chứng minh nhu cầu.

Cost experiment results MUST be reproducibly derivable từ retained raw telemetry của declared measurement window.

Có thể publish derived/versioned report như:

```text
docs/phase1/phase1-ai-cost-baseline.md
```

nhưng report không được thay raw observed evidence hoặc canonical governance.

Không lưu full prompt/response mặc định. Failure logs phải respect data classification/redaction để telemetry DB không trở thành secret dump.

---

## 9. Canonical runtime policy

`constitution/policies.yaml` is the single executable canonical authority:

```yaml
autonomous_execution:
  max_invocation_seconds: <positive integer approved before live invocation>
  max_attempts: 2
```

DEV-007 introduces `max_invocation_seconds` and its fail-closed reader. DEV-008
introduces `max_attempts=2` and its reader. No duplicate numeric authority may exist
in code, prompts, `AGENTS.md`, provider config, adapter metadata, or
`.codex/config.toml`. Missing or invalid policy fails closed. This candidate does
not edit governance.

---

## 10. Artifact and delivery plan

| Artifact | Purpose |
|---|---|
| `PROB-002` | Missing bounded, attributable, portable runtime control |
| `FR-006` | Attributable controlled-invocation telemetry |
| `FR-007` | Restart-safe implementation-attempt budget and circuit |
| `NFR-002` | Failure, concurrency, restart, watchdog, and evidence safety |
| `CMP-003` | Bounded AI Execution Runtime |
| `ADR-006` | Boundary, port, persistence, attempt/circuit, telemetry, portability |
| `DEV-007` / `TEST-007` | Port, adapter, telemetry, watchdog, live proof |
| `DEV-008` / `TEST-008` | Attempt controller, lifecycles, circuit, anti-bypass |

```text
accepted design
 -> DEV-007 + TEST-007 bounded live proof (no autonomous retry)
 -> DEV-008 + TEST-008 attempt/circuit proof
 -> enable bounded autonomous retry
 -> chat-heavy control window
 -> Phase-1.1 experiments
```

This design pass creates no DEV-007/008 or TEST-007/008 artifacts.

---

## 11. Completed discovery evidence

- The repository has no autonomous AI runtime.
- The bootstrap adapter is the Codex Python SDK.
- `ControlledAIInvocation` through `AIRuntimePort` is the accounting unit.
- Exact completed no-tool bootstrap invocation usage is proven.
- Tool-bearing current-invocation completeness remains a DEV-007 acceptance proof.
- Failed/interrupted usage may remain unknown.
- `constitution/policies.yaml` is the executable authority.

ADR-006 is not waiting for further discovery.

---

## 12. Required acceptance tests for DEV-007 / DEV-008

### 12.1 DEV-007

Tests cover mandatory pre-start identity; optional reservation identity for
review/orchestration work; pre-port rejection; a real tool-bearing Codex invocation;
optional runtime correlation without invented IDs; watchdog interruption; requested
versus observed model evidence; provider-neutral exact-core usage with optional
breakdowns; separate terminal status/reason and usage status; unknown-usage
continuation exception; aggregate completeness; and the live invocation's explicit
`acceptance_validation` classification.

The DEV-007 live test is explicitly human-authorized, uses a provider-neutral
non-mutating capability profile, executes a real command/tool item, and proves the
governed repository/workspace state was not mutated. A read-only sandbox is one
permitted adapter mechanism, not a canonical requirement.

Its watchdog-timeout case proves terminal/usage evidence and human attention are
recorded, autonomous follow-on stops, and no fake consumed attempt or budget capacity
is created.

### 12.2 DEV-008

| Test | Expected result |
|---|---|
| Reservation/release/reuse | unique reservation IDs; released evidence retained; slot reusable |
| Consume | candidate binds to unique scope plus attempt number |
| Reservation evidence mapping | affirmative accepted execution -> consumed; affirmative non-start -> released; insufficient -> unresolved |
| Unresolved reconciliation | later affirmative evidence resolves to released/consumed; otherwise remains unresolved |
| Permanently unresolved | old reservation remains immutable/unresolved; old scope stops; only linked governed successor may continue |
| One open attempt | reservation/unresolved/unclosed attempt blocks another |
| Restart/concurrency | one-open and candidate exclusion survive |
| Attempt 1 PASS | scope accepted; no attempt 2 |
| Attempt 1 FAIL | attempt 2 only if budget remains |
| Usage-limit continuation | human-authorized new invocation preserves attempt lineage |
| Reconciliation to suspend | only affirmative interrupted/usage_limit evidence |
| Recovered checkpoint | reconciliation closes passed/failed only from deterministic evidence |
| Other reconciliation | human disposition; stopped scope; successor scope required |
| Non-resumable outcomes | timeout/failure/network/cancel/unknown never auto-resume |
| Continuation anti-bypass | continuation does not change attempt accounting |
| Two attempts FAIL | second failure and circuit persist atomically |
| Attempt 3 | cannot be consumed or reach `AIRuntimePort` |
| Invocation count | never used as attempt-count proxy |
| Successor scope | provenance retained; closed scope immutable |
| Same-scope reset | unavailable in Phase 1.0 |
| Regression | deterministic governance and validation still pass |

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
controlled invocations / accepted DEV
first-attempt acceptance rate
overall acceptance rate
human-attention rate
usage-limit interruptions / DEV
continuation invocations / accepted DEV
input tokens in continuation invocations / accepted DEV
human continuation actions / DEV
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

This exact gate is decision-eligible only when every contributing accepted DEV has
complete usage. Otherwise report incomplete coverage and known subtotals without
claiming an exact reduction.

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

## 15. Implementation and enablement blockers

### 15.1 DEV-007 conditions

Canonical `max_invocation_seconds` field/schema/value; `AIRuntimePort`;
`CodexRuntimeAdapter`; local telemetry persistence; finite watchdog; tool-bearing
usage proof; exact/unknown and aggregate completeness.

### 15.2 DEV-008 conditions

Canonical `max_attempts=2`; reservation/consumption controller; one-open-attempt
enforcement; consumed-attempt continuation lifecycle; circuit transition;
restart/concurrency correctness; successor-scope provenance and anti-bypass.

### 15.3 Non-blocking debt

Remote telemetry, dashboards, monetary normalization, Graphify, Context Pack, full
ARI, multi-agent concurrency, provider routing, automatic model routing,
checkpointing, automatic resume, context compaction, and continuation manifests.

---

## 16. Definition of Done for ADR-006

ADR-006 must answer deterministically and testably:

1. Controlled-invocation definition and hard boundary.
2. Minimum `AIRuntimePort` contract.
3. Mandatory pre-start identities.
4. Reservation, candidate, and consumed attempt identity evolution.
5. One-open-attempt enforcement across restart/concurrency.
6. Deterministic closure and atomic circuit transition.
7. Prevention of candidate attempt 3 and its port invocation.
8. Exact/unknown usage and aggregate completeness.
9. Canonical finite-watchdog policy and distinct attempt/non-attempt timeout effects.
10. Requested versus observed model identity.
11. Runtime SDK isolation.
12. Human-authorized continuation without attempt bypass.
13. Successor-scope provenance preserving closed-scope history.
14. Canonical-base `source_revision` semantics without claiming workspace snapshot.
15. Machine-readable context strategy for comparable context experiments.

Any ambiguous or untestable answer blocks design lock.

---

## 17. Phase 1.0 Definition of Done

```text
[ ] every ControlledAIInvocation passes through gateway and AIRuntimePort
[ ] every invocation has DEV, trace, scope, run, invocation, and source identity
[ ] every invocation has a valid invocation_purpose
[ ] DEV-007 live proof is human-authorized acceptance_validation
[ ] every invocation without attempt identity is denied implementation mutation capability
[ ] DEV-007 live proof executes a real tool under non-mutating capability and proves no governed-state mutation
[ ] implementation reservation has reservation_id + candidate_attempt_number
[ ] attempt_number exists only after consumption
[ ] review/orchestration may omit reservation and attempt identity
[ ] runtime IDs are optional and never invented
[ ] model_selection_strategy and routing_policy_version support comparable experiments
[ ] context_strategy uses the canonical measurement vocabulary
[ ] canonical watchdog and max-attempt policies fail closed
[ ] non-attempt timeout creates no fake consumed attempt or budget capacity
[ ] terminal_status and usage_status remain separate
[ ] aggregate usage completeness and accepted-DEV coverage are explicit
[ ] RELEASED preserves evidence; UNRESOLVED never auto-releases
[ ] permanently UNRESOLVED scope can continue only through a linked governed successor
[ ] no scope has more than one open attempt across restart/concurrency
[ ] usage_limit continuation preserves lineage and requires human authorization
[ ] continuation cannot replenish or bypass MAX_ATTEMPTS
[ ] non-resumable outcomes never auto-resume
[ ] attempt-3 work cannot reach AIRuntimePort
[ ] new run cannot reset scope budget
[ ] successor scope preserves immutable closed-scope history
[ ] continuation usage is included in cost measurements
[ ] retained telemetry reproduces DEV and experiment metrics
[ ] deterministic governance and regression gates remain intact
```

When these conditions pass, the Factory has demonstrated:


> **bounded, measurable, cost-aware AI execution**

và mới đủ điều kiện bước sang Phase 1.1 Cost Optimization experiments.
