from pathlib import Path

import pytest

from agent_workflow_shell.skill_portability import check_portability

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"

EXPECTED_COMMANDS = {
    "fix.md",
    "spec.md",
    "build.md",
    "prd.md",
    "setup-rules.md",
    "create-skill.md",
}


class TestCommandFilesExist:
    def test_all_six_commands_are_present(self):
        found = {p.name for p in COMMANDS_DIR.glob("*.md")}
        assert EXPECTED_COMMANDS <= found

    @pytest.mark.parametrize("name", sorted(EXPECTED_COMMANDS))
    def test_command_has_valid_frontmatter_description(self, name):
        content = (COMMANDS_DIR / name).read_text()
        result = check_portability(content, max_description_tokens=200)
        assert not any("frontmatter" in v.lower() for v in result.violations), (
            name,
            result.violations,
        )
        assert not any("description field" in v for v in result.violations)


class TestFixCommandEnforcesEscalation:
    def test_fix_references_check_escalation_script(self):
        content = (COMMANDS_DIR / "fix.md").read_text()
        assert "check-escalation" in content
        assert "/spec" in content

    def test_fix_references_confidence_gate(self):
        content = (COMMANDS_DIR / "fix.md").read_text()
        assert "check-confidence" in content

    def test_fix_references_diff_audit(self):
        content = (COMMANDS_DIR / "fix.md").read_text()
        assert "audit-diff" in content


class TestSpecCommandEnforcesApprovalGate(object):
    def test_spec_has_explicit_approval_step(self):
        content = (COMMANDS_DIR / "spec.md").read_text()
        assert "Approve" in content
        assert "never skip" in content.lower()


class TestBuildCommandEnforcesRoundCap:
    def test_build_states_hard_cap_of_four_rounds(self):
        content = (COMMANDS_DIR / "build.md").read_text()
        assert "4" in content
        assert "no 5th round" in content.lower() or "never" in content.lower()

    def test_build_references_the_tested_controller(self):
        content = (COMMANDS_DIR / "build.md").read_text()
        assert "BuildLoopController" in content


class TestCreateSkillEnforcesPortabilityCheck:
    def test_create_skill_references_portability_script(self):
        content = (COMMANDS_DIR / "create-skill.md").read_text()
        assert "check-skill-portability" in content


class TestSetupRulesReferencesScanner:
    def test_setup_rules_references_scan_script(self):
        content = (COMMANDS_DIR / "setup-rules.md").read_text()
        assert "scan-rules" in content
        assert "never overwrite" in content.lower()


class TestCommandsResolveProjectSlugDeterministically:
    """Every reference to `docs/memory/<project>.md` (or `<project>-project.md`)
    used to leave `<project>` for the agent to guess fresh each run — the
    exact gap that let two sessions on the same repo pick different
    filenames. Each command must now resolve it via the deterministic
    `resolve-project-slug` script instead.
    """

    @pytest.mark.parametrize("name", sorted(EXPECTED_COMMANDS))
    def test_every_command_resolves_the_project_slug(self, name):
        content = (COMMANDS_DIR / name).read_text()
        assert "resolve-project-slug" in content, name

    @pytest.mark.parametrize("name", sorted(EXPECTED_COMMANDS))
    def test_project_placeholder_only_used_after_it_is_resolved(self, name):
        content = (COMMANDS_DIR / name).read_text()
        # Skip the frontmatter block (delimited by the first two `---`
        # lines): a `<project>` mention there is prose in the command's
        # description, not an instruction the agent executes in order.
        body = content.split("---", 2)[-1]
        if "<project>" not in body:
            return
        assert body.index("resolve-project-slug") < body.index("<project>"), name
