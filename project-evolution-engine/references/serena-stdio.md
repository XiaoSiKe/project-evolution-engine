# Optional Serena stdio integration

Prefer already available native Serena tools. This bridge is for an explicitly installed official Serena runtime when the host does not expose native tools, or for reproducible integration checks. It communicates with the real MCP server using the MCP Python SDK; it is not a simulated symbol lookup.

## Runtime and project binding

The integration-tested source is [oraios/serena at 813fd98f4fd32e0606cb52281467fc055e45a356](https://github.com/oraios/serena/tree/813fd98f4fd32e0606cb52281467fc055e45a356), with MCP Python SDK 1.28.1. The Serena environment already includes the SDK. The main Skill and its other helpers do not require this optional dependency.

Use the Serena environment's Python and its executable. Do not resolve a virtualenv executable's symlink into another interpreter. Never install or configure tools just because a source is cited; use existing authorization or an already installed runtime.

On a host configured for this package, `~/.local/share/project-evolution-engine/serena-runtime.json` may provide the installed `python`, `serena`, and `state_base` paths. Read that file only if it exists; these are local runtime locations, not shared Skill instructions. Choose a separate child of `state_base` for each canonical project path, for example using its SHA-256. If the manifest or runtime is absent, continue with native tools instead of installing anything implicitly.

Supply the exact project root and a dedicated state directory outside it. The bridge creates its own state marker and Serena configuration, launches the server with an explicit project, and avoids the user's global Serena configuration. Reusing a state directory for a different project is rejected. Keep state directories separate even when projects share a folder name.

Serena may initialize language-server dependencies. Its project metadata, cache and logs use the dedicated state directory. The bridge starts no web dashboard or GUI log window and does not register a native tool in Codex.

## Discover, then call

First retrieve the available query tools and their actual argument schemas:

```bash
<serena-python> <skill-directory>/scripts/serena_mcp.py --root <project> --state-dir <external-state-directory> --serena <serena-executable> --describe
```

Prepare a JSON list using those schemas. For the tested version, a symbol request can look like:

```json
[
  {
    "tool": "find_symbol",
    "arguments": {
      "relative_path": "src/policy.py",
      "name_path_pattern": "apply_policy",
      "include_body": true
    }
  }
]
```

```bash
<serena-python> <skill-directory>/scripts/serena_mcp.py --root <project> --state-dir <external-state-directory> --serena <serena-executable> --requests /tmp/serena-queries.json
```

The bridge allows definition, overview, reference, implementation/declaration, diagnostics and text-search operations only when the server offers them. It rejects project-switching requests, write tools, escaping paths, unknown parameters, and known schema type mismatches. The server handles full argument validation.

A server started with a fixed project may omit activation/configuration tools. The bridge relies on its explicit project binding and never calls project-switching tools, even if a custom context exposes them. It reads current configuration only if that read tool is offered.

## Interpret evidence

The result contains connection metadata, live schemas, actual calls, and their returned content. `connected` and `ok` describe protocol execution, not whether a symbol existed, all callers were found, or the feature is correct. Check for backend errors in returned content, empty results, ambiguity, and missing coverage.

Read returned paths and source ranges against actual files. The pinned LSP backend uses zero-based body locations. Re-query current files after edits, creation or moves; do not treat a prior query as current evidence merely because the server remains connected.

If the server or a language backend is unavailable, preserve the error and continue with current search, code reading and tests. An optional integration failure does not turn a clear update into a request to change global configuration.
