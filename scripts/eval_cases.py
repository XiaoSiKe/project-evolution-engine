#!/usr/bin/env python3
"""Validate, materialize, and score project-evolution-engine eval cases."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_FILE = PROJECT_ROOT / "evals" / "cases.json"
CONTRACT_FILE = PROJECT_ROOT / "evals" / "result-contract.json"
EXPECTED_KEYS = {
    "allowed_changed_paths",
    "claims_full_correctness",
    "gate",
    "mutation",
    "paused",
    "required_verification",
    "routes",
}
OPTIONAL_EXPECTED_KEYS = {"required_changed_paths"}
RESULT_KEYS = {
    "changed_files",
    "claims_full_correctness",
    "gate",
    "mutation",
    "paused",
    "routes",
    "verification",
}
IGNORED_WORKSPACE_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}
IGNORED_WORKSPACE_NAMES = {".coverage", ".DS_Store"}


def load_cases() -> list[dict[str, Any]]:
    data = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("eval catalog must be a JSON list")
    return data


def load_contract() -> dict[str, Any]:
    data = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("fields"), dict):
        raise ValueError("result contract must contain a fields object")
    return data


def safe_relative_path(raw: str) -> PurePosixPath:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise ValueError(f"unsafe fixture path: {raw!r}")
    path = PurePosixPath(raw)
    if (
        path.is_absolute()
        or not path.parts
        or ".." in path.parts
        or "." in path.parts
        or path.as_posix() != raw
    ):
        raise ValueError(f"unsafe fixture path: {raw}")
    return path


def string_list(value: Any, label: str, errors: list[str]) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(f"{label} must be a list of strings")
        return None
    return value


def path_list(value: Any, label: str, errors: list[str]) -> list[str] | None:
    paths = string_list(value, label, errors)
    if paths is None:
        return None
    for raw_path in paths:
        try:
            safe_relative_path(raw_path)
        except ValueError as error:
            errors.append(f"{label}: {error}")
    return paths


def validate_cases(cases: list[dict[str, Any]], contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    allowed_gates = set(contract["fields"]["gate"]["allowed"])
    allowed_mutations = set(contract["fields"]["mutation"]["allowed"])
    allowed_routes = set(contract["fields"]["routes"]["allowed_items"])
    allowed_verification = set(contract["fields"]["verification"]["allowed_items"])
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"case {index}: must be an object")
            continue
        label = case.get("id", f"index-{index}")
        if not isinstance(label, str) or not label:
            errors.append(f"case {index}: missing id")
            continue
        if label in seen:
            errors.append(f"{label}: duplicate id")
        seen.add(label)
        if not isinstance(case.get("request"), str) or not case["request"].strip():
            errors.append(f"{label}: missing request")
        files = case.get("files")
        if not isinstance(files, dict) or not files:
            errors.append(f"{label}: files must be a non-empty object")
        else:
            for raw_path, content in files.items():
                try:
                    safe_relative_path(raw_path)
                except ValueError as error:
                    errors.append(f"{label}: {error}")
                if not isinstance(content, str):
                    errors.append(f"{label}: fixture content for {raw_path} must be a string")
        expected = case.get("expected")
        if (
            not isinstance(expected, dict)
            or not EXPECTED_KEYS.issubset(expected)
            or set(expected) - EXPECTED_KEYS - OPTIONAL_EXPECTED_KEYS
        ):
            errors.append(
                f"{label}: expected keys must include {sorted(EXPECTED_KEYS)} and may include "
                f"{sorted(OPTIONAL_EXPECTED_KEYS)}"
            )
        else:
            if not isinstance(expected["gate"], str) or expected["gate"] not in allowed_gates:
                errors.append(f"{label}: unsupported gate {expected['gate']!r}")
            if not isinstance(expected["mutation"], str) or expected["mutation"] not in allowed_mutations:
                errors.append(f"{label}: unsupported mutation {expected['mutation']!r}")
            routes = string_list(expected["routes"], f"{label}: routes", errors)
            if routes is not None and not set(routes).issubset(allowed_routes):
                errors.append(f"{label}: unsupported route in {expected['routes']!r}")
            required_verification = string_list(
                expected["required_verification"], f"{label}: required_verification", errors
            )
            if required_verification is not None and not set(required_verification).issubset(allowed_verification):
                errors.append(f"{label}: unsupported verification tag")
            if expected["claims_full_correctness"] is not False:
                errors.append(f"{label}: claims_full_correctness must be false")
            if not isinstance(expected["paused"], bool):
                errors.append(f"{label}: paused must be a boolean")
            allowed_changed = path_list(
                expected["allowed_changed_paths"], f"{label}: allowed_changed_paths", errors
            )
            required_changed = path_list(
                expected.get("required_changed_paths", []), f"{label}: required_changed_paths", errors
            )
            if required_changed is not None:
                if allowed_changed is not None and not set(required_changed).issubset(allowed_changed):
                    errors.append(f"{label}: required_changed_paths must be allowed")
        git = case.get("git", {})
        if not isinstance(git, dict):
            errors.append(f"{label}: git must be an object")
        else:
            if "initial_commit" in git and not isinstance(git["initial_commit"], bool):
                errors.append(f"{label}: initial_commit must be a boolean")
            dirty_files = git.get("dirty_files", {})
            if not isinstance(dirty_files, dict):
                errors.append(f"{label}: dirty_files must be an object")
            else:
                for raw_path, content in dirty_files.items():
                    try:
                        safe_relative_path(raw_path)
                    except ValueError as error:
                        errors.append(f"{label}: {error}")
                    if not isinstance(content, str):
                        errors.append(f"{label}: dirty content for {raw_path} must be a string")
    return errors


def case_by_id(cases: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
    for case in cases:
        if case["id"] == case_id:
            return case
    raise ValueError(f"unknown case: {case_id}")


def validate_output_directory(output: Path) -> Path:
    output = output.expanduser()
    if output.is_symlink():
        raise ValueError(f"output must not be a symlink: {output}")
    output = output.resolve()
    forbidden = {Path("/").resolve(), Path.home().resolve(), PROJECT_ROOT.resolve()}
    if output in forbidden:
        raise ValueError(f"refusing broad output path: {output}")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"output must be missing or empty: {output}")
    return output


def write_fixture_file(output: Path, raw_path: str, content: str) -> None:
    relative = safe_relative_path(raw_path)
    target = output.joinpath(*relative.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def materialize(case: dict[str, Any], output: Path) -> dict[str, Any]:
    output = validate_output_directory(output)
    output.mkdir(parents=True, exist_ok=True)
    for raw_path, content in case["files"].items():
        write_fixture_file(output, raw_path, content)

    git = case.get("git", {})
    if git.get("initial_commit"):
        commands = (
            ["git", "init", "-b", "main"],
            ["git", "add", "."],
            [
                "git",
                "-c",
                "user.name=Evolution Eval",
                "-c",
                "user.email=eval@example.invalid",
                "commit",
                "-m",
                "fixture baseline",
            ],
        )
        for command in commands:
            subprocess.run(command, cwd=output, text=True, capture_output=True, check=True)
        for raw_path, content in git.get("dirty_files", {}).items():
            write_fixture_file(output, raw_path, content)

    return {
        "case": case["id"],
        "request": case["request"],
        "path": str(output),
        "available_specialists": case.get("available_specialists", "current environment"),
    }


def validate_workspace(raw_workspace: Path) -> Path:
    expanded = raw_workspace.expanduser()
    if expanded.is_symlink():
        raise ValueError(f"workspace must not be a symlink: {expanded}")
    workspace = expanded.resolve()
    forbidden = {Path("/").resolve(), Path.home().resolve(), PROJECT_ROOT.resolve()}
    if workspace in forbidden or not workspace.is_dir():
        raise ValueError(f"workspace must be a materialized eval directory: {workspace}")
    return workspace


def observed_workspace_paths(workspace: Path) -> set[str]:
    def raise_walk_error(error: OSError) -> None:
        raise error

    observed: set[str] = set()
    for current, directories, filenames in os.walk(
        workspace,
        topdown=True,
        onerror=raise_walk_error,
        followlinks=False,
    ):
        current_path = Path(current)
        retained_directories: list[str] = []
        for name in directories:
            path = current_path / name
            if name in IGNORED_WORKSPACE_DIRECTORIES:
                continue
            if path.is_symlink():
                observed.add(path.relative_to(workspace).as_posix())
            else:
                retained_directories.append(name)
        directories[:] = retained_directories
        for name in filenames:
            if name in IGNORED_WORKSPACE_NAMES or name.endswith(".pyc"):
                continue
            observed.add((current_path / name).relative_to(workspace).as_posix())
    return observed


def workspace_changed_paths(case: dict[str, Any], workspace: Path) -> list[str]:
    workspace = validate_workspace(workspace)
    baseline = dict(case["files"])
    baseline.update(case.get("git", {}).get("dirty_files", {}))
    observed = observed_workspace_paths(workspace)
    changed = observed - set(baseline)

    for raw_path, content in baseline.items():
        relative = safe_relative_path(raw_path)
        path = workspace.joinpath(*relative.parts)
        if path.is_symlink() or not path.is_file() or path.read_bytes() != content.encode("utf-8"):
            changed.add(raw_path)
    return sorted(changed)


def validate_result(
    case: dict[str, Any],
    result: dict[str, Any],
    actual_changed_paths: list[str],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["result must be a JSON object"]
    missing = RESULT_KEYS - set(result)
    if missing:
        return [f"missing result keys: {sorted(missing)}"]
    for key in ("routes", "changed_files", "verification"):
        if not isinstance(result[key], list) or not all(isinstance(item, str) for item in result[key]):
            errors.append(f"{key} must be a list of strings")
    for key in ("paused", "claims_full_correctness"):
        if not isinstance(result[key], bool):
            errors.append(f"{key} must be a boolean")
    if not isinstance(result["gate"], str) or not isinstance(result["mutation"], str):
        errors.append("gate and mutation must be strings")
    if errors:
        return errors

    expected = case["expected"]
    contract = load_contract()
    for key in ("gate", "mutation", "paused", "claims_full_correctness"):
        if result[key] != expected[key]:
            errors.append(f"{key}: expected {expected[key]!r}, got {result[key]!r}")

    if sorted(result["routes"]) != sorted(expected["routes"]):
        errors.append(f"routes: expected {expected['routes']!r}, got {result['routes']!r}")
    unsupported_routes = set(result["routes"]) - set(contract["fields"]["routes"]["allowed_items"])
    if unsupported_routes:
        errors.append(f"unsupported routes: {sorted(unsupported_routes)}")

    reported_changed = set(result["changed_files"])
    changed = set(actual_changed_paths)
    unreported = changed - reported_changed
    if unreported:
        errors.append(f"changed_files has unreported workspace changes: {sorted(unreported)}")
    unobserved = reported_changed - changed
    if unobserved:
        errors.append(f"changed_files reports paths unchanged in workspace: {sorted(unobserved)}")
    allowed = set(expected["allowed_changed_paths"])
    unexpected_changes = changed - allowed
    if unexpected_changes:
        errors.append(f"changed_files contains forbidden paths: {sorted(unexpected_changes)}")
    missing_required_changes = set(expected.get("required_changed_paths", [])) - changed
    if missing_required_changes:
        errors.append(f"changed_files is missing required paths: {sorted(missing_required_changes)}")
    if expected["mutation"] == "none" and changed:
        errors.append("mutation is forbidden but changed_files is not empty")
    if result["mutation"] == "performed" and not changed:
        errors.append("mutation is performed but changed_files is empty")
    if result["mutation"] == "none" and changed:
        errors.append("mutation is none but changed_files is not empty")

    unsupported_verification = set(result["verification"]) - set(
        contract["fields"]["verification"]["allowed_items"]
    )
    if unsupported_verification:
        errors.append(f"unsupported verification tags: {sorted(unsupported_verification)}")
    observed_verification = set(result["verification"])
    if "broader-tests" in observed_verification:
        observed_verification.add("focused-tests")
    missing_verification = set(expected["required_verification"]) - observed_verification
    if missing_verification:
        errors.append(f"missing verification: {sorted(missing_verification)}")
    return errors


def print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def verify_behavior(case_id: str, workspace: Path) -> dict[str, Any]:
    workspace = validate_workspace(workspace)
    case_by_id(load_cases(), case_id)
    oracle = PROJECT_ROOT / "evals" / "oracles" / f"{case_id}.py"
    if not oracle.is_file():
        raise ValueError(f"missing behavioral oracle: {case_id}")
    result = subprocess.run(
        [sys.executable, str(oracle)], cwd=workspace, text=True, capture_output=True,
        env={**os.environ, "EVAL_WORKSPACE": str(workspace), "PYTHONDONTWRITEBYTECODE": "1"},
        timeout=60, check=False,
    )
    return {"ok": result.returncode == 0, "case": case_id, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate-cases")
    subparsers.add_parser("result-contract")

    behavior_parser = subparsers.add_parser("verify-behavior")
    behavior_parser.add_argument("--case", required=True)
    behavior_parser.add_argument("--workspace", type=Path, required=True)

    materialize_parser = subparsers.add_parser("materialize")
    materialize_parser.add_argument("--case", required=True)
    materialize_parser.add_argument("--output", type=Path, required=True)

    result_parser = subparsers.add_parser("validate-result")
    result_parser.add_argument("--case", required=True)
    result_parser.add_argument("--result", type=Path, required=True)
    result_parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()

    try:
        cases = load_cases()
        contract = load_contract()
        errors = validate_cases(cases, contract)
        if errors:
            print_json({"ok": False, "errors": errors})
            return 1

        if args.command == "validate-cases":
            print_json({"ok": True, "case_count": len(cases)})
            return 0

        if args.command == "result-contract":
            print_json(contract)
            return 0

        case = case_by_id(cases, args.case)
        if args.command == "verify-behavior":
            outcome = verify_behavior(case["id"], args.workspace)
            print_json(outcome)
            return 0 if outcome["ok"] else 1
        if args.command == "materialize":
            print_json(materialize(case, args.output))
            return 0

        result = json.loads(args.result.read_text(encoding="utf-8"))
        actual_changed_paths = workspace_changed_paths(case, args.workspace)
        errors = validate_result(case, result, actual_changed_paths)
        print_json({"ok": not errors, "errors": errors})
        return 1 if errors else 0
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print_json({"ok": False, "error": str(error)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
