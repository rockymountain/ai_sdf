## Change declaration

For multiple tasks, repeat the entire declaration block, including its task/level
and risk attestation. Each declared T1/T2 task needs its own commit marker and a
matching changed implementation path. Together the tasks must cover every
significant changed file. T2-sensitive files require a covering T2 task.

If every changed file is explicitly exempt or generated under the PR base's
constitution/policies.yaml, omit the declaration blocks. Canonical design files,
code, tests, governance, CI, and unclassified paths still require coverage.

For a non-task owner kind authorized by the PR base policy, repeat this paired
block as needed. Each owner ID requires its exact `[<owner-id>]` commit marker and
covers only the base policy's allowed paths. This does not replace T2 DEV coverage.

Change Owner: CTRL-CHANGE-___
Change Owner Kind: project_control

Traceability Task: DEV-___
Traceability Level: T_

### Why?
Describe the upstream problem/requirement this change serves.

### What changed?
Describe the implementation delta, not just the files touched.

### Evidence
List test/runtime/manual evidence and relevant IDs.

## Risk classification attestation

For **T1**, check all statements below. If any statement is false, classify the change as **T2**.

- [ ] I confirm this change does **NOT** affect architecture boundaries or dependencies.
- [ ] I confirm this change does **NOT** affect NFRs or reliability assumptions.
- [ ] I confirm this change does **NOT** affect security or authorization boundaries.
- [ ] I confirm this change does **NOT** affect persistent data models or migrations.
- [ ] I confirm this change does **NOT** affect public/external API or event contracts.
- [ ] I confirm this change does **NOT** create a compliance or irreversible migration concern.

For **T2**:

- [ ] I acknowledge this is a material design change and have linked the required design + decision/contract + verification evidence.

Reviewer note: classification is a human gate. If the declared level understates actual impact, reject the PR even if deterministic CI passes.
