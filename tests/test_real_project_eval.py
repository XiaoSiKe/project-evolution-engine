from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("real_project_eval", ROOT / "scripts/real_project_eval.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class PublicPilotTests(unittest.TestCase):
    def test_pinned_fixture_bytes_match_the_registered_snapshots(self):
        for case in json.loads((runner.DATA / "cases.json").read_text()):
            fixture = runner.DATA / case["fixture"]
            digest = hashlib.sha256()
            for name in sorted(runner.files(fixture)):
                digest.update(name.encode() + b"\0" + (fixture / name).read_bytes() + b"\0")
            self.assertEqual(digest.hexdigest(), case["fixture_sha256"], case["id"])

    def test_sources_have_fixed_commits_and_retained_notices(self):
        sources = json.loads((runner.DATA / "sources.lock.json").read_text())
        self.assertEqual({s["license"] for s in sources}, {"MIT", "BSD-3-Clause"})
        for source in sources:
            self.assertRegex(source["commit"], r"^[0-9a-f]{40}$")
        notice = (runner.DATA / "THIRD_PARTY_NOTICES.md").read_text()
        self.assertIn("Pallets", notice)
        self.assertIn("Addy Osmani", notice)

    def test_published_patches_reconstruct_the_evaluated_files(self):
        release = ROOT / "evals/results/v0.2.0"
        outcomes = json.loads((release / "results.json").read_text())
        cases = {c["id"]: c for c in json.loads((runner.DATA / "cases.json").read_text())}
        with tempfile.TemporaryDirectory() as temp:
            for trial in outcomes["trials"]:
                with self.subTest(trial=trial["id"]):
                    patch_path = release / trial["patch"]
                    self.assertEqual(hashlib.sha256(patch_path.read_bytes()).hexdigest(), trial["patch_sha256"])
                    target = Path(temp) / str(trial["id"])
                    shutil.copytree(runner.DATA / cases[trial["case"]]["fixture"], target,
                                    ignore=shutil.ignore_patterns(*runner.EXCLUDED, "*.pyc"))
                    subprocess.run(["git", "apply", str(patch_path)], cwd=target,
                                   capture_output=True, check=True)
                    self.assertEqual(runner.files(target), trial["source_files_after"])

    def test_prepare_preserves_virtualenv_execution_context_and_equal_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            environment = temp / "venv"
            venv.EnvBuilder(with_pip=False).create(environment)
            python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
            data = temp / "data"
            (data / "node/node_modules/jsdom").mkdir(parents=True)
            rows = []
            for name, identity in (("front", "todomvc-undo"), ("back", "flaskr-drafts")):
                fixture = data / "fixtures" / name
                fixture.mkdir(parents=True)
                (fixture / "app.txt").write_text("same raw input\n")
                (fixture / ".gitignore").write_text("node_modules/\n")
                rows.append({"id": identity, "fixture": f"fixtures/{name}", "request": "add a feature"})
            (data / "cases.json").write_text(json.dumps(rows))
            (data / "result-contract.json").write_text("{}")
            (data / "todomvc_oracle.cjs").write_text("// fixed acceptance")
            (data / "flaskr_oracle.py").write_text("# fixed acceptance")
            with patch.object(runner, "DATA", data):
                result = runner.prepare(temp / "trials", python)
            chosen = result["trials"][0]["python"]
            executed = subprocess.check_output([chosen, "-c", "import sys; print(sys.prefix)"], text=True).strip()
            self.assertEqual(Path(executed).resolve(), environment.resolve())
            front = [Path(t["workspace"]) for t in result["trials"] if t["case"] == "todomvc-undo"]
            self.assertEqual(runner.files(front[0]), runner.files(front[1]))
            self.assertEqual({t["condition"] for t in result["trials"]}, {"baseline", "skill"})
            self.assertEqual(len(result["pre_registered_checks"]), 2)
            self.assertIn("SKILL.md", result["skill_snapshot_files"])

    def test_source_directory_symlinks_cannot_disappear_from_the_diff(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "source").mkdir()
            (root / "source/app.py").write_text("original")
            (root / "linked-source").symlink_to(root / "source", target_is_directory=True)
            with self.assertRaises(ValueError):
                runner.files(root)

    def test_changed_acceptance_checks_require_a_new_trial(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp) / "manifest.json"
            manifest.write_text(json.dumps({"pre_registered_checks": {"fake": "changed"}}))
            with self.assertRaisesRegex(ValueError, "changed or were not frozen"):
                runner.evaluate(manifest, 1)

    def test_passing_behavior_does_not_override_a_false_change_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = root / "trial"
            work.mkdir()
            (work / "app.py").write_text("new capability")
            (root / "baseline-01.json").write_text("{}")
            result = root / "result.json"
            result.write_text(json.dumps({"status": "completed", "changed_files": [], "questions": []}))
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"pre_registered_checks": runner.acceptance_digests(), "trials": [{
                "id": 1, "case": "flaskr-drafts", "condition": "baseline", "workspace": str(work),
                "result": str(result), "python": sys.executable}]}))
            runs = [{"exit_code": 0}, {"exit_code": 0, "stdout": json.dumps({"checks": [{"passed": True}]})}]
            with patch.object(runner, "command", side_effect=runs):
                score = runner.evaluate(manifest, 1)
            self.assertTrue(score["behavior_passed"])
            self.assertFalse(score["report_matches_diff"])
            self.assertFalse(score["passed"])

    def test_preparation_refuses_repository_and_nonempty_destinations(self):
        with self.assertRaises(ValueError):
            runner.prepare(ROOT / "unsafe", Path(sys.executable))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "keep").write_text("user data")
            with self.assertRaises(ValueError):
                runner.prepare(root, Path(sys.executable))
            self.assertEqual((root / "keep").read_text(), "user data")


if __name__ == "__main__":
    unittest.main()
