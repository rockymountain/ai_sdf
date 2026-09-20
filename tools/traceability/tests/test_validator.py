from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
import sys
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("validator", ROOT / "tools/traceability/validate.py")
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules["validator"] = validator
SPEC.loader.exec_module(validator)


def copy_repo() -> tuple[tempfile.TemporaryDirectory, Path]:
    td = tempfile.TemporaryDirectory()
    dst = Path(td.name) / "repo"
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv"))
    return td, dst


class ValidatorTests(unittest.TestCase):
    def run_static(self, repo: Path):
        result = validator.ValidationErrorSet()
        registry = validator.scan_artifacts(repo, result)
        trace = validator.validate_traceability(repo, registry, result)
        return result, registry, trace

    def test_happy_path(self):
        td, repo = copy_repo()
        self.addCleanup(td.cleanup)
        result, registry, _ = self.run_static(repo)
        self.assertFalse(result.errors, result.errors)
        self.assertIn("ADR-001", registry)
        self.assertEqual("decision", registry["ADR-001"].kind)

    def test_autonomous_execution_policy_requires_positive_integer(self):
        for value in (None, 0, -1, "600", True):
            with self.subTest(value=value):
                td, repo = copy_repo(); self.addCleanup(td.cleanup)
                path = repo / "constitution/policies.yaml"
                data = yaml.safe_load(path.read_text())
                if value is None:
                    data.pop("autonomous_execution", None)
                else:
                    data["autonomous_execution"] = {"max_invocation_seconds": value}
                path.write_text(yaml.safe_dump(data, sort_keys=False))
                result, _, _ = self.run_static(repo)
                self.assertTrue(
                    any("autonomous_execution" in error for error in result.errors),
                    result.errors,
                )

    def test_frontmatter_is_identity_not_filename(self):
        td, repo = copy_repo(); self.addCleanup(td.cleanup)
        original = repo / "design/decisions/ADR-001.md"
        original.rename(repo / "design/decisions/adr-wrong-filename.md")
        result, registry, _ = self.run_static(repo)
        self.assertFalse(result.errors, result.errors)
        self.assertIn("ADR-001", registry)

    def test_missing_reference_fails(self):
        td, repo = copy_repo(); self.addCleanup(td.cleanup)
        path = repo / "knowledge/traceability.yaml"
        data = yaml.safe_load(path.read_text())
        data["tasks"]["DEV-001"]["decisions"] = ["ADR-999"]
        path.write_text(yaml.safe_dump(data, sort_keys=False))
        result, _, _ = self.run_static(repo)
        self.assertTrue(any("ADR-999" in e and "does not exist" in e for e in result.errors), result.errors)

    def test_duplicate_frontmatter_id_fails(self):
        td, repo = copy_repo(); self.addCleanup(td.cleanup)
        shutil.copy(repo / "design/decisions/ADR-001.md", repo / "design/decisions/copy.md")
        result, _, _ = self.run_static(repo)
        self.assertTrue(any("duplicate artifact id ADR-001" in e for e in result.errors), result.errors)

    def test_t2_missing_decision_or_contract_fails(self):
        td, repo = copy_repo(); self.addCleanup(td.cleanup)
        path = repo / "knowledge/traceability.yaml"
        data = yaml.safe_load(path.read_text())
        data["tasks"]["DEV-001"]["decisions"] = []
        data["tasks"]["DEV-001"]["contracts"] = []
        path.write_text(yaml.safe_dump(data, sort_keys=False))
        result, _, _ = self.run_static(repo)
        self.assertTrue(any("requires at least one decision or contract" in e for e in result.errors), result.errors)

    def test_orphan_task_artifact_fails(self):
        td, repo = copy_repo(); self.addCleanup(td.cleanup)
        path = repo / "knowledge/traceability.yaml"
        trace = yaml.safe_load(path.read_text())
        del trace["tasks"]["DEV-002"]
        path.write_text(yaml.safe_dump(trace, sort_keys=False))
        result, _, _ = self.run_static(repo)
        self.assertTrue(any("orphan task artifact DEV-002" in e for e in result.errors), result.errors)

    def check_path_evidence(self, paths, level="T2", status="active"):
        td, repo = copy_repo(); self.addCleanup(td.cleanup)
        # External files must not qualify even when a literal or glob finds them.
        (repo.parent / "outside.py").write_text("# outside repository\n")
        trace_path = repo / "knowledge/traceability.yaml"
        trace = yaml.safe_load(trace_path.read_text())
        trace["tasks"]["DEV-002"]["level"] = level
        trace["tasks"]["DEV-002"]["implementation"]["paths"] = paths
        trace_path.write_text(yaml.safe_dump(trace, sort_keys=False))
        task_path = repo / "design/tasks/DEV-002.md"
        metadata = validator.extract_frontmatter(task_path)
        metadata.update(traceability_level=level, status=status)
        task_path.write_text("---\n" + yaml.safe_dump(metadata) + "---\n")
        result, _, _ = self.run_static(repo)
        return result.errors

    def test_existing_literal_implementation_file_passes(self):
        for level in ("T1", "T2"):
            with self.subTest(level=level):
                self.assertEqual([], self.check_path_evidence(["src/document_indexing.py"], level))

    def test_missing_literal_implementation_file_fails(self):
        for level in ("T1", "T2"):
            with self.subTest(level=level):
                errors = self.check_path_evidence(["src/nonexistent.py"], level)
                self.assertTrue(any("DEV-002.implementation.paths" in e and "src/nonexistent.py" in e for e in errors), errors)

    def test_matching_implementation_globs_pass(self):
        for level in ("T1", "T2"):
            for pattern in ("src/*.py", "tools/traceability/tests/test_*.py", "tools/**/test_*.py"):
                with self.subTest(level=level, pattern=pattern):
                    self.assertEqual([], self.check_path_evidence([pattern], level))

    def test_unmatched_implementation_glob_fails(self):
        for level in ("T1", "T2"):
            with self.subTest(level=level):
                errors = self.check_path_evidence(["src/nonexistent_*.py"], level)
                self.assertTrue(any("DEV-002.implementation.paths" in e and "src/nonexistent_*.py" in e for e in errors), errors)

    def test_each_implementation_entry_must_resolve(self):
        errors = self.check_path_evidence(["src/document_indexing.py", "src/nonexistent_*.py"])
        self.assertTrue(any("src/nonexistent_*.py" in e for e in errors), errors)

    def test_directories_and_external_files_are_not_implementation_files(self):
        for pattern in ("src", "tools/trace*", "../outside.py", "../outside*.py"):
            with self.subTest(pattern=pattern):
                errors = self.check_path_evidence([pattern])
                self.assertTrue(any("DEV-002.implementation.paths" in e and pattern in e for e in errors), errors)

    def test_current_statuses_require_resolved_globs(self):
        for status in ("draft", "proposed", "accepted", "active", "implemented", "verified"):
            with self.subTest(status=status):
                errors = self.check_path_evidence(["src/nonexistent_*.py"], status=status)
                self.assertTrue(any("DEV-002.implementation.paths" in e for e in errors), errors)

    def test_t0_and_historical_tasks_retain_existing_path_checks(self):
        for level, status in (("T0", "active"), ("T2", "deprecated"), ("T2", "superseded"), ("T2", "retired")):
            with self.subTest(level=level, status=status):
                self.assertEqual([], self.check_path_evidence(["src/nonexistent_*.py"], level, status))
                errors = self.check_path_evidence(["src/nonexistent.py"], level, status)
                self.assertTrue(any("does not exist" in e for e in errors), errors)

    def test_t1_attestation_must_be_complete(self):
        body = "Traceability Task: DEV-002\nTraceability Level: T1\n- [x] I confirm this change does **NOT** affect architecture boundaries or dependencies."
        self.assertFalse(validator.has_risk_attestation(body, "T1"))

    def test_t2_attestation(self):
        body = "- [x] I acknowledge this is a material design change and have linked the required design + decision/contract + verification evidence."
        self.assertTrue(validator.has_risk_attestation(body, "T2"))


    def init_git(self, repo: Path):
        def run(*args):
            subprocess.run(["git", *args], cwd=repo, check=True, text=True, capture_output=True)
        run("init", "-b", "main")
        run("config", "user.email", "phase0@example.test")
        run("config", "user.name", "Phase0 Test")
        run("add", ".")
        run("commit", "-m", "baseline")
        base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        return run, base

    @staticmethod
    def t2_body():
        return """Traceability Task: DEV-001
Traceability Level: T2
- [x] I acknowledge this is a material design change and have linked the required design + decision/contract + verification evidence.
"""

    def test_git_evidence_passes_with_marker_and_declared_path(self):
        td, repo = copy_repo(); self.addCleanup(td.cleanup)
        run, base = self.init_git(repo)
        target = repo / "src/document_indexing.py"
        target.write_text(target.read_text() + "\n# implementation delta\n")
        run("add", "src/document_indexing.py")
        run("commit", "-m", "[DEV-001] refine async indexing")
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        static_result, _, trace = self.run_static(repo)
        self.assertFalse(static_result.errors, static_result.errors)
        result = validator.ValidationErrorSet()
        validator.validate_change_evidence(repo, trace, self.t2_body(), base, head, result)
        self.assertFalse(result.errors, result.errors)

    def test_git_evidence_fails_without_commit_marker(self):
        td, repo = copy_repo(); self.addCleanup(td.cleanup)
        run, base = self.init_git(repo)
        target = repo / "src/document_indexing.py"
        target.write_text(target.read_text() + "\n# implementation delta\n")
        run("add", "src/document_indexing.py")
        run("commit", "-m", "refine async indexing")
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        result = validator.ValidationErrorSet()
        trace = yaml.safe_load((repo / "knowledge/traceability.yaml").read_text())
        validator.validate_change_evidence(repo, trace, self.t2_body(), base, head, result)
        self.assertTrue(any("required marker [DEV-001]" in e for e in result.errors), result.errors)

    def test_t1_change_touching_architecture_path_forces_t2(self):
        td, repo = copy_repo(); self.addCleanup(td.cleanup)
        # Add a valid T1 task and trace node.
        task = (repo / "design/tasks/DEV-001.md").read_text()
        task = task.replace("DEV-001", "DEV-002").replace("T2", "T1")
        (repo / "design/tasks/DEV-002.md").write_text(task)
        trace_path = repo / "knowledge/traceability.yaml"
        trace = yaml.safe_load(trace_path.read_text())
        trace["tasks"]["DEV-002"] = {
            "level": "T1",
            "intent": ["FR-001"],
            "implementation": {"paths": ["design/architecture/CMP-001.md"]},
            "verification": ["TEST-001"],
        }
        trace_path.write_text(yaml.safe_dump(trace, sort_keys=False))
        run, base = self.init_git(repo)
        target = repo / "design/architecture/CMP-001.md"
        target.write_text(target.read_text() + "\narchitecture delta\n")
        run("add", "design/architecture/CMP-001.md")
        run("commit", "-m", "[DEV-002] architecture-like delta")
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        body = """Traceability Task: DEV-002
Traceability Level: T1
- [x] I confirm this change does **NOT** affect architecture boundaries or dependencies.
- [x] I confirm this change does **NOT** affect NFRs or reliability assumptions.
- [x] I confirm this change does **NOT** affect security or authorization boundaries.
- [x] I confirm this change does **NOT** affect persistent data models or migrations.
- [x] I confirm this change does **NOT** affect public/external API or event contracts.
- [x] I confirm this change does **NOT** create a compliance or irreversible migration concern.
"""
        result = validator.ValidationErrorSet()
        validator.validate_change_evidence(repo, trace, body, base, head, result)
        self.assertTrue(any("hit T2 path triggers" in e for e in result.errors), result.errors)

    def test_git_evidence_fails_when_diff_avoids_declared_paths(self):
        td, repo = copy_repo(); self.addCleanup(td.cleanup)
        run, base = self.init_git(repo)
        target = repo / "README.md"
        target.write_text(target.read_text() + "\nunrelated delta\n")
        run("add", "README.md")
        run("commit", "-m", "[DEV-001] misleading marker")
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        result = validator.ValidationErrorSet()
        trace = yaml.safe_load((repo / "knowledge/traceability.yaml").read_text())
        validator.validate_change_evidence(repo, trace, self.t2_body(), base, head, result)
        self.assertTrue(any("does not touch any declared implementation path" in e for e in result.errors), result.errors)


if __name__ == "__main__":
    unittest.main()
