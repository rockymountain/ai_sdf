"""Controlled invocation gateway with durable start evidence and finite watchdog."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Callable

from .model import (
    ControlledAIInvocation,
    InvocationPurpose,
    TerminalReason,
    TerminalStatus,
    UsageEvidence,
)
from .policy import load_watchdog_policy
from .runtime import (
    AIRuntimePort,
    CapabilityProfile,
    RuntimeResult,
    RuntimeSnapshot,
    RuntimeStartControl,
)
from .store import TelemetryStore


class InvocationRejected(RuntimeError):
    """The gateway rejected an invocation before it reached AIRuntimePort."""


@dataclass(frozen=True, slots=True)
class InvocationOutcome:
    invocation_id: str
    terminal_status: TerminalStatus
    terminal_reason: TerminalReason | None
    usage: UsageEvidence
    human_attention_required: bool
    autonomous_follow_on_allowed: bool
    runtime_session_id: str | None = None
    runtime_invocation_id: str | None = None
    observed_model: str | None = None
    tool_item_count: int = 0


class _Watchdog:
    """Revoke start or interrupt an attached handle when the deadline expires."""

    def __init__(
        self,
        seconds: int,
        interrupt: Callable[[object], None],
        start_control: RuntimeStartControl,
    ):
        self.seconds = seconds
        self.deadline = monotonic() + seconds
        self._interrupt = interrupt
        self._start_control = start_control
        self._cancelled = threading.Event()
        self.expired = threading.Event()
        self._lock = threading.Lock()
        self._handle: object | None = None
        self._handle_interrupted = False
        self.interrupt_error: str | None = None
        self._thread = threading.Thread(target=self._run, name="sdf-invocation-watchdog", daemon=True)

    def arm(self) -> None:
        self._thread.start()

    def attach(self, handle: object) -> None:
        with self._lock:
            self._handle = handle
            expired = self.expired.is_set()
        if expired:
            self._interrupt_handle(handle)

    def cancel(self) -> None:
        self._cancelled.set()
        if threading.current_thread() is not self._thread:
            self._thread.join()

    def _run(self) -> None:
        if self._cancelled.wait(max(0.0, self.deadline - monotonic())):
            return
        self._expire()

    def expire_if_due(self) -> None:
        """Close scheduler races before accepting a result at the deadline."""
        if monotonic() >= self.deadline:
            self._expire()

    def _expire(self) -> None:
        with self._lock:
            if self.expired.is_set():
                return
            self.expired.set()
            handle = self._handle
        if handle is None:
            self._start_control.cancel()
        else:
            self._interrupt_handle(handle)

    def _interrupt_handle(self, handle: object) -> None:
        with self._lock:
            if self._handle_interrupted:
                return
            self._handle_interrupted = True
        try:
            self._interrupt(handle)
        except Exception as exc:  # interruption failure remains terminal evidence
            self.interrupt_error = type(exc).__name__


class ControlledInvocationGateway:
    """The only DEV-007 path from governed invocation intent to AI runtime spend."""

    def __init__(self, repo: Path, store: TelemetryStore, runtime: AIRuntimePort):
        self.repo = Path(repo)
        self.store = store
        self.runtime = runtime

    def invoke(self, invocation: ControlledAIInvocation, input_text: str) -> InvocationOutcome:
        if not isinstance(input_text, str) or not input_text.strip():
            raise InvocationRejected("controlled invocation input must be nonempty")
        capability = self._capability_for(invocation)
        try:
            policy = load_watchdog_policy(self.repo)
        except ValueError as exc:
            raise InvocationRejected(str(exc)) from exc

        # The durable insert proves the evidence store is writable before runtime start.
        try:
            self.store.record_start(
                invocation,
                capability,
                policy.max_invocation_seconds,
                adapter_name=self.runtime.adapter_name,
                adapter_version=self.runtime.adapter_version,
            )
        except Exception as exc:
            raise InvocationRejected(f"telemetry start persistence failed: {type(exc).__name__}") from exc

        start_control = RuntimeStartControl()
        watchdog = _Watchdog(
            policy.max_invocation_seconds,
            self.runtime.interrupt,
            start_control,
        )
        watchdog.arm()
        handle: object | None = None
        latest = RuntimeSnapshot(UsageEvidence.unknown())
        latest_lock = threading.Lock()
        starts: queue.Queue[object | BaseException] = queue.Queue(maxsize=1)
        outcomes: queue.Queue[RuntimeResult | BaseException] = queue.Queue(maxsize=1)

        def publish(snapshot: RuntimeSnapshot) -> None:
            nonlocal latest
            with latest_lock:
                latest = snapshot

        try:
            def start_runtime() -> None:
                try:
                    starts.put(
                        self.runtime.start(
                            invocation,
                            input_text,
                            capability,
                            start_control,
                        )
                    )
                except BaseException as exc:
                    starts.put(exc)

            threading.Thread(
                target=start_runtime,
                name=f"sdf-start-{invocation.invocation_id}",
                daemon=True,
            ).start()
            started_value = starts.get()
            watchdog.expire_if_due()
            if isinstance(started_value, BaseException):
                if watchdog.expired.is_set():
                    return self._finish_timeout(
                        invocation.invocation_id,
                        latest,
                        watchdog,
                        start_control,
                        error_reference=type(started_value).__name__,
                    )
                self._finish(
                    invocation.invocation_id,
                    TerminalStatus.failure,
                    TerminalReason.runtime_error,
                    latest,
                    human_attention=True,
                    follow_on=False,
                    error_reference=type(started_value).__name__,
                )
                raise InvocationRejected(
                    f"runtime start failed: {type(started_value).__name__}"
                ) from started_value

            handle = started_value
            watchdog.attach(handle)
            initial = _identity_snapshot(handle)
            publish(initial)
            self.store.record_runtime_identity(
                invocation.invocation_id,
                runtime_name=getattr(handle, "runtime_name", None),
                runtime_version=getattr(handle, "runtime_version", None),
                snapshot=initial,
            )

            if watchdog.expired.is_set():
                return self._finish_timeout(
                    invocation.invocation_id,
                    latest,
                    watchdog,
                    start_control,
                )

            def observe() -> None:
                try:
                    outcomes.put(self.runtime.observe(handle, publish))
                except BaseException as exc:
                    outcomes.put(exc)

            threading.Thread(
                target=observe,
                name=f"sdf-observe-{invocation.invocation_id}",
                daemon=True,
            ).start()
            observed = outcomes.get()
            watchdog.expire_if_due()

            if watchdog.expired.is_set():
                with latest_lock:
                    return self._finish_timeout(
                        invocation.invocation_id,
                        latest,
                        watchdog,
                        start_control,
                    )

            if isinstance(observed, BaseException):
                with latest_lock:
                    snapshot = latest
                return self._finish(
                    invocation.invocation_id,
                    TerminalStatus.failure,
                    TerminalReason.runtime_error,
                    snapshot,
                    human_attention=True,
                    follow_on=False,
                    error_reference=type(observed).__name__,
                )

            publish(observed.snapshot)
            attention = observed.terminal_status not in {TerminalStatus.success}
            return self._finish(
                invocation.invocation_id,
                observed.terminal_status,
                observed.terminal_reason,
                observed.snapshot,
                human_attention=attention,
                follow_on=False,
            )
        except InvocationRejected:
            raise
        except Exception as exc:
            with latest_lock:
                snapshot = latest
            self._finish(
                invocation.invocation_id,
                TerminalStatus.failure,
                TerminalReason.runtime_error,
                snapshot,
                human_attention=True,
                follow_on=False,
                error_reference=type(exc).__name__,
            )
            raise InvocationRejected(f"runtime start failed: {type(exc).__name__}") from exc
        finally:
            watchdog.cancel()
            if handle is not None:
                close = getattr(handle, "close", None)
                if callable(close):
                    close()

    def _finish_timeout(
        self,
        invocation_id: str,
        snapshot: RuntimeSnapshot,
        watchdog: _Watchdog,
        start_control: RuntimeStartControl,
        *,
        error_reference: str | None = None,
    ) -> InvocationOutcome:
        metadata = dict(snapshot.runtime_native_metadata or {})
        if watchdog.interrupt_error:
            metadata["watchdog_interrupt_error"] = watchdog.interrupt_error
        if start_control.abort_error:
            metadata["runtime_start_abort_error"] = start_control.abort_error
        timed_out = RuntimeSnapshot(
            usage=snapshot.usage,
            cumulative_usage=snapshot.cumulative_usage,
            runtime_session_id=snapshot.runtime_session_id,
            runtime_invocation_id=snapshot.runtime_invocation_id,
            observed_model=snapshot.observed_model,
            runtime_native_metadata=metadata or None,
            tool_item_count=snapshot.tool_item_count,
        )
        return self._finish(
            invocation_id,
            TerminalStatus.timeout,
            TerminalReason.watchdog_timeout,
            timed_out,
            human_attention=True,
            follow_on=False,
            error_reference=error_reference,
        )

    def _finish(
        self,
        invocation_id: str,
        status: TerminalStatus,
        reason: TerminalReason | None,
        snapshot: RuntimeSnapshot,
        *,
        human_attention: bool,
        follow_on: bool,
        error_reference: str | None = None,
    ) -> InvocationOutcome:
        self.store.record_terminal(
            invocation_id,
            status=status,
            reason=reason,
            snapshot=snapshot,
            human_attention_required=human_attention,
            autonomous_follow_on_allowed=follow_on,
            error_reference=error_reference,
        )
        return InvocationOutcome(
            invocation_id,
            status,
            reason,
            snapshot.usage,
            human_attention,
            follow_on,
            snapshot.runtime_session_id,
            snapshot.runtime_invocation_id,
            snapshot.observed_model,
            snapshot.tool_item_count,
        )

    @staticmethod
    def _capability_for(invocation: ControlledAIInvocation) -> CapabilityProfile:
        if invocation.invocation_purpose in {
            InvocationPurpose.implementation,
            InvocationPurpose.continuation,
        }:
            raise InvocationRejected(
                "DEV-007 does not activate implementation-attempt or continuation capacity"
            )
        return CapabilityProfile.read_only()


def _identity_snapshot(handle: object) -> RuntimeSnapshot:
    return RuntimeSnapshot(
        usage=UsageEvidence.unknown(),
        runtime_session_id=_optional_string(handle, "runtime_session_id"),
        runtime_invocation_id=_optional_string(handle, "runtime_invocation_id"),
    )


def _optional_string(value: object, name: str) -> str | None:
    candidate = getattr(value, name, None)
    return candidate if isinstance(candidate, str) and candidate else None
