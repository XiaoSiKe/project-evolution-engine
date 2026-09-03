---
name: project-evolution-engine
description: "Evolve an existing software project by adding features, extending capabilities, or changing workflows: understand current code, locate integration points, implement the requested delta, and verify new and preserved behavior. Use for 项目更新、功能添加、版本迭代 and implementation planning on an existing codebase; not for greenfield scaffolding or pure bug-fixing and cleanup without an update goal."
license: MIT
---

# Project Evolution Engine

Read the existing project and make the requested update fit its actual responsibilities, interfaces, rules, and callers. Deliver working changes with evidence for both the new behavior and the behavior that must survive.

## Two built-in disciplines

1. **Precise execution.** Make assumptions visible, choose the smallest complete change, preserve unrelated work, and tie every edit to the requested outcome or a necessary integration repair.
2. **Responsibility and locality.** Place each rule, state transition, and failure policy in its actual owning module. Reuse that owner through the interface its callers use. A small patch is incomplete when it leaves the same rule scattered across callers.

These disciplines are part of this package. No other Skill or MCP server is required.

## Apply the Skill

Read [Execution workflow](references/execution-workflow.md) and scale it to the requested change. Start with a short update brief covering the intended change, preserved behavior, relevant scope, material assumptions, and observable acceptance checks.

A new requirement is sufficient grounds for an update. It does not need an existing bug or a Finding. Respect planning-only or review-only requests without mutating the project.

Load supporting material only when the change needs it:

- use [Project context](references/project-context.md) when current responsibilities or conventions are unclear;
- use [Incremental context](references/incremental-context.md) when prior reasoning must be refreshed or handed off;
- use [Integration analysis](references/integration-analysis.md) for non-trivial or cross-module placement;
- use [Change evidence](references/change-evidence.md) for consequential compatibility or cross-layer evidence;
- use [Verification](references/verification.md) to design checks for new, integrated, and preserved behavior.

## Operating boundaries

- Read enough to justify the proposed location and impact. File names, search hits, a graph, and a scanner are leads until grounded in actual code and callers.
- Preserve user edits, including unrelated edits within a file you must change. Read the current file immediately before editing; never reset, overwrite, stage, or clean unrelated state.
- Keep one authority for a business rule. Conflicting documentation is a question to investigate, not permission to invent a value.
- Distinguish an authorized new contract from an unresolved product choice. Complete independent work before returning one focused question when a material ambiguity blocks the rest.
- Treat generated artifacts through their source chain. Change the source when it is wrong; rerun the generator when only the output is stale.
- Recheck relevant context when its code, callers, tests, or rules change. A matching Git commit alone does not prove an uncommitted workspace or external service is unchanged.
- Do not turn a local update into an unsolicited rewrite, whole-project audit, dependency upgrade, or release.
- Permission to update a target project does not automatically authorize committing, pushing, deploying, installing global tools, or contacting others. Honor explicit authorization already given in the session.
- Do not promise perfect integration or universal correctness. Report the actual evidence and its limits.

## Optional tools and specialists

Read [Tool routing](references/tool-routing.md) only when an available capability would materially help the current work.

- Use Serena for supported symbol definitions and references when its tools are actually available and point to this project. Native search and file reading remain a complete fallback.
- Use an available `codebase-convergence` for a bounded integration defect or review, with the new contract and protected behavior included in its task.
- Use other specialists only when their expertise is relevant and their instructions and tools are available.

A named Skill is not an installed dependency, and a described MCP call is not an executed call. The main agent owns the change map, authorization, and final verification.

For a broad inventory, the bundled read-only helper is available:

```bash
python3 <skill-directory>/scripts/collect_evidence.py --root <repository> --pretty
```

Its metadata and worktree fingerprint help establish context; they cannot decide module ownership or prove behavioral compatibility.

The optional change-evidence helper checks declared paths, unique textual anchors, per-file freshness, and missing verification surfaces. It does not execute recorded commands or certify their results. Use it for consequential integration work; keep small updates lightweight.

## Delivery

Follow the finalization rules in [Execution workflow](references/execution-workflow.md). Keep small updates small; a formal table or machine-readable ledger is optional, while traceability and observed verification remain required.

See [Sources and adaptation](references/sources.md) for provenance and [third-party notices](THIRD_PARTY_NOTICES.md) for retained licenses.
