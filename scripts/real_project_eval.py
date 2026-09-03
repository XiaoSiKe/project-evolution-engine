#!/usr/bin/env python3
"""Prepare isolated public-app trials and independently evaluate their outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/real-projects"
EXCLUDED = {".git", "node_modules", "__pycache__", ".pytest_cache", ".venv", "dist", "instance", ".DS_Store"}


def files(root: Path) -> dict[str, str]:
    found = {}
    for directory, folders, names in os.walk(root, followlinks=False):
        retained = []
        for name in folders:
            if name in EXCLUDED:
                continue
            if (Path(directory) / name).is_symlink():
                raise ValueError(f"untracked source symlink: {Path(directory) / name}")
            retained.append(name)
        folders[:] = retained
        for name in names:
            path = Path(directory) / name
            if name in EXCLUDED or path.suffix == ".pyc":
                continue
            if path.is_symlink():
                raise ValueError(f"untracked source symlink: {path}")
            found[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def acceptance_digests() -> dict[str, str]:
    return {f"evals/real-projects/{name}": hashlib.sha256((DATA / name).read_bytes()).hexdigest()
            for name in ("todomvc_oracle.cjs", "flaskr_oracle.py")}


def command(argv: list[str], cwd: Path, env: dict[str, str] | None = None) -> dict:
    started = time.monotonic()
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=120)
    return {"command": argv, "exit_code": result.returncode, "stdout": result.stdout,
            "stderr": result.stderr, "wall_seconds": round(time.monotonic() - started, 3)}


def prepare(output: Path, python: Path) -> dict:
    output = output.expanduser()
    if output.is_symlink():
        raise ValueError("output cannot be a symlink")
    output = output.resolve()
    if output in {Path("/"), Path.home().resolve()} or output.is_relative_to(ROOT):
        raise ValueError("trial output must be an isolated directory outside this repository")
    if output.exists() and any(output.iterdir()):
        raise ValueError("trial output must be absent or empty")
    if not python.is_file() or not (DATA / "node/node_modules/jsdom").is_dir():
        raise ValueError("install the documented Python and Node pilot dependencies first")
    output.mkdir(parents=True, exist_ok=True)
    skill = output / "skill/project-evolution-engine"
    shutil.copytree(ROOT / "project-evolution-engine", skill, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(DATA / "result-contract.json", output / "result-contract.json")
    cases = {item["id"]: item for item in json.loads((DATA / "cases.json").read_text())}
    order = [("todomvc-undo", "baseline"), ("flaskr-drafts", "skill"),
             ("todomvc-undo", "skill"), ("flaskr-drafts", "baseline")]
    trials = []
    for index, (case_id, condition) in enumerate(order, 1):
        case = cases[case_id]
        target = output / f"trial-{index:02d}"
        shutil.copytree(DATA / case["fixture"], target, ignore=shutil.ignore_patterns(*EXCLUDED, "*.pyc"))
        if case_id == "todomvc-undo":
            (target / "node_modules").symlink_to(DATA / "node/node_modules", target_is_directory=True)
        for argv in (["git", "init", "-b", "main"], ["git", "add", "."],
                     ["git", "-c", "user.name=Evolution Pilot", "-c", "user.email=pilot@example.invalid",
                      "commit", "-m", "upstream application snapshot"]):
            if command(argv, target)["exit_code"]:
                raise ValueError("failed to initialize isolated trial repository")
        baseline = files(target)
        (output / f"baseline-{index:02d}.json").write_text(json.dumps(baseline, sort_keys=True, indent=2))
        trials.append({"id": index, "case": case_id, "condition": condition, "workspace": str(target),
                       "request": case["request"], "python": str(python.expanduser().absolute()), "node": shutil.which("node"),
                       "skill": str(skill), "result": str(output / f"result-{index:02d}.json"),
                       "contract": str(output / "result-contract.json")})
    manifest = {"created_at": time.time(), "method": "One paired trial per application, identical raw request/snapshot/runtime; inherited parent model with no override. Small exploratory sample, no significance or general uplift claim.",
                "trials": trials, "pre_registered_checks": acceptance_digests(), "skill_snapshot_files": files(skill)}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def evaluate(manifest_path: Path, trial_id: int) -> dict:
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("pre_registered_checks") != acceptance_digests():
        raise ValueError("acceptance checks changed or were not frozen before the trials")
    trial = next(t for t in manifest["trials"] if t["id"] == trial_id)
    workspace = Path(trial["workspace"])
    before = json.loads((manifest_path.parent / f"baseline-{trial_id:02d}.json").read_text())
    after = files(workspace)
    changed = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    outcome = {"id": trial_id, "case": trial["case"], "condition": trial["condition"], "changed_files": changed}
    result_path = Path(trial["result"])
    if result_path.exists():
        report = json.loads(result_path.read_text())
        reported = report.get("changed_files", [])
        outcome["report_matches_diff"] = isinstance(reported, list) and set(reported) == set(changed)
        outcome["reported_status"] = report.get("status")
        outcome["questions"] = report.get("questions", [])
    else:
        outcome["report_matches_diff"] = False
        outcome["reported_status"] = "missing"
    if trial["case"] == "todomvc-undo":
        # Build and exercise a copy, preserving the candidate's own final state.
        with tempfile.TemporaryDirectory(prefix=f"verification-{trial_id:02d}-", dir=manifest_path.parent) as temp:
            copy_root = Path(temp) / "application"
            shutil.copytree(workspace, copy_root, ignore=shutil.ignore_patterns(*EXCLUDED, "*.pyc"))
            (copy_root / "node_modules").symlink_to(DATA / "node/node_modules", target_is_directory=True)
            build = command([trial["node"], "scripts/build.js"], copy_root)
            outcome["build"] = build
            if build["exit_code"] == 0:
                run = command([trial["node"], str(DATA / "todomvc_oracle.cjs"), str(copy_root / "dist")], copy_root)
            else:
                run = {"exit_code": 2, "stdout": "", "stderr": "build failed"}
    else:
        environment = {**os.environ, "PYTHONPATH": str(workspace), "PYTHONDONTWRITEBYTECODE": "1"}
        old_tests = command([trial["python"], "-m", "pytest", "-q",
                             "-c", str(DATA / "fixtures/flaskr/pyproject.toml"),
                             str(DATA / "fixtures/flaskr/tests")], workspace, environment)
        outcome["upstream_tests"] = old_tests
        run = command([trial["python"], str(DATA / "flaskr_oracle.py"), str(workspace)], workspace, environment)
    outcome["oracle_execution"] = run
    try:
        outcome["checks"] = json.loads(run["stdout"])["checks"]
    except (json.JSONDecodeError, KeyError):
        outcome["checks"] = []
    outcome["behavior_passed"] = (run["exit_code"] == 0 and bool(outcome["checks"])
                                  and all(c["passed"] is True for c in outcome["checks"]))
    if "upstream_tests" in outcome:
        outcome["behavior_passed"] = outcome["behavior_passed"] and outcome["upstream_tests"]["exit_code"] == 0
    outcome["source_unchanged_during_verification"] = files(workspace) == after
    outcome["passed"] = (outcome["behavior_passed"] and outcome["report_matches_diff"]
                         and outcome["reported_status"] == "completed" and not outcome.get("questions")
                         and outcome["source_unchanged_during_verification"])
    (manifest_path.parent / f"score-{trial_id:02d}.json").write_text(json.dumps(outcome, ensure_ascii=False, indent=2))
    return outcome


def self_check(python: Path) -> dict:
    outputs = {}
    commands = {
        "todomvc": [shutil.which("node") or "node", str(DATA / "todomvc_oracle.cjs"), str(DATA / "fixtures/todomvc")],
        "flaskr": [str(python), str(DATA / "flaskr_oracle.py"), str(DATA / "fixtures/flaskr")],
    }
    for name, argv in commands.items():
        run = command(argv, ROOT)
        checks = json.loads(run["stdout"])["checks"]
        old = [c for c in checks if c["kind"] == "preserved"]
        new = [c for c in checks if c["kind"] != "preserved"]
        outputs[name] = {"preserved_pass": bool(old) and all(c["passed"] for c in old),
                         "missing_feature_detected": bool(new) and all(not c["passed"] for c in new)}
    env = {**os.environ, "PYTHONPATH": str(DATA / "fixtures/flaskr"), "PYTHONDONTWRITEBYTECODE": "1"}
    upstream = command([str(python), "-m", "pytest", "-q", "-c", str(DATA / "fixtures/flaskr/pyproject.toml"),
                        str(DATA / "fixtures/flaskr/tests")], ROOT, env)
    outputs["upstream_tests"] = {"exit_code": upstream["exit_code"], "output": upstream["stdout"]}
    return {"passed": all(v["preserved_pass"] and v["missing_feature_detected"] for k, v in outputs.items() if k != "upstream_tests")
                      and upstream["exit_code"] == 0, "results": outputs}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    create = sub.add_parser("prepare")
    create.add_argument("--output", required=True, type=Path)
    create.add_argument("--python", required=True, type=Path)
    run = sub.add_parser("evaluate")
    run.add_argument("--manifest", required=True, type=Path)
    run.add_argument("--trial", required=True, type=int)
    check = sub.add_parser("self-check")
    check.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args()
    try:
        if args.operation == "prepare":
            result = prepare(args.output, args.python)
        elif args.operation == "self-check":
            result = self_check(args.python)
        else:
            result = evaluate(args.manifest, args.trial)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if args.operation == "prepare" or result["passed"] else 1
    except (OSError, ValueError, StopIteration, subprocess.SubprocessError) as error:
        print(json.dumps({"error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
