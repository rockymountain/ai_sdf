"""ADR-013: the M4 context-effect KPI, kept distinct from delivery accounting.

`cost_baseline.py`'s `input_tokens_per_accepted_dev` / `total_tokens_per_accepted_dev`
remain exact, all-attributable, mixed-provider delivery-accounting totals — every
controlled invocation attributable to an accepted DEV, across every invocation
purpose and runtime adapter, including review, retries, and failed attempts. This
module answers a narrower, separately named question: holding an explicit,
evidence-backed compatibility rule fixed, did a treatment's Claude
implementation/continuation context usage fall by the Owner-approved threshold
against a predeclared baseline cohort?

This module creates no compatibility authority for any real Claude or OpenAI
runtime version, and no real M4 guardrail set. A `CompatibilityRule` and a
`GuardrailContract` are declarations the caller supplies from separately governed,
evidence-backed decisions; without them the result is correctly unavailable.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

from .cost_baseline import BaselineEvidenceError, EvidenceBoundary, SUPPORTED_EVIDENCE_SCHEMA_VERSIONS
from .model import ContextStrategy, InvocationPurpose


CONTEXT_EFFECT_REPORT_SCHEMA_VERSION = 1
CONTEXT_EFFECT_PURPOSES = (InvocationPurpose.implementation.value, InvocationPurpose.continuation.value)
CONTEXT_STRATEGIES = frozenset(value.value for value in ContextStrategy)
EFFECT_GATE_THRESHOLD = Fraction(7, 10)  # Owner-approved >= 70% reduction (ADR-013 / Phase-1 plan gate)

# The M4 direction is chat-heavy -> a declared context treatment, never an
# arbitrary pairing of two context strategies. `graphify-context-pack` and
# `manual-context-pack` are already-governed, named M4 treatments (Phase-1 plan
# §14.1; CMP-003/ADR-012 canonical `context_strategy` vocabulary). `other` has no
# governed declaration establishing what treatment it represents, so it is never
# eligible here; broadening this set requires a separate governed decision.
BASELINE_CONTEXT_STRATEGY = ContextStrategy.chat_heavy.value
TREATMENT_ELIGIBLE_CONTEXT_STRATEGIES = frozenset({
    ContextStrategy.manual_context_pack.value,
    ContextStrategy.graphify_context_pack.value,
})


@dataclass(frozen=True)
class CompatibilityRule:
    """An explicit, evidence-backed rule; never a default or real-version mapping."""

    id: str
    runtime_adapter: str
    covered_observed_models: frozenset[str]
    covered_runtime_versions: frozenset[str]
    token_accounting_semantics: str
    reasoning_conditions: frozenset[str | None]
    model_selection_strategy: str
    routing_policy_version: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise BaselineEvidenceError("compatibility rule id must be explicit")
        if not isinstance(self.runtime_adapter, str) or not self.runtime_adapter.strip():
            raise BaselineEvidenceError("compatibility rule runtime_adapter must be explicit")
        if not self.covered_observed_models or any(
            not isinstance(item, str) or not item.strip() for item in self.covered_observed_models
        ):
            raise BaselineEvidenceError(
                "compatibility rule must cover at least one explicit observed model"
            )
        if not self.covered_runtime_versions or any(
            not isinstance(item, str) or not item.strip() for item in self.covered_runtime_versions
        ):
            raise BaselineEvidenceError(
                "compatibility rule must cover at least one explicit observed runtime version"
            )
        if not isinstance(self.token_accounting_semantics, str) or not self.token_accounting_semantics.strip():
            raise BaselineEvidenceError("compatibility rule requires an explicit token_accounting_semantics tag")
        if not self.reasoning_conditions:
            raise BaselineEvidenceError("compatibility rule must declare at least one allowed reasoning condition")
        if len(self.reasoning_conditions) != 1:
            # For this KPI, reasoning effort is a fixed comparison condition, not
            # a set-membership condition: a rule permitting more than one value
            # cannot pin that condition and is invalid.
            raise BaselineEvidenceError(
                "compatibility rule reasoning_conditions must declare exactly one fixed "
                "reasoning-effort value for the context-effect KPI"
            )
        if self.model_selection_strategy not in {"fixed", "manual", "risk_routed", "other"}:
            raise BaselineEvidenceError("compatibility rule model_selection_strategy must use the canonical vocabulary")
        if self.routing_policy_version is not None and (
            not isinstance(self.routing_policy_version, str) or not self.routing_policy_version.strip()
        ):
            raise BaselineEvidenceError("compatibility rule routing_policy_version must be null or explicit")

    def covers(self, row: Mapping[str, Any]) -> bool:
        """Evaluate retained evidence only; requested_model is never checked here."""
        observed_model = row.get("observed_model")
        runtime_version = row.get("runtime_version")
        return (
            row.get("adapter_name") == self.runtime_adapter
            and isinstance(observed_model, str)
            and observed_model in self.covered_observed_models
            and isinstance(runtime_version, str)
            and runtime_version in self.covered_runtime_versions
            and row.get("requested_reasoning_effort") in self.reasoning_conditions
            and row.get("model_selection_strategy") == self.model_selection_strategy
            and row.get("routing_policy_version") == self.routing_policy_version
        )


@dataclass(frozen=True)
class ContextEffectCohort:
    """A predeclared accepted-DEV observation set for one side of the comparison.

    `context_strategy` is cohort identity, not row metadata: every contributing
    invocation must retain this exact declared value, and a baseline/treatment
    pair sharing the same `context_strategy` cannot represent a context-treatment
    contrast (`context_strategy` is deliberately excluded from `CompatibilityRule`
    for the opposite reason: it is the one thing that is expected to differ).

    `requested_reasoning_effort` is likewise a fixed comparison condition, not a
    set-membership condition: it is required and explicitly supplied even when
    the declared condition is null, so omission never silently becomes null.
    Baseline and treatment must declare the identical value, and every
    contributing invocation in both cohorts must match its own cohort's
    declared value. Inferring equivalence between different reasoning-effort
    values is out of scope and would require a separate, Owner-approved
    comparability decision.
    """

    accepted_dev_tasks: tuple[str, ...]
    evidence_boundary: EvidenceBoundary
    task_eval_mix_id: str
    acceptance_criteria_id: str
    context_strategy: str
    requested_reasoning_effort: str | None

    def __post_init__(self) -> None:
        if not self.accepted_dev_tasks or any(
            not isinstance(task, str) or not task.strip() for task in self.accepted_dev_tasks
        ):
            raise BaselineEvidenceError("context-effect cohort requires a non-empty predeclared DEV list")
        if len(set(self.accepted_dev_tasks)) != len(self.accepted_dev_tasks):
            raise BaselineEvidenceError("context-effect cohort must not repeat a DEV task")
        if not isinstance(self.evidence_boundary, EvidenceBoundary):
            raise BaselineEvidenceError("context-effect cohort requires a machine-readable evidence_boundary")
        self.evidence_boundary.validate()
        for name in ("task_eval_mix_id", "acceptance_criteria_id"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise BaselineEvidenceError(f"context-effect cohort requires an explicit {name}")
        if self.context_strategy not in CONTEXT_STRATEGIES:
            raise BaselineEvidenceError("context-effect cohort context_strategy must use the canonical vocabulary")
        if self.requested_reasoning_effort is not None and (
            not isinstance(self.requested_reasoning_effort, str) or not self.requested_reasoning_effort.strip()
        ):
            raise BaselineEvidenceError(
                "context-effect cohort requested_reasoning_effort must be null or a non-empty capability value"
            )


@dataclass(frozen=True)
class GuardrailContract:
    """A predeclared set of required guardrail-evidence keys; never invented here.

    An absent contract and an empty contract are both authority gaps, not
    permission: neither is sufficient for `treatment_decision_eligible`. Only a
    non-empty declared requirement set, fully satisfied by supplied evidence, is
    sufficient.
    """

    required_evidence_keys: frozenset[str]

    def sufficiency(self, evidence: Mapping[str, Any] | None) -> bool:
        if not self.required_evidence_keys:
            return False
        if evidence is None:
            return False
        return all(key in evidence and evidence[key] is not None for key in self.required_evidence_keys)


@dataclass(frozen=True)
class CohortObservation:
    accepted_dev_count: int
    context_input_token_sum: int | None
    calculable: bool
    reason: str | None
    detail: Mapping[str, Any]

    def report_value(self) -> dict[str, Any]:
        return {
            "accepted_dev_count": self.accepted_dev_count,
            "calculable": self.calculable,
            "reason": self.reason,
            "detail": dict(self.detail),
            "average_context_input_tokens_per_accepted_dev": _average_or_unavailable(
                self.context_input_token_sum, self.accepted_dev_count, self.calculable, self.reason
            ),
        }


def build_context_effect_report(
    database: Path,
    *,
    baseline_cohort: ContextEffectCohort,
    treatment_cohort: ContextEffectCohort,
    compatibility_rule: CompatibilityRule | None,
    guardrail_contract: GuardrailContract | None,
    guardrail_evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build the M4 context-effect report without mutating the evidence database."""
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
            baseline = _evaluate_cohort(connection, baseline_cohort, compatibility_rule)
            treatment = _evaluate_cohort(connection, treatment_cohort, compatibility_rule)
    except sqlite3.Error as exc:
        raise BaselineEvidenceError(f"invalid evidence database: {exc}") from exc

    baseline_strategy_valid = baseline_cohort.context_strategy == BASELINE_CONTEXT_STRATEGY
    treatment_strategy_eligible = treatment_cohort.context_strategy in TREATMENT_ELIGIBLE_CONTEXT_STRATEGIES
    reasoning_consistent = (
        baseline_cohort.requested_reasoning_effort == treatment_cohort.requested_reasoning_effort
    )
    conditions_comparable = (
        compatibility_rule is not None
        and baseline_cohort.task_eval_mix_id == treatment_cohort.task_eval_mix_id
        and baseline_cohort.acceptance_criteria_id == treatment_cohort.acceptance_criteria_id
        # The M4 direction is fixed: an explicit chat-heavy baseline against an
        # explicit, already-governed treatment. A mere inequality between two
        # arbitrary context_strategy values (including a reversed pairing, or
        # an undeclared `other`) is never sufficient.
        and baseline_strategy_valid
        and treatment_strategy_eligible
        # Reasoning effort is a fixed comparison condition: baseline and
        # treatment must declare the identical value (including both null).
        and reasoning_consistent
    )
    calculable = (
        baseline.calculable
        and treatment.calculable
        and conditions_comparable
        and baseline.context_input_token_sum is not None
        and baseline.context_input_token_sum > 0
    )

    if calculable:
        baseline_average = Fraction(baseline.context_input_token_sum, baseline.accepted_dev_count)
        treatment_average = Fraction(treatment.context_input_token_sum, treatment.accepted_dev_count)
        reduction = 1 - (treatment_average / baseline_average)
        gate_passes = (
            10 * treatment.context_input_token_sum * baseline.accepted_dev_count
            <= 3 * baseline.context_input_token_sum * treatment.accepted_dev_count
        )
        reduction_value: dict[str, Any] = {"status": "exact", "exact_ratio": str(reduction)}
        effect_gate_result = "pass" if gate_passes else "fail"
    else:
        reduction_value = {"status": "unavailable", "reason": "effect_metric_not_calculable"}
        effect_gate_result = "unavailable"

    guardrail_declared = guardrail_contract is not None
    guardrail_sufficient = guardrail_declared and guardrail_contract.sufficiency(guardrail_evidence)
    treatment_decision_eligible = calculable and guardrail_sufficient

    return {
        "report_schema_version": CONTEXT_EFFECT_REPORT_SCHEMA_VERSION,
        "baseline": baseline.report_value(),
        "treatment": treatment.report_value(),
        "comparability": {
            "compatibility_rule_declared": compatibility_rule is not None,
            "compatibility_rule_id": compatibility_rule.id if compatibility_rule is not None else None,
            "task_eval_mix_match": baseline_cohort.task_eval_mix_id == treatment_cohort.task_eval_mix_id,
            "acceptance_criteria_match": (
                baseline_cohort.acceptance_criteria_id == treatment_cohort.acceptance_criteria_id
            ),
            "baseline_context_strategy_valid": baseline_strategy_valid,
            "treatment_context_strategy_eligible": treatment_strategy_eligible,
            "baseline_context_strategy": baseline_cohort.context_strategy,
            "treatment_context_strategy": treatment_cohort.context_strategy,
            "reasoning_effort_consistent": reasoning_consistent,
            "baseline_requested_reasoning_effort": baseline_cohort.requested_reasoning_effort,
            "treatment_requested_reasoning_effort": treatment_cohort.requested_reasoning_effort,
        },
        "effect_metric_calculable": calculable,
        "effect_gate_threshold": str(EFFECT_GATE_THRESHOLD),
        "reduction": reduction_value,
        "effect_gate_result": effect_gate_result,
        "guardrail": {
            "contract_declared": guardrail_declared,
            "sufficient": guardrail_sufficient,
        },
        "treatment_decision_eligible": treatment_decision_eligible,
    }


# Priority order used only to select a single primary `reason` string after
# every diagnostic category below has already been collected in full. A
# diagnostic's presence in `detail` never depends on this order; only which one
# is reported as the singular `reason` does.
_REASON_PRIORITY = (
    "declared_task_not_accepted_in_boundary",
    "missing_invocation_coverage",
    "non_terminal_contributing_invocation",
    "boundary_spill_contributing_invocation",
    "context_strategy_mismatch",
    "requested_reasoning_effort_mismatch",
    "no_compatibility_rule_declared",
    "unknown_usage_present",
    "malformed_exact_usage",
    "not_comparable",
)


def _evaluate_cohort(
    connection: sqlite3.Connection,
    cohort: ContextEffectCohort,
    rule: CompatibilityRule | None,
) -> CohortObservation:
    """Scan the full declared cohort and collect every applicable context-effect
    coverage diagnostic before deciding calculability. An eligibility failure in
    one category never truncates collection of the others: one defect must not
    hide another. Every diagnostic list is complete, deterministically ordered
    (sorted), and duplicate-free.
    """
    count = len(cohort.accepted_dev_tasks)
    accepted = _accepted_within_boundary(connection, cohort.accepted_dev_tasks, cohort.evidence_boundary)
    missing_acceptance = sorted(task for task in cohort.accepted_dev_tasks if task not in accepted)

    rows_by_task = _cohort_rows(connection, cohort.accepted_dev_tasks, cohort.evidence_boundary)
    missing_coverage = sorted(task for task in cohort.accepted_dev_tasks if not rows_by_task.get(task))

    all_rows = [row for rows in rows_by_task.values() for row in rows]

    # Terminal/usage validity, reusing the existing EvidenceBoundary semantics:
    # admissible evidence requires started_at in [start, end) (already enforced
    # by the query) AND completed_at IS NOT NULL AND completed_at < end_exclusive
    # -- the same half-open terminal-evidence rule cost_baseline.build_report
    # already uses. A row that started in range but is non-terminal remains
    # visible rather than disappearing from coverage.
    non_terminal = sorted(row["invocation_id"] for row in all_rows if row.get("completed_at") is None)

    # A row that started in range but completed at or after end_exclusive is a
    # boundary spill: terminal, but its terminal evidence falls outside this
    # closed window and must not be borrowed into it. It stays visible in
    # diagnostics rather than being silently dropped or extending the window.
    terminal_rows = [row for row in all_rows if row.get("completed_at") is not None]
    boundary_spill = sorted(
        row["invocation_id"] for row in terminal_rows
        if row["completed_at"] >= cohort.evidence_boundary.end_exclusive
    )

    # Only rows admissible under the boundary (terminal, strictly before
    # end_exclusive) are meaningful candidates for identity/usage diagnostics
    # below; a non-terminal or boundary-spill row is already fully accounted
    # for above and is not re-flagged for its (moot) usage/identity fields.
    admissible_rows = [
        row for row in terminal_rows if row["completed_at"] < cohort.evidence_boundary.end_exclusive
    ]

    # context_strategy is cohort identity: every contributing invocation must
    # retain the exact declared value.
    mismatched_strategy = sorted(
        row["invocation_id"] for row in admissible_rows
        if row.get("context_strategy") != cohort.context_strategy
    )

    # requested_reasoning_effort is likewise a fixed comparison condition, not a
    # set-membership condition: every contributing invocation must retain the
    # cohort's declared value exactly, including when that value is null.
    mismatched_reasoning = sorted(
        row["invocation_id"] for row in admissible_rows
        if row.get("requested_reasoning_effort") != cohort.requested_reasoning_effort
    )

    # Every dimension below is evaluated independently over the SAME
    # admissible_rows set -- never a subset already narrowed by another
    # dimension's result. A row with two unrelated defects (e.g. a
    # context_strategy mismatch AND malformed exact usage) must appear in both
    # diagnostic collections; filtering it out before the second check would
    # let one applicable defect mask the other.

    # Usage validity is evaluated regardless of rule presence -- it is a
    # self-contained property of the row, not of the rule.
    unknown_usage: list[str] = []
    malformed_usage: list[str] = []
    exact_valid_rows: dict[str, dict[str, Any]] = {}
    for row in admissible_rows:
        status = row.get("usage_status")
        if status == "exact":
            if _has_valid_exact_usage(row):
                exact_valid_rows[row["invocation_id"]] = row
            else:
                malformed_usage.append(row["invocation_id"])
        elif status in (None, "unknown"):
            unknown_usage.append(row["invocation_id"])
        else:
            raise BaselineEvidenceError(f"unsupported usage status {status!r}")
    unknown_usage.sort()
    malformed_usage.sort()

    # Compatibility identity (adapter/observed-model/runtime-version/reasoning/
    # model-selection/routing evidence) is independent of usage validity, so it
    # is checked against every admissible row too, not only usage-valid ones.
    incompatible: list[str] = []
    if rule is not None:
        incompatible = sorted(
            row["invocation_id"] for row in admissible_rows if not rule.covers(row)
        )

    # A row contributes tokens only when it has zero applicable defects across
    # every independently evaluated dimension.
    defective_ids = (
        set(mismatched_strategy) | set(mismatched_reasoning)
        | set(unknown_usage) | set(malformed_usage) | set(incompatible)
    )
    total = sum(
        row["input_tokens"]
        for invocation_id, row in exact_valid_rows.items()
        if invocation_id not in defective_ids
    ) if rule is not None else 0

    categories: dict[str, list[str]] = {
        "declared_task_not_accepted_in_boundary": missing_acceptance,
        "missing_invocation_coverage": missing_coverage,
        "non_terminal_contributing_invocation": non_terminal,
        "boundary_spill_contributing_invocation": boundary_spill,
        "context_strategy_mismatch": mismatched_strategy,
        "requested_reasoning_effort_mismatch": mismatched_reasoning,
        "no_compatibility_rule_declared": [] if rule is not None else ["<no rule declared>"],
        "unknown_usage_present": unknown_usage,
        "malformed_exact_usage": malformed_usage,
        "not_comparable": incompatible,
    }
    detail_keys = {
        "declared_task_not_accepted_in_boundary": "missing_acceptance",
        "missing_invocation_coverage": "missing_coverage",
        "non_terminal_contributing_invocation": "non_terminal_invocation_ids",
        "boundary_spill_contributing_invocation": "boundary_spill_invocation_ids",
        "context_strategy_mismatch": "mismatched_context_strategy_invocation_ids",
        "requested_reasoning_effort_mismatch": "mismatched_reasoning_effort_invocation_ids",
        "unknown_usage_present": "unknown_usage_invocation_ids",
        "malformed_exact_usage": "malformed_exact_usage_invocation_ids",
        "not_comparable": "incompatible_invocation_ids",
    }
    detail: dict[str, Any] = {
        detail_keys[category]: items
        for category, items in categories.items()
        if items and category in detail_keys
    }

    calculable = rule is not None and not any(categories.values())
    primary_reason = next((category for category in _REASON_PRIORITY if categories.get(category)), None)
    return CohortObservation(count, total if calculable else None, calculable, primary_reason, detail)


def _has_valid_exact_usage(row: Mapping[str, Any]) -> bool:
    """The same core-usage invariants as `cost_baseline._usage_summary`'s exact
    branch (non-negative integer input/output/total with total = input + output),
    reimplemented locally so `cost_baseline.py` stays unmodified. This is not a
    weaker or competing definition of exact usage.
    """
    input_tokens, output_tokens, total_tokens = (
        row.get("input_tokens"), row.get("output_tokens"), row.get("total_tokens")
    )
    if any(type(value) is not int or value < 0 for value in (input_tokens, output_tokens, total_tokens)):
        return False
    return total_tokens == input_tokens + output_tokens


def _average_or_unavailable(
    sum_value: int | None, count: int, calculable: bool, reason: str | None
) -> dict[str, Any]:
    if calculable and sum_value is not None and count > 0:
        return {
            "status": "exact",
            "numerator": sum_value,
            "denominator": count,
            "exact_ratio": f"{sum_value}/{count}",
        }
    return {"status": "unavailable", "reason": reason, "denominator": count}


def _placeholders(values: tuple[str, ...]) -> str:
    return ",".join("?" for _ in values)


def _accepted_within_boundary(
    connection: sqlite3.Connection, tasks: tuple[str, ...], boundary: EvidenceBoundary
) -> set[str]:
    query = (
        "SELECT dev_task FROM dev_outcomes WHERE dev_task IN (" + _placeholders(tasks) + ") "
        "AND task_accepted=1 AND finalized_at>=? AND finalized_at<?"
    )
    parameters = (*tasks, boundary.start_inclusive, boundary.end_exclusive)
    return {row["dev_task"] for row in connection.execute(query, parameters)}


def _cohort_rows(
    connection: sqlite3.Connection, tasks: tuple[str, ...], boundary: EvidenceBoundary
) -> dict[str, list[dict[str, Any]]]:
    """Every attributable implementation/continuation invocation started within the
    boundary, regardless of terminal state. Unlike `cost_baseline._invocations`
    (which intentionally reports only terminal evidence for delivery accounting
    and is not changed by this module), a non-terminal contributing invocation
    must stay visible here: it makes the context-effect observation set
    incomplete rather than silently disappearing from coverage.
    """
    result: dict[str, list[dict[str, Any]]] = {task: [] for task in tasks}
    query = (
        "SELECT * FROM invocations WHERE dev_task IN (" + _placeholders(tasks) + ") "
        "AND invocation_purpose IN (" + _placeholders(CONTEXT_EFFECT_PURPOSES) + ") "
        "AND started_at>=? AND started_at<? "
        "ORDER BY dev_task, started_at, invocation_id"
    )
    parameters = (*tasks, *CONTEXT_EFFECT_PURPOSES, boundary.start_inclusive, boundary.end_exclusive)
    for row in connection.execute(query, parameters):
        result[row["dev_task"]].append(dict(row))
    return result
