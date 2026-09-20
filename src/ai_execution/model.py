"""SDF-owned controlled invocation and evidence types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class InvocationPurpose(StrEnum):
    implementation = "implementation"
    continuation = "continuation"
    acceptance_validation = "acceptance_validation"
    review = "review"
    orchestration = "orchestration"


class ModelSelectionStrategy(StrEnum):
    fixed = "fixed"
    manual = "manual"
    risk_routed = "risk_routed"
    other = "other"


class ContextStrategy(StrEnum):
    chat_heavy = "chat-heavy"
    manual_context_pack = "manual-context-pack"
    graphify_context_pack = "graphify-context-pack"
    other = "other"


class UsageStatus(StrEnum):
    exact = "exact"
    unknown = "unknown"


class TerminalStatus(StrEnum):
    success = "success"
    failure = "failure"
    interrupted = "interrupted"
    timeout = "timeout"
    cancelled = "cancelled"
    unknown = "unknown"


class TerminalReason(StrEnum):
    usage_limit = "usage_limit"
    watchdog_timeout = "watchdog_timeout"
    runtime_error = "runtime_error"
    user_cancelled = "user_cancelled"
    other = "other"
    unknown = "unknown"


@dataclass(frozen=True, slots=True)
class ControlledAIInvocation:
    dev_task: str
    traceability_level: str
    execution_scope_id: str
    run_id: str
    invocation_id: str
    source_revision: str
    invocation_purpose: InvocationPurpose
    model_selection_strategy: ModelSelectionStrategy
    context_strategy: ContextStrategy
    requested_model: str | None = None
    requested_reasoning_effort: str | None = None
    routing_policy_version: str | None = None

    def __post_init__(self) -> None:
        mandatory = {
            "dev_task": self.dev_task,
            "traceability_level": self.traceability_level,
            "execution_scope_id": self.execution_scope_id,
            "run_id": self.run_id,
            "invocation_id": self.invocation_id,
            "source_revision": self.source_revision,
        }
        missing = [name for name, value in mandatory.items() if not isinstance(value, str) or not value.strip()]
        if missing:
            raise ValueError(f"missing mandatory invocation identity: {', '.join(missing)}")
        if self.traceability_level not in {"T0", "T1", "T2"}:
            raise ValueError("traceability_level must be T0, T1, or T2")
        if not self.dev_task.startswith("DEV-"):
            raise ValueError("dev_task must identify a DEV artifact")
        if self.model_selection_strategy is ModelSelectionStrategy.risk_routed and not self.routing_policy_version:
            raise ValueError("risk_routed selection requires routing_policy_version")


@dataclass(frozen=True, slots=True)
class UsageEvidence:
    usage_status: UsageStatus
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_output_tokens: int | None = None

    def __post_init__(self) -> None:
        core = (self.input_tokens, self.output_tokens, self.total_tokens)
        all_values = core + (self.cached_input_tokens, self.reasoning_output_tokens)
        if self.usage_status is UsageStatus.exact:
            if any(type(value) is not int or value < 0 for value in core):
                raise ValueError("exact usage requires non-negative integer core token values")
            if any(value is not None and (type(value) is not int or value < 0) for value in all_values[3:]):
                raise ValueError("optional token breakdowns must be non-negative integers when present")
        elif any(value is not None for value in all_values):
            raise ValueError("unknown usage must not invent token values")

    @classmethod
    def unknown(cls) -> "UsageEvidence":
        return cls(UsageStatus.unknown)

    @classmethod
    def exact(
        cls,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        *,
        cached_input_tokens: int | None = None,
        reasoning_output_tokens: int | None = None,
    ) -> "UsageEvidence":
        return cls(
            UsageStatus.exact,
            input_tokens,
            output_tokens,
            total_tokens,
            cached_input_tokens,
            reasoning_output_tokens,
        )


def evidence_metadata(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return JSON-compatible runtime metadata without accepting arbitrary objects."""
    if value is None:
        return None
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError("runtime_native_metadata must be a string-keyed mapping")
    return value
