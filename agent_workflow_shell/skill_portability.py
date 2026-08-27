"""Portability check for /create-skill output.

A generated skill must describe a pattern applicable to any file matching
its trigger condition — not the specific filename/class/variable from the
session that inspired it. This is a deterministic grep-based check, run
before a drafted skill is accepted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional, Tuple

DEFAULT_MAX_DESCRIPTION_TOKENS = 100

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_DESCRIPTION_RE = re.compile(r"^description:\s*(.*)$", re.MULTILINE)

_ABSOLUTE_PATH_RE = re.compile(
    r"(?:/home/[^\s`'\")]+|/Users/[^\s`'\")]+|/root/[^\s`'\")]+|"
    r"[A-Za-z]:\\[^\s`'\")]+)"
)


@dataclass(frozen=True)
class PortabilityResult:
    passed: bool
    violations: Tuple[str, ...] = field(default_factory=tuple)


def check_portability(
    skill_markdown: str,
    session_identifiers: Optional[Iterable[str]] = None,
    max_description_tokens: int = DEFAULT_MAX_DESCRIPTION_TOKENS,
) -> PortabilityResult:
    """Check a drafted skill file for portability violations.

    Rejects the draft if it: is missing frontmatter, has a description over
    `max_description_tokens`, references a hardcoded absolute filesystem
    path, or references any of `session_identifiers` (specific
    filenames/classnames/variables from the current session) verbatim.
    """
    if max_description_tokens < 1:
        raise ValueError("max_description_tokens must be a positive integer")

    violations = []

    match = _FRONTMATTER_RE.match(skill_markdown)
    if match is None:
        violations.append(
            "missing frontmatter: skill must start with a --- ... --- block "
            "containing a description"
        )
        body = skill_markdown
    else:
        frontmatter, body = match.group(1), match.group(2)
        description_match = _DESCRIPTION_RE.search(frontmatter)
        if description_match is None:
            violations.append("frontmatter is missing a description field")
        else:
            description = description_match.group(1).strip()
            token_count = len(description.split())
            if token_count > max_description_tokens:
                violations.append(
                    f"description is {token_count} tokens, exceeding the "
                    f"{max_description_tokens}-token budget"
                )

    path_matches = sorted(set(_ABSOLUTE_PATH_RE.findall(body)))
    for path in path_matches:
        violations.append(
            f"references a hardcoded absolute path instead of a portable "
            f"pattern: {path}"
        )

    identifiers = [
        identifier.strip()
        for identifier in (session_identifiers or [])
        if identifier and identifier.strip()
    ]
    for identifier in identifiers:
        if identifier in body:
            violations.append(
                "references session-specific identifier instead of "
                f"describing a generic pattern: {identifier}"
            )

    return PortabilityResult(passed=not violations, violations=tuple(violations))
