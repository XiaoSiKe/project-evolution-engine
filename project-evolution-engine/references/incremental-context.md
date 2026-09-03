# Incremental project context

Use this when previous project reasoning will be reused across updates, when new consumers are likely, or when a handoff needs evidence. Keep a small one-shot update lightweight. Prefer links to authoritative project documents over duplicating their business rules.

## A complete refresh cycle

1. Record a few relevant facts, their current file evidence, and searches that can reveal consumers. Distinguish implementation facts, accepted decisions, and inferences.
2. Before reusing the record, refresh it against current files. Inspect new, modified, and removed reference candidates, affected facts, and coverage gaps.
3. Read affected code and actual callers. Use a supported symbol tool when available. A literal match can be a comment, import, or unrelated same-named symbol.
4. Correct outdated statements, evidence paths, and dependencies in the record and affected authoritative documents. Verify the requested behavior using the project's real checks.
5. Refresh the revised record, then confirm only the facts actually reviewed against that snapshot. If evidence changes again, refresh and review the affected portion again.

Do not clear pending review by creating another baseline. Repeated refreshes deliberately retain pending facts, even if files later revert. A dependent fact cannot be confirmed while a dependency is pending, unless that dependency is reviewed in the same confirmation.

## Record format

The optional standard-library helper accepts a draft like this:

```json
{
  "schema_version": 1,
  "queries": [{
    "id": "policy-consumers",
    "include": ["src/**/*.py"],
    "exclude": ["src/vendor/**"],
    "terms": ["apply_policy"],
    "match": "identifier"
  }],
  "facts": [{
    "id": "policy-owner",
    "kind": "implementation",
    "statement": "The shared policy is owned by the policy module",
    "evidence": [{"path": "src/policy.py", "anchor": "def apply_policy("}],
    "queries": ["policy-consumers"],
    "depends_on": []
  }]
}
```

Every fact needs file evidence. Optional anchors must match unique current text. Queries use project-relative file globs: `*` stays within a path segment; `**` matches zero or more segments. `identifier` uses identifier boundaries; `literal` supports other exact text. Both search text, without proving symbol identity. Use appropriate include patterns for the project's languages.

Facts can depend on other facts by ID. Dependencies must be acyclic. New facts and edited declarations require review. To retire facts, update the authoritative document and deliberately create a new context record; do not silently drop unresolved facts from a captured record.

## Commands

Keep task records outside the project unless a durable record is requested or an existing project convention provides its location:

```bash
python3 <skill-directory>/scripts/refresh_context.py capture --root <project> --record /tmp/context-draft.json > /tmp/context.json
python3 <skill-directory>/scripts/refresh_context.py refresh --root <project> --record /tmp/context.json > /tmp/context-pending.json
```

Read the returned report and affected code. After updating the record and running relevant checks, refresh again and use that report's `snapshot_id`:

```bash
python3 <skill-directory>/scripts/refresh_context.py confirm --root <project> --record /tmp/context-pending.json --facts policy-owner --against <snapshot-id> --note "What was read, verified, and updated" > /tmp/context-reviewed.json
```

This confirmation is performed by the working agent after verification. It is not an extra user approval gate.

The tool keeps accepted evidence under `_state.basis` and pending fact IDs under `_state.pending`. `report` contains per-fact status, changed evidence, reference changes, new candidates, scan gaps, and the snapshot identifier. Preserve these fields between invocations.

Exit 0 means no fact is pending; exit 1 means review is needed; exit 2 means invalid input or an execution error. A current record does not certify its statements or substitute for behavioral tests.

## Coverage boundaries

Searches skip `.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.serena`, `.pytest_cache`, `dist`, and `build`. Source generators and their canonical files should be declared directly when relevant. Symlink, unreadable, non-UTF-8, and oversized content within a query's scope becomes an explicit coverage gap. The default limits are 20,000 matching files and 2,000,000 bytes per searched file.

New imports, including many aliased imports, can reveal candidates because the original identifier is present in text. Dynamic construction, wildcard imports, indirect calls, external consumers, and runtime state can evade a declared search. Record and investigate those limits where they matter. The helper rechecks selected file scopes and updates only affected fact states; it is not a background indexer or an automatically authoritative knowledge base.
