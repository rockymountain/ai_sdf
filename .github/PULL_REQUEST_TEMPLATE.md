## Change declaration

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
