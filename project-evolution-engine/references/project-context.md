# Project context

Build the amount of understanding needed to make this update coherent. A project map is a navigation aid, not a second specification.

## Read existing knowledge first

Look for repository instructions, domain vocabulary, accepted architectural decisions, maintained design documents, and relevant tests. Verify their named files and entry points still exist.

For an unfamiliar area, identify these dimensions only as needed:

- purpose and observable behavior;
- entry points, layers, module responsibilities, and ownership;
- data and control flow, external boundaries, and actual consumers;
- project-specific naming, dependency direction, and error conventions;
- test locations, generators, configuration, and runnable checks;
- known constraints and uncertainty affecting this change.

Follow concrete symbols and callers into their logical blocks. Distinguish a current implementation fact, an accepted rule, an inference, and a hypothesis. Do not promote repeated buggy code into an authoritative business rule.

## Keep knowledge local and useful

Capture non-obvious conventions with a code reference and, when available, their reason. Use existing documents and links rather than copying the same rule into several new files.

A local feature does not require a full repository map or seven new documents. A missing context document is not a blocker when the necessary facts can be established from code.

When a multi-session change needs a durable plan, use the project's established place. Include scope, decisions, verified owners, acceptance checks, and progress. Avoid copying entire files or generating an inventory of every function.

## Revalidate context

Before relying on a previous map or plan:

1. Verify the target paths and symbols in the current working tree.
2. Compare the relevant rules, implementation, consumers, and tests with the evidence used earlier.
3. Include staged, unstaged, and relevant untracked changes; HEAD equality is insufficient.
4. Re-trace new consumers when the change affects a public boundary.
5. Refresh only the affected knowledge.

A change in another subsystem does not automatically invalidate every fact. A file fingerprint detects declared file changes but cannot discover a new undeclared caller, dynamic dependency, external consumer, or runtime state.

For a maintained context record, the optional [incremental-context helper](incremental-context.md) also reruns declared reference searches and propagates invalidation through fact dependencies. It can discover new textual reference candidates within those searches. Read them as candidates, confirm semantic references with available tools and code, and update the affected statements before confirmation.

The bundled collector supplies repository metadata and heuristics. Its limitations travel with its output. Neither a fingerprint nor a graph proves correct placement or complete impact coverage.

## After implementation

Update documents that would otherwise contradict the new behavior. Keep verified new reasoning only when it is not recoverable from the final code, tests, or existing docs and losing it would cause substantial rediscovery or repeated mistakes.
