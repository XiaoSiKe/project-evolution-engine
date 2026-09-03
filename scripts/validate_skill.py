#!/usr/bin/env python3
"""Validate the installable skill structure and metadata."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
NAME = "project-evolution-engine"


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    entry = root / "SKILL.md"
    if not entry.is_file():
        return ["SKILL.md is missing"]
    text = entry.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if not match:
        return ["YAML frontmatter is missing"]
    try:
        data = yaml.safe_load(match.group(1))
        ui = yaml.safe_load((root / "agents/openai.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        return [str(error)]
    if not isinstance(data, dict):
        return ["frontmatter must be a mapping"]
    if data.get("name") != NAME or root.name != NAME:
        errors.append("name must match the skill directory")
    if not isinstance(data.get("description"), str) or not data["description"].strip():
        errors.append("description must be a non-empty string")
    interface = ui.get("interface", {}) if isinstance(ui, dict) else {}
    if interface.get("display_name") != "项目进化引擎skill":
        errors.append("unexpected display name")
    short = interface.get("short_description", "")
    if not isinstance(short, str) or not 25 <= len(short) <= 64:
        errors.append("short_description must have 25–64 characters")
    prompt = interface.get("default_prompt", "")
    if not isinstance(prompt, str) or "$" + NAME not in prompt:
        errors.append("default_prompt must invoke the skill")
    if isinstance(ui, dict) and ui.get("policy", {}).get("allow_implicit_invocation") is False:
        errors.append("automatic discovery must remain enabled")
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        if not (root / name).is_file():
            errors.append(f"{name} is missing")
    reached: set[Path] = set()
    pending = [entry]
    while pending:
        source = pending.pop().resolve()
        if source in reached:
            continue
        reached.add(source)
        body = source.read_text(encoding="utf-8")
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", body):
            raw = link.split("#", 1)[0]
            if not raw or "://" in raw or raw.startswith("mailto:"):
                continue
            target = (source.parent / raw).resolve()
            if not target.is_relative_to(root.resolve()):
                errors.append(f"{source.name}: link escapes skill: {link}")
            elif not target.is_file():
                errors.append(f"{source.name}: missing link: {link}")
            elif target.suffix == ".md":
                pending.append(target)
    for ref in (root / "references").glob("*.md"):
        if ref.resolve() not in reached:
            errors.append(f"unreachable reference: {ref.name}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / NAME)
    args = parser.parse_args()
    errors = validate(args.root)
    for error in errors:
        print(error)
    if not errors:
        print("Skill structure and metadata are valid.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
