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

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
TASK_RE = re.compile(r"^DEV-[0-9]{3,}$")
COMMIT_MARKER = lambda task: f"[{task}]"

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


def validate_traceability(repo: Path, registry: dict[str, Artifact], result: ValidationErrorSet) -> dict[str, Any]:
    trace_path = repo / "knowledge" / "traceability.yaml"
    trace = load_yaml(trace_path)
    validator = Draft202012Validator(load_json(repo / "knowledge/schemas/traceability.schema.json"))
    schema_errors = list(validator.iter_errors(trace))
    for err in sorted(schema_errors, key=lambda e: list(e.path)):
        loc = ".".join(map(str, err.path)) or "<root>"
        result.error(f"knowledge/traceability.yaml:{loc}: {err.message}")
    if schema_errors or not isinstance(trace, dict):
        return trace if isinstance(trace, dict) else {}

    policies = load_yaml(repo / "constitution/policies.yaml")["traceability"]["levels"]
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

        for pattern in node.get("implementation", {}).get("paths", []):
            # Declared path must currently resolve unless it is a glob; prevents fictional evidence.
            if not any(ch in pattern for ch in "*?[") and not (repo / pattern).exists():
                result.error(f"{task_id}.implementation.paths: {pattern} does not exist")

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
    return [x for x in git(repo, "diff", "--name-only", f"{base_ref}..{head_ref}").splitlines() if x]


def commit_messages(repo: Path, base_ref: str, head_ref: str) -> list[str]:
    raw = git(repo, "log", "--format=%B%x00", f"{base_ref}..{head_ref}")
    return [x.strip() for x in raw.split("\x00") if x.strip()]


def parse_pr_declaration(body: str) -> tuple[str | None, str | None]:
    task_m = re.search(r"(?mi)^\s*Traceability Task:\s*(DEV-[0-9]{3,})\s*$", body)
    level_m = re.search(r"(?mi)^\s*Traceability Level:\s*(T[0-2])\s*$", body)
    return (task_m.group(1) if task_m else None, level_m.group(1) if level_m else None)


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
    task_id, declared_level = parse_pr_declaration(body)
    if not task_id:
        result.error("PR body: missing machine-readable 'Traceability Task: DEV-nnn'")
        return
    node = trace.get("tasks", {}).get(task_id)
    if not node:
        result.error(f"PR body: declared task {task_id} is not present in traceability")
        return
    actual_level = node.get("level")
    if declared_level != actual_level:
        result.error(f"PR body: declared level {declared_level!r} != {task_id} level {actual_level!r}")
    if actual_level in {"T1", "T2"} and not has_risk_attestation(body, actual_level):
        result.error(f"PR body: {actual_level} risk attestation is incomplete")

    try:
        messages = commit_messages(repo, base_ref, head_ref)
        files = changed_files(repo, base_ref, head_ref)
    except RuntimeError as exc:
        result.error(f"git evidence: {exc}")
        return

    policies_doc = load_yaml(repo / "constitution/policies.yaml")
    t2_path_triggers = policies_doc.get("traceability", {}).get("t2_path_triggers", [])
    if actual_level != "T2":
        triggered = [path for path in files if path_matches([path], t2_path_triggers)]
        if triggered:
            result.error(
                f"risk classification: {task_id} is {actual_level} but changed files hit T2 path triggers: {triggered}"
            )

    if actual_level in {"T1", "T2"}:
        marker = COMMIT_MARKER(task_id)
        if not any(marker in msg for msg in messages):
            result.error(f"git evidence: no PR commit message contains required marker {marker}")
        patterns = node.get("implementation", {}).get("paths", [])
        if not path_matches(files, patterns):
            result.error(
                f"git evidence: diff does not touch any declared implementation path for {task_id}; "
                f"declared={patterns}, changed={files}"
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
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
