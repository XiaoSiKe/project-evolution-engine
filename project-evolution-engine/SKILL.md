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

- Preserve user edits and keep changes within the requested scope, including when the same file contains unrelated work.
- Keep rules at their authoritative owner and generated files on their source chain. Investigate conflicting domain facts before choosing a value.
- Use the latest authorized contract. Complete independent work before asking about a material ambiguity; commits, publishing, global tool changes, and contact with others require their own authorization.
- Ground decisions in current code and callers, recheck affected evidence after changes, and limit completion claims to observed checks.

## Optional tools and specialists

Read [Tool routing](references/tool-routing.md) only when an available capability would materially help the current work.

For a broad inventory, the bundled read-only helper is available:

```bash
python3 <skill-directory>/scripts/collect_evidence.py --root <repository> --pretty
```

The collector's output includes its coverage limits. Use the [change-evidence helper](references/change-evidence.md) when declared file locations and checks must survive a consequential handoff.

## Delivery

Follow the finalization rules in [Execution workflow](references/execution-workflow.md). Keep small updates small; a formal table or machine-readable ledger is optional, while traceability and observed verification remain required.

See [Sources and adaptation](references/sources.md) for provenance and [third-party notices](THIRD_PARTY_NOTICES.md) for retained licenses.
