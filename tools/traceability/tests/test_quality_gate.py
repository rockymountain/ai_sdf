import unittest
from unittest.mock import patch

import yaml

import test_change_provenance as provenance
from test_validator import ValidatorTests, copy_repo, validator


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

    def edit_structural_gate(self, repo, gate_id, edit):
        self.edit_yaml(repo, "constitution/quality-gates.yaml",
                       lambda doc: edit(next(g for g in doc["gates"] if g["id"] == gate_id)))

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


class StructuralGateTests(unittest.TestCase):
    """TEST-014: QG-001/QG-002 declaration binding to existing CMP-002 enforcement."""

    git = staticmethod(provenance.ChangeProvenanceTests.git)
    repository = provenance.ChangeProvenanceTests.repository
    commit = provenance.ChangeProvenanceTests.commit
    body = staticmethod(provenance.ChangeProvenanceTests.body)
    evidence = provenance.ChangeProvenanceTests.evidence
    edit_yaml = staticmethod(provenance.ChangeProvenanceTests.edit_yaml)
    edit_structural_gate = QualityGateTests.edit_structural_gate

    def workspace(self):
        td, repo = copy_repo()
        self.addCleanup(td.cleanup)
        return repo

    def test_valid_canonical_structural_gate_configuration(self):
        gates = validator.load_structural_gates(self.workspace())
        self.assertEqual(
            (validator.StructuralGate("QG-001", "artifact-schema"),
             validator.StructuralGate("QG-002", "reference-integrity")),
            gates,
        )

    def test_structural_gates_retain_separate_identities_and_failure_evidence(self):
        for gate_id, other_id in (("QG-001", "QG-002"), ("QG-002", "QG-001")):
            with self.subTest(gate_id=gate_id):
                repo = self.workspace()
                self.edit_yaml(repo, "constitution/quality-gates.yaml",
                               lambda doc, gate_id=gate_id: doc.update(gates=[g for g in doc["gates"] if g["id"] != gate_id]))
                # Failure evidence names exactly the missing gate, never the untouched sibling.
                with self.assertRaisesRegex(ValueError, f"mandatory {gate_id} declaration"):
                    validator.load_structural_gates(repo)
                gates_doc = yaml.safe_load((repo / "constitution/quality-gates.yaml").read_text(encoding="utf-8"))
                self.assertTrue(any(g["id"] == other_id for g in gates_doc["gates"]))

    def test_missing_qg001_or_qg002_fails_closed(self):
        for gate_id in ("QG-001", "QG-002"):
            with self.subTest(gate_id=gate_id):
                repo = self.workspace()
                self.edit_yaml(repo, "constitution/quality-gates.yaml",
                               lambda doc: doc.update(gates=[g for g in doc["gates"] if g["id"] != gate_id]))
                with self.assertRaisesRegex(ValueError, "structural gate governance"):
                    validator.load_structural_gates(repo)
                result = validator.ValidationErrorSet()
                registry = validator.scan_artifacts(repo, result)
                validator.validate_traceability(repo, registry, result)
                self.assertTrue(any("structural gate governance" in e and gate_id in e for e in result.errors), result.errors)

    def test_malformed_and_disabled_structural_declarations_fail_closed(self):
        for gate_id in ("QG-001", "QG-002"):
            for change in ({"deterministic": False}, {"blocks_merge": False},
                           {"name": "renamed"}, {"unexpected": True}):
                with self.subTest(gate_id=gate_id, change=change):
                    repo = self.workspace()
                    self.edit_structural_gate(repo, gate_id, lambda g: g.update(change))
                    with self.assertRaisesRegex(ValueError, f"unsupported {gate_id} declaration shape"):
                        validator.load_structural_gates(repo)
            with self.subTest(gate_id=gate_id, change="missing field"):
                repo = self.workspace()
                self.edit_structural_gate(repo, gate_id, lambda g: g.pop("blocks_merge"))
                with self.assertRaisesRegex(ValueError, f"unsupported {gate_id} declaration shape"):
                    validator.load_structural_gates(repo)

    def test_duplicated_structural_declaration_fails_closed(self):
        for gate_id in ("QG-001", "QG-002"):
            with self.subTest(gate_id=gate_id):
                repo = self.workspace()
                self.edit_yaml(repo, "constitution/quality-gates.yaml",
                               lambda doc, gate_id=gate_id: doc["gates"].append(
                                   next(g.copy() for g in doc["gates"] if g["id"] == gate_id)))
                with self.assertRaisesRegex(ValueError, f"mandatory {gate_id} declaration is missing or duplicated"):
                    validator.load_structural_gates(repo)

    def test_unsupported_declaration_shape_fails_closed(self):
        repo = self.workspace()
        (repo / "constitution/quality-gates.yaml").write_text("version: 1\ngates: not-a-list\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "structural gate governance"):
            validator.load_structural_gates(repo)

    def test_existing_artifact_schema_behavior_is_unchanged(self):
        repo = self.workspace()
        path = repo / "design/tasks/DEV-001.md"
        path.write_text(path.read_text(encoding="utf-8").replace("status: implemented", "status: not-a-real-status"),
                         encoding="utf-8")
        result = validator.ValidationErrorSet()
        registry = validator.scan_artifacts(repo, result)
        validator.validate_traceability(repo, registry, result)
        self.assertTrue(any("not-a-real-status" in e for e in result.errors), result.errors)

    def test_existing_reference_integrity_behavior_is_unchanged(self):
        repo = self.workspace()
        self.edit_yaml(repo, "knowledge/traceability.yaml",
                       lambda doc: doc["tasks"]["DEV-001"]["decisions"].append("ADR-999"))
        result = validator.ValidationErrorSet()
        registry = validator.scan_artifacts(repo, result)
        validator.validate_traceability(repo, registry, result)
        self.assertTrue(any("ADR-999" in e and "does not exist" in e for e in result.errors), result.errors)

    def test_no_duplicate_schema_or_reference_enforcement_path_introduced(self):
        repo = self.workspace()
        result, _, _ = ValidatorTests().run_static(repo)
        self.assertEqual([], result.errors, result.errors)
        # load_structural_gates validates only declaration identity/shape; the actual
        # schema/reference engines (Draft202012Validator, iter_errors) remain solely
        # in scan_artifacts/validate_traceability, never reimplemented here.
        import inspect
        body = inspect.getsource(validator.load_structural_gates).split('"""', 2)[-1]
        self.assertNotIn("Draft202012Validator", body)
        self.assertNotIn("iter_errors", body)

    def test_missing_proposed_structural_gate_cannot_self_disable(self):
        repo, base = self.repository()
        self.edit_yaml(repo, "constitution/quality-gates.yaml",
                       lambda doc: doc.update(gates=[g for g in doc["gates"] if g["id"] != "QG-001"]))
        head = self.commit(repo, ["src/document_indexing.py"])
        result = validator.ValidationErrorSet()
        trace = validator.load_yaml(repo / "knowledge/traceability.yaml")
        validator.validate_change_evidence(repo, trace, self.body(), base, head, result)
        self.assertTrue(
            any("structural gate governance (workspace)" in e and "QG-001" in e for e in result.errors),
            result.errors,
        )

    def test_malformed_base_structural_gate_fails_closed_for_the_pr(self):
        def break_base(repo):
            self.edit_yaml(repo, "constitution/quality-gates.yaml",
                           lambda doc: doc.update(gates=[g for g in doc["gates"] if g["id"] != "QG-002"]))
        repo, base = self.repository(break_base)
        self.edit_yaml(repo, "constitution/quality-gates.yaml",
                       lambda doc: doc["gates"].append({"id": "QG-002", "name": "reference-integrity",
                                                        "deterministic": True, "blocks_merge": True}))
        head = self.commit(repo, ["src/document_indexing.py"])
        result = validator.ValidationErrorSet()
        trace = validator.load_yaml(repo / "knowledge/traceability.yaml")
        validator.validate_change_evidence(repo, trace, self.body(), base, head, result)
        self.assertTrue(
            any(f"structural gate governance ({base})" in e and "QG-002" in e for e in result.errors),
            result.errors,
        )

    def test_qg004_configuration_and_regressions_remain_passing_alongside_structural_gates(self):
        repo = self.workspace()
        gate = validator.load_implementation_evidence_gate(repo)
        self.assertEqual(("T1", "T2"), gate.levels)
        structural = validator.load_structural_gates(repo)
        self.assertEqual(2, len(structural))
        result, _, _ = ValidatorTests().run_static(repo)
        self.assertFalse(result.errors, result.errors)


class TraceabilityRiskGateTests(unittest.TestCase):
    """TEST-015: QG-003 traceability-policy / QG-005 risk-attestation authoritative
    binding, base/proposed self-protection, and the pinned pre-Increment-B bootstrap."""

    git = staticmethod(provenance.ChangeProvenanceTests.git)
    repository = provenance.ChangeProvenanceTests.repository
    commit = provenance.ChangeProvenanceTests.commit
    body = staticmethod(provenance.ChangeProvenanceTests.body)
    evidence = provenance.ChangeProvenanceTests.evidence
    edit_yaml = staticmethod(provenance.ChangeProvenanceTests.edit_yaml)
    edit_structural_gate = QualityGateTests.edit_structural_gate

    def workspace(self):
        td, repo = copy_repo()
        self.addCleanup(td.cleanup)
        return repo

    def legacy_gates(self, repo):
        self.edit_structural_gate(repo, "QG-003", lambda g: g.pop("policy"))
        self.edit_structural_gate(repo, "QG-005", lambda g: (g.pop("scope"), g.pop("policy")))

    # -- Valid canonical configuration -----------------------------------------

    def test_valid_canonical_configuration(self):
        trace_policy, risk_policy = validator.load_traceability_and_risk_gates(self.workspace())
        self.assertEqual({"T0", "T1", "T2"}, set(trace_policy.levels))
        self.assertEqual(8, len(trace_policy.escalation_triggers))
        self.assertTrue(trace_policy.t2_path_triggers)
        self.assertEqual((), risk_policy.levels["T0"])
        self.assertEqual(6, len(risk_policy.levels["T1"]))
        self.assertEqual(("material design change",), risk_policy.levels["T2"])

    # -- QG-003 / QG-005 declaration failures -----------------------------------

    def test_qg003_and_qg005_declaration_failures_fail_closed(self):
        for gate_id in ("QG-003", "QG-005"):
            for change in ({"deterministic": False}, {"blocks_merge": False},
                           {"name": "renamed"}, {"unexpected": True}):
                with self.subTest(gate_id=gate_id, change=change):
                    repo = self.workspace()
                    self.edit_structural_gate(repo, gate_id, lambda g, change=change: g.update(change))
                    with self.assertRaises(ValueError):
                        validator.load_traceability_and_risk_gates(repo)
            with self.subTest(gate_id=gate_id, change="missing"):
                repo = self.workspace()
                self.edit_yaml(repo, "constitution/quality-gates.yaml",
                               lambda doc, gate_id=gate_id: doc.update(gates=[g for g in doc["gates"] if g["id"] != gate_id]))
                with self.assertRaisesRegex(ValueError, f"mandatory {gate_id} declaration is missing"):
                    validator.load_traceability_and_risk_gates(repo)
            with self.subTest(gate_id=gate_id, change="duplicate"):
                repo = self.workspace()
                self.edit_yaml(repo, "constitution/quality-gates.yaml",
                               lambda doc, gate_id=gate_id: doc["gates"].append(
                                   next(g.copy() for g in doc["gates"] if g["id"] == gate_id)))
                with self.assertRaisesRegex(ValueError, f"mandatory {gate_id} declaration is missing or duplicated"):
                    validator.load_traceability_and_risk_gates(repo)

        repo = self.workspace()
        self.edit_structural_gate(repo, "QG-003", lambda g: g.update(policy="wrong"))
        with self.assertRaises(ValueError):
            validator.load_traceability_and_risk_gates(repo)
        repo = self.workspace()
        self.edit_structural_gate(repo, "QG-005", lambda g: g.update(policy="wrong"))
        with self.assertRaises(ValueError):
            validator.load_traceability_and_risk_gates(repo)
        repo = self.workspace()
        self.edit_structural_gate(repo, "QG-005", lambda g: g["scope"].update(event="push"))
        with self.assertRaises(ValueError):
            validator.load_traceability_and_risk_gates(repo)

    # -- Trace-policy / risk-policy completeness --------------------------------

    def test_trace_policy_completeness_fails_closed(self):
        booleans = ("upstream_intent", "design", "decision_or_contract", "implementation", "verification", "risk_attestation")
        cases = [
            lambda p: p["traceability"]["levels"].pop("T0"),
            lambda p: p["traceability"]["levels"].update(T3={"description": "x", "requires": {k: False for k in booleans}}),
            lambda p: p["traceability"]["levels"]["T2"].pop("description"),
            lambda p: p["traceability"]["levels"]["T2"].update(description=""),
            lambda p: p["traceability"]["levels"]["T2"].pop("requires"),
            lambda p: p["traceability"]["levels"]["T2"]["requires"].pop("design"),
            lambda p: p["traceability"]["levels"]["T2"]["requires"].update(design="yes"),
            lambda p: p["traceability"]["levels"]["T2"]["requires"].update(extra=True),
            lambda p: p["traceability"].update(escalation_triggers=[]),
            lambda p: p["traceability"]["escalation_triggers"].remove("security"),
            lambda p: p["traceability"]["escalation_triggers"].append("architecture"),
            lambda p: p["traceability"]["escalation_triggers"].append("unknown_trigger"),
            lambda p: p["traceability"].pop("t2_path_triggers"),
            lambda p: p["traceability"].update(t2_path_triggers=[]),
            lambda p: p["traceability"].update(t2_path_triggers=[""]),
        ]
        for index, mutate in enumerate(cases):
            with self.subTest(case=index):
                repo = self.workspace()
                self.edit_yaml(repo, "constitution/policies.yaml", mutate)
                with self.assertRaises(ValueError):
                    validator.load_traceability_and_risk_gates(repo)

    def test_risk_policy_completeness_fails_closed(self):
        cases = [
            lambda p: p.pop("risk_attestation"),
            lambda p: p["risk_attestation"].pop("evidence_source"),
            lambda p: p["risk_attestation"].update(evidence_source="unsupported"),
            lambda p: p["risk_attestation"].pop("evidence_format"),
            lambda p: p["risk_attestation"].update(evidence_format="unsupported"),
            lambda p: p["risk_attestation"].pop("match_mode"),
            lambda p: p["risk_attestation"].update(match_mode="unsupported"),
            lambda p: p["risk_attestation"]["levels"].pop("T1"),
            lambda p: p["risk_attestation"]["levels"].update(T3={"required_substrings": []}),
            lambda p: p["risk_attestation"]["levels"]["T1"].pop("required_substrings"),
            lambda p: p["risk_attestation"]["levels"]["T1"]["required_substrings"].append(
                p["risk_attestation"]["levels"]["T1"]["required_substrings"][0]),
            lambda p: p["risk_attestation"]["levels"]["T1"]["required_substrings"].append(""),
            lambda p: p["risk_attestation"]["levels"]["T1"].update(extra=True),
        ]
        for index, mutate in enumerate(cases):
            with self.subTest(case=index):
                repo = self.workspace()
                self.edit_yaml(repo, "constitution/policies.yaml", mutate)
                with self.assertRaises(ValueError):
                    validator.load_traceability_and_risk_gates(repo)

    # -- Applicability / evidence separation ------------------------------------

    def test_t0_fixture_proves_policy_driven_applicability(self):
        repo = self.workspace()
        self.edit_yaml(repo, "constitution/policies.yaml", lambda p: (
            p["traceability"]["levels"]["T0"]["requires"].update(risk_attestation=True),
            p["risk_attestation"]["levels"]["T0"].update(required_substrings=["fixture-only T0 attestation"]),
        ))
        trace_policy, risk_policy = validator.load_traceability_and_risk_gates(repo)
        self.assertTrue(trace_policy.levels["T0"].requires["risk_attestation"])
        self.assertEqual(("fixture-only T0 attestation",), risk_policy.levels["T0"])

    def test_t0_risk_attestation_is_enforced_through_the_real_pr_path(self):
        # Loader-level applicability alone is insufficient: this proves the
        # PR/change-evidence enforcement path itself rejects/accepts based on
        # canonical requires.risk_attestation for T0, with no hidden special case.
        def configure(repo):
            self.edit_yaml(repo, "constitution/policies.yaml", lambda p: (
                p["traceability"]["levels"]["T0"]["requires"].update(risk_attestation=True),
                p["risk_attestation"]["levels"]["T0"].update(required_substrings=["fixture-only T0 attestation"]),
            ))
        repo, base = self.repository(configure)
        head = self.commit(repo, ["tools/traceability/validate.py"], "[DEV-009] change")
        body_without_evidence = "Traceability Task: DEV-009\nTraceability Level: T0\n"
        errors = self.evidence(repo, base, head, body_without_evidence)
        self.assertTrue(any("DEV-009 base T0 risk attestation is incomplete" in e for e in errors), errors)
        self.assertTrue(any("DEV-009 proposed T0 risk attestation is incomplete" in e for e in errors), errors)
        body_with_evidence = body_without_evidence + "- [x] fixture-only T0 attestation\n"
        self.assertEqual([], self.evidence(repo, base, head, body_with_evidence))

    def test_applicable_level_with_empty_contract_fails_closed(self):
        repo = self.workspace()
        self.edit_yaml(repo, "constitution/policies.yaml",
                       lambda p: p["traceability"]["levels"]["T0"]["requires"].update(risk_attestation=True))
        with self.assertRaisesRegex(ValueError, "applicable but has no required evidence"):
            validator.load_traceability_and_risk_gates(repo)

    def test_non_applicable_level_may_carry_populated_contract(self):
        repo = self.workspace()
        self.edit_yaml(repo, "constitution/policies.yaml",
                       lambda p: p["risk_attestation"]["levels"]["T0"].update(required_substrings=["dormant"]))
        trace_policy, risk_policy = validator.load_traceability_and_risk_gates(repo)
        self.assertFalse(trace_policy.levels["T0"].requires["risk_attestation"])
        self.assertEqual(("dormant",), risk_policy.levels["T0"])

    # -- Schema provenance -------------------------------------------------------

    def test_base_schema_provenance_is_immune_to_workspace_schema_mutation(self):
        for schema_path in (validator.QG003_SCHEMA, validator.QG005_SCHEMA):
            with self.subTest(schema=schema_path):
                repo, base = self.repository()
                (repo / schema_path).write_text("not valid json", encoding="utf-8")
                with self.assertRaises(ValueError):
                    validator.load_traceability_and_risk_gates(repo)
                trace_policy, risk_policy = validator.load_traceability_and_risk_gates(repo, base)
                self.assertIn("T2", trace_policy.levels)
                self.assertEqual(("material design change",), risk_policy.levels["T2"])

    # -- Bootstrap ----------------------------------------------------------------

    def test_bootstrap_pinned_legacy_happy_path(self):
        repo, base = self.repository(self.legacy_gates)
        with self.assertRaises(ValueError):
            validator.load_traceability_and_risk_gates(repo, base)
        with patch.object(validator, "QG003_QG005_BOOTSTRAP_BASE", base):
            trace_policy, risk_policy = validator.load_traceability_and_risk_gates(repo, base)
            self.assertEqual({"T0", "T1", "T2"}, set(trace_policy.levels))
            self.assertEqual(risk_policy.levels["T1"], validator.LEGACY_RISK_ATTESTATION_SUBSTRINGS["T1"])
            self.assertEqual(risk_policy.levels["T2"], validator.LEGACY_RISK_ATTESTATION_SUBSTRINGS["T2"])
            # Legacy shape in the workspace never triggers bootstrap treatment.
            with self.assertRaises(ValueError):
                validator.load_traceability_and_risk_gates(repo)

    def test_bootstrap_wrong_revision_is_rejected(self):
        repo, historical = self.repository(self.legacy_gates)
        with self.assertRaises(ValueError):
            validator.load_traceability_and_risk_gates(repo, historical)

    # B0 section 12.2: the pinned base must accept only exactly one mapping of
    # each legacy gate, with exact keys, exact id/name, and deterministic/
    # blocks_merge as actual boolean True (never a merely-equal-under-`==`
    # value such as the integer 1, since `1 == True` in Python).
    LEGACY_GATE_MALFORMATIONS = (
        ("missing", lambda doc, gid: doc.update(gates=[g for g in doc["gates"] if g["id"] != gid])),
        ("duplicate", lambda doc, gid: doc["gates"].append(next(g.copy() for g in doc["gates"] if g["id"] == gid))),
        ("wrong_name", lambda doc, gid: next(g for g in doc["gates"] if g["id"] == gid).update(name="renamed")),
        ("deterministic_false", lambda doc, gid: next(g for g in doc["gates"] if g["id"] == gid).update(deterministic=False)),
        ("blocks_merge_false", lambda doc, gid: next(g for g in doc["gates"] if g["id"] == gid).update(blocks_merge=False)),
        ("deterministic_wrong_type_int", lambda doc, gid: next(g for g in doc["gates"] if g["id"] == gid).update(deterministic=1)),
        ("blocks_merge_wrong_type_int", lambda doc, gid: next(g for g in doc["gates"] if g["id"] == gid).update(blocks_merge=1)),
        ("deterministic_wrong_type_str", lambda doc, gid: next(g for g in doc["gates"] if g["id"] == gid).update(deterministic="true")),
        ("blocks_merge_wrong_type_str", lambda doc, gid: next(g for g in doc["gates"] if g["id"] == gid).update(blocks_merge="true")),
        ("extra_field", lambda doc, gid: next(g for g in doc["gates"] if g["id"] == gid).update(extra=True)),
        ("non_mapping", lambda doc, gid: doc.update(gates=[("not-a-mapping" if g["id"] == gid else g) for g in doc["gates"]])),
    )

    def test_bootstrap_declaration_failures_fail_closed(self):
        for gate_id in ("QG-003", "QG-005"):
            for name, mutate in self.LEGACY_GATE_MALFORMATIONS:
                with self.subTest(gate_id=gate_id, case=name):
                    def configure(repo, gate_id=gate_id, mutate=mutate):
                        self.legacy_gates(repo)
                        self.edit_yaml(repo, "constitution/quality-gates.yaml",
                                       lambda doc, gate_id=gate_id, mutate=mutate: mutate(doc, gate_id))
                    repo, base = self.repository(configure)
                    with patch.object(validator, "QG003_QG005_BOOTSTRAP_BASE", base):
                        with self.assertRaises(ValueError):
                            validator.load_traceability_and_risk_gates(repo, base)

    def test_malformed_base_gate_cannot_be_rescued_by_permissive_proposed_schema(self):
        # A proposed/workspace schema permissive enough to accept the malformed
        # legacy declaration must be irrelevant: the pinned bootstrap precondition
        # never consults the proposed schema to interpret the legacy base.
        for gate_id, schema_path in (("QG-003", validator.QG003_SCHEMA), ("QG-005", validator.QG005_SCHEMA)):
            with self.subTest(gate_id=gate_id):
                def configure(repo, gate_id=gate_id):
                    self.legacy_gates(repo)
                    self.edit_structural_gate(repo, gate_id, lambda g: g.update(deterministic=1))
                repo, base = self.repository(configure)
                (repo / schema_path).write_text('{"type": "object"}', encoding="utf-8")
                with patch.object(validator, "QG003_QG005_BOOTSTRAP_BASE", base):
                    with self.assertRaises(ValueError):
                        validator.load_traceability_and_risk_gates(repo, base)

    def test_bootstrap_ignores_proposed_schema_and_risk_policy(self):
        repo, base = self.repository(self.legacy_gates)
        (repo / validator.QG003_SCHEMA).write_text("not valid json", encoding="utf-8")
        (repo / validator.QG005_SCHEMA).write_text("not valid json", encoding="utf-8")
        self.edit_yaml(repo, "constitution/policies.yaml",
                       lambda p: p["risk_attestation"]["levels"]["T2"].update(required_substrings=["a different phrase"]))
        with patch.object(validator, "QG003_QG005_BOOTSTRAP_BASE", base):
            _, risk_policy = validator.load_traceability_and_risk_gates(repo, base)
            self.assertEqual(("material design change",), risk_policy.levels["T2"])

    # -- Existing-task transition -------------------------------------------------

    def test_existing_t2_to_t1_transition_cannot_delete_base_required_evidence(self):
        repo, base = self.repository()
        self.edit_yaml(repo, "knowledge/traceability.yaml", lambda d: d["tasks"]["DEV-001"].update(
            level="T1", design=[], decisions=[], contracts=[],
            implementation={"paths": d["tasks"]["DEV-001"]["implementation"]["paths"] + [
                "knowledge/traceability.yaml", "design/tasks/DEV-001.md"]},
        ))
        path = repo / "design/tasks/DEV-001.md"
        metadata = validator.extract_frontmatter(path)
        metadata["traceability_level"] = "T1"
        path.write_text("---\n" + yaml.safe_dump(metadata) + "---\n", encoding="utf-8")
        head = self.commit(repo, ["src/document_indexing.py"], "[DEV-001] downgrade")
        errors = self.evidence(repo, base, head, self.body(level="T1"))
        self.assertTrue(any("DEV-001 (base T2): requires design evidence" in e for e in errors), errors)
        self.assertTrue(any("DEV-001 (base T2): requires at least one decision or contract" in e for e in errors), errors)

    def test_existing_t2_to_t1_transition_succeeds_when_base_evidence_survives(self):
        repo, base = self.repository()
        self.edit_yaml(repo, "knowledge/traceability.yaml", lambda d: d["tasks"]["DEV-001"].update(
            level="T1",
            implementation={"paths": d["tasks"]["DEV-001"]["implementation"]["paths"] + [
                "knowledge/traceability.yaml", "design/tasks/DEV-001.md"]},
        ))
        path = repo / "design/tasks/DEV-001.md"
        metadata = validator.extract_frontmatter(path)
        metadata["traceability_level"] = "T1"
        path.write_text("---\n" + yaml.safe_dump(metadata) + "---\n", encoding="utf-8")
        head = self.commit(repo, ["src/document_indexing.py"], "[DEV-001] downgrade")
        body = self.body(level="T1") + "- [x] I acknowledge this is a material design change and have linked evidence.\n"
        self.assertEqual([], self.evidence(repo, base, head, body))

    def test_existing_t1_to_t2_upgrade_enforces_proposed_requirement(self):
        # Risk attestation (never checked statically) isolates the cross-revision
        # applicability check from static design/decision/verification requirements.
        def configure(repo):
            self.edit_yaml(repo, "knowledge/traceability.yaml", lambda d: d["tasks"]["DEV-001"].update(
                level="T1",
                implementation={"paths": d["tasks"]["DEV-001"]["implementation"]["paths"] + [
                    "knowledge/traceability.yaml", "design/tasks/DEV-001.md"]},
            ))
            path = repo / "design/tasks/DEV-001.md"
            metadata = validator.extract_frontmatter(path)
            metadata["traceability_level"] = "T1"
            path.write_text("---\n" + yaml.safe_dump(metadata) + "---\n", encoding="utf-8")
            # Base-only policy weakening: base T1 does not require risk attestation.
            self.edit_yaml(repo, "constitution/policies.yaml",
                           lambda p: p["traceability"]["levels"]["T1"]["requires"].update(risk_attestation=False))
        repo, base = self.repository(configure)
        self.edit_yaml(repo, "knowledge/traceability.yaml", lambda d: d["tasks"]["DEV-001"].update(level="T2"))
        path = repo / "design/tasks/DEV-001.md"
        metadata = validator.extract_frontmatter(path)
        metadata["traceability_level"] = "T2"
        path.write_text("---\n" + yaml.safe_dump(metadata) + "---\n", encoding="utf-8")
        head = self.commit(repo, ["src/document_indexing.py"], "[DEV-001] upgrade")
        for attest in (False, True):
            with self.subTest(attest=attest):
                body = "Traceability Task: DEV-001\nTraceability Level: T2\n"
                if attest:
                    body += "- [x] I acknowledge this is a material design change and have linked evidence.\n"
                errors = self.evidence(repo, base, head, body)
                if attest:
                    self.assertEqual([], errors)
                else:
                    self.assertTrue(any("DEV-001 proposed T2 risk attestation is incomplete" in e for e in errors), errors)
                    self.assertFalse(any("DEV-001 base T1 risk attestation is incomplete" in e for e in errors), errors)

    # -- New-task base-policy projection -------------------------------------------

    def test_new_task_cannot_self_waive_base_risk_requirement(self):
        repo, base = self.repository()
        self.edit_yaml(repo, "knowledge/traceability.yaml", lambda d: d["tasks"].update(**{
            "DEV-021": {
                "level": "T2", "intent": ["FR-001"], "design": ["CMP-001"],
                "decisions": ["ADR-001"], "verification": ["TEST-001"],
                "implementation": {"paths": [
                    "src/document_indexing.py", "knowledge/traceability.yaml", "design/tasks/DEV-021.md",
                    "constitution/policies.yaml"]},
            },
        }))
        (repo / "design/tasks/DEV-021.md").write_text(
            "---\nid: DEV-021\nkind: task\ntitle: New task\nstatus: proposed\nversion: 1\n"
            "traceability_level: T2\nowner: factory-maintainer\n---\n# New task\n",
            encoding="utf-8",
        )
        # Proposed governance weakens T2 risk applicability; canonical base policy still requires it.
        self.edit_yaml(repo, "constitution/policies.yaml",
                       lambda p: p["traceability"]["levels"]["T2"]["requires"].update(risk_attestation=False))
        head = self.commit(repo, ["src/document_indexing.py", "design/tasks/DEV-021.md"], "[DEV-021] new task")
        body = "Traceability Task: DEV-021\nTraceability Level: T2\n"
        errors = self.evidence(repo, base, head, body)
        self.assertTrue(any("DEV-021 base T2 risk attestation is incomplete" in e for e in errors), errors)
        body_with_attestation = body + "- [x] I acknowledge this is a material design change and have linked evidence.\n"
        self.assertEqual([], self.evidence(repo, base, head, body_with_attestation))

    def test_base_and_proposed_risk_contracts_are_independently_enforced(self):
        # B0 section 27.9: distinct applicable base/proposed evidence contracts
        # must both be satisfied in the same PR task block, without collapsing
        # into one opaque merged contract that loses base/proposed identity.
        def configure(repo):
            self.edit_yaml(repo, "constitution/policies.yaml",
                           lambda p: p["risk_attestation"]["levels"]["T2"].update(
                               required_substrings=["base-only attestation"]))
        repo, base = self.repository(configure)
        self.edit_yaml(repo, "constitution/policies.yaml",
                       lambda p: p["risk_attestation"]["levels"]["T2"].update(
                           required_substrings=["proposed-only attestation"]))
        self.edit_yaml(repo, "knowledge/traceability.yaml", lambda d: d["tasks"]["DEV-001"].update(
            implementation={"paths": d["tasks"]["DEV-001"]["implementation"]["paths"] + [
                "constitution/policies.yaml", "knowledge/traceability.yaml"]}))
        head = self.commit(repo, ["src/document_indexing.py"], "[DEV-001] change")

        proposed_only_body = "Traceability Task: DEV-001\nTraceability Level: T2\n- [x] proposed-only attestation\n"
        errors = self.evidence(repo, base, head, proposed_only_body)
        self.assertTrue(any("DEV-001 base T2 risk attestation is incomplete" in e for e in errors), errors)
        self.assertFalse(any("DEV-001 proposed T2 risk attestation is incomplete" in e for e in errors), errors)

        base_only_body = "Traceability Task: DEV-001\nTraceability Level: T2\n- [x] base-only attestation\n"
        errors = self.evidence(repo, base, head, base_only_body)
        self.assertTrue(any("DEV-001 proposed T2 risk attestation is incomplete" in e for e in errors), errors)
        self.assertFalse(any("DEV-001 base T2 risk attestation is incomplete" in e for e in errors), errors)

        both_body = ("Traceability Task: DEV-001\nTraceability Level: T2\n"
                     "- [x] base-only attestation\n- [x] proposed-only attestation\n")
        self.assertEqual([], self.evidence(repo, base, head, both_body))

    # -- Removed-task fail-closed ---------------------------------------------------

    def test_pr_relevant_removed_task_fails_closed(self):
        repo, base = self.repository()
        self.edit_yaml(repo, "knowledge/traceability.yaml", lambda d: d["tasks"].pop("DEV-002"))
        (repo / "design/tasks/DEV-002.md").unlink()
        head = self.commit(
            repo, ["src/document_indexing.py", "tools/traceability/tests/test_validator.py"],
            "[DEV-001] remove DEV-002",
        )
        # Path-matched removal without declaration.
        errors = self.evidence(repo, base, head, self.body())
        self.assertTrue(
            any("DEV-002: base task is relevant to this PR but is absent from proposed traceability" in e for e in errors),
            errors,
        )
        # Declared removal.
        errors_declared = self.evidence(repo, base, head, self.body("DEV-002"))
        self.assertTrue(any("not present in traceability" in e for e in errors_declared), errors_declared)
        self.assertTrue(
            any("DEV-002: base task is relevant" in e for e in errors_declared),
            errors_declared,
        )

    # -- T2 path base/proposed protection --------------------------------------------

    def test_removing_proposed_t2_path_trigger_cannot_disable_base_protection(self):
        repo, base = self.repository()
        self.edit_yaml(repo, "constitution/policies.yaml",
                       lambda p: p["traceability"].update(t2_path_triggers=["nonexistent/**"]))
        head = self.commit(repo, ["src/document_indexing.py", "design/architecture/CMP-001.md"], "[DEV-001] change")
        errors = self.evidence(repo, base, head, self.body())
        self.assertTrue(any("hit T2 path triggers" in e for e in errors), errors)

    # -- Regression safety -------------------------------------------------------------

    def test_regression_families_remain_passing_alongside_new_gates(self):
        repo = self.workspace()
        result, _, _ = ValidatorTests().run_static(repo)
        self.assertEqual([], result.errors, result.errors)
        structural = validator.load_structural_gates(repo)
        self.assertEqual(2, len(structural))
        gate = validator.load_implementation_evidence_gate(repo)
        self.assertEqual(("T1", "T2"), gate.levels)


if __name__ == "__main__":
    unittest.main()
