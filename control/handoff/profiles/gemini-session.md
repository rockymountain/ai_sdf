---
id: CTRL-HANDOFF-PROFILE-GEMINI-SESSION-001
kind: handoff-consumer-profile
title: Gemini Conversation Session Handoff Profile
status: active
version: 1
owner: factory-maintainer
last_updated: 2026-09-21
consumer_kind: gemini-conversation
---

# Gemini Conversation Session Handoff Profile

## 1. Purpose

This profile specializes the provider-neutral Handoff Operating Standard for
continuation from one project/session into a fresh Gemini Apps conversation.

It does not redefine core handoff authority, verification budgets, Git
semantics, project baselines, implementation budgets, or locked design state.

Provider-specific transport limits are isolated here so that the core SDF
handoff protocol remains provider-neutral.

## 2. Applicability

Use this profile when:

- the Receiver is a fresh Gemini Apps conversation;
- direct file upload is the selected transport mechanism;
- previous chat history MUST NOT be required for reconstruction.

The normal handoff type for routine same-workspace continuation is:

```text
Type A — Session / Agent Continuation
```

A stricter core handoff type MAY use this profile only when all stricter core
requirements are also satisfied.

## 3. Consumer constraints

```yaml
profile_id: CTRL-HANDOFF-PROFILE-GEMINI-SESSION-001
consumer_kind: gemini-conversation

transport:
  mode: direct-file-source-pack

context_constraints:
  max_source_files: 10
  subject_to_availability: true
  provider_constraint_last_verified: 2026-09-21
  provider_constraint_source: Google Gemini Apps Help

receiver_verification:
  max_passes: 2
  max_clarification_cycles: 1
```

At the time this profile was materialized, Google Gemini Apps documentation
states that up to 10 supported files can be uploaded in the same prompt,
subject to availability.

This limit is provider-specific and may change.

If the observed Gemini product/account limit is lower or otherwise different
at handoff time, the Sender MUST use the actually available limit and record it
in the Source Manifest.

A code-folder or GitHub-repository ingestion path is a different transport mode
and MUST NOT be silently treated as equivalent to this direct-file profile.
If that mode is intentionally used later, its transfer semantics SHOULD be
defined explicitly rather than weakening this profile's bounded-source rules.

## 4. Required outputs

A Gemini session handoff package MUST contain:

```yaml
required_outputs:
  - handoff_packet
  - source_manifest
  - receiver_bootstrap_instruction
  - verification_contract
  - authority_and_stop_conditions
```

The package MUST NOT be declared `READY` if any required output is missing.

## 5. Source-selection policy

This profile inherits the core `P0`–`P6` priority model.

Every candidate represented in the Source Manifest MUST have:

```yaml
priority: P0 | P1 | P2 | P3 | P4 | P5 | P6
mandatory: true | false
disposition: selected | pruned
```

### 5.1 Default source intent

For a project-continuation session, source derivation SHOULD normally consider:

```text
P0
  handoff packet

P1
  control/handoff/README.md
  this consumer profile
  current project-control state
  active roadmap
  active baseline

P2
  executable governance
  trace truth
  active phase/work plan

P3
  next-work problem / requirement / NFR / design / ADR / contract chain

P4
  directly relevant predecessor DEV / TEST / accepted evidence

P5
  implementation reality required to understand or continue the next work

P6
  historical/reference/supporting material
```

This is a derivation order, not a fixed filename template.

Actual selection MUST follow current project authority and current work state.

## 6. Mandatory-source rule

The Sender MUST determine mandatory sources before applying the Gemini
direct-file limit.

If mandatory sources exceed the observed direct-file limit:

```text
HANDOFF NOT READY
reason: mandatory_source_set_exceeds_consumer_limit
human_attention_required: true
```

The Sender MUST NOT silently prune mandatory context to fit the provider limit.

A human MAY choose a separately governed transfer strategy, but that decision
must be explicit.

## 7. Pruning and context-loss evidence

When candidate count exceeds the available direct-file limit, non-mandatory
sources MAY be pruned according to the core priority rules.

Every relevant pruned candidate retained in the derivation set MUST have a
visible prune record.

At minimum:

```yaml
priority: P5 | P6 | <other-priority-if-applicable>
path: <repo-relative-path-or-durable-source-id>
mandatory: false
disposition: pruned
reason: <why-this-source-lost-selection>
context_loss: <what-the-receiver-will-not-have-directly>
```

Pruning of `P5` or `P6` MUST be explicit.

A Receiver MUST be able to tell which implementation or historical context was
intentionally omitted because of Gemini's bounded direct-file transport.

## 8. Source Manifest minimum contract

A derived Gemini Source Manifest MUST include:

```yaml
consumer_profile: CTRL-HANDOFF-PROFILE-GEMINI-SESSION-001
source_limit: 10
source_limit_subject_to_availability: true

selected_sources:
  - priority: P0
    path: .sdf/runtime/handoff/<handoff-file>.md
    mandatory: true
    role: handoff-transfer-identity

pruned_sources: []

derivation:
  candidate_count: <integer>
  selected_count: <integer>
  pruned_count: <integer>
  human_overrides: []
```

If the observed available source limit differs from 10, `source_limit` MUST
record the observed value used for that actual transfer.

## 9. Receiver Bootstrap Instruction contract

The Sender MUST generate a bootstrap prompt for the new Gemini conversation.

The prompt MUST instruct the Receiver to:

1. identify this as a Gemini conversation handoff;
2. treat the uploaded source pack as bounded reconstruction evidence, not
   replacement authority;
3. avoid relying on prior chat history or provider memory;
4. perform Receiver Verification before project/domain mutation;
5. compare actual Git/control/workspace evidence with Sender claims;
6. preserve declared unrelated local state;
7. obey the two-pass / one-clarification verification budget;
8. stop on unresolved mismatch;
9. distinguish next intended work from current execution authority;
10. report the first post-acceptance decision required from the Project Owner.

The bootstrap instruction MUST NOT imply that provider access, file possession,
or handoff context grants permission to modify protected or governed systems.

## 10. Receiver Verification contract

For a Git-backed project, the bootstrap instruction SHOULD request the
functional equivalent of:

```text
git branch --show-current
git rev-parse HEAD
git status --porcelain=v1
```

Additional checks MAY be required by the handoff packet.

The Receiver MUST produce one gate outcome:

```text
HANDOFF ACCEPTED
```

or:

```text
HANDOFF REJECTED — PASS 1
```

After one permitted clarification/correction cycle, a second failure MUST
produce:

```text
HANDOFF_CIRCUIT_OPEN
human_attention_required = true
autonomous_follow_on_allowed = false
```

No third automatic verification pass is permitted.

## 11. Package Completeness Gate

Before a Gemini session handoff can be `READY`, verify:

```text
[ ] core handoff type resolved
[ ] Gemini consumer profile resolved
[ ] observed direct-file limit established
[ ] handoff packet generated
[ ] Source Manifest generated
[ ] all represented candidates have P0–P6 labels
[ ] selected source count <= observed Gemini direct-file limit
[ ] every relevant pruned source remains visible
[ ] P5/P6 pruning includes context_loss
[ ] no mandatory source was pruned
[ ] bootstrap prompt generated
[ ] verification contract generated
[ ] preserve / stop / authority boundaries present
[ ] known unknowns explicit
[ ] no secret or convenience credential embedded
```

One failed mandatory check means:

```text
HANDOFF NOT READY
```

## 12. Semi-auto readiness proof

This profile is not proven semi-auto derivation ready merely because this file
exists.

A real Gemini-session handoff MUST demonstrate that all required outputs are
derived without requiring the Project Owner to discover a missing mandatory
package component.

Human source-selection overrides are permitted only when recorded with:

```yaml
action: add | remove | substitute
source: <path-or-id>
reason: <explicit-reason>
```

Original derivation and prune evidence MUST remain visible.
