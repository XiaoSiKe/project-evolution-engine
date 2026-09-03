#!/usr/bin/env python3
"""Safely check, preview, or install project-evolution-engine to an explicit target."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "project-evolution-engine"
SKILL_NAME = "project-evolution-engine"
MANIFEST_NAME = ".project-evolution-engine-install.json"
IGNORED_NAMES = {".DS_Store", "__pycache__"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files() -> dict[str, str]:
    if not (SOURCE / "SKILL.md").is_file():
        raise ValueError("source skill is missing SKILL.md")
    files: dict[str, str] = {}
    for path in sorted(SOURCE.rglob("*")):
        relative = path.relative_to(SOURCE)
        if any(part in IGNORED_NAMES for part in relative.parts) or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError(f"source contains unsupported symlink: {relative}")
        if path.is_file():
            files[relative.as_posix()] = digest(path)
    return files


def validate_target(raw_target: Path) -> Path:
    expanded = raw_target.expanduser()
    if expanded.is_symlink():
        raise ValueError(f"target directory must not be a symlink: {expanded}")
    target = expanded.resolve()
    forbidden = {Path("/").resolve(), Path.home().resolve(), PROJECT_ROOT.resolve(), SOURCE.resolve()}
    if target in forbidden or target.is_relative_to(SOURCE.resolve()) or target.name != SKILL_NAME:
        raise ValueError(f"target must be an explicit directory named {SKILL_NAME}: {target}")
    return target


def load_manifest(target: Path) -> dict[str, Any] | None:
    path = target / MANIFEST_NAME
    if path.is_symlink():
        raise ValueError(f"install manifest must not be a symlink: {path}")
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("skill") != SKILL_NAME or not isinstance(data.get("files"), dict):
        raise ValueError(f"invalid install manifest: {path}")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in data["files"].items()):
        raise ValueError(f"invalid manifest file entries: {path}")
    return data


def safe_target_path(target: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe manifest path: {relative}")
    candidate = target
    for part in path.parts:
        candidate /= part
        if candidate.is_symlink():
            raise ValueError(f"managed path must not contain a symlink: {relative}")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(target):
        raise ValueError(f"manifest path escapes target: {relative}")
    return resolved


def inspect_target(target: Path, current_source: dict[str, str]) -> dict[str, Any]:
    if not target.exists():
        return {
            "status": "missing",
            "installable": True,
            "add": sorted(current_source),
            "update": [],
            "remove": [],
            "local_changes": [],
            "conflicts": [],
        }
    if not target.is_dir():
        raise ValueError(f"target is not a directory: {target}")

    manifest = load_manifest(target)
    if manifest is None:
        if not any(target.iterdir()):
            return {
                "status": "empty", "installable": True, "add": sorted(current_source),
                "update": [], "remove": [], "local_changes": [], "conflicts": [],
            }
        return {
            "status": "unmanaged",
            "installable": False,
            "add": [],
            "update": [],
            "remove": [],
            "local_changes": [],
            "conflicts": ["existing target has no install manifest"],
        }

    previous: dict[str, str] = manifest["files"]
    local_changes: list[str] = []
    for relative, expected_hash in previous.items():
        path = safe_target_path(target, relative)
        if not path.is_file() or digest(path) != expected_hash:
            local_changes.append(relative)

    conflicts = [
        relative
        for relative in current_source
        if relative not in previous and safe_target_path(target, relative).exists()
    ]
    add = sorted(set(current_source) - set(previous))
    update = sorted(
        relative
        for relative in set(current_source) & set(previous)
        if current_source[relative] != previous[relative]
    )
    remove = sorted(set(previous) - set(current_source))
    installable = not local_changes and not conflicts
    status = "current" if installable and not (add or update or remove) else "update-available"
    if local_changes:
        status = "locally-modified"
    elif conflicts:
        status = "conflict"
    return {
        "status": status,
        "installable": installable,
        "add": add,
        "update": update,
        "remove": remove,
        "local_changes": sorted(local_changes),
        "conflicts": sorted(conflicts),
    }


def write_manifest(target: Path, files: dict[str, str]) -> None:
    payload = json.dumps({"skill": SKILL_NAME, "files": files}, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, target / MANIFEST_NAME)


def remove_empty_parents(path: Path, target: Path) -> None:
    parent = path.parent
    while parent != target and parent.is_relative_to(target):
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def install(target: Path, plan: dict[str, Any], current_source: dict[str, str]) -> None:
    if not plan["installable"]:
        raise ValueError(f"refusing install with target status {plan['status']}")
    target.mkdir(parents=True, exist_ok=True)

    for relative in plan["remove"]:
        path = safe_target_path(target, relative)
        if path.exists():
            path.unlink()
            remove_empty_parents(path, target)

    for relative in sorted(set(plan["add"]) | set(plan["update"])):
        source = SOURCE.joinpath(*PurePosixPath(relative).parts)
        destination = safe_target_path(target, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    write_manifest(target, current_source)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Compare source and target without writing")
    mode.add_argument("--dry-run", action="store_true", help="Preview an install without writing")
    mode.add_argument("--install", action="store_true", help="Install after safety checks")
    parser.add_argument("--target", type=Path, required=True, help="Explicit target skill directory")
    args = parser.parse_args()

    try:
        target = validate_target(args.target)
        current_source = source_files()
        plan = inspect_target(target, current_source)
        payload = {"source": str(SOURCE), "target": str(target), **plan}

        if args.install:
            install(target, plan, current_source)
            payload = {"source": str(SOURCE), "target": str(target), **inspect_target(target, current_source)}

        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        if args.check:
            return 0 if payload["status"] == "current" else 1
        return 0 if payload["installable"] else 2
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
