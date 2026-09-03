#!/usr/bin/env python3
"""Stamp and check declared change evidence without modifying the target project."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

ROLES = {"owner", "consumer", "test", "contract", "planned"}
KINDS = {"new", "integration", "preserved"}
STATUSES = {"passed", "failed", "not-run"}
LIMITS = [
    "Freshness covers declared files only; newly introduced or undeclared consumers are not discovered.",
    "An anchor is a textual location, not proof of symbol identity or business ownership.",
    "Check results are reported evidence; this tool does not execute commands or certify completion.",
    "Valid evidence does not grant authorization to change or publish anything.",
]


def nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def strings(value: Any, label: str, required: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError(f"{label} must be a list of non-empty strings")
    if required and not value:
        raise ValueError(f"{label} must not be empty")
    if len(set(value)) != len(value):
        raise ValueError(f"{label} has duplicate entries")
    return value


def safe_path(root: Path, value: Any) -> Path:
    raw = nonempty(value, "file path")
    path = PurePosixPath(raw)
    if path.is_absolute() or path.as_posix() != raw or ".." in path.parts or "." in path.parts or "\\" in raw:
        raise ValueError(f"unsafe relative path: {raw}")
    candidate = root
    for part in path.parts:
        candidate /= part
        if candidate.is_symlink():
            raise ValueError(f"symlink evidence is unsupported: {raw}")
    if not candidate.resolve().is_relative_to(root):
        raise ValueError(f"path escapes project: {raw}")
    return candidate


def validate(record: Any, root: Path) -> None:
    if not isinstance(record, dict) or type(record.get("schema_version")) is not int or record["schema_version"] != 1:
        raise ValueError("record must have schema_version 1")
    if set(record) - {"schema_version", "goals", "files", "checks", "unknowns", "basis"}:
        raise ValueError("record has unsupported top-level fields")
    for key in ("goals", "files", "checks"):
        if not isinstance(record.get(key), list) or not record[key]:
            raise ValueError(f"{key} must be a non-empty list")
    strings(record.get("unknowns", []), "unknowns")
    paths: set[str] = set()
    for item in record["files"]:
        if not isinstance(item, dict) or set(item) - {"path", "role", "anchor"}:
            raise ValueError("file entries allow path, role, and optional anchor")
        safe_path(root, item.get("path"))
        if item["path"] in paths:
            raise ValueError(f"duplicate file: {item['path']}")
        paths.add(item["path"])
        if item.get("role") not in ROLES:
            raise ValueError(f"unsupported file role: {item.get('role')}")
        if "anchor" in item:
            nonempty(item["anchor"], "anchor")
            if item["role"] == "planned":
                raise ValueError("planned files cannot have a current-code anchor")
    checks: set[str] = set()
    for check in record["checks"]:
        if not isinstance(check, dict):
            raise ValueError("each check must be an object")
        key = nonempty(check.get("id"), "check id")
        if key in checks:
            raise ValueError(f"duplicate check id: {key}")
        checks.add(key)
        kinds = strings(check.get("kinds"), "check kinds", required=True)
        if set(kinds) - KINDS:
            raise ValueError("check kinds must be new, integration, or preserved")
        nonempty(check.get("command"), "check command or procedure")
        status = check.get("status")
        if status not in STATUSES:
            raise ValueError("check status must be passed, failed, or not-run")
        if status == "not-run":
            nonempty(check.get("reason"), "reason for not-run check")
        else:
            nonempty(check.get("evidence"), "observed check evidence")
        if "exit_code" in check and type(check["exit_code"]) is not int:
            raise ValueError("exit_code must be an integer")
        if status == "passed" and "exit_code" in check and check["exit_code"] != 0:
            raise ValueError("a passed command cannot have a nonzero exit code")
    goals: set[str] = set()
    for goal in record["goals"]:
        if not isinstance(goal, dict):
            raise ValueError("each goal must be an object")
        key = nonempty(goal.get("id"), "goal id")
        if key in goals:
            raise ValueError(f"duplicate goal id: {key}")
        goals.add(key)
        nonempty(goal.get("change"), "intended change")
        strings(goal.get("preserved"), "preserved behaviors")
        for field in ("owners", "consumers"):
            referenced = strings(goal.get(field), field, required=field == "owners")
            if set(referenced) - paths:
                raise ValueError(f"{field} refers to undeclared files")
        linked = strings(goal.get("checks"), "goal checks", required=True)
        if set(linked) - checks:
            raise ValueError("goal refers to undeclared checks")


def observe(root: Path, item: dict[str, Any]) -> dict[str, Any]:
    path = safe_path(root, item["path"])
    if not path.exists():
        return {"state": "absent", "sha256": None}
    if not path.is_file():
        raise ValueError(f"evidence path is not a regular file: {item['path']}")
    raw = path.read_bytes()
    result: dict[str, Any] = {"state": "present", "sha256": hashlib.sha256(raw).hexdigest()}
    if "anchor" in item:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            result["anchor"] = {"status": "non-text"}
        else:
            anchor = item["anchor"]
            matches = text.count(anchor)
            location: dict[str, Any] = {"status": "current" if matches == 1 else "missing" if matches == 0 else "ambiguous"}
            if matches == 1:
                location["line"] = text[:text.index(anchor)].count("\n") + 1
            result["anchor"] = location
    return result


def gaps(record: dict[str, Any]) -> list[str]:
    result: list[str] = []
    checks = {c["id"]: c for c in record["checks"]}
    for goal in record["goals"]:
        covered = {kind for key in goal["checks"] for kind in checks[key]["kinds"]}
        required = {"new", "integration"} | ({"preserved"} if goal["preserved"] else set())
        missing = sorted(required - covered)
        if missing:
            result.append(f"{goal['id']}: no checks for {', '.join(missing)}")
    for check in record["checks"]:
        if check["status"] != "passed":
            result.append(f"{check['id']}: {check['status']}")
    return result


def stamp(record: dict[str, Any], root: Path) -> dict[str, Any]:
    validate(record, root)
    result = copy.deepcopy(record)
    basis = {}
    for item in record["files"]:
        observation = observe(root, item)
        if observation["state"] == "absent" and item["role"] != "planned":
            raise ValueError(f"current evidence is missing: {item['path']}")
        if observation.get("anchor", {}).get("status", "current") != "current":
            raise ValueError(f"anchor is not unique and current: {item['path']}")
        basis[item["path"]] = observation
    result["basis"] = basis
    return result


def check_record(record: dict[str, Any], root: Path) -> dict[str, Any]:
    validate(record, root)
    basis = record.get("basis")
    paths = {item["path"] for item in record["files"]}
    if not isinstance(basis, dict) or set(basis) != paths:
        raise ValueError("basis must cover exactly the declared files; run stamp first")
    for value in basis.values():
        if not isinstance(value, dict) or value.get("state") not in {"present", "absent"}:
            raise ValueError("invalid stamped file state")
        digest = value.get("sha256")
        if value["state"] == "present" and (not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)):
            raise ValueError("invalid stamped digest")
        if value["state"] == "absent" and digest is not None:
            raise ValueError("an absent file cannot have a digest")
    changed: list[str] = []
    unavailable: list[str] = []
    anchor_issues: list[str] = []
    for item in record["files"]:
        try:
            current = observe(root, item)
        except OSError:
            unavailable.append(item["path"])
            continue
        if current != basis[item["path"]]:
            changed.append(item["path"])
        if current.get("anchor", {}).get("status", "current") != "current":
            anchor_issues.append(item["path"])
    freshness = "unknown" if unavailable else "stale" if changed else "current"
    return {"freshness": freshness, "changed_files": changed, "unavailable_files": unavailable,
            "anchor_issues": anchor_issues, "verification_gaps": gaps(record),
            "unknowns": record.get("unknowns", []), "limitations": LIMITS}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("stamp", "check"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--record", required=True, help="JSON record path, or - for stdin")
    args = parser.parse_args()
    try:
        root = args.root.expanduser().resolve()
        if not root.is_dir():
            raise ValueError("root must be a project directory")
        data = sys.stdin.read() if args.record == "-" else Path(args.record).read_text(encoding="utf-8")
        record = json.loads(data)
        result = stamp(record, root) if args.operation == "stamp" else check_record(record, root)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if args.operation == "stamp" or result["freshness"] == "current" else 1
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
