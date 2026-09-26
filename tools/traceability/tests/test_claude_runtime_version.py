"""TEST-018: observed Claude runtime-version provenance (DEV-018).

Version discovery runs inside ClaudeRuntimeAdapter.start(), after the gateway has
already persisted governed invocation-start/reservation state (FR-006 provenance
without bypassing FR-007 reservation semantics). A discovery failure is therefore a
normal local pre-start failure: the adapter's existing except clause reports exactly
one StartDisposition.not_started, which releases any implementation reservation
through the existing gateway/controller machinery. No Claude inference process starts.
"""

from __future__ import annotations

import importlib.util
import inspect
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ai_execution.claude_adapter import ClaudeRuntimeAdapter, resolve_runtime_version
from ai_execution.execution import BoundedExecutionController
from ai_execution.gateway import ControlledInvocationGateway, InvocationRejected
from ai_execution.model import (
    ContextStrategy,
    ControlledAIInvocation,
    HumanAuthorization,
    InvocationPurpose,
    ModelSelectionStrategy,
    TerminalStatus,
)
from ai_execution.runtime import AIRuntimePort
from ai_execution.store import TelemetryStore


AUTH = HumanAuthorization(
    "project-owner",
    "2026-09-25T10:00:00+07:00",
    "authorize deterministic review",
    "approved",
)


def load_operator():
    spec = importlib.util.spec_from_file_location("ai_execution_operator_018", ROOT / "tools/ai_execution.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runner(stdout="", returncode=0, error=None, calls=None):
    def run(command, **options):
        if calls is not None:
            calls.append((command, options))
        if error is not None:
            raise error
        return subprocess.CompletedProcess(command, returncode, stdout=stdout)
    return run


def never_started(*args, **kwargs):
    raise AssertionError("Claude inference process must not start when version discovery fails")


class FakeProcess:
    def __init__(self, events):
        self.stdout = [_line(event) for event in events]

    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        pass

    def kill(self):
        pass


def _line(event):
    import json
    return json.dumps(event) + "\n"


class ResolverTests(unittest.TestCase):
    def test_version_comes_from_declared_executable_output(self):
        calls = []
        observed = resolve_runtime_version(
            "declared-claude", run=runner("observed 9.9 (fixture)\n", calls=calls)
        )
        self.assertEqual("observed 9.9 (fixture)", observed)
        command, options = calls[0]
        self.assertEqual(["declared-claude", "--version"], command)
        self.assertEqual(subprocess.DEVNULL, options["stdin"])
        self.assertIsNotNone(options["timeout"])

    def test_unavailable_blank_or_malformed_version_fails_closed(self):
        cases = {
            "missing-executable": runner(error=FileNotFoundError("missing")),
            "timeout": runner(error=subprocess.TimeoutExpired(["claude"], 30)),
            "nonzero-exit": runner("observed\n", returncode=1),
            "empty": runner(""),
            "whitespace": runner("  \n\t\n"),
            "multi-line": runner("observed\nsecond line\n"),
            "non-text": runner(None),
        }
        for name, run in cases.items():
            with self.subTest(case=name):
                with self.assertRaisesRegex(ValueError, "runtime version unavailable"):
                    resolve_runtime_version("declared-claude", run=run)

    def test_executable_must_be_explicit_before_inspection(self):
        calls = []
        for executable in ("", "  ", None):
            with self.subTest(executable=executable):
                with self.assertRaisesRegex(ValueError, "must be explicit"):
                    resolve_runtime_version(executable, run=runner("x", calls=calls))
        self.assertEqual([], calls)


class AdapterConstructionTests(unittest.TestCase):
    def test_pinned_override_must_be_non_blank_when_supplied(self):
        for value in ("", "   "):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "override must be non-blank"):
                    ClaudeRuntimeAdapter(repo=str(ROOT), executable="claude-test", runtime_version=value)

    def test_no_pinned_override_is_accepted_without_any_version_inspection(self):
        calls = []
        adapter = ClaudeRuntimeAdapter(
            repo=str(ROOT), executable="claude-test", version_runner=runner("x", calls=calls)
        )
        self.assertIsNone(adapter.runtime_version)
        self.assertEqual([], calls)  # construction alone performs no inspection

    def test_ai_runtime_port_is_unchanged(self):
        self.assertEqual(
            {"adapter_name": "str", "adapter_version": "str"},
            {name: str(value) for name, value in AIRuntimePort.__annotations__.items()},
        )
        self.assertEqual(
            ["self", "invocation", "input_text", "capability", "start_control"],
            list(inspect.signature(AIRuntimePort.start).parameters),
        )
        self.assertEqual(
            ["self", "handle", "publish"], list(inspect.signature(AIRuntimePort.observe).parameters)
        )
        self.assertEqual(
            ["self", "handle"], list(inspect.signature(AIRuntimePort.interrupt).parameters)
        )

    def test_no_hardcoded_claude_version_or_extension_path(self):
        forbidden = re.compile(r"\d+\.\d+\.\d+|vscode|anthropic\.claude-code|native-binary", re.I)
        for relative in ("src/ai_execution/claude_adapter.py", "tools/ai_execution.py"):
            with self.subTest(path=relative):
                self.assertIsNone(forbidden.search((ROOT / relative).read_text(encoding="utf-8")))


class OperatorWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.operator = load_operator()

    def test_codex_selection_performs_no_claude_version_inspection(self):
        calls = []
        adapter = self.operator.runtime_adapter(
            self.operator.argparse.Namespace(runtime_adapter="codex", claude_executable=None),
            ROOT,
            version_runner=runner("x", calls=calls),
        )
        self.assertEqual("codex", adapter.adapter_name)
        self.assertEqual([], calls)


class GovernedGatewayTests(unittest.TestCase):
    """Exercises the true production path: gateway -> AIRuntimePort -> adapter."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        temp = Path(self.temporary.name)
        self.repo = temp / "repo"
        (self.repo / "constitution").mkdir(parents=True)
        (self.repo / "knowledge/schemas").mkdir(parents=True)
        shutil.copy(
            ROOT / "knowledge/schemas/autonomous-execution-policy.schema.json",
            self.repo / "knowledge/schemas/autonomous-execution-policy.schema.json",
        )
        (self.repo / "constitution/policies.yaml").write_text(
            "version: 1\nautonomous_execution:\n  max_invocation_seconds: 600\n  max_attempts: 2\n",
            encoding="utf-8",
        )
        self.store = TelemetryStore(temp / "telemetry.sqlite3")
        self.controller = BoundedExecutionController(self.repo, self.store)

    def implementation_invocation(self, *, scope_id, reservation, invocation_id):
        return ControlledAIInvocation(
            dev_task="DEV-018",
            traceability_level="T1",
            execution_scope_id=scope_id,
            objective_id=scope_id,
            run_id=f"run-{invocation_id}",
            invocation_id=invocation_id,
            source_revision="a" * 40,
            invocation_purpose=InvocationPurpose.implementation,
            model_selection_strategy=ModelSelectionStrategy.fixed,
            context_strategy=ContextStrategy.chat_heavy,
            requested_model="declared-model",
            reservation_id=reservation["reservation_id"],
            candidate_attempt_number=reservation["candidate_attempt_number"],
        )

    def test_successful_discovery_runs_after_gateway_start_governance_and_persists_version(self):
        self.controller.create_scope(
            "scope-18a", dev_task="DEV-018", objective_id="scope-18a", source_revision="a" * 40
        )
        reservation = self.controller.reserve("scope-18a")
        calls = []

        def version_runner(command, **options):
            # Proves ordering: the invocation-start record (and reservation
            # binding) already exist when Claude-local version inspection runs.
            row = self.store.fetch("inv-18a")
            self.assertIsNotNone(row)
            self.assertEqual("claude", row["adapter_name"])
            calls.append(("version", list(command)))
            return subprocess.CompletedProcess(command, 0, stdout="observed-runtime 3 (fixture)\n")

        def process_factory(command, **options):
            calls.append(("process", list(command)))
            return FakeProcess((
                {
                    "type": "result", "subtype": "success", "is_error": False,
                    "usage": {
                        "input_tokens": 1, "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0, "output_tokens": 1,
                    },
                },
            ))

        adapter = ClaudeRuntimeAdapter(
            repo=str(self.repo), executable="claude-test",
            version_runner=version_runner, process_factory=process_factory,
        )
        invocation = self.implementation_invocation(
            scope_id="scope-18a", reservation=reservation, invocation_id="inv-18a"
        )
        outcome = ControlledInvocationGateway(self.repo, self.store, adapter).invoke(invocation, "implement")

        self.assertEqual(TerminalStatus.success, outcome.terminal_status)
        self.assertEqual(["version", "process"], [kind for kind, _ in calls])
        row = self.store.fetch("inv-18a")
        self.assertEqual("observed-runtime 3 (fixture)", row["runtime_version"])
        self.assertEqual("claude", row["runtime_name"])

    def test_definitive_discovery_failure_releases_implementation_reservation_without_consuming_attempt(self):
        self.controller.create_scope(
            "scope-18b", dev_task="DEV-018", objective_id="scope-18b", source_revision="a" * 40
        )
        reservation = self.controller.reserve("scope-18b")
        reservation_id = reservation["reservation_id"]
        self.assertEqual(1, reservation["candidate_attempt_number"])

        adapter = ClaudeRuntimeAdapter(
            repo=str(self.repo), executable="missing-claude",
            version_runner=runner(error=FileNotFoundError("declared Claude executable is missing")),
            process_factory=never_started,
        )
        invocation = self.implementation_invocation(
            scope_id="scope-18b", reservation=reservation, invocation_id="inv-18b"
        )
        with self.assertRaisesRegex(InvocationRejected, "runtime start failed"):
            ControlledInvocationGateway(self.repo, self.store, adapter).invoke(invocation, "implement")

        # 1. The invocation row exists with terminal failure evidence.
        row = self.store.fetch("inv-18b")
        self.assertIsNotNone(row)
        self.assertEqual("failure", row["terminal_status"])
        self.assertEqual("runtime_error", row["terminal_reason"])

        # 2/3. Exactly one reservation-release event; RESERVED -> RELEASED; no attempt consumed.
        snapshot = self.controller.snapshot("scope-18b")
        reservations = {r["reservation_id"]: r for r in snapshot["reservations"]}
        self.assertEqual("RELEASED", reservations[reservation_id]["state"])
        release_events = [
            e for e in snapshot["execution_evidence"]
            if e["kind"] == "reservation_released" and e["reservation_id"] == reservation_id
        ]
        self.assertEqual(1, len(release_events))
        self.assertEqual([], snapshot["attempts"])

        # 4. Candidate attempt 1 is reusable with a new reservation_id.
        replacement = self.controller.reserve("scope-18b")
        self.assertEqual(1, replacement["candidate_attempt_number"])
        self.assertNotEqual(reservation_id, replacement["reservation_id"])

        # 5. The original released reservation and its evidence remain immutable.
        snapshot_after = self.controller.snapshot("scope-18b")
        original_after = {r["reservation_id"]: r for r in snapshot_after["reservations"]}[reservation_id]
        self.assertEqual("RELEASED", original_after["state"])
        release_events_after = [
            e for e in snapshot_after["execution_evidence"]
            if e["kind"] == "reservation_released" and e["reservation_id"] == reservation_id
        ]
        self.assertEqual(1, len(release_events_after))
        self.assertEqual(release_events, release_events_after)

    def test_nonimplementation_discovery_failure_persists_terminal_failure_without_reservation(self):
        adapter = ClaudeRuntimeAdapter(
            repo=str(self.repo), executable="missing-claude",
            version_runner=runner(error=FileNotFoundError("declared Claude executable is missing")),
            process_factory=never_started,
        )
        invocation = ControlledAIInvocation(
            dev_task="DEV-018",
            traceability_level="T1",
            execution_scope_id="scope-18c",
            objective_id="scope-18c",
            run_id="run-18c",
            invocation_id="inv-18c",
            source_revision="a" * 40,
            invocation_purpose=InvocationPurpose.review,
            model_selection_strategy=ModelSelectionStrategy.fixed,
            context_strategy=ContextStrategy.chat_heavy,
            requested_model="declared-model",
            human_authorization=AUTH,
        )
        with self.assertRaisesRegex(InvocationRejected, "runtime start failed"):
            ControlledInvocationGateway(self.repo, self.store, adapter).invoke(invocation, "review only")

        row = self.store.fetch("inv-18c")
        self.assertIsNotNone(row)
        self.assertEqual("failure", row["terminal_status"])
        self.assertIsNone(row.get("reservation_id"))
        self.assertIsNone(row.get("attempt_number"))
        snapshot = self.controller.snapshot("scope-18c")
        self.assertEqual([], snapshot["reservations"])
        self.assertEqual([], snapshot["attempts"])


if __name__ == "__main__":
    unittest.main()
