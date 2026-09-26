from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ai_execution.execution import BoundedExecutionController, ExecutionRejected
from ai_execution.gateway import ControlledInvocationGateway, InvocationRejected
from ai_execution.model import (
    CheckpointEvidence, ContextStrategy, ControlledAIInvocation, HumanAuthorization,
    InvocationPurpose, ModelSelectionStrategy, TerminalReason, TerminalStatus, UsageEvidence,
)
from ai_execution.policy import load_watchdog_policy
from ai_execution.runtime import RuntimeResult, RuntimeSnapshot, StartDisposition, StartEvidence
from ai_execution.store import SCHEMA_VERSION, TelemetryStore


AUTH = HumanAuthorization("project-owner", "2026-09-21T10:00:00Z", "reviewed retained evidence", "authorize continuation")
PASS = CheckpointEvidence("python deterministic_check.py", 0, "retained:checkpoint-pass")
FAIL = CheckpointEvidence("python deterministic_check.py", 1, "retained:checkpoint-fail")


class Port:
    adapter_name = "deterministic-fake"
    adapter_version = "1"

    def __init__(self, disposition=StartDisposition.accepted, status=TerminalStatus.success,
                 reason=None, usage=None, block_start=False, block_observe=False):
        self.disposition, self.status, self.reason = disposition, status, reason
        self.usage = usage if usage is not None else UsageEvidence.exact(3, 2, 5)
        self.block_start, self.block_observe = block_start, block_observe
        self.starts = self.interrupts = 0
        self.done = threading.Event()
        self.entered = threading.Event()

    def start(self, invocation, text, capability, control):
        self.starts += 1
        self.capability = capability
        self.invocation = invocation
        control.register_abort(self.done.set)
        if self.block_start:
            self.entered.set()
            self.done.wait(5)
            control.raise_if_cancelled()
        if self.disposition is not None:
            control.report_start(StartEvidence(self.disposition, "fake:machine-readable-start"))
        if self.disposition in {StartDisposition.not_started, StartDisposition.uncertain}:
            raise RuntimeError("fake start termination")
        return SimpleNamespace()

    def observe(self, handle, publish):
        snapshot = RuntimeSnapshot(self.usage)
        publish(snapshot)
        if self.block_observe:
            self.entered.set()
            self.done.wait(5)
        return RuntimeResult(self.status, self.reason, snapshot)

    def interrupt(self, handle):
        self.interrupts += 1
        self.done.set()


class BoundedExecutionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        for directory in ("constitution", "knowledge/schemas"):
            (self.repo / directory).mkdir(parents=True)
        for filename in ("constitution/policies.yaml", "knowledge/schemas/autonomous-execution-policy.schema.json"):
            shutil.copy(ROOT / filename, self.repo / filename)
        self.path = self.repo / "operational.sqlite3"
        self.store = TelemetryStore(self.path)
        self.controller = BoundedExecutionController(self.repo, self.store)
        self.controller.create_scope("scope", dev_task="DEV-008", objective_id="objective", source_revision="base")
        self.counter = 0

    def invocation(self, **changes):
        self.counter += 1
        data = dict(dev_task="DEV-008", traceability_level="T2", execution_scope_id="scope",
                    objective_id="objective", source_revision="base", run_id="run",
                    invocation_id=f"inv-{self.counter}", invocation_purpose=InvocationPurpose.implementation,
                    model_selection_strategy=ModelSelectionStrategy.fixed,
                    context_strategy=ContextStrategy.manual_context_pack)
        data.update(changes)
        return ControlledAIInvocation(**data)

    def invoke(self, port=None, **changes):
        reservation = self.controller.reserve(changes.get("execution_scope_id", "scope"))
        invocation = self.invocation(**reservation, **changes)
        port = port or Port()
        outcome = ControlledInvocationGateway(self.repo, self.store, port).invoke(invocation, "governed objective")
        return invocation, port, outcome

    def snapshot(self):
        return self.controller.snapshot("scope")

    def short_watchdog(self):
        path = self.repo / "constitution/policies.yaml"
        data = yaml.safe_load(path.read_text())
        data["autonomous_execution"]["max_invocation_seconds"] = 1
        path.write_text(yaml.safe_dump(data))

    def test_a_release_preserves_independent_unknown_review_blocker(self):
        with self.assertRaises(InvocationRejected):
            self.invoke(Port(StartDisposition.uncertain))
        review = self.invocation(invocation_purpose=InvocationPurpose.review, human_authorization=AUTH)
        port = Port(usage=UsageEvidence.unknown())
        gateway = ControlledInvocationGateway(self.repo, self.store, port)
        gateway.invoke(review, "authorized review")
        rid = self.snapshot()["reservations"][0]["reservation_id"]
        self.controller.resolve_reservation(rid, StartEvidence(StartDisposition.not_started, "definite non-start"), authorization=AUTH)
        self.assertEqual("RELEASED", self.snapshot()["reservations"][0]["state"])
        self.assertEqual("STOPPED", self.snapshot()["scope"]["state"])
        restarted = BoundedExecutionController(self.repo, TelemetryStore(self.path))
        with self.assertRaises(ExecutionRejected):
            restarted.reserve("scope")
        with self.assertRaises(InvocationRejected):
            gateway.invoke(self.invocation(reservation_id=rid, candidate_attempt_number=1), "blocked implementation")
        self.assertEqual(1, port.starts, "release must not permit a new port call")
        self.assertEqual("unknown", self.store.fetch(review.invocation_id)["usage_status"])

    def test_b_continuation_preserves_independent_unknown_review_blocker(self):
        first, _, _ = self.invoke(Port(status=TerminalStatus.interrupted, reason=TerminalReason.usage_limit,
                                      usage=UsageEvidence.unknown()))
        port = Port(usage=UsageEvidence.unknown())
        review = self.invocation(invocation_purpose=InvocationPurpose.review, human_authorization=AUTH)
        ControlledInvocationGateway(self.repo, self.store, port).invoke(review, "authorized review")
        before = self.snapshot()
        continuation = self.invocation(invocation_purpose=InvocationPurpose.continuation, attempt_number=1,
                                       resume_of_invocation_id=first.invocation_id, human_authorization=AUTH)
        restarted = TelemetryStore(self.path)
        with self.assertRaises(InvocationRejected):
            ControlledInvocationGateway(self.repo, restarted, port).invoke(continuation, "blocked continuation")
        self.assertEqual(1, port.starts, "unrelated unknown usage must block before mutation capability reaches the port")
        self.assertEqual(before, self.snapshot())
        self.assertIsNone(restarted.fetch(continuation.invocation_id))

    def test_c_implicit_nonimplementation_scope_cannot_reserve(self):
        for purpose in (InvocationPurpose.review, InvocationPurpose.orchestration, InvocationPurpose.acceptance_validation):
            with self.subTest(purpose=purpose):
                scope = f"implicit-{purpose}"
                inv = self.invocation(execution_scope_id=scope, objective_id=scope, invocation_purpose=purpose,
                                      human_authorization=AUTH)
                review_port = Port()
                ControlledInvocationGateway(self.repo, self.store, review_port).invoke(inv, "nonimplementation")
                self.assertFalse(review_port.capability.repository_mutation)
                reopened = TelemetryStore(self.path)
                with self.assertRaises(ExecutionRejected):
                    BoundedExecutionController(self.repo, reopened).reserve(scope)
                implementation_port = Port()
                with self.assertRaises(InvocationRejected):
                    ControlledInvocationGateway(self.repo, reopened, implementation_port).invoke(
                        self.invocation(execution_scope_id=scope, objective_id=scope,
                                        reservation_id="forged", candidate_attempt_number=1), "blocked implementation")
                self.assertEqual(0, implementation_port.starts)

    def test_explicit_registration_and_successor_authority_survive_restart(self):
        reopened = TelemetryStore(self.path)
        controller = BoundedExecutionController(self.repo, reopened)
        registration = self.snapshot()["execution_evidence"][0]
        self.assertEqual("objective_registered", registration["kind"])
        self.assertEqual("objective", json.loads(registration["payload"])["objective_id"])
        reservation = controller.reserve("scope")
        controller.resolve_reservation(reservation["reservation_id"], StartEvidence(StartDisposition.uncertain, "lost start evidence"))
        controller.successor_scope("scope", "successor", authorization=AUTH)
        restarted = BoundedExecutionController(self.repo, TelemetryStore(self.path))
        self.assertEqual(1, restarted.reserve("successor")["candidate_attempt_number"])
        with self.assertRaises(ExecutionRejected):
            restarted.reserve("scope")

    def test_explicit_registration_of_implicit_scope_preserves_existing_blockers(self):
        for usage in (UsageEvidence.exact(3, 2, 5), UsageEvidence.unknown()):
            with self.subTest(usage=usage):
                scope = f"implicit-{usage.usage_status}"
                review = self.invocation(execution_scope_id=scope, objective_id=scope,
                                         invocation_purpose=InvocationPurpose.review,
                                         human_authorization=AUTH)
                ControlledInvocationGateway(self.repo, self.store, Port(usage=usage)).invoke(review, "review")
                before = self.store.fetch(review.invocation_id)
                self.controller.create_scope(scope, dev_task="DEV-008", objective_id=scope, source_revision="base")
                restarted = BoundedExecutionController(self.repo, TelemetryStore(self.path))
                if usage.usage_status == "unknown":
                    self.assertEqual("STOPPED", restarted.snapshot(scope)["scope"]["state"])
                    with self.assertRaises(ExecutionRejected):
                        restarted.reserve(scope)
                else:
                    self.assertEqual(1, restarted.reserve(scope)["candidate_attempt_number"])
                self.assertEqual(before, self.store.fetch(review.invocation_id))

    def test_legacy_root_and_existing_reservation_do_not_imply_registration(self):
        reservation = self.controller.reserve("scope")
        # Reproduce a schema-3 root written before explicit registration evidence
        # existed. Neither an old ACTIVE flag nor its reservation proves authority.
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("DELETE FROM execution_evidence WHERE kind='objective_registered'")
        reopened = TelemetryStore(self.path)
        port = Port()
        invocation = self.invocation(**reservation)
        with self.assertRaises(InvocationRejected):
            ControlledInvocationGateway(self.repo, reopened, port).invoke(invocation, "unregistered work")
        self.assertEqual(0, port.starts)
        controller = BoundedExecutionController(self.repo, reopened)
        controller.create_scope("scope", dev_task="DEV-008", objective_id="objective", source_revision="base")
        ControlledInvocationGateway(self.repo, reopened, port).invoke(invocation, "explicitly registered work")
        self.assertEqual(1, port.starts)
        self.assertEqual(1, len(self.snapshot()["reservations"]), "registration must not reset capacity")

    def test_consumed_resolution_composes_independent_review_blocker(self):
        self.invoke(Port(disposition=None))
        self.assertEqual("UNRESOLVED", self.snapshot()["reservations"][0]["state"])
        ControlledInvocationGateway(self.repo, self.store, Port(usage=UsageEvidence.unknown())).invoke(
            self.invocation(invocation_purpose=InvocationPurpose.review, human_authorization=AUTH), "review")
        rid = self.snapshot()["reservations"][0]["reservation_id"]
        self.controller.resolve_reservation(rid, StartEvidence(StartDisposition.accepted, "recovered acceptance"), authorization=AUTH)
        self.assertEqual("OPEN", self.snapshot()["attempts"][0]["state"])
        self.assertEqual("STOPPED", self.snapshot()["scope"]["state"])
        self.controller.close_attempt("scope", 1, FAIL)
        self.assertEqual("STOPPED", self.snapshot()["scope"]["state"])
        with self.assertRaises(ExecutionRejected):
            self.controller.reserve("scope")

    def test_consumed_resolution_without_other_blockers_restores_active(self):
        self.invoke(Port(disposition=None))
        rid = self.snapshot()["reservations"][0]["reservation_id"]
        self.controller.resolve_reservation(rid, StartEvidence(StartDisposition.accepted, "recovered acceptance"), authorization=AUTH)
        self.assertEqual("OPEN", self.snapshot()["attempts"][0]["state"])
        self.assertEqual("ACTIVE", self.snapshot()["scope"]["state"])
        with self.assertRaises(ExecutionRejected):
            self.controller.reserve("scope")
        self.controller.close_attempt("scope", 1, FAIL)
        self.assertEqual(2, self.controller.reserve("scope")["candidate_attempt_number"])

    def test_unrelated_terminal_review_blocker_is_not_usage_limit_lineage(self):
        for status, reason in ((TerminalStatus.failure, TerminalReason.runtime_error),
                               (TerminalStatus.interrupted, TerminalReason.usage_limit)):
            with self.subTest(status=status):
                scope = f"scope-review-{status}"
                self.controller.create_scope(scope, dev_task="DEV-008", objective_id=scope, source_revision="base")
                first, _, _ = self.invoke(Port(status=TerminalStatus.interrupted, reason=TerminalReason.usage_limit),
                                          execution_scope_id=scope, objective_id=scope)
                port = Port(status=status, reason=reason)
                gateway = ControlledInvocationGateway(self.repo, self.store, port)
                gateway.invoke(self.invocation(execution_scope_id=scope, objective_id=scope,
                                               invocation_purpose=InvocationPurpose.review, human_authorization=AUTH), "review")
                with self.assertRaises(InvocationRejected):
                    gateway.invoke(self.invocation(execution_scope_id=scope, objective_id=scope,
                                                   invocation_purpose=InvocationPurpose.continuation, attempt_number=1,
                                                   resume_of_invocation_id=first.invocation_id, human_authorization=AUTH), "resume")
                self.assertEqual(1, port.starts)

    def test_canonical_budget_and_invalid_policy_fail_closed_before_port(self):
        self.assertEqual(2, load_watchdog_policy(ROOT).max_attempts)
        self.assertEqual(600, load_watchdog_policy(ROOT).max_invocation_seconds)
        path = self.repo / "constitution/policies.yaml"
        original = path.read_text()
        for value in (None, True, False, 0, -1, 1.5, 2.0, "2", [], {}):
            with self.subTest(value=value):
                data = yaml.safe_load(original)
                if value is None:
                    del data["autonomous_execution"]["max_attempts"]
                else:
                    data["autonomous_execution"]["max_attempts"] = value
                path.write_text(yaml.safe_dump(data))
                with self.assertRaises(ValueError):
                    self.controller.reserve("scope")
                port = Port()
                with self.assertRaises(InvocationRejected):
                    ControlledInvocationGateway(self.repo, self.store, port).invoke(self.invocation(), "work")
                self.assertEqual(0, port.starts)
        path.write_text(original + "\nautonomous_execution: {max_attempts: 2, max_invocation_seconds: 600}\n")
        with self.assertRaises(ValueError):
            load_watchdog_policy(self.repo)

    def test_release_reuses_candidate_under_new_reservation_identity(self):
        first = self.controller.reserve("scope")
        self.assertEqual([], self.snapshot()["attempts"])
        self.controller.resolve_reservation(first["reservation_id"], StartEvidence(StartDisposition.not_started, "local pre-start failure"))
        before = self.snapshot()["reservations"][0]
        second = self.controller.reserve("scope")
        self.assertEqual(first["candidate_attempt_number"], second["candidate_attempt_number"])
        self.assertNotEqual(first["reservation_id"], second["reservation_id"])
        self.assertEqual(before, self.snapshot()["reservations"][0])
        with self.assertRaises(ExecutionRejected):
            self.controller.resolve_reservation(first["reservation_id"], StartEvidence(StartDisposition.accepted, "contradiction"))

    def test_consumption_binds_candidate_and_port_sees_no_attempt_number(self):
        inv, port, _ = self.invoke()
        self.assertIsNone(port.invocation.attempt_number)
        self.assertTrue(port.capability.repository_mutation)
        self.assertEqual(1, self.store.fetch(inv.invocation_id)["attempt_number"])
        self.assertEqual("CONSUMED", self.snapshot()["reservations"][0]["state"])
        self.assertEqual("OPEN", self.snapshot()["attempts"][0]["state"])

    def test_definite_non_start_releases_without_consumption(self):
        with self.assertRaises(InvocationRejected):
            self.invoke(Port(StartDisposition.not_started))
        self.assertEqual([], self.snapshot()["attempts"])
        self.assertEqual("RELEASED", self.snapshot()["reservations"][0]["state"])
        self.assertEqual(1, self.controller.reserve("scope")["candidate_attempt_number"])

    def test_uncertain_start_retains_slot_and_requires_human_affirmative_resolution(self):
        with self.assertRaises(InvocationRejected):
            self.invoke(Port(StartDisposition.uncertain))
        reservation = self.snapshot()["reservations"][0]
        self.assertEqual("UNRESOLVED", reservation["state"])
        with self.assertRaises(ExecutionRejected):
            self.controller.reserve("scope")
        evidence = StartEvidence(StartDisposition.not_started, "recovered definite non-start")
        with self.assertRaises(ExecutionRejected):
            self.controller.resolve_reservation(reservation["reservation_id"], evidence)
        self.controller.resolve_reservation(reservation["reservation_id"], evidence, authorization=AUTH)
        self.assertEqual(1, self.controller.reserve("scope")["candidate_attempt_number"])
        self.assertEqual(
            ["objective_registered", "reservation_reserved", "reservation_unresolved", "reservation_released", "reservation_reserved"],
            [row["kind"] for row in self.snapshot()["execution_evidence"]],
        )

    def test_unresolved_accepted_resolution_consumes_but_retains_terminal_uncertainty(self):
        with self.assertRaises(InvocationRejected):
            self.invoke(Port(StartDisposition.uncertain))
        rid = self.snapshot()["reservations"][0]["reservation_id"]
        self.controller.resolve_reservation(rid, StartEvidence(StartDisposition.accepted, "recovered acceptance"), authorization=AUTH)
        self.assertEqual("RECONCILIATION_REQUIRED", self.snapshot()["attempts"][0]["state"])
        with self.assertRaises(ExecutionRejected):
            self.controller.reserve("scope")

    def test_handle_without_start_evidence_is_unresolved(self):
        self.invoke(Port(disposition=None))
        self.assertEqual("UNRESOLVED", self.snapshot()["reservations"][0]["state"])
        self.assertEqual([], self.snapshot()["attempts"])

    def test_reserved_and_consumed_open_exclude_new_reservations(self):
        reservation = self.controller.reserve("scope")
        with self.assertRaises(ExecutionRejected):
            self.controller.reserve("scope")
        ControlledInvocationGateway(self.repo, self.store, Port()).invoke(self.invocation(**reservation), "work")
        with self.assertRaises(ExecutionRejected):
            self.controller.reserve("scope")

    def test_pass_accepts_scope_and_blocks_all_later_port_calls(self):
        self.invoke()
        self.controller.close_attempt("scope", 1, PASS)
        self.assertEqual("ACCEPTED", self.snapshot()["scope"]["state"])
        with self.assertRaises(ExecutionRejected):
            self.controller.reserve("scope")
        port = Port()
        with self.assertRaises(InvocationRejected):
            ControlledInvocationGateway(self.repo, self.store, port).invoke(self.invocation(), "work")
        self.assertEqual(0, port.starts)

    def test_two_failures_open_circuit_and_attempt_three_never_reaches_port(self):
        port = Port()
        for number in (1, 2):
            inv, _, _ = self.invoke(port, run_id=f"run-{number}")
            self.assertEqual(number, self.store.fetch(inv.invocation_id)["attempt_number"])
            self.controller.close_attempt("scope", number, FAIL)
        self.assertEqual("CIRCUIT_OPEN", self.snapshot()["scope"]["state"])
        self.assertEqual(["FAILED", "FAILED"], [a["state"] for a in self.snapshot()["attempts"]])
        reopened = TelemetryStore(self.path)
        controller = BoundedExecutionController(self.repo, reopened)
        with self.assertRaises(ExecutionRejected):
            controller.reserve("scope")
        for purpose in InvocationPurpose:
            with self.subTest(purpose=purpose):
                with self.assertRaises(InvocationRejected):
                    ControlledInvocationGateway(self.repo, reopened, port).invoke(
                        self.invocation(run_id="new-process-run", invocation_purpose=purpose,
                                        reservation_id="forged", candidate_attempt_number=3), "forbidden work")
        self.assertEqual(2, port.starts, "attempt 3 and every post-circuit purpose must be blocked before AIRuntimePort")

    def test_final_failure_and_circuit_are_one_transaction(self):
        self.invoke()
        self.controller.close_attempt("scope", 1, FAIL)
        self.invoke()
        before = self.snapshot()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TRIGGER inject_commit_failure BEFORE UPDATE ON execution_scopes "
                               "WHEN NEW.state='CIRCUIT_OPEN' BEGIN SELECT RAISE(ABORT, 'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.controller.close_attempt("scope", 2, FAIL)
        self.assertEqual(before, self.snapshot(), "failed transaction must retain OPEN attempt and no failed checkpoint")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("DROP TRIGGER inject_commit_failure")
        self.controller.close_attempt("scope", 2, FAIL)
        self.assertEqual("CIRCUIT_OPEN", self.snapshot()["scope"]["state"])

    def test_restart_preserves_reserved_and_consumed_capacity(self):
        reservation = self.controller.reserve("scope")
        for consumed in (False, True):
            if consumed:
                ControlledInvocationGateway(self.repo, self.store, Port()).invoke(self.invocation(**reservation), "work")
            restarted = BoundedExecutionController(self.repo, TelemetryStore(self.path))
            with self.assertRaises(ExecutionRejected):
                restarted.reserve("scope")

    def test_concurrent_processes_cannot_own_same_active_candidate(self):
        # Every child opens its own store and competes for the final candidate.
        self.invoke()
        self.controller.close_attempt("scope", 1, FAIL)
        script = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from ai_execution.store import TelemetryStore
from ai_execution.execution import BoundedExecutionController, ExecutionRejected
c = BoundedExecutionController(Path(sys.argv[2]), TelemetryStore(Path(sys.argv[3])))
sys.stdin.readline()
try:
    print('OWNED', c.reserve('scope')['candidate_attempt_number'])
except ExecutionRejected:
    print('BLOCKED')
"""
        processes = [subprocess.Popen([sys.executable, "-c", script, str(ROOT / "src"), str(self.repo), str(self.path)],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                     for _ in range(6)]
        for process in processes:
            process.stdin.write("start\n")
            process.stdin.flush()
        outputs = []
        for process in processes:
            out, err = process.communicate(timeout=30)
            self.assertEqual(0, process.returncode, err)
            outputs.append(out.strip())
        self.assertEqual(1, outputs.count("OWNED 2"), outputs)
        self.assertEqual(5, outputs.count("BLOCKED"), outputs)

    def test_same_reservation_cannot_start_two_invocations(self):
        reservation = self.controller.reserve("scope")
        port = Port(block_observe=True)
        gateway = ControlledInvocationGateway(self.repo, self.store, port)
        failures = []
        def run():
            try:
                gateway.invoke(self.invocation(**reservation), "work")
            except Exception as exc:
                failures.append(exc)
        thread = threading.Thread(target=run)
        thread.start()
        self.assertTrue(port.entered.wait(3))
        with self.assertRaises(InvocationRejected):
            gateway.invoke(self.invocation(**reservation), "duplicate work")
        with self.assertRaises(ExecutionRejected):
            self.controller.close_attempt("scope", 1, FAIL)
        port.done.set()
        thread.join(5)
        self.assertEqual([], failures)
        self.assertEqual(1, port.starts)

    def test_consumed_timeout_requires_reconciliation(self):
        self.short_watchdog()
        _, port, outcome = self.invoke(Port(block_observe=True))
        self.assertEqual(1, port.interrupts)
        self.assertEqual(TerminalStatus.timeout, outcome.terminal_status)
        self.assertEqual("RECONCILIATION_REQUIRED", self.snapshot()["attempts"][0]["state"])
        self.assertEqual(5, outcome.usage.total_tokens)
        with self.assertRaises(ExecutionRejected):
            self.controller.reserve("scope")

    def test_pre_consumption_timeout_creates_no_attempt_and_retains_slot(self):
        self.short_watchdog()
        _, _, outcome = self.invoke(Port(block_start=True))
        self.assertEqual(TerminalStatus.timeout, outcome.terminal_status)
        self.assertEqual([], self.snapshot()["attempts"])
        self.assertEqual("UNRESOLVED", self.snapshot()["reservations"][0]["state"])

    def test_usage_limit_continuation_uses_same_attempt_and_preserves_unknown_usage(self):
        first, _, _ = self.invoke(Port(status=TerminalStatus.interrupted, reason=TerminalReason.usage_limit,
                                      usage=UsageEvidence.unknown()))
        self.assertEqual("SUSPENDED", self.snapshot()["attempts"][0]["state"])
        continuation = self.invocation(invocation_purpose=InvocationPurpose.continuation, attempt_number=1,
                                       resume_of_invocation_id=first.invocation_id, human_authorization=AUTH, run_id="new-run")
        port = Port()
        ControlledInvocationGateway(self.repo, self.store, port).invoke(continuation, "continue same objective")
        self.assertEqual("OPEN", self.snapshot()["attempts"][0]["state"])
        self.assertEqual(1, len(self.snapshot()["attempts"]))
        self.assertEqual(1, len(self.snapshot()["reservations"]))
        self.assertEqual(first.invocation_id, self.store.fetch(continuation.invocation_id)["resume_of_invocation_id"])
        self.assertEqual("unknown", self.store.fetch(first.invocation_id)["usage_status"])
        aggregate = self.store.dev_aggregate("DEV-008")
        self.assertEqual(2, aggregate["invocation_count"])
        self.assertEqual("incomplete", aggregate["usage_completeness"])
        self.assertNotIn("exact_total", aggregate)
        self.assertEqual(5, aggregate["known_subtotal"]["total_tokens"])
        attempt_usage = self.store.attempt_aggregate("scope", 1)
        self.assertEqual(2, attempt_usage["invocation_count"])
        self.assertEqual("incomplete", attempt_usage["usage_completeness"])
        self.assertNotIn("exact_total", attempt_usage)

    def test_continuation_requires_human_objective_scope_attempt_and_latest_lineage(self):
        first, _, _ = self.invoke(Port(status=TerminalStatus.interrupted, reason=TerminalReason.usage_limit))
        base = self.invocation(invocation_purpose=InvocationPurpose.continuation, attempt_number=1,
                               resume_of_invocation_id=first.invocation_id, human_authorization=AUTH)
        for changes in ({"human_authorization": None}, {"objective_id": "different"},
                        {"execution_scope_id": "different"}, {"attempt_number": 2},
                        {"resume_of_invocation_id": "missing"}, {"reservation_id": "new"}):
            port = Port()
            with self.subTest(changes=changes), self.assertRaises(InvocationRejected):
                ControlledInvocationGateway(self.repo, self.store, port).invoke(replace(base, **changes), "resume")
            self.assertEqual(0, port.starts)
        self.assertEqual("SUSPENDED", self.snapshot()["attempts"][0]["state"])

    def test_invocation_count_is_not_budget_and_continuation_never_replenishes(self):
        port = Port(status=TerminalStatus.interrupted, reason=TerminalReason.usage_limit)
        first, _, _ = self.invoke(port)
        for _ in range(3):
            first = self.invocation(invocation_purpose=InvocationPurpose.continuation, attempt_number=1,
                                    resume_of_invocation_id=first.invocation_id, human_authorization=AUTH)
            ControlledInvocationGateway(self.repo, self.store, port).invoke(first, "same attempt")
        self.assertEqual(4, port.starts)
        self.controller.close_attempt("scope", 1, FAIL)
        second, _, _ = self.invoke()
        self.assertEqual(2, second.candidate_attempt_number)
        self.controller.close_attempt("scope", 2, FAIL)
        with self.assertRaises(ExecutionRejected):
            self.controller.reserve("scope")

    def test_nonresumable_outcomes_never_resume_or_create_retry(self):
        for status in (TerminalStatus.failure, TerminalStatus.timeout, TerminalStatus.cancelled, TerminalStatus.unknown):
            with self.subTest(status=status):
                scope = f"scope-{status}"
                self.controller.create_scope(scope, dev_task="DEV-008", objective_id=f"objective-{status}", source_revision="base")
                inv, port, _ = self.invoke(Port(status=status, reason=TerminalReason.usage_limit),
                                           execution_scope_id=scope, objective_id=f"objective-{status}")
                with self.assertRaises(InvocationRejected):
                    ControlledInvocationGateway(self.repo, self.store, port).invoke(
                        self.invocation(execution_scope_id=scope, objective_id=f"objective-{status}",
                                        invocation_purpose=InvocationPurpose.continuation, attempt_number=1,
                                        resume_of_invocation_id=inv.invocation_id, human_authorization=AUTH), "resume")
                self.assertEqual(1, port.starts)

    def test_recovered_checkpoint_only_deterministically_closes_reconciliation(self):
        self.invoke(Port(status=TerminalStatus.failure))
        with self.assertRaises(ExecutionRejected):
            self.controller.close_attempt("scope", 1, AUTH)
        self.controller.close_attempt("scope", 1, FAIL)
        self.assertEqual(2, self.controller.reserve("scope")["candidate_attempt_number"])

    def test_recovered_usage_limit_allows_only_authorized_same_attempt_continuation(self):
        inv, _, _ = self.invoke(Port(status=TerminalStatus.unknown, usage=UsageEvidence.unknown()))
        with self.assertRaises(ExecutionRejected):
            self.controller.recover_usage_limit("scope", 1, invocation_id=inv.invocation_id,
                                                status="timeout", reason="usage_limit", evidence_reference="retained", authorization=AUTH)
        self.controller.recover_usage_limit("scope", 1, invocation_id=inv.invocation_id,
                                            status="interrupted", reason="usage_limit", evidence_reference="retained", authorization=AUTH)
        continuation = self.invocation(invocation_purpose=InvocationPurpose.continuation, attempt_number=1,
                                       resume_of_invocation_id=inv.invocation_id, human_authorization=AUTH)
        ControlledInvocationGateway(self.repo, self.store, Port()).invoke(continuation, "resume")
        self.assertEqual("OPEN", self.snapshot()["attempts"][0]["state"])
        self.assertEqual("unknown", self.store.fetch(inv.invocation_id)["terminal_status"])

    def test_successor_provenance_preserves_permanently_unresolved_predecessor(self):
        with self.assertRaises(InvocationRejected):
            self.invoke(Port(StartDisposition.uncertain))
        self.assert_successor_immutability()

    def test_successor_provenance_preserves_circuit_open_predecessor(self):
        for number in (1, 2):
            self.invoke()
            self.controller.close_attempt("scope", number, FAIL)
        self.assert_successor_immutability()

    def test_successor_provenance_preserves_reconciliation_predecessor(self):
        self.invoke(Port(status=TerminalStatus.failure))
        self.assert_successor_immutability()

    def assert_successor_immutability(self):
        before, invocations = self.snapshot(), list(self.store.rows())
        with self.assertRaises(ExecutionRejected):
            self.controller.create_scope("unlinked", dev_task="DEV-008", objective_id="objective", source_revision="new-base")
        with self.assertRaises(ExecutionRejected):
            self.controller.successor_scope("scope", "next", authorization=None)
        self.controller.successor_scope("scope", "next", authorization=AUTH)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(invocations, list(self.store.rows()))
        successor = self.controller.snapshot("next")
        evidence = json.loads(successor["execution_evidence"][0]["payload"])
        self.assertEqual("scope", evidence["predecessor_scope_id"])
        self.assertEqual("next", evidence["execution_scope_id"])
        for field in ("actor", "timestamp", "reason", "disposition"):
            self.assertEqual(getattr(AUTH, field), evidence[field])
        with self.assertRaises(ExecutionRejected):
            self.controller.reserve("scope")
        with self.assertRaises(ExecutionRejected):
            self.controller.successor_scope("scope", "duplicate", authorization=AUTH)
        rid = before["reservations"][0]["reservation_id"]
        with self.assertRaises(ExecutionRejected):
            self.controller.resolve_reservation(rid, StartEvidence(StartDisposition.not_started, "late"), authorization=AUTH)
        self.assertEqual(1, self.controller.reserve("next")["candidate_attempt_number"])

    def test_nonattempt_timeout_stops_scope_without_fake_capacity(self):
        self.short_watchdog()
        port = Port(block_observe=True)
        inv = self.invocation(invocation_purpose=InvocationPurpose.review, human_authorization=AUTH)
        ControlledInvocationGateway(self.repo, self.store, port).invoke(inv, "review")
        self.assertEqual([], self.snapshot()["attempts"])
        self.assertEqual([], self.snapshot()["reservations"])
        with self.assertRaises(ExecutionRejected):
            self.controller.reserve("scope")
        with self.assertRaises(InvocationRejected):
            ControlledInvocationGateway(self.repo, self.store, Port()).invoke(
                self.invocation(invocation_purpose=InvocationPurpose.review), "review")
        port = Port()
        ControlledInvocationGateway(self.repo, self.store, port).invoke(
            self.invocation(invocation_purpose=InvocationPurpose.review, human_authorization=AUTH), "authorized review")
        self.assertFalse(port.capability.repository_mutation)
        self.assertEqual("STOPPED", self.snapshot()["scope"]["state"])

    def test_migration_from_v1_and_v2_preserves_all_existing_evidence(self):
        for version in (1, 2):
            with self.subTest(version=version):
                path = self.repo / f"schema-{version}.sqlite3"
                store = TelemetryStore(path)
                inv = self.invocation(invocation_purpose=InvocationPurpose.review,
                                      human_authorization=AUTH)
                ControlledInvocationGateway(self.repo, store, Port()).invoke(inv, "review")
                store.finalize_dev_outcome("DEV-008", task_accepted=True)
                with closing(sqlite3.connect(path)) as connection, connection:
                    raw_before = connection.execute("SELECT * FROM invocations").fetchall()
                    outcomes = connection.execute("SELECT * FROM dev_outcomes").fetchall()
                    for table in ("execution_evidence", "invocation_attempts", "attempts", "reservations", "execution_scopes"):
                        connection.execute(f"DROP TABLE {table}")
                    if version == 1:
                        connection.execute("DROP TABLE dev_outcomes")
                    connection.execute(f"PRAGMA user_version={version}")
                TelemetryStore(path)
                with closing(sqlite3.connect(path)) as connection, connection:
                    self.assertEqual(SCHEMA_VERSION, connection.execute("PRAGMA user_version").fetchone()[0])
                    self.assertEqual(raw_before, connection.execute("SELECT * FROM invocations").fetchall())
                    self.assertEqual(outcomes if version == 2 else [], connection.execute("SELECT * FROM dev_outcomes").fetchall())

    def test_unknown_usage_stops_free_retry_even_after_failed_checkpoint(self):
        _, _, outcome = self.invoke(Port(usage=UsageEvidence.unknown()))
        self.assertTrue(outcome.human_attention_required)
        self.assertEqual("RECONCILIATION_REQUIRED", self.snapshot()["attempts"][0]["state"])
        self.controller.close_attempt("scope", 1, FAIL)
        with self.assertRaises(ExecutionRejected):
            self.controller.reserve("scope")

    def test_insufficient_later_evidence_never_releases_unresolved_slot(self):
        with self.assertRaises(InvocationRejected):
            self.invoke(Port(StartDisposition.uncertain))
        rid = self.snapshot()["reservations"][0]["reservation_id"]
        self.controller.resolve_reservation(rid, StartEvidence(StartDisposition.uncertain, "still unavailable"), authorization=AUTH)
        self.assertEqual("UNRESOLVED", self.snapshot()["reservations"][0]["state"])
        with self.assertRaises(ExecutionRejected):
            BoundedExecutionController(self.repo, TelemetryStore(self.path)).reserve("scope")

    def test_accepted_start_then_exception_consumes_and_requires_reconciliation(self):
        class AcceptedThenBroken(Port):
            def start(self, *args):
                super().start(*args)
                raise RuntimeError("transport failed after accepted execution")
        with self.assertRaises(InvocationRejected):
            self.invoke(AcceptedThenBroken())
        self.assertEqual("CONSUMED", self.snapshot()["reservations"][0]["state"])
        self.assertEqual("RECONCILIATION_REQUIRED", self.snapshot()["attempts"][0]["state"])

    def test_checkpoint_failure_cannot_be_relabelled_as_continuation(self):
        first, _, _ = self.invoke()
        self.controller.close_attempt("scope", 1, FAIL)
        port = Port()
        with self.assertRaises(InvocationRejected):
            ControlledInvocationGateway(self.repo, self.store, port).invoke(
                self.invocation(invocation_purpose=InvocationPurpose.continuation, attempt_number=1,
                                resume_of_invocation_id=first.invocation_id, human_authorization=AUTH), "retry as resume")
        self.assertEqual(0, port.starts)

    def test_terminal_evidence_is_immutable(self):
        inv, _, _ = self.invoke()
        before = self.store.fetch(inv.invocation_id)
        with self.assertRaises(ExecutionRejected):
            self.store.record_terminal(inv.invocation_id, status=TerminalStatus.interrupted,
                                       reason=TerminalReason.usage_limit, snapshot=RuntimeSnapshot(UsageEvidence.unknown()),
                                       human_attention_required=True, autonomous_follow_on_allowed=False)
        self.assertEqual(before, self.store.fetch(inv.invocation_id))

    def test_migrated_nonattempt_unknown_usage_cannot_reset_scope(self):
        path = self.repo / "legacy-stopped.sqlite3"
        store = TelemetryStore(path)
        inv = self.invocation(invocation_purpose=InvocationPurpose.review, human_authorization=AUTH)
        ControlledInvocationGateway(self.repo, store, Port(usage=UsageEvidence.unknown())).invoke(inv, "legacy review")
        with closing(sqlite3.connect(path)) as connection, connection:
            for table in ("execution_evidence", "invocation_attempts", "attempts", "reservations", "execution_scopes"):
                connection.execute(f"DROP TABLE {table}")
            connection.execute("PRAGMA user_version=2")
        migrated = TelemetryStore(path)
        controller = BoundedExecutionController(self.repo, migrated)
        controller.create_scope("scope", dev_task="DEV-008", objective_id="objective", source_revision="base")
        with self.assertRaises(ExecutionRejected):
            controller.reserve("scope")

    def test_adapter_conformance_accepted_nonstart_uncertain_and_mutation_profile(self):
        from ai_execution.codex_adapter import CodexRuntimeAdapter
        from ai_execution.runtime import CapabilityProfile, RuntimeStartControl
        calls = []

        class Thread:
            id = "native-thread"
            def turn(self, text, **options):
                calls.append(options)
                return SimpleNamespace(id="native-turn")

        class Client:
            def thread_start(self, **options):
                calls.append(options)
                return Thread()
            def close(self):
                pass

        evidence = []
        adapter = CodexRuntimeAdapter(repo=str(self.repo), codex_factory=Client)
        inv = self.invocation(**self.controller.reserve("scope"))
        handle = adapter.start(inv, "work", CapabilityProfile.implementation(), RuntimeStartControl(evidence.append))
        handle.close()
        self.assertEqual([StartDisposition.accepted], [e.disposition for e in evidence])
        self.assertTrue(all(c["sandbox"].value == "workspace-write" for c in calls))

        def local_failure():
            raise OSError("client construction failed before execution")
        evidence.clear()
        with self.assertRaises(OSError):
            CodexRuntimeAdapter(repo=str(self.repo), codex_factory=local_failure).start(
                inv, "work", CapabilityProfile.implementation(), RuntimeStartControl(evidence.append))
        self.assertEqual([StartDisposition.not_started], [e.disposition for e in evidence])

        class UncertainThread(Thread):
            def turn(self, *args, **kwargs):
                raise OSError("request sent, response lost")
        class UncertainClient(Client):
            def thread_start(self, **kwargs):
                return UncertainThread()
        evidence.clear()
        with self.assertRaises(OSError):
            CodexRuntimeAdapter(repo=str(self.repo), codex_factory=UncertainClient).start(
                inv, "work", CapabilityProfile.implementation(), RuntimeStartControl(evidence.append))
        self.assertEqual([], evidence, "request uncertainty must never be labelled definite non-start")
        for purpose in (InvocationPurpose.review, InvocationPurpose.orchestration, InvocationPurpose.acceptance_validation):
            with self.subTest(purpose=purpose), self.assertRaises(ValueError):
                adapter.start(self.invocation(invocation_purpose=purpose), "work",
                              CapabilityProfile.implementation(), RuntimeStartControl())


if __name__ == "__main__":
    unittest.main()
