import pytest

from agent_workflow_shell.memory_gate import MemoryTouchResult, check_memory_touch


def _diff(path, added_lines):
    header = [
        f"diff --git a/{path} b/{path}",
        f"--- a/{path}",
        f"+++ b/{path}",
        f"@@ -0,0 +1,{len(added_lines)} @@",
    ]
    body = [f"+{line}" for line in added_lines]
    return "\n".join(header + body) + "\n"


def _new_file_diff(path, added_lines):
    # Mirrors what `git diff` produces for a file staged via
    # `git add -N` (intent-to-add): the standard trick to make a brand
    # new, previously-untracked file show up in a plain `git diff`.
    header = [
        f"diff --git a/{path} b/{path}",
        "new file mode 100644",
        "--- /dev/null",
        f"+++ b/{path}",
        f"@@ -0,0 +1,{len(added_lines)} @@",
    ]
    body = [f"+{line}" for line in added_lines]
    return "\n".join(header + body) + "\n"


class TestCheckMemoryTouch:
    def test_diff_touching_memory_file_passes(self):
        diff = _diff("docs/memory/widget-app.md", ["- [2026-01-01] [fix] root cause"])
        result = check_memory_touch(diff, "docs/memory/widget-app.md")
        assert isinstance(result, MemoryTouchResult)
        assert result.passed is True

    def test_diff_not_touching_memory_file_fails(self):
        diff = _diff("src/mod.py", ["x = 1"])
        result = check_memory_touch(diff, "docs/memory/widget-app.md")
        assert result.passed is False
        assert "src/mod.py" in result.touched_files

    def test_empty_diff_fails(self):
        result = check_memory_touch("", "docs/memory/widget-app.md")
        assert result.passed is False

    def test_newly_created_memory_file_via_intent_to_add_passes(self):
        diff = _new_file_diff(
            "docs/memory/widget-app.md", ["- [2026-01-01] [fix] first entry"]
        )
        result = check_memory_touch(diff, "docs/memory/widget-app.md")
        assert result.passed is True

    def test_diff_touching_memory_file_among_other_files_passes(self):
        diff = _diff("src/mod.py", ["x = 1"]) + _diff(
            "docs/memory/widget-app.md", ["- [2026-01-01] [fix] note"]
        )
        result = check_memory_touch(diff, "docs/memory/widget-app.md")
        assert result.passed is True

    def test_leading_dot_slash_is_normalized_on_both_sides(self):
        diff = _diff("docs/memory/widget-app.md", ["- entry"])
        result = check_memory_touch(diff, "./docs/memory/widget-app.md")
        assert result.passed is True

    def test_wrong_memory_file_path_does_not_match(self):
        diff = _diff("docs/memory/widget-app.md", ["- entry"])
        result = check_memory_touch(diff, "docs/memory/other-project.md")
        assert result.passed is False

    def test_empty_memory_file_argument_raises(self):
        with pytest.raises(ValueError):
            check_memory_touch(_diff("a.py", ["x = 1"]), "")

    def test_touched_files_are_reported_sorted(self):
        diff = _diff("b.py", ["y = 1"]) + _diff("a.py", ["x = 1"])
        result = check_memory_touch(diff, "docs/memory/widget-app.md")
        assert result.touched_files == ("a.py", "b.py")
