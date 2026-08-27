---
description: Goal-oriented autonomous loop for work where the approach isn't known upfront. Hard-capped at 4 rounds so cost never spirals.
argument-hint: <goal>
---

# /build — goal-oriented autonomous loop

Goal: $ARGUMENTS

This command's round cap is not a suggestion — it is the direct fix for
unbounded retry cost. The exact cap semantics (3 normal rounds + 1
automatic extension = 4 max, oracle-criterion handling, VERIFIED vs.
COMPLETE status) are implemented and unit-tested in
`agent_workflow_shell/build_loop.py::BuildLoopController`. Follow that
logic here even though you (the agent) are the judge, not a Python
callback — the discipline is identical.

## 0. Read relevant memory first
```
agent-workflow-shell memory-search --file docs/memory/<project>.md --keyword "<1-2 keywords>"
```

## 1. Name the goal
State the goal in one sentence, plus its **oracle**: the single observable
fact that would prove the goal was actually met — not "the code ran" but
something checkable against the finished artifact. If you cannot name an
oracle, STOP and ask the user instead of proceeding blind.

## 2. Draft tasks + acceptance criteria
- 3-7 tasks: title + objective only. No file-level detail yet — that's
  discovered during the round.
- 3-6 pass/fail criteria, exactly one marked as the oracle criterion.
  Every criterion must be decidable from the finished artifact, not from
  intent ("the API returns X for input Y", not "the API is now robust").

Write these to `docs/builds/YYYY-MM-DD-<slug>.md` before round 1.

## 3. Round loop (hard cap: 4 rounds total)
Round counter starts at 1.

**Each round:**
1. Work all open tasks. Tasks may be added, split, or dropped as the work
   reveals more — log every such change to the buildout file as it
   happens, not retroactively.
2. After all tasks in the round: run a **judge pass**. Evaluate every
   criterion strictly pass/fail (never partial) against the *current*
   artifact state. Write the verdicts to the buildout file.
3. If every criterion passed: stop the loop now, status is a candidate
   `VERIFIED` (confirmed in step 5). Do not run a redundant round.
4. If any criterion failed:
   - Round 1, 2, or 3 (normal rounds): failing criteria become next
     round's tasks. Increment the round counter and continue.
   - Round 4 (the automatic extension round, only reached if rounds 1-3
     all had failures): after this round's judge pass, **stop
     unconditionally** — there is no 5th round, ever, regardless of what
     still fails.

Before every round after the first, summarize the previous round's failed
attempt in 2-3 sentences — do not carry the full failed diff forward into
your working context.

## 4. Verify (only reachable after the loop above ends)
- Full test suite
- Lint / type-check
- An independent diff-review audit pass — treat this as a second, skeptical
  reviewer whose only job is catching hardcoding/scope creep, not restating
  what you already believe:
  ```
  git diff | agent-workflow-shell audit-diff --task-type feature \
    --investigated-files "<files touched>" --max-lines 20
  ```
  A failing exit code here means loop back to fix the flagged issue before
  hand-back, even if the round cap was already reached — this step runs
  once, outside the round budget.

## 5. Hand back
Update `docs/builds/YYYY-MM-DD-<slug>.md` with:
- Every criterion and the evidence that settled it (pass or fail)
- How tasks changed across rounds and why
- What was **not** verified

Status:
- `VERIFIED` only if the loop ended because all criteria passed *and* every
  check in step 4 ran and passed.
- `COMPLETE` otherwise — list the unresolved criteria explicitly. Never
  imply success on a criterion that failed.

Append a memory entry:
```
agent-workflow-shell memory-append --file docs/memory/<project>.md --command build \
  --text "<goal>: <final status + the one thing worth remembering, 1-3 lines>"
```
