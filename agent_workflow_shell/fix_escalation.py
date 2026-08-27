"""Escalation and confidence-gate rules for the /fix workflow command.

`/fix` is for local bugfixes only. If the Investigate step reveals the bug
spans too many files, or requires an architectural change, the command must
stop and point the user at /spec instead of attempting the fix anyway.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

DEFAULT_FILE_THRESHOLD = 3

_VALID_CONFIDENCE_LEVELS = {"high", "medium", "low"}
_BLOCKING_CONFIDENCE_LEVELS = {"low"}


@dataclass(frozen=True)
class EscalationDecision:
    """Result of evaluating whether /fix should escalate to /spec."""

    escalate: bool
    reason: str


def should_escalate_to_spec(
    investigated_files: Iterable[str],
    threshold: int = DEFAULT_FILE_THRESHOLD,
    architectural_change: bool = False,
) -> EscalationDecision:
    """Decide whether /fix must stop and defer to /spec.

    Escalates when the Investigate step touched `threshold` or more distinct
    files, or when the fix would require an architectural change.
    """
    if threshold < 1:
        raise ValueError("threshold must be a positive integer")

    unique_files = set(investigated_files)
    file_count = len(unique_files)

    if architectural_change:
        return EscalationDecision(
            escalate=True,
            reason=(
                "Fix requires an architectural change; use /spec instead of /fix."
            ),
        )

    if file_count >= threshold:
        return EscalationDecision(
            escalate=True,
            reason=(
                f"Bug spans {file_count} files (threshold is {threshold}); "
                "use /spec instead of /fix."
            ),
        )

    return EscalationDecision(
        escalate=False,
        reason=f"Bug is contained to {file_count} file(s); /fix may proceed.",
    )


def check_confidence_gate(confidence: str) -> bool:
    """Return True if the Investigate step's stated confidence permits
    proceeding with /fix. Blocks on "Low" confidence.

    Raises ValueError for anything other than High/Medium/Low (case- and
    whitespace-insensitive).
    """
    normalized = confidence.strip().lower()
    if normalized not in _VALID_CONFIDENCE_LEVELS:
        raise ValueError(
            f"Unknown confidence level {confidence!r}; expected one of "
            "High, Medium, Low."
        )
    return normalized not in _BLOCKING_CONFIDENCE_LEVELS
