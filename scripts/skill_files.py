#!/usr/bin/env python3
"""Select the files that belong to the installable skill."""
from __future__ import annotations

from pathlib import Path

IGNORED_NAMES = {".DS_Store", "__pycache__"}


def iter_skill_files(source: Path) -> list[Path]:
    """Return the deterministic, regular-file contents of a skill directory."""
    if not (source / "SKILL.md").is_file():
        raise ValueError("source skill is missing SKILL.md")
    files: list[Path] = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in IGNORED_NAMES for part in relative.parts) or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError(f"source contains unsupported symlink: {relative}")
        if path.is_file():
            files.append(path)
    return files
