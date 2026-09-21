---
id: CTRL-HANDOFF-PROFILE-CHATGPT-SESSION-001
kind: handoff-consumer-profile
title: ChatGPT Conversation Session Handoff Profile
status: active
version: 1
owner: factory-maintainer
last_updated: 2026-09-21
consumer_kind: chatgpt-conversation
---

# ChatGPT Conversation Session Handoff Profile

## 1. Purpose

This profile specializes the provider-neutral Handoff Operating Standard for
continuation from one ChatGPT conversation to another.

It does not redefine core handoff authority, verification budgets, Git
semantics, project baselines, implementation budgets, or locked design state.

This profile exists to make ChatGPT session handoff **semi-auto derivation
ready** rather than a manual context-packaging exercise.

## 2. Applicability

Use this profile when:

- the Receiver is a fresh ChatGPT conversation;
- the handoff depends on a bounded set of source files attached to that
  conversation;
- previous chat history MUST NOT be required for reconstruction.

The normal handoff type for routine same-workspace continuation is:

```text
Type A — Session / Agent Continuation
```

A different core handoff type MAY still use this profile when its stricter
requirements are also satisfied.

## 3. Consumer constraints

```yaml
profile_id: CTRL-HANDOFF-PROFILE-CHATGPT-SESSION-001
consumer_kind: chatgpt-conversation

transport:
  mode: direct-file-source-pack

context_constraints:
  max_source_files: 20
  limit_basis: project-owner-confirmed
  limit_as_of: 2026-09-21

receiver_verification:
  max_passes: 2
  max_clarification_cycles: 1
```

The `20`-file limit is a ChatGPT consumer-profile constraint.

It MUST NOT be interpreted as a universal SDF handoff invariant.

If the observed product limit differs at handoff time, the Sender MUST use the
lower actually available limit for that transfer and record the observed
constraint in the Source Manifest.

## 4. Required outputs

A ChatGPT session handoff package MUST contain:

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

Actual selection MUST follow the current project's authority and work state.

## 6. Mandatory-source rule

The Sender MUST decide whether a candidate is mandatory for correct Receiver
reconstruction before applying the 20-file limit.

Mandatory context MUST NOT be silently dropped.

If the mandatory source set alone exceeds the available source-file limit:

```text
HANDOFF NOT READY
reason: mandatory_source_set_exceeds_consumer_limit
human_attention_required: true
```

Possible human dispositions include changing the transfer strategy, reducing
handoff scope, or approving another governed transport mechanism.

The Sender MUST NOT simply omit mandatory files to make the count equal 20.

## 7. Pruning and context-loss evidence

When candidate count exceeds the available limit, non-mandatory candidates MAY
be pruned according to the core priority rules.

The Source Manifest MUST retain every relevant pruned candidate that was
considered part of the derivation set.

Each prune record MUST contain:

```yaml
priority: P5 | P6 | <other-priority-if-applicable>
path: <repo-relative-path-or-durable-source-id>
mandatory: false
disposition: pruned
reason: <why-this-source-lost-selection>
context_loss: <what-the-receiver-will-not-have-directly>
```

Pruning of `P5` or `P6` MUST be visible.

A Receiver MUST be able to distinguish:

```text
irrelevant and never selected
```

from:

```text
relevant but pruned to satisfy the ChatGPT source limit
```

## 8. Source Manifest minimum contract

A derived ChatGPT Source Manifest MUST include:

```yaml
consumer_profile: CTRL-HANDOFF-PROFILE-CHATGPT-SESSION-001
source_limit: 20

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

If the observed available source limit differs from 20, `source_limit` MUST
record the observed value for the actual transfer.

## 9. Receiver Bootstrap Instruction contract

The Sender MUST generate a bootstrap prompt for the new ChatGPT conversation.

The prompt MUST instruct the Receiver to:

1. identify this as a ChatGPT conversation handoff;
2. treat the attached source pack as bounded reconstruction evidence, not as
   replacement authority;
3. avoid relying on previous chat history or hidden memory;
4. execute Receiver Verification before project/domain mutation;
5. compare actual Git/control/workspace state with Sender claims;
6. preserve declared unrelated local state;
7. obey the two-pass / one-clarification verification budget;
8. stop on unresolved mismatch;
9. distinguish next intended work from current execution authority;
10. report the first post-acceptance decision required from the Project Owner.

The bootstrap prompt MUST NOT authorize implementation merely because an
implementation task is named as next intended work.

## 10. Receiver Verification contract

For a Git-backed project, the bootstrap instruction SHOULD request the
functional equivalent of:

```text
git branch --show-current
git rev-parse HEAD
git status --porcelain=v1
```

Additional project-control inspection MAY be required by the handoff packet.

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

Before a ChatGPT session handoff can be `READY`, verify:

```text
[ ] core handoff type resolved
[ ] ChatGPT consumer profile resolved
[ ] handoff packet generated
[ ] Source Manifest generated
[ ] all represented candidates have P0–P6 labels
[ ] selected source count <= observed ChatGPT source-file limit
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

This profile becomes proven semi-auto derivation ready only after a real
ChatGPT-session handoff demonstrates that the Project Owner does not have to
discover a missing mandatory package component.

The delayed M2 / DEV-008 session handoff is the initial Patient Zero for this
profile.

A human MAY review or override a derived source selection.

Any add/remove/substitute override MUST retain:

```yaml
action: add | remove | substitute
source: <path-or-id>
reason: <explicit-reason>
```

and MUST NOT erase original prune/derivation evidence.
