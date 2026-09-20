from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ai_execution.codex_adapter import CodexRuntimeAdapter, _CodexHandle, _map_thread_usage
from ai_execution.gateway import ControlledInvocationGateway, InvocationRejected
from ai_execution.model import (
    ContextStrategy,
    ControlledAIInvocation,
    InvocationPurpose,
    ModelSelectionStrategy,
    TerminalReason,
    TerminalStatus,
    UsageEvidence,
    UsageStatus,
)
from ai_execution.policy import load_watchdog_policy
from ai_execution.runtime import CapabilityProfile, RuntimeResult, RuntimeSnapshot
from ai_execution.store import TelemetryStore


def invocation(**changes) -> ControlledAIInvocation:
    values = {
        "dev_task": "DEV-007",
        "traceability_level": "T2",
        "execution_scope_id": "scope-1",
        "run_id": "run-1",
        "invocation_id": "invocation-1",
        "source_revision": "abc123",
        "invocation_purpose": InvocationPurpose.acceptance_validation,
        "model_selection_strategy": ModelSelectionStrategy.manual,
        "context_strategy": ContextStrategy.chat_heavy,
        "requested_model": "requested-model",
    }
    values.update(changes)
    return ControlledAIInvocation(**values)


class FakeRuntime:
    adapter_name = "fake"
    adapter_version = "1"

    def __init__(self, result: RuntimeResult | None = None):
        self.starts = 0
        self.interrupts = 0
        self.capability = None
        self.interrupted = threading.Event()
        self.result = result or RuntimeResult(
            TerminalStatus.success,
            None,
            RuntimeSnapshot(
                UsageEvidence.exact(3, 2, 5),
                UsageEvidence.exact(7, 3, 10),
                runtime_session_id="session-1",
                runtime_invocation_id="turn-1",
                tool_item_count=1,
            ),
        )

    def start(self, controlled, input_text, capability):
        self.starts += 1
        self.capability = capability
        return SimpleNamespace(
            runtime_session_id=self.result.snapshot.runtime_session_id,
            runtime_invocation_id=self.result.snapshot.runtime_invocation_id,
            runtime_name="fake-runtime",
            runtime_version="1",
        )

    def observe(self, handle, publish):
        publish(self.result.snapshot)
        return self.result

    def interrupt(self, handle):
        self.interrupts += 1
        self.interrupted.set()


class BlockingRuntime(FakeRuntime):
    def observe(self, handle, publish):
        self.interrupted.wait(3)
        return RuntimeResult(
            TerminalStatus.interrupted,
            TerminalReason.other,
            RuntimeSnapshot(UsageEvidence.unknown()),
        )


class EvidenceBlockingRuntime(FakeRuntime):
    def observe(self, handle, publish):
        publish(RuntimeSnapshot(UsageEvidence.exact(5, 2, 7)))
        self.interrupted.wait(3)
        return RuntimeResult(
            TerminalStatus.interrupted,
            TerminalReason.other,
            RuntimeSnapshot(UsageEvidence.exact(5, 2, 7)),
        )


class BrokenStore:
    def record_start(self, *args, **kwargs):
        raise OSError("read only")


class AIExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.temp = Path(self.temporary.name)
        self.repo = self.temp / "repo"
        (self.repo / "constitution").mkdir(parents=True)
        (self.repo / "knowledge/schemas").mkdir(parents=True)
        shutil.copy(
            ROOT / "knowledge/schemas/autonomous-execution-policy.schema.json",
            self.repo / "knowledge/schemas/autonomous-execution-policy.schema.json",
        )
        self.write_policy(600)

    def write_policy(self, value):
        (self.repo / "constitution/policies.yaml").write_text(
            f"version: 1\nautonomous_execution:\n  max_invocation_seconds: {value}\n",
            encoding="utf-8",
        )

    def store(self):
        return TelemetryStore(self.temp / "telemetry.sqlite3")

    def test_missing_mandatory_identity_rejected_before_runtime(self):
        with self.assertRaisesRegex(ValueError, "mandatory invocation identity"):
            invocation(invocation_id="")

    def test_unavailable_store_rejects_before_runtime(self):
        runtime = FakeRuntime()
        gateway = ControlledInvocationGateway(self.repo, BrokenStore(), runtime)
        with self.assertRaisesRegex(InvocationRejected, "telemetry start persistence"):
            gateway.invoke(invocation(), "read only")
        self.assertEqual(0, runtime.starts)

    def test_missing_and_invalid_watchdog_policy_fail_closed(self):
        policy = self.repo / "constitution/policies.yaml"
        policy.unlink()
        with self.assertRaisesRegex(ValueError, "policy unavailable"):
            load_watchdog_policy(self.repo)
        for value in (0, -1, "bad", "true"):
            with self.subTest(value=value):
                self.write_policy(value)
                with self.assertRaises(ValueError):
                    load_watchdog_policy(self.repo)

    def test_watchdog_value_comes_from_canonical_policy(self):
        store = self.store()
        outcome = ControlledInvocationGateway(self.repo, store, FakeRuntime()).invoke(
            invocation(), "read only"
        )
        self.assertEqual(TerminalStatus.success, outcome.terminal_status)
        self.assertEqual(600, store.fetch("invocation-1")["watchdog_seconds"])

    def test_watchdog_interrupts_without_creating_attempt_capacity(self):
        self.write_policy(1)
        store = self.store()
        runtime = BlockingRuntime()
        outcome = ControlledInvocationGateway(self.repo, store, runtime).invoke(
            invocation(), "read only"
        )
        row = store.fetch("invocation-1")
        self.assertEqual(1, runtime.interrupts)
        self.assertEqual(TerminalStatus.timeout, outcome.terminal_status)
        self.assertEqual(UsageStatus.unknown, outcome.usage.usage_status)
        self.assertTrue(outcome.human_attention_required)
        self.assertFalse(outcome.autonomous_follow_on_allowed)
        self.assertNotIn("attempt_number", row)
        self.assertNotIn("reservation_id", row)

    def test_watchdog_retains_exact_usage_observed_before_timeout(self):
        self.write_policy(1)
        outcome = ControlledInvocationGateway(
            self.repo, self.store(), EvidenceBlockingRuntime()
        ).invoke(invocation(), "read only")
        self.assertEqual(TerminalStatus.timeout, outcome.terminal_status)
        self.assertEqual(UsageStatus.exact, outcome.usage.usage_status)
        self.assertEqual(7, outcome.usage.total_tokens)

    def test_exact_core_and_optional_breakdown_semantics(self):
        exact = UsageEvidence.exact(4, 2, 6)
        self.assertEqual(UsageStatus.exact, exact.usage_status)
        self.assertIsNone(exact.cached_input_tokens)
        self.assertIsNone(exact.reasoning_output_tokens)
        with self.assertRaises(ValueError):
            UsageEvidence(UsageStatus.unknown, input_tokens=0)

    def test_terminal_and_usage_status_are_independent(self):
        result = RuntimeResult(
            TerminalStatus.failure,
            TerminalReason.runtime_error,
            RuntimeSnapshot(UsageEvidence.exact(8, 3, 11)),
        )
        outcome = ControlledInvocationGateway(self.repo, self.store(), FakeRuntime(result)).invoke(
            invocation(), "read only"
        )
        self.assertEqual(TerminalStatus.failure, outcome.terminal_status)
        self.assertEqual(UsageStatus.exact, outcome.usage.usage_status)

    def test_optional_runtime_ids_are_not_invented(self):
        result = RuntimeResult(
            TerminalStatus.success, None, RuntimeSnapshot(UsageEvidence.exact(1, 1, 2))
        )
        store = self.store()
        ControlledInvocationGateway(self.repo, store, FakeRuntime(result)).invoke(
            invocation(), "read only"
        )
        row = store.fetch("invocation-1")
        self.assertIsNone(row["runtime_session_id"])
        self.assertIsNone(row["runtime_invocation_id"])

    def test_requested_model_is_not_assumed_observed(self):
        store = self.store()
        ControlledInvocationGateway(self.repo, store, FakeRuntime()).invoke(
            invocation(requested_model="requested-only"), "read only"
        )
        row = store.fetch("invocation-1")
        self.assertEqual("requested-only", row["requested_model"])
        self.assertIsNone(row["observed_model"])

    def test_purpose_is_persisted_and_non_attempt_purpose_is_read_only(self):
        runtime = FakeRuntime()
        store = self.store()
        ControlledInvocationGateway(self.repo, store, runtime).invoke(invocation(), "read only")
        self.assertEqual("acceptance_validation", store.fetch("invocation-1")["invocation_purpose"])
        self.assertEqual(CapabilityProfile.read_only(), runtime.capability)

    def test_attempt_purposes_are_not_enabled_in_dev_007(self):
        for purpose in (InvocationPurpose.implementation, InvocationPurpose.continuation):
            runtime = FakeRuntime()
            with self.subTest(purpose=purpose):
                with self.assertRaises(InvocationRejected):
                    ControlledInvocationGateway(self.repo, self.store(), runtime).invoke(
                        invocation(invocation_id=f"inv-{purpose}", invocation_purpose=purpose),
                        "mutate",
                    )
                self.assertEqual(0, runtime.starts)

    def test_telemetry_persists_across_reopen_and_exports_reproducibly(self):
        path = self.temp / "telemetry.sqlite3"
        store = TelemetryStore(path)
        ControlledInvocationGateway(self.repo, store, FakeRuntime()).invoke(
            invocation(), "read only"
        )
        reopened = TelemetryStore(path)
        self.assertEqual("DEV-007", reopened.fetch("invocation-1")["dev_task"])
        first, second = io.StringIO(), io.StringIO()
        self.assertEqual(1, reopened.export_jsonl(first, dev_task="DEV-007"))
        self.assertEqual(1, reopened.export_jsonl(second, dev_task="DEV-007"))
        self.assertEqual(first.getvalue(), second.getvalue())
        self.assertEqual("invocation-1", json.loads(first.getvalue())["invocation_id"])

    def test_unsupported_store_schema_version_fails_closed(self):
        import sqlite3

        path = self.temp / "unsupported.sqlite3"
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA user_version = 99")
        connection.close()
        with self.assertRaisesRegex(RuntimeError, "unsupported telemetry schema"):
            TelemetryStore(path)

    def test_codex_usage_maps_last_and_total_without_inventing_optional_values(self):
        last = SimpleNamespace(
            input_tokens=10,
            output_tokens=4,
            total_tokens=14,
            cached_input_tokens=None,
            reasoning_output_tokens=None,
        )
        total = SimpleNamespace(
            input_tokens=20,
            output_tokens=8,
            total_tokens=28,
            cached_input_tokens=3,
            reasoning_output_tokens=2,
        )
        current, cumulative = _map_thread_usage(SimpleNamespace(last=last, total=total))
        self.assertEqual((10, 4, 14), (current.input_tokens, current.output_tokens, current.total_tokens))
        self.assertIsNone(current.cached_input_tokens)
        self.assertEqual(28, cumulative.total_tokens)

    def test_missing_codex_core_usage_remains_unknown_not_zero(self):
        current, cumulative = _map_thread_usage(None)
        self.assertEqual(UsageStatus.unknown, current.usage_status)
        self.assertIsNone(current.total_tokens)
        self.assertIsNone(cumulative)

    def test_codex_start_forces_read_only_and_maps_native_ids(self):
        turn = SimpleNamespace(id="turn-native")
        thread = SimpleNamespace(id="thread-native", turn=lambda *args, **kwargs: turn)
        calls = {}

        class FakeCodex:
            metadata = SimpleNamespace(serverInfo=SimpleNamespace(version="runtime-1"))

            def thread_start(self, **kwargs):
                calls["thread"] = kwargs
                return thread

            def close(self):
                calls["closed"] = True

        adapter = CodexRuntimeAdapter(repo=str(self.repo), codex_factory=FakeCodex)
        handle = adapter.start(invocation(), "read only", CapabilityProfile.read_only())
        self.assertEqual("read-only", calls["thread"]["sandbox"].value)
        self.assertEqual("thread-native", handle.runtime_session_id)
        self.assertEqual("turn-native", handle.runtime_invocation_id)
        self.assertEqual("runtime-1", handle.runtime_version)
        handle.close()

    def test_codex_observe_stream_maps_usage_terminal_and_tool_evidence(self):
        breakdown = SimpleNamespace(
            input_tokens=6,
            output_tokens=3,
            total_tokens=9,
            cached_input_tokens=1,
            reasoning_output_tokens=2,
        )
        token_event = SimpleNamespace(
            method="thread/tokenUsage/updated",
            payload=SimpleNamespace(
                token_usage=SimpleNamespace(last=breakdown, total=breakdown)
            ),
        )
        command = type("CommandExecutionThreadItem", (), {})()
        item_event = SimpleNamespace(
            method="item/completed",
            payload=SimpleNamespace(item=SimpleNamespace(root=command)),
        )
        completed_event = SimpleNamespace(
            method="turn/completed",
            payload=SimpleNamespace(
                turn=SimpleNamespace(status=SimpleNamespace(value="completed"), error=None)
            ),
        )
        turn = SimpleNamespace(stream=lambda: iter((token_event, item_event, completed_event)))
        client = SimpleNamespace(close=lambda: None)
        handle = _CodexHandle(client, turn, "thread-1", "turn-1", runtime_version="1")
        snapshots = []
        result = CodexRuntimeAdapter(repo=str(self.repo)).observe(handle, snapshots.append)
        self.assertEqual(TerminalStatus.success, result.terminal_status)
        self.assertEqual(UsageStatus.exact, result.snapshot.usage.usage_status)
        self.assertEqual(9, result.snapshot.cumulative_usage.total_tokens)
        self.assertEqual(1, result.snapshot.tool_item_count)
        self.assertTrue(snapshots)


if __name__ == "__main__":
    unittest.main()
