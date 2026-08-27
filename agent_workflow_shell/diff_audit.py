"""Anti-hardcoding / quality-gate audit for diffs produced by /fix, /spec,
and /build.

This is deliberately a deterministic, grep-style checker (not an LLM
judgment call) so it is cheap and reliable: git diff/test-suite results are
facts, not opinions. It flags rather than silently allowing; the calling
workflow command decides what to do with a failed AuditResult (per the
build spec: reject and loop back to diagnose/plan, never auto-merge with
just a warning).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

DEFAULT_MAX_LINES = 20

_VALID_TASK_TYPES = {"fix", "feature", "refactor", "chore"}
_TASK_TYPES_REQUIRING_IMPLEMENTATION = {"fix", "feature"}

_FILE_HEADER_RE = re.compile(r"^diff --git a/(?P<a>.*?) b/(?P<b>.*)$")
_BINARY_RE = re.compile(r"^Binary files (?:a/)?(?P<a>.*) and (?:b/)?(?P<b>.*) differ$")

_TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|__tests__|spec)(/|$)|"
    r"(^|/)test_[^/]+$|"
    r"_test\.[a-zA-Z0-9]+$|"
    r"\.test\.[a-zA-Z0-9]+$|"
    r"\.spec\.[a-zA-Z0-9]+$"
)

_LITERAL_EQUALITY_RE = re.compile(r"(?:===|==)\s*[\"']([^\"']+)[\"']")
_EQUALS_CALL_RE = re.compile(r"\.equals\(\s*[\"']([^\"']+)[\"']\s*\)")
_NUMERIC_EQUALITY_RE = re.compile(r"(?:===|==)\s*(-?\d+(?:\.\d+)?)\b")


def _strip_ab_prefix(path: str) -> str:
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def _new_file_stat() -> dict:
    return {"added": 0, "removed": 0, "added_lines": [], "binary": False}


def _parse_diff(diff_text: str) -> dict:
    files: dict = {}
    current: Optional[str] = None
    for raw_line in diff_text.splitlines():
        header_match = _FILE_HEADER_RE.match(raw_line)
        if header_match:
            current = header_match.group("b")
            files.setdefault(current, _new_file_stat())
            continue

        binary_match = _BINARY_RE.match(raw_line)
        if binary_match:
            path = _strip_ab_prefix(binary_match.group("b"))
            current = path
            stat = files.setdefault(current, _new_file_stat())
            stat["binary"] = True
            continue

        if raw_line.startswith("+++ "):
            path = _strip_ab_prefix(raw_line[4:].strip())
            if path == "/dev/null":
                continue
            if current is None or current not in files:
                current = path
                files.setdefault(current, _new_file_stat())
            continue

        if raw_line.startswith("--- "):
            continue

        if raw_line.startswith("@@"):
            continue

        if raw_line.startswith("\\ No newline"):
            continue

        if current is None:
            continue

        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            stat = files[current]
            stat["added"] += 1
            stat["added_lines"].append(raw_line[1:])
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            files[current]["removed"] += 1

    return files


def list_touched_files(diff_text: str) -> frozenset:
    """Return the set of file paths (post-change side) touched by a
    unified diff. Shared with `memory_gate.check_memory_touch`, which
    needs the same touched-file extraction this module already does for
    the out-of-scope-files check.
    """
    return frozenset(_parse_diff(diff_text).keys())


def _looks_like_test_file(path: str) -> bool:
    return bool(_TEST_PATH_RE.search(path))


def _looks_like_fixture_literal(value: str) -> bool:
    if len(value) < 3:
        return False
    lowered = value.lower()
    if "test" in lowered or "fixture" in lowered or "mock" in lowered:
        return True
    if re.search(r"\d", value) and re.fullmatch(r"[A-Za-z0-9_\-]+", value):
        return True
    return False


def _extract_string_literal_values(line: str) -> list:
    values = [m.group(1) for m in _LITERAL_EQUALITY_RE.finditer(line)]
    values.extend(m.group(1) for m in _EQUALS_CALL_RE.finditer(line))
    return values


def _extract_numeric_literal_values(line: str) -> list:
    return [m.group(1) for m in _NUMERIC_EQUALITY_RE.finditer(line)]


@dataclass(frozen=True)
class AuditResult:
    """Outcome of running audit_diff over a diff."""

    passed: bool
    flags: tuple = field(default_factory=tuple)
    stats: dict = field(default_factory=dict)


def audit_diff(
    diff_text: str,
    task_type: str = "fix",
    investigated_files: Optional[Iterable[str]] = None,
    max_lines: int = DEFAULT_MAX_LINES,
    known_fixture_values: Optional[Iterable[str]] = None,
) -> AuditResult:
    """Run the deterministic quality gate over a unified diff.

    Args:
        diff_text: unified diff text (e.g. `git diff` output).
        task_type: one of "fix", "feature", "refactor", "chore". Controls
            whether a test-only diff is treated as a hardcoding smell.
        investigated_files: files identified during Investigate/Plan.
            `None` skips the out-of-scope check (not enough information).
            An explicit empty set/iterable means nothing was investigated,
            so every touched file is out of scope.
        max_lines: diff line-change budget before the size flag fires.
        known_fixture_values: literal values (strings or numbers, compared
            as strings) known to be test fixture data. When provided,
            equality checks against these exact values are flagged,
            including numeric literals (e.g. `array.length === 7`). When
            `None`, only string literals are checked, via a heuristic
            (contains "test"/"fixture"/"mock", or is a bare alnum token
            containing a digit) — bare numeric equality is too common in
            legitimate code to heuristically flag.
    """
    if max_lines < 1:
        raise ValueError("max_lines must be a positive integer")

    task_type_normalized = task_type.strip().lower()
    if task_type_normalized not in _VALID_TASK_TYPES:
        raise ValueError(
            f"Unknown task_type {task_type!r}; expected one of "
            f"{sorted(_VALID_TASK_TYPES)}"
        )

    known_fixture_set = (
        set(known_fixture_values) if known_fixture_values is not None else None
    )

    files = _parse_diff(diff_text)
    touched_files = set(files.keys())
    flags = []

    total_lines = sum(stat["added"] + stat["removed"] for stat in files.values())
    if total_lines > max_lines:
        flags.append(
            f"diff changes {total_lines} lines, exceeding the {max_lines}-line "
            "threshold without explanation"
        )

    if (
        task_type_normalized in _TASK_TYPES_REQUIRING_IMPLEMENTATION
        and touched_files
        and all(_looks_like_test_file(p) for p in touched_files)
    ):
        flags.append(
            f"diff only modifies test files for a {task_type_normalized} task "
            "(hardcoding smell: no implementation change)"
        )

    if investigated_files is not None:
        investigated_set = set(investigated_files)
        out_of_scope = sorted(touched_files - investigated_set)
        if out_of_scope:
            flags.append(
                "diff touches files never mentioned in Investigate/Plan: "
                + ", ".join(out_of_scope)
            )

    literal_hits = []
    for path, stat in files.items():
        if stat["binary"]:
            continue
        for line in stat["added_lines"]:
            for value in _extract_string_literal_values(line):
                if known_fixture_set is not None:
                    if value in known_fixture_set:
                        literal_hits.append((path, value))
                elif _looks_like_fixture_literal(value):
                    literal_hits.append((path, value))
            # Numeric literals (e.g. `array.length === 7`) are only ever
            # flagged deterministically against known_fixture_values: bare
            # numeric equality checks are too common in legitimate code to
            # heuristically flag without flooding every diff with noise.
            if known_fixture_set is not None:
                for value in _extract_numeric_literal_values(line):
                    if value in known_fixture_set:
                        literal_hits.append((path, value))
    if literal_hits:
        details = ", ".join(f"{p}: {v!r}" for p, v in literal_hits)
        flags.append(
            "diff contains equality checks against literal(s) matching test "
            f"fixture data: {details}"
        )

    stats = {
        "touched_files": sorted(touched_files),
        "total_lines_changed": total_lines,
        "per_file": {
            path: {"added": stat["added"], "removed": stat["removed"]}
            for path, stat in files.items()
        },
    }

    return AuditResult(passed=not flags, flags=tuple(flags), stats=stats)
