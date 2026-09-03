# Execution workflow

Use one continuous chain from requested outcome to current code to observed result. A small feature may need only a short brief and a few commands; a broad update needs a reviewable plan with ownership and dependencies.

## 1. Establish the update brief

Capture added, modified, removed, and preserved behavior. Translate vague outcomes into observable acceptance checks. Note scope and instructions that actually affect this task.

Read existing user authorization before asking questions. An explicit request to change a rule or public interface authorizes that intended delta; preserve its unmentioned consumers and behaviors. If a product decision is genuinely unresolved, identify the competing interpretations and their effects. Continue independent work before asking one consolidated question.

Keep the brief in the conversation for short work. Reuse an existing plan or design location for multi-session work rather than creating parallel specifications.

## 2. Establish current evidence

Inspect worktree state before edits. Identify pre-existing changes and read the current contents of files you need. A dirty file is not automatically unavailable: the requested change can be added while preserving the user's other edits. Ask only for a real conflict that cannot be resolved from their instructions.

Read relevant repository instructions and accepted domain decisions. Trace the feature from entry point through its owner and consumers. Consult implementation, types, tests, configuration, and documentation together; a stale document does not outweigh current authoritative evidence.

Find proportionate baseline commands. Record existing failures separately so a pre-existing failure is not blamed on the update or hidden by a success claim.

Use the collector only when a broad inventory is useful. It does not replace reading relevant logical blocks, checking callers, or understanding runtime behavior.

## 3. Build the change map

For each requested outcome identify:

| Outcome | Current owner and symbol | Intended change | Consumers and preserved behavior | Evidence/check |
| --- | --- | --- | --- | --- |
| The user's observable goal | A verified path and interface | Extension, new responsibility, or combined change | Relevant callers, formats, state, errors | A test or reproducible flow |

A new file can be a valid owner when a distinct responsibility or current interface need justifies it. Explain where it connects. Do not add abstractions or alternate paths only for speculative future uses.

Read [Integration analysis](integration-analysis.md) for cross-module changes. Set the order so each increment has a usable interface and meaningful verification.

For consequential compatibility or cross-layer work, keep confirmed consumers and impact unknowns separate and use [Change evidence](change-evidence.md) when a durable evidence record helps. A single test can cover new, integration, and preserved behavior; distinguish those claims in the map even when the command is shared.

## 4. Implement through the existing system

Reread the target before mutation, especially after another agent or tool changes it. Reuse existing policy and error handling at their authoritative location. Update consumers when their required inputs or outputs intentionally change.

Write focused regression tests for changed executable behavior when a suitable test surface exists. For a low-impact text or mechanical change, use a direct proportionate check instead of artificial tests.

For an integration blocker, prove the symptom and the remedy separately. Keep an incidental cleanup out of the patch unless it is required for the update or explicitly requested.

Use existing generators, migrations, or configuration conventions. If a data migration is necessary, follow the established sequence and verify old-data behavior; do not apply a live migration merely because code was prepared.

## 5. Close the loop

Run the new behavior and the relevant old behavior through actual interfaces. Verify changed consumers, errors, generated artifacts, and configuration when they are affected. Inspect the final combined diff, including additions and deletions.

If a check contradicts the plan, revisit the current evidence and adjust the plan or implementation. Do not keep compensating for an incorrect premise with fallbacks.

Correct affected documentation at its canonical location. Remove only temporary instrumentation and artifacts introduced by this work.

## 6. Hand back one result

Report implemented and unfinished outcomes, the owning modules and reasons, preserved behaviors, and actual verification. Link to the changed code and important evidence.

If blocked, explain the unresolved decision and show completed independent work. If a check could not run, identify the missing prerequisite and the resulting coverage gap. Never report an unavailable specialist or unexecuted command as successful.
