#!/usr/bin/env python3
"""Prepare, run and verify repeated local Codex trials on pinned public projects."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/repeated-projects"
sys.path.insert(0, str(ROOT / "project-evolution-engine/scripts"))
from refresh_context import matches

IGNORED = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
           ".ruff_cache", ".serena", "dist", "build"}
REPORT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["completed", "decision-required", "blocked"]},
        "changed_files": {"type": "array", "items": {"type": "string"}},
        "checks": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                   "properties": {"command": {"type": "string"}, "exit_code": {"type": "integer"}, "outcome": {"type": "string"}},
                   "required": ["command", "exit_code", "outcome"]}},
        "questions": {"type": "array", "items": {"type": "string"}}, "notes": {"type": "string"},
    },
    "required": ["status", "changed_files", "checks", "questions", "notes"],
}


def snapshot(root: Path) -> dict[str, str]:
    result = {}
    for directory, folders, names in os.walk(root, followlinks=False):
        kept = []
        for name in folders:
            if name in IGNORED or name.endswith(".egg-info"):
                continue
            if (Path(directory) / name).is_symlink():
                raise ValueError("source directory symlink cannot be omitted from the trial")
            kept.append(name)
        folders[:] = sorted(kept)
        for name in sorted(names):
            if name in {".DS_Store", ".coverage"} or name.endswith(".pyc"):
                continue
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError("source file symlink is not supported")
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def tree_digest(files: dict) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def copy_source(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=False)
    for relative in snapshot(source):
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, path)


def invoke(argv: list[str], cwd: Path, env: dict | None = None, timeout: int = 180) -> dict:
    start = time.monotonic()
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    return {"command": argv, "exit_code": result.returncode, "stdout": result.stdout,
            "stderr": result.stderr, "wall_seconds": round(time.monotonic() - start, 3)}


def configuration() -> dict:
    # Read only non-secret model-selection fields; never copy auth or full config.
    path = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"
    data = tomllib.loads(path.read_text()) if path.is_file() else {}
    keys = ("model", "model_provider", "model_reasoning_effort", "profile")
    return {key: data.get(key) for key in keys}


def prepare(output: Path, sources: Path, httpx_python: Path, datasette_python: Path) -> dict:
    if output.is_symlink():
        raise ValueError("output cannot be a symlink")
    output = output.expanduser().resolve()
    if output.is_relative_to(ROOT) or output in {Path("/"), Path.home().resolve()}:
        raise ValueError("use an isolated trial directory outside the repository")
    if output.exists() and any(output.iterdir()):
        raise ValueError("output must be absent or empty")
    cases = {case["id"]: case for case in json.loads((DATA / "cases.json").read_text())}
    interpreters = {"httpx-line-endings": httpx_python.expanduser().absolute(),
                    "datasette-csv-null": datasette_python.expanduser().absolute()}
    for name in ("httpx", "datasette"):
        if not (sources / name).is_dir():
            raise ValueError(f"missing pinned project: {name}")
    if any(not python.is_file() for python in interpreters.values()):
        raise ValueError("documented runtime is missing")
    cli = shutil.which("codex")
    if not cli:
        raise ValueError("Codex CLI is not installed")
    output.mkdir(parents=True, exist_ok=True)
    skill = output / "fixed-skill/project-evolution-engine"
    copy_source(ROOT / "project-evolution-engine", skill)
    write_json(output / "report-schema.json", REPORT_SCHEMA)
    order = [("httpx-line-endings", "baseline", 1), ("datasette-csv-null", "skill", 1),
             ("httpx-line-endings", "skill", 1), ("datasette-csv-null", "baseline", 1),
             ("httpx-line-endings", "skill", 2), ("datasette-csv-null", "baseline", 2),
             ("httpx-line-endings", "baseline", 2), ("datasette-csv-null", "skill", 2)]
    trials = []
    for number, (case_id, condition, round_number) in enumerate(order, 1):
        directory = output / f"trial-{number:02d}"
        app = directory / "application"
        artifacts = directory / "artifacts"
        source_name = "httpx" if case_id.startswith("httpx") else "datasette"
        copy_source(sources / source_name, app)
        artifacts.mkdir()
        for argv in (["git", "init", "-b", "main"], ["git", "add", "--all"],
                     ["git", "-c", "user.name=Evolution Evaluation", "-c", "user.email=evaluation@example.invalid",
                      "commit", "-m", "Pinned public project baseline"]):
            if invoke(argv, app)["exit_code"]:
                raise ValueError("cannot initialize trial repository")
        before = snapshot(app)
        write_json(artifacts / "baseline.json", before)
        case = cases[case_id]
        instructions = (
            f"Use only the fixed Skill at {skill / 'SKILL.md'} and its needed resources. "
            "Do not load another copy or an external specialist Skill."
            if condition == "skill" else
            "This is the no-Skill control condition. Do not read or load any SKILL.md or Skill instructions."
        )
        prompt = f"""Complete this real project update independently.
Project: {app}
Python: {interpreters[case_id]} (preserve this virtualenv executable path).
Original request:
{case['request']}

Condition: {instructions}
You may read and change this application and use its preinstalled dependencies.
Use this existing regression command: {interpreters[case_id]} -m pytest -q {' '.join(case['upstream_tests'])}
Do not install dependencies, use the network, read another trial, read the parent repository or its evaluators, create agents, commit, push, or publish.
Work only within this application and {artifacts}. Preserve unrelated content and source/dependency configuration.
The final response must follow the supplied neutral JSON schema. List all net changed relative paths, actual checks and exit codes, unanswered material questions, and a brief explanation.
Do not claim success based solely on a report. If blocked, complete independent work and report what remains.
"""
        (artifacts / "prompt.txt").write_text(prompt)
        trials.append({"id": number, "case": case_id, "round": round_number, "condition": condition,
                       "application": str(app), "artifacts": str(artifacts), "python": str(interpreters[case_id]),
                       "baseline_sha256": tree_digest(before), "source_commit": case["commit"]})
    frozen = {name: hashlib.sha256((DATA / name).read_bytes()).hexdigest()
              for name in ("cases.json", "httpx_oracle.py", "datasette_oracle.py")}
    manifest = {"created_at": time.time(), "cli": cli, "cli_version": invoke([cli, "--version"], ROOT)["stdout"].strip(),
                "configured_model": configuration(), "schema": str(output / "report-schema.json"),
                "skill": str(skill), "skill_files": snapshot(skill), "frozen_evaluators": frozen,
                "source_roots": {"httpx": str(sources / "httpx"), "datasette": str(sources / "datasette")},
                "trials": trials}
    write_json(output / "manifest.json", manifest)
    return manifest


def parse_events(path: Path) -> dict:
    commands, files, tools, usages, messages, errors = [], [], [], [], [], []
    for line in path.read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "turn.completed":
            usages.append(event.get("usage"))
        elif event.get("type") in {"turn.failed", "error"}:
            errors.append(event)
        elif event.get("type") == "item.completed":
            item = event.get("item", {})
            kind = item.get("type")
            if kind == "command_execution":
                commands.append({key: item.get(key) for key in ("command", "exit_code", "aggregated_output", "status")})
            elif kind == "file_change":
                files.append(item.get("changes", []))
            elif kind in {"mcp_tool_call", "web_search"}:
                tools.append({key: item.get(key) for key in ("type", "server", "tool", "status")})
            elif kind == "agent_message":
                messages.append(item.get("text", ""))
    return {"usage": usages[-1] if usages else None, "usage_events": len(usages),
            "command_count": len(commands), "tool_count": len(tools), "commands": commands,
            "file_events": files, "other_tools": tools, "agent_messages": messages, "errors": errors}


def check_frozen(manifest: dict) -> None:
    for name, expected in manifest["frozen_evaluators"].items():
        if hashlib.sha256((DATA / name).read_bytes()).hexdigest() != expected:
            raise ValueError("registered evaluation or task changed after preparation")
    if snapshot(Path(manifest["skill"])) != manifest["skill_files"]:
        raise ValueError("fixed Skill changed after preparation")


def run_trial(manifest: dict, trial: dict) -> dict:
    check_frozen(manifest)
    if configuration() != manifest["configured_model"]:
        raise ValueError("model-selection configuration changed; do not mix unmatched conditions")
    artifacts, app = Path(trial["artifacts"]), Path(trial["application"])
    if (artifacts / "execution.json").exists():
        raise ValueError("this trial already has a run; preserve it and prepare a new trial for a retry")
    prompt = (artifacts / "prompt.txt").read_text()
    argv = [manifest["cli"], "exec", "--json", "--ephemeral", "--sandbox", "workspace-write",
            "-C", str(app), "--add-dir", str(artifacts), "--output-schema", manifest["schema"],
            "-o", str(artifacts / "report.json"), "-"]
    started = time.time()
    clock = time.monotonic()
    with (artifacts / "events.jsonl").open("w") as stdout, (artifacts / "stderr.log").open("w") as stderr:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, text=True)
        write_json(artifacts / "process.json", {"pid": process.pid, "started_at": started})
        process.stdin.write(prompt)
        process.stdin.close()
        timed_out = False
        try:
            code = process.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.terminate()
            try:
                code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                code = process.wait()
    metrics = parse_events(artifacts / "events.jsonl")
    result = {"id": trial["id"], "exit_code": code, "started_at": started, "finished_at": time.time(),
              "wall_seconds": round(time.monotonic() - clock, 3), "timed_out": timed_out,
              "configured_model": manifest["configured_model"], **metrics}
    write_json(artifacts / "execution.json", result)
    return {key: result[key] for key in ("id", "exit_code", "wall_seconds", "usage", "command_count", "tool_count", "timed_out")}


def evaluate(manifest: dict, trial: dict) -> dict:
    check_frozen(manifest)
    case = next(c for c in json.loads((DATA / "cases.json").read_text()) if c["id"] == trial["case"])
    artifacts, app = Path(trial["artifacts"]), Path(trial["application"])
    before = json.loads((artifacts / "baseline.json").read_text())
    after = snapshot(app)
    changed = sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))
    report_path = artifacts / "report.json"
    report = json.loads(report_path.read_text()) if report_path.is_file() else {}
    forbidden = [p for p in changed if not matches(p, case["allowed_changes"]) or p in case["protected"]]
    test_change = any(p.startswith("tests/") and p.endswith(".py") for p in changed)
    verification = artifacts / "verification-application"
    if verification.exists():
        raise ValueError("verification output exists; preserve previous evaluation before a new one")
    copy_source(app, verification)
    # Overlay unchanged upstream tests into the verification copy. Testing external
    # package-style tests can otherwise import the pristine package instead of the candidate.
    source_name = "httpx" if case["id"].startswith("httpx") else "datasette"
    original = Path(manifest["source_roots"][source_name])
    for path in snapshot(original):
        if path.startswith("tests/"):
            target = verification / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original / path, target)
    env = {**os.environ, "PYTHONPATH": str(verification), "PYTHONDONTWRITEBYTECODE": "1"}
    old_tests = invoke([trial["python"], "-m", "pytest", "-q", *case["upstream_tests"]], verification, env)
    oracle_name = "httpx_oracle.py" if case["id"].startswith("httpx") else "datasette_oracle.py"
    oracle = invoke([trial["python"], str(DATA / oracle_name), str(verification)], verification, env)
    try:
        checks = json.loads(oracle["stdout"])["checks"]
    except (ValueError, KeyError):
        checks = []
    behavior = bool(checks) and oracle["exit_code"] == 0 and all(c["passed"] is True for c in checks) and old_tests["exit_code"] == 0
    source_unchanged = snapshot(app) == after
    reported = report.get("changed_files")
    report_matches = isinstance(reported, list) and set(reported) == set(changed)
    execution_path = artifacts / "execution.json"
    execution = json.loads(execution_path.read_text()) if execution_path.exists() else {}
    passed = (behavior and source_unchanged and report_matches and not forbidden and test_change
              and report.get("status") == "completed" and not report.get("questions")
              and execution.get("exit_code") == 0)
    outcome = {"id": trial["id"], "case": trial["case"], "condition": trial["condition"], "round": trial["round"],
               "passed": passed, "behavior_passed": behavior, "changed_files": changed, "forbidden_changes": forbidden,
               "test_changed": test_change, "report_matches_diff": report_matches, "reported_status": report.get("status"),
               "unanswered_questions": report.get("questions"), "source_unchanged": source_unchanged,
               "checks": checks, "upstream_tests": old_tests, "oracle": oracle, "source_files_after": after}
    write_json(artifacts / "score.json", outcome)
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    create = sub.add_parser("prepare")
    for flag in ("output", "sources", "httpx-python", "datasette-python"):
        create.add_argument("--" + flag, required=True, type=Path)
    for name in ("run", "evaluate"):
        operation = sub.add_parser(name)
        operation.add_argument("--manifest", type=Path, required=True)
        operation.add_argument("--trials", type=int, nargs="+", required=True)
        if name == "run":
            operation.add_argument("--workers", type=int, choices=(1, 2, 3), default=2)
    args = parser.parse_args()
    if args.operation == "prepare":
        result = prepare(args.output, args.sources, args.httpx_python, args.datasette_python)
        print(json.dumps({"trials": len(result["trials"]), "configured_model": result["configured_model"],
                          "cli_version": result["cli_version"], "manifest": str(args.output / "manifest.json")}))
        return 0
    manifest = json.loads(args.manifest.read_text())
    selected = [t for t in manifest["trials"] if t["id"] in args.trials]
    if len(selected) != len(set(args.trials)):
        raise ValueError("unknown or duplicate trial IDs")
    if args.operation == "run":
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            for result in executor.map(lambda trial: run_trial(manifest, trial), selected):
                print(json.dumps(result, ensure_ascii=False), flush=True)
    else:
        outcomes = []
        for trial in selected:
            result = evaluate(manifest, trial)
            outcomes.append(result)
            print(json.dumps({key: result[key] for key in ("id", "case", "condition", "passed", "behavior_passed",
                                                          "report_matches_diff", "forbidden_changes")}), flush=True)
        return 0 if all(r["passed"] for r in outcomes) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
