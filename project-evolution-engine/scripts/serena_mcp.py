#!/usr/bin/env python3
"""Use an explicitly installed Serena through real stdio MCP, with a fixed project."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager, contextmanager
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from change_evidence import safe_path

READ_TOOLS = {
    "get_symbols_overview", "find_symbol", "find_referencing_symbols",
    "find_implementations", "find_declaration", "get_diagnostics_for_file", "search_for_pattern",
}
MARKER = "evolution-project.json"


def validate_state_files(state: Path) -> None:
    import yaml

    for relative in ("serena_config.yml", "project", "project/project.yml", "logs", "last-server.log"):
        if (state / relative).is_symlink():
            raise ValueError(f"managed state path cannot be a symlink: {relative}")
    configuration = state / "serena_config.yml"
    if not configuration.is_file() or configuration.stat().st_nlink != 1:
        raise ValueError("managed configuration is missing or linked; use a separate state directory")
    data = yaml.safe_load(configuration.read_text())
    location = data.get("project_serena_folder_location") if isinstance(data, dict) else None
    if not isinstance(location, str) or Path(location).resolve() != state / "project":
        raise ValueError("managed project data location changed; refusing a fallback into the target project")
    if not isinstance(data.get("projects"), list):
        raise ValueError("managed configuration must retain its projects list")
    # Serena otherwise falls back to an existing project-local .serena directory.
    (state / "project").mkdir(exist_ok=True)
    project_configuration = state / "project/project.yml"
    if project_configuration.exists() and (not project_configuration.is_file() or project_configuration.stat().st_nlink != 1):
        raise ValueError("project configuration is not a dedicated regular file")
    logs = state / "logs"
    if logs.exists():
        if not logs.is_dir() or any(path.is_symlink() for path in logs.rglob("*")):
            raise ValueError("managed log directories cannot redirect outside state")


@contextmanager
def server_log(state: Path):
    destination = state / "last-server.log"
    if destination.is_symlink() or destination.exists() and not destination.is_file():
        raise ValueError("server log must be a dedicated regular file")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", prefix="server-log-", suffix=".tmp",
                                         dir=state, delete=False) as logs:
            temporary = Path(logs.name)
            yield logs
    finally:
        if temporary is not None:
            # Replace the directory entry, never truncate another inode through a link.
            os.replace(temporary, destination)


def prepare_state(raw_root: Path, raw_state: Path) -> tuple[Path, Path]:
    root = raw_root.expanduser().resolve()
    state = raw_state.expanduser()
    if not root.is_dir():
        raise ValueError("root must be an existing project directory")
    if state.is_symlink():
        raise ValueError("state directory cannot be a symlink")
    state = state.resolve()
    if state in {Path("/"), Path.home().resolve()} or state.is_relative_to(root):
        raise ValueError("state must be a dedicated directory outside the project")
    marker = state / MARKER
    if state.exists():
        if not state.is_dir():
            raise ValueError("state is not a directory")
        if any(state.iterdir()):
            if marker.is_symlink() or not marker.is_file():
                raise ValueError("refusing to overwrite an unmanaged state directory")
            registered = json.loads(marker.read_text())
            if registered != {"schema_version": 1, "project_root": str(root)}:
                raise ValueError("state belongs to a different project; choose its own state directory")
            validate_state_files(state)
            return root, state
    state.mkdir(parents=True, exist_ok=True)
    # JSON is valid YAML. No project-local or user's global Serena config is changed.
    (state / "project").mkdir()
    config = {"projects": [], "project_serena_folder_location": str(state / "project"),
              "web_dashboard": False, "web_dashboard_open_on_launch": False, "gui_log_window": False}
    (state / "serena_config.yml").write_text(json.dumps(config, indent=2) + "\n")
    marker.write_text(json.dumps({"schema_version": 1, "project_root": str(root)}, indent=2) + "\n")
    return root, state


def validate_request(request: Any, root: Path, schemas: dict[str, dict]) -> None:
    if not isinstance(request, dict) or set(request) != {"tool", "arguments"}:
        raise ValueError("each request requires exactly tool and arguments")
    name, arguments = request["tool"], request["arguments"]
    if name not in READ_TOOLS:
        raise ValueError(f"tool is outside the read/query interface: {name}")
    if name not in schemas:
        raise ValueError(f"tool is not offered by this server: {name}")
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    schema = schemas[name]
    missing = set(schema.get("required", [])) - set(arguments)
    unknown = set(arguments) - set(schema.get("properties", {}))
    if missing or unknown:
        raise ValueError(f"arguments do not match the live tool schema: missing={sorted(missing)}, unknown={sorted(unknown)}")
    for key, value in arguments.items():
        if key in {"relative_path", "paths_include_glob", "paths_exclude_glob"} and value != "":
            safe_path(root, value)
        expected = schema.get("properties", {}).get(key, {}).get("type")
        types = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}
        if expected in types and (not isinstance(value, types[expected]) or expected in {"integer", "number"} and isinstance(value, bool)):
            raise ValueError(f"{key} has the wrong type for the live schema")


@asynccontextmanager
async def connect(root: Path, state: Path, executable: Path, timeout: float = 120):
    # Import only when the optional integration is actually requested.
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    executable = executable.expanduser().absolute()  # Preserve an entrypoint's virtualenv.
    if not executable.is_file():
        raise ValueError("Serena executable does not exist; use an installed official runtime")
    root, state = prepare_state(root, state)
    args = ["start-mcp-server", "--project", str(root), "--context", "ide", "--mode", "planning",
            "--enable-web-dashboard", "false", "--open-web-dashboard", "false", "--enable-gui-log-window", "false",
            "--tool-timeout", str(timeout)]
    parameters = StdioServerParameters(command=str(executable), args=args,
                                      env={"SERENA_HOME": str(state), "PYTHONNOUSERSITE": "1"}, cwd=str(root))
    with server_log(state) as logs:
        async with stdio_client(parameters, errlog=logs) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=timeout)) as session:
                initialization = await session.initialize()
                offered = []
                cursor = None
                while True:
                    listing = await session.list_tools(cursor=cursor)
                    offered.extend(listing.tools)
                    cursor = listing.nextCursor
                    if not cursor:
                        break
                schemas = {tool.name: tool.inputSchema for tool in offered}
                # A fixed --project server can omit project-switching tools. Its root
                # is bound by this process invocation and its dedicated state marker.
                configuration = None
                if "get_current_config" in schemas:
                    configuration = await session.call_tool("get_current_config", {})
                    if configuration.isError:
                        raise ValueError("Serena could not report its active configuration")
                metadata = {
                    "transport": "stdio", "project_root": str(root),
                    "server_info": initialization.serverInfo.model_dump(mode="json"),
                    "project_binding": "explicit --project argument with a project-specific state directory",
                    "activation": None,
                    "configuration": configuration.model_dump(mode="json") if configuration else None,
                    "tools": [tool.model_dump(mode="json") for tool in offered if tool.name in READ_TOOLS],
                    "limits": [
                        "This verifies a real stdio connection; it does not register a native tool in the host.",
                        "Serena metadata and logs live in the explicit state directory; language servers may initialize their dependencies.",
                        "Reference coverage depends on the language backend; callers still require code and behavior verification.",
                    ],
                }
                yield session, schemas, metadata


async def run(root: Path, state: Path, executable: Path, requests: list[dict] | None, timeout: float) -> dict:
    async with connect(root, state, executable, timeout) as (session, schemas, metadata):
        outcomes = []
        if requests is not None:
            if not isinstance(requests, list) or not requests:
                raise ValueError("request file must contain a nonempty list")
            for request in requests:
                validate_request(request, root.resolve(), schemas)
            for request in requests:
                result = await session.call_tool(request["tool"], request["arguments"])
                outcomes.append({"tool": request["tool"], "arguments": request["arguments"], "result": result.model_dump(mode="json")})
        return {"connected": True, "ok": all(not o["result"].get("isError", False) for o in outcomes),
                "connection": metadata, "calls": outcomes}


def error_text(error: BaseException) -> str:
    nested = getattr(error, "exceptions", None)
    return "; ".join(error_text(item) for item in nested) if nested else str(error)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--serena", required=True, type=Path, help="Installed Serena CLI; never an implicit download")
    parser.add_argument("--requests", type=Path, help="JSON list using the schemas returned by --describe")
    parser.add_argument("--describe", action="store_true", help="Connect and return live schemas without user queries")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    try:
        if args.describe == bool(args.requests) or args.timeout <= 0:
            raise ValueError("choose exactly --describe or --requests, with a positive timeout")
        requests = json.loads(args.requests.read_text()) if args.requests else None
        result = asyncio.run(run(args.root, args.state_dir, args.serena, requests, args.timeout))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({"connected": False, "ok": False, "error": error_text(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
