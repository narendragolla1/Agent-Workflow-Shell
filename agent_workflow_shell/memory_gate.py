"""Deterministic gate verifying a command's diff actually touched
persistent memory.

Every other quality gate in this package (`diff_audit`, `fix_escalation`,
`skill_portability`) fails the run by exit code when its check doesn't
hold. "Append a memory entry" had no equivalent — an agent could silently
skip it in a long or compacted session and nothing would catch it.
`check_memory_touch` closes that gap the same way the others do: it
inspects the same uncommitted diff `audit-diff` already consumes and
fails unless the project's memory file is among the touched paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from .diff_audit import list_touched_files


def _normalize(path: str) -> str:
    return path.strip().lstrip("./")


@dataclass(frozen=True)
class MemoryTouchResult:
    """Outcome of running check_memory_touch over a diff."""

    passed: bool
    memory_file: str
    touched_files: Tuple[str, ...] = field(default_factory=tuple)


def check_memory_touch(diff_text: str, memory_file: str) -> MemoryTouchResult:
    """Check whether `memory_file` appears among the files touched by
    `diff_text` (typically `git diff` output).

    `memory_file` and diff paths are both normalized (leading `./`
    stripped) before comparing, so `docs/memory/proj.md` and
    `./docs/memory/proj.md` are treated as the same path.
    """
    if not memory_file or not memory_file.strip():
        raise ValueError("memory_file must be non-empty")

    touched = list_touched_files(diff_text)
    target = _normalize(memory_file)
    passed = any(_normalize(path) == target for path in touched)

    return MemoryTouchResult(
        passed=passed,
        memory_file=memory_file,
        touched_files=tuple(sorted(touched)),
    )
