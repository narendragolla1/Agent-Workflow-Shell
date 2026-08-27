from datetime import date

import pytest

from agent_workflow_shell.memory import append_entry, search_memory


class TestAppendEntry:
    def test_creates_file_and_parent_dirs_if_missing(self, tmp_path):
        target = tmp_path / "nested" / "dir" / "project.md"
        assert not target.exists()
        append_entry(target, "fix", "root cause was off-by-one in parser")
        assert target.exists()
        assert "root cause was off-by-one in parser" in target.read_text()

    def test_second_append_preserves_first_entry(self, tmp_path):
        target = tmp_path / "project.md"
        append_entry(target, "fix", "first decision", today=date(2026, 1, 1))
        append_entry(target, "spec", "second decision", today=date(2026, 1, 2))
        content = target.read_text()
        assert "first decision" in content
        assert "second decision" in content
        assert content.index("first decision") < content.index("second decision")

    def test_entry_includes_date_and_command(self, tmp_path):
        target = tmp_path / "project.md"
        entry = append_entry(
            target, "fix", "found the bug", today=date(2026, 3, 4)
        )
        assert "2026-03-04" in entry
        assert "[fix]" in entry
        assert "found the bug" in entry

    def test_multiline_entry_up_to_three_lines_allowed(self, tmp_path):
        target = tmp_path / "project.md"
        entry = append_entry(
            target, "build", "line one\nline two\nline three"
        )
        assert "line one" in entry
        assert "line two" in entry
        assert "line three" in entry

    def test_entry_over_three_lines_raises(self, tmp_path):
        target = tmp_path / "project.md"
        with pytest.raises(ValueError):
            append_entry(target, "build", "l1\nl2\nl3\nl4")

    def test_empty_entry_text_raises(self, tmp_path):
        target = tmp_path / "project.md"
        with pytest.raises(ValueError):
            append_entry(target, "fix", "")

    def test_whitespace_only_entry_text_raises(self, tmp_path):
        target = tmp_path / "project.md"
        with pytest.raises(ValueError):
            append_entry(target, "fix", "   \n  ")

    def test_empty_command_raises(self, tmp_path):
        target = tmp_path / "project.md"
        with pytest.raises(ValueError):
            append_entry(target, "", "some decision")

    def test_custom_max_lines_is_enforced(self, tmp_path):
        target = tmp_path / "project.md"
        with pytest.raises(ValueError):
            append_entry(target, "fix", "l1\nl2", max_lines=1)

    def test_exactly_max_lines_is_allowed(self, tmp_path):
        target = tmp_path / "project.md"
        entry = append_entry(target, "fix", "l1\nl2\nl3", max_lines=3)
        assert entry.count("\n") == 2


class TestSearchMemory:
    def test_missing_file_returns_empty_list(self, tmp_path):
        target = tmp_path / "does-not-exist.md"
        assert search_memory(target, "anything") == []

    def test_empty_keyword_raises(self, tmp_path):
        target = tmp_path / "project.md"
        append_entry(target, "fix", "some decision")
        with pytest.raises(ValueError):
            search_memory(target, "")

    def test_keyword_not_found_returns_empty_list(self, tmp_path):
        target = tmp_path / "project.md"
        append_entry(target, "fix", "parser off-by-one bug")
        assert search_memory(target, "database") == []

    def test_keyword_match_is_case_insensitive(self, tmp_path):
        target = tmp_path / "project.md"
        append_entry(target, "fix", "Parser Off-By-One Bug")
        results = search_memory(target, "parser")
        assert len(results) == 1
        assert "Parser Off-By-One Bug" in results[0]

    def test_keyword_in_continuation_line_is_found(self, tmp_path):
        target = tmp_path / "project.md"
        append_entry(target, "build", "summary line\ndetail mentions redis cache")
        results = search_memory(target, "redis")
        assert len(results) == 1
        assert "redis cache" in results[0]

    def test_search_filters_across_multiple_entries(self, tmp_path):
        target = tmp_path / "project.md"
        append_entry(target, "fix", "auth bug root cause", today=date(2026, 1, 1))
        append_entry(target, "spec", "payments refactor plan", today=date(2026, 1, 2))
        results = search_memory(target, "auth")
        assert len(results) == 1
        assert "auth bug root cause" in results[0]

    def test_search_returns_full_entry_not_just_matching_line(self, tmp_path):
        target = tmp_path / "project.md"
        append_entry(
            target,
            "build",
            "goal met\noracle criterion satisfied",
            today=date(2026, 2, 2),
        )
        results = search_memory(target, "oracle")
        assert "goal met" in results[0]
        assert "2026-02-02" in results[0]
