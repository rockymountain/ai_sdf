import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("environment_check", ROOT / "tools/check_environment.py")
environment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(environment)


class EnvironmentTests(unittest.TestCase):
    def contract_copy(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        repo = Path(temporary.name)
        for name in (".python-version", "requirements-dev.txt"):
            (repo / name).write_bytes((ROOT / name).read_bytes())
        return repo

    def test_actual_isolated_environment_matches_all_pins_and_imports(self):
        self.assertEqual([], environment.check(ROOT))

    def test_missing_or_malformed_python_declaration_is_detected(self):
        repo = self.contract_copy()
        (repo / ".python-version").unlink()
        self.assertTrue(environment.check(repo, python_only=True))
        (repo / ".python-version").write_text("3.14\n")
        self.assertTrue(environment.check(repo, python_only=True))

    def test_actual_python_mismatch_is_detected(self):
        with patch.object(environment.platform, "python_version", return_value="0.0.0"):
            self.assertTrue(any("!= declared" in error for error in environment.check(ROOT, python_only=True)))

    def test_missing_unpinned_or_duplicate_dependencies_are_detected(self):
        repo = self.contract_copy()
        for content in ("", "PyYAML>=6\n", "PyYAML==6.0.3\npyyaml==6.0.3\n"):
            with self.subTest(content=content):
                (repo / "requirements-dev.txt").write_text(content)
                self.assertTrue(environment.check(repo))

    def test_actual_dependency_mismatch_is_detected(self):
        real_version = environment.metadata.version
        with patch.object(environment.metadata, "version", side_effect=lambda name: "0.0.0" if name == "pyyaml" else real_version(name)):
            errors = environment.check(ROOT)
            self.assertTrue(any("pyyaml 0.0.0 != declared" in error for error in errors), errors)

    def test_global_environment_is_rejected(self):
        with patch.object(environment.sys, "prefix", environment.sys.base_prefix):
            self.assertTrue(any("isolated virtual environment" in error for error in environment.check(ROOT)))

    def test_ci_consumes_repository_runtime_and_dependency_contracts(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/sdf-validation.yml").read_text())
        steps = workflow["jobs"]["deterministic-validation"]["steps"]
        setup = [step for step in steps if step.get("uses", "").startswith("actions/setup-python@")]
        self.assertEqual(1, len(setup))
        self.assertEqual(".python-version", setup[0]["with"]["python-version-file"])
        self.assertNotIn("python-version", setup[0]["with"])
        installs = [step["run"] for step in steps if "pip --isolated install" in step.get("run", "")]
        self.assertEqual(1, len(installs))
        self.assertIn(".venv/bin/python -m pip --isolated install --only-binary=:all: -r requirements-dev.txt", installs[0])
        self.assertIn(".venv/bin/python tools/check_environment.py", installs[0])


if __name__ == "__main__":
    unittest.main()
