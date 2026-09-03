# Verification

Verify two things separately: the requested behavior exists, and the relevant preserved behavior still works.

## Choose evidence before implementation

For each outcome, identify an observable check at the interface a real caller uses. Run a proportionate baseline when it provides useful evidence.

Examples:

| Update | New behavior | Preserved behavior |
| --- | --- | --- |
| Batch operation | Several inputs use the established policy and formatting | Single-item operation and rejection behavior |
| New optional argument | Its specified effect | Existing calls that omit it |
| Added generated type | Canonical schema and generated output agree | Existing values, order, and generator idempotence |
| New role | Newly permitted operation | Existing roles and denied operations |
| Intentional rule change | Latest authorized rule | Unchanged rules and consumers |

Do not equate a successful linter with a working build, passing package tests with a correct feature, or a specialist's success message with observed behavior.

## Verify the final combined state

Check the relevant subset:

- focused behavior tests and affected existing tests;
- build, types, lint, or a reproducible user flow;
- relevant invalid inputs and error paths;
- generated files and idempotence;
- schema/configuration and migration compatibility when changed;
- docs and examples that state the changed contract;
- final diff for scope, lost user edits, duplicate policy, and temporary residue.

Broaden testing to resolve a concrete risk or satisfy the project's gate. Do not rerun unrelated suites indefinitely after the outcome is sufficiently verified.

## Evidence freshness

Rerun affected checks when implementation or its evidence changes. A previous passing result does not validate a later edit. An unrelated documentation edit need not invalidate an executable behavior check, but its own links or examples may need checking.

An inventory or fingerprint establishes what was observed. It does not establish semantic correctness, dependency completeness, or authority to modify code.

## Reporting

Label checks as passed, failed, or not run, with actual commands and useful outcome detail. Separate pre-existing failures from new regressions and unverified surfaces.

For partial completion, identify finished outcomes and the exact blocker. For an unavailable environment or optional tool, explain the practical coverage gap without claiming an execution that did not occur.

Only report a test count from its actual run. A CI badge reports CI status; independent behavior evaluations and live optional integrations have their own evidence.
