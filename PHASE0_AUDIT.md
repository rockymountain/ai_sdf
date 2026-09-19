# Phase 0 Audit Notes

## Enforced deterministically

- Markdown artifact identity comes only from YAML frontmatter.
- Artifact frontmatter is validated against JSON Schema.
- Duplicate IDs fail.
- Dangling references fail.
- Task artifacts missing from the trace graph fail.
- T1/T2 policy requirements fail when evidence classes are missing.
- T1/T2 PRs require a matching `[DEV-nnn]` marker in at least one commit.
- T1/T2 PR diffs must touch at least one declared `implementation.paths` entry.
- Obvious architecture/decision/contract/infra/migration path changes force T2.
- PR-declared task and traceability level must match canonical traceability data.
- T1/T2 risk attestation must be complete.
- `AGENTS.md` must be reproducible from canonical governance.

## Deliberately NOT claimed by Phase 0

A deterministic validator cannot prove that a code-only change is semantically non-architectural. A developer can still alter architecture inside an ordinary source path while declaring T1. In Phase 0 this is explicitly a **Human Gate** responsibility: the reviewer must reject understated classification. A later semantic critic may assist, but it must not replace deterministic checks or human accountability.

## Bill attack cases covered by tests

1. Filename disagrees with frontmatter ID: frontmatter wins; no grep-based identity.
2. Trace points to `ADR-999`: validation fails.
3. Duplicate frontmatter ID: validation fails.
4. T2 lacks decision/contract: validation fails.
5. Orphan task artifact: validation fails.
6. Correct DEV marker but diff avoids declared implementation path: validation fails.
7. Correct diff but commit lacks DEV marker: validation fails.
8. T1 touches `design/architecture/**`: validation forces T2.
9. T1 attestation is incomplete: validation fails.
