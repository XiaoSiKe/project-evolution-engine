from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "project-evolution-engine" / "scripts" / "collect_evidence.py"


def load_module():
    spec = importlib.util.spec_from_file_location("collect_evidence", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load collect_evidence")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


def run_git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )


def initialize_repository(root: Path) -> None:
    run_git(root, "init", "-b", "main")
    run_git(root, "add", ".")
    run_git(
        root,
        "-c",
        "user.name=Convergence Tests",
        "-c",
        "user.email=tests@example.invalid",
        "commit",
        "-m",
        "fixture baseline",
    )


class CollectEvidenceTests(unittest.TestCase):
    def test_subproject_fingerprint_excludes_sibling_worktree_changes(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inside = root / "inside"
            outside = root / "outside"
            inside.mkdir()
            outside.mkdir()
            (inside / "app.py").write_text("value = 1\n")
            (outside / "other.py").write_text("value = 1\n")
            initialize_repository(root)
            before = module.collect_evidence(inside)
            (outside / "other.py").write_text("value = 2\n")
            (outside / "new.txt").write_text("unrelated\n")
            after = module.collect_evidence(inside)
            self.assertEqual(before["git"]["worktree_fingerprint"], after["git"]["worktree_fingerprint"])
            self.assertFalse(after["git"]["dirty"])
            (inside / "app.py").write_text("value = 2\n")
            self.assertNotEqual(before["git"]["worktree_fingerprint"], module.collect_evidence(inside)["git"]["worktree_fingerprint"])

    def test_collects_inventory_commands_and_git_without_writing(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            files = {
                ".github/workflows/validate.yml": "name: Validate\n",
                ".gitignore": "__pycache__/\n",
                "AGENTS.md": "docs/generated.md is generated; do not edit it manually.\n",
                "agents/openai.yaml": "interface:\n  display_name: Example\n",
                "CONTEXT.md": "# Domain\n",
                "docs/adr/0001-example.md": "# Accepted decision\n",
                "docs/generated.md": "<!-- generated; do not edit -->\n",
                "docs/prose.md": ("ordinary explanation\n" * 8) + "The phrase do not edit is discussed here.\n",
                "package.json": json.dumps({"scripts": {"test": "python3 -m unittest"}}),
                "Makefile": "lint:\n\tpython3 -m compileall src\n",
                "schema/api.json": "{}\n",
                "references/finding.schema.json": "{}\n",
                "migrations/001.sql": "select 1;\n",
                "src/app.py": "VALUE = 1\n",
                "scripts/generate.py": "TARGET = '<!-- generated; do not edit -->'\n",
                "tests/test_app.py": "# test\n",
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            before = snapshot(root)
            evidence = module.collect_evidence(root)

            self.assertEqual(before, snapshot(root))
            self.assertIn("AGENTS.md", evidence["inventory"]["instruction_files"])
            self.assertIn("CONTEXT.md", evidence["inventory"]["domain_files"])
            self.assertIn("docs/adr/0001-example.md", evidence["inventory"]["adr_files"])
            self.assertIn("docs/generated.md", evidence["inventory"]["generated_files"])
            self.assertNotIn("docs/prose.md", evidence["inventory"]["generated_files"])
            self.assertNotIn("AGENTS.md", evidence["inventory"]["generated_files"])
            self.assertNotIn("scripts/generate.py", evidence["inventory"]["generated_files"])
            self.assertIn("schema/api.json", evidence["inventory"]["schema_files"])
            self.assertIn("references/finding.schema.json", evidence["inventory"]["schema_files"])
            self.assertIn("agents/openai.yaml", evidence["inventory"]["config_files"])
            self.assertIn(".github/workflows/validate.yml", evidence["inventory"]["config_files"])
            self.assertIn(".gitignore", evidence["inventory"]["config_files"])
            self.assertIn("migrations/001.sql", evidence["inventory"]["migration_files"])
            self.assertIn("tests/test_app.py", evidence["inventory"]["test_files"])
            self.assertIn("npm run test", evidence["available_commands"])
            self.assertIn("make lint", evidence["available_commands"])
            self.assertEqual(2, evidence["schema_version"])
            self.assertFalse(evidence["git"]["is_repository"])
            self.assertIsNone(evidence["git"]["head"])
            self.assertIsNone(evidence["git"]["branch"])
            self.assertFalse(evidence["git"]["dirty"])
            self.assertIsNone(evidence["git"]["worktree_fingerprint"])
            self.assertIsNone(evidence["git"]["fingerprint_method"])

    def test_skips_symlinks_instead_of_reading_outside_root(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            outside = Path(temp_dir) / "outside.md"
            outside.write_text("secret\n", encoding="utf-8")
            (root / "linked.md").symlink_to(outside)

            evidence = module.collect_evidence(root)

            self.assertEqual(["linked.md"], evidence["coverage"]["skipped_symlinks"])
            self.assertNotIn("linked.md", evidence["inventory"]["markdown_files"])

    def test_git_fingerprint_is_stable_and_tracks_visible_content(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tracked = root / "app.py"
            tracked.write_text("VALUE = 1\n", encoding="utf-8")
            (root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
            initialize_repository(root)

            before = snapshot(root)
            first = module.collect_evidence(root)
            repeated = module.collect_evidence(root)

            self.assertEqual(before, snapshot(root))
            self.assertEqual(first["git"]["worktree_fingerprint"], repeated["git"]["worktree_fingerprint"])
            self.assertRegex(first["git"]["worktree_fingerprint"], r"^sha256:[0-9a-f]{64}$")
            self.assertEqual("git-head+binary-diff+untracked-content-v1", first["git"]["fingerprint_method"])
            self.assertEqual("main", first["git"]["branch"])
            self.assertRegex(first["git"]["head"], r"^[0-9a-f]{40}$")
            self.assertFalse(first["git"]["dirty"])

            tracked.write_text("VALUE = 2\n", encoding="utf-8")
            tracked_change = module.collect_evidence(root)
            self.assertNotEqual(first["git"]["worktree_fingerprint"], tracked_change["git"]["worktree_fingerprint"])
            self.assertTrue(tracked_change["git"]["dirty"])

            tracked.write_text("VALUE = 1\n", encoding="utf-8")
            untracked = root / "new.py"
            untracked.write_text("NEW = 1\n", encoding="utf-8")
            untracked_first = module.collect_evidence(root)
            untracked.write_text("NEW = 2\n", encoding="utf-8")
            untracked_second = module.collect_evidence(root)
            self.assertNotEqual(
                untracked_first["git"]["worktree_fingerprint"],
                untracked_second["git"]["worktree_fingerprint"],
            )

    def test_ignored_content_does_not_change_fingerprint(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
            initialize_repository(root)

            baseline = module.collect_evidence(root)
            ignored = root / "ignored.txt"
            ignored.write_text("first\n", encoding="utf-8")
            first = module.collect_evidence(root)
            ignored.write_text("second\n", encoding="utf-8")
            second = module.collect_evidence(root)

            self.assertEqual(baseline["git"]["worktree_fingerprint"], first["git"]["worktree_fingerprint"])
            self.assertEqual(first["git"]["worktree_fingerprint"], second["git"]["worktree_fingerprint"])
            self.assertFalse(second["git"]["dirty"])
            self.assertTrue(any("ignored files" in item for item in second["limitations"]))

    def test_unborn_repository_fingerprint_uses_current_files(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_git(root, "init", "-b", "main")
            source = root / "app.py"
            source.write_text("VALUE = 1\n", encoding="utf-8")

            first = module.collect_evidence(root)
            source.write_text("VALUE = 2\n", encoding="utf-8")
            second = module.collect_evidence(root)

            self.assertIsNone(first["git"]["head"])
            self.assertEqual("main", first["git"]["branch"])
            self.assertRegex(first["git"]["worktree_fingerprint"], r"^sha256:[0-9a-f]{64}$")
            self.assertNotEqual(first["git"]["worktree_fingerprint"], second["git"]["worktree_fingerprint"])
