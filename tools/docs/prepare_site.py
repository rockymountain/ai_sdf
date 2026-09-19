from __future__ import annotations

import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_SOURCE = REPO_ROOT / ".site-src"

CANONICAL_TREES = (
    ("docs", REPO_ROOT / "docs"),
    ("design", REPO_ROOT / "design"),
)


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise SystemExit(f"ERROR: required source directory missing: {source}")

    shutil.copytree(source, destination)


def write_root_index() -> None:
    content = """\
# AI-Native Software Design Factory

Canonical engineering documentation published from the SDF repository.

## Start Here

- [Documentation Home](docs/index.md)
- [Reference Architecture](docs/reference/ai-native-sdf-reference-architecture.md)
- [Roadmap](docs/reference/ai-native-sdf-roadmap.md)
- [Phase 0 Decision Index](docs/phase0-decision-index.md)
- [Phase 0 Evolution Log](docs/phase0-evolution-log.md)
- [Phase 0 AI Cost Baseline](docs/phase0-ai-cost-baseline.md)
- [Phase 0 Exit Report](docs/phase0-exit-report.md)

## Engineering Design

- [Problems](design/problems/)
- [Requirements](design/requirements/)
- [Architecture](design/architecture/)
- [Decisions](design/decisions/)
- [Contracts](design/contracts/)
- [Development Tasks](design/tasks/)
- [Verification](design/verification/)
"""

    (SITE_SOURCE / "index.md").write_text(content, encoding="utf-8")


def main() -> None:
    if SITE_SOURCE.exists():
        shutil.rmtree(SITE_SOURCE)

    SITE_SOURCE.mkdir(parents=True)

    for target_name, source in CANONICAL_TREES:
        copy_tree(source, SITE_SOURCE / target_name)

    write_root_index()

    print("PASS: documentation publication tree prepared")
    print(f"      source: {SITE_SOURCE}")


if __name__ == "__main__":
    main()