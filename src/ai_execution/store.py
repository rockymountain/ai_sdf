"""SQLite operational evidence store for controlled AI invocations."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, TextIO

from .model import ControlledAIInvocation, TerminalReason, TerminalStatus, UsageEvidence
from .runtime import CapabilityProfile, RuntimeSnapshot


SCHEMA_VERSION = 2
DEFAULT_RELATIVE_PATH = Path(".sdf/runtime/ai-execution.sqlite3")


class TelemetryStore:
    """Durable observations only; this database is never policy authority."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._initialize()

    @classmethod
    def for_repo(cls, repo: Path) -> "TelemetryStore":
        repo = Path(repo).resolve()
        path = (repo / DEFAULT_RELATIVE_PATH).resolve()
        runtime_root = (repo / DEFAULT_RELATIVE_PATH.parent).resolve()
        if path.parent != runtime_root or not path.is_relative_to(repo):
            raise RuntimeError("governed telemetry path resolves outside the repository")
        return cls(path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, SCHEMA_VERSION):
                raise RuntimeError(
                    f"unsupported telemetry schema version {version}; expected 1 or {SCHEMA_VERSION}"
                )
            if version == 0:
                connection.executescript(
                    """
                    CREATE TABLE invocations (
                        invocation_id TEXT PRIMARY KEY,
                        dev_task TEXT NOT NULL,
                        traceability_level TEXT NOT NULL,
                        execution_scope_id TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        source_revision TEXT NOT NULL,
                        invocation_purpose TEXT NOT NULL,
                        capability_profile TEXT NOT NULL,
                        watchdog_seconds INTEGER NOT NULL CHECK (watchdog_seconds > 0),
                        model_selection_strategy TEXT NOT NULL,
                        routing_policy_version TEXT,
                        context_strategy TEXT NOT NULL,
                        requested_model TEXT,
                        requested_reasoning_effort TEXT,
                        observed_model TEXT,
                        adapter_name TEXT NOT NULL,
                        adapter_version TEXT NOT NULL,
                        runtime_name TEXT,
                        runtime_version TEXT,
                        runtime_session_id TEXT,
                        runtime_invocation_id TEXT,
                        runtime_native_metadata TEXT,
                        started_at TEXT NOT NULL,
                        completed_at TEXT,
                        terminal_status TEXT,
                        terminal_reason TEXT,
                        human_attention_required INTEGER NOT NULL DEFAULT 0,
                        autonomous_follow_on_allowed INTEGER NOT NULL DEFAULT 0,
                        usage_status TEXT,
                        input_tokens INTEGER,
                        output_tokens INTEGER,
                        total_tokens INTEGER,
                        cached_input_tokens INTEGER,
                        reasoning_output_tokens INTEGER,
                        cumulative_usage_status TEXT,
                        cumulative_input_tokens INTEGER,
                        cumulative_output_tokens INTEGER,
                        cumulative_total_tokens INTEGER,
                        cumulative_cached_input_tokens INTEGER,
                        cumulative_reasoning_output_tokens INTEGER,
                        tool_item_count INTEGER NOT NULL DEFAULT 0,
                        error_reference TEXT
                    );
                    CREATE INDEX invocations_by_dev
                        ON invocations(dev_task, started_at, invocation_id);
                    CREATE INDEX invocations_by_scope
                        ON invocations(execution_scope_id, started_at, invocation_id);
                    PRAGMA user_version = 1;
                    """
                )
                version = 1
            if version == 1:
                connection.executescript(
                    """
                    CREATE TABLE dev_outcomes (
                        dev_task TEXT PRIMARY KEY,
                        task_accepted INTEGER NOT NULL CHECK (task_accepted IN (0, 1)),
                        finalized_at TEXT NOT NULL
                    );
                    PRAGMA user_version = 2;
                    """
                )
        self._verify_access()

    def _verify_access(self) -> None:
        """Prove inherited workspace access supports DB read and write transactions."""
        with closing(self._connect()) as connection:
            connection.execute("SELECT COUNT(*) FROM invocations").fetchone()
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE dev_outcomes SET finalized_at = finalized_at WHERE 0"
            )
            connection.rollback()

    def record_start(
        self,
        invocation: ControlledAIInvocation,
        capability: CapabilityProfile,
        watchdog_seconds: int,
        *,
        adapter_name: str,
        adapter_version: str,
    ) -> str:
        started_at = _now()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO invocations (
                    invocation_id, dev_task, traceability_level, execution_scope_id,
                    run_id, source_revision, invocation_purpose, capability_profile,
                    watchdog_seconds, model_selection_strategy, routing_policy_version,
                    context_strategy, requested_model, requested_reasoning_effort,
                    adapter_name, adapter_version, started_at,
                    autonomous_follow_on_allowed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invocation.invocation_id,
                    invocation.dev_task,
                    invocation.traceability_level,
                    invocation.execution_scope_id,
                    invocation.run_id,
                    invocation.source_revision,
                    invocation.invocation_purpose.value,
                    capability.name,
                    watchdog_seconds,
                    invocation.model_selection_strategy.value,
                    invocation.routing_policy_version,
                    invocation.context_strategy.value,
                    invocation.requested_model,
                    invocation.requested_reasoning_effort,
                    adapter_name,
                    adapter_version,
                    started_at,
                    0,
                ),
            )
        return started_at

    def record_runtime_identity(
        self,
        invocation_id: str,
        *,
        runtime_name: str | None,
        runtime_version: str | None,
        snapshot: RuntimeSnapshot,
    ) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                UPDATE invocations
                   SET runtime_name = ?, runtime_version = ?, runtime_session_id = ?,
                       runtime_invocation_id = ?
                 WHERE invocation_id = ?
                """,
                (
                    runtime_name,
                    runtime_version,
                    snapshot.runtime_session_id,
                    snapshot.runtime_invocation_id,
                    invocation_id,
                ),
            )

    def record_terminal(
        self,
        invocation_id: str,
        *,
        status: TerminalStatus,
        reason: TerminalReason | None,
        snapshot: RuntimeSnapshot,
        human_attention_required: bool,
        autonomous_follow_on_allowed: bool,
        error_reference: str | None = None,
    ) -> None:
        usage = _usage_columns(snapshot.usage)
        cumulative = _usage_columns(snapshot.cumulative_usage, prefix="cumulative_")
        native = (
            json.dumps(snapshot.runtime_native_metadata, sort_keys=True, separators=(",", ":"))
            if snapshot.runtime_native_metadata is not None
            else None
        )
        values = {
            "completed_at": _now(),
            "terminal_status": status.value,
            "terminal_reason": reason.value if reason is not None else None,
            "human_attention_required": int(human_attention_required),
            "autonomous_follow_on_allowed": int(autonomous_follow_on_allowed),
            "runtime_session_id": snapshot.runtime_session_id,
            "runtime_invocation_id": snapshot.runtime_invocation_id,
            "observed_model": snapshot.observed_model,
            "runtime_native_metadata": native,
            "tool_item_count": snapshot.tool_item_count,
            "error_reference": error_reference,
            **usage,
            **cumulative,
        }
        assignments = ", ".join(f"{name} = ?" for name in values)
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                f"UPDATE invocations SET {assignments} WHERE invocation_id = ?",
                (*values.values(), invocation_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown invocation_id {invocation_id}")

    def fetch(self, invocation_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT * FROM invocations WHERE invocation_id = ?", (invocation_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    def rows(self, *, dev_task: str | None = None) -> Iterable[dict[str, Any]]:
        sql = "SELECT * FROM invocations"
        params: tuple[str, ...] = ()
        if dev_task is not None:
            sql += " WHERE dev_task = ?"
            params = (dev_task,)
        sql += " ORDER BY started_at, invocation_id"
        with closing(self._connect()) as connection, connection:
            rows = [dict(row) for row in connection.execute(sql, params)]
        for row in rows:
            if row["runtime_native_metadata"] is not None:
                row["runtime_native_metadata"] = json.loads(row["runtime_native_metadata"])
            yield row

    def export_jsonl(self, output: TextIO, *, dev_task: str | None = None) -> int:
        count = 0
        for row in self.rows(dev_task=dev_task):
            output.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            count += 1
        return count

    def finalize_dev_outcome(self, dev_task: str, *, task_accepted: bool) -> str:
        """Record an immutable final DEV outcome; no row means not finalized."""
        if not isinstance(dev_task, str) or not dev_task.strip():
            raise ValueError("dev_task is required")
        if type(task_accepted) is not bool:
            raise TypeError("task_accepted must be true or false")
        finalized_at = _now()
        with closing(self._connect()) as connection, connection:
            if connection.execute(
                "SELECT 1 FROM invocations WHERE dev_task = ? LIMIT 1", (dev_task,)
            ).fetchone() is None:
                raise KeyError(f"no invocation evidence for {dev_task}")
            try:
                connection.execute(
                    "INSERT INTO dev_outcomes (dev_task, task_accepted, finalized_at) "
                    "VALUES (?, ?, ?)",
                    (dev_task, int(task_accepted), finalized_at),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"outcome already finalized for {dev_task}") from exc
        return finalized_at

    def dev_aggregate(self, dev_task: str) -> dict[str, Any]:
        """Rebuild DEV usage and outcome from every retained invocation row."""
        with closing(self._connect()) as connection, connection:
            usage = connection.execute(
                """
                SELECT
                    COUNT(*) AS invocation_count,
                    COALESCE(SUM(CASE WHEN usage_status = 'exact' THEN 1 ELSE 0 END), 0)
                        AS exact_usage_count,
                    COALESCE(SUM(CASE WHEN usage_status = 'exact' THEN input_tokens ELSE 0 END), 0)
                        AS input_tokens,
                    COALESCE(SUM(CASE WHEN usage_status = 'exact' THEN output_tokens ELSE 0 END), 0)
                        AS output_tokens,
                    COALESCE(SUM(CASE WHEN usage_status = 'exact' THEN total_tokens ELSE 0 END), 0)
                        AS total_tokens
                FROM invocations
                WHERE dev_task = ?
                """,
                (dev_task,),
            ).fetchone()
            outcome = connection.execute(
                "SELECT task_accepted, finalized_at FROM dev_outcomes WHERE dev_task = ?",
                (dev_task,),
            ).fetchone()
        invocation_count = int(usage["invocation_count"])
        exact_count = int(usage["exact_usage_count"])
        subtotal = {
            "input_tokens": int(usage["input_tokens"]),
            "output_tokens": int(usage["output_tokens"]),
            "total_tokens": int(usage["total_tokens"]),
        }
        complete = invocation_count > 0 and exact_count == invocation_count
        result: dict[str, Any] = {
            "dev_task": dev_task,
            "invocation_count": invocation_count,
            "exact_usage_count": exact_count,
            "usage_completeness": "complete" if complete else "incomplete",
            "known_subtotal": subtotal,
            "outcome_finalized": outcome is not None,
        }
        if complete:
            result["exact_total"] = dict(subtotal)
        if outcome is not None:
            result["task_accepted"] = bool(outcome["task_accepted"])
            result["outcome_finalized_at"] = outcome["finalized_at"]
        return result

    def export_dev_aggregate(self, output: TextIO, dev_task: str) -> None:
        output.write(
            json.dumps(self.dev_aggregate(dev_task), sort_keys=True, separators=(",", ":"))
            + "\n"
        )


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _usage_columns(
    usage: UsageEvidence | None, *, prefix: str = ""
) -> dict[str, int | str | None]:
    names = (
        "usage_status",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "reasoning_output_tokens",
    )
    if usage is None:
        return {prefix + name: None for name in names}
    data = asdict(usage)
    data["usage_status"] = usage.usage_status.value
    return {prefix + name: data[name] for name in names}
