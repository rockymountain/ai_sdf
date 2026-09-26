from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ai_execution.execution import BoundedExecutionController
from ai_execution.gateway import ControlledInvocationGateway, InvocationRejected
from ai_execution.model import (
    ContextStrategy,
    ControlledAIInvocation,
    HumanAuthorization,
    InvocationPurpose,
    ModelSelectionStrategy,
    TerminalReason,
    TerminalStatus,
    UsageEvidence,
)
from ai_execution.runtime import CapabilityProfile, RuntimeResult, RuntimeSnapshot
from ai_execution.store import SCHEMA_VERSION, TelemetryStore


AUTH = HumanAuthorization(
    "project-owner",
    "2026-09-23T09:00:00+07:00",
    "approved DEV-012 controlled invocation",
    "allow read-only execution",
)


def load_operator_module():
    spec = importlib.util.spec_from_file_location("ai_execution_operator", ROOT / "tools/ai_execution.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Port:
    adapter_name = "authorization-test-port"
    adapter_version = "1"

    def __init__(self, *, result=None, start_error=None, before_start=None):
        self.starts = 0
        self.capability = None
        self.result = result or RuntimeResult(
            TerminalStatus.success,
            None,
            RuntimeSnapshot(UsageEvidence.exact(3, 2, 5)),
        )
        self.start_error = start_error
        self.before_start = before_start

    def start(self, invocation, text, capability, control):
        self.starts += 1
        self.capability = capability
        if self.before_start is not None:
            self.before_start(invocation)
        if self.start_error is not None:
            raise self.start_error
        return SimpleNamespace()

    def observe(self, handle, publish):
        publish(self.result.snapshot)
        return self.result

    def interrupt(self, handle):
        pass


class BlockingPort(Port):
    def __init__(self):
        super().__init__()
        self.interrupted = threading.Event()

    def observe(self, handle, publish):
        self.interrupted.wait(3)
        return RuntimeResult(
            TerminalStatus.interrupted,
            TerminalReason.other,
            RuntimeSnapshot(UsageEvidence.unknown()),
        )

    def interrupt(self, handle):
        self.interrupted.set()


class AuthorizationAdoptionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo"
        (self.repo / "constitution").mkdir(parents=True)
        (self.repo / "knowledge/schemas").mkdir(parents=True)
        shutil.copy(ROOT / "constitution/policies.yaml", self.repo / "constitution/policies.yaml")
        shutil.copy(
            ROOT / "knowledge/schemas/autonomous-execution-policy.schema.json",
            self.repo / "knowledge/schemas/autonomous-execution-policy.schema.json",
        )
        self.path = self.root / "telemetry.sqlite3"
        self.store = TelemetryStore(self.path)
        self.counter = 0

    def invocation(self, purpose=InvocationPurpose.review, **changes):
        self.counter += 1
        values = dict(
            dev_task="DEV-012",
            traceability_level="T2",
            execution_scope_id="scope",
            run_id="run",
            invocation_id=f"inv-{self.counter}",
            source_revision="base",
            invocation_purpose=purpose,
            model_selection_strategy=ModelSelectionStrategy.fixed,
            context_strategy=ContextStrategy.chat_heavy,
            requested_model="gpt-5.6-sol",
            requested_reasoning_effort="medium",
            human_authorization=AUTH,
        )
        values.update(changes)
        return ControlledAIInvocation(**values)

    def invoke(self, invocation, port=None):
        port = port or Port()
        outcome = ControlledInvocationGateway(self.repo, self.store, port).invoke(invocation, "read only")
        return port, outcome

    def test_all_nonimplementation_purposes_require_authorization_before_port_start(self):
        for purpose in (
            InvocationPurpose.acceptance_validation,
            InvocationPurpose.review,
            InvocationPurpose.orchestration,
        ):
            with self.subTest(purpose=purpose):
                port = Port()
                with self.assertRaisesRegex(InvocationRejected, "start persistence"):
                    self.invoke(self.invocation(purpose, human_authorization=None), port)
                self.assertEqual(0, port.starts)
                self.assertIsNone(self.store.fetch(f"inv-{self.counter}"))

    def test_malformed_authorization_is_rejected_before_invocation_construction(self):
        for values in (
            ("", AUTH.timestamp, AUTH.reason, AUTH.disposition),
            (AUTH.actor, "2026-09-23T09:00:00", AUTH.reason, AUTH.disposition),
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                HumanAuthorization(*values)

    def test_exact_authorization_fields_are_durable_for_every_required_purpose(self):
        expected = {
            "actor": AUTH.actor,
            "timestamp": AUTH.timestamp,
            "reason": AUTH.reason,
            "disposition": AUTH.disposition,
        }
        for purpose in (
            InvocationPurpose.acceptance_validation,
            InvocationPurpose.review,
            InvocationPurpose.orchestration,
        ):
            with self.subTest(purpose=purpose):
                inv = self.invocation(purpose, execution_scope_id=f"scope-{purpose.value}")
                self.invoke(inv)
                evidence = TelemetryStore(self.path).nonimplementation_authorization(inv.invocation_id)
                self.assertTrue(evidence["authorization_valid"])
                self.assertEqual(1, evidence["authorization_event_count"])
                self.assertEqual(expected, evidence["authorization_payload"])

    def test_authorization_is_committed_before_port_start(self):
        def assert_durable(invocation):
            evidence = TelemetryStore(self.path).nonimplementation_authorization(invocation.invocation_id)
            self.assertTrue(evidence["authorization_valid"])

        port = Port(before_start=assert_durable)
        self.invoke(self.invocation(), port)
        self.assertEqual(1, port.starts)

    def test_authorization_insert_failure_rolls_back_invocation_and_blocks_port(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "CREATE TRIGGER reject_authorization BEFORE INSERT ON execution_evidence "
                "WHEN NEW.kind='nonimplementation_authorized' BEGIN "
                "SELECT RAISE(ABORT, 'injected authorization failure'); END"
            )
        inv = self.invocation()
        port = Port()
        with self.assertRaisesRegex(InvocationRejected, "start persistence"):
            self.invoke(inv, port)
        self.assertEqual(0, port.starts)
        self.assertIsNone(self.store.fetch(inv.invocation_id))

    def test_authorization_survives_start_and_terminal_failures(self):
        terminal_failure = RuntimeResult(
            TerminalStatus.failure,
            TerminalReason.runtime_error,
            RuntimeSnapshot(UsageEvidence.unknown()),
        )
        terminal_inv = self.invocation(execution_scope_id="terminal-failure")
        self.invoke(terminal_inv, Port(result=terminal_failure))
        self.assertTrue(self.store.nonimplementation_authorization(terminal_inv.invocation_id)["authorization_valid"])

        for name, error in (("definite-non-start", FileNotFoundError("local")),
                            ("uncertain-start", OSError("response lost"))):
            with self.subTest(name=name):
                inv = self.invocation(execution_scope_id=name)
                with self.assertRaises(InvocationRejected):
                    self.invoke(inv, Port(start_error=error))
                self.assertTrue(self.store.nonimplementation_authorization(inv.invocation_id)["authorization_valid"])

    def test_timeout_preserves_authorization_and_creates_no_attempt(self):
        policy = self.repo / "constitution/policies.yaml"
        text = policy.read_text(encoding="utf-8").replace("max_invocation_seconds: 600", "max_invocation_seconds: 1")
        policy.write_text(text, encoding="utf-8")
        inv = self.invocation()
        self.invoke(inv, BlockingPort())
        self.assertTrue(self.store.nonimplementation_authorization(inv.invocation_id)["authorization_valid"])
        snapshot = BoundedExecutionController(self.repo, self.store).snapshot("scope")
        self.assertEqual([], snapshot["reservations"])
        self.assertEqual([], snapshot["attempts"])

    def test_event_cardinality_fails_closed_for_zero_and_duplicates(self):
        inv = self.invocation()
        self.invoke(inv)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "DELETE FROM execution_evidence WHERE invocation_id=? AND kind='nonimplementation_authorized'",
                (inv.invocation_id,),
            )
        evidence = self.store.nonimplementation_authorization(inv.invocation_id)
        self.assertEqual(0, evidence["authorization_event_count"])
        self.assertFalse(evidence["authorization_valid"])

        payload = json.dumps({
            "actor": AUTH.actor,
            "timestamp": AUTH.timestamp,
            "reason": AUTH.reason,
            "disposition": AUTH.disposition,
        }, sort_keys=True)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "INSERT INTO execution_evidence "
                "(execution_scope_id,reservation_id,invocation_id,kind,payload,recorded_at) "
                "VALUES (?,NULL,?,'nonimplementation_authorized',?,'2026-09-23T02:00:00Z')",
                (inv.execution_scope_id, inv.invocation_id, payload),
            )
            connection.execute(
                "INSERT INTO execution_evidence "
                "(execution_scope_id,reservation_id,invocation_id,kind,payload,recorded_at) "
                "VALUES (?,NULL,?,'nonimplementation_authorized',?,'2026-09-23T02:00:01Z')",
                (inv.execution_scope_id, inv.invocation_id, payload),
            )
        evidence = self.store.nonimplementation_authorization(inv.invocation_id)
        self.assertEqual(2, evidence["authorization_event_count"])
        self.assertFalse(evidence["authorization_valid"])

    def test_replayed_invocation_identity_is_rejected_without_second_port_start(self):
        inv = self.invocation()
        self.invoke(inv)
        port = Port()
        with self.assertRaises(InvocationRejected):
            self.invoke(inv, port)
        self.assertEqual(0, port.starts)
        self.assertEqual(1, self.store.nonimplementation_authorization(inv.invocation_id)["authorization_event_count"])

    def test_required_purposes_are_read_only_and_create_no_capacity(self):
        for purpose in (
            InvocationPurpose.acceptance_validation,
            InvocationPurpose.review,
            InvocationPurpose.orchestration,
        ):
            with self.subTest(purpose=purpose):
                scope = f"scope-{purpose.value}"
                inv = self.invocation(purpose, execution_scope_id=scope)
                port, _ = self.invoke(inv)
                self.assertEqual(CapabilityProfile.read_only(), port.capability)
                snapshot = BoundedExecutionController(self.repo, self.store).snapshot(scope)
                self.assertEqual([], snapshot["reservations"])
                self.assertEqual([], snapshot["attempts"])

    def test_stopped_scope_retains_distinct_authorization_and_disposition_events(self):
        unknown = RuntimeResult(
            TerminalStatus.success,
            None,
            RuntimeSnapshot(UsageEvidence.unknown()),
        )
        self.invoke(self.invocation(), Port(result=unknown))
        follow_up = self.invocation()
        self.invoke(follow_up)
        snapshot = BoundedExecutionController(self.repo, self.store).snapshot("scope")
        kinds = [row["kind"] for row in snapshot["execution_evidence"]
                 if row["invocation_id"] == follow_up.invocation_id]
        self.assertEqual(["nonimplementation_authorized", "non_mutating_disposition"], kinds)

    def test_schema_version_remains_three_and_historical_rows_are_not_backfilled(self):
        inv = self.invocation()
        self.invoke(inv)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "DELETE FROM execution_evidence WHERE kind='nonimplementation_authorized'"
            )
            for table in ("invocation_attempts", "attempts", "reservations", "execution_evidence", "execution_scopes"):
                connection.execute(f"DROP TABLE {table}")
            connection.execute("PRAGMA user_version=2")
        migrated = TelemetryStore(self.path)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(SCHEMA_VERSION, connection.execute("PRAGMA user_version").fetchone()[0])
            self.assertEqual(0, connection.execute(
                "SELECT COUNT(*) FROM execution_evidence WHERE kind='nonimplementation_authorized'"
            ).fetchone()[0])
        self.assertFalse(migrated.nonimplementation_authorization(inv.invocation_id)["authorization_valid"])

    def test_operator_builds_exact_m3_profile_and_structured_authorization(self):
        operator = load_operator_module()
        args = self.operator_args()
        invocation = operator.controlled_invocation(args)
        self.assertEqual("DEV-012", invocation.dev_task)
        self.assertEqual("T2", invocation.traceability_level)
        self.assertEqual("gpt-5.6-sol", invocation.requested_model)
        self.assertEqual("medium", invocation.requested_reasoning_effort)
        self.assertIs(ModelSelectionStrategy.fixed, invocation.model_selection_strategy)
        self.assertIsNone(invocation.routing_policy_version)
        self.assertIs(ContextStrategy.chat_heavy, invocation.context_strategy)
        self.assertEqual(AUTH, invocation.human_authorization)

    def test_operator_missing_or_partial_authorization_fails_closed(self):
        operator = load_operator_module()
        missing = self.operator_args(
            authorization_actor=None,
            authorization_timestamp=None,
            authorization_reason=None,
            authorization_disposition=None,
        )
        with self.assertRaisesRegex(ValueError, "authorization is required"):
            operator.controlled_invocation(missing)
        with self.assertRaisesRegex(ValueError, "all canonical fields"):
            operator.controlled_invocation(self.operator_args(authorization_reason=None))

    def test_operator_parser_requires_identity_profile_and_keeps_legacy_live_proof(self):
        operator = load_operator_module()
        parser = operator.parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["invoke"])
        live = parser.parse_args([
            "live-proof",
            "--authorization-actor", AUTH.actor,
            "--authorization-timestamp", AUTH.timestamp,
            "--authorization-reason", AUTH.reason,
            "--authorization-disposition", AUTH.disposition,
        ])
        self.assertIs(live.function, operator.live_proof)

    def test_operator_implementation_identity_does_not_synthesize_capacity(self):
        operator = load_operator_module()
        args = self.operator_args(
            invocation_purpose="implementation",
            objective_id="objective",
            reservation_id=None,
            candidate_attempt_number=None,
            authorization_actor=None,
            authorization_timestamp=None,
            authorization_reason=None,
            authorization_disposition=None,
        )
        invocation = operator.controlled_invocation(args)
        port = Port()
        with self.assertRaises(InvocationRejected):
            self.invoke(invocation, port)
        self.assertEqual(0, port.starts)

    @staticmethod
    def operator_args(**changes):
        values = dict(
            dev_task="DEV-012",
            traceability_level="T2",
            execution_scope_id="scope",
            objective_id=None,
            run_id="run",
            invocation_id="operator-invocation",
            source_revision="base",
            invocation_purpose="acceptance_validation",
            model_selection_strategy="fixed",
            routing_policy_version="none",
            context_strategy="chat-heavy",
            requested_model="gpt-5.6-sol",
            requested_reasoning_effort="medium",
            reservation_id=None,
            candidate_attempt_number=None,
            attempt_number=None,
            resume_of_invocation_id=None,
            authorization_actor=AUTH.actor,
            authorization_timestamp=AUTH.timestamp,
            authorization_reason=AUTH.reason,
            authorization_disposition=AUTH.disposition,
        )
        values.update(changes)
        return argparse.Namespace(**values)


if __name__ == "__main__":
    unittest.main()
