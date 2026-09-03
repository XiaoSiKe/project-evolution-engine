#!/usr/bin/env python3
"""Exercise real Serena symbols and refresh-context behavior in isolated fixtures."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "project-evolution-engine/scripts"))
import refresh_context as context
import serena_mcp as bridge


def files(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts}


def text_result(result):
    if result.isError:
        raise AssertionError("MCP returned isError")
    text = "\n".join(block.text for block in result.content if block.type == "text")
    return json.loads(text)


def fixture(root, language, *, other=False):
    (root / "app").mkdir(parents=True)
    if language == "python":
        (root / "app/__init__.py").write_text("")
        (root / "app/pricing.py").write_text(
            "def shipping_fee(total, member=False):\n    return " + ("99" if other else "0 if total >= 100 else 5") + "\n")
        (root / "app/api.py").write_text("from .pricing import shipping_fee as fee\n\ndef quote(total, member=False):\n    return fee(total, member)\n")
        (root / "pyproject.toml").write_text('[project]\nname = "evolution-integration-fixture"\nversion = "0.0.0"\n')
        return "shipping_fee", "app/pricing.py", "app/api.py", "app/worker.py"
    (root / "app/pricing.ts").write_text(
        "export function shippingFee(total: number, member = false): number {\n  return " +
        ("99" if other else "total >= 100 ? 0 : 5") + ";\n}\n")
    (root / "app/api.ts").write_text("import { shippingFee as fee } from './pricing.ts';\nexport function quote(total: number, member = false) { return fee(total, member); }\n")
    (root / "package.json").write_text('{"name":"evolution-integration-fixture","version":"0.0.0","type":"module"}\n')
    (root / "tsconfig.json").write_text('{"compilerOptions":{"target":"ES2022","module":"NodeNext","moduleResolution":"NodeNext","allowImportingTsExtensions":true,"noEmit":true},"include":["app/**/*.ts"]}\n')
    return "shippingFee", "app/pricing.ts", "app/api.ts", "app/worker.ts"


async def scenario(base, language, executable):
    project = base / language / "project"
    symbol, owner, api, worker = fixture(project, language)
    state = base / language / "state"
    suffix = "py" if language == "python" else "ts"
    draft = {
        "schema_version": 1,
        "queries": [{"id": "fee-users", "include": [f"app/**/*.{suffix}"], "terms": [symbol]}],
        "facts": [
            {"id": "fee-rule", "kind": "implementation", "statement": "All orders ship free at 100",
             "evidence": [{"path": owner}], "queries": ["fee-users"], "depends_on": []},
            {"id": "api-rule", "kind": "implementation", "statement": "API delegates to the fee owner",
             "evidence": [{"path": api}], "queries": [], "depends_on": ["fee-rule"]},
        ],
    }
    record = context.capture(draft, project)
    calls, checks = [], []
    async with bridge.connect(project, state, executable) as (session, schemas, metadata):
        checks.append({"id": "real_stdio_server", "passed": metadata["server_info"]["name"] == "Serena"})

        async def call(name, arguments):
            bridge.validate_request({"tool": name, "arguments": arguments}, project, schemas)
            before = files(project)
            raw = await session.call_tool(name, arguments)
            assert files(project) == before, "query changed project files"
            value = text_result(raw)
            calls.append({"tool": name, "arguments": arguments, "result": value})
            return value

        definitions = await call("find_symbol", {"name_path_pattern": symbol, "relative_path": owner, "include_body": True})
        entry = next(item for item in definitions if item["name_path"] == symbol)
        source = (project / owner).read_text().splitlines()
        location = entry["body_location"]
        actual_body = "\n".join(source[location["start_line"]:location["end_line"] + 1]).strip()
        assert actual_body == entry["body"].strip()
        checks.append({"id": "definition_matches_current_file_and_zero_based_range", "passed": True})
        references = await call("find_referencing_symbols", {"name_path": symbol, "relative_path": owner})
        assert api in references, references
        checks.append({"id": "aliased_import_resolves_to_owner", "passed": True})

        if language == "python":
            (project / worker).write_text("from .pricing import shipping_fee as fee\n\ndef batch(orders):\n    return [fee(total, member) for total, member in orders]\n")
            (project / owner).write_text("def shipping_fee(total, member=False):\n    threshold = 80 if member else 100\n    return 0 if total >= threshold else 5\n")
            runtime = subprocess.run([sys.executable, "-B", "-c",
                                      "from app.api import quote; from app.worker import batch; assert quote(80, True)==0; assert quote(80)==5; assert batch([(79,True),(100,False)])==[5,0]"],
                                     cwd=project, capture_output=True, text=True)
        else:
            (project / worker).write_text("import { shippingFee as fee } from './pricing.ts';\nexport function batch(orders: [number, boolean][]) { return orders.map(([total, member]) => fee(total, member)); }\n")
            (project / owner).write_text("export function shippingFee(total: number, member = false): number {\n  const threshold = member ? 80 : 100;\n  return total >= threshold ? 0 : 5;\n}\n")
            runtime = subprocess.run(["node", "--input-type=module", "-e",
                                      "import assert from 'node:assert/strict'; import {quote} from './app/api.ts'; import {batch} from './app/worker.ts'; assert.equal(quote(80,true),0); assert.equal(quote(80),5); assert.deepEqual(batch([[79,true],[100,false]]),[5,0]);"],
                                     cwd=project, capture_output=True, text=True)
        assert runtime.returncode == 0, runtime.stderr
        checks.append({"id": "new_member_rule_and_preserved_nonmember_behavior", "passed": True})
        updated = context.refresh(record, project)
        assert worker in [hit["path"] for hit in updated["report"]["new_reference_candidates"]]
        assert set(updated["_state"]["pending"]) == {"fee-rule", "api-rule"}
        checks.append({"id": "new_consumer_invalidates_context_and_dependents", "passed": True})

        # Read the changed/new files through the live server before retracing references.
        await call("get_symbols_overview", {"relative_path": worker})
        definitions = await call("find_symbol", {"name_path_pattern": symbol, "relative_path": owner, "include_body": True})
        assert "80" in definitions[0]["body"]
        references = await call("find_referencing_symbols", {"name_path": symbol, "relative_path": owner})
        assert worker in references and api in references, references
        checks.append({"id": "live_server_sees_new_reference_and_changed_definition", "passed": True})
        updated["facts"][0]["statement"] = "Members ship free at 80; other orders at 100"
        updated["facts"][1]["statement"] = "API and worker delegate to the shared fee owner"
        updated["facts"][1]["evidence"].append({"path": worker})
        reviewed = context.refresh(updated, project)
        confirmed = context.confirm(reviewed, project, ["fee-rule", "api-rule"], reviewed["report"]["snapshot_id"],
                                    "Read updated definitions and semantic references, ran member/nonmember and batch behavior.")
        assert confirmed["report"]["ready"]
        checks.append({"id": "reviewed_statements_and_evidence_become_current", "passed": True})
        try:
            bridge.validate_request({"tool": "find_symbol", "arguments": {"name_path_pattern": symbol, "relative_path": "../outside.py"}},
                                    project, schemas)
        except ValueError:
            checks.append({"id": "escaping_query_is_rejected", "passed": True})
        else:
            raise AssertionError("escaping query accepted")

    # A partially cleared cache must not make Serena adopt project-local user settings.
    (state / "project").rename(state / "project-before-clear")
    user_config = project / ".serena/project.yml"
    user_config.parent.mkdir()
    user_config.write_text("project_name: user-owned-settings\n")
    before_reuse = files(project)
    async with bridge.connect(project, state, executable) as (session, _, reuse_metadata):
        raw = await session.call_tool("find_symbol", {"name_path_pattern": symbol, "relative_path": owner, "include_body": True})
        assert "80" in text_result(raw)[0]["body"]
        assert reuse_metadata["activation"] is None
    assert files(project) == before_reuse, "state reuse touched project-local configuration"
    checks.append({"id": "cleared_state_reuse_preserves_user_project_configuration", "passed": True})

    other = base / language / "other/project"
    fixture(other, language, other=True)
    try:
        bridge.prepare_state(other, state)
    except ValueError:
        checks.append({"id": "same_basename_wrong_project_state_is_rejected", "passed": True})
    else:
        raise AssertionError("wrong project accepted")
    async with bridge.connect(other, base / language / "other-state", executable) as (session, schemas, _):
        raw = await session.call_tool("find_symbol", {"name_path_pattern": symbol, "relative_path": owner, "include_body": True})
        assert "99" in text_result(raw)[0]["body"]
        checks.append({"id": "separate_state_returns_other_project_definition", "passed": True})
    result = {"language": language, "passed": all(c["passed"] for c in checks), "checks": checks,
              "connection": metadata, "calls": calls, "context_after_review": confirmed,
              "runtime_check": {"exit_code": runtime.returncode, "stdout": runtime.stdout, "stderr": runtime.stderr}}
    (base / f"{language}-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


async def run(args):
    if args.output.exists():
        raise ValueError("use a new isolated output directory")
    output = args.output.expanduser().resolve()
    if output.is_relative_to(ROOT) or output in {Path("/"), Path.home().resolve()}:
        raise ValueError("output must be outside the project")
    output.mkdir(parents=True)
    results = []
    for language in args.languages:
        try:
            result = await scenario(output, language, args.serena)
            results.append(result)
            print(json.dumps({"language": language, "passed": result["passed"], "checks": len(result["checks"])}), flush=True)
        except Exception as error:
            result = {"language": language, "passed": False, "error": bridge.error_text(error)}
            (output / f"{language}-error.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serena", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--languages", nargs="+", choices=("python", "typescript"), default=["python", "typescript"])
    raise SystemExit(asyncio.run(run(parser.parse_args())))
