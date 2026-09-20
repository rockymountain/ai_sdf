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
        policy_schema = load_json(repo / AUTONOMOUS_EXECUTION_SCHEMA)
        Draft202012Validator.check_schema(policy_schema)
        policy_errors = list(
            Draft202012Validator(policy_schema).iter_errors(policies_doc.get("autonomous_execution"))
        )
        for err in sorted(policy_errors, key=lambda error: list(error.path)):
            loc = ".".join(map(str, err.path)) or "<root>"
            result.error(f"constitution/policies.yaml:autonomous_execution.{loc}: {err.message}")
    except (OSError, TypeError, json.JSONDecodeError, SchemaError) as exc:
        result.error(f"constitution/policies.yaml: autonomous execution schema unavailable: {exc}")
    try:
        provenance_exclusions(policies_doc)
    except ValueError as exc:
        result.error(f"constitution/policies.yaml: {exc}")
    policies = policies_doc["traceability"]["levels"]
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
        requires = policies.get(level, {}).get("requires", {})
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


def provenance_exclusions(policies: dict[str, Any]) -> list[str]:
    """Missing classification is conservative; malformed governance fails closed."""
    if not isinstance(policies, dict):
        raise ValueError("governance must be a mapping")
    config = policies.get("change_provenance", {})
    if not isinstance(config, dict) or set(config) - {"default", "exempt_paths", "generated_paths"}:
        raise ValueError("change_provenance must contain only default, exempt_paths, generated_paths")
    if config.get("default", "required") != "required":
        raise ValueError("change_provenance.default must be required")
    exclusions = []
    for category in ("exempt_paths", "generated_paths"):
        patterns = config.get(category, [])
        if not isinstance(patterns, list) or any(not isinstance(p, str) or not p for p in patterns):
            raise ValueError(f"change_provenance.{category} must be a list of nonempty path patterns")
        exclusions.extend(patterns)
    return exclusions


def has_risk_attestation(body: str, level: str) -> bool:
    checked = lambda phrase: bool(re.search(rf"(?mi)^\s*- \[[xX]\].*{re.escape(phrase)}", body))
    if level == "T1":
        phrases = [
            "does **NOT** affect architecture",
            "does **NOT** affect NFRs",
            "does **NOT** affect security",
            "does **NOT** affect persistent data",
            "does **NOT** affect public/external API",
            "does **NOT** create a compliance",
        ]
        return all(checked(p) for p in phrases)
    if level == "T2":
        return checked("material design change")
    return True


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
        messages = commit_messages(repo, base_ref, head_ref)
        files = changed_files(repo, base_ref, head_ref)
        base_policies = yaml.safe_load(git(repo, "show", f"{base_ref}:constitution/policies.yaml"))
        if not isinstance(base_policies, dict):
            raise ValueError("base governance must be a mapping")
        exclusions = provenance_exclusions(base_policies)
        policies_doc = load_yaml(repo / "constitution/policies.yaml")
        provenance_exclusions(policies_doc)  # Validate proposed policy; never self-exempt.
    except (RuntimeError, ValueError, yaml.YAMLError) as exc:
        result.error(f"git evidence: {exc}")
        return

    t2_path_triggers = (
        base_policies.get("traceability", {}).get("t2_path_triggers", [])
        + policies_doc.get("traceability", {}).get("t2_path_triggers", [])
    )
    declarations = parse_pr_declarations(body, result)
    declared_nodes = []
    for task_id, declared_level, block in declarations:
        node = trace.get("tasks", {}).get(task_id)
        if not node:
            result.error(f"PR body: declared task {task_id} is not present in traceability")
            continue
        declared_nodes.append(node)
        actual_level = node.get("level")
        if declared_level != actual_level:
            result.error(f"PR body: declared level {declared_level!r} != {task_id} level {actual_level!r}")
        if actual_level in {"T1", "T2"}:
            if not has_risk_attestation(block, actual_level):
                result.error(f"PR body: {task_id} {actual_level} risk attestation is incomplete")
        for gate in evidence_gates:
            if actual_level not in gate.levels:
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

    for path in files:
        owners = [node for node in declared_nodes
                  if path_matches([path], node.get("implementation", {}).get("paths", []))]
        if path_matches([path], t2_path_triggers):
            if not any(node.get("level") == "T2" for node in owners):
                result.error(f"risk classification: {path} hit T2 path triggers but has no declared T2 task coverage")
        elif path_matches([path], exclusions):
            continue
        if not owners:
            result.error(f"git evidence: uncovered changed path {path}; declare a task with matching implementation.paths")


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
