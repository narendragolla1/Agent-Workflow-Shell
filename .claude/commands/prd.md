---
description: Turn a vague idea into a written requirements doc before /spec or /build.
argument-hint: <idea>
---

# /prd — product requirements doc

Idea: $ARGUMENTS

## 0. Read relevant memory first
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
