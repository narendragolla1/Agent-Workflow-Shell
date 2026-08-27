---
description: Capture a repeatable pattern as a portable skill. Blank -> mine the current session; topic given -> explore and draft.
argument-hint: [topic]
---

# /create-skill — capture a reusable pattern

Topic: $ARGUMENTS (if blank, review this session for a repeatable pattern
worth capturing instead of asking the user to supply one)

## 0. Resolve project slug
Resolve the canonical project slug once — pinned in `docs/memory/.project-slug`
on first run so every command agrees on the same memory file:

```
agent-workflow-shell resolve-project-slug --root .
```

Use the printed value as `<project>` in the memory-append step at the end.

## 1. Find the pattern
- **Blank**: look back over this session for something you did more than
  once, or something non-obvious enough that a future session would
  benefit from not re-deriving it.
- **Topic given**: explore the codebase for relevant conventions (grep/
  ripgrep, targeted reads). Ask clarifying questions if the topic is
  ambiguous about scope or trigger condition.

## 2. Draft
Write `.claude/skills/<slug>/SKILL.md` with:
- Frontmatter `description` under ~100 tokens, with explicit trigger
  phrases (what should make this skill fire).
- A procedure described as a **pattern** applicable to any file matching
  the trigger condition — not a walkthrough of what you just did in this
  session.
- **No hardcoded file paths or function/class/variable names from the
  current session anywhere in the body.**

## 3. Portability check — mandatory, run before presenting the draft
```
agent-workflow-shell check-skill-portability --file .claude/skills/<slug>/SKILL.md \
  --identifiers "<comma-separated list of specific names/paths from this session that must not leak in>"
```
- Exit code 0: draft passes — present it to the user.
- Exit code 1: read the `violations` in the JSON output and rewrite the
  offending parts as generic patterns, then re-run the check. Do not
  present a draft that failed this check, even with a caveat attached.

The check also independently flags absolute filesystem paths and an
over-budget description — fix those the same way: generalize, then
re-check.

## 4. Present and record
Show the user the final draft. Confirm it reads correctly when imagined
against a *different* repo, not just this one.

```
agent-workflow-shell memory-append --file docs/memory/<project>.md --command create-skill \
  --text "Captured skill: <slug> — <what pattern it covers, 1-2 lines>"
```

Then confirm the entry actually landed — this is a hard gate, not optional.
`git add -N` stages a brand-new memory file's path (without its content)
so a plain `git diff` picks it up even on the very first entry:
```
git add -N docs/memory/<project>.md 2>/dev/null; git diff | agent-workflow-shell check-memory-touch --memory-file docs/memory/<project>.md
```
- Exit code 0: memory was recorded — done.
- Exit code 1: STOP. The append never landed. Do not present the skill as
  done until this passes.
