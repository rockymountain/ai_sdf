"""Small provider-neutral runtime port used by the controlled gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .model import ControlledAIInvocation, TerminalReason, TerminalStatus, UsageEvidence


@dataclass(frozen=True, slots=True)
class CapabilityProfile:
    name: str
    repository_mutation: bool

    @classmethod
    def read_only(cls) -> "CapabilityProfile":
        return cls("read_only", False)


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


class AIRuntimePort(Protocol):
    """The complete DEV-007 provider-neutral runtime boundary."""

    adapter_name: str
    adapter_version: str

    def start(
        self,
        invocation: ControlledAIInvocation,
        input_text: str,
        capability: CapabilityProfile,
    ) -> object: ...

    def observe(self, handle: object, publish: EvidenceObserver) -> RuntimeResult: ...

    def interrupt(self, handle: object) -> None: ...
