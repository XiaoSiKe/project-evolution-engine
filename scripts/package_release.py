#!/usr/bin/env python3
"""Build a deterministic ZIP of the installable skill and a SHA-256 file."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "project-evolution-engine"
IGNORED = {"__pycache__", ".DS_Store"}


def build(output: Path) -> dict[str, object]:
    output = output.expanduser()
    checksum = Path(str(output) + ".sha256")
    if output.exists() or output.is_symlink() or checksum.exists() or checksum.is_symlink():
        raise ValueError("output or checksum already exists")
    output = output.resolve()
    if output.is_relative_to(SOURCE.resolve()):
        raise ValueError("release output must be outside the skill source")
    if not (SOURCE / "SKILL.md").is_file():
        raise ValueError("skill source is missing")
    paths = []
    for path in sorted(SOURCE.rglob("*")):
        relative = path.relative_to(SOURCE)
        if any(part in IGNORED for part in relative.parts) or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError(f"source symlink: {relative}")
        if path.is_file():
            paths.append(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in paths:
            name = SOURCE.name + "/" + path.relative_to(SOURCE).as_posix()
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return {"archive": str(output), "sha256": digest, "file_count": len(paths)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
