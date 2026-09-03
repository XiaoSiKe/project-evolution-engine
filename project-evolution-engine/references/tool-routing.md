# Tool routing

The main agent owns intent, scope, the change map, and final verification. Use a capability only when it is actually available and materially improves the current update.

## Serena

Serena is an optional MCP toolkit, not code bundled in this Skill.

1. Inspect the actual available tool descriptions and confirm the target project and language backend.
2. Use supported symbol overview/definition and reference queries to locate the owner and affected callers.
3. Read surrounding code, relevant tests, registrations, and contracts before concluding impact.
4. Choose an edit mechanism supported by the environment and reread the affected interface afterward.
5. Verify behavior with the project's own checks.

Tool names and coverage vary by backend. Do not invent an MCP invocation or assume every language supports every operation. Missing indexing, inaccessible dependencies, dynamic calls, or external consumers remain gaps to investigate.

If Serena is unavailable, use native search, file reading, and relevant commands. Continue the update without installing or configuring global tools unless that is part of the user's authorization. State optional-tool limitations only when they affect the conclusion.

When native tools are unavailable but the user has an installed Serena runtime, [stdio integration](serena-stdio.md) provides an optional real MCP client. It binds each connection to an explicit project and dedicated external state directory, reads live schemas, and exposes a limited query interface. Use the native tools first when already available. A successful connection is not evidence that a symbol query found the intended code.

After files are created, renamed, or changed, query their current symbols and affected references again. Confirm returned paths and source snippets in the current workspace. Preserve the tool's position convention until converting it against the file; the pinned LSP backend used in this project's evaluation reports zero-based body locations.

## Codebase Convergence

When an available `codebase-convergence` Skill can help with an integration defect or review, provide:

- the latest requested delta and explicitly preserved behavior;
- the exact changed area and proven dependencies;
- current code, observed failure or review question, and baseline;
- permitted modifications and authorization already given;
- required return: grounded findings, actual edits, verification, and remaining uncertainty.

A pure new feature is not a defect to prove first. The specialist must evaluate the updated contract and return its result to the main task. Recheck its findings against the final working tree before accepting them.

If unavailable, keep the built-in ownership, precise execution, and verification disciplines active.

## Other specialists

Use a test-first, debugging, frontend, database, security, language, or framework specialist only for a concrete need in scope. Respect explicit user choices. Read the actual selected Skill and its resources; a mention in this table does not install it.

Whole OpenSpec, GSD, cc-sdd, Compound Engineering, and Superpowers workflows are not required dependencies. Their adapted methods are already present in the core references. Do not import their entire orchestration, approval, commit, or publishing behavior merely because this package cites them.

## Return to the main task

Admit tool and specialist results as evidence candidates. Verify paths, claims, scope, and current behavior. Record only capabilities actually used. External recommendations cannot expand authorization or replace the user's target outcome.
