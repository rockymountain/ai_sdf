"""DEV-008 durable scope accounting; all mutations use the store's transaction.

Objective IDs are stable workflow identities, not run IDs, prompts, or provider
session IDs. The workflow registers an objective once; further scopes for that
objective must use the authorized successor operation.
"""

from __future__ import annotations

import json
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .model import CheckpointEvidence, HumanAuthorization, InvocationPurpose
from .policy import load_watchdog_policy
from .runtime import StartDisposition, StartEvidence


class ExecutionRejected(ValueError):
    human_attention_required = True
    autonomous_follow_on_allowed = False


NONIMPLEMENTATION_AUTHORIZED_PURPOSES = frozenset({
    InvocationPurpose.acceptance_validation,
    InvocationPurpose.review,
    InvocationPurpose.orchestration,
})


SCHEMA = """
CREATE TABLE IF NOT EXISTS execution_scopes (
    execution_scope_id TEXT PRIMARY KEY,
    dev_task TEXT NOT NULL,
    objective_id TEXT NOT NULL,
    source_revision TEXT NOT NULL,
    max_attempts INTEGER NOT NULL CHECK (max_attempts > 0),
    state TEXT NOT NULL CHECK (state IN ('ACTIVE','STOPPED','ACCEPTED','CIRCUIT_OPEN')),
    predecessor_scope_id TEXT UNIQUE REFERENCES execution_scopes(execution_scope_id),
    authorization TEXT,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_objective_root
    ON execution_scopes(dev_task, objective_id) WHERE predecessor_scope_id IS NULL;
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id TEXT PRIMARY KEY,
    execution_scope_id TEXT NOT NULL REFERENCES execution_scopes(execution_scope_id),
    candidate_attempt_number INTEGER NOT NULL CHECK (candidate_attempt_number > 0),
    state TEXT NOT NULL CHECK (state IN ('RESERVED','CONSUMED','RELEASED','UNRESOLVED')),
    invocation_id TEXT UNIQUE REFERENCES invocations(invocation_id),
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_candidate
    ON reservations(execution_scope_id) WHERE state IN ('RESERVED','UNRESOLVED');
CREATE TABLE IF NOT EXISTS attempts (
    execution_scope_id TEXT NOT NULL REFERENCES execution_scopes(execution_scope_id),
    attempt_number INTEGER NOT NULL,
    reservation_id TEXT NOT NULL UNIQUE REFERENCES reservations(reservation_id),
    state TEXT NOT NULL CHECK (state IN ('OPEN','PASSED','FAILED','SUSPENDED','RECONCILIATION_REQUIRED')),
    latest_invocation_id TEXT NOT NULL REFERENCES invocations(invocation_id),
    PRIMARY KEY (execution_scope_id, attempt_number)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_attempt
    ON attempts(execution_scope_id) WHERE state NOT IN ('PASSED','FAILED');
CREATE TABLE IF NOT EXISTS invocation_attempts (
    invocation_id TEXT PRIMARY KEY REFERENCES invocations(invocation_id),
    reservation_id TEXT REFERENCES reservations(reservation_id),
    candidate_attempt_number INTEGER,
    attempt_number INTEGER,
    resume_of_invocation_id TEXT UNIQUE REFERENCES invocations(invocation_id),
    human_authorization TEXT
);
CREATE TABLE IF NOT EXISTS execution_evidence (
    evidence_id INTEGER PRIMARY KEY,
    execution_scope_id TEXT NOT NULL REFERENCES execution_scopes(execution_scope_id),
    reservation_id TEXT REFERENCES reservations(reservation_id),
    invocation_id TEXT REFERENCES invocations(invocation_id),
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
"""


def now():
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _authorization(value):
    if not isinstance(value, HumanAuthorization):
        raise ExecutionRejected("explicit recorded human authorization is required")
    return json.dumps(asdict(value), sort_keys=True)


def validate_start_authorization(invocation):
    """Validate prospective per-invocation authority before start persistence."""
    if invocation.invocation_purpose in NONIMPLEMENTATION_AUTHORIZED_PURPOSES:
        return json.loads(_authorization(invocation.human_authorization))
    return None


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ExecutionRejected(f"{name} is required")


def _scope(connection, scope_id, *, mutable=True):
    row = connection.execute(
        "SELECT * FROM execution_scopes WHERE execution_scope_id=?", (scope_id,)
    ).fetchone()
    if row is None:
        raise ExecutionRejected("unknown execution scope")
    if mutable and (row["state"] in {"CIRCUIT_OPEN", "ACCEPTED"} or connection.execute(
        "SELECT 1 FROM execution_scopes WHERE predecessor_scope_id=?", (scope_id,)
    ).fetchone()):
        raise ExecutionRejected("execution scope is permanently closed")
    return row


def _event(connection, scope_id, kind, payload, reservation_id=None, invocation_id=None):
    connection.execute(
        "INSERT INTO execution_evidence "
        "(execution_scope_id,reservation_id,invocation_id,kind,payload,recorded_at) "
        "VALUES (?,?,?,?,?,?)",
        (scope_id, reservation_id, invocation_id, kind, json.dumps(payload, sort_keys=True), now()),
    )


def _no_live_invocation(connection, scope_id):
    if connection.execute(
        "SELECT 1 FROM invocations WHERE execution_scope_id=? AND completed_at IS NULL",
        (scope_id,),
    ).fetchone():
        raise ExecutionRejected("scope has a live invocation; terminal evidence is required")


def _legacy_state(connection, scope_id, exclude_invocation_id=""):
    # v1/v2 had no attempt budget, but their retained timeout/unknown evidence
    # must not be erased by upgrading or registering that existing scope.
    unsafe = connection.execute(
        "SELECT 1 FROM invocations WHERE execution_scope_id=? AND invocation_id<>? "
        "AND (completed_at IS NULL OR terminal_status<>'success' OR usage_status IS NULL OR usage_status<>'exact')",
        (scope_id, exclude_invocation_id),
    ).fetchone()
    return "STOPPED" if unsafe else "ACTIVE"


def _implementation_authority(connection, scope):
    """Only trusted workflow events register capacity, never invocation metadata.

    Old roots without registration evidence fail closed until create_scope is
    explicitly called with their unchanged identity. No schema backfill guesses
    whether an old root was registered or created by the compatibility path.
    """
    return connection.execute(
        "SELECT 1 FROM execution_evidence WHERE execution_scope_id=? AND "
        "(kind='objective_registered' OR (kind='successor_authorized' AND ? IS NOT NULL AND ? IS NOT NULL))",
        (scope["execution_scope_id"], scope["predecessor_scope_id"], scope["authorization"]),
    ).fetchone() is not None


def _autonomy_blockers(connection, scope_id, *, active_invocation_id=None, resume_of=None):
    """Derive independent blockers from retained evidence in the caller's transaction.

    P1-I16 exempts only interrupted/usage_limit predecessors in the authorized
    continuation chain of the current open attempt. It never exempts a review,
    another attempt, or unknown usage when allocating a new attempt.
    """
    attempts = {row["attempt_number"]: row for row in connection.execute(
        "SELECT * FROM attempts WHERE execution_scope_id=?", (scope_id,))}
    invocations = {row["invocation_id"]: row for row in connection.execute(
        "SELECT i.*, a.reservation_id, a.attempt_number, a.resume_of_invocation_id, a.human_authorization "
        "FROM invocations i LEFT JOIN invocation_attempts a USING(invocation_id) WHERE i.execution_scope_id=?",
        (scope_id,))}
    reservations = {row["reservation_id"]: row for row in connection.execute(
        "SELECT * FROM reservations WHERE execution_scope_id=?", (scope_id,))}
    recovered_usage_limits = set()
    authorized_releases = set()
    for row in connection.execute("SELECT * FROM execution_evidence WHERE execution_scope_id=?", (scope_id,)):
        if row["kind"] == "recovered_usage_limit":
            payload = json.loads(row["payload"])
            if (payload.get("terminal_status") == "interrupted" and payload.get("terminal_reason") == "usage_limit"
                    and payload.get("authorization")):
                recovered_usage_limits.add(row["invocation_id"])
        elif row["kind"] == "reservation_released" and json.loads(row["payload"]).get("authorization"):
            authorized_releases.add(row["reservation_id"])

    lineage = set()
    resuming_attempt = None
    for number, attempt in attempts.items():
        latest = invocations.get(attempt["latest_invocation_id"])
        if attempt["state"] == "SUSPENDED" and attempt["latest_invocation_id"] == resume_of:
            predecessor = latest
            resuming_attempt = number
        elif (attempt["state"] == "OPEN" and latest is not None
              and latest["invocation_purpose"] == "continuation" and latest["human_authorization"]):
            predecessor = invocations.get(latest["resume_of_invocation_id"])
        else:
            continue
        while predecessor is not None and predecessor["invocation_id"] not in lineage:
            if predecessor["attempt_number"] != number:
                break
            lineage.add(predecessor["invocation_id"])
            if not predecessor["human_authorization"]:
                break
            predecessor = invocations.get(predecessor["resume_of_invocation_id"])

    blockers = {f"reservation:{rid}" for rid, row in reservations.items() if row["state"] == "UNRESOLVED"}
    blockers.update(f"attempt:{number}" for number, row in attempts.items()
                    if row["state"] in {"SUSPENDED", "RECONCILIATION_REQUIRED"} and number != resuming_attempt)
    for invocation_id, row in invocations.items():
        if row["completed_at"] is None:
            if invocation_id != active_invocation_id:
                blockers.add(f"inflight:{invocation_id}")
            continue
        reservation = reservations.get(row["reservation_id"])
        if reservation is not None and reservation["state"] == "RELEASED":
            # Affirmative non-start resolves this invocation only. A pre-start
            # timeout still needs human disposition, evidenced by its release.
            if row["terminal_status"] != "timeout" or row["reservation_id"] in authorized_releases:
                continue
        usage_limit = ((row["terminal_status"] == "interrupted" and row["terminal_reason"] == "usage_limit")
                       or invocation_id in recovered_usage_limits)
        if invocation_id in lineage and usage_limit:
            continue
        if row["usage_status"] != "exact":
            blockers.add(f"usage:{invocation_id}")
        attempt = attempts.get(row["attempt_number"])
        checkpoint_closed = attempt is not None and attempt["state"] in {"PASSED", "FAILED"}
        if row["terminal_status"] != "success" and not checkpoint_closed:
            blockers.add(f"terminal:{invocation_id}")
    return blockers


def _refresh_scope_state(connection, scope_id, *, active_invocation_id=None):
    scope = _scope(connection, scope_id, mutable=False)
    # Closed/predecessor evidence stays immutable. All other state changes must
    # compose the remaining blockers rather than unconditionally assign ACTIVE.
    if scope["state"] in {"ACCEPTED", "CIRCUIT_OPEN"} or connection.execute(
        "SELECT 1 FROM execution_scopes WHERE predecessor_scope_id=?", (scope_id,)
    ).fetchone():
        return scope
    blockers = _autonomy_blockers(connection, scope_id, active_invocation_id=active_invocation_id)
    connection.execute("UPDATE execution_scopes SET state=? WHERE execution_scope_id=?",
                       ("STOPPED" if blockers else "ACTIVE", scope_id))
    return _scope(connection, scope_id)


def authorize_start(connection, invocation, max_attempts, *, nonimplementation_authorization=None):
    """Called inside the same transaction that persists invocation start."""
    scope_id = invocation.execution_scope_id
    purpose = invocation.invocation_purpose
    scope = connection.execute(
        "SELECT * FROM execution_scopes WHERE execution_scope_id=?", (scope_id,)
    ).fetchone()
    if scope is None:
        if purpose in {InvocationPurpose.implementation, InvocationPurpose.continuation}:
            raise ExecutionRejected("implementation objective must be registered")
        # Legacy non-mutating invocations acquire durable circuit identity without
        # reserving or consuming capacity. Their objective defaults to their scope.
        connection.execute(
            "INSERT INTO execution_scopes VALUES (?,?,?,?,?,?,NULL,NULL,?)",
            (scope_id, invocation.dev_task, invocation.objective_id or scope_id,
             invocation.source_revision, max_attempts,
             _legacy_state(connection, scope_id, invocation.invocation_id), now()),
        )
    _scope(connection, scope_id)
    scope = _refresh_scope_state(connection, scope_id, active_invocation_id=invocation.invocation_id)
    if (scope["dev_task"] != invocation.dev_task
            or scope["source_revision"] != invocation.source_revision
            or scope["max_attempts"] != max_attempts):
        raise ExecutionRejected("scope attribution or canonical budget differs")
    # Serialize all controlled starts in a scope. This also prevents checkpoint
    # closure from racing a review or a second invocation of one reservation.
    if connection.execute(
        "SELECT 1 FROM invocations WHERE execution_scope_id=? "
        "AND completed_at IS NULL AND invocation_id<>?",
        (scope_id, invocation.invocation_id),
    ).fetchone():
        raise ExecutionRejected("another invocation is active in this scope")
    if purpose not in {InvocationPurpose.implementation, InvocationPurpose.continuation}:
        if any(value is not None for value in (
            invocation.reservation_id, invocation.candidate_attempt_number,
            invocation.attempt_number, invocation.resume_of_invocation_id,
        )):
            raise ExecutionRejected("non-implementation purpose cannot claim attempt identity")
        if purpose in NONIMPLEMENTATION_AUTHORIZED_PURPOSES:
            if nonimplementation_authorization is None:
                raise ExecutionRejected("explicit recorded human authorization is required")
            _event(
                connection,
                scope_id,
                "nonimplementation_authorized",
                nonimplementation_authorization,
                invocation_id=invocation.invocation_id,
            )
        if scope["state"] == "STOPPED":
            _event(connection, scope_id, "non_mutating_disposition", nonimplementation_authorization,
                   invocation_id=invocation.invocation_id)
        return
    if invocation.objective_id != scope["objective_id"]:
        raise ExecutionRejected("implementation objective must remain unchanged")
    if not _implementation_authority(connection, scope):
        raise ExecutionRejected("explicit trusted implementation objective registration is required")
    if purpose == InvocationPurpose.implementation:
        if scope["state"] != "ACTIVE":
            raise ExecutionRejected("scope is stopped")
        if invocation.attempt_number is not None or invocation.resume_of_invocation_id is not None:
            raise ExecutionRejected("reservation alone cannot create an attempt")
        row = connection.execute(
            "SELECT * FROM reservations WHERE reservation_id=?", (invocation.reservation_id,)
        ).fetchone()
        if (row is None or row["execution_scope_id"] != scope_id or row["state"] != "RESERVED"
                or row["invocation_id"] is not None
                or type(invocation.candidate_attempt_number) is not int
                or row["candidate_attempt_number"] != invocation.candidate_attempt_number
                or row["candidate_attempt_number"] > max_attempts):
            raise ExecutionRejected("an exclusive active reservation is required")
        connection.execute("UPDATE reservations SET invocation_id=? WHERE reservation_id=?",
                           (invocation.invocation_id, row["reservation_id"]))
        connection.execute(
            "INSERT INTO invocation_attempts VALUES (?,?,?,NULL,NULL,NULL)",
            (invocation.invocation_id, row["reservation_id"], row["candidate_attempt_number"]),
        )
    else:
        authorization = _authorization(invocation.human_authorization)
        if (invocation.reservation_id is not None or invocation.candidate_attempt_number is not None
                or type(invocation.attempt_number) is not int):
            raise ExecutionRejected("continuation requires only an existing consumed attempt")
        attempt = connection.execute(
            "SELECT * FROM attempts WHERE execution_scope_id=? AND attempt_number=?",
            (scope_id, invocation.attempt_number),
        ).fetchone()
        if (attempt is None or attempt["state"] != "SUSPENDED"
                or attempt["latest_invocation_id"] != invocation.resume_of_invocation_id):
            raise ExecutionRejected("continuation requires suspended, open checkpoint and predecessor lineage")
        if _autonomy_blockers(connection, scope_id, active_invocation_id=invocation.invocation_id,
                              resume_of=invocation.resume_of_invocation_id):
            raise ExecutionRejected("independent autonomy blockers prevent continuation")
        connection.execute(
            "INSERT INTO invocation_attempts VALUES (?,NULL,NULL,?,?,?)",
            (invocation.invocation_id, invocation.attempt_number,
             invocation.resume_of_invocation_id, authorization),
        )
        connection.execute(
            "UPDATE attempts SET state='OPEN', latest_invocation_id=? "
            "WHERE execution_scope_id=? AND attempt_number=?",
            (invocation.invocation_id, scope_id, invocation.attempt_number),
        )
        _event(connection, scope_id, "continuation_authorized", json.loads(authorization),
               invocation_id=invocation.invocation_id)
        _refresh_scope_state(connection, scope_id, active_invocation_id=invocation.invocation_id)


def apply_start_evidence(connection, reservation_id, evidence, *, authorization=None):
    if not isinstance(evidence, StartEvidence):
        raise ExecutionRejected("affirmative provider-neutral StartEvidence is required")
    reservation = connection.execute(
        "SELECT * FROM reservations WHERE reservation_id=?", (reservation_id,)
    ).fetchone()
    if reservation is None:
        raise ExecutionRejected("unknown reservation")
    scope_id = reservation["execution_scope_id"]
    scope = _scope(connection, scope_id)
    if reservation["state"] not in {"RESERVED", "UNRESOLVED"}:
        raise ExecutionRejected("final reservation evidence is immutable")
    if reservation["state"] == "UNRESOLVED":
        _authorization(authorization)
    state = {StartDisposition.accepted: "CONSUMED", StartDisposition.not_started: "RELEASED",
             StartDisposition.uncertain: "UNRESOLVED"}[evidence.disposition]
    invocation_id = reservation["invocation_id"]
    if state == "CONSUMED":
        if invocation_id is None:
            raise ExecutionRejected("accepted execution requires persisted invocation identity")
        number = reservation["candidate_attempt_number"]
        if number > scope["max_attempts"]:
            raise ExecutionRejected("candidate exceeds governed budget")
        terminal = connection.execute("SELECT * FROM invocations WHERE invocation_id=?", (invocation_id,)).fetchone()
        attempt_state = "OPEN"
        if terminal["completed_at"] is not None:
            attempt_state = terminal_attempt_state(terminal["terminal_status"], terminal["terminal_reason"],
                                                   terminal["usage_status"])
        connection.execute("INSERT INTO attempts VALUES (?,?,?,?,?)",
                           (scope_id, number, reservation_id, attempt_state, invocation_id))
        connection.execute("UPDATE invocation_attempts SET attempt_number=? WHERE invocation_id=?",
                           (number, invocation_id))
    connection.execute("UPDATE reservations SET state=? WHERE reservation_id=?", (state, reservation_id))
    payload = asdict(evidence)
    if authorization is not None:
        payload["authorization"] = json.loads(_authorization(authorization))
    _event(connection, scope_id, "reservation_" + state.lower(), payload, reservation_id, invocation_id)
    _refresh_scope_state(connection, scope_id, active_invocation_id=invocation_id)


def terminal_attempt_state(status, reason, usage_status):
    if status == "interrupted" and reason == "usage_limit":
        return "SUSPENDED"
    if status == "success" and usage_status == "exact":
        return "OPEN"
    return "RECONCILIATION_REQUIRED"


def apply_terminal(connection, invocation_id, status, reason, usage_status):
    invocation = connection.execute("SELECT * FROM invocations WHERE invocation_id=?", (invocation_id,)).fetchone()
    scope_id = invocation["execution_scope_id"]
    scope = connection.execute("SELECT * FROM execution_scopes WHERE execution_scope_id=?", (scope_id,)).fetchone()
    if scope is None:  # Unchanged legacy rows may be finalized after migration.
        return
    _scope(connection, scope_id)
    identity = connection.execute("SELECT * FROM invocation_attempts WHERE invocation_id=?", (invocation_id,)).fetchone()
    if identity is not None:
        if identity["reservation_id"] is not None and identity["attempt_number"] is None:
            reservation = connection.execute("SELECT * FROM reservations WHERE reservation_id=?",
                                             (identity["reservation_id"],)).fetchone()
            if reservation["state"] == "RESERVED":
                apply_start_evidence(connection, reservation["reservation_id"],
                                     StartEvidence(StartDisposition.uncertain, "start returned without affirmative evidence"))
        if identity["attempt_number"] is not None:
            state = terminal_attempt_state(status, reason, usage_status)
            connection.execute("UPDATE attempts SET state=? WHERE execution_scope_id=? AND attempt_number=?",
                               (state, scope_id, identity["attempt_number"]))
    _refresh_scope_state(connection, scope_id)


class BoundedExecutionController:
    """Trusted workflow API. Policy is reread on every operation; no fallback."""

    def __init__(self, repo: Path, store):
        self.repo, self.store = Path(repo), store

    def _budget(self):
        return load_watchdog_policy(self.repo).max_attempts

    def create_scope(self, scope_id, *, dev_task, objective_id, source_revision):
        budget = self._budget()
        for name, value in (("scope_id", scope_id), ("dev_task", dev_task),
                            ("objective_id", objective_id), ("source_revision", source_revision)):
            _text(value, name)
        with closing(self.store._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT * FROM execution_scopes WHERE execution_scope_id=?", (scope_id,)).fetchone()
            if existing is not None:
                _scope(connection, scope_id)
                if (_implementation_authority(connection, existing)
                        or (existing["dev_task"], existing["objective_id"], existing["source_revision"], existing["max_attempts"])
                        != (dev_task, objective_id, source_revision, budget)):
                    raise ExecutionRejected("scope is already registered or its identity differs")
                _event(connection, scope_id, "objective_registered",
                       {"dev_task": dev_task, "objective_id": objective_id, "source_revision": source_revision})
                _refresh_scope_state(connection, scope_id)
                return
            if connection.execute("SELECT 1 FROM execution_scopes WHERE dev_task=? AND objective_id=?",
                                  (dev_task, objective_id)).fetchone():
                raise ExecutionRejected("objective already has a scope; linked human-authorized successor required")
            connection.execute("INSERT INTO execution_scopes VALUES (?,?,?,?,?,?,NULL,NULL,?)",
                               (scope_id, dev_task, objective_id, source_revision, budget,
                                _legacy_state(connection, scope_id), now()))
            _event(connection, scope_id, "objective_registered",
                   {"dev_task": dev_task, "objective_id": objective_id, "source_revision": source_revision})

    def reserve(self, scope_id):
        budget = self._budget()
        with closing(self.store._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            scope = _scope(connection, scope_id)
            if not _implementation_authority(connection, scope):
                raise ExecutionRejected("explicit trusted implementation objective registration is required")
            scope = _refresh_scope_state(connection, scope_id)
            if scope["state"] != "ACTIVE" or scope["max_attempts"] != budget:
                raise ExecutionRejected("scope is stopped or canonical policy changed")
            _no_live_invocation(connection, scope_id)
            if connection.execute("SELECT 1 FROM reservations WHERE execution_scope_id=? "
                                  "AND state IN ('RESERVED','UNRESOLVED')", (scope_id,)).fetchone():
                raise ExecutionRejected("scope already owns a candidate slot")
            if connection.execute("SELECT 1 FROM attempts WHERE execution_scope_id=? AND state<>'FAILED'",
                                  (scope_id,)).fetchone():
                raise ExecutionRejected("previous attempt is not deterministically failed")
            number = connection.execute("SELECT COUNT(*) FROM attempts WHERE execution_scope_id=?", (scope_id,)).fetchone()[0] + 1
            if number > budget:
                raise ExecutionRejected("attempt budget exhausted")
            reservation_id = str(uuid4())
            connection.execute("INSERT INTO reservations VALUES (?,?,?,'RESERVED',NULL,?)",
                               (reservation_id, scope_id, number, now()))
            _event(connection, scope_id, "reservation_reserved", {"candidate_attempt_number": number}, reservation_id)
            return {"reservation_id": reservation_id, "candidate_attempt_number": number}

    def resolve_reservation(self, reservation_id, evidence, *, authorization=None):
        self._budget()
        with closing(self.store._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            reservation = connection.execute("SELECT * FROM reservations WHERE reservation_id=?",
                                             (reservation_id,)).fetchone()
            if reservation is not None:
                _no_live_invocation(connection, reservation["execution_scope_id"])
            apply_start_evidence(connection, reservation_id, evidence, authorization=authorization)

    def close_attempt(self, scope_id, attempt_number, checkpoint):
        budget = self._budget()
        if type(attempt_number) is not int or attempt_number <= 0:
            raise ExecutionRejected("positive integer attempt_number required")
        if not isinstance(checkpoint, CheckpointEvidence):
            raise ExecutionRejected("deterministic checkpoint evidence is required")
        with closing(self.store._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            scope = _scope(connection, scope_id)
            if scope["max_attempts"] != budget:
                raise ExecutionRejected("canonical policy differs from scope budget")
            _no_live_invocation(connection, scope_id)
            attempt = connection.execute("SELECT * FROM attempts WHERE execution_scope_id=? AND attempt_number=?",
                                         (scope_id, attempt_number)).fetchone()
            if attempt is None or attempt["state"] in {"PASSED", "FAILED"}:
                raise ExecutionRejected("checkpoint must close an existing unclosed consumed attempt")
            passed = checkpoint.exit_code == 0
            _event(connection, scope_id, "deterministic_checkpoint", asdict(checkpoint), attempt["reservation_id"])
            connection.execute("UPDATE attempts SET state=? WHERE execution_scope_id=? AND attempt_number=?",
                               ("PASSED" if passed else "FAILED", scope_id, attempt_number))
            state = "ACCEPTED" if passed else ("CIRCUIT_OPEN" if attempt_number >= budget else "ACTIVE")
            connection.execute("UPDATE execution_scopes SET state=? WHERE execution_scope_id=?", (state, scope_id))
            state = _refresh_scope_state(connection, scope_id)["state"]
            _event(connection, scope_id, "scope_" + state.lower(), {"attempt_number": attempt_number})

    def recover_usage_limit(self, scope_id, attempt_number, *, invocation_id, status, reason, evidence_reference, authorization):
        self._budget()
        auth = _authorization(authorization)
        _text(evidence_reference, "evidence_reference")
        if status != "interrupted" or reason != "usage_limit":
            raise ExecutionRejected("only affirmative interrupted/usage_limit evidence permits suspension")
        with closing(self.store._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            _scope(connection, scope_id)
            _no_live_invocation(connection, scope_id)
            changed = connection.execute(
                "UPDATE attempts SET state='SUSPENDED' WHERE execution_scope_id=? AND attempt_number=? "
                "AND state='RECONCILIATION_REQUIRED' AND latest_invocation_id=?",
                (scope_id, attempt_number, invocation_id),
            ).rowcount
            if changed != 1:
                raise ExecutionRejected("recovery must identify latest reconciliation-required invocation")
            _event(connection, scope_id, "recovered_usage_limit",
                   {"terminal_status": status, "terminal_reason": reason, "reference": evidence_reference,
                    "authorization": json.loads(auth)}, invocation_id=invocation_id)

    def successor_scope(self, predecessor_scope_id, successor_scope_id, *, authorization):
        budget = self._budget()
        auth = _authorization(authorization)
        _text(successor_scope_id, "successor_scope_id")
        with closing(self.store._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            predecessor = _scope(connection, predecessor_scope_id, mutable=False)
            if predecessor["state"] not in {"STOPPED", "CIRCUIT_OPEN"}:
                raise ExecutionRejected("successor requires a stopped or circuit-open predecessor")
            _no_live_invocation(connection, predecessor_scope_id)
            if connection.execute("SELECT 1 FROM execution_scopes WHERE predecessor_scope_id=?",
                                  (predecessor_scope_id,)).fetchone():
                raise ExecutionRejected("predecessor already has an authorized successor")
            connection.execute("INSERT INTO execution_scopes VALUES (?,?,?,?,?,'ACTIVE',?,?,?)",
                               (successor_scope_id, predecessor["dev_task"], predecessor["objective_id"],
                                predecessor["source_revision"], budget, predecessor_scope_id, auth, now()))
            # All provenance belongs to the successor; predecessor rows are untouched.
            _event(connection, successor_scope_id, "successor_authorized",
                   {"predecessor_scope_id": predecessor_scope_id, "execution_scope_id": successor_scope_id,
                    **json.loads(auth)})

    def snapshot(self, scope_id):
        with closing(self.store._connect()) as connection, connection:
            connection.execute("BEGIN")
            scope = dict(_scope(connection, scope_id, mutable=False))
            result = {"scope": scope}
            for table in ("reservations", "attempts", "execution_evidence"):
                result[table] = [dict(row) for row in connection.execute(
                    f"SELECT * FROM {table} WHERE execution_scope_id=? ORDER BY rowid", (scope_id,))]
            return result
