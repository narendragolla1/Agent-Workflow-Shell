---
description: Planned feature work with an approval gate before implementation. Discuss -> Plan -> Approve -> Implement (TDD) -> Verify -> Done.
argument-hint: <feature description>
---

# /spec — planned feature work

Feature: $ARGUMENTS

## 0. Read relevant memory first
```
agent-workflow-shell memory-search --file docs/memory/<project>.md --keyword "<1-2 keywords>"
```

## 1. Discuss
Explore the codebase (file tree + grep/ripgrep for relevant modules — not a full-tree dump). If requirements are ambiguous on scope, target user, or done-criteria, ask the user clarifying questions before drafting a plan.

## 2. Plan
Write a plan file to `docs/plans/YYYY-MM-DD-<slug>.md` containing:
- **Scope** — what this feature does and does not include
- **Ordered task list** — each task small enough to TDD in one sitting
- **Definition of done per task**
- **Out-of-scope notes**

## 3. Approve — hard gate, never skip
Print the plan in full and ask the user to explicitly confirm before writing any code. "Looks good" or an explicit approval is required. If the user seems to be in a hurry, still gate — say so and ask for a one-line "approved" rather than silently proceeding.

## 4. Implement (TDD), one task at a time
For each task in the plan, in order:
1. **RED** — write a failing test for that task.
2. **GREEN** — write the minimal implementation that makes it pass.
3. **REFACTOR** — clean up for clarity without changing behavior; re-run the test to confirm it's still green.
4. Run the **full test suite** now, not just at the end of all tasks.
5. Audit the task's diff:
   ```
   git diff | agent-workflow-shell audit-diff --task-type feature \
     --investigated-files "<files this task touches>" --max-lines 20
   ```
   On a failing exit code, loop back within the task (don't move to the next task with a flagged diff).
6. Update the plan file: mark the task done, note any deviation from the original plan.

## 5. Verify
- Full test suite
- Lint / type-check
- A manual "does this actually run" check: execute the entry point, not just unit tests.

## 6. Done
Update the plan file with final status. Report deviations from the original plan explicitly — don't bury them.

Append a memory entry:
```
agent-workflow-shell memory-append --file docs/memory/<project>.md --command spec \
  --text "<feature>: <key decision or gotcha, 1-3 lines>"
```
