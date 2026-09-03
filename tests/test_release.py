from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package_release", ROOT / "scripts/package_release.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


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
            self.assertTrue(Path(str(first) + ".sha256").read_text().startswith(hashlib.sha256(first.read_bytes()).hexdigest()))

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
