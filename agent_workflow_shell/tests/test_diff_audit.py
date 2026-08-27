import pytest

from agent_workflow_shell.diff_audit import AuditResult, audit_diff


def _diff(path, added_lines, old_path=None, new_file=False):
    """Build a minimal single-file unified diff for tests."""
    old_path = old_path or path
    header = [f"diff --git a/{old_path} b/{path}"]
    if new_file:
        header.append("new file mode 100644")
        header.append("--- /dev/null")
    else:
        header.append(f"--- a/{old_path}")
    header.append(f"+++ b/{path}")
    header.append(f"@@ -0,0 +1,{len(added_lines)} @@")
    body = [f"+{line}" for line in added_lines]
    return "\n".join(header + body) + "\n"


class TestBasicParsingAndStats:
    def test_empty_diff_passes_with_no_touched_files(self):
        result = audit_diff("", task_type="fix")
        assert isinstance(result, AuditResult)
        assert result.passed is True
        assert result.flags == ()
        assert result.stats["touched_files"] == []

    def test_touched_files_recorded(self):
        diff = _diff("pkg/mod.py", ["x = 1"])
        result = audit_diff(diff, task_type="fix", investigated_files={"pkg/mod.py"})
        assert result.stats["touched_files"] == ["pkg/mod.py"]

    def test_new_file_diff_parses_without_crashing(self):
        diff = _diff("pkg/new.py", ["def f():", "    return 1"], new_file=True)
        result = audit_diff(diff, task_type="feature", investigated_files={"pkg/new.py"})
        assert "pkg/new.py" in result.stats["touched_files"]
        assert result.stats["total_lines_changed"] == 2

    def test_deleted_file_diff_counts_removed_lines_without_crashing(self):
        diff = "\n".join(
            [
                "diff --git a/pkg/old.py b/pkg/old.py",
                "deleted file mode 100644",
                "--- a/pkg/old.py",
                "+++ /dev/null",
                "@@ -1,2 +0,0 @@",
                "-x = 1",
                "-y = 2",
            ]
        )
        result = audit_diff(diff, task_type="fix", investigated_files={"pkg/old.py"})
        assert result.stats["total_lines_changed"] == 2

    def test_binary_diff_is_recorded_but_not_scanned(self):
        diff = "\n".join(
            [
                "diff --git a/img.png b/img.png",
                "index 111..222 100644",
                "Binary files a/img.png and b/img.png differ",
            ]
        )
        result = audit_diff(diff, task_type="fix", investigated_files={"img.png"})
        assert "img.png" in result.stats["touched_files"]
        assert result.stats["total_lines_changed"] == 0
        assert result.passed is True

    def test_rename_diff_uses_new_path(self):
        diff = _diff("pkg/new_name.py", ["x = 1"], old_path="pkg/old_name.py")
        result = audit_diff(
            diff, task_type="fix", investigated_files={"pkg/new_name.py"}
        )
        assert result.stats["touched_files"] == ["pkg/new_name.py"]

    def test_no_newline_at_eof_marker_is_ignored(self):
        diff = _diff("pkg/mod.py", ["x = 1"]) + "\\ No newline at end of file\n"
        result = audit_diff(diff, task_type="fix", investigated_files={"pkg/mod.py"})
        assert result.stats["total_lines_changed"] == 1

    def test_unicode_content_does_not_crash(self):
        diff = _diff("pkg/mod.py", ['greeting = "héllo wörld 你好"'])
        result = audit_diff(diff, task_type="fix", investigated_files={"pkg/mod.py"})
        assert result.passed is True


class TestLineCountThreshold:
    def test_exactly_at_threshold_is_not_flagged(self):
        diff = _diff("pkg/mod.py", [f"line_{i} = {i}" for i in range(20)])
        result = audit_diff(
            diff, task_type="fix", investigated_files={"pkg/mod.py"}, max_lines=20
        )
        assert not any("threshold" in f for f in result.flags)
        assert result.passed is True

    def test_one_over_threshold_is_flagged(self):
        diff = _diff("pkg/mod.py", [f"line_{i} = {i}" for i in range(21)])
        result = audit_diff(
            diff, task_type="fix", investigated_files={"pkg/mod.py"}, max_lines=20
        )
        assert any("threshold" in f for f in result.flags)
        assert result.passed is False

    def test_threshold_aggregates_across_multiple_files(self):
        diff = _diff("pkg/a.py", [f"a{i} = 1" for i in range(11)]) + _diff(
            "pkg/b.py", [f"b{i} = 1" for i in range(10)]
        )
        result = audit_diff(
            diff,
            task_type="fix",
            investigated_files={"pkg/a.py", "pkg/b.py"},
            max_lines=20,
        )
        assert result.stats["total_lines_changed"] == 21
        assert any("threshold" in f for f in result.flags)

    def test_non_positive_max_lines_raises(self):
        with pytest.raises(ValueError):
            audit_diff("", max_lines=0)


class TestTestOnlyDiffDetection:
    def test_test_only_diff_flagged_for_fix_task(self):
        diff = _diff("pkg/tests/test_mod.py", ["def test_x(): assert True"])
        result = audit_diff(
            diff, task_type="fix", investigated_files={"pkg/tests/test_mod.py"}
        )
        assert any("test" in f.lower() and "only" in f.lower() for f in result.flags)
        assert result.passed is False

    def test_test_only_diff_flagged_for_feature_task(self):
        diff = _diff("pkg/test_mod.py", ["def test_x(): assert True"])
        result = audit_diff(
            diff, task_type="feature", investigated_files={"pkg/test_mod.py"}
        )
        assert any("only" in f.lower() for f in result.flags)

    def test_test_only_diff_not_flagged_for_refactor_task(self):
        diff = _diff("pkg/test_mod.py", ["def test_x(): assert True"])
        result = audit_diff(
            diff, task_type="refactor", investigated_files={"pkg/test_mod.py"}
        )
        assert not any("only" in f.lower() for f in result.flags)

    def test_diff_touching_both_test_and_impl_files_not_flagged(self):
        diff = _diff("pkg/test_mod.py", ["def test_x(): assert True"]) + _diff(
            "pkg/mod.py", ["def f(): return True"]
        )
        result = audit_diff(
            diff,
            task_type="fix",
            investigated_files={"pkg/test_mod.py", "pkg/mod.py"},
        )
        assert not any("only" in f.lower() for f in result.flags)

    def test_invalid_task_type_raises(self):
        with pytest.raises(ValueError):
            audit_diff("", task_type="nonsense")


class TestOutOfScopeFiles:
    def test_file_outside_investigated_set_is_flagged(self):
        diff = _diff("pkg/other.py", ["x = 1"])
        result = audit_diff(
            diff, task_type="fix", investigated_files={"pkg/mod.py"}
        )
        assert any("out" in f.lower() and "scope" in f.lower() or "pkg/other.py" in f for f in result.flags)
        assert result.passed is False

    def test_investigated_files_none_skips_scope_check(self):
        diff = _diff("pkg/other.py", ["x = 1"])
        result = audit_diff(diff, task_type="fix", investigated_files=None)
        assert result.passed is True

    def test_investigated_files_empty_set_flags_everything_touched(self):
        diff = _diff("pkg/other.py", ["x = 1"])
        result = audit_diff(diff, task_type="fix", investigated_files=set())
        assert result.passed is False

    def test_file_within_investigated_set_not_flagged(self):
        diff = _diff("pkg/mod.py", ["x = 1"])
        result = audit_diff(
            diff, task_type="fix", investigated_files={"pkg/mod.py", "pkg/other.py"}
        )
        assert result.passed is True


class TestHardcodeLiteralDetection:
    def test_known_fixture_value_equality_is_flagged(self):
        diff = _diff("pkg/mod.py", ['if x == "test_input_3":', "    return True"])
        result = audit_diff(
            diff,
            task_type="fix",
            investigated_files={"pkg/mod.py"},
            known_fixture_values={"test_input_3"},
        )
        assert result.passed is False
        assert any("literal" in f.lower() for f in result.flags)

    def test_literal_not_in_known_fixtures_is_not_flagged(self):
        diff = _diff("pkg/mod.py", ['if x == "test_input_3":', "    return True"])
        result = audit_diff(
            diff,
            task_type="fix",
            investigated_files={"pkg/mod.py"},
            known_fixture_values={"some_other_value"},
        )
        assert result.passed is True

    def test_heuristic_mode_flags_test_like_literal(self):
        diff = _diff("pkg/mod.py", ['if x == "test_input_3":', "    return True"])
        result = audit_diff(
            diff,
            task_type="fix",
            investigated_files={"pkg/mod.py"},
            known_fixture_values=None,
        )
        assert result.passed is False

    def test_heuristic_mode_does_not_flag_benign_literal(self):
        diff = _diff("pkg/mod.py", ['if status == "active":', "    return True"])
        result = audit_diff(
            diff,
            task_type="fix",
            investigated_files={"pkg/mod.py"},
            known_fixture_values=None,
        )
        assert result.passed is True

    def test_strict_equality_js_style_is_detected(self):
        diff = _diff("pkg/mod.js", ['if (x === "test_case_2") return true;'])
        result = audit_diff(
            diff,
            task_type="fix",
            investigated_files={"pkg/mod.js"},
            known_fixture_values={"test_case_2"},
        )
        assert result.passed is False

    def test_java_style_equals_call_is_detected(self):
        diff = _diff("pkg/Mod.java", ['if (x.equals("test_case_2")) return true;'])
        result = audit_diff(
            diff,
            task_type="fix",
            investigated_files={"pkg/Mod.java"},
            known_fixture_values={"test_case_2"},
        )
        assert result.passed is False

    def test_numeric_literal_equality_flagged_when_matching_known_fixtures(self):
        diff = _diff(
            "pkg/mod.js",
            ["if (array.length === 7 && size === 3) {", "  return special;", "}"],
        )
        result = audit_diff(
            diff,
            task_type="fix",
            investigated_files={"pkg/mod.js"},
            known_fixture_values={"7", "3"},
        )
        assert result.passed is False
        assert any("literal" in f.lower() for f in result.flags)

    def test_numeric_literal_not_in_known_fixtures_is_not_flagged(self):
        diff = _diff("pkg/mod.js", ["if (retries === 3) {", "  return null;", "}"])
        result = audit_diff(
            diff,
            task_type="fix",
            investigated_files={"pkg/mod.js"},
            known_fixture_values={"42"},
        )
        assert result.passed is True

    def test_bare_numeric_literal_not_flagged_heuristically_by_default(self):
        # Numeric equality checks (== 0, === 3) are extremely common in
        # legitimate code; without known_fixture_values we must not flag
        # them heuristically or every diff would trip this check.
        diff = _diff("pkg/mod.py", ["if x == 0:", "    return None"])
        result = audit_diff(
            diff,
            task_type="fix",
            investigated_files={"pkg/mod.py"},
            known_fixture_values=None,
        )
        assert result.passed is True

    def test_binary_files_are_not_scanned_for_literals(self):
        diff = "\n".join(
            [
                "diff --git a/img.png b/img.png",
                "index 111..222 100644",
                "Binary files a/img.png and b/img.png differ",
            ]
        )
        result = audit_diff(
            diff,
            task_type="fix",
            investigated_files={"img.png"},
            known_fixture_values={"test_input_3"},
        )
        assert result.passed is True


class TestMultipleFlags:
    def test_multiple_violations_all_reported(self):
        diff = _diff(
            "pkg/other.py",
            [f"line_{i} = {i}" for i in range(25)] + ['if x == "test_input_3":'],
        )
        result = audit_diff(
            diff,
            task_type="fix",
            investigated_files={"pkg/mod.py"},  # different file -> out of scope
            max_lines=20,
            known_fixture_values={"test_input_3"},
        )
        assert result.passed is False
        assert len(result.flags) >= 3
