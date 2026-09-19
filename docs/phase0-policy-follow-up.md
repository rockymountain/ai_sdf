# Phase 0 policy inventory and follow-up debt

Recorded for DEV-004 on 2026-09-19. Owner: factory-maintainer. No future task IDs
are allocated here; prioritize and allocate each follow-up separately.

| Category at the merged DEV-003 baseline | Inventory |
|---|---|
| Canonical-policy-driven semantics | Per-level evidence classes; sensitive-path patterns; provenance exclusion lists; artifact schemas; generated instruction content. |
| Hardcoded governance semantics | PR evidence applicability, marker/path requirements and marker format despite canonical flags; T2 ownership; risk-attestation text; current-task lifecycle scope; provenance precedence; quality-gate declarations not executed. |
| Hardcoded execution mechanisms | YAML/JSON/schema parsing, Git invocation, filesystem traversal/resolution, path matching, PR-text extraction, diagnostics, and CI sequencing. These are mechanisms, not governance merely because they are Python. |

## Candidate evaluation

- T2 sensitive-path escalation: patterns already canonical; ownership/precedence
  remain hardcoded. Defer this independent rule family.
- Traceability-level evidence: already reads canonical requires flags. Defer
  comprehensive policy validation and base-policy protection for these flags.
- PR evidence: existing flags/template are ignored. DEV-004 moves this family
  into executable QG-004 with validated scope and protected base obligations.
- Change provenance: exclusions already canonical and base-governed. Defer
  migration of precedence and mandatory-default semantics into further gates.

## Environment reproducibility debt

CI uses Python 3.13. requirements-dev.txt pins PyYAML 6.0.2 and jsonschema 4.25.1.
The current local interpreter is Python 3.14.6 with PyYAML 6.0.3 and jsonschema
4.25.1, confirming the user's reported environment drift. PyYAML 6.0.2 lacked a
wheel for the local 3.14 setup. Earlier agent runs used a temporary pure-Python
6.0.2 installation, but that does not make the current global environment match CI.
There is no repository declaration aligning the local interpreter with CI and
no complete transitive dependency lock.

Keep environment/dependency changes out of DEV-004: they are independently useful
work, not needed to implement the selected policy family. Follow-up acceptance:
declare one supported local/CI Python setup, install the declared dependencies in
a clean environment, record versions, and run the same complete suite locally and
in CI. Preserve historical evidence with the versions actually used.

## Remaining governance work

- Make QG-001/002/003/005/006 executable as separately scoped, justified increments.
- Validate all trace-level requirements and escalation settings without permissive
  missing-field defaults, with explicit self-modification protection.
- Move risk-attestation content, T2 ownership/precedence, DEV-002 lifecycle scope,
  and provenance precedence into their appropriate canonical rule families.
- Risk-attestation applicability is also still hardcoded rather than driven by
  each level's risk_attestation flag. Artifact identity descriptors remain
  declarative; Python enforces frontmatter identity, duplicate rejection, task
  orphan checks, and relationship-prefix mappings. Treat these as future rule
  families, distinct from the parsing and matching mechanisms that implement them.
- Preserve human review for semantic level classification and material policy/risk
  approval; deterministic checks do not establish reviewer identity or authorization.
- Remove the pinned QG-004 legacy adapter once no supported transition PR needs it.
- Protect validator/CI code through review and branch rules; base-policy evaluation
  alone does not defend against replacement of the enforcement code itself.
