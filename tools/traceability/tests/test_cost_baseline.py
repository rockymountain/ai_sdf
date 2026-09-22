from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ai_execution.cost_baseline import (
    BaselineEvidenceError,
    MeasurementWindow,
    build_report,
    canonical_json,
    load_trace_levels,
)


class CostBaselineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database = self.root / "evidence.sqlite3"
        self._create_database(version=3)

    def tearDown(self):
        self.temporary.cleanup()

    def window(self, tasks=("DEV-A",), levels=None, **changes):
        levels = levels or {"T0": 0, "T1": len(tasks), "T2": 0}
        value = {
            "id": "m3-control-window-1",
            "included_dev_tasks": list(tasks),
            "task_mix": {"implementation": len(tasks)},
            "trace_level_mix": levels,
            "review_policy": "all retained review calls are included",
            "acceptance_policy": "immutable dev_outcomes evidence",
            "evidence_boundary": {
                "start_inclusive": "2026-01-01T00:00:00.000Z",
                "end_exclusive": "2026-02-01T00:00:00.000Z",
            },
            "requested_model": "gpt-5.6-sol",
            "requested_reasoning_effort": "medium",
            "model_selection_strategy": "fixed",
            "routing_policy_version": None,
            "context_strategy": "chat-heavy",
            "automatic_model_routing": False,
            "context_optimization": False,
        }
        value.update(changes)
        return MeasurementWindow.from_mapping(value)

    def report(self, window=None, trace=None):
        window = window or self.window()
        if trace is None:
            trace = {task: "T1" for task in window.included_dev_tasks}
        return build_report(self.database, window, trace)

    def _create_database(self, version):
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE invocations (
                invocation_id TEXT PRIMARY KEY,
                dev_task TEXT NOT NULL,
                execution_scope_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                invocation_purpose TEXT NOT NULL,
                terminal_status TEXT,
                usage_status TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                total_tokens INTEGER,
                requested_model TEXT,
                requested_reasoning_effort TEXT,
                model_selection_strategy TEXT NOT NULL,
                routing_policy_version TEXT,
                context_strategy TEXT NOT NULL,
                observed_model TEXT
            );
            CREATE TABLE dev_outcomes (
                dev_task TEXT PRIMARY KEY,
                task_accepted INTEGER NOT NULL,
                finalized_at TEXT NOT NULL
            );
            """
        )
        if version == 3:
            connection.executescript(
                """
                CREATE TABLE execution_scopes (
                    execution_scope_id TEXT PRIMARY KEY,
                    dev_task TEXT NOT NULL
                );
                CREATE TABLE attempts (
                    execution_scope_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    PRIMARY KEY (execution_scope_id, attempt_number)
                );
                CREATE TABLE invocation_attempts (
                    invocation_id TEXT PRIMARY KEY,
                    attempt_number INTEGER
                );
                """
            )
        connection.execute(f"PRAGMA user_version={version}")
        connection.commit()
        connection.close()

    def invocation(
        self,
        invocation_id="inv-1",
        dev_task="DEV-A",
        started_at="2026-01-15T00:00:00.000Z",
        completed_at="2026-01-15T00:01:00.000Z",
        purpose="implementation",
        terminal="success",
        usage="exact",
        tokens=(10, 5, 15),
        observed_model=None,
        **profile,
    ):
        values = {
            "requested_model": "gpt-5.6-sol",
            "requested_reasoning_effort": "medium",
            "model_selection_strategy": "fixed",
            "routing_policy_version": None,
            "context_strategy": "chat-heavy",
        }
        values.update(profile)
        connection = sqlite3.connect(self.database)
        connection.execute(
            "INSERT INTO invocations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                invocation_id,
                dev_task,
                f"scope-{dev_task}",
                started_at,
                completed_at,
                purpose,
                terminal,
                usage,
                *(tokens if usage == "exact" else (None, None, None)),
                values["requested_model"],
                values["requested_reasoning_effort"],
                values["model_selection_strategy"],
                values["routing_policy_version"],
                values["context_strategy"],
                observed_model,
            ),
        )
        connection.commit()
        connection.close()

    def outcome(
        self,
        task="DEV-A",
        accepted=True,
        finalized_at="2026-01-20T00:00:00.000Z",
    ):
        connection = sqlite3.connect(self.database)
        connection.execute(
            "INSERT INTO dev_outcomes VALUES (?,?,?)", (task, int(accepted), finalized_at)
        )
        connection.commit()
        connection.close()

    def attempt(self, task="DEV-A", count=1):
        connection = sqlite3.connect(self.database)
        scope = f"scope-{task}"
        connection.execute("INSERT INTO execution_scopes VALUES (?,?)", (scope, task))
        connection.executemany(
            "INSERT INTO attempts VALUES (?,?,?)",
            [(scope, number, "FAILED" if number < count else "PASSED") for number in range(1, count + 1)],
        )
        invocation_ids = [
            row[0]
            for row in connection.execute(
                "SELECT invocation_id FROM invocations WHERE dev_task=? ORDER BY started_at, invocation_id",
                (task,),
            )
        ]
        connection.executemany(
            "INSERT INTO invocation_attempts VALUES (?,?)",
            [
                (invocation_id, min(index + 1, count))
                for index, invocation_id in enumerate(invocation_ids)
            ],
        )
        connection.commit()
        connection.close()

    def test_window_records_the_locked_profile_and_explicit_boundary(self):
        value = self.window().report_value()
        self.assertEqual("gpt-5.6-sol", value["requested_model"])
        self.assertEqual("medium", value["requested_reasoning_effort"])
        self.assertEqual("fixed", value["model_selection_strategy"])
        self.assertIsNone(value["routing_policy_version"])
        self.assertEqual("chat-heavy", value["context_strategy"])
        self.assertFalse(value["automatic_model_routing"])
        self.assertFalse(value["context_optimization"])
        self.assertEqual(
            {
                "start_inclusive": "2026-01-01T00:00:00.000Z",
                "end_exclusive": "2026-02-01T00:00:00.000Z",
            },
            value["evidence_boundary"],
        )

    def test_every_locked_profile_field_must_be_explicit(self):
        required = (
            "requested_model",
            "requested_reasoning_effort",
            "model_selection_strategy",
            "routing_policy_version",
            "context_strategy",
            "automatic_model_routing",
            "context_optimization",
        )
        for field in required:
            declaration = self.window().report_value()
            del declaration[field]
            with self.subTest(field=field), self.assertRaisesRegex(
                BaselineEvidenceError, "invalid measurement window"
            ):
                MeasurementWindow.from_mapping(declaration)

    def test_window_rejects_any_profile_drift(self):
        for field, value in (
            ("requested_model", "other"),
            ("requested_reasoning_effort", "high"),
            ("model_selection_strategy", "manual"),
            ("routing_policy_version", "route-1"),
            ("context_strategy", "manual-context-pack"),
            ("automatic_model_routing", True),
            ("context_optimization", True),
        ):
            with self.subTest(field=field), self.assertRaises(BaselineEvidenceError):
                self.window(**{field: value})

    def test_window_requires_explicit_task_and_trace_mixes(self):
        with self.assertRaisesRegex(BaselineEvidenceError, "task_mix"):
            self.window(task_mix={})
        with self.assertRaisesRegex(BaselineEvidenceError, "trace_level_mix"):
            self.window(trace_level_mix={"T1": 1})

    def test_evidence_before_boundary_is_excluded(self):
        self.invocation(
            started_at="2025-12-31T23:58:00.000Z",
            completed_at="2025-12-31T23:59:00.000Z",
        )
        self.outcome()
        report = self.report()
        self.assertEqual(0, report["aggregate"]["invocation_count"])
        self.assertEqual("incomplete", report["aggregate"]["usage_completeness"])

    def test_evidence_inside_boundary_is_included(self):
        self.invocation()
        self.outcome()
        report = self.report()
        self.assertEqual(1, report["aggregate"]["invocation_count"])
        self.assertEqual(1, report["aggregate"]["accepted_dev_count"])

    def test_evidence_outside_boundary_is_excluded(self):
        self.invocation(
            started_at="2026-02-01T00:00:00.000Z",
            completed_at="2026-02-01T00:01:00.000Z",
        )
        self.outcome(finalized_at="2026-02-01T00:00:00.000Z")
        report = self.report()
        self.assertEqual(0, report["aggregate"]["invocation_count"])
        self.assertEqual(1, report["aggregate"]["unfinalized_dev_count"])

    def test_invocation_not_terminal_by_boundary_end_is_excluded(self):
        self.invocation(
            started_at="2026-01-31T23:58:00.000Z",
            completed_at="2026-02-01T00:01:00.000Z",
        )
        self.outcome()
        self.assertEqual(0, self.report()["aggregate"]["invocation_count"])

    def test_out_of_window_append_does_not_change_canonical_report_bytes(self):
        self.invocation()
        self.outcome()
        before = canonical_json(self.report())
        self.invocation(
            "inv-outside",
            started_at="2026-02-02T00:00:00.000Z",
            completed_at="2026-02-02T00:01:00.000Z",
            tokens=(100, 100, 200),
        )
        after = canonical_json(self.report())
        self.assertEqual(before.encode(), after.encode())

    def test_bounded_attempt_count_uses_only_authoritative_linked_identities(self):
        self.invocation("inv-inside")
        self.invocation(
            "inv-outside",
            started_at="2026-02-02T00:00:00.000Z",
            completed_at="2026-02-02T00:01:00.000Z",
        )
        self.outcome()
        self.attempt(count=2)
        report = self.report()
        self.assertEqual(1, report["aggregate"]["attempt_count"])
        self.assertEqual(1, len(report["attempts"]["records"]))

    def test_exact_usage_aggregates_and_enables_exact_token_ratios(self):
        self.invocation()
        self.outcome()
        report = self.report()
        self.assertEqual({"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}, report["aggregate"]["exact_total"])
        self.assertEqual("exact", report["aggregate"]["metrics"]["total_tokens_per_accepted_dev"]["status"])

    def test_unknown_usage_preserves_subtotal_without_exact_total(self):
        self.invocation("inv-1", tokens=(10, 5, 15))
        self.invocation("inv-2", usage="unknown")
        self.outcome()
        aggregate = self.report()["aggregate"]
        self.assertEqual("incomplete", aggregate["usage_completeness"])
        self.assertEqual(15, aggregate["known_subtotal"]["total_tokens"])
        self.assertNotIn("exact_total", aggregate)
        metric = aggregate["metrics"]["total_tokens_per_accepted_dev"]
        self.assertEqual("unavailable", metric["status"])
        self.assertEqual(15, metric["known_numerator_subtotal"])
        self.assertEqual(1, metric["denominator"])
        self.assertEqual("incomplete", metric["completeness_state"])

    def test_declared_dev_without_telemetry_remains_in_denominator_and_incomplete(self):
        window = self.window(("DEV-A", "DEV-B"), {"T0": 0, "T1": 2, "T2": 0})
        self.invocation()
        self.outcome()
        self.outcome("DEV-B", False)
        aggregate = self.report(window, {"DEV-A": "T1", "DEV-B": "T1"})["aggregate"]
        self.assertEqual(2, aggregate["declared_dev_count"])
        self.assertEqual(1, aggregate["devs_with_invocation_evidence"])
        self.assertEqual("incomplete", aggregate["usage_completeness"])
        self.assertEqual("unavailable", aggregate["metrics"]["calls_per_accepted_dev"]["status"])

    def test_rejected_dev_cost_is_not_filtered(self):
        window = self.window(("DEV-A", "DEV-B"), {"T0": 0, "T1": 2, "T2": 0})
        self.invocation(tokens=(10, 5, 15))
        self.invocation("inv-2", "DEV-B", tokens=(20, 10, 30))
        self.outcome()
        self.outcome("DEV-B", False)
        aggregate = self.report(window, {"DEV-A": "T1", "DEV-B": "T1"})["aggregate"]
        self.assertEqual(45, aggregate["exact_total"]["total_tokens"])
        self.assertEqual(1, aggregate["rejected_dev_count"])

    def test_failed_retry_review_and_orchestration_invocations_are_included(self):
        self.invocation("inv-1", purpose="implementation", terminal="error", tokens=(1, 1, 2))
        self.invocation("inv-2", purpose="implementation", tokens=(2, 1, 3))
        self.invocation("inv-3", purpose="review", tokens=(3, 1, 4))
        self.invocation("inv-4", purpose="orchestration", tokens=(4, 1, 5))
        self.outcome()
        dev = self.report()["dev_tasks"][0]
        self.assertEqual(4, dev["invocation_count"])
        self.assertEqual(14, dev["exact_total"]["total_tokens"])
        self.assertEqual({"implementation": 2, "orchestration": 1, "review": 1}, dev["invocation_purposes"])
        self.assertEqual(1, dev["terminal_statuses"]["error"])

    def test_trace_levels_are_reported_separately_and_in_aggregate(self):
        tasks = ("DEV-0", "DEV-1", "DEV-2")
        window = self.window(tasks, {"T0": 1, "T1": 1, "T2": 1}, task_mix={"implementation": 3})
        trace = {"DEV-0": "T0", "DEV-1": "T1", "DEV-2": "T2"}
        for index, task in enumerate(tasks):
            self.invocation(f"inv-{index}", task, tokens=(index + 1, 1, index + 2))
            self.outcome(task)
        report = self.report(window, trace)
        self.assertEqual(3, report["aggregate"]["declared_dev_count"])
        self.assertEqual([1, 1, 1], [report["by_trace_level"][level]["declared_dev_count"] for level in ("T0", "T1", "T2")])

    def test_unfinalized_outcome_is_visible_and_rates_are_unavailable(self):
        self.invocation()
        aggregate = self.report()["aggregate"]
        self.assertEqual(1, aggregate["unfinalized_dev_count"])
        self.assertEqual("unavailable", aggregate["metrics"]["acceptance_rate"]["status"])

    def test_acceptance_rate_uses_declared_dev_set(self):
        window = self.window(("DEV-A", "DEV-B"), {"T0": 0, "T1": 2, "T2": 0})
        for task, accepted in (("DEV-A", True), ("DEV-B", False)):
            self.invocation(f"inv-{task[-1]}", task)
            self.outcome(task, accepted)
        metric = self.report(window, {"DEV-A": "T1", "DEV-B": "T1"})["aggregate"]["metrics"]["acceptance_rate"]
        self.assertEqual((1, 2), (metric["numerator"], metric["denominator"]))

    def test_attempt_count_comes_from_authoritative_attempt_rows(self):
        self.invocation("inv-1")
        self.invocation("inv-2")
        self.invocation("inv-3")
        self.outcome()
        self.attempt(count=2)
        aggregate = self.report()["aggregate"]
        self.assertEqual(3, aggregate["invocation_count"])
        self.assertEqual(2, aggregate["attempt_count"])
        self.assertEqual("2/1", aggregate["metrics"]["attempts_per_accepted_dev"]["exact_ratio"])

    def test_accepted_dev_without_invocation_makes_attempt_kpi_unavailable(self):
        self.outcome()
        metric = self.report()["aggregate"]["metrics"]["attempts_per_accepted_dev"]
        self.assertEqual("unavailable", metric["status"])
        self.assertEqual("declared_dev_invocation_coverage_incomplete", metric["reason"])
        self.assertEqual("incomplete", metric["completeness_state"])

    def test_rejected_dev_missing_invocation_blocks_aggregate_attempt_kpi(self):
        window = self.window(("DEV-A", "DEV-B"), {"T0": 0, "T1": 2, "T2": 0})
        self.invocation()
        self.outcome()
        self.outcome("DEV-B", False)
        self.attempt()
        metric = self.report(
            window, {"DEV-A": "T1", "DEV-B": "T1"}
        )["aggregate"]["metrics"]["attempts_per_accepted_dev"]
        self.assertEqual("unavailable", metric["status"])
        self.assertEqual("declared_dev_invocation_coverage_incomplete", metric["reason"])

    def test_complete_invocation_and_attempt_coverage_allows_exact_attempt_kpi(self):
        window = self.window(("DEV-A", "DEV-B"), {"T0": 0, "T1": 2, "T2": 0})
        for task, accepted in (("DEV-A", True), ("DEV-B", False)):
            self.invocation(f"inv-{task[-1]}", task)
            self.outcome(task, accepted)
            self.attempt(task)
        metric = self.report(
            window, {"DEV-A": "T1", "DEV-B": "T1"}
        )["aggregate"]["metrics"]["attempts_per_accepted_dev"]
        self.assertEqual("exact", metric["status"])
        self.assertEqual("2/1", metric["exact_ratio"])

    def test_attempt_usage_completeness_is_derived_from_linked_invocations(self):
        self.invocation("inv-1", tokens=(2, 1, 3))
        self.invocation("inv-2", usage="unknown")
        self.outcome()
        self.attempt(count=1)
        attempt = self.report()["attempts"]["records"][0]
        self.assertEqual("incomplete", attempt["usage_completeness"])
        self.assertEqual(3, attempt["known_subtotal"]["total_tokens"])
        self.assertNotIn("exact_total", attempt)

    def test_schema_v2_is_read_without_migration_and_attempts_are_unavailable(self):
        self.database.unlink()
        self._create_database(version=2)
        self.invocation()
        self.outcome()
        report = self.report()
        self.assertEqual(2, report["evidence"]["database_schema_version"])
        self.assertEqual("unavailable_legacy_schema_v2", report["evidence"]["attempt_evidence"])
        self.assertEqual("unavailable", report["aggregate"]["metrics"]["attempts_per_accepted_dev"]["status"])
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(2, connection.execute("PRAGMA user_version").fetchone()[0])

    def test_report_access_does_not_change_database_bytes_or_schema(self):
        self.invocation()
        self.outcome()
        before = hashlib.sha256(self.database.read_bytes()).hexdigest()
        self.report()
        after = hashlib.sha256(self.database.read_bytes()).hexdigest()
        self.assertEqual(before, after)
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(3, connection.execute("PRAGMA user_version").fetchone()[0])

    def test_repeated_report_serialization_is_byte_stable(self):
        self.invocation()
        self.outcome()
        first = canonical_json(self.report())
        second = canonical_json(self.report())
        self.assertEqual(first.encode(), second.encode())
        self.assertNotIn("generated_at", first)

    def test_trace_evidence_must_exactly_cover_the_window(self):
        with self.assertRaisesRegex(BaselineEvidenceError, "exactly"):
            self.report(trace={})
        with self.assertRaisesRegex(BaselineEvidenceError, "trace_level_mix"):
            self.report(trace={"DEV-A": "T2"})

    def test_trace_levels_load_from_canonical_shape(self):
        path = self.root / "traceability.yaml"
        path.write_text("version: 1\ntasks:\n  DEV-A:\n    level: T1\n", encoding="utf-8")
        self.assertEqual({"DEV-A": "T1"}, load_trace_levels(path, ("DEV-A",)))

    def test_profile_mismatch_blocks_exact_token_kpi_without_relabeling_observed_identity(self):
        self.invocation(requested_model="other", observed_model=None)
        self.outcome()
        dev = self.report()["dev_tasks"][0]
        self.assertEqual("incomplete", dev["profile_consistency"])
        self.assertEqual(1, dev["observed_model"]["unknown_count"])
        self.assertEqual("unavailable", self.report()["aggregate"]["metrics"]["total_tokens_per_accepted_dev"]["status"])

    def test_report_has_no_file_count_proxy_or_m4_conclusion(self):
        self.invocation()
        self.outcome()
        serialized = canonical_json(self.report())
        self.assertNotIn("file_count", serialized)
        self.assertNotIn("savings", serialized)
        self.assertNotIn("ROI", serialized)
        self.assertNotIn("M4", serialized)


if __name__ == "__main__":
    unittest.main()
