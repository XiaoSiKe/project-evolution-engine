# Change evidence

Use a compact evidence record when an update crosses module boundaries, changes compatibility-sensitive behavior, or relies on context that must survive a handoff. A small local update can keep the same reasoning in conversation.

## Record the three verification surfaces

For every outcome distinguish:

- **new**: the requested capability exists;
- **integration**: it follows the established owner, policy, and consumer interfaces;
- **preserved**: the relevant existing calls, data, and failure behavior survive.

One real check may cover several surfaces. A planned check is explicitly not-run. For existing databases, verify a populated old database and repeatability of the migration; a newly initialized empty database alone is insufficient. For a frontend update, follow user events through state, rendering, and persistence, including changes made between the new operation and its reversal.

List confirmed consumers and unresolved impact separately. A repository search can miss dynamic or external consumers; record that gap instead of labelling the list exhaustive.

## Optional read-only helper

The bundled helper stamps only declared files and textual anchors:

```bash
python3 <skill-directory>/scripts/change_evidence.py stamp --root <project> --record /tmp/change-draft.json > /tmp/change-evidence.json
python3 <skill-directory>/scripts/change_evidence.py check --root <project> --record /tmp/change-evidence.json
```

Keep these task artifacts outside the target project unless the user asks for a durable project record. Prefer its existing documentation location when one is needed.

A record has this shape (replace example paths and commands with observed project evidence):

```json
{
  "schema_version": 1,
  "goals": [{
    "id": "batch",
    "change": "Add ordered batch export using existing export policy",
    "preserved": ["Single-record export and rejection behavior"],
    "owners": ["app/exporter.py"],
    "consumers": ["tests/test_exporter.py"],
    "checks": ["exports"]
  }],
  "files": [
    {"path": "app/exporter.py", "role": "owner", "anchor": "def export_one("},
    {"path": "tests/test_exporter.py", "role": "test"}
  ],
  "checks": [{
    "id": "exports",
    "kinds": ["new", "integration", "preserved"],
    "command": "python -m unittest discover -s tests",
    "status": "not-run",
    "reason": "Implementation has not begun"
  }],
  "unknowns": []
}
```

File roles are owner, consumer, test, contract, or planned. A planned path may be absent, and its later creation makes the old evidence stale. Current paths must exist at stamp time. Anchors are optional unique UTF-8 text, not a compiler's symbol identity.

Checks use passed, failed, or not-run. A passed/failed result includes observed evidence; a not-run check includes a reason. When an exit code is supplied for a passed command it must be zero.

## Interpret the result

- stamp returns the record with per-file observations in basis.
- check returns current, stale, or unknown file evidence, changed paths, anchor problems, verification gaps, and declared unknowns.
- Exit 0 means the stamp succeeded or declared file evidence is current; exit 1 means stale/unknown evidence; exit 2 means invalid input or an unsafe path.
- Exit 0 does not mean the feature works. Inspect verification gaps and actual command results.
- The helper neither executes recorded commands nor certifies their reported results, ownership, completeness, or authorization.

After changing relevant files, re-read their owners and consumers, rerun affected checks, and then stamp an updated record. Do not restamp blindly just to make a stale warning disappear. A new undeclared caller is invisible to the fingerprints and must be sought through current search or a supported symbol tool.
