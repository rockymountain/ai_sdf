---
id: CTRL-HANDOFF-README-001
kind: handoff-definition
title: AI-Native SDF Project Handoff Operating Standard
status: active
version: 2
owner: factory-maintainer
last_updated: 2026-09-21
---

# AI-Native SDF Project Handoff Operating Standard

## 1. Purpose

`control/handoff/` định nghĩa protocol chuẩn để chuyển giao project context
giữa:

- human sessions;
- AI sessions;
- AI agents;
- human và AI;
- machines/environments;
- milestones;
- project phases;
- recovery situations.

Mục tiêu của Handoff Protocol là cho phép một Receiver tiếp tục công việc mà
không phụ thuộc vào:

- previous chat history;
- memory riêng của một AI model;
- undocumented local state;
- một workstation cụ thể;
- một editor cụ thể;
- một AI provider cụ thể;
- assumption không được ghi nhận.

Một handoff hợp lệ phải cho phép Receiver xác định:

> Project đang ở trạng thái nào, evidence nào chứng minh trạng thái đó,
> điều gì được phép làm tiếp theo, điều gì chưa được phép làm, và các risk /
> invariant nào đang giới hạn công việc.

Handoff transfers context.

Handoff does not create authority.

# 2. Authority Boundary

Handoff artifacts là control/evidence artifacts.

Chúng MAY:

- summarize current project-control state;
- reference canonical artifacts;
- reference runtime or Git evidence;
- record transfer context;
- record receiver verification evidence;
- record acceptance/rejection of a transfer.

Handoff artifacts MUST NOT redefine or override authority owned by:

| Concern | Authority |
|---|---|
| Problem / requirements | `design/problems/*`, `design/requirements/*` |
| Architecture | `design/architecture/*` |
| Architectural decisions | `design/decisions/*` |
| Executable governance | `constitution/*` |
| Trace truth | `knowledge/traceability.yaml` |
| Implementation reality | source, tests, config, IaC, migrations |
| Runtime reality | governed runtime evidence |
| Delivery roadmap | `control/roadmap.md` |
| Current project control state | `control/project-control.yaml` |
| Accepted/rebaseline history | `control/history/*` |

If a handoff claim conflicts with canonical or runtime evidence:

```text
canonical / runtime evidence wins
```

The handoff MUST then be rejected, corrected, superseded, or escalated.

The Receiver MUST NOT silently choose the handoff prose over stronger evidence.

# 3. Normative Language

The keywords `MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, and `MAY` are
normative.

They are used as follows:

- `MUST` / `MUST NOT`:
  required to preserve correctness, governance, reproducibility, safety, or
  auditability;

- `SHOULD` / `SHOULD NOT`:
  expected default behavior; deviation requires an explicit reason;

- `MAY`:
  permitted but optional behavior.

A handoff that violates a `MUST` requirement is:

```text
HANDOFF NOT READY
```

or, if already transferred:

```text
HANDOFF REJECTED
```

# 4. Definitions

## 4.1 Sender

The `Sender` is the human, agent, session, process, or role preparing the
handoff.

## 4.2 Receiver

The `Receiver` is the human, agent, session, process, or role expected to
continue work after the handoff.

## 4.3 Handoff Packet

A `Handoff Packet` is the minimal structured context required to transfer work.

A Handoff Packet MAY exist only in a governed session for lightweight Type A
handoffs, or MAY be materialized as a durable snapshot when required.

## 4.4 Durable Handoff

A `Durable Handoff` is a handoff intended to survive loss of:

- the current session;
- the current process;
- the current workstation;
- local transient state;
- chat history.

A Durable Handoff MUST be reconstructable from durable evidence.

## 4.5 Project/Domain State Mutation

A `Project/Domain State Mutation` is any change that modifies the project being
delivered or its governed design/implementation state.

Examples include:

- source-code modification;
- requirement/design modification;
- ADR modification;
- policy modification;
- migration;
- dependency change;
- generated canonical evidence;
- implementation execution;
- destructive Git operation.

Writing receiver-verification evidence required by this protocol is NOT treated
as project/domain work mutation for the purpose of the pre-acceptance gate.

## 4.6 Verification Pass

A `Verification Pass` is one complete Receiver evaluation of the current
handoff claims against actual observed evidence.

Verification Pass numbering starts at `1`.

A single handoff transfer has a maximum of two verification passes.

# 5. Handoff Invariants

The following invariants apply to all handoff implementations.

## HO-I01 — Chat Independence

A handoff MUST be reconstructable without access to previous chat history.

Chat MAY assist the transfer.

Chat MUST NOT be the sole location of material project state required to
resume work.

## HO-I02 — Authority Preservation

A handoff MUST reference existing authority.

It MUST NOT become a competing source of:

- architecture truth;
- requirement truth;
- policy truth;
- trace truth;
- implementation truth.

## HO-I03 — Revision Identity

A handoff MUST identify the relevant repository state using a full Git commit
SHA when Git state is material to the transfer.

Short SHAs MAY be shown for readability.

A short SHA MUST NOT be the only durable revision identity.

## HO-I04 — Workspace State

The Sender MUST explicitly classify the workspace state relevant to the
handoff.

The handoff MUST NOT imply a clean workspace when uncommitted changes exist.

Dirty state MUST NOT be hidden.

Durable Handoffs have additional clean-state requirements defined later in this
standard.

## HO-I05 — Control Position

A handoff MUST make explicit, directly or by authoritative reference:

- active project baseline;
- current phase;
- current milestone;
- latest completed milestone when relevant;
- current DEV/work item when one exists;
- next intended work item when one exists.

## HO-I06 — Authorized Next Action

A handoff MUST identify the next permitted action or class of actions.

A handoff MUST identify material stop conditions.

The Receiver MUST NOT infer execution authority merely from the existence of a
handoff.

## HO-I07 — Unknown Preservation

Unknown or missing evidence MUST remain unknown.

A Sender or Receiver MUST NOT transform:

```text
unknown → 0
unknown → false
missing date → guessed date
missing usage → estimated usage
missing authorization → assumed authorization
```

unless a separate governed decision explicitly produces an estimate and labels
it as such.

## HO-I08 — Cross-Platform Portability

Repository references in handoff artifacts MUST use repository-relative paths.

Paths MUST use `/`.

Handoff semantics MUST NOT depend on:

- Windows drive letters;
- a specific user home directory;
- local absolute paths;
- shell-specific transient aliases;
- one IDE;
- one AI runtime;
- one provider.

## HO-I09 — Minimal Context Transfer

A handoff SHOULD reference canonical content rather than copy it.

The handoff MUST transfer enough context to resume safely.

It SHOULD NOT duplicate large canonical artifacts merely for convenience.

## HO-I10 — Historical Integrity

A durable accepted handoff snapshot is historical evidence.

Later project changes MUST NOT silently rewrite what was observed at the time
of that handoff.

A later transfer MAY supersede an earlier snapshot.

It MUST NOT erase it merely because the project moved forward.

## HO-I11 — Proof of Verification

Receiver verification execution MUST leave a verifiable trace.

If a Durable Handoff is used, the Receiver MUST record the outcome of the
verification gate before performing any project/domain state mutation.

The verification trace MUST be sufficient to establish:

- what the handoff claimed;
- what the Receiver observed;
- which checks were performed;
- whether mismatches existed;
- which verification pass was executed;
- the resulting gate decision.

Writing verification evidence itself is permitted before handoff acceptance.

No other project/domain mutation is permitted before the applicable acceptance
gate passes.

## HO-I12 — Bounded Verification

Handoff verification MUST be bounded.

A Receiver MAY execute at most:

```text
verification_pass_max = 2
```

After a failed first verification pass:

```text
clarification_count_max = 1
```

Exactly one clarification/correction cycle MAY occur.

If the second verification pass fails:

```text
HANDOFF_CIRCUIT_OPEN
human_attention_required = true
```

All autonomous follow-on MUST stop.

No AI actor MAY:

- initiate a third verification pass;
- silently increase the verification budget;
- guess the intended state;
- fabricate missing evidence;
- repair the handoff and continue without human authorization.

This handoff verification budget is independent of implementation-attempt
budgets such as `MAX_ATTEMPTS = 2`.

One budget MUST NOT reset or replenish the other.

## HO-I13 — Durable Clean State

A Durable Handoff MUST originate from a clean, reproducible Git working state.

All state required by the Receiver to continue the transferred work MUST be
represented by:

- reachable Git revisions; or
- another explicitly governed durable evidence mechanism.

Local-only state MUST NOT be required to resume a Durable Handoff.

In particular:

```text
git stash ≠ durable handoff state
```

A local stash MAY be used as a temporary operator technique.

A stash containing state required by the Receiver MUST NOT be treated as
durable transfer evidence.

If required state exists only in a stash or uncommitted workspace:

```text
HANDOFF NOT READY
```

## HO-I14 — Consumer-Complete Derivation

For every supported handoff Consumer Profile, the Sender MUST be able to derive
the complete Receiver package without requiring the human operator to discover
missing mandatory package components.

Derivation MAY require human review, approval, or an explicit override, but the
human MUST NOT be required to invent a missing mandatory output that the
Consumer Profile already declares.

A handoff that depends on the human noticing that a required output is absent
is NOT semi-auto derivation ready.

## HO-I15 — Bounded Source Manifest

When the Receiver has bounded context or attachment capacity, the handoff MUST
include an explicit bounded Source Manifest appropriate to the selected Consumer
Profile.

Every candidate and selected source represented in the manifest MUST carry a
priority label from `P0` through `P6`.

The Source Manifest MUST make context loss visible. If any candidate source is
pruned to satisfy a consumer limit, the manifest MUST retain a prune record with
at least:

- priority;
- repository-relative path or durable source identity;
- selected/pruned disposition;
- prune reason.

In particular, pruning of `P5` or `P6` sources MUST be explicitly visible to
the Receiver and Auditor. It MUST NOT disappear silently from the generated
package.

Priority is not authority. A lower-numbered priority does not by itself make an
artifact canonical, and a higher-numbered priority does not permit omission of
a source that is mandatory for correctness.

If the mandatory source set cannot fit within the consumer's declared context
limit, the Sender MUST NOT silently drop mandatory context. The handoff MUST
fail closed as:

```text
HANDOFF NOT READY
reason: mandatory_source_set_exceeds_consumer_limit
human_attention_required: true
```

## HO-I16 — Receiver Bootstrap Instruction

Every supported Consumer Profile MUST define a Receiver Bootstrap Instruction.

The derived bootstrap instruction MUST establish, at minimum:

- handoff identity and handoff type;
- Consumer Profile identity;
- semantics of the attached/available source set;
- Receiver Verification gate;
- expected source/workspace/control state when known;
- preserve conditions;
- stop conditions;
- authority boundary;
- verification-pass budget;
- first post-acceptance decision or action boundary.

The bootstrap instruction MUST NOT imply authority that is absent from
canonical governance, current human authorization, or another already-valid
authority mechanism.

## HO-I17 — Package Completeness Gate

A handoff MUST NOT be declared `READY` for a supported Consumer Profile until
all mandatory outputs defined by that profile have been derived and checked.

The Package Completeness Gate MUST verify at least:

1. handoff type is resolved;
2. Consumer Profile is resolved;
3. all profile-required outputs exist;
4. Source Manifest entries carry `P0`–`P6` priority labels;
5. selected sources fit the declared consumer limit;
6. every pruned candidate retains a visible prune record;
7. no mandatory source was silently pruned;
8. Receiver Bootstrap Instruction satisfies HO-I16;
9. Receiver Verification contract is present;
10. preserve, stop, and authority boundaries are present;
11. known unknowns remain explicit;
12. secrets or convenience credentials are not embedded in the package.

Human review MAY reject a derived package or approve an explicit substitution.
Any human substitution, addition, or removal that changes the derived source
set MUST be recorded as an override with a reason. Human review MUST NOT erase
the original derivation/prune evidence.

# 6. Handoff Types

Every handoff SHOULD be classified before preparation.

The available types are:

```text
Type A — Session / Agent Continuation
Type B — Material Work Handoff
Type C — Durable / Recovery Handoff
```

The most restrictive applicable type SHOULD be used.

## 6.1 Type A — Session / Agent Continuation

Type A is intended for short-lived continuation where the same repository
workspace remains available.

Examples:

- one ChatGPT thread to another;
- one agent session to another in the same environment;
- operator pauses and resumes shortly afterward;
- executor session restarts while workspace remains intact.

Type A MAY operate with a dirty working tree.

If the working tree is dirty:

- dirty state MUST be explicitly acknowledged;
- unrelated changes MUST be identified when material;
- destructive Git cleanup MUST NOT be inferred as permitted;
- the Receiver MUST verify actual workspace state before mutation.

Type A SHOULD avoid creating a durable snapshot unless:

- context-loss risk is high;
- work is material;
- the continuation will cross a long interruption;
- auditability requires durable evidence.

## 6.2 Type B — Material Work Handoff

Type B transfers material work between roles, humans, or agents.

Examples:

- Architect → Executor;
- Designer → Reviewer;
- Human Owner → AI Executor;
- Agent A → Agent B;
- Reviewer → Integrator.

A Type B handoff SHOULD originate from a clean working tree.

A dirty Type B handoff is permitted only when:

- the transfer remains in the same physical/logical workspace;
- explicit human authorization allows it;
- dirty state is fully disclosed;
- no destructive normalization is required;
- Receiver verification can observe the same state.

A Type B handoff that crosses machines or cannot preserve the same workspace
MUST be treated as Type C.

## 6.3 Type C — Durable / Recovery Handoff

Type C is required when transfer must survive workspace loss or environment
replacement.

Examples:

- machine migration;
- long interruption;
- milestone boundary requiring durable state;
- phase boundary;
- recovery after failure;
- significant ownership transfer;
- cross-machine transfer;
- disaster-recovery scenario;
- explicit durable audit snapshot.

Type C MUST:

- use durable evidence;
- use a clean working tree;
- contain no required local-only stash state;
- identify full Git revisions;
- pass bounded Receiver verification;
- persist Receiver verification outcome;
- stop on unresolved mismatch.

A Type C handoff MUST NOT proceed from a dirty working tree.

# 7. Workspace State Rules

## 7.1 Verification Commands

When Git is the relevant versioning system, Receiver verification MUST include
the functional equivalent of:

```text
git branch --show-current
git rev-parse HEAD
git status --porcelain=v1
```

Additional checks MAY be required by the current task.

The protocol does not require one particular shell syntax.

The observed facts are what matter.

## 7.2 Clean State

For Type C:

```text
git status --porcelain=v1
```

MUST produce no tracked or untracked workspace mutation relevant to the
handoff state.

If required work is uncommitted, the Sender MUST place it into durable Git
history before the handoff can become ready.

Permitted strategies MAY include:

- normal commit;
- explicit WIP commit;
- dedicated handoff branch.

The selected revision MUST be available to the Receiver.

Creating a local commit that the Receiver cannot access is insufficient for a
cross-machine Durable Handoff.

## 7.3 Unrelated Local Changes

Type A MAY preserve unrelated local changes when the same workspace is being
continued.

Such state SHOULD be recorded as:

```yaml
working_tree:
  clean: false

preserve_unrelated_changes:
  - path/to/file-a
  - path/to/file-b
```

This declaration is a preservation warning.

It is NOT permission to:

- discard;
- stash;
- reset;
- restore;
- commit;
- amend;

those changes.

For Type C, unrelated local changes MUST be resolved into a clean durable
state before transfer.

## 7.4 Stash Rule

A stash MAY temporarily help an operator reach a clean local working tree.

A stash MUST NOT contain state required by the Durable Handoff Receiver.

A handoff MUST NOT rely on a reference such as:

```text
stash@{0}
```

as transfer evidence.

If the Receiver needs the stashed state:

```text
HANDOFF NOT READY
```

# 8. Durable Revision Model

A Durable Handoff distinguishes three revision concepts.

## 8.1 `source_revision`

`source_revision` identifies the project state being handed off.

Example:

```yaml
source_revision:
  sha: "<full-git-sha>"
```

The source revision MUST be durable and reachable by the Receiver.

## 8.2 `snapshot_revision`

`snapshot_revision` identifies the Git revision containing the prepared durable
handoff snapshot.

Conceptually:

```text
A -------- B -------- C
           ↑          ↑
           │          │
     source_revision  snapshot_revision
```

`B` is the state being transferred.

`C` records the prepared handoff snapshot.

The snapshot MUST clearly identify `source_revision`.

## 8.3 `verification_revision`

`verification_revision` identifies the revision containing the final recorded
Receiver verification outcome for the current handoff.

Conceptually:

```text
source
  ↓
prepared snapshot
  ↓
receiver verification
  ↓
verification revision
  ↓
accepted / rejected
```

If two verification passes occur, each pass SHOULD remain recoverable through
Git history.

The final `verification_revision` MUST refer to the final gate outcome for that
handoff.

## 8.4 Revision Availability

For a cross-machine or recovery Type C handoff, the relevant revisions MUST be
available through a durable channel accessible to the Receiver.

A local-only commit that can disappear with the Sender workstation is
insufficient.

# 9. Receiver Read Order

Unless task-specific governance requires otherwise, a Receiver SHOULD
reconstruct project context in this order:

```text
1. control/README.md
2. control/roadmap.md
3. control/project-control.yaml
4. control/handoff/README.md
5. control/history/README.md
6. active baseline referenced by project-control.yaml
7. relevant latest CTRL-SNAPSHOT-* when one exists
8. AGENTS.md
9. current DEV/work item and directly linked design/ADR/TEST artifacts
10. Git state and relevant implementation evidence
```

The Receiver SHOULD then read additional source only as needed.

The Receiver SHOULD NOT read the entire repository by default merely because
context is available.

Context acquisition SHOULD remain relevance-driven.

# 10. Mandatory Receiver Verification

A Receiver MUST independently verify material handoff claims.

The Receiver MUST NOT treat Sender prose as proof.

At minimum the Receiver MUST compare:

```text
HANDOFF CLAIM
        ↕
OBSERVED STATE
```

Material comparisons include, where applicable:

- branch;
- full Git revision;
- working-tree state;
- active baseline;
- current phase;
- current milestone;
- current DEV/work item;
- relevant canonical artifact state;
- relevant quality/verification state;
- declared preserve/do-not-touch state.

If a material mismatch exists:

```text
verification_result = rejected
```

The Receiver MUST NOT continue project/domain mutation as though verification
passed.

# 11. Verification Evidence Contract

## 11.1 Minimum Evidence

A Receiver verification record MUST contain enough evidence to reconstruct the
gate decision.

A recommended structure is:

```yaml
receiver_verification:
  verification_pass: 1
  receiver_role: executor
  verified_at: "2026-09-21T12:30:00+07:00"

  expected:
    source_revision: "<full-sha>"
    active_baseline: CTRL-BASELINE-001
    current_milestone: M2

  observed:
    source_revision: "<full-sha>"
    working_tree_clean: true
    active_baseline: CTRL-BASELINE-001
    current_milestone: M2

  checks:
    - check: branch
      command: git branch --show-current
      result: pass

    - check: revision
      command: git rev-parse HEAD
      result: pass

    - check: working_tree
      command: git status --porcelain=v1
      result: pass

  mismatches: []

  result: accepted
  clarification_count: 0
  human_attention_required: false
```

The exact schema MAY evolve.

The semantics MUST remain equivalent.

## 11.2 Evidence Precision

Verification evidence MUST record observed facts.

It MUST NOT invent:

- timestamps;
- command output;
- revision identity;
- clean-state claims;
- successful checks.

If exact time was not captured, the record SHOULD omit the exact time rather
than fabricate one.

## 11.3 Evidence Storage by Handoff Type

For Type A, verification evidence MAY be retained in a governed execution or
session log when that log is reliably available for audit.

For material Type B, verification evidence SHOULD be associated with the
relevant governed work record, PR evidence, DEV evidence, or durable snapshot.

For Type C, verification evidence MUST be persisted durably before project/
domain mutation resumes.

## 11.4 Verification Evidence Is Not Authority

A successful verification record proves that the handoff claims matched the
observed state at verification time.

It does NOT:

- approve architecture;
- approve a DEV;
- waive a policy;
- authorize implementation;
- create an exception;
- change a baseline.

Those authorities remain governed separately.

# 12. Handoff Verification Circuit Breaker

## 12.1 State Machine

The handoff verification lifecycle is:

```text
PREPARED
    ↓
VERIFY_PASS_1
    ├── PASS
    │     ↓
    │   ACCEPTED
    │     ↓
    │   AUTHORITY_CHECK
    │     ↓
    │   RESUME
    │
    └── REJECT
          ↓
      REJECTED_PASS_1
          ↓
      ONE CLARIFICATION/CORRECTION
          ↓
      VERIFY_PASS_2
          ├── PASS
          │     ↓
          │   ACCEPTED
          │     ↓
          │   AUTHORITY_CHECK
          │     ↓
          │   RESUME
          │
          └── REJECT
                ↓
        HANDOFF_CIRCUIT_OPEN
                ↓
      human_attention_required
                ↓
               STOP
```

## 12.2 Pass Budget

The verification budget is:

```text
verification_pass_max = 2
clarification_count_max = 1
```

A failed Pass 1 consumes Pass 1.

A clarification does NOT reset the verification-pass counter.

A corrected snapshot does NOT create a new automatic verification budget for
the same transfer attempt.

## 12.3 Clarification

After Pass 1 rejects the handoff, the Receiver MAY request exactly one
clarification/correction cycle.

The Sender MAY:

- explain an ambiguous claim;
- correct a factual handoff error;
- issue a corrected prepared snapshot;
- make required state durable.

The Sender MUST NOT use clarification to silently:

- expand scope;
- create authority;
- waive a mismatch;
- hide failed verification evidence;
- reset the verification budget.

If correction materially changes the project state being transferred,
`source_revision` MUST be updated accordingly.

## 12.4 Second Failure

If Pass 2 fails:

```text
handoff_circuit_state = open
human_attention_required = true
autonomous_follow_on_allowed = false
```

The Receiver MUST stop autonomous follow-on.

The Sender MUST NOT automatically produce another correction and retry.

No AI actor MAY start Pass 3.

Further disposition requires accountable human action.

## 12.5 Independence from Implementation Circuit Breaker

Handoff verification attempts and implementation attempts are different
budgets.

For example:

```text
handoff verification:
  max passes = 2

implementation:
  MAX_ATTEMPTS = 2
```

A successful handoff does not replenish implementation attempts.

A failed implementation does not reset handoff verification.

A new process or runtime session does not silently reset either governed
budget.

# 13. Handoff Packet Contract

A durable Handoff Packet MUST contain the sections below.

A lightweight Type A packet MAY be smaller where the omitted state can be
deterministically reconstructed from the same workspace.

## 13.1 Identity

The packet MUST identify:

```yaml
handoff:
  id: CTRL-SNAPSHOT-NNN
  type: C
  reason: "<reason>"
  created_on: "YYYY-MM-DD"
  created_by_role: "<role>"
```

Durable identity MUST use an artifact ID defined by the applicable history
convention.

## 13.2 Revision Identity

The packet MUST include:

```yaml
revisions:
  source_revision: "<full-sha>"
  snapshot_revision: "<full-sha-or-pending-until-commit>"
  verification_revision: null
```

Once verification evidence is persisted, `verification_revision` MUST be
recorded or deterministically recoverable.

## 13.3 Control Position

The packet MUST identify or reference:

```text
active baseline
current phase
current milestone
latest completed milestone when relevant
current DEV/work item
next intended DEV/work item when known
```

The packet SHOULD link to `control/project-control.yaml` rather than duplicate
large amounts of current-control data.

## 13.4 Completed Since Previous Transfer

The packet MAY summarize material outcomes completed since the previous
handoff.

This section SHOULD contain outcomes, not commit-by-commit history.

## 13.5 Workspace State

The packet MUST declare workspace assumptions.

Example for Type C:

```yaml
workspace:
  required_clean: true
  observed_clean_at_sender_gate: true
  required_state_in_local_stash: false
```

Example for Type A:

```yaml
workspace:
  required_clean: false
  observed_clean: false

  preserve_unrelated_changes:
    - path/to/unrelated-file
```

## 13.6 Active Constraints and Invariants

The packet MUST identify material invariants that directly constrain the next
work.

It SHOULD reference their canonical source.

It SHOULD NOT copy the entire project invariant catalog.

Example:

```text
MAX_ATTEMPTS = 2
attempt budget owned by execution_scope_id
one open implementation attempt per execution scope
unknown usage never becomes zero
blocked invocation must not reach AIRuntimePort
```

## 13.7 Risks and Blockers

The packet MUST identify material active blockers.

It SHOULD reference active risk IDs from `control/project-control.yaml`.

Resolved historical risk SHOULD NOT be copied unless it materially affects the
transfer.

## 13.8 Resource / Control State

When relevant, the packet SHOULD summarize:

```text
human actual vs baseline
timeline actual vs forecast
AI usage coverage
known variance
current budget/circuit state
```

Unknown resource data MUST remain unknown.

## 13.9 Open Decisions

The packet MUST identify decisions that remain genuinely unresolved and are
required for safe continuation.

Resolved historical discussions SHOULD NOT be copied into this section.

## 13.10 Next Authorized Action

The packet MUST distinguish:

```text
next intended action
```

from:

```text
current authorized action
```

Example:

```text
Next intended:
  implement DEV-008

Currently authorized:
  design/audit DEV-008 only
```

The Receiver MUST obey the narrower authorization.

## 13.11 Stop Conditions

The packet MUST state material stop conditions.

Examples:

```text
unexpected Git revision
dirty Type-C workspace
active baseline mismatch
required artifact missing
policy mismatch
verification pass 2 failure
implementation circuit open
missing human approval
```

## 13.12 Preserve / Do-Not-Touch State

The packet MUST identify known state that the Receiver MUST preserve when
relevant.

Examples:

```text
do not reopen closed Phase 0
do not modify accepted DEV-007 semantics without new governed evidence
do not reset unrelated local work
do not bypass active baseline
do not promote experimental treatment before its gate
```

Preserve instructions MUST NOT override canonical authority.

## 13.13 Known Unknowns

The packet MUST explicitly identify material unknowns that could affect
continuation.

Unknowns MUST NOT be hidden merely to make the handoff appear complete.

## 13.14 Receiver Verification Procedure

The packet MUST define or reference the checks the Receiver is expected to
execute.

For Type C, this procedure MUST include proof-of-verification persistence.

# 14. Authority Transfer Rule

## HO-AUTH-01

A handoff transfers context.

A handoff MUST NOT create, extend, infer, or restore execution authority.

Execution authority MUST originate from:

- applicable canonical governance;
- an explicit accountable human decision;
- an already-valid governed runtime authorization;
- another authority mechanism explicitly defined by SDF governance.

A statement such as:

```text
Next action: implement DEV-008
```

does NOT by itself authorize implementation.

The Receiver MUST distinguish:

```text
what should happen next
```

from:

```text
what I am authorized to do now
```

If authorization is unclear:

```text
STOP
```

and request accountable clarification.

# 15. Pre-Acceptance Mutation Boundary

Before a handoff is accepted, the Receiver MAY:

- read repository state;
- inspect canonical evidence;
- execute non-mutating verification;
- inspect runtime/control evidence;
- write required handoff verification evidence.

Before acceptance, the Receiver MUST NOT:

- implement code;
- modify design;
- modify requirements;
- change policy;
- create migrations;
- modify dependencies;
- perform destructive Git actions;
- auto-fix the handoff mismatch;
- proceed with the transferred domain task.

Verification evidence recording is the only protocol-required write permitted
before acceptance.

# 16. Handoff Lifecycle

The complete lifecycle is:

```text
CLASSIFY
    ↓
PREPARE
    ↓
SENDER VERIFY
    ↓
HANDOFF READY?
    ├── NO → STOP / CORRECT
    └── YES
          ↓
      TRANSFER
          ↓
      RECEIVER RECONSTRUCT
          ↓
      VERIFY PASS 1
          ├── PASS
          │     ↓
          │   ACCEPT
          │     ↓
          │   AUTHORITY CHECK
          │     ↓
          │   RESUME
          │
          └── REJECT
                ↓
          ONE CLARIFICATION
                ↓
          VERIFY PASS 2
                ├── PASS
                │     ↓
                │   ACCEPT
                │     ↓
                │   AUTHORITY CHECK
                │     ↓
                │   RESUME
                │
                └── REJECT
                      ↓
              HANDOFF CIRCUIT OPEN
                      ↓
                 HUMAN ESCALATION
```

Every automatic loop in this lifecycle MUST be finite.

# 17. Sender Gate

Before transfer, the Sender MUST confirm:

- handoff type is classified;
- mandatory packet fields exist;
- source revision is identified;
- applicable workspace-state rule is satisfied;
- Type C source state is durable;
- no required Type C state exists only in stash;
- current project-control state is referenced;
- next action and authorization boundary are distinguished;
- known blockers/risks are disclosed;
- Receiver verification procedure exists;
- when a supported Consumer Profile applies, the Consumer Profile is resolved;
- all profile-required outputs exist;
- the Source Manifest includes `P0`–`P6` labels for represented sources;
- any pruning is visible with reason and context-loss evidence;
- no mandatory source is silently pruned;
- the Package Completeness Gate passes.

If these conditions fail:

```text
HANDOFF NOT READY
```

The Sender MUST NOT label the transfer ready merely because prose has been
written.

# 18. Snapshot Lifecycle

Durable handoff snapshots use the history namespace.

Recommended filename:

```text
control/history/CTRL-SNAPSHOT-NNN.md
```

Recommended artifact type:

```yaml
kind: project-handoff-snapshot
```

## 18.1 Prepared

A snapshot initially enters:

```yaml
status: prepared
```

`prepared` means:

- Sender believes the packet is ready;
- Receiver has not yet accepted it.

`prepared` MUST NOT be interpreted as successful transfer.

## 18.2 Accepted

After successful Receiver verification and persisted verification evidence:

```yaml
status: accepted
```

An accepted snapshot becomes durable historical evidence.

Acceptance of the handoff does NOT imply approval of the domain work itself.

## 18.3 Rejected

If Receiver verification fails:

```yaml
status: rejected
```

Rejected snapshot evidence MUST NOT be deleted merely because a later transfer
succeeds.

A rejected snapshot is useful audit evidence.

## 18.4 Circuit Open

If Pass 2 rejects:

```yaml
status: rejected

handoff_circuit:
  state: open
  human_attention_required: true
```

The failed transfer MUST NOT automatically continue.

## 18.5 Correction Before Final Acceptance

A `prepared` snapshot MAY be corrected after Pass 1 rejection.

The correction MUST remain visible in Git history.

If the project state being transferred changed:

```text
source_revision MUST change
```

If only handoff description/evidence changed:

```text
snapshot_revision MUST change
```

The same transfer still has only one remaining verification pass.

## 18.6 Supersession

A later durable handoff MAY supersede an older snapshot.

The older snapshot MUST remain historically recoverable.

A new independent transfer after human disposition SHOULD normally use a new
`CTRL-SNAPSHOT-NNN` identity rather than pretending that the failed transfer
never occurred.

# 19. Definition of Handoff Ready

Handoff readiness is binary.

Allowed results:

```text
HANDOFF READY
HANDOFF NOT READY
```

No percentage or aggregate handoff score is used.

A handoff is READY only when all applicable checks below pass:

```text
[ ] handoff type classified

[ ] source revision explicit

[ ] snapshot revision model defined when durable

[ ] active baseline explicit or deterministically referenced

[ ] current phase/milestone/work explicit

[ ] workspace rule satisfied for the selected handoff type

[ ] Type C working tree clean

[ ] Type C required state does not exist only in stash

[ ] relevant canonical evidence linked

[ ] active blockers/risks explicit

[ ] next intended action explicit

[ ] current authorization boundary explicit

[ ] stop conditions explicit

[ ] preserve/do-not-touch state explicit where applicable

[ ] material unknowns explicit

[ ] receiver verification procedure defined

[ ] verification evidence location defined where required

[ ] verification pass budget = 2

[ ] clarification budget = 1

[ ] circuit-open escalation behavior defined

[ ] paths are repository-relative and cross-platform

[ ] no required context exists only in previous chat history

[ ] applicable Consumer Profile resolved

[ ] all Consumer-Profile required outputs generated

[ ] Source Manifest priorities and prune evidence complete

[ ] no mandatory source silently pruned

[ ] Receiver Bootstrap Instruction complete

[ ] Package Completeness Gate passed
```

One failed mandatory check means:

```text
HANDOFF NOT READY
```

# 20. Receiver Acceptance Gate

Before resuming transferred work, the Receiver MUST be able to answer:

```text
1. What outcome is the project currently pursuing?

2. What active project baseline governs the current work?

3. What repository revision and workspace state am I actually observing?

4. What phase and milestone is the project currently in?

5. What work item is current or next?

6. Which invariants, blockers and risks materially constrain that work?

7. What am I authorized to do now, and what am I not authorized to do?
```

For a durable handoff, the Receiver MUST additionally prove:

```text
HANDOFF CLAIM == OBSERVED STATE
```

for all material transfer claims.

If a material claim cannot be verified:

```text
REJECT
```

not:

```text
probably correct
close enough
likely intended
```

# 21. Staleness and Mismatch Handling

## 21.1 Stale Control State

If a snapshot and current project-control state differ because the project
legitimately advanced after the snapshot:

- the snapshot remains historical evidence;
- `control/project-control.yaml` remains current delivery-control authority;
- Receiver MUST determine whether the old snapshot is still applicable.

The snapshot MUST NOT overwrite newer current state.

## 21.2 Unexpected Revision

If observed revision differs materially from the handoff claim:

```text
REJECT
```

The Receiver MUST NOT reset, checkout, restore, or otherwise force the
repository to match the handoff unless separately authorized.

Mismatch discovery is evidence.

It is not automatic permission to repair.

## 21.3 Unexpected Dirty State

For Type C:

```text
observed dirty state
        ↓
REJECT
```

The Receiver MUST NOT clean the workspace automatically merely to make
verification pass.

The dirty state may contain valuable untransferred work.

## 21.4 Missing Artifact

If a required canonical/control artifact is missing:

```text
REJECT
```

The Receiver MUST NOT synthesize a replacement and proceed unless separately
authorized to repair project state.

## 21.5 Semantic Conflict

If deterministic checks pass but the Receiver identifies a material semantic
conflict:

```text
REJECT or ESCALATE
```

depending on verification-pass state.

Structural validation does not overrule accountable semantic review.

# 22. Human Escalation

Human escalation is required when:

- verification Pass 2 fails;
- source state cannot be reconstructed;
- authorization is ambiguous;
- required durable state appears lost;
- a material semantic conflict remains unresolved;
- a destructive repair would be required;
- policy/governance conflict exists;
- handoff circuit is open.

When escalation is required:

```text
human_attention_required = true
autonomous_follow_on_allowed = false
```

The accountable human MAY decide to:

- correct source state;
- approve a new handoff;
- create a new snapshot;
- abandon the transfer;
- change scope;
- change authorization;
- accept a risk;
- initiate a separately governed repair.

Human action MUST NOT be represented as though it were automatic protocol
behavior.

# 23. Cross-Platform Rules

Handoff artifacts MUST be portable across supported development environments.

Repository paths MUST:

- be repository-relative;
- use `/`;
- avoid machine-specific roots.

Correct:

```text
control/project-control.yaml
design/decisions/ADR-006.md
src/ai_execution/gateway.py
```

Incorrect:

```text
D:\Docs\ai_sdf\design\decisions\ADR-006.md
C:\Users\name\project\...
/Users/name/project/...
```

Text artifacts SHOULD use:

```text
UTF-8
```

Repository line-ending policy SHOULD determine final line endings.

Exact timestamps SHOULD use timezone-aware ISO 8601:

```text
2026-09-21T12:30:00+07:00
```

Dates SHOULD use:

```text
YYYY-MM-DD
```

A timestamp MUST NOT be invented when only a date is known.

# 24. Provider and Tool Neutrality

Handoff semantics MUST NOT depend on:

- ChatGPT memory;
- Codex-specific hidden state;
- one VS Code extension;
- one MCP implementation;
- one provider session;
- one proprietary conversation identifier.

A provider-specific execution tool MAY participate in a handoff.

Provider-specific state MUST NOT become the only durable representation of
project context.

# 25. Lean and Duplication Rules

Handoff is a control mechanism, not a documentation ceremony.

The Factory MUST NOT create a durable snapshot for every trivial session
transition.

Recommended default:

```text
routine same-workspace continuation:
  Type A
  no durable snapshot unless needed

material transfer:
  Type B
  durable evidence when risk justifies it

cross-machine / long pause / recovery / phase boundary:
  Type C
  durable snapshot
```

A handoff SHOULD link to:

- roadmap;
- project control;
- baseline;
- ADR;
- DEV;
- TEST;
- Git evidence;

instead of copying their full content.

The handoff packet SHOULD contain only information needed to:

```text
reconstruct
verify
decide
resume safely
```

No handoff artifact should exist merely because a template contains an empty
section.

# 26. Current State vs Handoff History

The roles of project-control artifacts are distinct:

```text
control/project-control.yaml
    = current delivery-control state

control/roadmap.md
    = outcome/milestone structure

control/history/CTRL-BASELINE-*
    = accepted baseline history

control/history/CTRL-REBASELINE-*
    = accepted material rebaseline history

control/history/CTRL-SNAPSHOT-*
    = durable observation/transfer history

control/handoff/README.md
    = handoff protocol
```

A snapshot MUST NOT become a second mutable current-state database.

Current-state changes belong in `control/project-control.yaml`.

Historical transfer evidence belongs in snapshots.

# 27. Handoff and Project Baselines

A handoff MUST identify the active baseline that governed the transferred work
when baseline state is material.

A handoff MUST NOT:

- silently rebaseline;
- reinterpret a forecast as a commitment;
- alter approved scope;
- change resource budgets;
- reset variance.

If a handoff discovers that a baseline assumption is materially invalid:

```text
handoff verification
        ↓
report mismatch/risk
        ↓
human/project-control decision
        ↓
rebaseline if approved
```

Handoff itself is not a rebaseline mechanism.

# 28. Handoff and Execution Budgets

A handoff MUST preserve existing governed execution-budget state.

A new:

- session;
- process;
- machine;
- Receiver;
- snapshot;

MUST NOT silently reset:

- implementation attempts;
- circuit state;
- runtime reconciliation state;
- execution-scope identity;
- another governed resource budget.

Handoff is a transfer mechanism.

It is not a budget-reset mechanism.

# 29. Handoff Security Rules

A Handoff Packet MUST NOT contain secrets merely for convenience.

Secrets include, where applicable:

- access tokens;
- passwords;
- private keys;
- session credentials;
- provider credentials.

A handoff SHOULD reference the governed mechanism for obtaining authorized
credentials rather than copy credential values.

A Receiver MUST NOT infer that possession of handoff context grants permission
to access protected systems.

# 30. Failure Semantics

A failed handoff is a valid system outcome.

The protocol MUST prefer:

```text
explicit rejection
```

over:

```text
unsafe continuation
```

The Factory MUST preserve enough evidence to learn from repeated handoff
failure.

Repeated failure patterns SHOULD eventually become:

- deterministic validation;
- schema rules;
- tooling;
- improved control design;

when evidence shows that automation would reduce recurring waste.

# 31. Initial Adoption State

At initial adoption of this standard:

```text
Project Control Baseline:
  CTRL-BASELINE-001
  accepted / active

Current project phase:
  Phase 1

Current planned next milestone:
  M2 — Bounded Autonomous Execution
```

This section records adoption context only.

It MUST NOT be maintained as a competing current-state record.

Current project state MUST always be read from:

```text
control/project-control.yaml
```

# 32. First Validation Strategy

The Factory SHOULD prove this standard through real handoffs before adding
large automation around it.

Initial validation SHOULD include at least:

```text
one Type A handoff
one durable Type C handoff
```

The first durable validation SHOULD demonstrate:

```text
clean source state
full source revision
prepared CTRL-SNAPSHOT-NNN
receiver reconstruction
persisted verification evidence
bounded verification
accepted or explicitly rejected outcome
authority check before resume
```

Automation, schemas, or validators SHOULD be introduced after repeated
handoff behavior reveals stable deterministic rules worth enforcing.

The Factory MUST NOT build a large handoff platform before the protocol itself
has been exercised.

# 33. Consumer Profiles

The core Handoff Operating Standard MUST remain consumer/provider-neutral.

Receiver-specific constraints MUST be expressed through a named Consumer
Profile rather than embedded as universal handoff invariants.

A Consumer Profile defines the derivation contract required to make the
handoff operational for one receiver class.

A supported Consumer Profile MUST declare at least:

```yaml
profile_id: <stable-id>
consumer_kind: <receiver-class>
status: active | experimental | retired

context_constraints:
  max_source_files: <integer-or-null>

required_outputs:
  - handoff_packet
  - source_manifest
  - receiver_bootstrap_instruction
  - verification_contract
  - authority_and_stop_conditions

source_selection_policy:
  priority_model: P0-P6

receiver_verification:
  max_passes: 2
  max_clarification_cycles: 1
```

Additional constraints MAY be declared when required by the receiver, but they
MUST NOT redefine core authority, budget, baseline, or handoff semantics.

Consumer-specific limits such as an attachment count belong to the Consumer
Profile. They MUST NOT be promoted into universal SDF invariants.

Initial supported profiles include:

```text
control/handoff/profiles/chatgpt-session.md
control/handoff/profiles/gemini-session.md
```

# 34. Source Priority Model

The following priority model is the default derivation order for
bounded-context handoffs. A Consumer Profile MAY refine selection within a
priority class but MUST preserve the meaning of the classes.

| Priority | Source class | Derivation intent |
|---|---|---|
| `P0` | Handoff packet / transfer identity | Establish exactly what is being transferred |
| `P1` | Current project-control authority/state | Active baseline, roadmap/current control, handoff/profile contract |
| `P2` | Active governance and current-work control | Executable policy, trace truth, active phase/work plan |
| `P3` | Next-work intent/design chain | Problem, requirements/NFRs, component/design, ADR/contracts needed for the next work |
| `P4` | Predecessor evidence | Latest completed work and verification needed to understand the current boundary |
| `P5` | Implementation reality | Code/config/tests/runtime surfaces materially needed by the next work |
| `P6` | Historical/reference/supporting material | Background, older history, reference material, secondary evidence |

## 34.1 Selection Semantics

The derivation process MUST first determine whether a candidate source is
`mandatory` for correct reconstruction. Priority ordering is then used to rank
non-mandatory candidates under the consumer limit.

The Sender MUST NOT treat `P6` as "safe to lose" merely because it is
historical/reference material. A `P6` source that is mandatory for the current
handoff remains mandatory.

When the limit requires pruning:

1. prune non-mandatory sources before mandatory sources;
2. prefer pruning lower-value candidates from `P6`, then `P5`, before reducing
   higher-priority context;
3. preserve an explicit prune log in the Source Manifest;
4. state the context region lost by the pruning, not merely the filename;
5. fail closed if mandatory context still exceeds the consumer limit.

A Receiver MUST be able to distinguish:

```text
not selected because irrelevant
```

from:

```text
relevant but pruned because of consumer limit
```

and from:

```text
mandatory and therefore not legally prunable
```

# 35. Source Manifest Contract

For a bounded-context handoff, the Source Manifest is a mandatory derived
output.

It MUST contain, at minimum:

```yaml
consumer_profile: <profile-id>
source_limit: <integer-or-null>

selected_sources:
  - priority: P0
    path: <repo-relative-path-or-durable-source-id>
    mandatory: true
    role: <why-the-receiver-needs-this-source>

pruned_sources:
  - priority: P6
    path: <repo-relative-path-or-durable-source-id>
    mandatory: false
    reason: <why-it-was-pruned>
    context_loss: <what-context-region-is-no-longer-directly-available>

derivation:
  candidate_count: <integer>
  selected_count: <integer>
  pruned_count: <integer>
  human_overrides: []
```

Repository sources MUST use repository-relative forward-slash paths.

The manifest MUST NOT claim that a source exists, is current, or is reachable
when that has not been established.

When a human override changes the generated selection, record:

```yaml
human_overrides:
  - action: add | remove | substitute
    source: <path-or-id>
    reason: <explicit-reason>
```

The generated prune history MUST remain visible after the override.

# 36. Semi-Auto Derivation Process

For a handoff using a supported Consumer Profile, the Sender MUST execute the
following logical process before declaring the package `READY`:

```text
1. Classify handoff
        ↓
2. Resolve Consumer Profile
        ↓
3. Capture repository/control/workspace state
        ↓
4. Resolve current work, locked state, authority, and known unknowns
        ↓
5. Derive candidate source set
        ↓
6. Mark mandatory sources
        ↓
7. Assign P0–P6 priority to every candidate
        ↓
8. Select/prune under consumer constraints
        ↓
9. Generate Source Manifest, including prune log
        ↓
10. Generate handoff packet
        ↓
11. Generate Receiver Bootstrap Instruction
        ↓
12. Generate Receiver Verification contract
        ↓
13. Run Package Completeness Gate
        ↓
14. Human review / explicit override if needed
        ↓
15. Re-run Package Completeness Gate after override
        ↓
16. Declare READY
```

The Sender MUST NOT skip Source Manifest generation merely because the handoff
packet already names some files.

The Sender MUST NOT declare `READY` before the Package Completeness Gate passes.

# 37. Derivation Failure States

The following failures block `READY`:

```text
consumer_profile_unresolved
mandatory_output_missing
mandatory_source_set_exceeds_consumer_limit
source_priority_missing
prune_log_missing
bootstrap_instruction_incomplete
verification_contract_missing
authority_boundary_missing
known_state_contradiction
```

A derivation failure is not permission to fabricate, compress away, or silently
drop required context.

Human attention MAY resolve the condition, but the resolution MUST remain
visible in the handoff evidence.

# 38. Semi-Auto Readiness Acceptance

A Consumer Profile is not considered semi-auto derivation ready merely because
its document exists.

It MUST be proven through at least one real handoff in which:

```text
[ ] handoff type is derived without human correction
[ ] consumer profile is selected without human discovering it is needed
[ ] all profile-required outputs are generated
[ ] source candidates receive P0–P6 labels
[ ] bounded Source Manifest is generated
[ ] all pruning is visible with reasons/context loss
[ ] Receiver Bootstrap Instruction is generated
[ ] Receiver Verification contract is generated
[ ] human does not have to identify a missing mandatory package component
[ ] Package Completeness Gate passes before READY
[ ] Receiver can execute the verification protocol from the package
```

A failed real handoff MAY be used as dogfood evidence to refine the standard.
Failure does not justify weakening the gate.

The delayed DEV-008 ChatGPT-session handoff MAY serve as the first Patient Zero
for this v2 derivation contract.

# 39. v2 Explicit Non-Effects

This v2 standard:

- does NOT change `CTRL-BASELINE-001`;
- does NOT change `CTRL-ROADMAP-001` v2;
- does NOT change Phase-1 bounded-AI design;
- does NOT expand DEV-008 scope;
- does NOT create or consume an implementation attempt;
- does NOT require `knowledge/evolution.yaml`;
- does NOT require a generator, schema, validator, or CI integration yet;
- does NOT make any Consumer-specific limit a universal SDF invariant.

The initial implementation target is the operating contract itself plus
Consumer-Profile evidence. Automation MAY follow only after repeated handoffs
show a stable derivation shape.

# 40. Standard Evolution

This standard MAY evolve as handoff evidence accumulates.

Material changes to handoff authority, verification budgets, clean-state
requirements, or escalation semantics MUST receive accountable human review.

Accepted historical handoff evidence MUST remain interpretable under the
standard version that governed it.

Future automation MAY validate this standard.

Automation MUST NOT silently weaken its human-accountability or bounded-loop
requirements.
