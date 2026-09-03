from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "install_local.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("install_local", SCRIPT)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@contextmanager
def managed_update():
    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp) / "source"
        source.mkdir()
        (source / "SKILL.md").write_text("old version\n")
        target = installer.validate_target(Path(temp) / "project-evolution-engine")
        with patch.object(installer, "SOURCE", source):
            old = installer.source_files()
            installer.install(target, installer.inspect_target(target, old), old)
            (source / "SKILL.md").write_text("new version\n")
            current = installer.source_files()
            yield target, installer.inspect_target(target, current), current


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class InstallLocalTests(unittest.TestCase):
    def test_update_preserves_hard_linked_backup_outside_target(self) -> None:
        with managed_update() as (target, plan, current):
            backup = target.parent / "backup.md"
            os.link(target / "SKILL.md", backup)
            installer.install(target, plan, current)
            self.assertEqual("new version\n", (target / "SKILL.md").read_text())
            self.assertEqual("old version\n", backup.read_text())
            self.assertEqual("current", installer.inspect_target(target, current)["status"])

    def test_failed_file_copy_preserves_existing_install_without_temporary_residue(self) -> None:
        with managed_update() as (target, plan, current):
            before = {p.name: p.read_bytes() for p in target.iterdir()}

            def interrupted_copy(source, destination):
                Path(destination).write_bytes(b"partial write")
                raise OSError("copy interrupted")

            with patch.object(installer.shutil, "copy2", interrupted_copy):
                with self.assertRaises(OSError):
                    installer.install(target, plan, current)
            self.assertEqual(before, {p.name: p.read_bytes() for p in target.iterdir()})

    def test_install_into_explicit_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "project-evolution-engine"
            target.mkdir()
            self.assertEqual(0, run_cli("--dry-run", "--target", str(target)).returncode)
            self.assertEqual([], list(target.iterdir()))
            self.assertEqual(0, run_cli("--install", "--target", str(target)).returncode)
            self.assertEqual(0, run_cli("--check", "--target", str(target)).returncode)

    def test_recursive_source_target_is_rejected(self) -> None:
        target = PROJECT_ROOT / "project-evolution-engine" / "nested" / "project-evolution-engine"
        result = run_cli("--install", "--target", str(target))
        self.assertEqual(2, result.returncode)
        self.assertFalse(target.exists())

    def test_invalid_manifest_shape_is_reported_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "project-evolution-engine"
            target.mkdir()
            manifest = target / ".project-evolution-engine-install.json"
            manifest.write_text("[]\n")
            result = run_cli("--install", "--target", str(target))
            self.assertEqual(2, result.returncode)
            self.assertEqual("[]\n", manifest.read_text())

    def test_dry_run_never_creates_the_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "project-evolution-engine"
            result = run_cli("--dry-run", "--target", str(target))

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse(target.exists())
            self.assertEqual("missing", json.loads(result.stdout)["status"])

    def test_install_then_check_reports_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "project-evolution-engine"
            installed = run_cli("--install", "--target", str(target))
            checked = run_cli("--check", "--target", str(target))

            self.assertEqual(0, installed.returncode, installed.stderr)
            self.assertEqual(0, checked.returncode, checked.stderr)
            self.assertTrue((target / "SKILL.md").exists())
            self.assertTrue((target / ".project-evolution-engine-install.json").exists())
            self.assertEqual("current", json.loads(checked.stdout)["status"])

    def test_install_refuses_to_overwrite_a_locally_modified_managed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "project-evolution-engine"
            self.assertEqual(0, run_cli("--install", "--target", str(target)).returncode)
            skill_file = target / "SKILL.md"
            skill_file.write_text("local customization\n", encoding="utf-8")

            result = run_cli("--install", "--target", str(target))

            self.assertNotEqual(0, result.returncode)
            self.assertEqual("local customization\n", skill_file.read_text(encoding="utf-8"))

    def test_check_refuses_a_managed_file_replaced_by_an_internal_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "project-evolution-engine"
            self.assertEqual(0, run_cli("--install", "--target", str(target)).returncode)
            skill_file = target / "SKILL.md"
            preserved_copy = target / "local-skill-copy.md"
            preserved_copy.write_bytes(skill_file.read_bytes())
            skill_file.unlink()
            skill_file.symlink_to(preserved_copy.name)

            result = run_cli("--check", "--target", str(target))

            self.assertNotEqual(0, result.returncode)
            self.assertTrue(skill_file.is_symlink())
            self.assertIn("symlink", result.stdout)

    def test_check_refuses_a_symlinked_install_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "project-evolution-engine"
            self.assertEqual(0, run_cli("--install", "--target", str(target)).returncode)
            manifest = target / ".project-evolution-engine-install.json"
            preserved_copy = target / "local-manifest-copy.json"
            preserved_copy.write_bytes(manifest.read_bytes())
            manifest.unlink()
            manifest.symlink_to(preserved_copy.name)

            result = run_cli("--check", "--target", str(target))

            self.assertNotEqual(0, result.returncode)
            self.assertTrue(manifest.is_symlink())
            self.assertIn("manifest must not be a symlink", result.stdout)

    def test_check_refuses_a_symlinked_target_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_target = root / "real" / "project-evolution-engine"
            alias_target = root / "alias" / "project-evolution-engine"
            real_target.parent.mkdir()
            alias_target.parent.mkdir()
            self.assertEqual(0, run_cli("--install", "--target", str(real_target)).returncode)
            alias_target.symlink_to(real_target, target_is_directory=True)

            result = run_cli("--check", "--target", str(alias_target))

            self.assertEqual(2, result.returncode)
            self.assertIn("target directory must not be a symlink", result.stdout)
            self.assertTrue(alias_target.is_symlink())

    def test_install_refuses_an_unmanaged_existing_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "project-evolution-engine"
            target.mkdir()
            (target / "SKILL.md").write_text("legacy\n", encoding="utf-8")

            result = run_cli("--install", "--target", str(target))

            self.assertNotEqual(0, result.returncode)
            self.assertEqual("legacy\n", (target / "SKILL.md").read_text(encoding="utf-8"))

    def test_managed_update_preserves_unmanaged_extra_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "project-evolution-engine"
            self.assertEqual(0, run_cli("--install", "--target", str(target)).returncode)
            extra = target / "local-notes.txt"
            extra.write_text("keep me\n", encoding="utf-8")

            result = run_cli("--install", "--target", str(target))

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("keep me\n", extra.read_text(encoding="utf-8"))
