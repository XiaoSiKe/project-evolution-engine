from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "project-evolution-engine/scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("refresh_context", SCRIPTS / "refresh_context.py")
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)


class ContextRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "src").mkdir()
        (self.root / "src/owner.py").write_text("def quote(value):\n    return value * 2\n")
        (self.root / "src/api.py").write_text("from owner import quote\n\ndef api(value):\n    return quote(value)\n")
        (self.root / "docs.md").write_text("Unrelated naming convention.\n")
        self.draft = {
            "schema_version": 1,
            "queries": [{"id": "quote-users", "include": ["src/**/*.py", "src/*.py"],
                         "terms": ["quote"], "match": "identifier"}],
            "facts": [
                {"id": "quote-rule", "kind": "implementation", "statement": "quote owns the rule",
                 "evidence": [{"path": "src/owner.py", "anchor": "def quote("}],
                 "queries": ["quote-users"], "depends_on": []},
                {"id": "api-rule", "kind": "implementation", "statement": "api uses the shared rule",
                 "evidence": [{"path": "src/api.py", "anchor": "def api("}],
                 "queries": [], "depends_on": ["quote-rule"]},
                {"id": "naming", "kind": "decision", "statement": "Naming is documented",
                 "evidence": [{"path": "docs.md"}], "queries": [], "depends_on": []},
            ],
        }
        self.record = context.capture(self.draft, self.root)

    def statuses(self, record):
        return {f["id"]: f["status"] for f in record["report"]["facts"]}

    def test_capture_and_refresh_do_not_mutate_project_or_input(self):
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        original = copy.deepcopy(self.record)
        result = context.refresh(self.record, self.root)
        self.assertTrue(result["report"]["ready"])
        self.assertEqual(self.record, original)
        self.assertEqual(before, {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_new_aliased_import_invalidates_owner_and_dependent_fact(self):
        (self.root / "src/worker.py").write_text("from owner import quote as calculate\nanswer = calculate(3)\n")
        updated = context.refresh(self.record, self.root)
        self.assertEqual(self.statuses(updated), {"quote-rule": "needs-review", "api-rule": "needs-review", "naming": "current"})
        self.assertEqual(updated["report"]["new_reference_candidates"][0]["path"], "src/worker.py")
        self.assertEqual(updated["report"]["new_reference_candidates"][0]["lines"], [1])

    def test_existing_file_can_become_a_new_reference_candidate(self):
        (self.root / "src/worker.py").write_text("answer = 3\n")
        record = context.capture(self.draft, self.root)
        (self.root / "src/worker.py").write_text("from owner import quote\nanswer = quote(3)\n")
        updated = context.refresh(record, self.root)
        self.assertEqual(updated["report"]["reference_changes"][0]["kind"], "added")

    def test_modified_reference_exposes_the_changed_file(self):
        (self.root / "src/api.py").write_text("from owner import quote\n\ndef api(value):\n    return quote(value + 1)\n")
        result = context.refresh(self.record, self.root)
        self.assertTrue(any(c["kind"] == "modified" and c["path"] == "src/api.py" for c in result["report"]["reference_changes"]))

    def test_removed_reference_is_recorded_without_claiming_old_lines_are_current(self):
        (self.root / "src/api.py").write_text("def api(value):\n    return value\n")
        result = context.refresh(self.record, self.root)
        removed = next(c for c in result["report"]["reference_changes"] if c["path"] == "src/api.py")
        self.assertEqual(removed["kind"], "removed")
        self.assertIsNone(removed["current"])
        self.assertIsNotNone(removed["previous"])

    def test_renamed_file_invalidates_old_location_and_discovers_new_candidate(self):
        (self.root / "src/owner.py").rename(self.root / "src/pricing.py")
        result = context.refresh(self.record, self.root)
        self.assertEqual(self.statuses(result)["quote-rule"], "unknown")
        self.assertIn("src/pricing.py", [c["path"] for c in result["report"]["new_reference_candidates"]])
        with self.assertRaises(ValueError):
            context.confirm(result, self.root, ["quote-rule", "api-rule"], result["report"]["snapshot_id"], "old path not corrected")

    def test_unrelated_modification_does_not_invalidate_facts(self):
        (self.root / "src/unrelated.py").write_text("def unrelated(): return 9\n")
        self.assertTrue(context.refresh(self.record, self.root)["report"]["ready"])

    def test_dependency_invalidation_is_transitive(self):
        draft = copy.deepcopy(self.draft)
        draft["facts"][2]["depends_on"] = ["api-rule"]
        record = context.capture(draft, self.root)
        (self.root / "src/owner.py").write_text("def quote(value):\n    return value * 3\n")
        self.assertEqual(set(context.refresh(record, self.root)["_state"]["pending"]), {"quote-rule", "api-rule", "naming"})

    def test_repeated_refresh_does_not_clear_pending_review(self):
        path = self.root / "src/owner.py"
        original = path.read_text()
        path.write_text("def quote(value):\n    return value * 3\n")
        changed = context.refresh(self.record, self.root)
        again = context.refresh(changed, self.root)
        self.assertFalse(again["report"]["ready"])
        path.write_text(original)
        reverted = context.refresh(again, self.root)
        self.assertFalse(reverted["report"]["ready"])
        self.assertIn("quote-rule", reverted["_state"]["pending"])

    def test_confirm_after_actual_review_updates_only_selected_facts(self):
        (self.root / "src/owner.py").write_text("def quote(value):\n    return value * 3\n")
        result = context.refresh(self.record, self.root)
        old_naming = copy.deepcopy(result["_state"]["basis"]["naming"])
        confirmed = context.confirm(result, self.root, ["quote-rule", "api-rule"], result["report"]["snapshot_id"],
                                    "Read owner and API; checked shared-rule behavior.")
        self.assertTrue(confirmed["report"]["ready"])
        self.assertEqual(confirmed["_state"]["basis"]["naming"], old_naming)
        self.assertTrue(context.refresh(confirmed, self.root)["report"]["ready"])

    def test_cannot_confirm_a_dependent_without_its_pending_dependency(self):
        (self.root / "src/owner.py").write_text("def quote(value): return 5\n")
        result = context.refresh(self.record, self.root)
        with self.assertRaisesRegex(ValueError, "unreviewed fact"):
            context.confirm(result, self.root, ["api-rule"], result["report"]["snapshot_id"], "reviewed only API")

    def test_confirmation_rejects_intervening_code_change(self):
        result = context.refresh(self.record, self.root)
        (self.root / "src/owner.py").write_text("def quote(value): return 5\n")
        with self.assertRaisesRegex(ValueError, "changed since"):
            context.confirm(result, self.root, ["quote-rule"], result["report"]["snapshot_id"], "stale review")

    def test_confirmation_rejects_intervening_statement_change(self):
        result = context.refresh(self.record, self.root)
        result["facts"][0]["statement"] = "A new claim not covered by the earlier review"
        with self.assertRaisesRegex(ValueError, "changed since"):
            context.confirm(result, self.root, ["quote-rule"], result["report"]["snapshot_id"], "stale statement")

    def test_updated_location_and_statement_can_be_reviewed_and_confirmed(self):
        (self.root / "src/owner.py").rename(self.root / "src/pricing.py")
        revised = copy.deepcopy(self.record)
        revised["facts"][0]["statement"] = "pricing now owns the rule"
        revised["facts"][0]["evidence"][0]["path"] = "src/pricing.py"
        result = context.refresh(revised, self.root)
        confirmed = context.confirm(result, self.root, ["quote-rule", "api-rule"], result["report"]["snapshot_id"], "Verified the move and callers")
        self.assertTrue(confirmed["report"]["ready"])

    def test_new_fact_requires_review_and_preserves_existing_basis(self):
        revised = copy.deepcopy(self.record)
        revised["facts"].append({"id": "additional", "kind": "inference", "statement": "Proposed interpretation",
                                 "evidence": [{"path": "docs.md"}], "depends_on": [], "queries": []})
        result = context.refresh(revised, self.root)
        self.assertEqual(result["_state"]["pending"], ["additional"])
        confirmed = context.confirm(result, self.root, ["additional"], result["report"]["snapshot_id"], "Reviewed evidence for interpretation")
        self.assertTrue(confirmed["report"]["ready"])

    def test_identifier_search_does_not_match_a_longer_identifier(self):
        (self.root / "src/other.py").write_text("quote_extra = 3\n")
        self.assertTrue(context.refresh(self.record, self.root)["report"]["ready"])

    def test_globs_cover_zero_or_more_directories_without_overmatching_single_star(self):
        for path in ("src/a.py", "src/nested/a.py", "src/nested/deeper/a.py"):
            self.assertTrue(context.matches(path, ["src/**/*.py"]), path)
        self.assertFalse(context.matches("src/nested/a.py", ["src/*.py"]))
        self.assertFalse(context.matches("other/a.py", ["src/**/*.py"]))

    def test_literal_search_can_watch_non_python_sources(self):
        (self.root / "src/owner.ts").write_text("export const buildQuote = () => 1;\n")
        draft = copy.deepcopy(self.draft)
        draft["queries"][0] = {"id": "quote-users", "include": ["**/*.ts"], "terms": ["buildQuote"], "match": "literal"}
        record = context.capture(draft, self.root)
        (self.root / "src/page.ts").write_text("import {buildQuote as price} from './owner';\n")
        result = context.refresh(record, self.root)
        self.assertEqual(result["report"]["new_reference_candidates"][0]["path"], "src/page.ts")

    def test_excluded_dependencies_do_not_become_project_references(self):
        directory = self.root / "node_modules"
        directory.mkdir()
        (directory / "tool.py").write_text("quote(1)\n")
        self.assertTrue(context.refresh(self.record, self.root)["report"]["ready"])

    def test_oversized_matching_file_is_a_coverage_gap(self):
        (self.root / "src/large.py").write_text("x" * 500)
        result = context.refresh(self.record, self.root, max_bytes=100)
        self.assertFalse(result["report"]["ready"])
        self.assertTrue(any("src/large.py" in gap for gap in result["report"]["coverage_gaps"]))

    def test_non_text_file_is_not_silently_treated_as_no_references(self):
        (self.root / "src/nontext.py").write_bytes(b"\xff")
        result = context.refresh(self.record, self.root)
        self.assertEqual(self.statuses(result)["quote-rule"], "unknown")

    def test_symbolic_directory_and_scan_limit_are_coverage_gaps(self):
        (self.root / "src/link").symlink_to(self.root / "src", target_is_directory=True)
        self.assertFalse(context.refresh(self.record, self.root)["report"]["ready"])
        (self.root / "src/link").unlink()
        self.assertFalse(context.refresh(self.record, self.root, max_files=1)["report"]["ready"])

    def test_out_of_scope_symbolic_directory_does_not_invalidate_any_fact(self):
        (self.root / "unrelated-link").symlink_to(self.root / "src", target_is_directory=True)
        result = context.refresh(self.record, self.root)
        self.assertTrue(result["report"]["ready"])
        self.assertEqual(result["report"]["coverage_gaps"], [])

    def test_gap_only_invalidates_queries_whose_scope_contains_the_directory(self):
        draft = copy.deepcopy(self.draft)
        draft["queries"].append({"id": "docs-users", "include": ["docs/**/*.py"], "terms": ["documentation"]})
        draft["facts"][2]["queries"] = ["docs-users"]
        record = context.capture(draft, self.root)
        (self.root / "src/link").symlink_to(self.root / "src", target_is_directory=True)
        result = context.refresh(record, self.root)
        self.assertEqual(self.statuses(result)["naming"], "current")
        self.assertEqual(self.statuses(result)["quote-rule"], "unknown")

    def test_unsafe_paths_and_cyclic_dependencies_are_rejected(self):
        bad = copy.deepcopy(self.draft)
        bad["queries"][0]["include"] = ["../*.py"]
        with self.assertRaises(ValueError):
            context.capture(bad, self.root)
        bad = copy.deepcopy(self.draft)
        bad["facts"][0]["depends_on"] = ["api-rule"]
        with self.assertRaises(ValueError):
            context.capture(bad, self.root)

    def test_existing_record_cannot_be_blindly_recaptured(self):
        with self.assertRaisesRegex(ValueError, "refresh and confirm"):
            context.capture(self.record, self.root)

    def test_cli_emits_changed_context_and_nonzero_pending_status(self):
        (self.root / "src/worker.py").write_text("from owner import quote\n")
        result = subprocess.run([sys.executable, str(SCRIPTS / "refresh_context.py"), "refresh", "--root", str(self.root), "--record", "-"],
                                input=json.dumps(self.record), text=True, capture_output=True)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(json.loads(result.stdout)["_state"]["pending"], ["api-rule", "quote-rule"])


if __name__ == "__main__":
    unittest.main()
