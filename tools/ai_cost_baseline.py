#!/usr/bin/env python3
"""Export one deterministic M3 cost-baseline report from governed evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_execution.cost_baseline import (  # noqa: E402
    BaselineEvidenceError,
    MeasurementWindow,
    build_report,
    canonical_json,
    load_trace_levels,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--window", type=Path, required=True)
    parser.add_argument("--traceability", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        with args.window.open(encoding="utf-8") as stream:
            window = MeasurementWindow.from_mapping(json.load(stream))
        trace_levels = load_trace_levels(args.traceability, window.included_dev_tasks)
        sys.stdout.write(canonical_json(build_report(args.database, window, trace_levels)))
    except (BaselineEvidenceError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
