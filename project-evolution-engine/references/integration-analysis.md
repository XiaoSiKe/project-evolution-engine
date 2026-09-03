# Integration analysis

Decide how a new outcome belongs in the existing project. Start from domain responsibility and the caller's interface, then choose the implementation.

## Locate the real owner

Search the entry point, imports/exports, registrations, and consumers. Read complete logical blocks and relevant tests. Identify where the rule is actually maintained, where state lives, and what callers must know.

If documentation points to an obsolete file, trace the active route and correct the affected reference. Similar names, duplicated syntax, or a large file alone are not grounds to move responsibility.

## Choose a proportionate approach

| Approach | Use when | Verify |
| --- | --- | --- |
| Extend an existing module | The new behavior belongs to its current responsibility | Old consumers, added inputs, error behavior, policy reuse |
| Add a module | A distinct current responsibility needs its own interface | Its connection to existing callers, ownership, lifecycle, and test surface |
| Combine both | The new outcome requires a new capability and existing integration changes | Sequence, cross-boundary contracts, old-data behavior, and complete caller updates |

Choose the simplest complete option. Present alternatives only when there is a consequential tradeoff, not to manufacture a choice for an obvious change.

## Preserve and change intentionally

Separate:

- behavior explicitly changed by the new request;
- behavior explicitly protected;
- behavior implicitly relied upon by relevant existing callers;
- unresolved product decisions.

Keep the latest authorized contract in the plan and in any specialist's task. A reviewer restoring old behavior is wrong when that behavior was intentionally changed.

Check affected types, return formats, parameter defaults, ordering, failures, state transitions, permissions, configuration, persistence, and generated artifacts. Examine only the dimensions this change can affect.

## Judge module quality

- Place a shared rule at one owner; make consumers use it.
- Keep knowledge and its verification close to the owning module.
- Prefer a useful small interface that hides implementation complexity.
- Keep tests on the interfaces real callers use.
- Justify new abstraction with a current need, not an imagined extension.
- Avoid a local patch that makes every caller repeat the same new policy.

Required integration restructuring is part of the authorized feature when it is necessary and proportionate. An unrelated architecture redesign remains outside scope.

## Confirm the map

Before editing, be able to explain: why this location, what existing capability is reused, which consumers are affected, what stays unchanged, and which check demonstrates the outcome.

If the intended location cannot be justified, continue tracing. Do not hide uncertainty by building a parallel implementation that bypasses the existing system.

## Retain evidence when the boundary matters

For cross-layer updates, old-data compatibility, or a later handoff, record the confirmed owners and consumers alongside explicit unknowns. Pair each outcome with checks for the new behavior, its integration, and the relevant preserved behavior. Use [Change evidence](change-evidence.md) to stamp and recheck declared files when useful; a current stamp is not a completeness or correctness verdict.
