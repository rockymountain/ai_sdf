"""Deterministic, read-only M3 cost-baseline measurement and reporting."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import yaml

from .model import ContextStrategy, InvocationPurpose, ModelSelectionStrategy


REPORT_SCHEMA_VERSION = 2
SUPPORTED_EVIDENCE_SCHEMA_VERSIONS = {2, 3}
TRACE_LEVELS = ("T0", "T1", "T2")
TOKEN_FIELDS = ("input_tokens", "output_tokens", "total_tokens")
MODEL_SELECTION_STRATEGIES = tuple(value.value for value in ModelSelectionStrategy)
CONTEXT_STRATEGIES = tuple(value.value for value in ContextStrategy)


class BaselineEvidenceError(ValueError):
    """The declared window or retained evidence is invalid or unsupported."""


@dataclass(frozen=True)
class EvidenceBoundary:
    """Half-open UTC interval applied to immutable terminal evidence."""

    start_inclusive: str
    end_exclusive: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceBoundary":
        if not isinstance(value, Mapping) or set(value) != {"start_inclusive", "end_exclusive"}:
            raise BaselineEvidenceError(
                "evidence_boundary must explicitly declare start_inclusive and end_exclusive"
            )
        boundary = cls(value["start_inclusive"], value["end_exclusive"])
        boundary.validate()
        return boundary

    def validate(self) -> None:
        pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z"
        for name in ("start_inclusive", "end_exclusive"):
            value = getattr(self, name)
            if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
                raise BaselineEvidenceError(f"{name} must be a canonical millisecond UTC timestamp")
        try:
            start = datetime.fromisoformat(self.start_inclusive[:-1] + "+00:00")
            end = datetime.fromisoformat(self.end_exclusive[:-1] + "+00:00")
        except ValueError as exc:
            raise BaselineEvidenceError("evidence_boundary contains an invalid timestamp") from exc
        if start >= end:
            raise BaselineEvidenceError("evidence_boundary start must precede end")


@dataclass(frozen=True)
class PurposeTreatment:
    """One explicit runtime/profile treatment bound to an invocation purpose."""

    runtime_adapter: str
    requested_model: str
    requested_reasoning_effort: str | None
    model_selection_strategy: str
    routing_policy_version: str | None
    context_strategy: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PurposeTreatment":
        required = {
            "runtime_adapter",
            "requested_model",
            "requested_reasoning_effort",
            "model_selection_strategy",
            "routing_policy_version",
            "context_strategy",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise BaselineEvidenceError(
                "each purpose treatment must explicitly declare runtime_adapter and all profile fields"
            )
        treatment = cls(**{name: value[name] for name in required})
        treatment.validate()
        return treatment

    def validate(self) -> None:
        if not isinstance(self.runtime_adapter, str) or not self.runtime_adapter.strip():
            raise BaselineEvidenceError("runtime_adapter must be an explicit non-empty identifier")
        if not isinstance(self.requested_model, str) or not self.requested_model.strip():
            raise BaselineEvidenceError("requested_model must be an explicit non-empty identifier")
        if self.requested_reasoning_effort is not None and (
            not isinstance(self.requested_reasoning_effort, str)
            or not self.requested_reasoning_effort.strip()
        ):
            raise BaselineEvidenceError(
                "requested_reasoning_effort must be null or a non-empty capability value"
            )
        if self.model_selection_strategy not in MODEL_SELECTION_STRATEGIES:
            raise BaselineEvidenceError(
                "model_selection_strategy must use the provider-neutral vocabulary"
            )
        if self.routing_policy_version is not None and (
            not isinstance(self.routing_policy_version, str)
            or not self.routing_policy_version.strip()
        ):
            raise BaselineEvidenceError(
                "routing_policy_version must be null or a non-empty identifier"
            )
        if self.context_strategy not in CONTEXT_STRATEGIES:
            raise BaselineEvidenceError("context_strategy must use the canonical vocabulary")
        if (
            self.model_selection_strategy == "risk_routed"
            and self.routing_policy_version is None
        ):
            raise BaselineEvidenceError(
                "risk-routed model selection requires routing_policy_version"
            )


@dataclass(frozen=True)
class MeasurementWindow:
    """The explicit, fixed control window used by an M3 report."""

    id: str
    included_dev_tasks: tuple[str, ...]
    task_mix: Mapping[str, int]
    trace_level_mix: Mapping[str, int]
    review_policy: str
    acceptance_policy: str
    evidence_boundary: EvidenceBoundary
    purpose_treatments: Mapping[str, PurposeTreatment]
    automatic_model_routing: bool
    context_optimization: bool

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MeasurementWindow":
        try:
            raw_treatments = value["purpose_treatments"]
            if not isinstance(raw_treatments, Mapping):
                raise BaselineEvidenceError("purpose_treatments must be a mapping")
            window = cls(
                id=value["id"],
                included_dev_tasks=tuple(value["included_dev_tasks"]),
                task_mix=dict(value["task_mix"]),
                trace_level_mix=dict(value["trace_level_mix"]),
                review_policy=value["review_policy"],
                acceptance_policy=value["acceptance_policy"],
                evidence_boundary=EvidenceBoundary.from_mapping(value["evidence_boundary"]),
                purpose_treatments={
                    purpose: PurposeTreatment.from_mapping(treatment)
                    for purpose, treatment in raw_treatments.items()
                },
                automatic_model_routing=value["automatic_model_routing"],
                context_optimization=value["context_optimization"],
            )
        except (KeyError, TypeError) as exc:
            raise BaselineEvidenceError(f"invalid measurement window: {exc}") from exc
        window.validate()
        return window

    def validate(self) -> None:
        for name in ("id", "review_policy", "acceptance_policy"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise BaselineEvidenceError(f"{name} must be explicit")
        if not isinstance(self.evidence_boundary, EvidenceBoundary):
            raise BaselineEvidenceError("evidence_boundary must be machine-readable")
        self.evidence_boundary.validate()
        if not self.included_dev_tasks or any(
            not isinstance(task, str) or not task.strip() for task in self.included_dev_tasks
        ):
            raise BaselineEvidenceError("included_dev_tasks must be a non-empty DEV list")
        if len(set(self.included_dev_tasks)) != len(self.included_dev_tasks):
            raise BaselineEvidenceError("included_dev_tasks must not contain duplicates")
        _validate_mix("task_mix", self.task_mix, len(self.included_dev_tasks))
        if set(self.trace_level_mix) != set(TRACE_LEVELS):
            raise BaselineEvidenceError("trace_level_mix must declare T0, T1, and T2")
        _validate_mix("trace_level_mix", self.trace_level_mix, len(self.included_dev_tasks))
        if not isinstance(self.purpose_treatments, Mapping) or not self.purpose_treatments:
            raise BaselineEvidenceError("purpose_treatments must explicitly declare at least one purpose")
        valid_purposes = {purpose.value for purpose in InvocationPurpose}
        if any(purpose not in valid_purposes for purpose in self.purpose_treatments):
            raise BaselineEvidenceError("purpose_treatments contains an unsupported invocation purpose")
        for treatment in self.purpose_treatments.values():
            if not isinstance(treatment, PurposeTreatment):
                raise BaselineEvidenceError("purpose_treatments must contain structured treatments")
            treatment.validate()
        for name in ("automatic_model_routing", "context_optimization"):
            if type(getattr(self, name)) is not bool:
                raise BaselineEvidenceError(f"{name} must be an explicit boolean")
        if (
            self.automatic_model_routing
            and any(
                treatment.routing_policy_version is None
                for treatment in self.purpose_treatments.values()
            )
        ):
            raise BaselineEvidenceError(
                "active or risk-routed model selection requires routing_policy_version"
            )

    def report_value(self) -> dict[str, Any]:
        result = asdict(self)
        result["included_dev_tasks"] = sorted(self.included_dev_tasks)
        result["task_mix"] = dict(sorted(self.task_mix.items()))
        result["trace_level_mix"] = {
            level: self.trace_level_mix[level] for level in TRACE_LEVELS
        }
        result["purpose_treatments"] = {
            purpose: asdict(self.purpose_treatments[purpose])
            for purpose in sorted(self.purpose_treatments)
        }
        return result


def load_trace_levels(path: Path, included_dev_tasks: tuple[str, ...]) -> dict[str, str]:
    """Load only declared DEV trace levels from canonical traceability evidence."""
    with Path(path).open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream)
    tasks = document.get("tasks") if isinstance(document, dict) else None
    if not isinstance(tasks, dict):
        raise BaselineEvidenceError("trace evidence has no tasks mapping")
    result: dict[str, str] = {}
    for dev_task in included_dev_tasks:
        task = tasks.get(dev_task)
        level = task.get("level") if isinstance(task, dict) else None
        if level not in TRACE_LEVELS:
            raise BaselineEvidenceError(f"missing valid trace evidence for {dev_task}")
        result[dev_task] = level
    return result


def build_report(
    database: Path,
    window: MeasurementWindow,
    trace_levels: Mapping[str, str],
) -> dict[str, Any]:
    """Build a report without changing the evidence database or its schema."""
    window.validate()
    levels = _validate_trace_evidence(window, trace_levels)
    database = Path(database).resolve()
    uri = database.as_uri() + "?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise BaselineEvidenceError(f"cannot open evidence database read-only: {exc}") from exc
    connection.row_factory = sqlite3.Row
    try:
        with closing(connection):
            schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if schema_version not in SUPPORTED_EVIDENCE_SCHEMA_VERSIONS:
                raise BaselineEvidenceError(
                    f"unsupported evidence schema version {schema_version}; expected 2 or 3"
                )
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
            }
            required = {"invocations", "dev_outcomes"}
            if not required.issubset(tables):
                raise BaselineEvidenceError("evidence database lacks required M1 tables")
            attempts_available = schema_version >= 3
            if attempts_available and not {
                "attempts", "execution_scopes", "invocation_attempts"
            }.issubset(tables):
                raise BaselineEvidenceError("schema v3 lacks authoritative attempt tables")
            rows = _invocations(
                connection, window.included_dev_tasks, window.evidence_boundary
            )
            outcomes = _outcomes(
                connection, window.included_dev_tasks, window.evidence_boundary
            )
            attempt_reports = (
                _attempt_reports(connection, rows)
                if attempts_available
                else None
            )
    except sqlite3.Error as exc:
        raise BaselineEvidenceError(f"invalid evidence database: {exc}") from exc

    attempt_counts = (
        Counter(report["dev_task"] for report in attempt_reports)
        if attempt_reports is not None
        else None
    )
    dev_reports = [
        _dev_report(
            task,
            levels[task],
            rows.get(task, []),
            outcomes.get(task),
            attempt_counts,
            window,
        )
        for task in sorted(window.included_dev_tasks)
    ]
    aggregate = _rollup(dev_reports, attempts_available)
    by_trace_level = {
        level: _rollup(
            [report for report in dev_reports if report["traceability_level"] == level],
            attempts_available,
        )
        for level in TRACE_LEVELS
    }
    aggregate["metrics"] = _metrics(aggregate)
    for value in by_trace_level.values():
        value["metrics"] = _metrics(value)
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "window": window.report_value(),
        "evidence": {
            "database_schema_version": schema_version,
            "database_open_mode": "read-only",
            "attempt_evidence": "available" if attempts_available else "unavailable_legacy_schema_v2",
            "trace_evidence": "explicit",
        },
        "aggregate": aggregate,
        "by_trace_level": by_trace_level,
        "dev_tasks": dev_reports,
        "attempts": {
            "evidence_status": (
                "available" if attempt_reports is not None else "unavailable_legacy_schema_v2"
            ),
            "records": attempt_reports if attempt_reports is not None else [],
        },
    }


def canonical_json(report: Mapping[str, Any]) -> str:
    """Serialize a report byte-stably without runtime-generated metadata."""
    return json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _validate_mix(name: str, mix: Mapping[str, int], task_count: int) -> None:
    if not isinstance(mix, Mapping) or not mix:
        raise BaselineEvidenceError(f"{name} must be explicit")
    if any(not isinstance(key, str) or not key.strip() for key in mix):
        raise BaselineEvidenceError(f"{name} keys must be non-empty strings")
    if any(type(value) is not int or value < 0 for value in mix.values()):
        raise BaselineEvidenceError(f"{name} counts must be non-negative integers")
    if sum(mix.values()) != task_count:
        raise BaselineEvidenceError(f"{name} counts must equal the declared DEV count")


def _validate_trace_evidence(
    window: MeasurementWindow, trace_levels: Mapping[str, str]
) -> dict[str, str]:
    included = set(window.included_dev_tasks)
    if set(trace_levels) != included:
        raise BaselineEvidenceError("trace evidence must cover exactly the declared DEV set")
    if any(level not in TRACE_LEVELS for level in trace_levels.values()):
        raise BaselineEvidenceError("trace evidence contains an invalid level")
    actual = Counter(trace_levels.values())
    if any(actual[level] != window.trace_level_mix[level] for level in TRACE_LEVELS):
        raise BaselineEvidenceError("trace evidence does not match declared trace_level_mix")
    return dict(trace_levels)


def _placeholders(values: tuple[str, ...]) -> str:
    return ",".join("?" for _ in values)


def _invocations(
    connection: sqlite3.Connection,
    tasks: tuple[str, ...],
    boundary: EvidenceBoundary,
) -> dict[str, list[dict[str, Any]]]:
    result = {task: [] for task in tasks}
    query = (
        "SELECT * FROM invocations WHERE dev_task IN ("
        + _placeholders(tasks)
        + ") AND started_at>=? AND started_at<? "
        "AND completed_at IS NOT NULL AND completed_at<? "
        "ORDER BY dev_task, started_at, invocation_id"
    )
    parameters = (
        *tasks,
        boundary.start_inclusive,
        boundary.end_exclusive,
        boundary.end_exclusive,
    )
    for row in connection.execute(query, parameters):
        result[row["dev_task"]].append(dict(row))
    return result


def _outcomes(
    connection: sqlite3.Connection,
    tasks: tuple[str, ...],
    boundary: EvidenceBoundary,
) -> dict[str, bool]:
    query = (
        "SELECT dev_task, task_accepted FROM dev_outcomes WHERE dev_task IN ("
        + _placeholders(tasks)
        + ") AND finalized_at>=? AND finalized_at<? ORDER BY dev_task"
    )
    parameters = (*tasks, boundary.start_inclusive, boundary.end_exclusive)
    return {
        row["dev_task"]: bool(row["task_accepted"])
        for row in connection.execute(query, parameters)
    }


def _attempt_reports(
    connection: sqlite3.Connection,
    invocation_rows: Mapping[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    included = {
        row["invocation_id"]: row
        for rows in invocation_rows.values()
        for row in rows
    }
    if not included:
        return []
    invocation_ids = tuple(sorted(included))
    query = (
        "SELECT s.dev_task, a.execution_scope_id, a.attempt_number, ia.invocation_id "
        "FROM attempts a JOIN execution_scopes s USING(execution_scope_id) "
        "JOIN invocation_attempts ia ON ia.attempt_number=a.attempt_number "
        "JOIN invocations i ON i.invocation_id=ia.invocation_id "
        "AND i.execution_scope_id=a.execution_scope_id WHERE ia.invocation_id IN ("
        + _placeholders(invocation_ids)
        + ") ORDER BY s.dev_task, a.execution_scope_id, a.attempt_number, ia.invocation_id"
    )
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for row in connection.execute(query, invocation_ids):
        key = (row["dev_task"], row["execution_scope_id"], int(row["attempt_number"]))
        grouped.setdefault(key, []).append(included[row["invocation_id"]])
    result: list[dict[str, Any]] = []
    for (dev_task, scope_id, attempt_number), rows in sorted(grouped.items()):
        result.append(
            {
                "dev_task": dev_task,
                "execution_scope_id": scope_id,
                "attempt_number": attempt_number,
                **_usage_summary(rows),
            }
        )
    return result


def _dev_report(
    task: str,
    level: str,
    rows: list[dict[str, Any]],
    outcome: bool | None,
    attempts: Counter[str] | None,
    window: MeasurementWindow,
) -> dict[str, Any]:
    usage = _usage_summary(rows)
    row_mismatches = [_profile_mismatch_fields(row, window) for row in rows]
    mismatch_fields = [field for fields in row_mismatches for field in fields]
    profile_mismatches = sum(bool(fields) for fields in row_mismatches)
    result: dict[str, Any] = {
        "dev_task": task,
        "traceability_level": level,
        "outcome": "unfinalized" if outcome is None else ("accepted" if outcome else "rejected"),
        **usage,
        "profile_consistency": "consistent" if rows and profile_mismatches == 0 else "incomplete",
        "profile_mismatch_count": profile_mismatches,
        "profile_mismatch_reasons": dict(sorted(Counter(mismatch_fields).items())),
        "invocation_purposes": dict(sorted(Counter(
            row["invocation_purpose"] for row in rows
        ).items())),
        "terminal_statuses": dict(sorted(Counter(
            row["terminal_status"] or "unfinalized" for row in rows
        ).items())),
        "observed_model": {
            "known": sorted({row["observed_model"] for row in rows if row["observed_model"]}),
            "unknown_count": sum(not row["observed_model"] for row in rows),
        },
        "attempt_count": attempts[task] if attempts is not None else None,
        "attempt_evidence": "available" if attempts is not None else "unavailable_legacy_schema_v2",
        "by_invocation_purpose": _usage_breakdown(rows, "invocation_purpose", "runtime_adapters"),
        "by_runtime_adapter": _usage_breakdown(rows, "adapter_name", "invocation_purposes"),
    }
    return result


def _usage_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    exact = []
    unknown = []
    for row in rows:
        status = row.get("usage_status")
        if status == "exact":
            if any(type(row.get(field)) is not int or row[field] < 0 for field in TOKEN_FIELDS):
                raise BaselineEvidenceError(f"malformed exact usage for {row['invocation_id']}")
            if row["total_tokens"] != row["input_tokens"] + row["output_tokens"]:
                raise BaselineEvidenceError(
                    f"inconsistent exact canonical usage for {row['invocation_id']}"
                )
            exact.append(row)
        elif status in (None, "unknown"):
            unknown.append(row)
        else:
            raise BaselineEvidenceError(f"unsupported usage status {status!r}")
    subtotal = {field: sum(row[field] for row in exact) for field in TOKEN_FIELDS}
    complete = bool(rows) and len(exact) == len(rows)
    result: dict[str, Any] = {
        "invocation_count": len(rows),
        "exact_usage_count": len(exact),
        "unknown_usage_count": len(unknown),
        "usage_completeness": "complete" if complete else "incomplete",
        "known_subtotal": subtotal,
    }
    if complete:
        result["exact_total"] = dict(subtotal)
    return result


def _profile_mismatch_fields(
    row: Mapping[str, Any], window: MeasurementWindow
) -> tuple[str, ...]:
    purpose = row.get("invocation_purpose")
    treatment = window.purpose_treatments.get(purpose)
    if treatment is None:
        return ("undeclared_purpose",)
    if not row.get("adapter_name"):
        mismatches = ["runtime_adapter_missing"]
    else:
        mismatches = []
    fields = {
        "runtime_adapter": "adapter_name",
        "requested_model": "requested_model",
        "requested_reasoning_effort": "requested_reasoning_effort",
        "model_selection_strategy": "model_selection_strategy",
        "routing_policy_version": "routing_policy_version",
        "context_strategy": "context_strategy",
    }
    for treatment_field, row_field in fields.items():
        if getattr(treatment, treatment_field) != row.get(row_field):
            mismatches.append(treatment_field)
    return tuple(mismatches)


def _usage_breakdown(
    rows: list[dict[str, Any]], group_field: str, cross_label: str
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = row.get(group_field)
        key = key if isinstance(key, str) and key else "unknown"
        grouped.setdefault(key, []).append(row)
    cross_field = "adapter_name" if group_field == "invocation_purpose" else "invocation_purpose"
    result: dict[str, dict[str, Any]] = {}
    for key, values in sorted(grouped.items()):
        result[key] = {
            **_usage_summary(values),
            cross_label: dict(sorted(Counter(
                row.get(cross_field) or "unknown" for row in values
            ).items())),
        }
    return result


def _rollup(dev_reports: list[dict[str, Any]], attempts_available: bool) -> dict[str, Any]:
    counts = Counter(report["outcome"] for report in dev_reports)
    subtotal = {
        field: sum(report["known_subtotal"][field] for report in dev_reports)
        for field in TOKEN_FIELDS
    }
    usage_complete = bool(dev_reports) and all(
        report["usage_completeness"] == "complete" for report in dev_reports
    )
    profile_consistent = bool(dev_reports) and all(
        report["profile_consistency"] == "consistent" for report in dev_reports
    )
    result: dict[str, Any] = {
        "declared_dev_count": len(dev_reports),
        "devs_with_invocation_evidence": sum(
            report["invocation_count"] > 0 for report in dev_reports
        ),
        "accepted_dev_count": counts["accepted"],
        "rejected_dev_count": counts["rejected"],
        "unfinalized_dev_count": counts["unfinalized"],
        "invocation_count": sum(report["invocation_count"] for report in dev_reports),
        "exact_usage_count": sum(report["exact_usage_count"] for report in dev_reports),
        "unknown_usage_count": sum(report["unknown_usage_count"] for report in dev_reports),
        "usage_completeness": "complete" if usage_complete else "incomplete",
        "known_subtotal": subtotal,
        "profile_consistency": "consistent" if profile_consistent else "incomplete",
        "attempt_evidence": "available" if attempts_available else "unavailable_legacy_schema_v2",
        "attempt_count": (
            sum(report["attempt_count"] for report in dev_reports)
            if attempts_available
            else None
        ),
    }
    if usage_complete:
        result["exact_total"] = dict(subtotal)
    return result


def _metrics(rollup: Mapping[str, Any]) -> dict[str, Any]:
    accepted = rollup["accepted_dev_count"]
    outcomes_complete = rollup["unfinalized_dev_count"] == 0 and rollup["declared_dev_count"] > 0
    invocation_coverage_complete = (
        rollup["devs_with_invocation_evidence"] == rollup["declared_dev_count"]
        and rollup["declared_dev_count"] > 0
    )
    if rollup["attempt_evidence"] != "available":
        attempt_unavailable_reason = "attempt_evidence_unavailable"
        attempt_completeness = rollup["attempt_evidence"]
    elif not invocation_coverage_complete:
        attempt_unavailable_reason = "declared_dev_invocation_coverage_incomplete"
        attempt_completeness = "incomplete"
    elif not outcomes_complete:
        attempt_unavailable_reason = "outcomes_incomplete"
        attempt_completeness = "incomplete"
    else:
        attempt_unavailable_reason = "no_accepted_dev"
        attempt_completeness = "complete"
    metrics: dict[str, Any] = {
        "acceptance_rate": _ratio_or_unavailable(
            rollup["accepted_dev_count"],
            rollup["declared_dev_count"],
            outcomes_complete,
            "outcomes_incomplete",
            completeness_state="complete" if outcomes_complete else "incomplete",
        ),
        "calls_per_accepted_dev": _ratio_or_unavailable(
            rollup["invocation_count"],
            accepted,
            outcomes_complete
            and accepted > 0
            and invocation_coverage_complete,
            "incomplete_invocation_evidence_or_no_accepted_dev",
            completeness_state=(
                "complete"
                if rollup["devs_with_invocation_evidence"] == rollup["declared_dev_count"]
                else "incomplete"
            ),
        ),
        "attempts_per_accepted_dev": _ratio_or_unavailable(
            rollup["attempt_count"],
            accepted,
            outcomes_complete
            and accepted > 0
            and invocation_coverage_complete
            and rollup["attempt_evidence"] == "available",
            attempt_unavailable_reason,
            completeness_state=attempt_completeness,
        ),
    }
    tokens_eligible = (
        outcomes_complete
        and accepted > 0
        and rollup["usage_completeness"] == "complete"
        and rollup["profile_consistency"] == "consistent"
    )
    for field in TOKEN_FIELDS:
        metrics[f"{field}_per_accepted_dev"] = _ratio_or_unavailable(
            rollup["known_subtotal"][field],
            accepted,
            tokens_eligible,
            "usage_or_profile_incomplete_or_no_accepted_dev",
            known_numerator_subtotal=rollup["known_subtotal"][field],
            completeness_state=rollup["usage_completeness"],
        )
    return metrics


def _ratio_or_unavailable(
    numerator: int | None,
    denominator: int,
    eligible: bool,
    reason: str,
    *,
    known_numerator_subtotal: int | None = None,
    completeness_state: str,
) -> dict[str, Any]:
    if eligible and numerator is not None and denominator > 0:
        return {
            "status": "exact",
            "numerator": numerator,
            "denominator": denominator,
            "exact_ratio": f"{numerator}/{denominator}",
        }
    result: dict[str, Any] = {
        "status": "unavailable",
        "reason": reason,
        "denominator": denominator,
        "completeness_state": completeness_state,
    }
    if known_numerator_subtotal is not None:
        result["known_numerator_subtotal"] = known_numerator_subtotal
    return result
