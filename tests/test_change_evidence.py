from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "project-evolution-engine/scripts/change_evidence.py"
spec = importlib.util.spec_from_file_location("change_evidence", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "owner.py").write_text("def export_one():\n    return 1\n")
        (self.root / "caller.py").write_text("from owner import export_one\n")
        self.record = {
            "schema_version": 1,
            "goals": [{"id": "export", "change": "Add batch export", "preserved": ["single export"],
                       "owners": ["owner.py"], "consumers": ["caller.py"], "checks": ["suite"]}],
            "files": [{"path": "owner.py", "role": "owner", "anchor": "def export_one("},
                      {"path": "caller.py", "role": "consumer"}],
            "checks": [{"id": "suite", "kinds": ["new", "integration", "preserved"],
                        "command": "python -m unittest", "status": "not-run", "reason": "before implementation"}],
            "unknowns": ["External consumers have not been inspected"],
        }

    def test_stamp_is_read_only_and_does_not_modify_input(self):
        original = copy.deepcopy(self.record)
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        stamped = module.stamp(self.record, self.root)
        self.assertEqual(self.record, original)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        self.assertEqual(stamped["basis"]["owner.py"]["anchor"]["line"], 1)

    def test_current_evidence_still_reports_unrun_checks_and_unknowns(self):
        result = module.check_record(module.stamp(self.record, self.root), self.root)
        self.assertEqual(result["freshness"], "current")
        self.assertEqual(result["verification_gaps"], ["suite: not-run"])
        self.assertEqual(result["unknowns"], self.record["unknowns"])

    def test_declared_consumer_change_stales_evidence(self):
        stamped = module.stamp(self.record, self.root)
        (self.root / "caller.py").write_text("from owner import export_one\nexport_one()\n")
        result = module.check_record(stamped, self.root)
        self.assertEqual(result["freshness"], "stale")
        self.assertEqual(result["changed_files"], ["caller.py"])

    def test_unrelated_file_does_not_stale_declared_evidence(self):
        stamped = module.stamp(self.record, self.root)
        (self.root / "unrelated.txt").write_text("new")
        self.assertEqual(module.check_record(stamped, self.root)["freshness"], "current")

    def test_new_undeclared_caller_is_an_explicit_limitation(self):
        stamped = module.stamp(self.record, self.root)
        (self.root / "new_caller.py").write_text("from owner import export_one\n")
        result = module.check_record(stamped, self.root)
        self.assertEqual(result["freshness"], "current")
        self.assertTrue(any("undeclared" in text for text in result["limitations"]))

    def test_planned_file_creation_stales_the_plan(self):
        self.record["files"].append({"path": "batch.py", "role": "planned"})
        self.record["goals"][0]["owners"].append("batch.py")
        stamped = module.stamp(self.record, self.root)
        (self.root / "batch.py").write_text("def batch(): pass\n")
        self.assertIn("batch.py", module.check_record(stamped, self.root)["changed_files"])

    def test_removed_and_ambiguous_anchors_are_not_current(self):
        stamped = module.stamp(self.record, self.root)
        (self.root / "owner.py").write_text("def renamed(): pass\n")
        self.assertEqual(module.check_record(stamped, self.root)["anchor_issues"], ["owner.py"])
        (self.root / "owner.py").write_text("def export_one(): pass\ndef export_one(): pass\n")
        with self.assertRaises(ValueError):
            module.stamp(self.record, self.root)

    def test_missing_current_owner_is_rejected_but_later_deletion_is_stale(self):
        stamped = module.stamp(self.record, self.root)
        (self.root / "owner.py").unlink()
        self.assertEqual(module.check_record(stamped, self.root)["freshness"], "stale")
        with self.assertRaises(ValueError):
            module.stamp(self.record, self.root)

    def test_symlink_and_traversal_evidence_is_rejected(self):
        (self.root / "alias.py").symlink_to(self.root / "owner.py")
        for path in ("../outside", "/absolute", "a/../b", "a//b", "alias.py"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                module.safe_path(self.root, path)

    def test_broken_goal_links_and_missing_baseline_are_rejected(self):
        bad = copy.deepcopy(self.record)
        bad["goals"][0]["owners"] = ["unknown.py"]
        with self.assertRaises(ValueError):
            module.stamp(bad, self.root)
        with self.assertRaises(ValueError):
            module.check_record(self.record, self.root)

    def test_passed_status_requires_consistent_evidence(self):
        check = self.record["checks"][0]
        check["status"] = "passed"
        with self.assertRaises(ValueError):
            module.stamp(self.record, self.root)
        check["evidence"] = "Observed test output"
        check["exit_code"] = 1
        with self.assertRaises(ValueError):
            module.stamp(self.record, self.root)
        check["exit_code"] = 0
        result = module.check_record(module.stamp(self.record, self.root), self.root)
        self.assertEqual(result["verification_gaps"], [])

    def test_missing_compatibility_coverage_is_visible(self):
        self.record["checks"][0]["kinds"] = ["new"]
        result = module.check_record(module.stamp(self.record, self.root), self.root)
        self.assertTrue(any("integration, preserved" in text for text in result["verification_gaps"]))

    def test_malformed_basis_is_rejected(self):
        stamped = module.stamp(self.record, self.root)
        stamped["basis"]["owner.py"]["sha256"] = "fake"
        with self.assertRaises(ValueError):
            module.check_record(stamped, self.root)

    def test_cli_stdin_and_exit_codes(self):
        stamp = subprocess.run([sys.executable, str(SCRIPT), "stamp", "--root", str(self.root), "--record", "-"],
                               input=json.dumps(self.record), capture_output=True, text=True)
        self.assertEqual(stamp.returncode, 0, stamp.stdout)
        (self.root / "caller.py").write_text("changed\n")
        check = subprocess.run([sys.executable, str(SCRIPT), "check", "--root", str(self.root), "--record", "-"],
                               input=stamp.stdout, capture_output=True, text=True)
        self.assertEqual(check.returncode, 1)
        self.assertEqual(json.loads(check.stdout)["freshness"], "stale")


if __name__ == "__main__":
    unittest.main()
