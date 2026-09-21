Traceability Task: DEV-009
Traceability Level: T0

### Why?

Default-required provenance must support material Project Control changes without
misclassifying them as implementation DEV tasks or exempting `control/**`.

### What changed?

Canonical policy defines the `project_control` owner kind. The validator uses only
base-authorized owner kinds and paths for coverage, requires durable unique commit
markers, validates proposed policy structure, and preserves separate T2 DEV task
coverage. Existing DEV declarations continue unchanged.

### Evidence

Focused provenance and policy-validation regressions cover owner parsing, path
boundaries, commit markers, historical ID reuse, mixed DEV/control ownership,
anti-self-authorization, malformed policy, and unchanged DEV behavior. The complete
deterministic suite and committed PR-evidence validation also pass.
