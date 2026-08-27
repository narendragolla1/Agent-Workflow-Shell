import pytest

from agent_workflow_shell.skill_portability import (
    PortabilityResult,
    check_portability,
)


GENERIC_SKILL = """---
name: extract-error-context
description: Use when a stack trace needs root-causing. Triggers on "stack trace", "traceback", "exception".
---

## Procedure
1. Find the file matching the top frame of the traceback.
2. Read the surrounding function.
3. Trace the call chain backwards until the invariant that broke is found.
"""


class TestGenericSkillPasses:
    def test_generic_skill_with_no_identifiers_passes(self):
        result = check_portability(GENERIC_SKILL)
        assert isinstance(result, PortabilityResult)
        assert result.passed is True
        assert result.violations == ()

    def test_generic_skill_passes_even_with_session_identifiers_supplied(self):
        result = check_portability(
            GENERIC_SKILL, session_identifiers=["UserAuthController", "parse_config"]
        )
        assert result.passed is True


class TestIdentifierLeakage:
    def test_flags_session_specific_class_name_in_body(self):
        skill = GENERIC_SKILL.replace(
            "2. Read the surrounding function.",
            "2. Read the surrounding function, e.g. UserAuthController.login().",
        )
        result = check_portability(skill, session_identifiers=["UserAuthController"])
        assert result.passed is False
        assert any("UserAuthController" in v for v in result.violations)

    def test_case_sensitive_identifier_match_does_not_false_positive(self):
        skill = GENERIC_SKILL.replace(
            "2. Read the surrounding function.",
            "2. Read the surrounding userauthcontroller helper.",
        )
        result = check_portability(skill, session_identifiers=["UserAuthController"])
        assert result.passed is True

    def test_empty_identifier_strings_are_ignored(self):
        result = check_portability(GENERIC_SKILL, session_identifiers=["", "   "])
        assert result.passed is True

    def test_none_identifiers_only_checks_generic_rules(self):
        result = check_portability(GENERIC_SKILL, session_identifiers=None)
        assert result.passed is True


class TestHardcodedPaths:
    def test_flags_unix_home_absolute_path(self):
        skill = GENERIC_SKILL.replace(
            "1. Find the file matching the top frame of the traceback.",
            "1. Open /home/user/PyTorch/src/parser.py directly.",
        )
        result = check_portability(skill)
        assert result.passed is False
        assert any("/home/user/PyTorch/src/parser.py" in v for v in result.violations)

    def test_flags_windows_absolute_path(self):
        skill = GENERIC_SKILL.replace(
            "1. Find the file matching the top frame of the traceback.",
            r"1. Open C:\Users\dev\project\parser.py directly.",
        )
        result = check_portability(skill)
        assert result.passed is False

    def test_generic_glob_pattern_is_not_flagged_as_a_path(self):
        result = check_portability(GENERIC_SKILL)
        assert result.passed is True


class TestDescriptionLength:
    def test_description_within_budget_passes(self):
        result = check_portability(GENERIC_SKILL, max_description_tokens=100)
        assert result.passed is True

    def test_description_over_budget_is_flagged(self):
        long_description = " ".join(["word"] * 150)
        skill = f"""---
name: too-verbose
description: {long_description}
---

Body text.
"""
        result = check_portability(skill, max_description_tokens=100)
        assert result.passed is False
        assert any("token" in v.lower() for v in result.violations)

    def test_description_exactly_at_budget_passes(self):
        description = " ".join(["word"] * 100)
        skill = f"""---
name: exactly-at-budget
description: {description}
---

Body text.
"""
        result = check_portability(skill, max_description_tokens=100)
        assert result.passed is True

    def test_missing_frontmatter_is_flagged_but_does_not_crash(self):
        result = check_portability("# Just a body, no frontmatter at all.")
        assert result.passed is False
        assert any("frontmatter" in v.lower() for v in result.violations)


class TestMultipleViolations:
    def test_all_violation_types_reported_together(self):
        long_description = " ".join(["word"] * 150)
        skill = f"""---
name: bad-skill
description: {long_description}
---

Open /home/user/PyTorch/foo.py and call UserAuthController.login() directly.
"""
        result = check_portability(
            skill,
            session_identifiers=["UserAuthController"],
            max_description_tokens=100,
        )
        assert result.passed is False
        assert len(result.violations) >= 3
