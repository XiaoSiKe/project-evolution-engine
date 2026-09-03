from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("eval_cases", ROOT / "scripts/eval_cases.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class EvalCaseTests(unittest.TestCase):
    def setUp(self):
        self.cases = runner.load_cases()
        self.contract = runner.load_contract()

    def test_catalog_has_valid_paths_and_contract(self):
        self.assertEqual(runner.validate_cases(self.cases, self.contract), [])
        self.assertEqual(len(self.cases), 7)

    def test_unsafe_paths_are_rejected(self):
        for path in ("../escape", "/absolute", "a/../b", "a//b", "a\\b", ""):
            with self.subTest(path=path), self.assertRaises(ValueError):
                runner.safe_relative_path(path)

    def test_invalid_case_metadata_is_rejected(self):
        cases = copy.deepcopy(self.cases)
        cases[0]["expected"]["routes"] = ["invented-server"]
        cases[0]["files"]["../escape"] = "bad"
        self.assertTrue(runner.validate_cases(cases, self.contract))

    def test_materialization_excludes_answers_and_starts_with_no_net_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            for index, case in enumerate(self.cases):
                target = Path(temp) / str(index)
                result = runner.materialize(case, target)
                self.assertNotIn("expected", result)
                self.assertNotIn("oracle", result)
                self.assertEqual(runner.workspace_changed_paths(case, target), [])
                self.assertFalse((target / "result-contract.json").exists())

    def test_dirty_baseline_is_user_state_not_original_commit(self):
        case = runner.case_by_id(self.cases, "dirty-worktree")
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "fixture"
            runner.materialize(case, target)
            self.assertEqual(runner.workspace_changed_paths(case, target), [])
            (target / "notes.txt").write_text(case["files"]["notes.txt"])
            self.assertEqual(runner.workspace_changed_paths(case, target), ["notes.txt"])

    def test_materialization_refuses_nonempty_and_symlink_targets(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "nonempty"
            target.mkdir()
            (target / "keep").write_text("user")
            with self.assertRaises(ValueError):
                runner.materialize(self.cases[0], target)
            empty = Path(temp) / "empty"
            empty.mkdir()
            link = Path(temp) / "link"
            link.symlink_to(empty, target_is_directory=True)
            with self.assertRaises(ValueError):
                runner.materialize(self.cases[0], link)
            self.assertEqual((target / "keep").read_text(), "user")
            self.assertEqual(list(empty.iterdir()), [])

    def test_reports_are_reconciled_against_actual_changes(self):
        case = self.cases[0]
        expected = case["expected"]
        result = {key: expected[key] for key in ("gate", "mutation", "routes", "paused", "claims_full_correctness")}
        result.update(changed_files=[], verification=expected["required_verification"])
        errors = runner.validate_result(case, result, ["app/exporter.py"])
        self.assertTrue(any("unreported" in e for e in errors))
        result["changed_files"] = ["app/exporter.py", "README.md", "tests/test_exporter.py"]
        self.assertEqual(runner.validate_result(case, result, result["changed_files"]), [])
        self.assertTrue(runner.validate_result(case, result, result["changed_files"] + ["app/policy.py"]))

    def test_every_oracle_rejects_the_unchanged_project(self):
        with tempfile.TemporaryDirectory() as temp:
            for index, case in enumerate(self.cases):
                with self.subTest(case=case["id"]):
                    target = Path(temp) / str(index)
                    runner.materialize(case, target)
                    outcome = runner.verify_behavior(case["id"], target)
                    self.assertFalse(outcome["ok"])
                    self.assertEqual(runner.workspace_changed_paths(case, target), [])

    def test_full_suite_evidence_satisfies_focused_test_requirement(self):
        case = self.cases[0]
        expected = case["expected"]
        result = {key: expected[key] for key in ("gate", "mutation", "routes", "paused", "claims_full_correctness")}
        result.update(changed_files=expected["required_changed_paths"], verification=["baseline", "broader-tests", "diff"])
        self.assertEqual(runner.validate_result(case, result, result["changed_files"]), [])

    def test_generated_files_require_the_canonical_source(self):
        case = runner.case_by_id(self.cases, "generated-source")
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "fixture"
            runner.materialize(case, target)
            (target / "app/statuses.py").write_text(
                "# generated; do not edit\nVALID_STATUSES = ('queued', 'running', 'done', 'cancelled')\n"
            )
            self.assertFalse(runner.verify_behavior(case["id"], target)["ok"])

    def test_baseline_tests_are_executable(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as temp:
            for index, case in enumerate(self.cases):
                with self.subTest(case=case["id"]):
                    target = Path(temp) / str(index)
                    runner.materialize(case, target)
                    result = subprocess.run(
                        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                        cwd=target, text=True, capture_output=True, timeout=30,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
