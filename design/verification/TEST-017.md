---
id: TEST-017
kind: verification
title: Controlled dual-runtime and purpose-scoped measurement verification
status: verified
version: 1
verification_type: integration
---

# Verification contract

TEST-017 uses injected process fixtures and temporary SQLite evidence. It performs no
live provider invocation and does not mutate the governed operational database.

# Required assertions

## Claude runtime conformance

- Assistant/terminal machine events map affirmative accepted start.
- Local process creation failure maps definite non-start.
- Exit without affirmative accepted evidence maps uncertain start.
- Terminal results and interruption map to provider-neutral status/reason values.
- Complete authoritative Claude base-input, cache-creation-input, cache-read-input,
  and output components normalize to canonical input/output and a derived total.
- Terminal provider usage key names and actually emitted numeric values are retained
  in native metadata; missing keys, prompt content, and response content are not
  synthesized or retained for accounting.
- Missing, malformed, negative, or noninteger required provider components remain
  unknown rather than estimated.
- Generic `cached_input_tokens` maps only Claude cache-read input, not cache creation.
- Runtime session/model/tool evidence is retained only when observed, and native
  identifiers are never invented.

## Capability and operator selection

- Governed implementation receives mutation-capable execution only with valid
  attempt identity.
- Review remains read-only and cannot acquire implementation capability by selecting
  Claude or Codex.
- The Claude command has no top-level working-directory or permission-prompt flag;
  process `cwd` is the governed repository.
- Claude read-only execution uses plan mode, only `Read`, `Glob`, and `Grep` from the
  built-in tool set, and strict MCP configuration with no supplied MCP server.
- Claude implementation uses supported `acceptEdits` semantics without unrestricted
  permission bypass.
- `codex` and `claude` selection are explicit and unknown identifiers fail before
  runtime execution.
- Explicit operator reasoning effort `none` becomes canonical null and emits no
  Claude `--effort`; a non-empty requested value is retained and emitted.
- Codex behavior and the unchanged `AIRuntimePort` remain regression-tested.
- Codex exact usage remains internally consistent with canonical total equal to input
  plus output; inconsistent native aggregates fail closed without historical rewrite.

## Measurement and accounting

- One synthetic DEV containing Claude implementation plus Codex review is
  treatment-consistent and aggregates both usages.
- Wrong model, wrong adapter, undeclared orchestration, and missing adapter identity
  remain visible and block exact treatment-dependent KPI eligibility.
- Breakdowns by invocation purpose and runtime adapter reconcile with the DEV total.
- Continuation/retry, failed/rejected, and review costs remain visible.
- Unknown usage preserves known subtotals and is never converted to zero.
- Generic measurement/model/policy modules contain no Claude/Anthropic cache-field
  vocabulary; provider normalization occurs before generic aggregation.

## Regression

Existing authorization, reservation, attempt, circuit, continuation, watchdog,
outcome-finalization, schema-v2/v3, cost-baseline reproducibility, provider
neutrality, environment, and generated-governance checks remain passing.

# Acceptance boundary

TEST-017 is verified by its deterministic contract. It did not perform live provider
calls or mutate the governed operational database. The separately authorized
PRE-WINDOW adoption proof supplied distinct runtime evidence; deterministic
TEST-017, that runtime evidence, and Project Owner acceptance together support
DEV-017 closure.

Verification does not start M3, declare a fixed M3 set, prove the baseline, make
exact token KPIs decision-eligible, or authorize M4.
