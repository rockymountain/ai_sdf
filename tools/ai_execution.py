#!/usr/bin/env python3
"""Operate and query the governed controlled AI execution runtime."""

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
from ai_execution.execution import BoundedExecutionController  # noqa: E402
from ai_execution.gateway import ControlledInvocationGateway  # noqa: E402
from ai_execution.model import (  # noqa: E402
    CheckpointEvidence,
    ContextStrategy,
    ControlledAIInvocation,
    HumanAuthorization,
    InvocationPurpose,
    ModelSelectionStrategy,
    TerminalStatus,
    UsageStatus,
)
from ai_execution.store import TelemetryStore  # noqa: E402


def store_for(args: argparse.Namespace) -> TelemetryStore:
    """Use governed repository storage unless the CLI explicitly overrides it."""
    return TelemetryStore(args.database) if args.database else TelemetryStore.for_repo(args.repo)


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
    store = store_for(args)
    store.export_jsonl(sys.stdout, dev_task=args.dev_task)
    return 0


def aggregate(args: argparse.Namespace) -> int:
    store_for(args).export_dev_aggregate(sys.stdout, args.dev_task)
    return 0


def finalize_outcome(args: argparse.Namespace) -> int:
    store = store_for(args)
    store.finalize_dev_outcome(args.dev_task, task_accepted=args.task_accepted)
    store.export_dev_aggregate(sys.stdout, args.dev_task)
    return 0


def _routing_policy(value: str) -> str | None:
    return None if value == "none" else value


def _human_authorization(args: argparse.Namespace, *, required: bool) -> HumanAuthorization | None:
    values = (
        args.authorization_actor,
        args.authorization_timestamp,
        args.authorization_reason,
        args.authorization_disposition,
    )
    if not any(value is not None for value in values):
        if required:
            raise ValueError("structured human authorization is required")
        return None
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise ValueError("structured human authorization requires all canonical fields")
    return HumanAuthorization(*values)


def controlled_invocation(args: argparse.Namespace) -> ControlledAIInvocation:
    purpose = InvocationPurpose(args.invocation_purpose)
    authorization = _human_authorization(
        args,
        required=purpose in {
            InvocationPurpose.acceptance_validation,
            InvocationPurpose.review,
            InvocationPurpose.orchestration,
            InvocationPurpose.continuation,
        },
    )
    return ControlledAIInvocation(
        dev_task=args.dev_task,
        traceability_level=args.traceability_level,
        execution_scope_id=args.execution_scope_id,
        objective_id=args.objective_id,
        run_id=args.run_id,
        invocation_id=args.invocation_id,
        source_revision=args.source_revision,
        invocation_purpose=purpose,
        model_selection_strategy=ModelSelectionStrategy(args.model_selection_strategy),
        routing_policy_version=_routing_policy(args.routing_policy_version),
        context_strategy=ContextStrategy(args.context_strategy),
        requested_model=args.requested_model,
        requested_reasoning_effort=args.requested_reasoning_effort,
        reservation_id=args.reservation_id,
        candidate_attempt_number=args.candidate_attempt_number,
        attempt_number=args.attempt_number,
        resume_of_invocation_id=args.resume_of_invocation_id,
        human_authorization=authorization,
    )


def register_scope(args: argparse.Namespace) -> int:
    controller = BoundedExecutionController(args.repo.resolve(), store_for(args))
    controller.create_scope(
        args.execution_scope_id,
        dev_task=args.dev_task,
        objective_id=args.objective_id,
        source_revision=args.source_revision,
    )
    print(json.dumps(controller.snapshot(args.execution_scope_id), indent=2, sort_keys=True))
    return 0


def reserve(args: argparse.Namespace) -> int:
    result = BoundedExecutionController(args.repo.resolve(), store_for(args)).reserve(
        args.execution_scope_id
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def invoke_controlled(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    store = store_for(args)
    invocation = controlled_invocation(args)
    outcome = ControlledInvocationGateway(
        repo, store, CodexRuntimeAdapter(repo=str(repo))
    ).invoke(invocation, args.input)
    report = {
        "invocation_id": invocation.invocation_id,
        "terminal_status": outcome.terminal_status.value,
        "terminal_reason": outcome.terminal_reason.value if outcome.terminal_reason else None,
        "telemetry": store.fetch(invocation.invocation_id),
    }
    if invocation.invocation_purpose in {
        InvocationPurpose.acceptance_validation,
        InvocationPurpose.review,
        InvocationPurpose.orchestration,
    }:
        report["authorization"] = store.nonimplementation_authorization(invocation.invocation_id)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if outcome.terminal_status is TerminalStatus.success else 1


def close_checkpoint(args: argparse.Namespace) -> int:
    controller = BoundedExecutionController(args.repo.resolve(), store_for(args))
    controller.close_attempt(
        args.execution_scope_id,
        args.attempt_number,
        CheckpointEvidence(args.command, args.exit_code, args.evidence_reference),
    )
    print(json.dumps(controller.snapshot(args.execution_scope_id), indent=2, sort_keys=True))
    return 0


def live_proof(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    pre = workspace_snapshot(repo)
    store = store_for(args)
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
        human_authorization=_human_authorization(args, required=True),
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

    aggregate_parser = subparsers.add_parser("aggregate")
    aggregate_parser.add_argument("--repo", type=Path, default=ROOT)
    aggregate_parser.add_argument("--database", type=Path)
    aggregate_parser.add_argument("--dev-task", required=True)
    aggregate_parser.set_defaults(function=aggregate)

    outcome_parser = subparsers.add_parser("finalize-outcome")
    outcome_parser.add_argument("--repo", type=Path, default=ROOT)
    outcome_parser.add_argument("--database", type=Path)
    outcome_parser.add_argument("--dev-task", required=True)
    outcome = outcome_parser.add_mutually_exclusive_group(required=True)
    outcome.add_argument("--accepted", dest="task_accepted", action="store_true")
    outcome.add_argument("--rejected", dest="task_accepted", action="store_false")
    outcome_parser.set_defaults(function=finalize_outcome)

    register_parser = subparsers.add_parser("scope-register")
    _add_store_arguments(register_parser)
    register_parser.add_argument("--dev-task", required=True)
    register_parser.add_argument("--execution-scope-id", required=True)
    register_parser.add_argument("--objective-id", required=True)
    register_parser.add_argument("--source-revision", required=True)
    register_parser.set_defaults(function=register_scope)

    reserve_parser = subparsers.add_parser("reserve")
    _add_store_arguments(reserve_parser)
    reserve_parser.add_argument("--execution-scope-id", required=True)
    reserve_parser.set_defaults(function=reserve)

    invoke_parser = subparsers.add_parser("invoke")
    _add_store_arguments(invoke_parser)
    invoke_parser.add_argument("--dev-task", required=True)
    invoke_parser.add_argument("--traceability-level", choices=("T0", "T1", "T2"), required=True)
    invoke_parser.add_argument("--execution-scope-id", required=True)
    invoke_parser.add_argument("--objective-id")
    invoke_parser.add_argument("--run-id", required=True)
    invoke_parser.add_argument("--invocation-id", required=True)
    invoke_parser.add_argument("--source-revision", required=True)
    invoke_parser.add_argument(
        "--invocation-purpose", choices=tuple(item.value for item in InvocationPurpose), required=True
    )
    invoke_parser.add_argument("--requested-model", required=True)
    invoke_parser.add_argument("--requested-reasoning-effort", required=True)
    invoke_parser.add_argument(
        "--model-selection-strategy",
        choices=tuple(item.value for item in ModelSelectionStrategy),
        required=True,
    )
    invoke_parser.add_argument(
        "--routing-policy-version",
        required=True,
        help="governed version, or the literal 'none' for canonical absence",
    )
    invoke_parser.add_argument(
        "--context-strategy", choices=tuple(item.value for item in ContextStrategy), required=True
    )
    invoke_parser.add_argument("--reservation-id")
    invoke_parser.add_argument("--candidate-attempt-number", type=int)
    invoke_parser.add_argument("--attempt-number", type=int)
    invoke_parser.add_argument("--resume-of-invocation-id")
    _add_authorization_arguments(invoke_parser)
    invoke_parser.add_argument("--input", required=True)
    invoke_parser.set_defaults(function=invoke_controlled)

    checkpoint_parser = subparsers.add_parser("checkpoint-close")
    _add_store_arguments(checkpoint_parser)
    checkpoint_parser.add_argument("--execution-scope-id", required=True)
    checkpoint_parser.add_argument("--attempt-number", type=int, required=True)
    checkpoint_parser.add_argument("--command", required=True)
    checkpoint_parser.add_argument("--exit-code", type=int, required=True)
    checkpoint_parser.add_argument("--evidence-reference", required=True)
    checkpoint_parser.set_defaults(function=close_checkpoint)

    live_parser = subparsers.add_parser("live-proof")
    live_parser.add_argument("--repo", type=Path, default=ROOT)
    live_parser.add_argument("--database", type=Path)
    live_parser.add_argument("--model")
    live_parser.add_argument("--reasoning-effort")
    _add_authorization_arguments(live_parser, required=True)
    live_parser.set_defaults(function=live_proof)
    return result


def _add_store_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--repo", type=Path, default=ROOT)
    command.add_argument("--database", type=Path)


def _add_authorization_arguments(command: argparse.ArgumentParser, *, required: bool = False) -> None:
    command.add_argument("--authorization-actor", required=required)
    command.add_argument("--authorization-timestamp", required=required)
    command.add_argument("--authorization-reason", required=required)
    command.add_argument("--authorization-disposition", required=required)


def main() -> int:
    args = parser().parse_args()
    return args.function(args)


if __name__ == "__main__":
    raise SystemExit(main())
