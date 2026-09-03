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

## Start with the user's intent

State a short update brief: what changes, what stays, the relevant scope, material assumptions, and observable acceptance checks. Use the language of the user. Clear requests are authorization to perform their necessary, proportionate implementation; do not repeatedly ask to approve an already specified behavior or interface change.

A new requirement is sufficient grounds for an update. It does not need an existing bug or a Finding. Respect planning-only or review-only requests without mutating the project.

## Workflow

Follow this sequence while scaling its depth to the change. Read [Execution workflow](references/execution-workflow.md) when applying the Skill.

1. **Define the delta.** Describe added, modified, and removed behavior, plus explicitly preserved behavior. Use the latest user requirement when it intentionally changes the old contract.
2. **Understand the current project.** Inspect repository instructions, worktree state, relevant domain decisions, entry points, real call paths, data ownership, and verification commands. Confirm remembered locations against current code. Use [Project context](references/project-context.md) when context is missing, unfamiliar, stale, or shared across sessions.
3. **Locate the integration.** Map each outcome to an owning file and symbol, existing reusable behavior, affected consumers, and a check. Read [Integration analysis](references/integration-analysis.md) before choosing a non-trivial or cross-module change. For compatibility-sensitive work or evidence that must survive a handoff, use [Change evidence](references/change-evidence.md) to retain file locations, consumers, explicit unknowns, and new/integration/preserved checks.
4. **Implement a coherent increment.** Follow existing conventions and update the canonical source. Include necessary callers, configuration, schemas, generated output, and documentation. Repair related blockers within scope; keep unrelated findings out of the change.
5. **Verify new and preserved behavior.** Exercise actual caller interfaces and inspect the combined final diff. Use [Verification](references/verification.md) to distinguish behavioral evidence from package checks, stale reports, or unexecuted assumptions.
6. **Update useful project knowledge.** Correct affected authoritative documentation. Persist a plan only when work spans sessions or needs a reviewable handoff; record a lesson only when verified reasoning would otherwise be lost.

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

Give a concise, unified result:

- the implemented delta and the behavior preserved;
- changed files/modules and why those were the right integration points;
- verification commands and actual outcomes, including any baseline failures;
- necessary document or generated-output updates;
- remaining gaps, or the one unresolved decision and independent work already completed.

Keep small updates small. A formal table or machine-readable ledger is optional; traceability and evidence are not.

See [Sources and adaptation](references/sources.md) for provenance and [third-party notices](THIRD_PARTY_NOTICES.md) for retained licenses.
