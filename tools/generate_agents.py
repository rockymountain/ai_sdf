#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import yaml


def render(repo: Path) -> str:
    cfg = yaml.safe_load((repo / "constitution/agent-runtime.yaml").read_text(encoding="utf-8"))
    principles = yaml.safe_load((repo / "constitution/principles.yaml").read_text(encoding="utf-8"))
    p = cfg["runtime_projection"]
    lines = [
        f"# {p['title']}",
        "",
        f"> {p['preamble']}",
        "",
        "## Canonical principles",
        "",
    ]
    for item in principles["principles"]:
        lines.append(f"- **{item['id']}** — {item['statement']}")
    lines += ["", "## Runtime invariants", ""]
    for i, item in enumerate(p["invariants"], 1):
        lines.append(f"{i}. {item}")
    lines += ["", "## Before proposing a change", "", "Read:"]
    for path in p["before_change_read"]:
        lines.append(f"- `{path}`")
    lines += ["", "Run:", "", "```bash", p["validation_command"], "```", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    target = repo / "AGENTS.md"
    expected = render(repo)
    if args.check:
        actual = target.read_text(encoding="utf-8") if target.exists() else ""
        if actual != expected:
            print("ERROR: AGENTS.md is stale; run: python tools/generate_agents.py --repo .", file=sys.stderr)
            return 1
        print("PASS: AGENTS.md is reproducible from canonical governance")
        return 0
    target.write_text(expected, encoding="utf-8")
    print(f"WROTE: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
