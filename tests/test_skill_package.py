from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "project-evolution-engine"
spec = importlib.util.spec_from_file_location("validate_skill", ROOT / "scripts/validate_skill.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class PackageTests(unittest.TestCase):
    def test_installable_metadata_and_reference_graph(self):
        self.assertEqual(validator.validate(SKILL), [])

    def test_broken_reference_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / SKILL.name
            shutil.copytree(SKILL, target)
            (target / "references/integration-analysis.md").unlink()
            self.assertTrue(any("missing link" in e for e in validator.validate(target)))

    def test_outside_reference_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / SKILL.name
            shutil.copytree(SKILL, target)
            with (target / "SKILL.md").open("a") as stream:
                stream.write("\n[external local file](../../outside.md)\n")
            self.assertTrue(any("escapes" in e for e in validator.validate(target)))

    def test_invalid_yaml_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / SKILL.name
            shutil.copytree(SKILL, target)
            (target / "SKILL.md").write_text("---\nname: [invalid\n---\n")
            self.assertTrue(validator.validate(target))

    def test_license_in_package_matches_distribution(self):
        self.assertEqual((ROOT / "LICENSE").read_bytes(), (SKILL / "LICENSE").read_bytes())

    def test_source_lock_points_to_fixed_commits_and_permitted_licenses(self):
        import json
        sources = json.loads((ROOT / "research/sources.lock.json").read_text())
        self.assertEqual(len(sources["sources"]), 8)
        for source in sources["sources"]:
            with self.subTest(repo=source["repository"]):
                self.assertRegex(source["commit"], r"^[0-9a-f]{40}$")
                self.assertEqual(source["license"], "MIT")


if __name__ == "__main__":
    unittest.main()
