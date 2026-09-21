"""Small provider-neutral runtime port used by the controlled gateway."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Protocol

from .model import ControlledAIInvocation, TerminalReason, TerminalStatus, UsageEvidence


@dataclass(frozen=True, slots=True)
class CapabilityProfile:
    name: str
    repository_mutation: bool

    @classmethod
    def read_only(cls) -> "CapabilityProfile":
        return cls("read_only", False)

    @classmethod
    def implementation(cls) -> "CapabilityProfile":
        return cls("implementation", True)


class StartDisposition(StrEnum):
    accepted = "accepted"
    not_started = "not_started"
    uncertain = "uncertain"


@dataclass(frozen=True, slots=True)
class StartEvidence:
    disposition: StartDisposition
    reference: str

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, StartDisposition):
            raise ValueError("start disposition must be provider-neutral")
        if not isinstance(self.reference, str) or not self.reference.strip():
            raise ValueError("start evidence reference is required")


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    usage: UsageEvidence
    cumulative_usage: UsageEvidence | None = None
    runtime_session_id: str | None = None
    runtime_invocation_id: str | None = None
    observed_model: str | None = None
    runtime_native_metadata: dict[str, Any] | None = None
    tool_item_count: int = 0


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    terminal_status: TerminalStatus
    terminal_reason: TerminalReason | None
    snapshot: RuntimeSnapshot


EvidenceObserver = Callable[[RuntimeSnapshot], None]


class RuntimeStartCancelled(RuntimeError):
    """The watchdog revoked runtime-start authorization before a handle was returned."""


class RuntimeStartControl:
    """Per-invocation cooperative abort control for spend-capable start work."""

    def __init__(self, evidence_observer: Callable[[StartEvidence], None] | None = None) -> None:
        self._cancelled = threading.Event()
        self._abort_completed = threading.Event()
        self._lock = threading.Lock()
        self._abort: Callable[[], None] | None = None
        self._abort_started = False
        self.abort_error: str | None = None
        self._evidence_observer = evidence_observer

    def report_start(self, evidence: StartEvidence) -> None:
        """Report affirmative acceptance/non-start, or explicit uncertainty.

        Adapters report acceptance immediately after the runtime accepts work,
        including when returning a handle or subsequent observation later fails.
        Returning a handle or raising an arbitrary exception alone proves neither.
        """
        if not isinstance(evidence, StartEvidence):
            raise TypeError("StartEvidence required")
        if self._evidence_observer is not None:
            self._evidence_observer(evidence)

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def register_abort(self, abort: Callable[[], None]) -> None:
        """Register the adapter stop operation before spend-capable start work."""
        if not callable(abort):
            raise TypeError("runtime-start abort must be callable")
        with self._lock:
            if self._abort is not None:
                raise RuntimeError("runtime-start abort is already registered")
            self._abort = abort
            run_abort = self._claim_abort_locked()
        if run_abort:
            self._run_abort(abort)

    def cancel(self) -> None:
        """Revoke start authorization and synchronously run an available abort."""
        self._cancelled.set()
        with self._lock:
            abort = self._abort
            run_abort = self._claim_abort_locked()
            wait_for_abort = self._abort_started and not run_abort
        if run_abort:
            assert abort is not None
            self._run_abort(abort)
        elif wait_for_abort and abort is not None:
            self._abort_completed.wait()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise RuntimeStartCancelled("runtime start authorization expired")

    def _claim_abort_locked(self) -> bool:
        if self._cancelled.is_set() and self._abort is not None and not self._abort_started:
            self._abort_started = True
            return True
        return False

    def _run_abort(self, abort: Callable[[], None]) -> None:
        try:
            abort()
        except BaseException as exc:
            self.abort_error = type(exc).__name__
        finally:
            self._abort_completed.set()


class AIRuntimePort(Protocol):
    """The complete DEV-007 provider-neutral runtime boundary."""

    adapter_name: str
    adapter_version: str

    def start(
        self,
        invocation: ControlledAIInvocation,
        input_text: str,
        capability: CapabilityProfile,
        start_control: RuntimeStartControl,
    ) -> object: ...

    def observe(self, handle: object, publish: EvidenceObserver) -> RuntimeResult: ...

    def interrupt(self, handle: object) -> None: ...
