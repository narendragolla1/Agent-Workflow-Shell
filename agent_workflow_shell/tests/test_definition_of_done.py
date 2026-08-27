"""Acceptance tests mapping 1:1 to the build prompt's own
"Definition of done for this build itself" checklist:

- /fix correctly refuses a bug that spans 3+ files and points to /spec
- /build correctly caps at 4 rounds and reports unresolved criteria
  rather than looping indefinitely
- Anti-hardcoding audit catches at least one deliberately-planted
  hardcoded-fix test case
- /create-skill output passes a portability check (works when
  copy-pasted into a different sample repo)

These exercise the same deterministic modules the individual unit test
files already cover, but frame each scenario the way the spec itself
does, against the shipped examples/sample-project fixture.
"""

from pathlib import Path

from agent_workflow_shell.build_loop import BuildLoopController, Criterion
from agent_workflow_shell.diff_audit import audit_diff
from agent_workflow_shell.fix_escalation import should_escalate_to_spec
from agent_workflow_shell.skill_portability import check_portability

SAMPLE_PROJECT = Path(__file__).resolve().parents[2] / "examples" / "sample-project"


class TestFixRefusesMultiFileBug:
    def test_investigate_touching_four_files_escalates_to_spec(self):
        # A hypothetical bug in chunk() that also requires touching the
        # CLI wrapper, the docs generator, and the memory writer to fix
        # consistently — this is architecturally bigger than /fix's scope.
        investigated = {
            "src/chunk.js",
            "src/cli-wrapper.js",
            "src/docs-generator.js",
            "src/memory-writer.js",
        }
        decision = should_escalate_to_spec(investigated)
        assert decision.escalate is True
        assert "/spec" in decision.reason
        assert "3" in decision.reason or "files" in decision.reason.lower()

    def test_investigate_touching_two_files_does_not_escalate(self):
        decision = should_escalate_to_spec({"src/chunk.js", "test/chunk.test.js"})
        assert decision.escalate is False


class TestBuildCapsAtFourRounds:
    def test_build_loop_never_exceeds_four_rounds_and_reports_unresolved(self):
        criteria = [
            Criterion(name="oracle: chunk handles empty arrays", is_oracle=True),
            Criterion(name="lint passes"),
            Criterion(name="docs updated"),
        ]
        controller = BuildLoopController(criteria)
        rounds_seen = []

        def always_failing_judge(round_number):
            rounds_seen.append(round_number)
            return {c.name: False for c in criteria}

        report = controller.run(always_failing_judge)

        assert report.rounds_run == 4
        assert rounds_seen == [1, 2, 3, 4]
        assert report.status == "COMPLETE"
        assert len(report.unresolved_criteria) == 3
        assert "oracle: chunk handles empty arrays" in report.unresolved_criteria


class TestAntiHardcodingAuditCatchesPlantedFix:
    def test_real_fix_to_chunk_off_by_one_passes_the_gate(self):
        # A legitimate minimal fix: guard against size <= 0 at the root
        # cause, inside the implementation the bug actually lives in.
        legit_diff = (
            "diff --git a/src/chunk.js b/src/chunk.js\n"
            "--- a/src/chunk.js\n"
            "+++ b/src/chunk.js\n"
            "@@ -1,4 +1,7 @@\n"
            " function chunk(array, size) {\n"
            "+  if (size <= 0) {\n"
            "+    throw new Error(\"size must be a positive integer\");\n"
            "+  }\n"
            "   const chunks = [];\n"
        )
        result = audit_diff(
            legit_diff,
            task_type="fix",
            investigated_files={"src/chunk.js"},
            known_fixture_values={"7-item-input"},
        )
        assert result.passed is True

    def test_planted_hardcoded_fix_is_flagged_and_rejected(self):
        # A deliberately-planted bad "fix": instead of fixing the off-by-
        # one logic, it special-cases the exact failing test input so
        # that one test goes green without touching the actual bug.
        hardcoded_diff = (
            "diff --git a/src/chunk.js b/src/chunk.js\n"
            "--- a/src/chunk.js\n"
            "+++ b/src/chunk.js\n"
            "@@ -1,4 +1,9 @@\n"
            " function chunk(array, size) {\n"
            "+  if (array.length === 7 && size === 3) {\n"
            "+    return [[1, 2, 3], [4, 5, 6], [7]];\n"
            "+  }\n"
            "   const chunks = [];\n"
        )
        result = audit_diff(
            hardcoded_diff,
            task_type="fix",
            investigated_files={"src/chunk.js"},
            known_fixture_values={"7", "3"},
        )
        assert result.passed is False
        assert any("literal" in flag.lower() for flag in result.flags)

    def test_planted_hardcoded_fix_is_also_caught_heuristically(self):
        # Even without known_fixture_values supplied, a literal that
        # reads as fixture data (contains a digit, alnum token) trips
        # the heuristic — this is what /fix actually runs by default.
        hardcoded_diff = (
            "diff --git a/src/chunk.js b/src/chunk.js\n"
            "--- a/src/chunk.js\n"
            "+++ b/src/chunk.js\n"
            "@@ -1,4 +1,7 @@\n"
            " function chunk(array, size) {\n"
            '+  if (JSON.stringify(array) === "test_case_7") {\n'
            "+    return [[1, 2, 3], [4, 5, 6], [7]];\n"
            "+  }\n"
            "   const chunks = [];\n"
        )
        result = audit_diff(
            hardcoded_diff, task_type="fix", investigated_files={"src/chunk.js"}
        )
        assert result.passed is False


class TestCreateSkillPortabilityAcrossRepos:
    def test_skill_drafted_from_sample_project_session_passes_when_generalized(self):
        # The skill as it SHOULD be written: describes the pattern, not
        # this session's specific function/file.
        generalized_skill = """---
name: fix-array-chunking-edge-cases
description: Use when a chunking/batching function mishandles boundary sizes. Triggers on "off-by-one", "chunk", "batch size".
---

## Procedure
1. Find the function that splits a collection into fixed-size groups.
2. Check its behavior for: empty input, a non-positive size, and input
   length being an exact multiple of the chunk size.
3. Add a guard at the root cause, not a special case for one input shape.
"""
        # session_identifiers simulate what this session's actual names
        # were — the draft must not leak them even though it was written
        # while working in examples/sample-project.
        result = check_portability(
            generalized_skill,
            session_identifiers=["chunk.js", "chunk(array, size)", "sample-widget-app"],
        )
        assert result.passed is True

    def test_skill_that_leaks_session_specific_names_fails_before_handoff(self):
        # The skill as it SHOULD NOT be written: references this
        # session's specific file and function directly.
        leaky_skill = """---
name: fix-array-chunking-edge-cases
description: Use when a chunking/batching function mishandles boundary sizes.
---

## Procedure
1. Open src/chunk.js and look at the chunk(array, size) function.
2. Fix sample-widget-app's off-by-one bug the same way.
"""
        result = check_portability(
            leaky_skill,
            session_identifiers=["chunk.js", "chunk(array, size)", "sample-widget-app"],
        )
        assert result.passed is False
        assert len(result.violations) >= 3

    def test_generalized_skill_still_works_pasted_into_a_different_repo(self):
        # "Works when copy-pasted into a different sample repo": same
        # generalized draft, checked against an entirely different
        # session's identifiers — it must still pass, proving nothing
        # about it was actually tied to examples/sample-project.
        generalized_skill = """---
name: fix-array-chunking-edge-cases
description: Use when a chunking/batching function mishandles boundary sizes. Triggers on "off-by-one", "chunk", "batch size".
---

## Procedure
1. Find the function that splits a collection into fixed-size groups.
2. Check its behavior for: empty input, a non-positive size, and input
   length being an exact multiple of the chunk size.
3. Add a guard at the root cause, not a special case for one input shape.
"""
        different_repo_identifiers = [
            "PaymentBatcher.java",
            "splitIntoBatches",
            "checkout-service",
        ]
        result = check_portability(
            generalized_skill, session_identifiers=different_repo_identifiers
        )
        assert result.passed is True
