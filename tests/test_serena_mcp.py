from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "project-evolution-engine/scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("serena_mcp", SCRIPTS / "serena_mcp.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class SerenaBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "project"
        self.root.mkdir()
        (self.root / "owner.py").write_text("def owner(): return 1\n")
        self.schemas = {"find_symbol": {"properties": {"relative_path": {"type": "string"},
                                                       "name_path_pattern": {"type": "string"},
                                                       "include_body": {"type": "boolean"}},
                                         "required": ["name_path_pattern"]}}

    def test_state_is_external_and_has_required_server_configuration(self):
        before = list(self.root.iterdir())
        root, state = bridge.prepare_state(self.root, self.base / "state")
        data = json.loads((state / "serena_config.yml").read_text())
        self.assertEqual(data["projects"], [])
        self.assertEqual(data["project_serena_folder_location"], str(state / "project"))
        self.assertTrue((state / "project").is_dir())
        self.assertEqual(list(self.root.iterdir()), before)
        self.assertEqual(bridge.prepare_state(self.root, state), (root, state))

    def test_reusing_state_for_another_root_is_rejected_even_with_same_basename(self):
        bridge.prepare_state(self.root, self.base / "state")
        other = self.base / "other/project"
        other.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "different project"):
            bridge.prepare_state(other, self.base / "state")

    def test_unmanaged_state_and_project_local_state_are_preserved(self):
        state = self.base / "state"
        state.mkdir()
        (state / "existing").write_text("user configuration")
        with self.assertRaisesRegex(ValueError, "unmanaged"):
            bridge.prepare_state(self.root, state)
        self.assertEqual((state / "existing").read_text(), "user configuration")
        with self.assertRaises(ValueError):
            bridge.prepare_state(self.root, self.root / "state")

    def test_reuse_recreates_missing_external_project_folder_without_fallback(self):
        _, state = bridge.prepare_state(self.root, self.base / "state")
        (state / "project").rmdir()
        (self.root / ".serena").mkdir()
        (self.root / ".serena/project.yml").write_text("user configuration")
        bridge.prepare_state(self.root, state)
        self.assertTrue((state / "project").is_dir())
        self.assertEqual((self.root / ".serena/project.yml").read_text(), "user configuration")

    def test_missing_or_redirected_configuration_is_not_replaced_with_unsafe_defaults(self):
        _, state = bridge.prepare_state(self.root, self.base / "state")
        configuration = state / "serena_config.yml"
        original = configuration.read_text()
        configuration.unlink()
        with self.assertRaises(ValueError):
            bridge.prepare_state(self.root, state)
        configuration.write_text(original.replace(str(state / "project"), str(self.root / ".serena")))
        with self.assertRaises(ValueError):
            bridge.prepare_state(self.root, state)
        self.assertFalse((self.root / ".serena").exists())

    def test_log_symlink_does_not_truncate_a_project_file(self):
        _, state = bridge.prepare_state(self.root, self.base / "state")
        target = self.root / "owner.py"
        original = target.read_bytes()
        (state / "last-server.log").symlink_to(target)
        with self.assertRaises(ValueError):
            bridge.prepare_state(self.root, state)
        with self.assertRaises(ValueError), bridge.server_log(state):
            pass
        self.assertEqual(target.read_bytes(), original)

    def test_log_replacement_does_not_truncate_an_external_hardlink(self):
        _, state = bridge.prepare_state(self.root, self.base / "state")
        target = self.root / "owner.py"
        original = target.read_bytes()
        os.link(target, state / "last-server.log")
        with bridge.server_log(state) as logs:
            logs.write("new server log")
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual((state / "last-server.log").read_text(), "new server log")

    def test_symbol_query_is_checked_against_current_schema(self):
        request = {"tool": "find_symbol", "arguments": {"relative_path": "owner.py", "name_path_pattern": "owner", "include_body": True}}
        bridge.validate_request(request, self.root, self.schemas)
        for arguments in ({"name_path_pattern": "owner", "unknown": 1}, {}, {"name_path_pattern": 3}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                bridge.validate_request({"tool": "find_symbol", "arguments": arguments}, self.root, self.schemas)

    def test_write_switch_and_unavailable_tools_are_rejected(self):
        for name in ("replace_symbol_body", "activate_project", "get_symbols_overview"):
            with self.subTest(tool=name), self.assertRaises(ValueError):
                bridge.validate_request({"tool": name, "arguments": {}}, self.root, self.schemas)

    def test_escaping_and_symlink_query_paths_are_rejected(self):
        (self.root / "alias.py").symlink_to(self.root / "owner.py")
        for path in ("../other.py", "/absolute.py", "alias.py"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                bridge.validate_request({"tool": "find_symbol", "arguments": {"name_path_pattern": "owner", "relative_path": path}},
                                        self.root, self.schemas)

    def test_absent_optional_runtime_reports_failure_without_project_writes(self):
        run = subprocess.run([sys.executable, str(SCRIPTS / "serena_mcp.py"), "--root", str(self.root),
                              "--state-dir", str(self.base / "state"), "--serena", str(self.base / "absent-serena"), "--describe"],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertFalse(json.loads(run.stdout)["connected"])
        self.assertEqual([p.name for p in self.root.iterdir()], ["owner.py"])


if __name__ == "__main__":
    unittest.main()
