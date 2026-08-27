"""Command-line entry point wiring the deterministic checks used by the
/fix, /spec, /build, /prd, /setup-rules, and /create-skill slash commands.

Each subcommand prints a single JSON object (or a plain doc, for
scan-rules) and uses its exit code to signal pass/fail so a slash
command's markdown instructions can shell out to it and branch on the
result without needing an LLM judgment call for the deterministic parts.

Exit codes: 0 = check passed / proceed. 1 = check failed (as documented
per-subcommand). 2 = usage error (bad input), reported on stderr.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Sequence

from .diff_audit import audit_diff
from .fix_escalation import check_confidence_gate, should_escalate_to_spec
from .memory import append_entry, search_memory
from .rules_generator import render_rules_doc, scan_project
from .skill_portability import check_portability


def _split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _cmd_audit_diff(args: argparse.Namespace) -> int:
    if args.diff_file:
        diff_text = Path(args.diff_file).read_text()
    else:
        diff_text = sys.stdin.read()

    investigated = (
        set(_split_csv(args.investigated_files))
        if args.investigated_files is not None
        else None
    )
    fixtures = (
        set(_split_csv(args.known_fixtures)) if args.known_fixtures is not None else None
    )

    result = audit_diff(
        diff_text,
        task_type=args.task_type,
        investigated_files=investigated,
        max_lines=args.max_lines,
        known_fixture_values=fixtures,
    )
    print(json.dumps({"passed": result.passed, "flags": list(result.flags), "stats": result.stats}))
    return 0 if result.passed else 1


def _cmd_check_escalation(args: argparse.Namespace) -> int:
    files = _split_csv(args.files)
    decision = should_escalate_to_spec(
        files, threshold=args.threshold, architectural_change=args.architectural_change
    )
    print(json.dumps(asdict(decision)))
    return 1 if decision.escalate else 0


def _cmd_check_confidence(args: argparse.Namespace) -> int:
    try:
        allowed = check_confidence_gate(args.level)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0 if allowed else 1


def _cmd_memory_append(args: argparse.Namespace) -> int:
    try:
        entry = append_entry(args.file, args.command, args.text, max_lines=args.max_lines)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(entry)
    return 0


def _cmd_memory_search(args: argparse.Namespace) -> int:
    try:
        results = search_memory(args.file, args.keyword)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for entry in results:
        print(entry)
    return 0 if results else 1


def _cmd_check_skill_portability(args: argparse.Namespace) -> int:
    skill_markdown = Path(args.file).read_text()
    identifiers = _split_csv(args.identifiers) or None
    result = check_portability(
        skill_markdown,
        session_identifiers=identifiers,
        max_description_tokens=args.max_tokens,
    )
    print(json.dumps({"passed": result.passed, "violations": list(result.violations)}))
    return 0 if result.passed else 1


def _cmd_scan_rules(args: argparse.Namespace) -> int:
    try:
        profile = scan_project(args.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    doc = render_rules_doc(profile)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(doc)
    print(doc)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-workflow-shell")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    audit = subparsers.add_parser(
        "audit-diff", help="run the anti-hardcoding / quality-gate audit over a diff"
    )
    audit.add_argument("--diff-file", help="path to a unified diff; defaults to stdin")
    audit.add_argument("--task-type", default="fix")
    audit.add_argument("--investigated-files", help="comma-separated file list")
    audit.add_argument("--max-lines", type=int, default=20)
    audit.add_argument("--known-fixtures", help="comma-separated literal values")
    audit.set_defaults(func=_cmd_audit_diff)

    escalation = subparsers.add_parser(
        "check-escalation", help="decide whether /fix must escalate to /spec"
    )
    escalation.add_argument("--files", required=True, help="comma-separated file list")
    escalation.add_argument("--threshold", type=int, default=3)
    escalation.add_argument("--architectural-change", action="store_true")
    escalation.set_defaults(func=_cmd_check_escalation)

    confidence = subparsers.add_parser(
        "check-confidence", help="check the /fix Investigate confidence gate"
    )
    confidence.add_argument("--level", required=True)
    confidence.set_defaults(func=_cmd_check_confidence)

    mem_append = subparsers.add_parser(
        "memory-append", help="append a 1-3 line entry to a persistent memory log"
    )
    mem_append.add_argument("--file", required=True)
    mem_append.add_argument("--command", required=True)
    mem_append.add_argument("--text", required=True)
    mem_append.add_argument("--max-lines", type=int, default=3)
    mem_append.set_defaults(func=_cmd_memory_append)

    mem_search = subparsers.add_parser(
        "memory-search", help="grep a persistent memory log by keyword"
    )
    mem_search.add_argument("--file", required=True)
    mem_search.add_argument("--keyword", required=True)
    mem_search.set_defaults(func=_cmd_memory_search)

    portability = subparsers.add_parser(
        "check-skill-portability", help="run the /create-skill portability check"
    )
    portability.add_argument("--file", required=True, help="path to the drafted SKILL.md")
    portability.add_argument("--identifiers", help="comma-separated session-specific identifiers")
    portability.add_argument("--max-tokens", type=int, default=100)
    portability.set_defaults(func=_cmd_check_skill_portability)

    scan = subparsers.add_parser(
        "scan-rules", help="scan a project and render docs/rules/<project>-project.md"
    )
    scan.add_argument("--root", required=True)
    scan.add_argument("--out", help="optional path to write the rendered doc to")
    scan.set_defaults(func=_cmd_scan_rules)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
