---
description: Scan the codebase and generate/sync docs/rules/<project>-project.md. Run once per project and after major changes.
argument-hint: (no arguments)
---

# /setup-rules — generate project conventions doc

## 0. Resolve project slug
Resolve the canonical project slug once — pinned in `docs/memory/.project-slug`
on first run so `/setup-rules` and every other command agree on the same
name instead of each guessing independently:

```
agent-workflow-shell resolve-project-slug --root .
```

Use the printed value as `<project>` everywhere below, in this file's
`--out` path and in the memory-append step.

## 1. Scan
Run the deterministic scanner (manifests + lockfiles + top-level structure
only — never a full-tree dump):

```
agent-workflow-shell scan-rules --root . --out docs/rules/<project>-project.md
```

This detects languages, package managers, test frameworks, and test/lint/
build commands from package.json, pyproject.toml, requirements.txt,
Cargo.toml, and go.mod, plus the top-level source directories.

## 2. Enrich by hand
The scanner only sees manifests, not conventions. Read a handful of
representative files (grep for existing patterns, don't load everything)
and add to the generated doc:
- Naming conventions
- Error-handling style
- Test framework usage patterns (not just which framework — how it's used
  here: fixtures, mocking style, assertion style)
- Folder-structure conventions beyond the top level

## 3. Sync with AGENTS.md / CLAUDE.md
If `AGENTS.md` or `CLAUDE.md` already exists in the repo root:
- Offer to sync the generated rules into it.
- **Never overwrite a user-authored section without asking.** Show the
  diff you intend to make and get explicit confirmation first.

If neither file exists, tell the user the rules doc was generated at
`docs/rules/<project>-project.md` and offer to create a minimal
`CLAUDE.md` that points to it.

## 4. Record
```
agent-workflow-shell memory-append --file docs/memory/<project>.md --command setup-rules \
  --text "Rules regenerated: <one line on what changed since last run, or 'initial generation'>"
```

Then confirm the entry actually landed — this is a hard gate, not optional.
`git add -N` stages a brand-new memory file's path (without its content)
so a plain `git diff` picks it up even on the very first entry:
```
git add -N docs/memory/<project>.md 2>/dev/null; git diff | agent-workflow-shell check-memory-touch --memory-file docs/memory/<project>.md
```
- Exit code 0: memory was recorded — done.
- Exit code 1: STOP. The append never landed. Do not report the rules doc
  done until this passes.
