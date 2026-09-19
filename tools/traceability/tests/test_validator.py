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
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "__pycache__"))
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
        task = (repo / "design/tasks/DEV-001.md").read_text().replace("DEV-001", "DEV-002")
        (repo / "design/tasks/DEV-002.md").write_text(task)
        result, _, _ = self.run_static(repo)
        self.assertTrue(any("orphan task artifact DEV-002" in e for e in result.errors), result.errors)

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
