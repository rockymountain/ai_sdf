"""Verify the repository's Python/venv/dependency contract using standard Python."""
import argparse
import importlib
from importlib import metadata
from pathlib import Path
import platform
import re
import sys

IMPORTS = {
    "pyyaml": "yaml", "jsonschema": "jsonschema", "attrs": "attrs",
    "jsonschema-specifications": "jsonschema_specifications",
    "referencing": "referencing", "rpds-py": "rpds",
    "openai-codex": "openai_codex", "openai-codex-cli-bin": "codex_cli_bin",
    "pydantic": "pydantic", "pydantic-core": "pydantic_core",
    "packaging": "packaging", "annotated-types": "annotated_types",
    "typing-extensions": "typing_extensions", "typing-inspection": "typing_inspection",
}


def read_contract(repo: Path) -> tuple[str, dict[str, str]]:
    version = (repo / ".python-version").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(".python-version must declare one exact major.minor.patch version")
    pins = {}
    for line in (repo / "requirements-dev.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9_.-]*)==([0-9]+(?:\.[0-9]+)+)", line)
        if not match:
            raise ValueError(f"validation dependency must be exactly pinned: {line}")
        name = re.sub(r"[-_.]+", "-", match[1]).lower()
        if name in pins:
            raise ValueError(f"duplicate dependency declaration: {name}")
        pins[name] = match[2]
    if missing := IMPORTS.keys() - pins.keys():
        raise ValueError(f"missing validation dependency pins: {sorted(missing)}")
    return version, pins


def check(repo: Path, python_only: bool = False) -> list[str]:
    try:
        version, pins = read_contract(repo)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    errors = []
    if platform.python_version() != version:
        errors.append(f"Python {platform.python_version()} != declared {version}")
    if python_only:
        return errors
    prefix = Path(sys.prefix).resolve()
    if sys.prefix == sys.base_prefix:
        return errors + ["an isolated virtual environment is required"]
    try:
        config = dict(line.split("=", 1) for line in (prefix / "pyvenv.cfg").read_text().splitlines() if "=" in line)
        config = {key.strip(): value.strip() for key, value in config.items()}
        if config.get("include-system-site-packages", "").lower() != "false":
            errors.append("venv must exclude system site-packages")
        for name, expected in pins.items():
            if (actual := metadata.version(name)) != expected:
                errors.append(f"{name} {actual} != declared {expected}")
            if not Path(metadata.distribution(name).locate_file("")).resolve().is_relative_to(prefix):
                errors.append(f"{name} is installed outside the venv")
        for name, module in IMPORTS.items():
            if not Path(importlib.import_module(module).__file__).resolve().is_relative_to(prefix):
                errors.append(f"{name} imports from outside the venv")
    except (OSError, ImportError, metadata.PackageNotFoundError) as exc:
        errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--python-only", action="store_true", help="check interpreter before creating the venv")
    args = parser.parse_args()
    errors = check(args.repo, args.python_only)
    if errors:
        for error in errors:
            print(f"ERROR: environment: {error}", file=sys.stderr)
        return 1
    version, pins = read_contract(args.repo)
    print(f"PASS: declared Python {version}" + ("" if args.python_only else "; isolated validation environment"))
    if not args.python_only:
        for name, version in sorted(pins.items()):
            print(f"{name}=={version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
