from __future__ import annotations

import importlib.util
import json
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
    def test_non_mapping_ui_sections_produce_validation_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / SKILL.name
            shutil.copytree(SKILL, target)
            path = target / "agents/openai.yaml"
            original = validator.yaml.safe_load(path.read_text())
            for field in ("interface", "policy"):
                for value in (None, [], True, 1, "invalid"):
                    with self.subTest(field=field, value=value):
                        path.write_text(json.dumps({**original, field: value}))
                        errors = validator.validate(target)
                        self.assertIn(f"{field} must be a mapping", errors)

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
        sources = json.loads((ROOT / "research/sources.lock.json").read_text())
        repositories = [source["repository"] for source in sources["sources"]]
        self.assertTrue(repositories)
        self.assertEqual(len(repositories), len(set(repositories)))
        for source in sources["sources"]:
            with self.subTest(repo=source["repository"]):
                self.assertEqual(set(source), {"repository", "commit", "license", "reference"})
                self.assertRegex(source["commit"], r"^[0-9a-f]{40}$")
                self.assertEqual(source["license"], "MIT")
                self.assertTrue(source["reference"])

        notices = (SKILL / "THIRD_PARTY_NOTICES.md").read_text()
        self.assertEqual(notices.count("Permission is hereby granted"), 1)
        for source in sources["sources"]:
            with self.subTest(notice=source["repository"]):
                self.assertIn(source["repository"], notices)
                self.assertIn(source["commit"], notices)


if __name__ == "__main__":
    unittest.main()
