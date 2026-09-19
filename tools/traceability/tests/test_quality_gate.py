import unittest
from unittest.mock import patch

import yaml

import test_change_provenance as provenance
from test_validator import copy_repo, validator


class QualityGateTests(unittest.TestCase):
    # Reuse real-Git fixture operations without inheriting/discovering their tests twice.
    git = staticmethod(provenance.ChangeProvenanceTests.git)
    repository = provenance.ChangeProvenanceTests.repository
    commit = provenance.ChangeProvenanceTests.commit
    body = staticmethod(provenance.ChangeProvenanceTests.body)
    evidence = provenance.ChangeProvenanceTests.evidence
    edit_yaml = staticmethod(provenance.ChangeProvenanceTests.edit_yaml)

    def workspace(self):
        td, repo = copy_repo()
        self.addCleanup(td.cleanup)
        return repo

    def edit_gate(self, repo, edit):
        self.edit_yaml(repo, "constitution/quality-gates.yaml",
                       lambda doc: edit(next(g for g in doc["gates"] if g["id"] == "QG-004")))

    def edit_policy(self, repo, **settings):
        self.edit_yaml(repo, "constitution/policies.yaml",
                       lambda doc: doc["implementation_evidence"].update(settings))

    def test_valid_canonical_gate_configuration(self):
        gate = validator.load_implementation_evidence_gate(self.workspace())
        self.assertEqual(("T1", "T2"), gate.levels)
        self.assertTrue(gate.require_commit_marker)
        self.assertTrue(gate.require_changed_path_match)
        self.assertEqual("[DEV-n]", gate.marker_format)

    def test_missing_mandatory_files_fail_static_validation(self):
        for name in ("constitution/quality-gates.yaml", "constitution/policies.yaml", validator.QG004_SCHEMA):
            with self.subTest(name=name):
                repo = self.workspace()
                (repo / name).unlink()
                result = validator.ValidationErrorSet()
                registry = validator.scan_artifacts(repo, result)
                validator.validate_traceability(repo, registry, result)
                self.assertTrue(any("QG-004 governance" in e for e in result.errors), result.errors)

    def test_missing_gate_and_mandatory_fields_fail_closed(self):
        mutations = [lambda repo: self.edit_yaml(repo, "constitution/quality-gates.yaml",
                     lambda doc: doc.update(gates=[g for g in doc["gates"] if g["id"] != "QG-004"]))]
        for field in ("scope", "policy", "blocks_merge", "deterministic"):
            mutations.append(lambda repo, field=field: self.edit_gate(repo, lambda g: g.pop(field)))
        for field in ("t1_t2_require_commit_marker", "commit_marker_format", "t1_t2_require_changed_path_match"):
            mutations.append(lambda repo, field=field: self.edit_yaml(repo, "constitution/policies.yaml",
                             lambda doc: doc["implementation_evidence"].pop(field)))
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                repo = self.workspace()
                mutate(repo)
                with self.assertRaisesRegex(ValueError, "QG-004 governance"):
                    validator.load_implementation_evidence_gate(repo)

    def test_malformed_gate_and_policy_fail_closed(self):
        for change in ({"blocks_merge": False}, {"deterministic": False},
                       {"scope": {"event": "push", "levels": ["T2"]}},
                       {"scope": {"event": "pull_request", "levels": []}},
                       {"scope": {"event": "pull_request", "levels": ["T2", "T2"]}},
                       {"policy": "unknown"}, {"unknown": True}):
            with self.subTest(change=change):
                repo = self.workspace()
                self.edit_gate(repo, lambda g: g.update(change))
                with self.assertRaises(ValueError):
                    validator.load_implementation_evidence_gate(repo)
        for change in ({"t1_t2_require_commit_marker": "false"},
                       {"t1_t2_require_changed_path_match": 1},
                       {"commit_marker_format": ""}, {"commit_marker_format": "DEV-n DEV-n"},
                       {"commit_marker_format": "DEV-n\n"}):
            with self.subTest(change=change):
                repo = self.workspace()
                self.edit_policy(repo, **change)
                with self.assertRaises(ValueError):
                    validator.load_implementation_evidence_gate(repo)

    def test_duplicate_gate_ids_and_yaml_keys_fail_closed(self):
        repo = self.workspace()
        self.edit_yaml(repo, "constitution/quality-gates.yaml",
                       lambda doc: doc["gates"].append(next(g.copy() for g in doc["gates"] if g["id"] == "QG-004")))
        with self.assertRaisesRegex(ValueError, "duplicate quality gate ID"):
            validator.load_implementation_evidence_gate(repo)
        repo = self.workspace()
        path = repo / "constitution/policies.yaml"
        path.write_text(path.read_text(encoding="utf-8") + "\nimplementation_evidence: {}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate governance key"):
            validator.load_implementation_evidence_gate(repo)

    def test_canonical_flags_are_executed(self):
        for flags, paths, message in (
            ({"t1_t2_require_commit_marker": False}, ["src/document_indexing.py"], "No marker required"),
            ({"t1_t2_require_changed_path_match": False}, ["README.md"], "[DEV-001] documentation"),
        ):
            with self.subTest(flags=flags):
                repo, base = self.repository(lambda repo: self.edit_policy(repo, **flags))
                head = self.commit(repo, paths, message)
                self.assertEqual([], self.evidence(repo, base, head, self.body()))

    def test_canonical_marker_format_is_executed(self):
        repo, base = self.repository(lambda repo: self.edit_policy(repo, commit_marker_format="<DEV-n>"))
        head = self.commit(repo, ["src/document_indexing.py"], "<DEV-001> change")
        self.assertEqual([], self.evidence(repo, base, head, self.body()))

    def test_t0_t1_t2_behavior_remains_compatible(self):
        for level in ("T0", "T1", "T2"):
            with self.subTest(level=level):
                def configure(repo):
                    self.edit_yaml(repo, "knowledge/traceability.yaml", lambda d: d["tasks"]["DEV-001"].update(level=level))
                    path = repo / "design/tasks/DEV-001.md"
                    metadata = validator.extract_frontmatter(path)
                    metadata["traceability_level"] = level
                    path.write_text("---\n" + yaml.safe_dump(metadata) + "---\n", encoding="utf-8")
                repo, base = self.repository(configure)
                head = self.commit(repo, ["src/document_indexing.py"], "Change without marker")
                errors = self.evidence(repo, base, head, self.body(level=level))
                if level == "T0":
                    self.assertEqual([], errors)
                else:
                    self.assertTrue(any("required marker [DEV-001]" in e for e in errors), errors)

    def test_canonical_scope_is_executed(self):
        repo, base = self.repository(lambda repo: self.edit_gate(repo, lambda g: g["scope"].update(levels=["T0"])))
        head = self.commit(repo, ["README.md"], "Documentation")
        # Fixture governance excludes T2: unrelated families still run, but QG-004 does not.
        self.assertEqual([], self.evidence(repo, base, head, self.body()))

    def test_proposed_scope_and_flags_cannot_disable_base_obligations(self):
        repo, base = self.repository()
        self.edit_policy(repo, t1_t2_require_commit_marker=False, t1_t2_require_changed_path_match=False)
        self.edit_gate(repo, lambda g: g["scope"].update(levels=["T0"]))
        head = self.commit(repo, ["README.md"], "Attempt to weaken policy")
        errors = self.evidence(repo, base, head, self.body())
        self.assertTrue(any("required marker [DEV-001]" in e for e in errors), errors)
        self.assertTrue(any("does not touch any declared implementation path" in e for e in errors), errors)

    def test_proposed_marker_cannot_replace_base_marker(self):
        repo, base = self.repository()
        self.edit_policy(repo, commit_marker_format="<DEV-n>")
        head = self.commit(repo, ["src/document_indexing.py"], "<DEV-001> change")
        errors = self.evidence(repo, base, head, self.body())
        self.assertTrue(any("required marker [DEV-001]" in e for e in errors), errors)

    def test_missing_proposed_gate_cannot_self_disable(self):
        repo, base = self.repository()
        (repo / "constitution/quality-gates.yaml").unlink()
        head = self.commit(repo, ["src/document_indexing.py"])
        result = validator.ValidationErrorSet()
        trace = validator.load_yaml(repo / "knowledge/traceability.yaml")
        validator.validate_change_evidence(repo, trace, self.body(), base, head, result)
        self.assertTrue(any("QG-004 governance (workspace)" in e for e in result.errors), result.errors)

    def test_bootstrap_is_only_for_the_pinned_base_never_workspace(self):
        def legacy(repo):
            self.edit_gate(repo, lambda g: (g.pop("scope"), g.pop("policy")))
        repo, base = self.repository(legacy)
        with self.assertRaises(ValueError):
            validator.load_implementation_evidence_gate(repo, base)
        # Pin this immutable fixture commit only for the adapter test.
        with patch.object(validator, "QG004_BOOTSTRAP_BASE", base):
            gate = validator.load_implementation_evidence_gate(repo, base)
            self.assertEqual(("T1", "T2"), gate.levels)
            self.assertTrue(gate.require_commit_marker)
            with self.assertRaises(ValueError):
                validator.load_implementation_evidence_gate(repo)


if __name__ == "__main__":
    unittest.main()
