import subprocess
import unittest

import yaml

from test_validator import copy_repo, validator


class ChangeProvenanceTests(unittest.TestCase):
    @staticmethod
    def git(repo, *args):
        return subprocess.check_output(["git", *args], cwd=repo, text=True, stderr=subprocess.PIPE).strip()

    def repository(self, configure=None):
        td, repo = copy_repo()
        self.addCleanup(td.cleanup)
        if configure:
            configure(repo)
        self.git(repo, "init", "-b", "main")
        self.git(repo, "config", "user.name", "Provenance Test")
        self.git(repo, "config", "user.email", "provenance@example.test")
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-m", "baseline")
        return repo, self.git(repo, "rev-parse", "HEAD")

    def commit(self, repo, paths, message="[DEV-001] change"):
        for name in paths:
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                stream.write("\n# change\n")
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-m", message)
        return self.git(repo, "rev-parse", "HEAD")

    @staticmethod
    def body(task="DEV-001", level="T2", attestation=True):
        text = f"Traceability Task: {task}\nTraceability Level: {level}\n"
        if attestation and level == "T2":
            text += "- [x] I acknowledge this is a material design change and have linked evidence.\n"
        elif attestation and level == "T1":
            for phrase in ("architecture", "NFRs", "security", "persistent data", "public/external API"):
                text += f"- [x] I confirm this change does **NOT** affect {phrase}.\n"
            text += "- [x] I confirm this change does **NOT** create a compliance concern.\n"
        return text

    def evidence(self, repo, base, head, body):
        result = validator.ValidationErrorSet()
        registry = validator.scan_artifacts(repo, result)
        trace = validator.validate_traceability(repo, registry, result)
        self.assertFalse(result.errors, result.errors)
        validator.validate_change_evidence(repo, trace, body, base, head, result)
        return result.errors

    @staticmethod
    def edit_yaml(repo, name, edit):
        path = repo / name
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        edit(data)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    def test_all_significant_paths_covered(self):
        repo, base = self.repository()
        head = self.commit(repo, ["src/document_indexing.py", "tools/traceability/tests/test_patient_zero.py"])
        self.assertEqual([], self.evidence(repo, base, head, self.body()))

    def test_one_uncovered_significant_path_fails(self):
        repo, base = self.repository()
        head = self.commit(repo, ["src/document_indexing.py", "src/space name.py"])
        errors = self.evidence(repo, base, head, self.body())
        self.assertTrue(any("uncovered changed path src/space name.py" in e for e in errors), errors)

    def test_multiple_tasks_collectively_cover_diff(self):
        repo, base = self.repository()
        head = self.commit(repo, ["src/document_indexing.py", "tools/traceability/validate.py"], "[DEV-001] [DEV-002] change")
        body = self.body() + self.body("DEV-002")
        self.assertEqual([], self.evidence(repo, base, head, body))
        # Canonical declaration alone is insufficient: the PR must name that task.
        errors = self.evidence(repo, base, head, self.body())
        self.assertTrue(any("uncovered changed path tools/traceability/validate.py" in e for e in errors), errors)

    def test_exempt_path_needs_no_coverage(self):
        repo, base = self.repository()
        head = self.commit(repo, ["src/document_indexing.py", "README.md"])
        self.assertEqual([], self.evidence(repo, base, head, self.body()))

    def test_documentation_only_pr_needs_no_artificial_task(self):
        repo, base = self.repository()
        head = self.commit(repo, ["README.md", "docs/guide/note.md"], "Clarify documentation")
        self.assertEqual([], self.evidence(repo, base, head, "Documentation clarification."))
        # Supplying a material task still requires its original implementation match.
        errors = self.evidence(repo, base, head, self.body())
        self.assertTrue(any("does not touch any declared implementation path" in e for e in errors), errors)

    def test_code_under_docs_is_not_exempt(self):
        repo, base = self.repository()
        head = self.commit(repo, ["docs/script.py"], "Add script")
        errors = self.evidence(repo, base, head, "")
        self.assertTrue(any("uncovered changed path docs/script.py" in e for e in errors), errors)

    def test_generated_path_requires_explicit_base_governance(self):
        for governed in (True, False):
            with self.subTest(governed=governed):
                def configure(repo):
                    if not governed:
                        self.edit_yaml(repo, "constitution/policies.yaml",
                                       lambda p: p["change_provenance"].update(generated_paths=[]))
                repo, base = self.repository(configure)
                head = self.commit(repo, ["AGENTS.md"], "Regenerate instructions")
                # Coverage check only; CI separately enforces generator reproducibility.
                errors = self.evidence(repo, base, head, "")
                if governed:
                    self.assertEqual([], errors)
                else:
                    self.assertTrue(any("uncovered changed path AGENTS.md" in e for e in errors), errors)

    def test_generated_directory_name_does_not_grant_exemption(self):
        repo, base = self.repository()
        head = self.commit(repo, ["generated/client.py"], "Add generated-looking file")
        errors = self.evidence(repo, base, head, "")
        self.assertTrue(any("uncovered changed path generated/client.py" in e for e in errors), errors)

    def test_sensitive_path_cannot_hide_behind_source_coverage(self):
        for path in ("design/architecture/CMP-001.md", "infra/network.tf", "migrations/001.sql"):
            with self.subTest(path=path):
                repo, base = self.repository()
                head = self.commit(repo, ["src/document_indexing.py", path])
                errors = self.evidence(repo, base, head, self.body())
                self.assertTrue(any(path in e and "uncovered changed path" in e for e in errors), errors)
                self.assertTrue(any(path in e and "hit T2 path triggers" in e for e in errors), errors)

    def test_sensitive_path_requires_its_covering_task_to_be_t2(self):
        for level in ("T1", "T2"):
            with self.subTest(level=level):
                def configure(repo):
                    self.edit_yaml(repo, "knowledge/traceability.yaml",
                                   lambda p: p["tasks"]["DEV-002"].update(
                                       level=level, implementation={"paths": ["design/architecture/CMP-001.md"]}))
                    path = repo / "design/tasks/DEV-002.md"
                    metadata = validator.extract_frontmatter(path)
                    metadata["traceability_level"] = level
                    path.write_text("---\n" + yaml.safe_dump(metadata) + "---\n", encoding="utf-8")
                repo, base = self.repository(configure)
                head = self.commit(repo, ["src/document_indexing.py", "design/architecture/CMP-001.md"], "[DEV-001] [DEV-002] change")
                errors = self.evidence(repo, base, head, self.body() + self.body("DEV-002", level))
                if level == "T2":
                    self.assertEqual([], errors)
                else:
                    self.assertTrue(any("hit T2 path triggers" in e for e in errors), errors)

    def test_each_task_requires_marker_and_its_own_attestation(self):
        repo, base = self.repository()
        head = self.commit(repo, ["src/document_indexing.py", "tools/traceability/validate.py"])
        errors = self.evidence(repo, base, head, self.body() + self.body("DEV-002", attestation=False))
        self.assertTrue(any("required marker [DEV-002]" in e for e in errors), errors)
        self.assertTrue(any("DEV-002 T2 risk attestation is incomplete" in e for e in errors), errors)

    def test_invalid_declarations_fail(self):
        repo, base = self.repository()
        head = self.commit(repo, ["src/document_indexing.py"])
        for body, expected in (
            (self.body() + self.body(), "duplicate task declaration"),
            (self.body("DEV-999"), "not present in traceability"),
            (self.body(level="T1"), "declared level"),
            ("Traceability Task: DEV-___\nTraceability Level: T2", "invalid Traceability Task"),
            (self.body() + "Traceability Level: T1\n", "exactly one Traceability Level"),
        ):
            with self.subTest(expected=expected):
                errors = self.evidence(repo, base, head, body)
                self.assertTrue(any(expected in e for e in errors), errors)

    def test_pr_cannot_exempt_its_own_changes(self):
        repo, base = self.repository()
        self.edit_yaml(repo, "constitution/policies.yaml",
                       lambda p: p["change_provenance"]["exempt_paths"].append("src/orphan.py"))
        head = self.commit(repo, ["src/document_indexing.py", "src/orphan.py"])
        errors = self.evidence(repo, base, head, self.body())
        self.assertTrue(any("uncovered changed path src/orphan.py" in e for e in errors), errors)

    def test_missing_base_classification_defaults_to_required(self):
        repo, base = self.repository(lambda repo: self.edit_yaml(
            repo, "constitution/policies.yaml", lambda p: p.pop("change_provenance")))
        head = self.commit(repo, ["README.md"], "Documentation")
        errors = self.evidence(repo, base, head, "")
        self.assertTrue(any("uncovered changed path README.md" in e for e in errors), errors)

    def test_rename_and_deleted_paths_require_coverage(self):
        for operation in ("rename", "delete"):
            for covered in (True, False):
                with self.subTest(operation=operation, covered=covered):
                    def configure(repo):
                        (repo / "src/legacy.py").write_text("# legacy\n", encoding="utf-8")
                        if covered:
                            self.edit_yaml(repo, "knowledge/traceability.yaml",
                                           lambda p: p["tasks"]["DEV-001"]["implementation"]["paths"].append("src/*.py"))
                    repo, base = self.repository(configure)
                    if operation == "rename":
                        (repo / "src/legacy.py").rename(repo / "docs/moved.md")
                    else:
                        (repo / "src/legacy.py").unlink()
                    head = self.commit(repo, ["src/document_indexing.py"])
                    changed = validator.changed_files(repo, base, head)
                    self.assertIn("src/legacy.py", changed)
                    if operation == "rename":
                        self.assertIn("docs/moved.md", changed)
                    errors = self.evidence(repo, base, head, self.body())
                    if covered:
                        self.assertEqual([], errors)
                    else:
                        self.assertTrue(any("uncovered changed path src/legacy.py" in e for e in errors), errors)

    def test_malformed_classification_fails_closed(self):
        for config in ({"default": "exempt"}, {"exempt_paths": "*"}, {"generated_paths": [None]}, {"exmpt_paths": ["*"]}):
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    validator.provenance_exclusions({"change_provenance": config})


if __name__ == "__main__":
    unittest.main()
