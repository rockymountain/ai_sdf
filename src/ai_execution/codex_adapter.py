"""Bootstrap Codex SDK adapter; no SDK type escapes this module."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import version
from typing import Any, Callable

from openai_codex import ApprovalMode, Codex, Sandbox

from .model import ControlledAIInvocation, TerminalReason, TerminalStatus, UsageEvidence
from .runtime import (
    CapabilityProfile,
    EvidenceObserver,
    RuntimeResult,
    RuntimeSnapshot,
    RuntimeStartControl,
)


@dataclass(slots=True)
class _CodexHandle:
    client: Any
    turn: Any
    runtime_session_id: str | None
    runtime_invocation_id: str | None
    runtime_name: str = "codex"
    runtime_version: str | None = None

    def close(self) -> None:
        self.client.close()


class CodexRuntimeAdapter:
    """Map the stable public Codex Python SDK to AIRuntimePort semantics."""

    adapter_name = "CodexRuntimeAdapter"
    adapter_version = version("openai-codex")

    def __init__(self, *, repo: str, codex_factory: Callable[[], Any] = Codex):
        self.repo = repo
        self._codex_factory = codex_factory

    def start(
        self,
        invocation: ControlledAIInvocation,
        input_text: str,
        capability: CapabilityProfile,
        start_control: RuntimeStartControl,
    ) -> object:
        if capability.repository_mutation or capability.name != "read_only":
            raise ValueError("Codex DEV-007 invocations require the read-only capability profile")
        client = self._codex_factory()
        try:
            # Codex.close() terminates the pinned SDK's app-server process and
            # wakes pending request/stream waiters. Register it before any
            # thread/turn operation that can cross the invocation deadline.
            start_control.register_abort(client.close)
            start_control.raise_if_cancelled()
            runtime_version = _runtime_version(client)
            thread = client.thread_start(
                approval_mode=ApprovalMode.deny_all,
                cwd=self.repo,
                model=invocation.requested_model,
                sandbox=Sandbox.read_only,
            )
            start_control.raise_if_cancelled()
            options: dict[str, Any] = {"sandbox": Sandbox.read_only}
            if invocation.requested_model is not None:
                options["model"] = invocation.requested_model
            if invocation.requested_reasoning_effort is not None:
                options["effort"] = invocation.requested_reasoning_effort
            turn = thread.turn(input_text, **options)
            start_control.raise_if_cancelled()
            return _CodexHandle(
                client=client,
                turn=turn,
                runtime_session_id=_present_string(getattr(thread, "id", None)),
                runtime_invocation_id=_present_string(getattr(turn, "id", None)),
                runtime_version=runtime_version,
            )
        except Exception:
            client.close()
            raise

    def observe(self, handle: object, publish: EvidenceObserver) -> RuntimeResult:
        if not isinstance(handle, _CodexHandle):
            raise TypeError("CodexRuntimeAdapter received an incompatible handle")
        usage = UsageEvidence.unknown()
        cumulative: UsageEvidence | None = None
        observed_model: str | None = None
        reroutes: list[dict[str, str]] = []
        tool_types: list[str] = []
        terminal_status = TerminalStatus.unknown
        terminal_reason: TerminalReason | None = TerminalReason.unknown

        def snapshot() -> RuntimeSnapshot:
            metadata: dict[str, Any] = {}
            if reroutes:
                metadata["model_reroutes"] = list(reroutes)
            if tool_types:
                metadata["tool_item_types"] = list(tool_types)
            return RuntimeSnapshot(
                usage=usage,
                cumulative_usage=cumulative,
                runtime_session_id=handle.runtime_session_id,
                runtime_invocation_id=handle.runtime_invocation_id,
                observed_model=observed_model,
                runtime_native_metadata=metadata or None,
                tool_item_count=len(tool_types),
            )

        for event in handle.turn.stream():
            payload = getattr(event, "payload", None)
            if event.method == "thread/tokenUsage/updated" and payload is not None:
                token_usage = getattr(payload, "token_usage", None)
                usage, cumulative = _map_thread_usage(token_usage)
                publish(snapshot())
            elif event.method == "model/rerouted" and payload is not None:
                from_model = _present_string(getattr(payload, "from_model", None))
                to_model = _present_string(getattr(payload, "to_model", None))
                reason = getattr(getattr(payload, "reason", None), "value", None)
                if to_model is not None:
                    observed_model = to_model
                reroute = {key: value for key, value in {
                    "from_model": from_model,
                    "to_model": to_model,
                    "reason": _present_string(reason),
                }.items() if value is not None}
                if reroute:
                    reroutes.append(reroute)
                publish(snapshot())
            elif event.method == "item/completed" and payload is not None:
                item = getattr(getattr(payload, "item", None), "root", None)
                item_type = type(item).__name__ if item is not None else ""
                if item_type in {
                    "CommandExecutionThreadItem",
                    "McpToolCallThreadItem",
                    "DynamicToolCallThreadItem",
                }:
                    tool_types.append(item_type)
                    publish(snapshot())
            elif event.method == "turn/completed" and payload is not None:
                turn = getattr(payload, "turn", None)
                terminal_status, terminal_reason = _map_terminal(turn)

        final = snapshot()
        publish(final)
        return RuntimeResult(terminal_status, terminal_reason, final)

    def interrupt(self, handle: object) -> None:
        if not isinstance(handle, _CodexHandle):
            raise TypeError("CodexRuntimeAdapter received an incompatible handle")
        handle.turn.interrupt()


def _map_thread_usage(token_usage: Any) -> tuple[UsageEvidence, UsageEvidence | None]:
    if token_usage is None:
        return UsageEvidence.unknown(), None
    return _map_breakdown(getattr(token_usage, "last", None)), _map_breakdown(
        getattr(token_usage, "total", None)
    )


def _map_breakdown(value: Any) -> UsageEvidence:
    if value is None:
        return UsageEvidence.unknown()
    core = tuple(getattr(value, name, None) for name in ("input_tokens", "output_tokens", "total_tokens"))
    if any(type(item) is not int or item < 0 for item in core):
        return UsageEvidence.unknown()
    return UsageEvidence.exact(
        core[0],
        core[1],
        core[2],
        cached_input_tokens=_optional_nonnegative_int(getattr(value, "cached_input_tokens", None)),
        reasoning_output_tokens=_optional_nonnegative_int(
            getattr(value, "reasoning_output_tokens", None)
        ),
    )


def _map_terminal(turn: Any) -> tuple[TerminalStatus, TerminalReason | None]:
    status = getattr(getattr(turn, "status", None), "value", None)
    if status == "completed":
        return TerminalStatus.success, None
    if status == "failed":
        return TerminalStatus.failure, TerminalReason.runtime_error
    if status == "interrupted":
        error_text = str(getattr(turn, "error", "") or "").lower()
        reason = TerminalReason.usage_limit if "usage" in error_text and "limit" in error_text else TerminalReason.other
        return TerminalStatus.interrupted, reason
    return TerminalStatus.unknown, TerminalReason.unknown


def _runtime_version(client: Any) -> str | None:
    metadata = getattr(client, "metadata", None)
    server_info = getattr(metadata, "serverInfo", None)
    return _present_string(getattr(server_info, "version", None))


def _present_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_nonnegative_int(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None
