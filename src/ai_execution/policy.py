"""Fail-closed reader for canonical autonomous execution policy."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode) -> dict:
    loader.flatten_mapping(node)
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise ValueError(f"duplicate policy key {key!r}")
        result[key] = loader.construct_object(value_node)
    return result


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


@dataclass(frozen=True, slots=True)
class WatchdogPolicy:
    max_invocation_seconds: int


def load_watchdog_policy(repo: Path) -> WatchdogPolicy:
    """Read the one canonical value; absence or malformed governance is fatal."""
    repo = Path(repo)
    try:
        document = yaml.load(
            (repo / "constitution/policies.yaml").read_text(encoding="utf-8"),
            Loader=_UniqueKeyLoader,
        )
        if not isinstance(document, dict) or document.get("version") != 1:
            raise ValueError("constitution/policies.yaml requires supported version 1")
        policy = document["autonomous_execution"]
        schema = json.loads(
            (repo / "knowledge/schemas/autonomous-execution-policy.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator.check_schema(schema)
        errors = sorted(Draft202012Validator(schema).iter_errors(policy), key=lambda error: list(error.path))
        if errors:
            raise ValueError("; ".join(error.message for error in errors))
        return WatchdogPolicy(policy["max_invocation_seconds"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"canonical watchdog policy unavailable: {exc}") from exc
