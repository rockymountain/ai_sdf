from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ai_execution.claude_adapter import ClaudeRuntimeAdapter
from ai_execution.codex_adapter import _map_breakdown as map_codex_breakdown
from ai_execution.cost_baseline import BaselineEvidenceError, MeasurementWindow, build_report
from ai_execution.model import (
    ContextStrategy,
    ControlledAIInvocation,
    HumanAuthorization,
    InvocationPurpose,
    ModelSelectionStrategy,
    TerminalStatus,
    UsageStatus,
)
from ai_execution.runtime import (
    CapabilityProfile,
    RuntimeStartControl,
    StartDisposition,
)


AUTH = HumanAuthorization(
    "project-owner",
    "2026-09-24T10:00:00+07:00",
    "authorize deterministic review",
    "approved",
)


def invocation(purpose=InvocationPurpose.implementation, **changes):
    values = {
        "dev_task": "DEV-017",
        "traceability_level": "T2",
        "execution_scope_id": "scope-17",
        "objective_id": "DEV-017",
        "run_id": "run-17",
        "invocation_id": "inv-17",
        "source_revision": "a" * 40,
        "invocation_purpose": purpose,
        "model_selection_strategy": ModelSelectionStrategy.fixed,
        "context_strategy": ContextStrategy.chat_heavy,
        "requested_model": "declared-model",
        "requested_reasoning_effort": None,
        "reservation_id": "reservation-17" if purpose is InvocationPurpose.implementation else None,
        "candidate_attempt_number": 1 if purpose is InvocationPurpose.implementation else None,
        "human_authorization": AUTH if purpose in {
            InvocationPurpose.review,
            InvocationPurpose.acceptance_validation,
            InvocationPurpose.orchestration,
        } else None,
    }
    values.update(changes)
    return ControlledAIInvocation(**values)


class FakeProcess:
    def __init__(self, events=(), exit_code=0):
        self.stdout = [json.dumps(event) + "\n" for event in events]
        self.exit_code = exit_code
        self.terminated = False

    def poll(self):
        return self.exit_code if self.terminated else None

    def wait(self, timeout=None):
        return self.exit_code

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.terminated = True


class ProcessFactory:
    def __init__(self, process=None, error=None):
        self.process = process
        self.error = error
        self.calls = []

    def __call__(self, command, **options):
        self.calls.append((command, options))
        if self.error:
            raise self.error
        return self.process


class ClaudeAdapterTests(unittest.TestCase):
    def adapter(self, factory):
        return ClaudeRuntimeAdapter(
            repo=str(ROOT),
            executable="claude-test",
            runtime_version="test-version",
            process_factory=factory,
        )

    def test_accepted_start_terminal_identity_tool_and_exact_usage_mapping(self):
        process = FakeProcess(
            (
                {"type": "system", "subtype": "init", "session_id": "session-1"},
                {
                    "type": "assistant",
                    "session_id": "session-1",
                    "message": {
                        "model": "observed-claude",
                        "content": [{"type": "tool_use", "name": "Read"}],
                    },
                },
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "session_id": "session-1",
                    "usage": {
                        "input_tokens": 8,
                        "cache_creation_input_tokens": 2,
                        "cache_read_input_tokens": 4,
                        "output_tokens": 3,
                        "service_tier": "standard",
                    },
                },
            )
        )
        starts = []
        control = RuntimeStartControl(starts.append)
        adapter = self.adapter(ProcessFactory(process))
        handle = adapter.start(
            invocation(), "implement", CapabilityProfile.implementation(), control
        )
        snapshots = []
        result = adapter.observe(handle, snapshots.append)
        self.assertEqual(StartDisposition.accepted, starts[-1].disposition)
        self.assertEqual(TerminalStatus.success, result.terminal_status)
        self.assertEqual(UsageStatus.exact, result.snapshot.usage.usage_status)
        self.assertEqual(14, result.snapshot.usage.input_tokens)
        self.assertEqual(3, result.snapshot.usage.output_tokens)
        self.assertEqual(17, result.snapshot.usage.total_tokens)
        self.assertEqual(4, result.snapshot.usage.cached_input_tokens)
        self.assertEqual("session-1", result.snapshot.runtime_session_id)
        self.assertIsNone(result.snapshot.runtime_invocation_id)
        self.assertEqual("observed-claude", result.snapshot.observed_model)
        self.assertEqual(1, result.snapshot.tool_item_count)
        metadata = result.snapshot.runtime_native_metadata
        self.assertEqual(
            [
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
                "input_tokens",
                "output_tokens",
                "service_tier",
            ],
            metadata["provider_usage_keys"],
        )
        self.assertEqual(
            {
                "input_tokens": 8,
                "cache_creation_input_tokens": 2,
                "cache_read_input_tokens": 4,
                "output_tokens": 3,
            },
            metadata["provider_usage"],
        )
        self.assertNotIn("service_tier", metadata["provider_usage"])

    def test_definite_local_nonstart_and_uncertain_start_are_distinct(self):
        starts = []
        with self.assertRaises(OSError):
            self.adapter(ProcessFactory(error=OSError("missing"))).start(
                invocation(), "implement", CapabilityProfile.implementation(),
                RuntimeStartControl(starts.append),
            )
        self.assertEqual(StartDisposition.not_started, starts[-1].disposition)

        starts = []
        adapter = self.adapter(ProcessFactory(FakeProcess(({"type": "system"},), 1)))
        handle = adapter.start(
            invocation(), "implement", CapabilityProfile.implementation(),
            RuntimeStartControl(starts.append),
        )
        result = adapter.observe(handle, lambda _: None)
        self.assertEqual(StartDisposition.uncertain, starts[-1].disposition)
        self.assertEqual(TerminalStatus.failure, result.terminal_status)
        self.assertEqual(UsageStatus.unknown, result.snapshot.usage.usage_status)
        self.assertIsNone(result.snapshot.runtime_session_id)
        self.assertIsNone(result.snapshot.runtime_invocation_id)

    def test_incomplete_usage_stays_unknown_and_retains_only_emitted_raw_evidence(self):
        process = FakeProcess(({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "usage": {"input_tokens": 8, "output_tokens": 3},
        },))
        adapter = self.adapter(ProcessFactory(process))
        handle = adapter.start(
            invocation(), "implement", CapabilityProfile.implementation(), RuntimeStartControl()
        )
        result = adapter.observe(handle, lambda _: None)
        self.assertEqual(UsageStatus.unknown, result.snapshot.usage.usage_status)
        metadata = result.snapshot.runtime_native_metadata
        self.assertEqual(["input_tokens", "output_tokens"], metadata["provider_usage_keys"])
        self.assertEqual(
            {"input_tokens": 8, "output_tokens": 3}, metadata["provider_usage"]
        )
        self.assertNotIn("cache_creation_input_tokens", metadata["provider_usage"])
        self.assertNotIn("cache_read_input_tokens", metadata["provider_usage"])
        adapter.interrupt(handle)
        self.assertTrue(process.terminated)

    def test_malformed_claude_component_fails_closed_without_hiding_raw_value(self):
        process = FakeProcess(({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "usage": {
                "input_tokens": 8,
                "cache_creation_input_tokens": -1,
                "cache_read_input_tokens": 4,
                "output_tokens": 3,
            },
        },))
        adapter = self.adapter(ProcessFactory(process))
        handle = adapter.start(
            invocation(), "implement", CapabilityProfile.implementation(), RuntimeStartControl()
        )
        result = adapter.observe(handle, lambda _: None)
        self.assertEqual(UsageStatus.unknown, result.snapshot.usage.usage_status)
        self.assertEqual(
            -1,
            result.snapshot.runtime_native_metadata["provider_usage"]
            ["cache_creation_input_tokens"],
        )

    def test_codex_usage_remains_exact_only_for_consistent_canonical_total(self):
        exact = map_codex_breakdown(SimpleNamespace(
            input_tokens=8,
            output_tokens=3,
            total_tokens=11,
            cached_input_tokens=4,
            reasoning_output_tokens=2,
        ))
        self.assertEqual(UsageStatus.exact, exact.usage_status)
        self.assertEqual(11, exact.total_tokens)
        inconsistent = map_codex_breakdown(SimpleNamespace(
            input_tokens=8,
            output_tokens=3,
            total_tokens=12,
            cached_input_tokens=4,
            reasoning_output_tokens=2,
        ))
        self.assertEqual(UsageStatus.unknown, inconsistent.usage_status)

    def test_provider_cache_vocabulary_stays_out_of_generic_accounting(self):
        provider_fields = ("cache_creation_input_tokens", "cache_read_input_tokens")
        generic_paths = (
            ROOT / "src/ai_execution/model.py",
            ROOT / "src/ai_execution/runtime.py",
            ROOT / "src/ai_execution/policy.py",
            ROOT / "src/ai_execution/cost_baseline.py",
        )
        for path in generic_paths:
            contents = path.read_text(encoding="utf-8")
            for field in provider_fields:
                with self.subTest(path=path, field=field):
                    self.assertNotIn(field, contents)

    def test_capability_is_bound_to_purpose_and_runtime_cannot_escalate_review(self):
        review = invocation(InvocationPurpose.review)
        starts = []
        with self.assertRaisesRegex(ValueError, "attempt identity"):
            self.adapter(ProcessFactory()).start(
                review, "review", CapabilityProfile.implementation(), RuntimeStartControl(starts.append)
            )
        self.assertEqual(StartDisposition.not_started, starts[-1].disposition)

        factory = ProcessFactory(FakeProcess())
        self.adapter(factory).start(
            review, "review", CapabilityProfile.read_only(), RuntimeStartControl()
        )
        command, options = factory.calls[0]
        self.assertNotIn("--cwd", command)
        self.assertNotIn("--permission-prompts", command)
        self.assertEqual(str(ROOT.resolve()), options["cwd"])
        self.assertEqual("plan", command[command.index("--permission-mode") + 1])
        self.assertEqual("Read,Glob,Grep", command[command.index("--tools") + 1])
        self.assertIn("--strict-mcp-config", command)
        self.assertNotIn("--mcp-config", command)

    def test_implementation_command_uses_accepted_edits_and_reasoning_is_explicit(self):
        no_effort_factory = ProcessFactory(FakeProcess())
        self.adapter(no_effort_factory).start(
            invocation(requested_reasoning_effort=None),
            "implement",
            CapabilityProfile.implementation(),
            RuntimeStartControl(),
        )
        no_effort_command, options = no_effort_factory.calls[0]
        self.assertEqual(str(ROOT.resolve()), options["cwd"])
        self.assertNotIn("--cwd", no_effort_command)
        self.assertNotIn("--permission-prompts", no_effort_command)
        self.assertEqual(
            "acceptEdits",
            no_effort_command[no_effort_command.index("--permission-mode") + 1],
        )
        self.assertNotIn("--effort", no_effort_command)
        self.assertNotIn("--strict-mcp-config", no_effort_command)

        explicit_factory = ProcessFactory(FakeProcess())
        self.adapter(explicit_factory).start(
            invocation(requested_reasoning_effort="medium"),
            "implement",
            CapabilityProfile.implementation(),
            RuntimeStartControl(),
        )
        explicit_command = explicit_factory.calls[0][0]
        self.assertEqual("medium", explicit_command[explicit_command.index("--effort") + 1])


class OperatorSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("ai_execution_operator", ROOT / "tools/ai_execution.py")
        assert spec and spec.loader
        cls.operator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.operator)

    def test_selection_is_explicit_and_unknown_adapter_fails(self):
        codex = self.operator.runtime_adapter(
            Namespace(runtime_adapter="codex", claude_executable=None), ROOT
        )
        self.assertEqual("codex", codex.adapter_name)
        with self.assertRaisesRegex(ValueError, "unsupported runtime adapter"):
            self.operator.runtime_adapter(
                Namespace(runtime_adapter="automatic", claude_executable=None), ROOT
            )

    def test_explicit_claude_selection_uses_declared_executable_without_runtime_call(self):
        # Version discovery must not happen at operator/construction time: it now
        # runs inside ClaudeRuntimeAdapter.start(), after the gateway has already
        # persisted governed invocation-start/reservation state (TEST-018).
        calls = []

        def version_runner(command, **options):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="observed-version\n")

        adapter = self.operator.runtime_adapter(
            Namespace(runtime_adapter="claude", claude_executable="claude-test"),
            ROOT,
            version_runner=version_runner,
        )
        self.assertEqual("claude", adapter.adapter_name)
        self.assertEqual("claude-test", adapter.executable)
        self.assertEqual([], calls)
        self.assertIsNone(adapter.runtime_version)

    def test_operator_maps_explicit_none_and_preserves_explicit_reasoning_value(self):
        self.assertIsNone(self.operator._reasoning_effort("none"))
        self.assertEqual("medium", self.operator._reasoning_effort("medium"))


class PurposeScopedMeasurementTests(unittest.TestCase):
    def setUp(self):
        runtime_root = ROOT / ".sdf" / "runtime"
        runtime_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=runtime_root)
        self.database = Path(self.temporary.name) / "evidence.sqlite3"
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE invocations (
                invocation_id TEXT PRIMARY KEY, dev_task TEXT NOT NULL,
                execution_scope_id TEXT NOT NULL, started_at TEXT NOT NULL,
                completed_at TEXT, invocation_purpose TEXT NOT NULL,
                adapter_name TEXT, terminal_status TEXT, usage_status TEXT,
                input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER,
                requested_model TEXT, requested_reasoning_effort TEXT,
                model_selection_strategy TEXT NOT NULL, routing_policy_version TEXT,
                context_strategy TEXT NOT NULL, observed_model TEXT
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
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temporary.cleanup()

    def window(self):
        treatment = lambda adapter, model: {
            "runtime_adapter": adapter,
            "requested_model": model,
            "requested_reasoning_effort": None,
            "model_selection_strategy": "fixed",
            "routing_policy_version": None,
            "context_strategy": "chat-heavy",
        }
        return MeasurementWindow.from_mapping({
            "id": "dual-runtime-window",
            "included_dev_tasks": ["DEV-017"],
            "task_mix": {"implementation": 1},
            "trace_level_mix": {"T0": 0, "T1": 0, "T2": 1},
            "review_policy": "all review usage retained",
            "acceptance_policy": "governed outcome",
            "evidence_boundary": {
                "start_inclusive": "2026-09-24T00:00:00.000Z",
                "end_exclusive": "2026-09-25T00:00:00.000Z",
            },
            "purpose_treatments": {
                "implementation": treatment("claude", "claude-declared"),
                "continuation": treatment("claude", "claude-declared"),
                "review": treatment("codex", "gpt-declared"),
            },
            "automatic_model_routing": False,
            "context_optimization": False,
        })

    def add(self, identity, purpose, adapter, model, tokens=(5, 2, 7), usage="exact"):
        connection = sqlite3.connect(self.database)
        connection.execute(
            "INSERT INTO invocations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                identity, "DEV-017", "scope-17", "2026-09-24T01:00:00.000Z",
                "2026-09-24T01:01:00.000Z", purpose, adapter, "success", usage,
                *(tokens if usage == "exact" else (None, None, None)),
                model, None, "fixed", None, "chat-heavy", None,
            ),
        )
        connection.commit()
        connection.close()

    def finish(self):
        connection = sqlite3.connect(self.database)
        connection.execute(
            "INSERT INTO dev_outcomes VALUES (?,?,?)",
            ("DEV-017", 1, "2026-09-24T02:00:00.000Z"),
        )
        connection.commit()
        connection.close()

    def report(self):
        return build_report(self.database, self.window(), {"DEV-017": "T2"})

    def test_claude_implementation_and_codex_review_share_one_exact_dev_total(self):
        self.add("impl", "implementation", "claude", "claude-declared", (10, 4, 14))
        self.add("review", "review", "codex", "gpt-declared", (5, 1, 6))
        self.finish()
        dev = self.report()["dev_tasks"][0]
        self.assertEqual("consistent", dev["profile_consistency"])
        self.assertEqual(20, dev["exact_total"]["total_tokens"])
        self.assertEqual(14, dev["by_invocation_purpose"]["implementation"]["exact_total"]["total_tokens"])
        self.assertEqual(6, dev["by_runtime_adapter"]["codex"]["exact_total"]["total_tokens"])

    def test_mismatch_undeclared_purpose_and_missing_identity_remain_visible(self):
        cases = (
            ("wrong-model", "implementation", "claude", "wrong", "requested_model"),
            ("wrong-adapter", "review", "claude", "gpt-declared", "runtime_adapter"),
            ("undeclared", "orchestration", "codex", "gpt-declared", "undeclared_purpose"),
            ("missing", "review", None, "gpt-declared", "runtime_adapter_missing"),
        )
        for identity, purpose, adapter, model, reason in cases:
            with self.subTest(reason=reason):
                self.add(identity, purpose, adapter, model)
        self.finish()
        report = self.report()
        dev = report["dev_tasks"][0]
        self.assertEqual("incomplete", dev["profile_consistency"])
        for reason in ("requested_model", "runtime_adapter", "undeclared_purpose", "runtime_adapter_missing"):
            self.assertGreater(dev["profile_mismatch_reasons"][reason], 0)
        self.assertEqual(
            "unavailable",
            report["aggregate"]["metrics"]["total_tokens_per_accepted_dev"]["status"],
        )

    def test_unknown_continuation_usage_is_not_zero_and_known_subtotals_remain(self):
        self.add("impl", "implementation", "claude", "claude-declared", (10, 4, 14))
        self.add("continue", "continuation", "claude", "claude-declared", usage="unknown")
        self.add("review", "review", "codex", "gpt-declared", (5, 1, 6))
        self.finish()
        dev = self.report()["dev_tasks"][0]
        self.assertEqual("incomplete", dev["usage_completeness"])
        self.assertEqual(20, dev["known_subtotal"]["total_tokens"])
        self.assertNotIn("exact_total", dev)
        self.assertEqual(1, dev["by_invocation_purpose"]["continuation"]["unknown_usage_count"])

    def test_generic_reporting_rejects_inconsistent_canonical_total(self):
        self.add("impl", "implementation", "claude", "claude-declared", (10, 4, 15))
        self.finish()
        with self.assertRaisesRegex(BaselineEvidenceError, "inconsistent exact canonical usage"):
            self.report()


if __name__ == "__main__":
    unittest.main()
