---
description: Local bugfix, TDD-enforced, no plan file. Investigate -> RED -> Fix -> Verify -> Quality gate.
argument-hint: <bug description>
---

# /fix — local bugfix (TDD, no plan file)

Bug to fix: $ARGUMENTS

Run every step below in order. Do not skip a step because the bug "looks simple."

## 0. Resolve project + read relevant memory
Resolve the canonical project slug once — this pins `docs/memory/.project-slug`
on first run so every command, this session or a later one, agrees on the
same memory file instead of guessing a name:

```
agent-workflow-shell resolve-project-slug --root .
```

Use the printed value as `<project>` for every `docs/memory/<project>.md`
reference below, including the append step at the end.

Before investigating, grep prior context instead of re-discovering it:

```
agent-workflow-shell memory-search --file docs/memory/<project>.md --keyword "<1-2 keywords from the bug description>"
```

If `docs/memory/<project>.md` doesn't exist yet, this is a no-op (exit code 1, empty output) — proceed normally.

## 1. Investigate
Trace from a reproducible symptom to the root cause at `file:line`. Use grep/ripgrep and targeted reads — do not load the full repo into context.

State your confidence explicitly: **High**, **Medium**, or **Low**. Then run:

```
agent-workflow-shell check-confidence --level "<High|Medium|Low>"
```

- Exit code 0: proceed.
- Exit code 1: STOP. Tell the user your confidence is Low and what you'd need (a repro, logs, a pointer) to raise it. Do not guess your way to a fix.

## 2. Escalation check
List every file your Investigate step actually opened or would need to touch, then run:

```
agent-workflow-shell check-escalation --files "path/a.py,path/b.py,path/c.py"
```

- Exit code 0: the bug is contained — continue to RED.
- Exit code 1: STOP. Tell the user: "This spans 3+ files (or needs an architectural change) — use /spec instead." Do not attempt the fix anyway, even partially.

## 3. RED — write a failing test
Write a test that reproduces the bug through an existing **public entry point** — not a new internal hook created just for this test. Run it and confirm it fails with the documented symptom (not a different, unrelated error).

## 4. Fix — minimal diff at the root cause
Make the smallest change that fixes the root cause you found in step 1, not the symptom. Then audit your own diff before calling it done:

```
git diff | agent-workflow-shell audit-diff --task-type fix \
  --investigated-files "path/a.py,path/b.py" \
  --max-lines 20
```

- Exit code 0: diff passed the gate — continue.
- Exit code 1: read the `flags` in the JSON output. Each flag means one of:
  - the diff is larger than the configured line budget without justification — shrink it, or explain in your response to the user exactly why the size is necessary before proceeding;
  - it contains an equality check against what looks like literal test-fixture data — this is a hardcoding red flag; go back to step 1, you likely fixed the test instead of the bug;
  - it only touches test files for a fix task — same red flag, there is no real implementation change;
  - it touches files never mentioned in Investigate — either Investigate was incomplete (go back to step 1) or the diff is out of scope (shrink it).
  Loop back to the relevant step. Do not proceed with a flagged diff and a comment explaining it away — fix it or narrow it for real.

## 5. Verify
Run the reproducing test, then the full relevant test module (not just the one test).

## 6. Quality gate
Run lint, type-check, and the full test suite once. All must pass.

## 7. Record memory
Append a 1-3 line entry recording the root cause (not the whole fix):

```
agent-workflow-shell memory-append --file docs/memory/<project>.md --command fix \
  --text "<root cause in 1-3 short lines>"
```

## 8. Report
Summarize: symptom -> root cause (`file:line`) -> fix -> verification run. Nothing else.
