---
id: CP-DECISION-INDEX
type: closure-artifact
phase: 0
status: final
author: SDF-Orchestrator
title: "Phase 0 Decision Index"
version: "1.0"
date: "19/09/2026"
lang: vi-VN
---

# Phase 0 Decision Index

Tài liệu này là **index/navigation only**. Nó MUST NOT copy reasoning chi tiết của ADR; reasoning authority nằm trong `design/decisions/ADR-*`.

## Authority boundary

Closure Pack artifacts summarize, index, measure hoặc attest evidence. Chúng **MUST NOT** trở thành competing canonical source cho decisions, executable governance hoặc trace truth.

- Architecture/operating model authority: [CP-REFERENCE-ARCHITECTURE](reference/ai-native-sdf-reference-architecture.md)
- Accepted decisions: `design/decisions/ADR-*`
- Executable governance: `constitution/*`
- Trace truth: `knowledge/traceability.yaml`

## Phase 0 decision map

| Problem / decision need | Accepted decision | Status | Realization | Verification |
|---|---|---|---|---|
| Cần một governed vertical slice thực thay vì chỉ schema/docs | [ADR-001](../design/decisions/ADR-001.md) | accepted | [DEV-001](../design/tasks/DEV-001.md) | [TEST-001](../design/verification/TEST-001.md) |
| `implementation.paths` có thể tồn tại nhưng không resolve tới evidence thực | [ADR-002](../design/decisions/ADR-002.md) | accepted | [DEV-002](../design/tasks/DEV-002.md) | [TEST-002](../design/verification/TEST-002.md) |
| Changed file có thể không truy được về task/intent | [ADR-003](../design/decisions/ADR-003.md) | accepted | [DEV-003](../design/tasks/DEV-003.md) | [TEST-003](../design/verification/TEST-003.md) |
| QG-004/policy được khai báo nhưng validator vẫn sở hữu semantics | [ADR-004](../design/decisions/ADR-004.md) | accepted | [DEV-004](../design/tasks/DEV-004.md) | [TEST-004](../design/verification/TEST-004.md) |
| Local/CI validation environment drift và dependency closure không thống nhất | [ADR-005](../design/decisions/ADR-005.md) | accepted | [DEV-005](../design/tasks/DEV-005.md) | [TEST-005](../design/verification/TEST-005.md) |

## Foundational decision → Phase 0 realization

Các `SDF-DEC-*` nằm trong [CP-REFERENCE-ARCHITECTURE](reference/ai-native-sdf-reference-architecture.md) là architectural baseline, không phải ADR thay thế.

| Foundational decision | Phase 0 realization |
|---|---|
| SDF-DEC-001 — Git + structured artifacts là source of truth | [ADR-001], [DEV-001] |
| SDF-DEC-002 — Knowledge Graph là derived/query layer | RETAINED / NOT DIRECTLY REALIZED IN PHASE 0 — canonical Git/structured artifacts vẫn giữ authority; không có Graphify/Knowledge Graph nào được promote thành canonical truth. Next realization thuộc Phase 1 Reality/Context Graph experiment. |
| SDF-DEC-003 — Traceability many-to-many, bidirectional, risk-based | [ADR-001], [ADR-002], [ADR-003] |
| SDF-DEC-004 — Lean + PDCA + continuous flow | [DEV-001]–[DEV-005] small-batch hardening |
| SDF-DEC-005 — VS Code + Codex bootstrap stack | Phase 0 Codex-assisted execution; canonical truth không phụ thuộc Codex |
| SDF-DEC-006 — Core logic không nằm trong extension | Validator/CI/governance ở repository |
| SDF-DEC-007 — MCP cho tools/context; ARI cho runtime | TARGET; chưa được Phase 0 chứng minh end-to-end |
| SDF-DEC-008 — Codex-first, not Codex-dependent | [ADR-004] giữ governance/evidence provider-independent; Agent Runtime portability vẫn là TARGET |
| SDF-DEC-009 — Human gate cho high-risk/irreversible | [ADR-003], [ADR-004] giữ human classification/material governance gate |
| SDF-DEC-010 — Agent/eval/policy versioned | [ADR-004], [ADR-005] chứng minh versioned policy/schema/environment contract |

## Navigation rule

Specific IDs SHOULD xuất hiện ở dạng `[ADR-005]`, `[DEV-005]`, `[FR-005]`, `[TEST-005]` hoặc markdown link trực tiếp. Free-text references kiểu “ADR trước” SHOULD NOT được dùng.
