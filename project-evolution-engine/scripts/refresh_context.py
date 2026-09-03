#!/usr/bin/env python3
"""Refresh declared project facts and reference searches without changing the project."""
from __future__ import annotations

import argparse
import copy
import fnmatch
from functools import lru_cache
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from change_evidence import nonempty, observe, safe_path, strings

EXCLUDED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".serena", ".pytest_cache", "dist", "build"}
LIMITATIONS = [
    "Search hits are textual reference candidates, not semantic proof of a call or ownership.",
    "Coverage is limited to declared file patterns and terms; dynamic and external consumers can be missed.",
    "Current evidence does not establish that a statement is true or that its behavior has been tested.",
    "Refresh invalidates evidence; an agent must read affected code and update statements before confirming.",
]


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def matches(path: str, patterns: list[str]) -> bool:
    @lru_cache(maxsize=None)
    def match_parts(parts: tuple[str, ...], pattern: tuple[str, ...]) -> bool:
        if not pattern:
            return not parts
        if pattern[0] == "**":
            return match_parts(parts, pattern[1:]) or bool(parts and match_parts(parts[1:], pattern))
        return bool(parts and fnmatch.fnmatchcase(parts[0], pattern[0]) and match_parts(parts[1:], pattern[1:]))

    return any(match_parts(tuple(path.split("/")), tuple(pattern.split("/"))) for pattern in patterns)


def searches_directory(directory: str, query: dict) -> bool:
    """Whether a declared include can reach a file below this directory."""
    for excluded in query.get("exclude", []):
        if excluded == "**" or excluded.endswith("/**") and matches(directory, [excluded[:-3]]):
            return False

    @lru_cache(maxsize=None)
    def possible(parts: tuple[str, ...], pattern: tuple[str, ...]) -> bool:
        if not parts:
            return bool(pattern)
        if not pattern:
            return False
        if pattern[0] == "**":
            return possible(parts, pattern[1:]) or possible(parts[1:], pattern)
        return fnmatch.fnmatchcase(parts[0], pattern[0]) and possible(parts[1:], pattern[1:])

    parts = tuple(directory.split("/")) if directory else ()
    return any(possible(parts, tuple(pattern.split("/"))) for pattern in query["include"]
               if pattern not in query.get("exclude", []))


def validate(record: Any, root: Path) -> None:
    if not isinstance(record, dict) or type(record.get("schema_version")) is not int or record["schema_version"] != 1:
        raise ValueError("context must have schema_version 1")
    if set(record) - {"schema_version", "facts", "queries", "_state", "report"}:
        raise ValueError("unsupported context fields")
    facts, queries = record.get("facts"), record.get("queries")
    if not isinstance(facts, list) or not facts or not isinstance(queries, list):
        raise ValueError("facts must be a nonempty list and queries must be a list")
    query_ids = set()
    for query in queries:
        if not isinstance(query, dict):
            raise ValueError("each query must be an object")
        key = nonempty(query.get("id"), "query id")
        if key in query_ids:
            raise ValueError(f"duplicate query: {key}")
        query_ids.add(key)
        for field in ("include", "exclude"):
            values = strings(query.get(field, []), field, required=field == "include")
            for pattern in values:
                safe_path(root, pattern)
        terms = strings(query.get("terms"), "query terms", required=True)
        mode = query.get("match", "identifier")
        if mode not in {"identifier", "literal"}:
            raise ValueError("query match must be identifier or literal")
        if mode == "identifier" and any(not term.isidentifier() for term in terms):
            raise ValueError("identifier terms must be identifiers; use literal for other text")
    fact_ids = set()
    for fact in facts:
        if not isinstance(fact, dict):
            raise ValueError("each fact must be an object")
        key = nonempty(fact.get("id"), "fact id")
        if key in fact_ids:
            raise ValueError(f"duplicate fact: {key}")
        fact_ids.add(key)
        nonempty(fact.get("statement"), "fact statement")
        if fact.get("kind") not in {"implementation", "decision", "inference"}:
            raise ValueError("fact kind must be implementation, decision, or inference")
        if not isinstance(fact.get("evidence"), list) or not fact["evidence"]:
            raise ValueError("facts require file evidence")
        paths = set()
        for item in fact["evidence"]:
            if not isinstance(item, dict) or set(item) - {"path", "anchor"}:
                raise ValueError("evidence allows path and optional unique textual anchor")
            safe_path(root, item.get("path"))
            if item["path"] in paths:
                raise ValueError("duplicate evidence file")
            paths.add(item["path"])
            if "anchor" in item:
                nonempty(item["anchor"], "anchor")
        linked = strings(fact.get("queries", []), "fact queries")
        if set(linked) - query_ids:
            raise ValueError("fact references an unknown query")
        strings(fact.get("depends_on", []), "fact dependencies")
    graph = {f["id"]: f.get("depends_on", []) for f in facts}
    seen, active = set(), set()

    def visit(key: str) -> None:
        if key not in graph:
            raise ValueError(f"unknown fact dependency: {key}")
        if key in active:
            raise ValueError("fact dependencies contain a cycle")
        if key in seen:
            return
        active.add(key)
        for dependency in graph[key]:
            visit(dependency)
        active.remove(key)
        seen.add(key)

    for key in graph:
        visit(key)


def search(root: Path, queries: list[dict], max_files: int, max_bytes: int) -> dict:
    outcomes = {q["id"]: {"definition": digest(q), "hits": {}, "gaps": []} for q in queries}
    if not queries:
        return outcomes
    expressions = {
        q["id"]: re.compile("|".join(
            (r"(?<!\w)" + re.escape(term) + r"(?!\w)") if q.get("match", "identifier") == "identifier"
            else re.escape(term) for term in q["terms"]))
        for q in queries
    }
    def inaccessible(error: OSError) -> None:
        try:
            relative = Path(error.filename).relative_to(root).as_posix() if error.filename else ""
        except ValueError:
            relative = ""
        for query in queries:
            if searches_directory(relative, query):
                outcomes[query["id"]]["gaps"].append(str(error))

    count = 0
    for directory, folders, names in os.walk(root, followlinks=False, onerror=inaccessible):
        retained = []
        for name in sorted(folders):
            if name in EXCLUDED:
                continue
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            affected_queries = [query for query in queries if searches_directory(relative, query)]
            if not affected_queries:
                continue
            if path.is_symlink():
                for query in affected_queries:
                    outcomes[query["id"]]["gaps"].append(f"symlink directory not scanned: {relative}")
            else:
                retained.append(name)
        folders[:] = retained
        for name in sorted(names):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            relevant = [q for q in queries if matches(relative, q["include"]) and not matches(relative, q.get("exclude", []))]
            if not relevant:
                continue
            count += 1
            if count > max_files:
                for outcome in outcomes.values():
                    outcome["gaps"].append(f"search file limit exceeded: {max_files}")
                break
            try:
                if path.is_symlink():
                    raise ValueError("symlink file not scanned")
                if path.stat().st_size > max_bytes:
                    raise ValueError(f"file exceeds {max_bytes} byte limit")
                raw = path.read_bytes()
                content = raw.decode("utf-8")
            except (OSError, UnicodeError, ValueError) as error:
                for query in relevant:
                    outcomes[query["id"]]["gaps"].append(f"{relative}: {error}")
                continue
            for query in relevant:
                lines = [index for index, line in enumerate(content.splitlines(), 1)
                         if expressions[query["id"]].search(line)]
                if lines:
                    outcomes[query["id"]]["hits"][relative] = {
                        "lines": lines, "sha256": hashlib.sha256(raw).hexdigest(),
                    }
        if count > max_files:
            break
    return outcomes


def snapshot(record: dict, root: Path, max_files: int, max_bytes: int) -> dict:
    queries = search(root, record["queries"], max_files, max_bytes)
    result = {}
    for fact in record["facts"]:
        evidence = {}
        for item in fact["evidence"]:
            try:
                evidence[item["path"]] = observe(root, item)
            except (OSError, ValueError) as error:
                evidence[item["path"]] = {"state": "unknown", "error": str(error)}
        result[fact["id"]] = {
            "definition": digest(fact), "evidence": evidence,
            "queries": {key: queries[key] for key in fact.get("queries", [])},
        }
    return result


def incomplete(observation: dict) -> bool:
    return (any(item.get("state") != "present" or item.get("anchor", {}).get("status", "current") != "current"
                for item in observation["evidence"].values())
            or any(query["gaps"] for query in observation["queries"].values()))


def refresh(record: dict, root: Path, *, max_files: int = 20000, max_bytes: int = 2_000_000) -> dict:
    validate(record, root)
    state = record.get("_state")
    if not isinstance(state, dict) or not isinstance(state.get("basis"), dict):
        raise ValueError("context has no captured basis; capture a reviewed draft first")
    if max_files < 1 or max_bytes < 1:
        raise ValueError("scan limits must be positive")
    observed = snapshot(record, root, max_files, max_bytes)
    basis = state["basis"]
    removed = set(basis) - set(observed)
    if removed:
        raise ValueError(f"retire removed facts in the authoritative document, then capture a new context: {sorted(removed)}")
    pending = set(strings(state.get("pending", []), "pending facts"))
    if pending - set(observed):
        raise ValueError("pending contains unknown facts")
    reasons = {key: [] for key in observed}
    candidates = {}
    reference_changes = {}
    evidence_changes = {}
    for key, current in observed.items():
        old = basis.get(key)
        if old != current:
            pending.add(key)
            reasons[key].append("declared fact, evidence, or reference search changed")
        if incomplete(current):
            pending.add(key)
            reasons[key].append("evidence is unavailable, ambiguous, or the search has a coverage gap")
        if old:
            for path in set(old.get("evidence", {})) | set(current["evidence"]):
                previous_file = old.get("evidence", {}).get(path)
                current_file = current["evidence"].get(path)
                if previous_file != current_file:
                    evidence_changes[(key, path)] = {"fact": key, "path": path,
                                                     "previous": previous_file, "current": current_file}
            for query_id, query in current["queries"].items():
                previous = old.get("queries", {}).get(query_id, {}).get("hits", {})
                for path in set(previous) | set(query["hits"]):
                    if previous.get(path) != query["hits"].get(path):
                        reference_changes[(query_id, path)] = {
                            "query": query_id, "path": path,
                            "kind": "added" if path not in previous else "removed" if path not in query["hits"] else "modified",
                            "previous": previous.get(path), "current": query["hits"].get(path),
                        }
                for path in set(query["hits"]) - set(previous):
                    candidates[(query_id, path)] = {"query": query_id, "path": path, **query["hits"][path]}
    changed = True
    while changed:
        changed = False
        for fact in record["facts"]:
            dependencies = sorted(set(fact.get("depends_on", [])) & pending)
            if dependencies:
                reason = f"depends on facts requiring review: {', '.join(dependencies)}"
                if reason not in reasons[fact["id"]]:
                    reasons[fact["id"]].append(reason)
                if fact["id"] not in pending:
                    pending.add(fact["id"])
                    changed = True
    for key in pending:
        if not reasons[key]:
            reasons[key].append("previous review remains unresolved")
    result = copy.deepcopy(record)
    result["_state"]["pending"] = sorted(pending)
    result["report"] = {
        "ready": not pending, "snapshot_id": digest(observed),
        "facts": [{"id": key, "status": "unknown" if incomplete(observed[key]) else "needs-review" if key in pending else "current",
                   "reasons": reasons[key]} for key in observed],
        "new_reference_candidates": [candidates[key] for key in sorted(candidates)],
        "reference_changes": [reference_changes[key] for key in sorted(reference_changes)],
        "evidence_changes": [evidence_changes[key] for key in sorted(evidence_changes)],
        "coverage_gaps": sorted({gap for value in observed.values() for q in value["queries"].values() for gap in q["gaps"]}),
        "limitations": LIMITATIONS,
    }
    return result


def capture(record: dict, root: Path, **limits: int) -> dict:
    validate(record, root)
    if "_state" in record:
        raise ValueError("capture is only for a new draft; refresh and confirm an existing context")
    observed = snapshot(record, root, limits.get("max_files", 20000), limits.get("max_bytes", 2_000_000))
    if any(incomplete(value) for value in observed.values()):
        raise ValueError("cannot capture incomplete file evidence or reference searches")
    result = copy.deepcopy(record)
    result["_state"] = {"basis": observed, "pending": [], "last_review": {}}
    return refresh(result, root, **limits)


def confirm(record: dict, root: Path, fact_ids: list[str], against: str, note: str, **limits: int) -> dict:
    nonempty(note, "review note")
    strings(fact_ids, "reviewed facts", required=True)
    result = refresh(record, root, **limits)
    if result["report"]["snapshot_id"] != against:
        raise ValueError("project evidence or declarations changed since the review snapshot; refresh and review again")
    selected = set(fact_ids)
    facts = {fact["id"]: fact for fact in record["facts"]}
    if selected - set(facts):
        raise ValueError("confirmation contains unknown facts")
    pending = set(result["_state"]["pending"])
    for key in selected:
        if set(facts[key].get("depends_on", [])) & (pending - selected):
            raise ValueError(f"{key} still depends on an unreviewed fact")
    observed = snapshot(record, root, limits.get("max_files", 20000), limits.get("max_bytes", 2_000_000))
    if digest(observed) != against:
        raise ValueError("project evidence changed during confirmation")
    for key in selected:
        if incomplete(observed[key]):
            raise ValueError(f"cannot confirm incomplete evidence: {key}")
        result["_state"]["basis"][key] = observed[key]
        result["_state"]["last_review"][key] = {"snapshot_id": against, "note": note}
    result["_state"]["pending"] = sorted(pending - selected)
    return refresh(result, root, **limits)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("capture", "refresh", "confirm"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--record", required=True, help="JSON path or - for stdin")
    parser.add_argument("--facts", nargs="+", help="Fact IDs actually reviewed for confirm")
    parser.add_argument("--against", help="snapshot_id observed when reviewing")
    parser.add_argument("--note", help="What was read, verified, and updated")
    parser.add_argument("--max-files", type=int, default=20000)
    parser.add_argument("--max-file-bytes", type=int, default=2_000_000)
    args = parser.parse_args()
    try:
        root = args.root.expanduser().resolve()
        if not root.is_dir() or args.max_files < 1 or args.max_file_bytes < 1:
            raise ValueError("an existing project root and positive limits are required")
        raw = sys.stdin.read() if args.record == "-" else Path(args.record).read_text(encoding="utf-8")
        record = json.loads(raw)
        limits = {"max_files": args.max_files, "max_bytes": args.max_file_bytes}
        if args.operation == "capture":
            result = capture(record, root, **limits)
        elif args.operation == "refresh":
            result = refresh(record, root, **limits)
        else:
            result = confirm(record, root, args.facts, args.against, args.note, **limits)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result["report"]["ready"] else 1
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
