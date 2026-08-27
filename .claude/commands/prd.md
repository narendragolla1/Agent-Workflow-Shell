---
description: Turn a vague idea into a written requirements doc before /spec or /build.
argument-hint: <idea>
---

# /prd — product requirements doc

Idea: $ARGUMENTS

## 0. Resolve project + read relevant memory
Resolve the canonical project slug once — pinned in `docs/memory/.project-slug`
on first run so every command agrees on the same memory file:
```
agent-workflow-shell resolve-project-slug --root .
```
Use the printed value as `<project>` for every `docs/memory/<project>.md`
reference below, including the append step at the end.
```
agent-workflow-shell memory-search --file docs/memory/<project>.md --keyword "<1-2 keywords>"
```

## 1. Shape the idea
- **If the idea is vague** (no clear scope, unclear who it's for): propose
  2-4 concrete directions the idea could take. Let the user react to those
  before writing anything down. Don't converge on one direction yourself.
- **If the idea is already shaped**: ask structured clarifying questions
  covering scope boundaries, target user, and what "done" looks like. Don't
  ask questions the idea already answered.

## 2. Write the PRD
Once shape is agreed, write `docs/prd/YYYY-MM-DD-<slug>.md` containing:
- **Problem statement** — what's broken or missing, for whom
- **User flows** — concretely, step by step
- **Scope boundaries** — explicit in and out of scope
- **Technical context** — relevant existing systems, constraints, prior art

## 3. Hand off
Offer to hand off directly to `/spec <slug>` (planned, approval-gated
implementation) or `/build <slug>` (goal-oriented loop, when the approach
isn't known upfront). Let the user choose — don't pick for them.

Append a memory entry:
```
agent-workflow-shell memory-append --file docs/memory/<project>.md --command prd \
  --text "<idea>: <direction chosen, 1-3 lines>"
```

Then confirm the entry actually landed — this is a hard gate, not optional.
`git add -N` stages a brand-new memory file's path (without its content)
so a plain `git diff` picks it up even on the very first entry:
```
git add -N docs/memory/<project>.md 2>/dev/null; git diff | agent-workflow-shell check-memory-touch --memory-file docs/memory/<project>.md
```
- Exit code 0: memory was recorded — done.
- Exit code 1: STOP. The append never landed. Do not hand off until this
  passes.
