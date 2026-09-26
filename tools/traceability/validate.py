#!/usr/bin/env python3
"""Deterministic Phase-0 traceability validator.

Identity is extracted from YAML frontmatter, never filenames/grep.
Semantic architecture classification remains a human responsibility in Phase 0.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
TASK_RE = re.compile(r"^DEV-[0-9]{3,}$")
QG004_BOOTSTRAP_BASE = "972774f18b879d023eb005d1af021699ed6b4ed5"
QG004_SCHEMA = "knowledge/schemas/implementation-evidence-gate.schema.json"
AUTONOMOUS_EXECUTION_SCHEMA = "knowledge/schemas/autonomous-execution-policy.schema.json"
STRUCTURAL_GATES = {"QG-001": "artifact-schema", "QG-002": "reference-integrity"}
LEARNING_DISPOSITION_SCHEMA = "knowledge/schemas/learning-disposition.schema.json"
QG003_SCHEMA = "knowledge/schemas/traceability-policy-gate.schema.json"
QG005_SCHEMA = "knowledge/schemas/risk-attestation-gate.schema.json"
# Increment B (DEV-015) migration-only compatibility adapter: pinned to the exact
# pre-Increment-B base authorized by Owner Gate B-A. Never a branch name/HEAD~n.
QG003_QG005_BOOTSTRAP_BASE = "305d51446e3823f3b990668a2af120dc7b295d6e"
ESCALATION_TRIGGERS = frozenset({
    "architecture", "nfr", "security", "data_model",
    "external_contract", "reliability", "compliance", "migration",
})
# Pre-Increment-B has_risk_attestation() evidence semantics, preserved as migration-only
# bootstrap compatibility data. The identical values are also the canonical production
# risk_attestation policy content, but that policy is read from governance, never from here.
LEGACY_RISK_ATTESTATION_SUBSTRINGS: dict[str, tuple[str, ...]] = {
    "T0": (),
    "T1": (
        "does **NOT** affect architecture",
        "does **NOT** affect NFRs",
        "does **NOT** affect security",
        "does **NOT** affect persistent data",
        "does **NOT** affect public/external API",
        "does **NOT** create a compliance",
    ),
    "T2": ("material design change",),
}

SCHEMA_BY_KIND = {
    "problem": "problem.schema.json",
    "requirement": "requirement.schema.json",
    "decision": "decision.schema.json",
    "component": "component.schema.json",
    "contract": "contract.schema.json",
    "verification": "verification.schema.json",
    "task": "task.schema.json",
}

ALLOWED_PREFIX_BY_FIELD = {
    "intent": ("PROB-", "FR-", "NFR-"),
    "design": ("CMP-",),
    "decisions": ("ADR-",),
    "contracts": ("API-", "EVT-"),
    "verification": ("TEST-",),
}

@dataclass
class Artifact:
    id: str
    kind: str
    path: Path
    metadata: dict[str, Any]

class ValidationErrorSet:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
    def error(self, msg: str) -> None: self.errors.append(msg)
    def warn(self, msg: str) -> None: self.warnings.append(msg)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class GovernanceLoader(yaml.SafeLoader):
    """Reject ambiguous mappings in the canonical documents used by QG-004."""


def governance_mapping(loader: GovernanceLoader, node: yaml.MappingNode) -> dict:
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in mapping:
            raise ValueError(f"duplicate governance key {key!r}")
        mapping[key] = loader.construct_object(value_node)
    return mapping


GovernanceLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, governance_mapping)


@dataclass(frozen=True)
class ImplementationEvidenceGate:
    levels: tuple[str, ...]
    require_commit_marker: bool
    marker_format: str
    require_changed_path_match: bool


@dataclass(frozen=True)
class StructuralGate:
    id: str
    name: str


@dataclass(frozen=True)
class ChangeOwnerKind:
    id_pattern: str
    allowed_paths: tuple[str, ...]


@dataclass(frozen=True)
class ChangeProvenancePolicy:
    exclusions: tuple[str, ...]
    owner_kinds: dict[str, ChangeOwnerKind]


@dataclass(frozen=True)
class ChangeOwnerDeclaration:
    owner_id: str
    kind: str


@dataclass(frozen=True)
class LevelPolicy:
    description: str
    requires: dict[str, bool]


@dataclass(frozen=True)
class TracePolicy:
    levels: dict[str, LevelPolicy]
    escalation_triggers: tuple[str, ...]
    t2_path_triggers: tuple[str, ...]


@dataclass(frozen=True)
class RiskAttestationPolicy:
    evidence_source: str
    evidence_format: str
    match_mode: str
    levels: dict[str, tuple[str, ...]]


def load_implementation_evidence_gate(repo: Path, ref: str | None = None) -> ImplementationEvidenceGate:
    """Load one supported gate, not a general policy interpreter. No permissive defaults."""
    try:
        def read(path: str) -> str:
            return git(repo, "show", f"{ref}:{path}") if ref else (repo / path).read_text(encoding="utf-8")

        gates_doc = yaml.load(read("constitution/quality-gates.yaml"), Loader=GovernanceLoader)
        policies_doc = yaml.load(read("constitution/policies.yaml"), Loader=GovernanceLoader)
        if not isinstance(gates_doc, dict) or type(gates_doc.get("version")) is not int or gates_doc["version"] != 1:
            raise ValueError("quality-gates.yaml requires version 1")
        gates = gates_doc.get("gates")
        if not isinstance(gates, list) or any(not isinstance(g, dict) or not isinstance(g.get("id"), str) for g in gates):
            raise ValueError("gates must be a list of identified mappings")
        ids = [g["id"] for g in gates]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate quality gate ID")
        if ids.count("QG-004") != 1:
            raise ValueError("mandatory QG-004 declaration is missing")
        gate = next(g for g in gates if g["id"] == "QG-004")
        bootstrap = ref is not None and git(repo, "rev-parse", ref).strip() == QG004_BOOTSTRAP_BASE
        if bootstrap:
            # The only supported pre-executable shape is this immutable merged baseline.
            if gate != {"id": "QG-004", "name": "implementation-evidence", "deterministic": True, "blocks_merge": True}:
                raise ValueError("unexpected QG-004 bootstrap declaration")
            gate = dict(gate, scope={"event": "pull_request", "levels": ["T1", "T2"]}, policy="implementation_evidence")
        schema = load_json(repo / QG004_SCHEMA) if bootstrap else json.loads(read(QG004_SCHEMA))
        Draft202012Validator.check_schema(schema)
        policy = policies_doc["implementation_evidence"]
        errors = list(Draft202012Validator(schema).iter_errors({"gate": gate, "policy": policy}))
        if errors:
            raise ValueError("; ".join(error.message for error in errors))
        if policy["commit_marker_format"].count("DEV-n") != 1:
            raise ValueError("commit_marker_format must contain exactly one DEV-n placeholder")
        return ImplementationEvidenceGate(
            tuple(gate["scope"]["levels"]), policy["t1_t2_require_commit_marker"],
            policy["commit_marker_format"], policy["t1_t2_require_changed_path_match"],
        )
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, yaml.YAMLError, SchemaError) as exc:
        raise ValueError(f"QG-004 governance ({ref or 'workspace'}): {exc}") from exc


def load_structural_gates(repo: Path, ref: str | None = None) -> tuple[StructuralGate, ...]:
    """Bind QG-001/QG-002 as authoritative declarations for the existing artifact-schema
    (scan_artifacts) and reference-integrity (validate_traceability) checks. Validates
    only declaration identity, shape, and required presence; it does not duplicate or
    reinterpret those existing substantive checks."""
    try:
        def read(path: str) -> str:
            return git(repo, "show", f"{ref}:{path}") if ref else (repo / path).read_text(encoding="utf-8")

        gates_doc = yaml.load(read("constitution/quality-gates.yaml"), Loader=GovernanceLoader)
        if not isinstance(gates_doc, dict) or type(gates_doc.get("version")) is not int or gates_doc["version"] != 1:
            raise ValueError("quality-gates.yaml requires version 1")
        gates = gates_doc.get("gates")
        if not isinstance(gates, list) or any(not isinstance(g, dict) or not isinstance(g.get("id"), str) for g in gates):
            raise ValueError("gates must be a list of identified mappings")
        ids = [g["id"] for g in gates]
        resolved = []
        for gate_id, name in STRUCTURAL_GATES.items():
            if ids.count(gate_id) != 1:
                raise ValueError(f"mandatory {gate_id} declaration is missing or duplicated")
            gate = next(g for g in gates if g["id"] == gate_id)
            if gate != {"id": gate_id, "name": name, "deterministic": True, "blocks_merge": True}:
                raise ValueError(f"unsupported {gate_id} declaration shape")
            resolved.append(StructuralGate(gate_id, name))
        return tuple(resolved)
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
        raise ValueError(f"structural gate governance ({ref or 'workspace'}): {exc}") from exc


def _validate_risk_applicability_invariant(trace_policy: TracePolicy, risk_policy: RiskAttestationPolicy) -> None:
    """FR-009/ADR-010: requires.risk_attestation is the sole applicability authority;
    an applicable level must select a non-empty QG-005 evidence contract."""
    for level, level_policy in trace_policy.levels.items():
        if level_policy.requires.get("risk_attestation") and not risk_policy.levels.get(level):
            raise ValueError(f"risk_attestation policy: level {level} is applicable but has no required evidence")


def _parse_legacy_traceability_policy(policies_doc: dict[str, Any]) -> TracePolicy:
    """DEV-015 bootstrap only: reconstruct the pre-Increment-B traceability policy
    shape already present at the pinned base, without consulting the new schema."""
    required_fields = {
        "upstream_intent", "design", "decision_or_contract",
        "implementation", "verification", "risk_attestation",
    }
    raw = policies_doc.get("traceability")
    if not isinstance(raw, dict) or set(raw) != {"levels", "escalation_triggers", "t2_path_triggers"}:
        raise ValueError("legacy traceability policy must contain exactly levels, escalation_triggers, t2_path_triggers")
    levels_raw = raw["levels"]
    if not isinstance(levels_raw, dict) or set(levels_raw) != {"T0", "T1", "T2"}:
        raise ValueError("legacy traceability policy levels must be exactly T0, T1, T2")
    levels = {}
    for level, data in levels_raw.items():
        if (not isinstance(data, dict) or set(data) != {"description", "requires"}
                or not isinstance(data["description"], str) or not data["description"]
                or not isinstance(data["requires"], dict) or set(data["requires"]) != required_fields
                or any(type(v) is not bool for v in data["requires"].values())):
            raise ValueError(f"legacy traceability policy level {level} has unsupported shape")
        levels[level] = LevelPolicy(data["description"], dict(data["requires"]))
    triggers = raw["escalation_triggers"]
    if not isinstance(triggers, list) or len(triggers) != len(set(triggers)) or set(triggers) != ESCALATION_TRIGGERS:
        raise ValueError("legacy escalation_triggers must be exactly the supported eight-value set")
    path_triggers = raw["t2_path_triggers"]
    if (not isinstance(path_triggers, list) or not path_triggers
            or any(not isinstance(p, str) or not p for p in path_triggers)):
        raise ValueError("legacy t2_path_triggers must be a non-empty list of nonempty path patterns")
    return TracePolicy(levels, tuple(triggers), tuple(path_triggers))


def load_traceability_and_risk_gates(repo: Path, ref: str | None = None) -> tuple[TracePolicy, RiskAttestationPolicy]:
    """Bind QG-003 (traceability-policy) and QG-005 (risk-attestation) as one
    authoritative, fail-closed contract pair reused by static and PR validation.

    `traceability.levels.<level>.requires.risk_attestation` is the sole deterministic
    risk-attestation applicability authority; QG-005 level contracts determine
    evidence content only. QG-003/QG-005 retain separate gate identities. A
    migration-only compatibility adapter exists for exactly the pinned pre-Increment-B
    base; every other base/workspace revision requires the Increment B schemas."""
    try:
        def read(path: str) -> str:
            return git(repo, "show", f"{ref}:{path}") if ref else (repo / path).read_text(encoding="utf-8")

        gates_doc = yaml.load(read("constitution/quality-gates.yaml"), Loader=GovernanceLoader)
        if not isinstance(gates_doc, dict) or type(gates_doc.get("version")) is not int or gates_doc["version"] != 1:
            raise ValueError("quality-gates.yaml requires version 1")
        gates = gates_doc.get("gates")
        if not isinstance(gates, list) or any(not isinstance(g, dict) or not isinstance(g.get("id"), str) for g in gates):
            raise ValueError("gates must be a list of identified mappings")
        ids = [g["id"] for g in gates]
        if ids.count("QG-003") != 1:
            raise ValueError("mandatory QG-003 declaration is missing or duplicated")
        if ids.count("QG-005") != 1:
            raise ValueError("mandatory QG-005 declaration is missing or duplicated")
        qg003_gate = next(g for g in gates if g["id"] == "QG-003")
        qg005_gate = next(g for g in gates if g["id"] == "QG-005")
        legacy_qg003 = {"id": "QG-003", "name": "traceability-policy", "deterministic": True, "blocks_merge": True}
        legacy_qg005 = {"id": "QG-005", "name": "risk-attestation", "deterministic": True, "blocks_merge": True}
        bootstrap = ref is not None and git(repo, "rev-parse", ref).strip() == QG003_QG005_BOOTSTRAP_BASE

        if bootstrap:
            # Both exact legacy declarations must pass before any normalization occurs.
            if qg003_gate != legacy_qg003:
                raise ValueError("unexpected QG-003 bootstrap declaration")
            if qg005_gate != legacy_qg005:
                raise ValueError("unexpected QG-005 bootstrap declaration")
            policies_doc = yaml.load(read("constitution/policies.yaml"), Loader=GovernanceLoader)
            trace_policy = _parse_legacy_traceability_policy(policies_doc)
            risk_policy = RiskAttestationPolicy(
                "pull_request_body", "checked_markdown_line", "case_insensitive_substring",
                {level: tuple(subs) for level, subs in LEGACY_RISK_ATTESTATION_SUBSTRINGS.items()},
            )
            _validate_risk_applicability_invariant(trace_policy, risk_policy)
            return trace_policy, risk_policy

        if qg003_gate == legacy_qg003 or qg005_gate == legacy_qg005:
            raise ValueError("legacy QG-003/QG-005 declaration shape is supported only at the pinned bootstrap base")

        policies_doc = yaml.load(read("constitution/policies.yaml"), Loader=GovernanceLoader)
        schema003 = json.loads(read(QG003_SCHEMA))
        schema005 = json.loads(read(QG005_SCHEMA))
        Draft202012Validator.check_schema(schema003)
        Draft202012Validator.check_schema(schema005)

        errors = list(Draft202012Validator(schema003).iter_errors(
            {"gate": qg003_gate, "policy": policies_doc.get("traceability")}))
        if errors:
            raise ValueError("QG-003: " + "; ".join(sorted(e.message for e in errors)))
        errors = list(Draft202012Validator(schema005).iter_errors(
            {"gate": qg005_gate, "policy": policies_doc.get("risk_attestation")}))
        if errors:
            raise ValueError("QG-005: " + "; ".join(sorted(e.message for e in errors)))

        trace_raw = policies_doc["traceability"]
        risk_raw = policies_doc["risk_attestation"]
        trace_policy = TracePolicy(
            {level: LevelPolicy(data["description"], dict(data["requires"]))
             for level, data in trace_raw["levels"].items()},
            tuple(trace_raw["escalation_triggers"]),
            tuple(trace_raw["t2_path_triggers"]),
        )
        risk_policy = RiskAttestationPolicy(
            risk_raw["evidence_source"], risk_raw["evidence_format"], risk_raw["match_mode"],
            {level: tuple(data["required_substrings"]) for level, data in risk_raw["levels"].items()},
        )
        _validate_risk_applicability_invariant(trace_policy, risk_policy)
        return trace_policy, risk_policy
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, yaml.YAMLError, SchemaError) as exc:
        raise ValueError(f"traceability/risk-attestation governance ({ref or 'workspace'}): {exc}") from exc


def attestation_satisfied(block: str, required_substrings: tuple[str, ...]) -> bool:
    """QG-005 evidence check: a checked Markdown line containing each required
    substring, matched case-insensitively. Content only; applicability is decided
    solely by traceability.levels[level].requires.risk_attestation."""
    return all(re.search(rf"(?mi)^\s*- \[[xX]\].*{re.escape(s)}", block) for s in required_substrings)


def validate_learning_disposition(repo: Path, node: Any) -> None:
    """FR-012/ADR-014/DEV-020: validate the prospective learning_disposition shape
    (value + non-empty rationale). Deterministic and directly testable; intentionally
    not wired into main()/validate_traceability() against control/project-control.yaml
    — see ADR-014's verification scope boundary. Does not judge substantive correctness
    of the value or rationale."""
    try:
        schema = load_json(repo / LEARNING_DISPOSITION_SCHEMA)
        Draft202012Validator.check_schema(schema)
        errors = list(Draft202012Validator(schema).iter_errors(node))
        if errors:
            raise ValueError("; ".join(sorted(error.message for error in errors)))
    except (OSError, TypeError, json.JSONDecodeError, SchemaError) as exc:
        raise ValueError(f"learning_disposition schema unavailable: {exc}") from exc


def extract_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("missing YAML frontmatter delimited by ---")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a YAML mapping")
    return data


def scan_artifacts(repo: Path, result: ValidationErrorSet) -> dict[str, Artifact]:
    schemas = repo / "knowledge" / "schemas"
    registry: dict[str, Artifact] = {}
    for path in sorted((repo / "design").rglob("*.md")):
        try:
            md = extract_frontmatter(path)
        except Exception as exc:
            result.error(f"{path.relative_to(repo)}: {exc}")
            continue
        artifact_id, kind = md.get("id"), md.get("kind")
        if not isinstance(artifact_id, str) or not isinstance(kind, str):
            result.error(f"{path.relative_to(repo)}: frontmatter requires string id and kind")
            continue
        schema_name = SCHEMA_BY_KIND.get(kind)
        if not schema_name:
            result.error(f"{path.relative_to(repo)}: unsupported kind {kind!r}")
            continue
        validator = Draft202012Validator(load_json(schemas / schema_name))
        for err in sorted(validator.iter_errors(md), key=lambda e: list(e.path)):
            loc = ".".join(map(str, err.path)) or "<root>"
            result.error(f"{path.relative_to(repo)}:{loc}: {err.message}")
        if artifact_id in registry:
            result.error(
                f"duplicate artifact id {artifact_id}: "
                f"{registry[artifact_id].path.relative_to(repo)} and {path.relative_to(repo)}"
            )
        else:
            registry[artifact_id] = Artifact(artifact_id, kind, path, md)
    return registry


def implementation_path_resolves(repo: Path, pattern: str) -> bool:
    """Resolve post-change evidence to a file inside the repository, excluding Git metadata."""
    repo = repo.resolve()
    try:
        candidates = repo.glob(pattern) if any(ch in pattern for ch in "*?[") else [repo / pattern]
        for path in candidates:
            resolved = path.resolve()
            if (resolved.is_relative_to(repo)
                    and ".git" not in resolved.relative_to(repo).parts
                    and path.is_file()):
                return True
    except (OSError, ValueError, NotImplementedError):
        # Invalid/unreadable patterns cannot establish implementation evidence.
        return False
    return False


def validate_traceability(repo: Path, registry: dict[str, Artifact], result: ValidationErrorSet) -> dict[str, Any]:
    try:
        load_implementation_evidence_gate(repo)
    except ValueError as exc:
        result.error(str(exc))
        return {}
    try:
        load_structural_gates(repo)
    except ValueError as exc:
        result.error(str(exc))
        return {}
    try:
        trace_policy, _risk_policy = load_traceability_and_risk_gates(repo)
    except ValueError as exc:
        result.error(str(exc))
        return {}
    trace_path = repo / "knowledge" / "traceability.yaml"
    trace = load_yaml(trace_path)
    validator = Draft202012Validator(load_json(repo / "knowledge/schemas/traceability.schema.json"))
    schema_errors = list(validator.iter_errors(trace))
    for err in sorted(schema_errors, key=lambda e: list(e.path)):
        loc = ".".join(map(str, err.path)) or "<root>"
        result.error(f"knowledge/traceability.yaml:{loc}: {err.message}")
    if schema_errors or not isinstance(trace, dict):
        return trace if isinstance(trace, dict) else {}

    policies_doc = load_yaml(repo / "constitution/policies.yaml")
    try:
        gitignore_lines = {
            line.strip()
            for line in (repo / ".gitignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        if ".sdf/runtime/" not in gitignore_lines:
            result.error(".gitignore: governed telemetry path .sdf/runtime/ must be excluded")
    except OSError as exc:
        result.error(f".gitignore: unable to verify governed telemetry exclusion: {exc}")
    try:
        policy_schema = load_json(repo / AUTONOMOUS_EXECUTION_SCHEMA)
        Draft202012Validator.check_schema(policy_schema)
        policy_errors = list(
            Draft202012Validator(policy_schema).iter_errors(policies_doc.get("autonomous_execution"))
        )
        for err in sorted(policy_errors, key=lambda error: list(error.path)):
            loc = ".".join(map(str, err.path)) or "<root>"
            result.error(f"constitution/policies.yaml:autonomous_execution.{loc}: {err.message}")
        autonomous = policies_doc.get("autonomous_execution")
        if isinstance(autonomous, dict):
            for name in ("max_invocation_seconds", "max_attempts"):
                if type(autonomous.get(name)) is not int or autonomous[name] <= 0:
                    result.error(f"constitution/policies.yaml:autonomous_execution.{name}: positive integer required")
    except (OSError, TypeError, json.JSONDecodeError, SchemaError) as exc:
        result.error(f"constitution/policies.yaml: autonomous execution schema unavailable: {exc}")
    try:
        provenance_exclusions(policies_doc)
    except ValueError as exc:
        result.error(f"constitution/policies.yaml: {exc}")
    tasks = trace.get("tasks", {})
    referenced: set[str] = set(tasks)

    for task_id, node in tasks.items():
        task_art = registry.get(task_id)
        if not task_art:
            result.error(f"{task_id}: task is present in traceability but no task artifact exists")
        elif task_art.kind != "task":
            result.error(f"{task_id}: registry kind must be task, got {task_art.kind}")
        elif task_art.metadata.get("traceability_level") != node.get("level"):
            result.error(
                f"{task_id}: task frontmatter level {task_art.metadata.get('traceability_level')} "
                f"!= traceability level {node.get('level')}"
            )

        level = node.get("level")
        requires = trace_policy.levels[level].requires
        if requires.get("upstream_intent") and not node.get("intent"):
            result.error(f"{task_id} ({level}): requires upstream intent")
        if requires.get("design") and not node.get("design"):
            result.error(f"{task_id} ({level}): requires design evidence")
        if requires.get("decision_or_contract") and not (node.get("decisions") or node.get("contracts")):
            result.error(f"{task_id} ({level}): requires at least one decision or contract")
        if requires.get("verification") and not node.get("verification"):
            result.error(f"{task_id} ({level}): requires verification evidence")
        if requires.get("implementation") and not node.get("implementation", {}).get("paths"):
            result.error(f"{task_id} ({level}): requires implementation.paths")

        for field, prefixes in ALLOWED_PREFIX_BY_FIELD.items():
            for ref in node.get(field, []) or []:
                referenced.add(ref)
                if not ref.startswith(prefixes):
                    result.error(f"{task_id}.{field}: {ref} has invalid relationship type")
                art = registry.get(ref)
                if art is None:
                    result.error(f"{task_id}.{field}: referenced artifact {ref} does not exist")

        current_material_task = (
            level in {"T1", "T2"} and task_art is not None
            and task_art.metadata.get("status") not in {"deprecated", "superseded", "retired"}
        )
        for pattern in node.get("implementation", {}).get("paths", []):
            # Preserve literal-existence checks for every level and lifecycle status.
            if not any(ch in pattern for ch in "*?[") and not (repo / pattern).exists():
                result.error(f"{task_id}.implementation.paths: {pattern} does not exist")
            elif current_material_task and not implementation_path_resolves(repo, pattern):
                result.error(
                    f"{task_id}.implementation.paths: {pattern} does not resolve to an existing repository file"
                )

    # Task artifacts may not exist outside the trace graph.
    for artifact_id, artifact in registry.items():
        if artifact.kind == "task" and artifact_id not in tasks:
            result.error(f"orphan task artifact {artifact_id}: missing from knowledge/traceability.yaml")

    # Intentionally do not force every design artifact to be referenced: proposals/drafts may exist.
    return trace


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def changed_files(repo: Path, base_ref: str, head_ref: str) -> list[str]:
    # NUL framing preserves whitespace; disabling rename detection checks both paths.
    return [x for x in git(repo, "diff", "--name-only", "--no-renames", "-z", f"{base_ref}..{head_ref}").split("\x00") if x]


def commit_messages(repo: Path, base_ref: str, head_ref: str) -> list[str]:
    raw = git(repo, "log", "--format=%B%x00", f"{base_ref}..{head_ref}")
    return [x.strip() for x in raw.split("\x00") if x.strip()]


def reachable_commit_messages(repo: Path, ref: str) -> list[str]:
    raw = git(repo, "log", "--format=%B%x00", ref)
    return [x.strip() for x in raw.split("\x00") if x.strip()]


def parse_pr_declaration(body: str) -> tuple[str | None, str | None]:
    task_m = re.search(r"(?mi)^\s*Traceability Task:\s*(DEV-[0-9]{3,})\s*$", body)
    level_m = re.search(r"(?mi)^\s*Traceability Level:\s*(T[0-2])\s*$", body)
    return (task_m.group(1) if task_m else None, level_m.group(1) if level_m else None)


def parse_pr_declarations(body: str, result: ValidationErrorSet) -> list[tuple[str, str | None, str]]:
    """Each task/level/attestation block ends at the next task declaration."""
    starts = list(re.finditer(r"(?mi)^\s*Traceability Task:[^\r\n]*", body))
    declarations = []
    seen = set()
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        block = body[match.start():end]
        task_id, level = parse_pr_declaration(block)
        if not task_id:
            result.error("PR body: invalid Traceability Task declaration")
            continue
        if task_id in seen:
            result.error(f"PR body: duplicate task declaration {task_id}")
        if len(re.findall(r"(?mi)^\s*Traceability Level:", block)) != 1:
            result.error(f"PR body: {task_id} requires exactly one Traceability Level")
        seen.add(task_id)
        declarations.append((task_id, level, block))
    return declarations


def load_change_provenance_policy(policies: dict[str, Any]) -> ChangeProvenancePolicy:
    """Missing classification is conservative; malformed governance fails closed."""
    if not isinstance(policies, dict):
        raise ValueError("governance must be a mapping")
    config = policies.get("change_provenance", {})
    allowed_fields = {"default", "exempt_paths", "generated_paths", "owner_kinds"}
    if not isinstance(config, dict) or set(config) - allowed_fields:
        raise ValueError(
            "change_provenance must contain only default, exempt_paths, generated_paths, owner_kinds"
        )
    if config.get("default", "required") != "required":
        raise ValueError("change_provenance.default must be required")
    exclusions = []
    for category in ("exempt_paths", "generated_paths"):
        patterns = config.get(category, [])
        if not isinstance(patterns, list) or any(not isinstance(p, str) or not p for p in patterns):
            raise ValueError(f"change_provenance.{category} must be a list of nonempty path patterns")
        exclusions.extend(patterns)
    raw_kinds = config.get("owner_kinds", {})
    if not isinstance(raw_kinds, dict):
        raise ValueError("change_provenance.owner_kinds must be a mapping")
    owner_kinds = {}
    for kind, raw in raw_kinds.items():
        prefix = f"change_provenance.owner_kinds.{kind}"
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("change_provenance.owner_kinds names must be nonempty strings")
        if not isinstance(raw, dict) or set(raw) != {"id_pattern", "allowed_paths"}:
            raise ValueError(f"{prefix} must contain exactly id_pattern and allowed_paths")
        pattern = raw["id_pattern"]
        if not isinstance(pattern, str) or not pattern.strip():
            raise ValueError(f"{prefix}.id_pattern must be a nonempty regex string")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"{prefix}.id_pattern is not a valid regex: {exc}") from exc
        paths = raw["allowed_paths"]
        if (not isinstance(paths, list) or not paths
                or any(not isinstance(path, str) or not path.strip() for path in paths)):
            raise ValueError(f"{prefix}.allowed_paths must be a nonempty list of nonempty path patterns")
        owner_kinds[kind] = ChangeOwnerKind(pattern, tuple(paths))
    return ChangeProvenancePolicy(tuple(exclusions), owner_kinds)


def provenance_exclusions(policies: dict[str, Any]) -> list[str]:
    """Compatibility helper for callers that need only the exclusion patterns."""
    return list(load_change_provenance_policy(policies).exclusions)


def parse_change_owner_declarations(
    body: str,
    owner_kinds: dict[str, ChangeOwnerKind],
    result: ValidationErrorSet,
) -> list[ChangeOwnerDeclaration]:
    owner_starts = list(re.finditer(r"(?mi)^\s*Change Owner:[^\r\n]*", body))
    declaration_starts = sorted(
        owner_starts + list(re.finditer(r"(?mi)^\s*Traceability Task:[^\r\n]*", body)),
        key=lambda match: match.start(),
    )
    blocks = []
    for owner_match in owner_starts:
        later = [match.start() for match in declaration_starts if match.start() > owner_match.start()]
        end = min(later) if later else len(body)
        blocks.append((owner_match.start(), end))

    kind_lines = list(re.finditer(r"(?mi)^\s*Change Owner Kind:[^\r\n]*", body))
    for kind_line in kind_lines:
        if not any(start < kind_line.start() < end for start, end in blocks):
            result.error("PR body: Change Owner Kind declaration is missing Change Owner ID")

    declarations = []
    seen: dict[str, str] = {}
    for owner_match, (start, end) in zip(owner_starts, blocks):
        block = body[start:end]
        owner_id = owner_match.group(0).split(":", 1)[1].strip()
        if not owner_id:
            result.error("PR body: Change Owner declaration is missing owner ID")
            continue
        kinds = re.findall(r"(?mi)^\s*Change Owner Kind:\s*([^\r\n]*)$", block)
        if not kinds or not kinds[0].strip():
            result.error(f"PR body: {owner_id} is missing Change Owner Kind")
            continue
        if len(kinds) != 1:
            result.error(f"PR body: {owner_id} requires exactly one Change Owner Kind")
            continue
        kind = kinds[0].strip()
        if owner_id in seen:
            result.error(f"PR body: duplicate Change Owner ID {owner_id}")
            if seen[owner_id] == kind:
                result.error(f"PR body: duplicate change owner declaration {owner_id} / {kind}")
            continue
        seen[owner_id] = kind
        policy = owner_kinds.get(kind)
        if policy is None:
            result.error(f"PR body: unknown Change Owner Kind {kind!r}")
            continue
        if re.fullmatch(policy.id_pattern, owner_id) is None:
            result.error(
                f"PR body: Change Owner ID {owner_id!r} does not match {kind} id_pattern"
            )
            continue
        declarations.append(ChangeOwnerDeclaration(owner_id, kind))
    return declarations


def path_matches(changed: list[str], patterns: list[str]) -> bool:
    for path in changed:
        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern) or path == pattern:
                return True
    return False


def validate_change_evidence(repo: Path, trace: dict[str, Any], body: str, base_ref: str, head_ref: str, result: ValidationErrorSet) -> None:
    try:
        # Evaluate both independently: proposed weakening cannot remove base obligations.
        evidence_gates = tuple(dict.fromkeys((
            load_implementation_evidence_gate(repo, base_ref),
            load_implementation_evidence_gate(repo),
        )))
        # Evaluate both independently, mirroring evidence_gates above: proposed
        # weakening cannot remove the base binding, and this function remains
        # self-sufficient even when called without validate_traceability first.
        load_structural_gates(repo, base_ref)
        load_structural_gates(repo)
        # QG-003/QG-005: base governance is a lower bound on the surviving proposed
        # evidence; both revisions are loaded and enforced independently below.
        trace_policy_base, risk_policy_base = load_traceability_and_risk_gates(repo, base_ref)
        trace_policy_proposed, risk_policy_proposed = load_traceability_and_risk_gates(repo)
        messages = commit_messages(repo, base_ref, head_ref)
        base_messages = reachable_commit_messages(repo, base_ref)
        files = changed_files(repo, base_ref, head_ref)
        base_policies = yaml.load(
            git(repo, "show", f"{base_ref}:constitution/policies.yaml"), Loader=GovernanceLoader
        )
        if not isinstance(base_policies, dict):
            raise ValueError("base governance must be a mapping")
        base_provenance = load_change_provenance_policy(base_policies)
        exclusions = list(base_provenance.exclusions)
        policies_doc = yaml.load(
            (repo / "constitution/policies.yaml").read_text(encoding="utf-8"),
            Loader=GovernanceLoader,
        )
        load_change_provenance_policy(policies_doc)  # Validate proposed policy; never self-authorize.
        base_trace_doc = yaml.load(
            git(repo, "show", f"{base_ref}:knowledge/traceability.yaml"), Loader=GovernanceLoader
        )
        if not isinstance(base_trace_doc, dict) or not isinstance(base_trace_doc.get("tasks"), dict):
            raise ValueError("base knowledge/traceability.yaml must be a mapping with a tasks mapping")
        base_tasks = base_trace_doc["tasks"]
    except (RuntimeError, ValueError, yaml.YAMLError) as exc:
        result.error(f"git evidence: {exc}")
        return

    # Both base and proposed T2 path triggers remain independently effective: a path
    # matching either revision's set still requires covering T2 task declaration.
    t2_path_triggers = list(trace_policy_base.t2_path_triggers) + list(trace_policy_proposed.t2_path_triggers)
    declarations = parse_pr_declarations(body, result)
    change_owners = parse_change_owner_declarations(body, base_provenance.owner_kinds, result)
    valid_change_owners = []
    for declaration in change_owners:
        marker = f"[{declaration.owner_id}]"
        if not any(marker in message for message in messages):
            result.error(f"git evidence: no PR commit message contains required marker {marker}")
        if any(marker in message for message in base_messages):
            result.error(
                f"git evidence: Change Owner ID {declaration.owner_id} was already used in base history"
            )
        valid_change_owners.append(
            (declaration, base_provenance.owner_kinds[declaration.kind])
        )
    declared_nodes = []
    declared_task_ids = {task_id for task_id, _, _ in declarations}
    for task_id, declared_level, block in declarations:
        node = trace.get("tasks", {}).get(task_id)
        if not node:
            result.error(f"PR body: declared task {task_id} is not present in traceability")
            continue
        declared_nodes.append(node)
        proposed_level = node.get("level")
        if declared_level != proposed_level:
            result.error(f"PR body: declared level {declared_level!r} != {task_id} level {proposed_level!r}")

        base_node = base_tasks.get(task_id)
        if base_node is not None:
            # Existing task: base obligations are recovered from the historical base
            # level and applied to the surviving PROPOSED evidence, never the other
            # way around, so a proposed downgrade cannot erase a base requirement.
            revisions = (("base", base_node.get("level"), trace_policy_base, risk_policy_base),
                         ("proposed", proposed_level, trace_policy_proposed, risk_policy_proposed))
        else:
            # New task: no fictitious historical base level is invented. The task's
            # real proposed level is used as the lookup key in BOTH policy revisions,
            # so a proposed weakening cannot exempt the very task it introduces.
            revisions = (("base", proposed_level, trace_policy_base, risk_policy_base),
                         ("proposed", proposed_level, trace_policy_proposed, risk_policy_proposed))

        for revision, level, tpolicy, rpolicy in revisions:
            level_policy = tpolicy.levels.get(level)
            if level_policy is None:
                continue
            requires = level_policy.requires
            if requires.get("upstream_intent") and not node.get("intent"):
                result.error(f"{task_id} ({revision} {level}): requires upstream intent")
            if requires.get("design") and not node.get("design"):
                result.error(f"{task_id} ({revision} {level}): requires design evidence")
            if requires.get("decision_or_contract") and not (node.get("decisions") or node.get("contracts")):
                result.error(f"{task_id} ({revision} {level}): requires at least one decision or contract")
            if requires.get("verification") and not node.get("verification"):
                result.error(f"{task_id} ({revision} {level}): requires verification evidence")
            if requires.get("implementation") and not node.get("implementation", {}).get("paths"):
                result.error(f"{task_id} ({revision} {level}): requires implementation.paths")
            if requires.get("risk_attestation"):
                required_substrings = rpolicy.levels.get(level, ())
                if not attestation_satisfied(block, required_substrings):
                    result.error(f"PR body: {task_id} {revision} {level} risk attestation is incomplete")

        for gate in evidence_gates:
            if proposed_level not in gate.levels:
                continue
            marker = gate.marker_format.replace("DEV-n", task_id)
            if gate.require_commit_marker and not any(marker in msg for msg in messages):
                result.error(f"git evidence: no PR commit message contains required marker {marker}")
            patterns = node.get("implementation", {}).get("paths", [])
            if gate.require_changed_path_match and not path_matches(files, patterns):
                result.error(
                    f"git evidence: diff does not touch any declared implementation path for {task_id}; "
                    f"declared={patterns}, changed={files}"
                )

    # A base task absent from proposed traceability cannot silently drop its
    # obligations when it remains relevant to this PR (declared, or a changed path
    # matches its base implementation.paths). No successor/lifecycle inference.
    for task_id in sorted(set(base_tasks) - set(trace.get("tasks", {}))):
        base_node = base_tasks[task_id]
        base_patterns = base_node.get("implementation", {}).get("paths", []) if isinstance(base_node, dict) else []
        if task_id in declared_task_ids or path_matches(files, base_patterns):
            result.error(f"{task_id}: base task is relevant to this PR but is absent from proposed traceability")

    for path in files:
        task_owners = [node for node in declared_nodes
                       if path_matches([path], node.get("implementation", {}).get("paths", []))]
        non_task_owners = [declaration for declaration, policy in valid_change_owners
                           if path_matches([path], list(policy.allowed_paths))]
        if path_matches([path], t2_path_triggers):
            if not any(node.get("level") == "T2" for node in task_owners):
                result.error(f"risk classification: {path} hit T2 path triggers but has no declared T2 task coverage")
        elif path_matches([path], exclusions):
            continue
        if not task_owners and not non_task_owners:
            result.error(
                f"git evidence: uncovered changed path {path}; declare a task with matching "
                "implementation.paths or a base-authorized change owner"
            )


def load_pr_body(args: argparse.Namespace) -> str | None:
    if args.pr_body_file:
        return Path(args.pr_body_file).read_text(encoding="utf-8")
    if args.github_event:
        event = json.loads(Path(args.github_event).read_text(encoding="utf-8"))
        return (event.get("pull_request") or {}).get("body") or ""
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base-ref")
    ap.add_argument("--head-ref")
    ap.add_argument("--pr-body-file")
    ap.add_argument("--github-event")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    result = ValidationErrorSet()

    registry = scan_artifacts(repo, result)
    trace = validate_traceability(repo, registry, result)

    body = load_pr_body(args)
    if any([args.base_ref, args.head_ref, body is not None]):
        if not (args.base_ref and args.head_ref and body is not None):
            result.error("change evidence validation requires --base-ref, --head-ref and PR body/event")
        else:
            validate_change_evidence(repo, trace, body, args.base_ref, args.head_ref, result)

    for warning in result.warnings:
        print(f"WARNING: {warning}")
    if result.errors:
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"FAILED: {len(result.errors)} error(s)", file=sys.stderr)
        return 1
    print(f"PASS: {len(registry)} artifacts; deterministic traceability is valid")
    print("PASS: QG-004 canonical configuration is valid" + ("; base/proposed PR evidence passed" if body is not None else ""))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
