from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("repeated_project_eval", ROOT / "scripts/repeated_project_eval.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RepeatedEvaluationTests(unittest.TestCase):
    def test_changed_baseline_record_or_upstream_source_is_rejected_before_verification(self):
        for changed_input in ("record", "upstream"):
            with self.subTest(changed_input=changed_input), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                original, app, artifacts, data = [root / name for name in ("original", "app", "artifacts", "data")]
                for path in (original / "tests", artifacts, data):
                    path.mkdir(parents=True)
                (original / "app.py").write_text("VALUE = 0\n")
                (original / "tests/test_old.py").write_text("assert True\n")
                runner.copy_source(original, app)
                before = runner.snapshot(app)
                runner.write_json(artifacts / "baseline.json", before)
                runner.write_json(data / "cases.json", [{"id": "httpx-probe", "allowed_changes": ["**"],
                    "protected": [], "upstream_tests": ["tests/test_old.py"]}])
                trial = {"id": 1, "case": "httpx-probe", "condition": "baseline", "round": 1,
                    "application": str(app), "artifacts": str(artifacts), "python": sys.executable,
                    "baseline_sha256": runner.tree_digest(before)}
                if changed_input == "record":
                    runner.write_json(artifacts / "baseline.json", {**before, "app.py": "0" * 64})
                else:
                    (original / "tests/test_old.py").write_text("assert False\n")
                manifest = {"source_roots": {"httpx": str(original)}}
                with patch.object(runner, "DATA", data), patch.object(runner, "check_frozen"), \
                        patch.object(runner, "invoke", side_effect=AssertionError("stale input reached verification")) as invoked:
                    with self.assertRaisesRegex(ValueError, "baseline|upstream"):
                        runner.evaluate(manifest, trial)
                    invoked.assert_not_called()
                self.assertFalse((artifacts / "verification-application").exists())

    def test_changed_application_is_rejected_before_starting_a_coding_trial(self):
        with tempfile.TemporaryDirectory() as temp:
            app, artifacts = Path(temp) / "app", Path(temp) / "artifacts"
            app.mkdir()
            artifacts.mkdir()
            source = app / "app.py"
            source.write_text("VALUE = 0\n")
            before = runner.snapshot(app)
            runner.write_json(artifacts / "baseline.json", before)
            (artifacts / "prompt.txt").write_text("fixed request")
            source.write_text("VALUE = 1\n")
            trial = {"application": str(app), "artifacts": str(artifacts), "baseline_sha256": runner.tree_digest(before)}
            manifest = {"configured_model": {}, "cli": sys.executable, "schema": str(artifacts / "schema.json")}
            with patch.object(runner, "check_frozen"), patch.object(runner, "configuration", return_value={}), \
                    patch.object(runner.subprocess, "Popen", side_effect=AssertionError("unexpected coding run")) as launched:
                with self.assertRaisesRegex(ValueError, "baseline|application"):
                    runner.run_trial(manifest, trial)
                launched.assert_not_called()
            self.assertFalse((artifacts / "events.jsonl").exists())

    def test_usage_is_observed_not_inferred_and_started_commands_are_not_double_counted(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            events = [
                {"type": "item.started", "item": {"type": "command_execution", "id": "a", "command": "python -m unittest"}},
                {"type": "item.completed", "item": {"type": "command_execution", "id": "a", "command": "python -m unittest", "exit_code": 0}},
                {"type": "item.completed", "item": {"type": "reasoning", "text": "private reasoning"}},
                {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 70, "output_tokens": 20, "reasoning_output_tokens": 12}},
            ]
            path.write_text("\n".join(json.dumps(e) for e in events))
            result = runner.parse_events(path)
            self.assertEqual(result["command_count"], 1)
            self.assertEqual(result["usage"]["input_tokens"], 100)
            self.assertEqual(result["usage"]["output_tokens"], 20)
            self.assertNotIn("private reasoning", json.dumps(result))

    def test_missing_usage_remains_unavailable_and_errors_remain_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            path.write_text('{"type":"turn.failed","error":"interrupted"}\n')
            result = runner.parse_events(path)
            self.assertIsNone(result["usage"])
            self.assertEqual(len(result["errors"]), 1)

    def test_source_symlink_is_not_silently_omitted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "file.py").write_text("pass\n")
            (root / "alias.py").symlink_to(root / "file.py")
            with self.assertRaises(ValueError):
                runner.snapshot(root)

    def test_changed_frozen_tasks_or_skill_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data, skill = root / "data", root / "skill"
            data.mkdir()
            skill.mkdir()
            (data / "cases.json").write_text("[]")
            (skill / "SKILL.md").write_text("fixed input")
            import hashlib
            manifest = {"frozen_evaluators": {"cases.json": hashlib.sha256(b"[]").hexdigest()},
                        "skill": str(skill), "skill_files": runner.snapshot(skill)}
            with patch.object(runner, "DATA", data):
                runner.check_frozen(manifest)
                (skill / "SKILL.md").write_text("changed input")
                with self.assertRaises(ValueError):
                    runner.check_frozen(manifest)
                (skill / "SKILL.md").write_text("fixed input")
                (data / "cases.json").write_text("[1]")
                with self.assertRaises(ValueError):
                    runner.check_frozen(manifest)

    def test_upstream_test_overlay_checks_candidate_import_without_mutating_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, app, artifacts, data = [root / name for name in ("original", "application", "artifacts", "data")]
            for path in (original / "sample", original / "tests", artifacts, data):
                path.mkdir(parents=True)
            (original / "sample/__init__.py").write_text("from pathlib import Path\nVALUE = 0\nLOCATION = Path(__file__).resolve().parents[1]\n")
            (original / "tests/__init__.py").write_text("")
            (original / "tests/test_origin.py").write_text(
                "import unittest\nfrom pathlib import Path\nimport sample\nclass OriginTest(unittest.TestCase):\n"
                "    def test_import(self):\n        self.assertEqual(sample.LOCATION, Path.cwd())\n"
                "        self.assertGreaterEqual(sample.VALUE, 0)\n")
            runner.copy_source(original, app)
            before = runner.snapshot(app)
            runner.write_json(artifacts / "baseline.json", before)
            (app / "sample/__init__.py").write_text((app / "sample/__init__.py").read_text().replace("VALUE = 0", "VALUE = 1"))
            (app / "tests/test_origin.py").write_text("raise AssertionError('candidate cannot replace upstream regression')\n")
            after = runner.snapshot(app)
            changed = sorted(path for path in before if before[path] != after[path])
            runner.write_json(artifacts / "report.json", {"status": "completed", "changed_files": changed, "questions": []})
            runner.write_json(artifacts / "execution.json", {"exit_code": 0})
            case = {"id": "httpx-probe", "upstream_tests": ["tests/test_origin.py"],
                    "allowed_changes": ["sample/**/*.py", "tests/**/*.py"], "protected": []}
            runner.write_json(data / "cases.json", [case])
            (data / "httpx_oracle.py").write_text(
                "import json, sample\nprint(json.dumps({'checks':[{'passed':sample.VALUE == 1}]}))\n"
                "raise SystemExit(0 if sample.VALUE == 1 else 1)\n")
            manifest = {"source_roots": {"httpx": str(original)}}
            trial = {"id": 1, "case": "httpx-probe", "condition": "baseline", "round": 1,
                     "artifacts": str(artifacts), "application": str(app), "python": sys.executable,
                     "baseline_sha256": runner.tree_digest(before)}
            real_invoke = runner.invoke

            def stdlib_test_command(argv, cwd, env=None, timeout=180):
                if argv[1:3] == ["-m", "pytest"]:
                    argv = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_origin.py", "-t", "."]
                return real_invoke(argv, cwd, env, timeout)

            with patch.object(runner, "DATA", data), patch.object(runner, "check_frozen"), patch.object(runner, "invoke", stdlib_test_command):
                result = runner.evaluate(manifest, trial)
            self.assertTrue(result["passed"], result)
            self.assertEqual(runner.snapshot(app), after)
            self.assertEqual((artifacts / "verification-application/tests/test_origin.py").read_bytes(),
                             (original / "tests/test_origin.py").read_bytes())


if __name__ == "__main__":
    unittest.main()
