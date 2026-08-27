"""Persistent, append-only memory log shared by all workflow commands.

Each command run appends a short (1-3 line) entry recording a decision,
gotcha, or bugfix root cause. Later sessions grep this file by keyword
instead of re-tokenizing the whole repo to re-learn the same context.
"""

from __future__ import annotations

import re
from datetime import date as date_type
from pathlib import Path
from typing import List, Optional, Union

DEFAULT_MAX_LINES = 3

_ENTRY_HEADER_RE = re.compile(r"^- \[\d{4}-\d{2}-\d{2}\] \[[^\]]*\] ", re.MULTILINE)

PathLike = Union[str, Path]


def _split_entries(content: str) -> List[str]:
    if not content.strip():
        return []
    starts = [m.start() for m in _ENTRY_HEADER_RE.finditer(content)]
    if not starts:
        return []
    starts.append(len(content))
    return [
        content[starts[i] : starts[i + 1]].rstrip("\n")
        for i in range(len(starts) - 1)
    ]


def append_entry(
    memory_path: PathLike,
    command: str,
    text: str,
    *,
    today: Optional[date_type] = None,
    max_lines: int = DEFAULT_MAX_LINES,
) -> str:
    """Append a memory entry and return the formatted entry text.

    `text` may span multiple lines but must not exceed `max_lines` (default
    3) — this keeps the log append-only and cheap to grep, per the
    token-cost controls in the build spec.
    """
    if max_lines < 1:
        raise ValueError("max_lines must be a positive integer")
    if not command or not command.strip():
        raise ValueError("command must be non-empty")

    stripped = text.strip("\n")
    if not stripped.strip():
        raise ValueError("entry text must be non-empty")

    lines = [line.rstrip() for line in stripped.split("\n")]
    if len(lines) > max_lines:
        raise ValueError(
            f"entry must be at most {max_lines} line(s), got {len(lines)}"
        )

    entry_date = today or date_type.today()
    header = f"- [{entry_date.isoformat()}] [{command.strip()}] {lines[0]}"
    body_lines = [f"  {line}" for line in lines[1:]]
    entry_text = "\n".join([header] + body_lines)

    path = Path(memory_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text() if path.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    path.write_text(existing + entry_text + "\n")

    return entry_text


def search_memory(memory_path: PathLike, keyword: str) -> List[str]:
    """Return full entries (as formatted text blocks) containing `keyword`,
    case-insensitively. Returns `[]` if the memory file doesn't exist yet.
    """
    if not keyword or not keyword.strip():
        raise ValueError("keyword must be non-empty")

    path = Path(memory_path)
    if not path.exists():
        return []

    content = path.read_text()
    entries = _split_entries(content)
    keyword_lower = keyword.lower()
    return [entry for entry in entries if keyword_lower in entry.lower()]
