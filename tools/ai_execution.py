#!/usr/bin/env python3
"""Query DEV-007 telemetry or run its one authorized live acceptance proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_execution.codex_adapter import CodexRuntimeAdapter  # noqa: E402
from ai_execution.gateway import ControlledInvocationGateway  # noqa: E402
from ai_execution.model import (  # noqa: E402
    ContextStrategy,
    ControlledAIInvocation,
    InvocationPurpose,
    ModelSelectionStrategy,
    TerminalStatus,
    UsageStatus,
)
from ai_execution.store import TelemetryStore  # noqa: E402


def git(repo: Path, *args: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, check=True, text=not binary
    )
    return result.stdout


def workspace_snapshot(repo: Path) -> dict[str, object]:
    status = git(
        repo,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--no-renames",
        binary=True,
    )
    assert isinstance(status, bytes)
    paths: list[str] = []
    hashes: dict[str, str] = {}
    records = [record for record in status.split(b"\0") if record]
    for record in records:
        path = record[3:].decode("utf-8", errors="surrogateescape")
        paths.append(path)
        target = repo / path
        if target.is_file():
            hashes[path] = hashlib.sha256(target.read_bytes()).hexdigest()
    # Avoid host-configured text converters: they are outside the governed
    # workspace and can fail independently (for example Windows astextplain).
    worktree_diff = git(repo, "diff", "--no-ext-diff", "--no-textconv", "--binary", binary=True)
    index_diff = git(
        repo,
        "diff",
        "--cached",
        "--no-ext-diff",
        "--no-textconv",
        "--binary",
        binary=True,
    )
    assert isinstance(worktree_diff, bytes) and isinstance(index_diff, bytes)
    return {
        "head": str(git(repo, "rev-parse", "HEAD")).strip(),
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "worktree_diff_sha256": hashlib.sha256(worktree_diff).hexdigest(),
        "index_diff_sha256": hashlib.sha256(index_diff).hexdigest(),
        "changed_paths": paths,
        "changed_file_sha256": hashes,
    }


def export(args: argparse.Namespace) -> int:
    store = TelemetryStore(args.database or (args.repo / ".sdf/runtime/ai-execution.sqlite3"))
    store.export_jsonl(sys.stdout, dev_task=args.dev_task)
    return 0


def live_proof(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    pre = workspace_snapshot(repo)
    store = TelemetryStore(args.database or (repo / ".sdf/runtime/ai-execution.sqlite3"))
    invocation_id = str(uuid.uuid4())
    invocation = ControlledAIInvocation(
        dev_task="DEV-007",
        traceability_level="T2",
        execution_scope_id=f"DEV-007-acceptance-{uuid.uuid4()}",
        run_id=str(uuid.uuid4()),
        invocation_id=invocation_id,
        source_revision=str(git(repo, "rev-parse", "HEAD")).strip(),
        invocation_purpose=InvocationPurpose.acceptance_validation,
        model_selection_strategy=ModelSelectionStrategy.manual,
        context_strategy=ContextStrategy.chat_heavy,
        requested_model=args.model,
        requested_reasoning_effort=args.reasoning_effort,
    )
    adapter = CodexRuntimeAdapter(repo=str(repo))
    gateway = ControlledInvocationGateway(repo, store, adapter)
    prompt = (
        "This is a read-only acceptance validation. Use the shell tool exactly as needed to run "
        "`git rev-parse HEAD` in the current repository, report the resulting SHA, and do not "
        "create, edit, delete, stage, restore, commit, or otherwise mutate any file or Git state."
    )
    failure: str | None = None
    outcome = None
    try:
        outcome = gateway.invoke(invocation, prompt)
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
    post = workspace_snapshot(repo)
    row = store.fetch(invocation_id)
    unchanged = pre == post
    accepted = bool(
        outcome is not None
        and outcome.terminal_status is TerminalStatus.success
        and outcome.usage.usage_status is UsageStatus.exact
        and outcome.tool_item_count > 0
        and row is not None
        and row["cumulative_usage_status"] == UsageStatus.exact.value
        and unchanged
    )
    report = {
        "accepted": accepted,
        "failure": failure,
        "invocation_id": invocation_id,
        "pre_workspace": pre,
        "post_workspace": post,
        "workspace_unchanged": unchanged,
        "telemetry": row,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if accepted else 1


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    subparsers = result.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--repo", type=Path, default=ROOT)
    export_parser.add_argument("--database", type=Path)
    export_parser.add_argument("--dev-task")
    export_parser.set_defaults(function=export)

    live_parser = subparsers.add_parser("live-proof")
    live_parser.add_argument("--repo", type=Path, default=ROOT)
    live_parser.add_argument("--database", type=Path)
    live_parser.add_argument("--model")
    live_parser.add_argument("--reasoning-effort")
    live_parser.set_defaults(function=live_proof)
    return result


def main() -> int:
    args = parser().parse_args()
    return args.function(args)


if __name__ == "__main__":
    raise SystemExit(main())
