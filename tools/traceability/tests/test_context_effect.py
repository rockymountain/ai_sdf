"""TEST-019: the M4 context-effect KPI, kept distinct from delivery accounting.

Every test uses a temporary, hand-built SQLite fixture database and synthetic,
clearly fixture-only identifiers (never a real Claude/OpenAI model or version
string). No governed runtime operator, live provider call, reservation, or
attempt is used anywhere in this file.
"""

from __future__ import annotations

import inspect
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ai_execution import cost_baseline
from ai_execution.context_effect import (
    CONTEXT_EFFECT_REPORT_SCHEMA_VERSION,
    CompatibilityRule,
    ContextEffectCohort,
    GuardrailContract,
    build_context_effect_report,
)
from ai_execution.cost_baseline import BaselineEvidenceError, EvidenceBoundary
from ai_execution.runtime import AIRuntimePort


SCHEMA = """
CREATE TABLE invocations (
    invocation_id TEXT PRIMARY KEY, dev_task TEXT NOT NULL,
    execution_scope_id TEXT NOT NULL, started_at TEXT NOT NULL,
    completed_at TEXT, invocation_purpose TEXT NOT NULL,
    adapter_name TEXT, terminal_status TEXT, usage_status TEXT,
    input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER,
    requested_model TEXT, requested_reasoning_effort TEXT,
    model_selection_strategy TEXT NOT NULL, routing_policy_version TEXT,
    context_strategy TEXT NOT NULL, observed_model TEXT, runtime_version TEXT
);
CREATE TABLE dev_outcomes (
    dev_task TEXT PRIMARY KEY, task_accepted INTEGER NOT NULL,
    finalized_at TEXT NOT NULL
);
CREATE TABLE execution_scopes (execution_scope_id TEXT PRIMARY KEY, dev_task TEXT NOT NULL);
CREATE TABLE attempts (
    execution_scope_id TEXT NOT NULL, attempt_number INTEGER NOT NULL,
    state TEXT NOT NULL, PRIMARY KEY (execution_scope_id, attempt_number)
);
CREATE TABLE invocation_attempts (invocation_id TEXT PRIMARY KEY, attempt_number INTEGER);
PRAGMA user_version=3;
"""

BOUNDARY = EvidenceBoundary("2026-09-24T00:00:00.000Z", "2026-09-25T00:00:00.000Z")

ROW_DEFAULTS = {
    "execution_scope_id": "scope-19",
    "started_at": "2026-09-24T01:00:00.000Z",
    "completed_at": "2026-09-24T01:05:00.000Z",
    "invocation_purpose": "implementation",
    "adapter_name": "claude",
    "terminal_status": "success",
    "usage_status": "exact",
    "input_tokens": 100,
    "output_tokens": 10,
    "total_tokens": 110,
    "requested_model": "declared-fixture-model",
    "requested_reasoning_effort": None,
    "model_selection_strategy": "fixed",
    "routing_policy_version": None,
    "context_strategy": "chat-heavy",
    "observed_model": "fixture-claude-observed-model",
    "runtime_version": "fixture-runtime-9.9.9-test",
}

# A clearly synthetic, fixture-only compatibility rule. No real Claude or OpenAI
# model/version string is used anywhere in this file, matching TEST-018's
# no-hardcoded-real-version discipline.
RULE = CompatibilityRule(
    id="synthetic-fixture-rule-v1",
    runtime_adapter="claude",
    covered_observed_models=frozenset({"fixture-claude-observed-model"}),
    covered_runtime_versions=frozenset({"fixture-runtime-9.9.9-test"}),
    token_accounting_semantics="fixture-claude-cache-read-input-plus-base",
    reasoning_conditions=frozenset({None}),
    model_selection_strategy="fixed",
    routing_policy_version=None,
)


class Fixture:
    """A small, self-contained SQLite evidence database for one test."""

    def __init__(self, path: Path):
        self.path = path
        connection = sqlite3.connect(path)
        connection.executescript(SCHEMA)
        connection.commit()
        connection.close()
        self._counter = 0

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def accept(self, dev_task: str, *, finalized_at: str = "2026-09-24T01:10:00.000Z") -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO dev_outcomes VALUES (?,?,?)", (dev_task, 1, finalized_at)
            )

    def reject(self, dev_task: str, *, finalized_at: str = "2026-09-24T01:10:00.000Z") -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO dev_outcomes VALUES (?,?,?)", (dev_task, 0, finalized_at)
            )

    def row(self, dev_task: str, **overrides) -> str:
        self._counter += 1
        invocation_id = overrides.pop("invocation_id", f"inv-{dev_task}-{self._counter}")
        fields = {**ROW_DEFAULTS, **overrides, "dev_task": dev_task}
        # Keep exact rows self-consistent by default (total = input + output) so
        # tests that only vary input_tokens don't accidentally become malformed;
        # a test that wants an inconsistent/malformed row overrides total_tokens
        # (or output_tokens) explicitly, which disables this auto-compute.
        if (
            "total_tokens" not in overrides
            and fields.get("usage_status") == "exact"
            and isinstance(fields.get("input_tokens"), int)
            and isinstance(fields.get("output_tokens"), int)
        ):
            fields["total_tokens"] = fields["input_tokens"] + fields["output_tokens"]
        columns = ["invocation_id", "dev_task", *fields.keys()]
        columns = list(dict.fromkeys(columns))  # dev_task appears once, order preserved
        values = [invocation_id] + [fields.get(name) for name in columns[1:]]
        placeholders = ",".join("?" for _ in columns)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                f"INSERT INTO invocations ({','.join(columns)}) VALUES ({placeholders})",
                values,
            )
        return invocation_id


class ContextEffectTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = Fixture(Path(self.temporary.name) / "evidence.sqlite3")

    def cohort(
        self, tasks, *, context_strategy, mix="cohort", criteria="criteria",
        requested_reasoning_effort=None,
    ):
        return ContextEffectCohort(
            accepted_dev_tasks=tuple(tasks),
            evidence_boundary=BOUNDARY,
            task_eval_mix_id=mix,
            acceptance_criteria_id=criteria,
            context_strategy=context_strategy,
            requested_reasoning_effort=requested_reasoning_effort,
        )


class DeliveryAccountingUnaffectedTests(ContextEffectTestCase):
    """Requirements 1, 2, 18, 20."""

    def test_delivery_accounting_stays_all_attributable_and_mixed_total_is_not_a_comparison_scalar(self):
        self.fixture.accept("DEV-100")
        self.fixture.row(
            "DEV-100", invocation_purpose="implementation", adapter_name="claude",
            requested_model="declared-fixture-model", input_tokens=50, output_tokens=5, total_tokens=55,
        )
        self.fixture.row(
            "DEV-100", invocation_purpose="review", adapter_name="codex",
            requested_model="declared-review-model", input_tokens=20, output_tokens=2, total_tokens=22,
        )
        self.fixture.reject("DEV-101")
        self.fixture.row("DEV-101", invocation_purpose="implementation")

        window = cost_baseline.MeasurementWindow.from_mapping({
            "id": "fixture-window",
            "included_dev_tasks": ["DEV-100", "DEV-101"],
            "task_mix": {"implementation": 2},
            "trace_level_mix": {"T0": 0, "T1": 0, "T2": 2},
            "review_policy": "all review usage retained",
            "acceptance_policy": "governed outcome",
            "evidence_boundary": {
                "start_inclusive": BOUNDARY.start_inclusive, "end_exclusive": BOUNDARY.end_exclusive,
            },
            "purpose_treatments": {
                "implementation": {
                    "runtime_adapter": "claude", "requested_model": "declared-fixture-model",
                    "requested_reasoning_effort": None, "model_selection_strategy": "fixed",
                    "routing_policy_version": None, "context_strategy": "chat-heavy",
                },
                "review": {
                    "runtime_adapter": "codex", "requested_model": "declared-review-model",
                    "requested_reasoning_effort": None, "model_selection_strategy": "fixed",
                    "routing_policy_version": None, "context_strategy": "chat-heavy",
                },
            },
            "automatic_model_routing": False,
            "context_optimization": False,
        })
        report = cost_baseline.build_report(
            self.fixture.path, window, {"DEV-100": "T2", "DEV-101": "T2"}
        )
        dev100 = next(d for d in report["dev_tasks"] if d["dev_task"] == "DEV-100")
        # Req 1/2: the mixed-provider total sums implementation + review exactly.
        self.assertEqual(77, dev100["exact_total"]["total_tokens"])
        self.assertEqual(70, dev100["exact_total"]["input_tokens"])
        # Nothing in the report shape claims this is a provider-independent
        # comparison scalar; it is accounting/reconciliation evidence only.
        self.assertNotIn("comparable", dev100)
        # Req 18: a rejected DEV remains visible, not hidden.
        dev101 = next(d for d in report["dev_tasks"] if d["dev_task"] == "DEV-101")
        self.assertEqual("rejected", dev101["outcome"])

        # Req 20: when the context-effect KPI is unavailable (no compatibility
        # rule declared), delivery-accounting metrics stay independently exact.
        effect_report = build_context_effect_report(
            self.fixture.path,
            baseline_cohort=self.cohort(["DEV-100"], context_strategy="chat-heavy"),
            treatment_cohort=self.cohort(["DEV-100"], context_strategy="chat-heavy"),
            compatibility_rule=None,
            guardrail_contract=None,
            guardrail_evidence=None,
        )
        self.assertFalse(effect_report["effect_metric_calculable"])
        self.assertEqual("unavailable", effect_report["effect_gate_result"])
        self.assertEqual(
            "exact",
            report["aggregate"]["metrics"]["total_tokens_per_accepted_dev"]["status"],
        )


class CohortComputationTests(ContextEffectTestCase):
    """Requirements 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13."""

    def test_happy_path_independent_cohort_with_failures_retries_continuation_and_excluded_review(self):
        # Req 3/4/5/10/11: independent assessment; failures/retries/continuations
        # count; review is excluded but does not block calculability even with
        # unknown usage; baseline/treatment differ only in context_strategy.
        self.fixture.accept("DEV-200")
        self.fixture.accept("DEV-201")
        self.fixture.row(
            "DEV-200", invocation_purpose="implementation", terminal_status="failure",
            input_tokens=40, context_strategy="chat-heavy",
        )
        self.fixture.row(
            "DEV-200", invocation_purpose="implementation", terminal_status="success",
            input_tokens=60, context_strategy="chat-heavy",
        )
        self.fixture.row(
            "DEV-200", invocation_purpose="continuation", terminal_status="success",
            input_tokens=10, context_strategy="chat-heavy",
        )
        self.fixture.row(
            "DEV-200", invocation_purpose="review", adapter_name="codex",
            requested_model="declared-review-model", usage_status="unknown",
            input_tokens=None, output_tokens=None, total_tokens=None,
            observed_model=None, runtime_version=None, context_strategy="chat-heavy",
        )
        self.fixture.row(
            "DEV-201", invocation_purpose="implementation", terminal_status="success",
            input_tokens=30, context_strategy="chat-heavy",
        )
        baseline = self.cohort(["DEV-200", "DEV-201"], context_strategy="chat-heavy")

        self.fixture.accept("DEV-300")
        self.fixture.row(
            "DEV-300", invocation_purpose="implementation", terminal_status="success",
            input_tokens=21, context_strategy="graphify-context-pack",
        )
        treatment = self.cohort(["DEV-300"], context_strategy="graphify-context-pack")

        report = build_context_effect_report(
            self.fixture.path,
            baseline_cohort=baseline,
            treatment_cohort=treatment,
            compatibility_rule=RULE,
            guardrail_contract=None,
            guardrail_evidence=None,
        )
        self.assertTrue(report["baseline"]["calculable"])
        self.assertIsNone(report["baseline"]["reason"])
        # 40+60+10 (DEV-200) + 30 (DEV-201) = 140; review excluded entirely.
        self.assertEqual(
            {"status": "exact", "numerator": 140, "denominator": 2, "exact_ratio": "140/2"},
            report["baseline"]["average_context_input_tokens_per_accepted_dev"],
        )
        self.assertTrue(report["treatment"]["calculable"])
        self.assertEqual(
            {"status": "exact", "numerator": 21, "denominator": 1, "exact_ratio": "21/1"},
            report["treatment"]["average_context_input_tokens_per_accepted_dev"],
        )
        self.assertTrue(report["effect_metric_calculable"])
        self.assertEqual("pass", report["effect_gate_result"])  # 21/70 -> 70% reduction exactly

    def test_missing_invocation_coverage_does_not_shrink_the_predeclared_denominator(self):
        # Req 6/7.
        self.fixture.accept("DEV-210")
        self.fixture.accept("DEV-211")
        self.fixture.row("DEV-210", invocation_purpose="implementation", input_tokens=50)
        # DEV-211 declared but has no contributing row at all.
        cohort = self.cohort(["DEV-210", "DEV-211"], context_strategy="chat-heavy")

        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertEqual(2, report["baseline"]["accepted_dev_count"])
        self.assertFalse(report["baseline"]["calculable"])
        self.assertEqual("missing_invocation_coverage", report["baseline"]["reason"])
        self.assertEqual(["DEV-211"], report["baseline"]["detail"]["missing_coverage"])
        self.assertFalse(report["effect_metric_calculable"])
        self.assertEqual("unavailable", report["effect_gate_result"])

    def test_requested_model_match_never_overrides_conflicting_or_missing_observed_model(self):
        # Req 8.
        self.fixture.accept("DEV-220")
        self.fixture.row(
            "DEV-220", invocation_purpose="implementation",
            requested_model=next(iter(RULE.covered_observed_models)),  # matches by name only
            observed_model="a-different-observed-model",
        )
        self.fixture.accept("DEV-221")
        self.fixture.row(
            "DEV-221", invocation_purpose="implementation",
            requested_model=next(iter(RULE.covered_observed_models)),
            observed_model=None,
        )
        for task in ("DEV-220", "DEV-221"):
            with self.subTest(task=task):
                cohort = self.cohort([task], context_strategy="chat-heavy")
                report = build_context_effect_report(
                    self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
                    compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
                )
                self.assertFalse(report["baseline"]["calculable"])
                self.assertEqual("not_comparable", report["baseline"]["reason"])

    def test_unknown_or_uncovered_runtime_version_and_absent_rule_fail_closed(self):
        # Req 9.
        self.fixture.accept("DEV-230")
        self.fixture.row("DEV-230", invocation_purpose="implementation", runtime_version="unfixtured-version")
        cohort = self.cohort(["DEV-230"], context_strategy="chat-heavy")

        with_rule = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertEqual("not_comparable", with_rule["baseline"]["reason"])

        without_rule = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=None, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertEqual("no_compatibility_rule_declared", without_rule["baseline"]["reason"])
        self.assertEqual("unavailable", without_rule["effect_gate_result"])

    def test_synthetic_rule_is_clearly_fixture_only_and_module_ships_no_real_version_mapping(self):
        # Req 10: the fixture rule is unmistakably synthetic...
        for value in RULE.covered_observed_models | RULE.covered_runtime_versions:
            self.assertIn("fixture", value.lower())
        # ...and the module itself contains no populated real-provider mapping.
        source = (ROOT / "src/ai_execution/context_effect.py").read_text(encoding="utf-8")
        forbidden = re.compile(r"\d+\.\d+\.\d+|anthropic|claude-code|gpt-|native-binary", re.I)
        self.assertIsNone(forbidden.search(source))

    def test_unknown_usage_blocks_cohort_only_for_contributing_purposes(self):
        # Req 12 (paired with req 5 above): an unrelated review row's unknown
        # usage never blocks the context-effect result on its own.
        self.fixture.accept("DEV-240")
        self.fixture.row("DEV-240", invocation_purpose="implementation", input_tokens=44)
        self.fixture.row(
            "DEV-240", invocation_purpose="continuation", usage_status="unknown",
            input_tokens=None, output_tokens=None, total_tokens=None,
        )
        cohort = self.cohort(["DEV-240"], context_strategy="chat-heavy")
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertFalse(report["baseline"]["calculable"])
        self.assertEqual("unknown_usage_present", report["baseline"]["reason"])

    def test_missing_acceptance_and_zero_baseline_both_yield_unavailable(self):
        # Req 13.
        self.fixture.row("DEV-250", invocation_purpose="implementation", input_tokens=10)  # never accepted
        not_accepted = self.cohort(["DEV-250"], context_strategy="chat-heavy")
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=not_accepted, treatment_cohort=not_accepted,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertEqual("declared_task_not_accepted_in_boundary", report["baseline"]["reason"])
        self.assertEqual("unavailable", report["effect_gate_result"])

        self.fixture.accept("DEV-251")
        self.fixture.row("DEV-251", invocation_purpose="implementation", input_tokens=0)
        self.fixture.accept("DEV-252")
        self.fixture.row(
            "DEV-252", invocation_purpose="implementation", input_tokens=5,
            context_strategy="graphify-context-pack",
        )
        zero_baseline = self.cohort(["DEV-251"], context_strategy="chat-heavy")
        treatment = self.cohort(["DEV-252"], context_strategy="graphify-context-pack")
        zero_report = build_context_effect_report(
            self.fixture.path, baseline_cohort=zero_baseline, treatment_cohort=treatment,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertTrue(zero_report["baseline"]["calculable"])  # coverage/comparability fine
        self.assertFalse(zero_report["effect_metric_calculable"])  # but baseline sum is zero
        self.assertEqual("unavailable", zero_report["effect_gate_result"])


class ExactArithmeticBoundaryTests(ContextEffectTestCase):
    """Requirement 14."""

    def _report_for(self, treatment_input_tokens: int) -> dict:
        self.fixture.accept("DEV-B")
        self.fixture.row("DEV-B", invocation_purpose="implementation", input_tokens=1000)
        self.fixture.accept("DEV-T")
        self.fixture.row(
            "DEV-T", invocation_purpose="implementation", input_tokens=treatment_input_tokens,
            context_strategy="graphify-context-pack",
        )
        return build_context_effect_report(
            self.fixture.path,
            baseline_cohort=self.cohort(["DEV-B"], context_strategy="chat-heavy"),
            treatment_cohort=self.cohort(["DEV-T"], context_strategy="graphify-context-pack"),
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )

    def test_exactly_seventy_percent_reduction_passes(self):
        report = self._report_for(300)  # 1 - 300/1000 = 0.70 exactly
        self.assertEqual("pass", report["effect_gate_result"])
        self.assertEqual("7/10", report["reduction"]["exact_ratio"])

    def test_strictly_below_seventy_percent_fails(self):
        report = self._report_for(301)  # 1 - 301/1000 = 0.699
        self.assertEqual("fail", report["effect_gate_result"])

    def test_strictly_above_seventy_percent_passes(self):
        report = self._report_for(299)  # 1 - 299/1000 = 0.701
        self.assertEqual("pass", report["effect_gate_result"])


class EligibilityTests(ContextEffectTestCase):
    """Requirements 15, 16, 17."""

    def _calculable_report(self, *, treatment_input_tokens, guardrail_contract, guardrail_evidence):
        self.fixture.accept("DEV-G-BASE")
        self.fixture.row("DEV-G-BASE", invocation_purpose="implementation", input_tokens=100)
        self.fixture.accept("DEV-G-TREAT")
        self.fixture.row(
            "DEV-G-TREAT", invocation_purpose="implementation", input_tokens=treatment_input_tokens,
            context_strategy="graphify-context-pack",
        )
        return build_context_effect_report(
            self.fixture.path,
            baseline_cohort=self.cohort(["DEV-G-BASE"], context_strategy="chat-heavy"),
            treatment_cohort=self.cohort(["DEV-G-TREAT"], context_strategy="graphify-context-pack"),
            compatibility_rule=RULE,
            guardrail_contract=guardrail_contract,
            guardrail_evidence=guardrail_evidence,
        )

    def test_passing_gate_without_a_declared_guardrail_contract_is_not_decision_eligible(self):
        # Req 15/17: a real M4 guardrail set is not yet authoritative.
        report = self._calculable_report(
            treatment_input_tokens=20, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertTrue(report["effect_metric_calculable"])
        self.assertEqual("pass", report["effect_gate_result"])
        self.assertFalse(report["guardrail"]["contract_declared"])
        self.assertFalse(report["treatment_decision_eligible"])

    def test_passing_gate_with_insufficient_declared_guardrail_evidence_is_not_decision_eligible(self):
        contract = GuardrailContract(frozenset({"quality_regression", "security_regression"}))
        report = self._calculable_report(
            treatment_input_tokens=20, guardrail_contract=contract,
            guardrail_evidence={"quality_regression": False},  # missing security_regression
        )
        self.assertEqual("pass", report["effect_gate_result"])
        self.assertTrue(report["guardrail"]["contract_declared"])
        self.assertFalse(report["guardrail"]["sufficient"])
        self.assertFalse(report["treatment_decision_eligible"])

    def test_failing_gate_with_sufficient_guardrail_evidence_is_decision_eligible_but_not_a_pass(self):
        # Req 16: a well-evidenced rejection is still a decision the Owner can act
        # on; eligibility never implies acceptance.
        contract = GuardrailContract(frozenset({"quality_regression", "security_regression"}))
        report = self._calculable_report(
            treatment_input_tokens=60,  # 1 - 60/100 = 0.40 < 0.70
            guardrail_contract=contract,
            guardrail_evidence={"quality_regression": False, "security_regression": False},
        )
        self.assertTrue(report["effect_metric_calculable"])
        self.assertEqual("fail", report["effect_gate_result"])
        self.assertTrue(report["guardrail"]["sufficient"])
        self.assertTrue(report["treatment_decision_eligible"])


class ContextStrategyIdentityTests(ContextEffectTestCase):
    """Corrected-blocker cases: direction (chat-heavy -> governed treatment),
    row-vs-cohort identity, and the required 5-case regression set from the
    directional correction.
    """

    def test_same_context_strategy_on_both_sides_cannot_pass_on_token_counts_alone(self):
        # Required regression 2: baseline=chat-heavy, treatment=chat-heavy.
        self.fixture.accept("DEV-SAME-BASE")
        self.fixture.row("DEV-SAME-BASE", invocation_purpose="implementation", input_tokens=1000)
        self.fixture.accept("DEV-SAME-TREAT")
        self.fixture.row("DEV-SAME-TREAT", invocation_purpose="implementation", input_tokens=200)
        report = build_context_effect_report(
            self.fixture.path,
            baseline_cohort=self.cohort(["DEV-SAME-BASE"], context_strategy="chat-heavy"),
            treatment_cohort=self.cohort(["DEV-SAME-TREAT"], context_strategy="chat-heavy"),
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertFalse(report["comparability"]["treatment_context_strategy_eligible"])
        self.assertFalse(report["effect_metric_calculable"])
        self.assertEqual("unavailable", report["effect_gate_result"])

    def test_reversed_pairing_baseline_treatment_swapped_cannot_pass(self):
        # Required regression 1: baseline=graphify-context-pack,
        # treatment=chat-heavy -- the exact invalid reversal the audit found.
        self.fixture.accept("DEV-REVERSED-BASE")
        self.fixture.row(
            "DEV-REVERSED-BASE", invocation_purpose="implementation", input_tokens=1000,
            context_strategy="graphify-context-pack",
        )
        self.fixture.accept("DEV-REVERSED-TREAT")
        self.fixture.row("DEV-REVERSED-TREAT", invocation_purpose="implementation", input_tokens=200)
        report = build_context_effect_report(
            self.fixture.path,
            baseline_cohort=self.cohort(["DEV-REVERSED-BASE"], context_strategy="graphify-context-pack"),
            treatment_cohort=self.cohort(["DEV-REVERSED-TREAT"], context_strategy="chat-heavy"),
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertFalse(report["comparability"]["baseline_context_strategy_valid"])
        self.assertFalse(report["comparability"]["treatment_context_strategy_eligible"])
        self.assertFalse(report["effect_metric_calculable"])
        self.assertEqual("unavailable", report["effect_gate_result"])

    def test_declared_graphify_context_pack_treatment_exercises_the_positive_path(self):
        # Required regression 3.
        self.fixture.accept("DEV-CONTRAST-BASE")
        self.fixture.row("DEV-CONTRAST-BASE", invocation_purpose="implementation", input_tokens=1000)
        self.fixture.accept("DEV-CONTRAST-TREAT")
        self.fixture.row(
            "DEV-CONTRAST-TREAT", invocation_purpose="implementation", input_tokens=200,
            context_strategy="graphify-context-pack",
        )
        report = build_context_effect_report(
            self.fixture.path,
            baseline_cohort=self.cohort(["DEV-CONTRAST-BASE"], context_strategy="chat-heavy"),
            treatment_cohort=self.cohort(["DEV-CONTRAST-TREAT"], context_strategy="graphify-context-pack"),
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertTrue(report["comparability"]["baseline_context_strategy_valid"])
        self.assertTrue(report["comparability"]["treatment_context_strategy_eligible"])
        self.assertTrue(report["effect_metric_calculable"])
        self.assertEqual("pass", report["effect_gate_result"])

    def test_declared_manual_context_pack_treatment_exercises_the_positive_path(self):
        # Required regression 4: manual-context-pack is already a governed named
        # M4 treatment under the current contract.
        self.fixture.accept("DEV-MANUAL-BASE")
        self.fixture.row("DEV-MANUAL-BASE", invocation_purpose="implementation", input_tokens=1000)
        self.fixture.accept("DEV-MANUAL-TREAT")
        self.fixture.row(
            "DEV-MANUAL-TREAT", invocation_purpose="implementation", input_tokens=200,
            context_strategy="manual-context-pack",
        )
        report = build_context_effect_report(
            self.fixture.path,
            baseline_cohort=self.cohort(["DEV-MANUAL-BASE"], context_strategy="chat-heavy"),
            treatment_cohort=self.cohort(["DEV-MANUAL-TREAT"], context_strategy="manual-context-pack"),
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertTrue(report["comparability"]["treatment_context_strategy_eligible"])
        self.assertTrue(report["effect_metric_calculable"])
        self.assertEqual("pass", report["effect_gate_result"])

    def test_other_treatment_fails_closed_without_a_governed_declaration(self):
        # Required regression 5: `other` is never silently treatment-eligible.
        self.fixture.accept("DEV-OTHER-BASE")
        self.fixture.row("DEV-OTHER-BASE", invocation_purpose="implementation", input_tokens=1000)
        self.fixture.accept("DEV-OTHER-TREAT")
        self.fixture.row(
            "DEV-OTHER-TREAT", invocation_purpose="implementation", input_tokens=200,
            context_strategy="other",
        )
        report = build_context_effect_report(
            self.fixture.path,
            baseline_cohort=self.cohort(["DEV-OTHER-BASE"], context_strategy="chat-heavy"),
            treatment_cohort=self.cohort(["DEV-OTHER-TREAT"], context_strategy="other"),
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertFalse(report["comparability"]["treatment_context_strategy_eligible"])
        self.assertFalse(report["effect_metric_calculable"])
        self.assertEqual("unavailable", report["effect_gate_result"])

    def test_row_context_strategy_mismatching_its_cohort_declaration_is_unavailable(self):
        self.fixture.accept("DEV-MISMATCH")
        self.fixture.row(
            "DEV-MISMATCH", invocation_purpose="implementation", input_tokens=50,
            context_strategy="manual-context-pack",  # cohort below declares chat-heavy
        )
        cohort = self.cohort(["DEV-MISMATCH"], context_strategy="chat-heavy")
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertEqual("context_strategy_mismatch", report["baseline"]["reason"])
        self.assertEqual("unavailable", report["effect_gate_result"])


class ReasoningEffortConsistencyTests(ContextEffectTestCase):
    """Reasoning effort is a fixed comparison condition, not a set-membership
    condition, for one M4 context-effect comparison.
    """

    MEDIUM_RULE = CompatibilityRule(
        id="synthetic-fixture-rule-medium",
        runtime_adapter="claude",
        covered_observed_models=frozenset({"fixture-claude-observed-model"}),
        covered_runtime_versions=frozenset({"fixture-runtime-9.9.9-test"}),
        token_accounting_semantics="fixture-claude-cache-read-input-plus-base",
        reasoning_conditions=frozenset({"medium"}),
        model_selection_strategy="fixed",
        routing_policy_version=None,
    )

    def test_baseline_null_treatment_high_reasoning_effort_cannot_pass(self):
        self.fixture.accept("DEV-RE-BASE")
        self.fixture.row("DEV-RE-BASE", invocation_purpose="implementation", input_tokens=1000)
        self.fixture.accept("DEV-RE-TREAT")
        self.fixture.row(
            "DEV-RE-TREAT", invocation_purpose="implementation", input_tokens=200,
            context_strategy="graphify-context-pack", requested_reasoning_effort="high",
        )
        report = build_context_effect_report(
            self.fixture.path,
            baseline_cohort=self.cohort(
                ["DEV-RE-BASE"], context_strategy="chat-heavy", requested_reasoning_effort=None,
            ),
            treatment_cohort=self.cohort(
                ["DEV-RE-TREAT"], context_strategy="graphify-context-pack",
                requested_reasoning_effort="high",
            ),
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertFalse(report["comparability"]["reasoning_effort_consistent"])
        self.assertFalse(report["effect_metric_calculable"])
        self.assertEqual("unavailable", report["effect_gate_result"])

    def test_multi_value_reasoning_compatibility_rule_is_invalid(self):
        with self.assertRaisesRegex(BaselineEvidenceError, "exactly one fixed"):
            CompatibilityRule(
                id="invalid-multi-reasoning-rule",
                runtime_adapter="claude",
                covered_observed_models=frozenset({"fixture-claude-observed-model"}),
                covered_runtime_versions=frozenset({"fixture-runtime-9.9.9-test"}),
                token_accounting_semantics="fixture-claude-cache-read-input-plus-base",
                reasoning_conditions=frozenset({None, "medium"}),
                model_selection_strategy="fixed",
                routing_policy_version=None,
            )

    def test_one_contributing_invocation_drifting_from_declared_reasoning_effort_is_unavailable(self):
        self.fixture.accept("DEV-RE-DRIFT")
        self.fixture.row(
            "DEV-RE-DRIFT", invocation_purpose="implementation", input_tokens=100,
            requested_reasoning_effort="medium",
        )
        drifted_id = self.fixture.row(
            "DEV-RE-DRIFT", invocation_purpose="continuation", input_tokens=10,
            requested_reasoning_effort="high",  # drifts from the cohort's declared "medium"
        )
        cohort = self.cohort(
            ["DEV-RE-DRIFT"], context_strategy="chat-heavy", requested_reasoning_effort="medium",
        )
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=self.MEDIUM_RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertEqual("requested_reasoning_effort_mismatch", report["baseline"]["reason"])
        self.assertEqual(
            [drifted_id], report["baseline"]["detail"]["mismatched_reasoning_effort_invocation_ids"]
        )
        self.assertFalse(report["effect_metric_calculable"])

    def test_declared_reasoning_effort_shared_by_both_cohorts_exercises_positive_path(self):
        self.fixture.accept("DEV-RE-POS-BASE")
        self.fixture.row(
            "DEV-RE-POS-BASE", invocation_purpose="implementation", input_tokens=1000,
            requested_reasoning_effort="medium",
        )
        self.fixture.accept("DEV-RE-POS-TREAT")
        self.fixture.row(
            "DEV-RE-POS-TREAT", invocation_purpose="implementation", input_tokens=200,
            context_strategy="graphify-context-pack", requested_reasoning_effort="medium",
        )
        report = build_context_effect_report(
            self.fixture.path,
            baseline_cohort=self.cohort(
                ["DEV-RE-POS-BASE"], context_strategy="chat-heavy", requested_reasoning_effort="medium",
            ),
            treatment_cohort=self.cohort(
                ["DEV-RE-POS-TREAT"], context_strategy="graphify-context-pack",
                requested_reasoning_effort="medium",
            ),
            compatibility_rule=self.MEDIUM_RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertTrue(report["comparability"]["reasoning_effort_consistent"])
        self.assertTrue(report["effect_metric_calculable"])
        self.assertEqual("pass", report["effect_gate_result"])

    def test_omitting_requested_reasoning_effort_from_cohort_construction_is_rejected(self):
        with self.assertRaises(TypeError):
            ContextEffectCohort(
                accepted_dev_tasks=("DEV-OMIT",),
                evidence_boundary=BOUNDARY,
                task_eval_mix_id="mix",
                acceptance_criteria_id="criteria",
                context_strategy="chat-heavy",
                # requested_reasoning_effort intentionally omitted
            )


class NonTerminalCoverageTests(ContextEffectTestCase):
    """Corrected-blocker cases 4, 5."""

    def test_one_terminal_and_one_non_terminal_contributing_invocation_is_incomplete(self):
        # Case 4.
        self.fixture.accept("DEV-INFLIGHT")
        self.fixture.row("DEV-INFLIGHT", invocation_purpose="implementation", input_tokens=50)
        inflight_id = self.fixture.row(
            "DEV-INFLIGHT", invocation_purpose="continuation",
            completed_at=None, terminal_status=None, usage_status=None,
            input_tokens=None, output_tokens=None, total_tokens=None,
        )
        cohort = self.cohort(["DEV-INFLIGHT"], context_strategy="chat-heavy")
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertEqual("non_terminal_contributing_invocation", report["baseline"]["reason"])
        self.assertEqual([inflight_id], report["baseline"]["detail"]["non_terminal_invocation_ids"])
        self.assertFalse(report["effect_metric_calculable"])
        self.assertEqual("unavailable", report["effect_gate_result"])

    def test_non_terminal_row_stays_visible_and_does_not_change_build_report_behavior(self):
        # Case 5.
        self.fixture.accept("DEV-VISIBLE")
        inflight_id = self.fixture.row(
            "DEV-VISIBLE", invocation_purpose="implementation",
            completed_at=None, terminal_status=None, usage_status=None,
            input_tokens=None, output_tokens=None, total_tokens=None,
        )
        # Req: the row is retained in raw telemetry, not deleted.
        with closing(self.fixture._connect()) as connection:
            row = connection.execute(
                "SELECT invocation_id FROM invocations WHERE invocation_id=?", (inflight_id,)
            ).fetchone()
        self.assertIsNotNone(row)

        cohort = self.cohort(["DEV-VISIBLE"], context_strategy="chat-heavy")
        effect_report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertIn(inflight_id, effect_report["baseline"]["detail"]["non_terminal_invocation_ids"])

        # cost_baseline.build_report's own existing non-terminal handling (it
        # simply reports no terminal evidence for that DEV) is unchanged.
        window = cost_baseline.MeasurementWindow.from_mapping({
            "id": "fixture-window-nonterminal",
            "included_dev_tasks": ["DEV-VISIBLE"],
            "task_mix": {"implementation": 1},
            "trace_level_mix": {"T0": 0, "T1": 0, "T2": 1},
            "review_policy": "all review usage retained",
            "acceptance_policy": "governed outcome",
            "evidence_boundary": {
                "start_inclusive": BOUNDARY.start_inclusive, "end_exclusive": BOUNDARY.end_exclusive,
            },
            "purpose_treatments": {
                "implementation": {
                    "runtime_adapter": "claude", "requested_model": "declared-fixture-model",
                    "requested_reasoning_effort": None, "model_selection_strategy": "fixed",
                    "routing_policy_version": None, "context_strategy": "chat-heavy",
                },
            },
            "automatic_model_routing": False,
            "context_optimization": False,
        })
        build_report = cost_baseline.build_report(
            self.fixture.path, window, {"DEV-VISIBLE": "T2"}
        )
        dev = build_report["dev_tasks"][0]
        self.assertEqual(0, dev["invocation_count"])  # unchanged: non-terminal rows excluded there


class EvidenceBoundaryTests(ContextEffectTestCase):
    """Owner boundary decision: reuse EvidenceBoundary unchanged. Admissible
    evidence requires started_at in range AND completed_at IS NOT NULL AND
    completed_at < end_exclusive -- the same half-open terminal-evidence rule
    cost_baseline.build_report already uses.
    """

    def _cohort_with_completion(self, dev_task: str, *, completed_at):
        self.fixture.accept(dev_task)
        invocation_id = self.fixture.row(
            dev_task, invocation_purpose="implementation", input_tokens=50, completed_at=completed_at,
        )
        return invocation_id, self.cohort([dev_task], context_strategy="chat-heavy")

    def test_completed_strictly_before_end_exclusive_may_contribute(self):
        # Required regression 1.
        _, cohort = self._cohort_with_completion(
            "DEV-EB-BEFORE", completed_at="2026-09-24T23:59:59.999Z"
        )
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertTrue(report["baseline"]["calculable"])
        self.assertIsNone(report["baseline"]["reason"])

    def test_completed_exactly_at_end_exclusive_is_not_admissible(self):
        # Required regression 2: half-open interval, end_exclusive is excluded.
        invocation_id, cohort = self._cohort_with_completion(
            "DEV-EB-AT-END", completed_at=BOUNDARY.end_exclusive
        )
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertEqual("boundary_spill_contributing_invocation", report["baseline"]["reason"])
        self.assertEqual(
            [invocation_id], report["baseline"]["detail"]["boundary_spill_invocation_ids"]
        )
        self.assertFalse(report["effect_metric_calculable"])
        self.assertEqual("unavailable", report["effect_gate_result"])

    def test_completed_after_end_exclusive_is_not_admissible(self):
        # Required regression 3.
        invocation_id, cohort = self._cohort_with_completion(
            "DEV-EB-AFTER-END", completed_at="2026-09-25T00:05:00.000Z"
        )
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertEqual("boundary_spill_contributing_invocation", report["baseline"]["reason"])
        self.assertEqual(
            [invocation_id], report["baseline"]["detail"]["boundary_spill_invocation_ids"]
        )
        self.assertFalse(report["effect_metric_calculable"])
        self.assertEqual("unavailable", report["effect_gate_result"])

    def test_non_terminal_at_end_exclusive_remains_unavailable(self):
        # Required regression 4 (reconfirms non-terminal handling reuses the
        # same EvidenceBoundary discipline, not a separate window model).
        _, cohort = self._cohort_with_completion("DEV-EB-NONTERMINAL", completed_at=None)
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertEqual("non_terminal_contributing_invocation", report["baseline"]["reason"])
        self.assertFalse(report["effect_metric_calculable"])
        self.assertEqual("unavailable", report["effect_gate_result"])

    def test_later_terminal_evidence_is_not_borrowed_into_the_closed_window(self):
        # Required regression 5: even though the boundary-spill row carries
        # otherwise-perfect exact usage, it must never be summed into a report
        # built against the already-closed [start, end_exclusive) window.
        self.fixture.accept("DEV-EB-NO-BORROW")
        self.fixture.row(
            "DEV-EB-NO-BORROW", invocation_purpose="implementation", input_tokens=999,
            completed_at="2026-09-25T00:00:00.001Z",  # one millisecond past end_exclusive
        )
        cohort = self.cohort(["DEV-EB-NO-BORROW"], context_strategy="chat-heavy")
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertEqual("boundary_spill_contributing_invocation", report["baseline"]["reason"])
        self.assertEqual(
            {"status": "unavailable", "reason": "boundary_spill_contributing_invocation", "denominator": 1},
            report["baseline"]["average_context_input_tokens_per_accepted_dev"],
        )

    def test_boundary_spill_invocation_remains_persisted_and_visible_in_diagnostics(self):
        # Required regression 6.
        self.fixture.accept("DEV-EB-VISIBLE")
        spill_id = self.fixture.row(
            "DEV-EB-VISIBLE", invocation_purpose="implementation", input_tokens=50,
            completed_at="2026-09-25T00:00:00.000Z",  # == end_exclusive
        )
        with closing(self.fixture._connect()) as connection:
            row = connection.execute(
                "SELECT invocation_id FROM invocations WHERE invocation_id=?", (spill_id,)
            ).fetchone()
        self.assertIsNotNone(row)  # retained in persisted telemetry, not deleted

        cohort = self.cohort(["DEV-EB-VISIBLE"], context_strategy="chat-heavy")
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertIn(spill_id, report["baseline"]["detail"]["boundary_spill_invocation_ids"])

    def test_cost_baseline_build_report_boundary_behavior_is_unchanged(self):
        # Required regression 7.
        self.fixture.accept("DEV-EB-DELIVERY")
        self.fixture.row(
            "DEV-EB-DELIVERY", invocation_purpose="implementation", input_tokens=50, output_tokens=5,
            completed_at="2026-09-25T00:00:00.000Z",  # == end_exclusive: already excluded there too
        )
        window = cost_baseline.MeasurementWindow.from_mapping({
            "id": "fixture-window-eb",
            "included_dev_tasks": ["DEV-EB-DELIVERY"],
            "task_mix": {"implementation": 1},
            "trace_level_mix": {"T0": 0, "T1": 0, "T2": 1},
            "review_policy": "all review usage retained",
            "acceptance_policy": "governed outcome",
            "evidence_boundary": {
                "start_inclusive": BOUNDARY.start_inclusive, "end_exclusive": BOUNDARY.end_exclusive,
            },
            "purpose_treatments": {
                "implementation": {
                    "runtime_adapter": "claude", "requested_model": "declared-fixture-model",
                    "requested_reasoning_effort": None, "model_selection_strategy": "fixed",
                    "routing_policy_version": None, "context_strategy": "chat-heavy",
                },
            },
            "automatic_model_routing": False,
            "context_optimization": False,
        })
        report = cost_baseline.build_report(self.fixture.path, window, {"DEV-EB-DELIVERY": "T2"})
        # cost_baseline's own half-open boundary already excludes completed_at ==
        # end_exclusive; this correction does not touch that behavior.
        self.assertEqual(0, report["dev_tasks"][0]["invocation_count"])


class DiagnosticsAggregationTests(ContextEffectTestCase):
    """Eligibility failure must not truncate diagnostic collection: one defect
    must not hide another. Every applicable diagnostic category is collected in
    one pass before a single primary `reason` is selected.
    """

    def test_nonterminal_and_boundary_spill_in_the_same_cohort_report_both_ids(self):
        self.fixture.accept("DEV-DIAG-A")
        inflight_id = self.fixture.row(
            "DEV-DIAG-A", invocation_purpose="implementation", input_tokens=50,
            completed_at=None,
        )
        spill_id = self.fixture.row(
            "DEV-DIAG-A", invocation_purpose="continuation", input_tokens=10,
            completed_at="2026-09-25T00:05:00.000Z",  # after end_exclusive
        )
        cohort = self.cohort(["DEV-DIAG-A"], context_strategy="chat-heavy")
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        detail = report["baseline"]["detail"]
        self.assertEqual([inflight_id], detail["non_terminal_invocation_ids"])
        self.assertEqual([spill_id], detail["boundary_spill_invocation_ids"])
        # Priority order still selects one primary reason deterministically.
        self.assertEqual("non_terminal_contributing_invocation", report["baseline"]["reason"])
        self.assertFalse(report["effect_metric_calculable"])
        self.assertEqual("unavailable", report["effect_gate_result"])
        self.assertFalse(report["treatment_decision_eligible"])

    def test_boundary_spill_and_missing_dev_coverage_retain_both_diagnostic_classes(self):
        self.fixture.accept("DEV-DIAG-B1")
        self.fixture.accept("DEV-DIAG-B2")
        spill_id = self.fixture.row(
            "DEV-DIAG-B1", invocation_purpose="implementation", input_tokens=50,
            completed_at="2026-09-25T00:00:00.000Z",  # == end_exclusive
        )
        # DEV-DIAG-B2 declared but has no contributing row at all.
        cohort = self.cohort(["DEV-DIAG-B1", "DEV-DIAG-B2"], context_strategy="chat-heavy")
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        detail = report["baseline"]["detail"]
        self.assertEqual(["DEV-DIAG-B2"], detail["missing_coverage"])
        self.assertEqual([spill_id], detail["boundary_spill_invocation_ids"])
        self.assertEqual("missing_invocation_coverage", report["baseline"]["reason"])
        self.assertFalse(report["effect_metric_calculable"])
        self.assertEqual("unavailable", report["effect_gate_result"])

    def test_boundary_spill_and_missing_outcome_evidence_still_reports_spill_ids(self):
        # DEV-DIAG-C1 is never accepted (missing/ineligible outcome evidence);
        # DEV-DIAG-C2 is accepted but boundary-spills.
        self.fixture.row("DEV-DIAG-C1", invocation_purpose="implementation", input_tokens=50)
        self.fixture.accept("DEV-DIAG-C2")
        spill_id = self.fixture.row(
            "DEV-DIAG-C2", invocation_purpose="implementation", input_tokens=10,
            completed_at="2026-09-25T00:10:00.000Z",  # after end_exclusive
        )
        cohort = self.cohort(["DEV-DIAG-C1", "DEV-DIAG-C2"], context_strategy="chat-heavy")
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        detail = report["baseline"]["detail"]
        self.assertEqual(["DEV-DIAG-C1"], detail["missing_acceptance"])
        self.assertEqual([spill_id], detail["boundary_spill_invocation_ids"])
        self.assertEqual("declared_task_not_accepted_in_boundary", report["baseline"]["reason"])
        self.assertFalse(report["effect_metric_calculable"])
        self.assertEqual("unavailable", report["effect_gate_result"])
        self.assertFalse(report["treatment_decision_eligible"])

    def test_diagnostic_lists_are_deterministically_ordered_and_duplicate_free(self):
        self.fixture.accept("DEV-DIAG-D")
        first_id = self.fixture.row(
            "DEV-DIAG-D", invocation_purpose="implementation", input_tokens=10, completed_at=None,
        )
        second_id = self.fixture.row(
            "DEV-DIAG-D", invocation_purpose="continuation", input_tokens=10, completed_at=None,
        )
        cohort = self.cohort(["DEV-DIAG-D"], context_strategy="chat-heavy")
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        ids = report["baseline"]["detail"]["non_terminal_invocation_ids"]
        self.assertEqual(sorted({first_id, second_id}), ids)
        self.assertEqual(len(ids), len(set(ids)))


class MultiDefectDiagnosticsTests(ContextEffectTestCase):
    """One admissible terminal invocation can independently violate more than
    one dimension at once; eligibility filtering or primary-reason selection
    must never prevent another applicable defect from being reported.
    """

    def test_context_strategy_mismatch_and_malformed_usage_on_the_same_row_both_reported(self):
        # Required regression 1.
        self.fixture.accept("DEV-MD-A")
        row_id = self.fixture.row(
            "DEV-MD-A", invocation_purpose="implementation",
            context_strategy="manual-context-pack",  # cohort below declares chat-heavy
            output_tokens=None,  # malformed exact usage: missing output_tokens
        )
        cohort = self.cohort(["DEV-MD-A"], context_strategy="chat-heavy")
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        detail = report["baseline"]["detail"]
        self.assertEqual([row_id], detail["mismatched_context_strategy_invocation_ids"])
        self.assertEqual([row_id], detail["malformed_exact_usage_invocation_ids"])
        self.assertFalse(report["baseline"]["calculable"])
        self.assertFalse(report["effect_metric_calculable"])
        self.assertEqual("unavailable", report["effect_gate_result"])
        self.assertFalse(report["treatment_decision_eligible"])

    def test_reasoning_drift_and_unknown_usage_on_the_same_row_both_reported(self):
        # Required regression 2.
        self.fixture.accept("DEV-MD-B")
        row_id = self.fixture.row(
            "DEV-MD-B", invocation_purpose="implementation",
            requested_reasoning_effort="high",  # cohort below declares None
            usage_status="unknown", input_tokens=None, output_tokens=None, total_tokens=None,
        )
        cohort = self.cohort(["DEV-MD-B"], context_strategy="chat-heavy", requested_reasoning_effort=None)
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        detail = report["baseline"]["detail"]
        self.assertEqual([row_id], detail["mismatched_reasoning_effort_invocation_ids"])
        self.assertEqual([row_id], detail["unknown_usage_invocation_ids"])
        self.assertFalse(report["effect_metric_calculable"])
        self.assertEqual("unavailable", report["effect_gate_result"])
        self.assertFalse(report["treatment_decision_eligible"])

    def test_a_multi_defect_row_appears_at_most_once_per_diagnostic_list(self):
        # Required regression 3.
        self.fixture.accept("DEV-MD-C")
        row_id = self.fixture.row(
            "DEV-MD-C", invocation_purpose="implementation",
            context_strategy="manual-context-pack",
            requested_reasoning_effort="high",
            output_tokens=None,
        )
        cohort = self.cohort(["DEV-MD-C"], context_strategy="chat-heavy", requested_reasoning_effort=None)
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        detail = report["baseline"]["detail"]
        for key in (
            "mismatched_context_strategy_invocation_ids",
            "mismatched_reasoning_effort_invocation_ids",
            "malformed_exact_usage_invocation_ids",
        ):
            self.assertEqual([row_id], detail[key])
            self.assertEqual(1, detail[key].count(row_id))

    def test_diagnostic_lists_remain_sorted_with_multiple_defective_rows(self):
        # Required regression 4.
        self.fixture.accept("DEV-MD-D")
        id_b = self.fixture.row(
            "DEV-MD-D", invocation_purpose="implementation",
            context_strategy="manual-context-pack", invocation_id="inv-DEV-MD-D-b",
        )
        id_a = self.fixture.row(
            "DEV-MD-D", invocation_purpose="continuation",
            context_strategy="graphify-context-pack", invocation_id="inv-DEV-MD-D-a",
        )
        cohort = self.cohort(["DEV-MD-D"], context_strategy="chat-heavy")
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        ids = report["baseline"]["detail"]["mismatched_context_strategy_invocation_ids"]
        self.assertEqual(sorted([id_a, id_b]), ids)

    def test_a_fully_valid_row_still_contributes_normally_when_no_defects_apply(self):
        # Required regression 5.
        self.fixture.accept("DEV-MD-VALID")
        self.fixture.row("DEV-MD-VALID", invocation_purpose="implementation", input_tokens=42)
        cohort = self.cohort(["DEV-MD-VALID"], context_strategy="chat-heavy")
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertTrue(report["baseline"]["calculable"])
        self.assertIsNone(report["baseline"]["reason"])
        self.assertEqual({}, report["baseline"]["detail"])
        self.assertEqual(
            {"status": "exact", "numerator": 42, "denominator": 1, "exact_ratio": "42/1"},
            report["baseline"]["average_context_input_tokens_per_accepted_dev"],
        )

    def test_cost_baseline_build_report_unaffected_by_multi_defect_correction(self):
        # Required regression 8.
        self.fixture.accept("DEV-MD-DELIVERY")
        self.fixture.row(
            "DEV-MD-DELIVERY", invocation_purpose="implementation", input_tokens=30, output_tokens=3,
        )
        window = cost_baseline.MeasurementWindow.from_mapping({
            "id": "fixture-window-md",
            "included_dev_tasks": ["DEV-MD-DELIVERY"],
            "task_mix": {"implementation": 1},
            "trace_level_mix": {"T0": 0, "T1": 0, "T2": 1},
            "review_policy": "all review usage retained",
            "acceptance_policy": "governed outcome",
            "evidence_boundary": {
                "start_inclusive": BOUNDARY.start_inclusive, "end_exclusive": BOUNDARY.end_exclusive,
            },
            "purpose_treatments": {
                "implementation": {
                    "runtime_adapter": "claude", "requested_model": "declared-fixture-model",
                    "requested_reasoning_effort": None, "model_selection_strategy": "fixed",
                    "routing_policy_version": None, "context_strategy": "chat-heavy",
                },
            },
            "automatic_model_routing": False,
            "context_optimization": False,
        })
        report = cost_baseline.build_report(self.fixture.path, window, {"DEV-MD-DELIVERY": "T2"})
        self.assertEqual(
            "exact", report["aggregate"]["metrics"]["input_tokens_per_accepted_dev"]["status"]
        )
        self.assertEqual(33, report["aggregate"]["metrics"]["total_tokens_per_accepted_dev"]["numerator"])


class GuardrailAuthorityTests(ContextEffectTestCase):
    """Corrected-blocker cases 6, 7, 8."""

    def _calculable_passing_report(self, *, guardrail_contract, guardrail_evidence):
        self.fixture.accept("DEV-GA-BASE")
        self.fixture.row("DEV-GA-BASE", invocation_purpose="implementation", input_tokens=100)
        self.fixture.accept("DEV-GA-TREAT")
        self.fixture.row(
            "DEV-GA-TREAT", invocation_purpose="implementation", input_tokens=20,
            context_strategy="graphify-context-pack",
        )
        return build_context_effect_report(
            self.fixture.path,
            baseline_cohort=self.cohort(["DEV-GA-BASE"], context_strategy="chat-heavy"),
            treatment_cohort=self.cohort(["DEV-GA-TREAT"], context_strategy="graphify-context-pack"),
            compatibility_rule=RULE,
            guardrail_contract=guardrail_contract,
            guardrail_evidence=guardrail_evidence,
        )

    def test_absent_guardrail_contract_is_never_sufficient(self):
        # Case 6.
        report = self._calculable_passing_report(guardrail_contract=None, guardrail_evidence=None)
        self.assertEqual("pass", report["effect_gate_result"])
        self.assertFalse(report["guardrail"]["sufficient"])
        self.assertFalse(report["treatment_decision_eligible"])

    def test_empty_guardrail_contract_is_never_sufficient(self):
        # Case 7: vacuous truth over zero requirements must not make this true.
        empty_contract = GuardrailContract(frozenset())
        report = self._calculable_passing_report(
            guardrail_contract=empty_contract, guardrail_evidence={"anything": "present"},
        )
        self.assertTrue(report["guardrail"]["contract_declared"])
        self.assertFalse(report["guardrail"]["sufficient"])
        self.assertFalse(report["treatment_decision_eligible"])
        self.assertFalse(empty_contract.sufficiency({}))
        self.assertFalse(empty_contract.sufficiency(None))

    def test_nonempty_synthetic_contract_with_sufficient_evidence_is_eligible_without_real_authority(self):
        # Case 8: exercises the positive mechanism only; creates no real M4
        # decision authority (the required-key set here is a test fixture, not
        # an authorized guardrail declaration).
        contract = GuardrailContract(frozenset({"quality_regression", "security_regression"}))
        report = self._calculable_passing_report(
            guardrail_contract=contract,
            guardrail_evidence={"quality_regression": False, "security_regression": False},
        )
        self.assertEqual("pass", report["effect_gate_result"])
        self.assertTrue(report["guardrail"]["sufficient"])
        self.assertTrue(report["treatment_decision_eligible"])


class ExactUsageValidityTests(ContextEffectTestCase):
    """Corrected-blocker cases 9, 10, 11, 12."""

    def _malformed_report(self, **row_overrides):
        self.fixture.accept("DEV-MALFORMED")
        invocation_id = self.fixture.row(
            "DEV-MALFORMED", invocation_purpose="implementation", **row_overrides
        )
        cohort = self.cohort(["DEV-MALFORMED"], context_strategy="chat-heavy")
        report = build_context_effect_report(
            self.fixture.path, baseline_cohort=cohort, treatment_cohort=cohort,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        return invocation_id, report

    def test_exact_status_with_missing_output_tokens_is_unavailable(self):
        # Case 9.
        invocation_id, report = self._malformed_report(output_tokens=None)
        self.assertEqual("malformed_exact_usage", report["baseline"]["reason"])
        self.assertEqual(
            [invocation_id], report["baseline"]["detail"]["malformed_exact_usage_invocation_ids"]
        )
        self.assertFalse(report["effect_metric_calculable"])

    def test_exact_status_with_missing_total_tokens_is_unavailable(self):
        # Case 10.
        invocation_id, report = self._malformed_report(total_tokens=None)
        self.assertEqual("malformed_exact_usage", report["baseline"]["reason"])
        self.assertEqual(
            [invocation_id], report["baseline"]["detail"]["malformed_exact_usage_invocation_ids"]
        )

    def test_exact_status_with_inconsistent_total_is_unavailable(self):
        # Case 11.
        invocation_id, report = self._malformed_report(input_tokens=100, output_tokens=10, total_tokens=999)
        self.assertEqual("malformed_exact_usage", report["baseline"]["reason"])
        self.assertEqual(
            [invocation_id], report["baseline"]["detail"]["malformed_exact_usage_invocation_ids"]
        )

    def test_malformed_exact_evidence_is_never_zeroed_or_silently_omitted(self):
        # Case 12: the malformed row is named in diagnostics (not omitted), and
        # the cohort has no numeric sum at all (never substitutes zero).
        invocation_id, report = self._malformed_report(output_tokens=None)
        self.assertIn(invocation_id, report["baseline"]["detail"]["malformed_exact_usage_invocation_ids"])
        self.assertEqual(
            {"status": "unavailable", "reason": "malformed_exact_usage", "denominator": 1},
            report["baseline"]["average_context_input_tokens_per_accepted_dev"],
        )


class DeliveryAccountingIndependenceTests(ContextEffectTestCase):
    """Corrected-blocker cases 13, 14 (explicit, direct-mapped regressions)."""

    def test_delivery_accounting_metrics_unaffected_by_any_context_effect_correction(self):
        # Case 13.
        self.fixture.accept("DEV-DA")
        self.fixture.row("DEV-DA", invocation_purpose="implementation", input_tokens=30, output_tokens=3)
        window = cost_baseline.MeasurementWindow.from_mapping({
            "id": "fixture-window-da",
            "included_dev_tasks": ["DEV-DA"],
            "task_mix": {"implementation": 1},
            "trace_level_mix": {"T0": 0, "T1": 0, "T2": 1},
            "review_policy": "all review usage retained",
            "acceptance_policy": "governed outcome",
            "evidence_boundary": {
                "start_inclusive": BOUNDARY.start_inclusive, "end_exclusive": BOUNDARY.end_exclusive,
            },
            "purpose_treatments": {
                "implementation": {
                    "runtime_adapter": "claude", "requested_model": "declared-fixture-model",
                    "requested_reasoning_effort": None, "model_selection_strategy": "fixed",
                    "routing_policy_version": None, "context_strategy": "chat-heavy",
                },
            },
            "automatic_model_routing": False,
            "context_optimization": False,
        })
        report = cost_baseline.build_report(self.fixture.path, window, {"DEV-DA": "T2"})
        metrics = report["aggregate"]["metrics"]
        self.assertEqual("exact", metrics["input_tokens_per_accepted_dev"]["status"])
        self.assertEqual("exact", metrics["total_tokens_per_accepted_dev"]["status"])
        self.assertEqual(30, metrics["input_tokens_per_accepted_dev"]["numerator"])
        self.assertEqual(33, metrics["total_tokens_per_accepted_dev"]["numerator"])

    def test_context_effect_unavailability_does_not_make_delivery_accounting_unavailable(self):
        # Case 14: same-strategy cohorts (unavailable KPI) alongside a fully
        # exact, eligible delivery-accounting window over the same evidence.
        self.fixture.accept("DEV-DA2")
        self.fixture.row("DEV-DA2", invocation_purpose="implementation", input_tokens=12, output_tokens=1)
        same_strategy = self.cohort(["DEV-DA2"], context_strategy="chat-heavy")
        effect_report = build_context_effect_report(
            self.fixture.path, baseline_cohort=same_strategy, treatment_cohort=same_strategy,
            compatibility_rule=RULE, guardrail_contract=None, guardrail_evidence=None,
        )
        self.assertFalse(effect_report["effect_metric_calculable"])

        window = cost_baseline.MeasurementWindow.from_mapping({
            "id": "fixture-window-da2",
            "included_dev_tasks": ["DEV-DA2"],
            "task_mix": {"implementation": 1},
            "trace_level_mix": {"T0": 0, "T1": 0, "T2": 1},
            "review_policy": "all review usage retained",
            "acceptance_policy": "governed outcome",
            "evidence_boundary": {
                "start_inclusive": BOUNDARY.start_inclusive, "end_exclusive": BOUNDARY.end_exclusive,
            },
            "purpose_treatments": {
                "implementation": {
                    "runtime_adapter": "claude", "requested_model": "declared-fixture-model",
                    "requested_reasoning_effort": None, "model_selection_strategy": "fixed",
                    "routing_policy_version": None, "context_strategy": "chat-heavy",
                },
            },
            "automatic_model_routing": False,
            "context_optimization": False,
        })
        report = cost_baseline.build_report(self.fixture.path, window, {"DEV-DA2": "T2"})
        self.assertEqual(
            "exact", report["aggregate"]["metrics"]["input_tokens_per_accepted_dev"]["status"]
        )


class StaticInvariantTests(unittest.TestCase):
    """Requirement 19, plus report-shape versioning discipline."""

    def test_ai_runtime_port_is_unchanged(self):
        self.assertEqual(
            {"adapter_name": "str", "adapter_version": "str"},
            {name: str(value) for name, value in AIRuntimePort.__annotations__.items()},
        )
        self.assertEqual(
            ["self", "invocation", "input_text", "capability", "start_control"],
            list(inspect.signature(AIRuntimePort.start).parameters),
        )

    def test_report_schema_versions_are_independently_declared(self):
        self.assertEqual(2, cost_baseline.REPORT_SCHEMA_VERSION)
        self.assertEqual(1, CONTEXT_EFFECT_REPORT_SCHEMA_VERSION)

    def test_context_effect_module_does_not_couple_into_cost_baseline_source(self):
        # cost_baseline.py is not modified by DEV-019: its delivery-accounting
        # field-name pattern is intact, and it gains no reference to the new
        # context-effect module.
        source = (ROOT / "src/ai_execution/cost_baseline.py").read_text(encoding="utf-8")
        self.assertIn("_per_accepted_dev", source)
        self.assertNotIn("context_effect", source)


if __name__ == "__main__":
    unittest.main()
