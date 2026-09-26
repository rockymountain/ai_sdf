import subprocess
import sys
import unittest

from test_validator import ROOT, copy_repo, validator


class LearningDispositionTests(unittest.TestCase):
    """TEST-020: FR-012/ADR-014 learning-disposition shape and AGENTS.md projection."""

    def workspace(self):
        td, repo = copy_repo()
        self.addCleanup(td.cleanup)
        return repo

    def test_valid_disposition_values_pass(self):
        repo = self.workspace()
        for value in (
            "NEW_LEARNING_CANDIDATE",
            "EXISTING_LEARNING_REINFORCED",
            "NO_REUSABLE_LEARNING",
        ):
            with self.subTest(value=value):
                validator.validate_learning_disposition(
                    repo, {"value": value, "rationale": "brief evidence-based rationale"}
                )

    def test_missing_value_fails_closed(self):
        repo = self.workspace()
        with self.assertRaises(ValueError):
            validator.validate_learning_disposition(repo, {"rationale": "why"})

    def test_invalid_enum_value_fails_closed(self):
        repo = self.workspace()
        with self.assertRaises(ValueError):
            validator.validate_learning_disposition(
                repo, {"value": "MAYBE_LEARNING", "rationale": "why"}
            )

    def test_missing_rationale_fails_closed(self):
        repo = self.workspace()
        with self.assertRaises(ValueError):
            validator.validate_learning_disposition(
                repo, {"value": "NO_REUSABLE_LEARNING"}
            )

    def test_empty_rationale_fails_closed(self):
        repo = self.workspace()
        with self.assertRaises(ValueError):
            validator.validate_learning_disposition(
                repo, {"value": "NO_REUSABLE_LEARNING", "rationale": ""}
            )

    def test_unsupported_extra_field_fails_closed(self):
        repo = self.workspace()
        with self.assertRaises(ValueError):
            validator.validate_learning_disposition(
                repo,
                {
                    "value": "NO_REUSABLE_LEARNING",
                    "rationale": "why",
                    "unexpected": True,
                },
            )

    def test_schema_is_a_valid_json_schema(self):
        repo = self.workspace()
        schema = validator.load_json(repo / validator.LEARNING_DISPOSITION_SCHEMA)
        validator.Draft202012Validator.check_schema(schema)

    def test_agents_md_reproducible_and_contains_new_invariants(self):
        repo = self.workspace()
        generator = ROOT / "tools/generate_agents.py"
        proc = subprocess.run(
            [sys.executable, "-B", str(generator), "--repo", str(repo), "--check"],
            capture_output=True, text=True,
        )
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        actual = (repo / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("When acting as the Owner-authorized correction or closure actor", actual)
        self.assertIn("When acting as implementation executor, before material T1/T2 design", actual)
        self.assertIn("When acting as independent auditor, independently derive which promoted lessons", actual)

    def test_not_wired_into_unconditional_traceability_run(self):
        # ADR-014's verification scope boundary: no historical control-decision
        # record is required to carry learning_disposition, and running the
        # unmodified static pipeline against the unmodified repository must
        # not fail merely because control/project-control.yaml lacks the field.
        repo = self.workspace()
        result = validator.ValidationErrorSet()
        registry = validator.scan_artifacts(repo, result)
        validator.validate_traceability(repo, registry, result)
        self.assertFalse(result.errors, result.errors)


if __name__ == "__main__":
    unittest.main()
