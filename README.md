# Agent Workflow Shell

A CLI-installable extension for Claude Code (and portable to Codex CLI)
that adds structured, quality-enforced development workflows via slash
commands, persistent memory, and rule generation. Single-developer, local
tool: no web dashboard, no team sync, no browser automation.

## What's here

Six slash commands, each defined as a markdown instruction file in
`.claude/commands/`, backed by a deterministic Python package
(`agent_workflow_shell/`) for the checks that shouldn't be an LLM
judgment call:

| Command | Purpose |
|---|---|
| `/fix <bug>` | Local bugfix, TDD-enforced, no plan file. Escalates to `/spec` if the bug spans 3+ files. |
| `/spec <feature>` | Planned feature work with an approval gate before any code is written. |
| `/build <goal>` | Goal-oriented autonomous loop, hard-capped at 4 rounds (3 normal + 1 automatic extension). |
| `/prd <idea>` | Turns a vague idea into a written requirements doc before `/spec` or `/build`. |
| `/setup-rules` | Scans the codebase and generates `docs/rules/<project>-project.md`. |
| `/create-skill [topic]` | Captures a repeatable pattern as a portable skill, gated by a portability check. |

Where a check is deterministic (line-count thresholds, hardcoded-literal
detection, round caps, file-scope checks), it's implemented and unit-
tested as an actual script — not left to an LLM to eyeball on each run.
The command markdown files shell out to it and branch on the exit code,
so the logic stays auditable and portable rather than hidden inside a
prompt.

## Install

```bash
pip install -e .
```

This installs the `agent-workflow-shell` console script used by the
command markdown files, and makes `agent_workflow_shell` importable.

## The deterministic core

| Module | Backs | What it checks |
|---|---|---|
| `fix_escalation.py` | `/fix` | Escalate to `/spec` when 3+ files are touched or an architectural change is needed; blocks on Low investigate-confidence. |
| `diff_audit.py` | `/fix`, `/spec`, `/build` | Anti-hardcoding / quality gate: line-count budget, literal-equality-against-fixture-data detection (string *and* numeric), test-only diffs, out-of-scope files. |
| `build_loop.py` | `/build` | Round-capped goal loop: 3 normal rounds + 1 automatic extension, oracle-criterion tracking, strict pass/fail judging (never partial). |
| `memory.py` | all commands | Append-only, 1-3 line persistent memory log per project, with keyword search. |
| `project_slug.py` | all commands | Derives the canonical `<project>` slug for `docs/memory/<project>.md` from `rules_generator.scan_project` and pins it to `docs/memory/.project-slug` on first use, so every command — this session or a later one — resolves the same slug instead of guessing a name each run. |
| `skill_portability.py` | `/create-skill` | Rejects a drafted skill that leaks session-specific identifiers, hardcoded absolute paths, or an over-budget description. |
| `rules_generator.py` | `/setup-rules` | Scans manifests (package.json, pyproject.toml, requirements.txt, Cargo.toml, go.mod) — never a full-tree dump — to detect stack, commands, and structure. |
| `cli.py` | all of the above | `agent-workflow-shell <subcommand>` wiring: JSON out, exit code signals pass/fail. |

Run the test suite:

```bash
pytest agent_workflow_shell/tests
```

Every module above was built test-first: the test file for each was
written and run to a red failure before its implementation existed. See
`agent_workflow_shell/tests/test_definition_of_done.py` for the
acceptance-level tests that exercise this build's own definition of
done directly — a bug spanning 3+ files, a round loop that never reaches
a 5th round, a deliberately-planted hardcoded fix, and a skill draft
checked for portability across two different sample repos.

## Cross-cutting behavior

- **Anti-hardcoding audit** runs on every diff `/fix`, `/spec`, and
  `/build` produce, before it's accepted. A flagged diff is rejected and
  looped back to diagnose/plan — never auto-merged with just a warning.
- **Persistent memory** (`docs/memory/<project>.md`) is read by keyword at
  the start of every command and appended to (1-3 lines) at the end, so a
  later session doesn't re-tokenize the whole repo to re-learn the same
  context. `<project>` is never guessed by the agent: every command first
  runs `agent-workflow-shell resolve-project-slug --root .`, which derives
  the slug deterministically and pins it to `docs/memory/.project-slug` on
  first use — so two sessions on the same repo always land on the same
  memory file instead of silently fragmenting into `project.md` vs.
  `agent-workflow-shell.md` vs. whatever a given run felt like calling it.
- **Token-cost controls**: no command loads the full repo into context
  (grep/ripgrep + targeted reads only); retries are capped explicitly
  (`/build`'s round cap, `/fix`'s escalate-to-spec rule) so cost scales
  with configured limits, not indefinitely.

## Example project

`examples/sample-project/` is a minimal Node project (a `chunk()`
array-batching function with a Node `--test` suite) used as the reference
scan target for `/setup-rules`. Its generated rules doc is checked in at
`docs/rules/example-project-project.md` as a reference/test case — run
`npm test` inside that directory to see its own suite pass, or
`agent-workflow-shell scan-rules --root examples/sample-project` to
regenerate the rules doc from scratch.

## File/folder structure

```
.claude/commands/{fix,spec,build,prd,setup-rules,create-skill}.md   # command defs
.claude/skills/                                                      # generated skills land here
agent_workflow_shell/                                                # deterministic core + tests
docs/plans/          # /spec output
docs/builds/          # /build output
docs/prd/            # /prd output
docs/rules/           # /setup-rules output (+ the shipped reference doc)
docs/memory/          # persistent memory log
examples/sample-project/  # reference project for /setup-rules
```
