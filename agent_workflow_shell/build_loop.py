"""Round-capped goal loop controller backing the /build workflow command.

This is the direct fix for unbounded "token cost spirals with every retry":
the loop runs a hard-capped number of rounds (3 normal + 1 automatic
extension = 4 max), judging every acceptance criterion pass/fail (never
partial) after each round, and reports unresolved criteria explicitly
rather than looping forever.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, Tuple

DEFAULT_MAX_NORMAL_ROUNDS = 3
DEFAULT_EXTENSION_ROUNDS = 1

JudgeFn = Callable[[int], Dict[str, bool]]


@dataclass(frozen=True)
class Criterion:
    """A single pass/fail acceptance criterion for a /build goal.

    Exactly one criterion per BuildLoopController must be the oracle: the
    single observable fact that would prove the goal was actually met.
    """

    name: str
    is_oracle: bool = False


@dataclass(frozen=True)
class RoundReport:
    round_number: int
    results: Dict[str, bool]
    failing: Tuple[str, ...]


@dataclass(frozen=True)
class BuildReport:
    status: str  # "VERIFIED" or "COMPLETE"
    rounds_run: int
    unresolved_criteria: Tuple[str, ...]
    oracle_passed: bool
    round_reports: Tuple[RoundReport, ...] = field(default_factory=tuple)


class BuildLoopController:
    """Drives the /build round -> judge pass -> loop control cycle."""

    def __init__(
        self,
        criteria: Iterable[Criterion],
        max_normal_rounds: int = DEFAULT_MAX_NORMAL_ROUNDS,
        extension_rounds: int = DEFAULT_EXTENSION_ROUNDS,
    ) -> None:
        criteria = list(criteria)
        if not criteria:
            raise ValueError("at least one criterion is required")

        names = [c.name for c in criteria]
        if len(set(names)) != len(names):
            raise ValueError("criterion names must be unique")

        oracle_names = [c.name for c in criteria if c.is_oracle]
        if len(oracle_names) != 1:
            raise ValueError(
                "exactly one criterion must be marked is_oracle=True, got "
                f"{len(oracle_names)}"
            )

        if max_normal_rounds < 1:
            raise ValueError("max_normal_rounds must be a positive integer")
        if extension_rounds < 0:
            raise ValueError("extension_rounds cannot be negative")

        self._criteria: Dict[str, Criterion] = {c.name: c for c in criteria}
        self._oracle_name = oracle_names[0]
        self.max_normal_rounds = max_normal_rounds
        self.extension_rounds = extension_rounds

    @property
    def max_rounds(self) -> int:
        return self.max_normal_rounds + self.extension_rounds

    def run(self, judge_fn: JudgeFn) -> BuildReport:
        """Run rounds until all criteria pass or the hard cap is hit.

        `judge_fn(round_number)` must return a dict mapping every criterion
        name to a strict bool verdict (never partial).
        """
        known_names = set(self._criteria.keys())
        round_reports = []
        round_number = 0
        failing: Tuple[str, ...] = tuple(sorted(known_names))

        while True:
            round_number += 1
            results = judge_fn(round_number)

            result_names = set(results.keys())
            unknown = result_names - known_names
            if unknown:
                raise ValueError(
                    f"judge_fn returned unknown criteria: {sorted(unknown)}"
                )
            missing = known_names - result_names
            if missing:
                raise ValueError(
                    f"judge_fn did not return a verdict for: {sorted(missing)}"
                )
            for name, verdict in results.items():
                if not isinstance(verdict, bool):
                    raise TypeError(
                        f"criterion {name!r} verdict must be a strict bool "
                        f"(pass/fail, never partial), got {type(verdict).__name__}"
                    )

            failing = tuple(sorted(name for name, ok in results.items() if not ok))
            round_reports.append(
                RoundReport(
                    round_number=round_number,
                    results=dict(results),
                    failing=failing,
                )
            )

            if not failing:
                break
            if round_number >= self.max_rounds:
                break

        status = "VERIFIED" if not failing else "COMPLETE"
        oracle_passed = self._oracle_name not in failing

        return BuildReport(
            status=status,
            rounds_run=round_number,
            unresolved_criteria=failing,
            oracle_passed=oracle_passed,
            round_reports=tuple(round_reports),
        )
