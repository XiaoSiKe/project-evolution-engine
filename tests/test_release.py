from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("package_release", SCRIPTS / "package_release.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
install_spec = importlib.util.spec_from_file_location("install_local", SCRIPTS / "install_local.py")
installer = importlib.util.module_from_spec(install_spec)
install_spec.loader.exec_module(installer)


class ReleaseTests(unittest.TestCase):
    def test_archive_is_deterministic_and_contains_installable_files(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / "first.zip", Path(temp) / "second.zip"
            one, two = builder.build(first), builder.build(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(one["sha256"], two["sha256"])
            with zipfile.ZipFile(first) as archive:
                names = archive.namelist()
                self.assertIn("project-evolution-engine/SKILL.md", names)
                self.assertIn("project-evolution-engine/LICENSE", names)
                self.assertIn("project-evolution-engine/THIRD_PARTY_NOTICES.md", names)
                self.assertTrue(all(n.startswith("project-evolution-engine/") for n in names))
                self.assertFalse(any("__pycache__" in n or n.endswith(".pyc") for n in names))
                self.assertEqual(archive.testzip(), None)
                installed = installer.source_files()
                archived = {
                    name.removeprefix(builder.SOURCE.name + "/"): hashlib.sha256(archive.read(name)).hexdigest()
                    for name in names
                }
                self.assertEqual(installed, archived)
            self.assertTrue(Path(str(first) + ".sha256").read_text().startswith(hashlib.sha256(first.read_bytes()).hexdigest()))

    def test_shared_file_selection_skips_caches_and_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            (source / "SKILL.md").write_text("skill\n")
            cache = source / "__pycache__"
            cache.mkdir()
            (cache / "generated.pyc").write_bytes(b"cache")
            (source / "ignored.pyc").write_bytes(b"cache")
            self.assertEqual([source / "SKILL.md"], builder.iter_skill_files(source))

            (source / "linked.md").symlink_to(source / "SKILL.md")
            with self.assertRaisesRegex(ValueError, "symlink"):
                builder.iter_skill_files(source)

    def test_existing_outputs_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "release.zip"
            path.write_bytes(b"existing archive")
            with self.assertRaises(ValueError):
                builder.build(path)
            self.assertEqual(path.read_bytes(), b"existing archive")

    def test_output_inside_source_is_rejected(self):
        with self.assertRaises(ValueError):
            builder.build(builder.SOURCE / "nested" / "release.zip")


if __name__ == "__main__":
    unittest.main()
