---
id: TEST-013
kind: verification
title: Provider-neutral measurement declaration verification
status: verified
version: 1
verification_type: integration
---

# Verification contract

TEST-013 deterministically verifies the ADR-008 / DEV-013 separation between the
generic measurement engine and a concrete window treatment. No live provider call or
operational database mutation is required.

# Required assertions

## Provider-neutral declaration

- A window explicitly declaring `synthetic-provider-model` is accepted without any
  second provider dependency or production-code edit.
- Explicit `requested_reasoning_effort: null` is accepted for an unsupported or
  unrequested capability.
- The current GPT-5.6 Sol / medium / fixed / null / chat-heavy M3 treatment remains
  valid when every treatment field is explicitly supplied.

## Generic structure and vocabulary

- Omission of any required treatment key fails closed.
- Requested model is a non-empty identifier.
- Requested reasoning effort is `null` or a non-empty capability value.
- Model-selection and context strategies use their existing SDF vocabularies.
- Routing-policy version is `null` or non-empty and is required for risk-routed or
  automatic routing declarations.
- Automatic-routing and context-optimization values are explicit booleans.

## Window-relative consistency

- Invocation evidence matching a synthetic declared treatment is profile-consistent
  and may contribute to an otherwise exact KPI.
- Evidence using a different synthetic model remains retained but is profile-
  inconsistent and makes the exact token KPI unavailable.
- Production validation does not require the literal current GPT model or medium
  reasoning value.

## Regression

- Half-open UTC boundary, exact/unknown usage, known subtotals, aggregate
  completeness, authoritative attempt linkage, accepted/rejected outcomes,
  failed/retry/review/orchestration visibility, T0/T1/T2 reporting, canonical byte
  reproducibility, read-only reporting, and schema-v2/v3 support remain passing.
- `AIRuntimePort`, runtime execution, telemetry schema, and the operational database
  are unchanged.

# Acceptance boundary

Passing TEST-013 proves only the provider-neutral measurement-contract correction.
It does not start or approve the M3 measurement window, prove the M3 baseline,
authorize M4, add a provider adapter, or authorize automatic routing.
