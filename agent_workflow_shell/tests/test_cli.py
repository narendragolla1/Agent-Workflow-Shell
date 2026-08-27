import json

import pytest

from agent_workflow_shell.cli import main


def _diff_text():
    return (
        "diff --git a/pkg/mod.py b/pkg/mod.py\n"
        "--- a/pkg/mod.py\n"
        "+++ b/pkg/mod.py\n"
        "@@ -0,0 +1,1 @@\n"
        "+x = 1\n"
    )


class TestAuditDiffCommand:
    def test_passing_diff_exits_zero_and_prints_json(self, tmp_path, capsys):
        diff_file = tmp_path / "d.diff"
        diff_file.write_text(_diff_text())
        code = main(
            [
                "audit-diff",
                "--diff-file",
                str(diff_file),
                "--task-type",
                "fix",
                "--investigated-files",
                "pkg/mod.py",
            ]
        )
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["passed"] is True

    def test_failing_diff_exits_one_with_flags(self, tmp_path, capsys):
        diff_file = tmp_path / "d.diff"
        diff_file.write_text(_diff_text())
        code = main(
            [
                "audit-diff",
                "--diff-file",
                str(diff_file),
                "--task-type",
                "fix",
                "--investigated-files",
                "pkg/other.py",
            ]
        )
        assert code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["passed"] is False
        assert payload["flags"]

    def test_reads_diff_from_stdin_when_no_file_given(self, capsys, monkeypatch):
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO(_diff_text()))
        code = main(
            ["audit-diff", "--task-type", "fix", "--investigated-files", "pkg/mod.py"]
        )
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["passed"] is True


class TestCheckEscalationCommand:
    def test_below_threshold_exits_zero(self, capsys):
        code = main(["check-escalation", "--files", "a.py,b.py"])
        assert code == 0

    def test_at_threshold_exits_one(self, capsys):
        code = main(["check-escalation", "--files", "a.py,b.py,c.py"])
        assert code == 1
        out = capsys.readouterr().out
        assert "spec" in out.lower()


class TestCheckConfidenceCommand:
    def test_high_confidence_exits_zero(self):
        assert main(["check-confidence", "--level", "High"]) == 0

    def test_low_confidence_exits_one(self):
        assert main(["check-confidence", "--level", "Low"]) == 1

    def test_invalid_confidence_exits_two_without_traceback(self, capsys):
        code = main(["check-confidence", "--level", "Certain"])
        assert code == 2
        err = capsys.readouterr().err
        assert "Certain" in err


class TestMemoryCommands:
    def test_append_then_search_round_trip(self, tmp_path, capsys):
        mem_file = tmp_path / "project.md"
        code = main(
            [
                "memory-append",
                "--file",
                str(mem_file),
                "--command",
                "fix",
                "--text",
                "root cause was a missing null check",
            ]
        )
        assert code == 0
        capsys.readouterr()

        code = main(
            ["memory-search", "--file", str(mem_file), "--keyword", "null check"]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "root cause was a missing null check" in out

    def test_search_with_no_matches_exits_one(self, tmp_path, capsys):
        mem_file = tmp_path / "project.md"
        main(
            [
                "memory-append",
                "--file",
                str(mem_file),
                "--command",
                "fix",
                "--text",
                "unrelated decision",
            ]
        )
        capsys.readouterr()
        code = main(
            ["memory-search", "--file", str(mem_file), "--keyword", "nonexistent"]
        )
        assert code == 1

    def test_append_over_line_limit_exits_two_with_friendly_error(self, tmp_path, capsys):
        mem_file = tmp_path / "project.md"
        code = main(
            [
                "memory-append",
                "--file",
                str(mem_file),
                "--command",
                "fix",
                "--text",
                "l1\nl2\nl3\nl4",
            ]
        )
        assert code == 2
        err = capsys.readouterr().err
        assert "line" in err.lower()


class TestSkillPortabilityCommand:
    def test_portable_skill_passes(self, tmp_path, capsys):
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(
            "---\nname: sample\ndescription: A generic pattern.\n---\n\nBody.\n"
        )
        code = main(["check-skill-portability", "--file", str(skill_file)])
        assert code == 0

    def test_skill_with_identifier_fails(self, tmp_path, capsys):
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(
            "---\nname: sample\ndescription: A generic pattern.\n---\n\n"
            "Call UserAuthController.login().\n"
        )
        code = main(
            [
                "check-skill-portability",
                "--file",
                str(skill_file),
                "--identifiers",
                "UserAuthController",
            ]
        )
        assert code == 1


class TestScanRulesCommand:
    def test_scan_rules_prints_doc_to_stdout(self, tmp_path, capsys):
        (tmp_path / "requirements.txt").write_text("pytest\n")
        code = main(["scan-rules", "--root", str(tmp_path)])
        assert code == 0
        out = capsys.readouterr().out
        assert "pytest" in out

    def test_scan_rules_writes_to_out_file(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("pytest\n")
        out_file = tmp_path / "docs" / "rules" / "proj.md"
        code = main(
            ["scan-rules", "--root", str(tmp_path), "--out", str(out_file)]
        )
        assert code == 0
        assert out_file.exists()
        assert "pytest" in out_file.read_text()


class TestResolveProjectSlugCommand:
    def test_prints_slug_and_exits_zero(self, tmp_path, capsys):
        (tmp_path / "package.json").write_text('{"name": "Widget App"}')
        code = main(["resolve-project-slug", "--root", str(tmp_path)])
        assert code == 0
        assert capsys.readouterr().out.strip() == "widget-app"

    def test_second_invocation_reuses_pinned_slug(self, tmp_path, capsys):
        (tmp_path / "package.json").write_text('{"name": "widget-app"}')
        main(["resolve-project-slug", "--root", str(tmp_path)])
        capsys.readouterr()

        (tmp_path / "package.json").write_text('{"name": "renamed-app"}')
        code = main(["resolve-project-slug", "--root", str(tmp_path)])
        assert code == 0
        assert capsys.readouterr().out.strip() == "widget-app"

    def test_nonexistent_root_exits_two(self, tmp_path, capsys):
        code = main(
            ["resolve-project-slug", "--root", str(tmp_path / "missing")]
        )
        assert code == 2
        assert capsys.readouterr().err.strip()


class TestArgparseErrors:
    def test_unknown_subcommand_raises_system_exit(self):
        with pytest.raises(SystemExit):
            main(["bogus-command"])
