"""Claude Code CLI adapter; provider-specific process semantics stay here."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .model import (
    ControlledAIInvocation,
    InvocationPurpose,
    TerminalReason,
    TerminalStatus,
    UsageEvidence,
)
from .runtime import (
    CapabilityProfile,
    EvidenceObserver,
    RuntimeResult,
    RuntimeSnapshot,
    RuntimeStartControl,
    StartDisposition,
    StartEvidence,
)


ProcessFactory = Callable[..., Any]


@dataclass(slots=True)
class _ProcessController:
    process: Any = None
    cancelled: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def attach(self, process: Any) -> None:
        with self._lock:
            self.process = process
            terminate = self.cancelled
        if terminate:
            _terminate_process(process)

    def abort(self) -> None:
        with self._lock:
            self.cancelled = True
            process = self.process
        if process is not None:
            _terminate_process(process)


@dataclass(slots=True)
class _ClaudeHandle:
    process: Any
    start_control: RuntimeStartControl
    runtime_version: str | None
    runtime_session_id: str | None = None
    runtime_invocation_id: str | None = None
    runtime_name: str = "claude"
    interrupted: bool = False
    accepted: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def terminate(self) -> None:
        with self._lock:
            self.interrupted = True
            _terminate_process(self.process)

    def close(self) -> None:
        _terminate_process(self.process)


class ClaudeRuntimeAdapter:
    """Map noninteractive Claude Code stream JSON to ``AIRuntimePort``."""

    adapter_name = "claude"
    adapter_version = "1"

    def __init__(
        self,
        *,
        repo: str,
        executable: str,
        runtime_version: str | None = None,
        process_factory: ProcessFactory = subprocess.Popen,
    ):
        if not isinstance(executable, str) or not executable.strip():
            raise ValueError("Claude executable must be explicit")
        self.repo = str(Path(repo).resolve())
        self.executable = executable
        self.runtime_version = runtime_version
        self._process_factory = process_factory

    def start(
        self,
        invocation: ControlledAIInvocation,
        input_text: str,
        capability: CapabilityProfile,
        start_control: RuntimeStartControl,
    ) -> object:
        controller = _ProcessController()
        start_control.register_abort(controller.abort)
        try:
            permission_mode, tools, strict_mcp = _capability_arguments(invocation, capability)
            command = [
                self.executable,
                "-p",
                input_text,
                "--output-format",
                "stream-json",
                "--verbose",
                "--no-session-persistence",
                "--permission-mode",
                permission_mode,
            ]
            if tools is not None:
                command.extend(("--tools", tools))
            if strict_mcp:
                command.append("--strict-mcp-config")
            if invocation.requested_model is not None:
                command.extend(("--model", invocation.requested_model))
            if invocation.requested_reasoning_effort is not None:
                command.extend(("--effort", invocation.requested_reasoning_effort))
            start_control.raise_if_cancelled()
            process = self._process_factory(
                command,
                cwd=self.repo,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )
            controller.attach(process)
            start_control.raise_if_cancelled()
            return _ClaudeHandle(process, start_control, self.runtime_version)
        except Exception:
            start_control.report_start(StartEvidence(
                (
                    StartDisposition.not_started
                    if controller.process is None
                    else StartDisposition.uncertain
                ),
                (
                    "local failure before a Claude execution process was established"
                    if controller.process is None
                    else "Claude process was established without affirmative accepted-execution evidence"
                ),
            ))
            raise

    def observe(self, handle: object, publish: EvidenceObserver) -> RuntimeResult:
        if not isinstance(handle, _ClaudeHandle):
            raise TypeError("ClaudeRuntimeAdapter received an incompatible handle")
        usage = UsageEvidence.unknown()
        observed_model: str | None = None
        tool_item_count = 0
        event_types: list[str] = []
        result_subtype: str | None = None
        provider_usage_keys: list[str] | None = None
        provider_usage: dict[str, int | float] | None = None
        terminal_status = TerminalStatus.unknown
        terminal_reason: TerminalReason | None = TerminalReason.unknown

        def snapshot(exit_code: int | None = None) -> RuntimeSnapshot:
            metadata: dict[str, Any] = {}
            if event_types:
                metadata["stream_event_types"] = sorted(set(event_types))
            if result_subtype is not None:
                metadata["result_subtype"] = result_subtype
            if provider_usage_keys is not None:
                metadata["provider_usage_keys"] = provider_usage_keys
                metadata["provider_usage"] = provider_usage or {}
            if exit_code is not None:
                metadata["process_exit_code"] = exit_code
            return RuntimeSnapshot(
                usage=usage,
                runtime_session_id=handle.runtime_session_id,
                runtime_invocation_id=handle.runtime_invocation_id,
                observed_model=observed_model,
                runtime_native_metadata=metadata or None,
                tool_item_count=tool_item_count,
            )

        stdout: Iterable[str] = handle.process.stdout or ()
        for line in stdout:
            try:
                event = json.loads(line)
            except (TypeError, json.JSONDecodeError):
                event_types.append("malformed")
                continue
            if not isinstance(event, Mapping):
                event_types.append("malformed")
                continue
            event_type = _present_string(event.get("type")) or "unknown"
            event_types.append(event_type)
            session_id = _present_string(event.get("session_id"))
            if session_id is not None:
                handle.runtime_session_id = session_id
            if event_type == "system":
                observed_model = _present_string(event.get("model")) or observed_model
            elif event_type == "assistant":
                if not handle.accepted:
                    handle.start_control.report_start(StartEvidence(
                        StartDisposition.accepted,
                        "Claude stream emitted an assistant event",
                    ))
                    handle.accepted = True
                message = event.get("message")
                if isinstance(message, Mapping):
                    observed_model = _present_string(message.get("model")) or observed_model
                    content = message.get("content")
                    if isinstance(content, list):
                        tool_item_count += sum(
                            isinstance(item, Mapping) and item.get("type") == "tool_use"
                            for item in content
                        )
            elif event_type == "result":
                result_subtype = _present_string(event.get("subtype"))
                terminal_status, terminal_reason = _terminal_from_result(event)
                if terminal_status is TerminalStatus.success and not handle.accepted:
                    handle.start_control.report_start(StartEvidence(
                        StartDisposition.accepted,
                        "Claude stream emitted a successful terminal result",
                    ))
                    handle.accepted = True
                raw_usage = event.get("usage")
                provider_usage_keys, provider_usage = _provider_usage_metadata(raw_usage)
                usage = _usage_from_mapping(raw_usage)
            publish(snapshot())

        exit_code = handle.process.wait()
        if not handle.accepted:
            handle.start_control.report_start(StartEvidence(
                StartDisposition.uncertain,
                "Claude process ended without affirmative accepted-execution evidence",
            ))
        if handle.interrupted:
            terminal_status = TerminalStatus.interrupted
            terminal_reason = TerminalReason.user_cancelled
        elif result_subtype is None and exit_code != 0:
            terminal_status = TerminalStatus.failure
            terminal_reason = TerminalReason.runtime_error
        final = snapshot(exit_code)
        publish(final)
        return RuntimeResult(terminal_status, terminal_reason, final)

    def interrupt(self, handle: object) -> None:
        if not isinstance(handle, _ClaudeHandle):
            raise TypeError("ClaudeRuntimeAdapter received an incompatible handle")
        handle.terminate()


def _capability_arguments(
    invocation: ControlledAIInvocation,
    capability: CapabilityProfile,
) -> tuple[str, str | None, bool]:
    if capability.repository_mutation:
        valid = capability == CapabilityProfile.implementation() and (
            (
                invocation.invocation_purpose is InvocationPurpose.implementation
                and invocation.reservation_id
                and invocation.candidate_attempt_number
            )
            or (
                invocation.invocation_purpose is InvocationPurpose.continuation
                and invocation.attempt_number
                and invocation.resume_of_invocation_id
                and invocation.human_authorization
            )
        )
        if not valid:
            raise ValueError("implementation capability requires governed attempt identity")
        return "acceptEdits", None, False
    if capability == CapabilityProfile.read_only():
        return "plan", "Read,Glob,Grep", True
    raise ValueError("unsupported capability profile")


def _usage_from_mapping(value: object) -> UsageEvidence:
    if not isinstance(value, Mapping):
        return UsageEvidence.unknown()
    components = tuple(value.get(name) for name in (
        "input_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "output_tokens",
    ))
    if any(type(item) is not int or item < 0 for item in components):
        return UsageEvidence.unknown()
    canonical_input = components[0] + components[1] + components[2]
    canonical_output = components[3]
    return UsageEvidence.exact(
        canonical_input,
        canonical_output,
        canonical_input + canonical_output,
        cached_input_tokens=components[2],
    )


def _provider_usage_metadata(
    value: object,
) -> tuple[list[str] | None, dict[str, int | float] | None]:
    """Retain emitted usage names and numeric values without prompt/response data."""
    if not isinstance(value, Mapping):
        return None, None
    keys = sorted(key for key in value if isinstance(key, str))
    numeric = {
        key: item
        for key, item in value.items()
        if isinstance(key, str) and type(item) in {int, float}
    }
    return keys, numeric


def _terminal_from_result(
    event: Mapping[str, Any],
) -> tuple[TerminalStatus, TerminalReason | None]:
    subtype = _present_string(event.get("subtype"))
    if subtype == "success" or event.get("is_error") is False:
        return TerminalStatus.success, None
    reason = _present_string(event.get("reason")) or _present_string(event.get("error_type"))
    if reason == "usage_limit":
        return TerminalStatus.interrupted, TerminalReason.usage_limit
    if subtype in {"cancelled", "user_cancelled"}:
        return TerminalStatus.cancelled, TerminalReason.user_cancelled
    return TerminalStatus.failure, TerminalReason.runtime_error


def _present_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _terminate_process(process: Any) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)
