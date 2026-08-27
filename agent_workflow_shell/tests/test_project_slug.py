import json

import pytest

from agent_workflow_shell.project_slug import resolve_project_slug, slugify


class TestSlugify:
    def test_lowercases_and_hyphenates_spaces(self):
        assert slugify("Widget App") == "widget-app"

    def test_strips_scope_marker_from_npm_package_name(self):
        assert slugify("@my-org/widget-app") == "my-org-widget-app"

    def test_collapses_runs_of_punctuation_into_one_hyphen(self):
        assert slugify("widget__app!!") == "widget-app"

    def test_strips_leading_and_trailing_hyphens(self):
        assert slugify("--widget-app--") == "widget-app"

    def test_blank_name_falls_back_to_project(self):
        assert slugify("   ") == "project"


class TestResolveProjectSlug:
    def test_derives_slug_from_package_json_name(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({"name": "Widget App"}))
        assert resolve_project_slug(tmp_path) == "widget-app"

    def test_derives_slug_from_pyproject_toml_name(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "svc-api"\n')
        assert resolve_project_slug(tmp_path) == "svc-api"

    def test_falls_back_to_directory_name_when_no_manifest(self, tmp_path):
        project_dir = tmp_path / "My Cool Project"
        project_dir.mkdir()
        assert resolve_project_slug(project_dir) == "my-cool-project"

    def test_pins_slug_to_docs_memory_project_slug_file(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({"name": "widget-app"}))
        resolve_project_slug(tmp_path)
        pin_path = tmp_path / "docs" / "memory" / ".project-slug"
        assert pin_path.exists()
        assert pin_path.read_text().strip() == "widget-app"

    def test_second_call_reuses_pinned_slug_even_if_manifest_name_changes(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({"name": "widget-app"}))
        first = resolve_project_slug(tmp_path)

        (tmp_path / "package.json").write_text(json.dumps({"name": "renamed-app"}))
        second = resolve_project_slug(tmp_path)

        assert first == second == "widget-app"

    def test_two_independent_resolutions_on_a_fresh_checkout_agree(self, tmp_path):
        # Simulates two different sessions cloning the same repo (no
        # pinned slug yet) and each resolving it independently — the
        # scenario the missing project-slug resolution used to leave to
        # per-session LLM guesswork.
        (tmp_path / "package.json").write_text(json.dumps({"name": "widget-app"}))
        session_one = resolve_project_slug(tmp_path)

        pin_path = tmp_path / "docs" / "memory" / ".project-slug"
        pin_path.unlink()

        session_two = resolve_project_slug(tmp_path)
        assert session_one == session_two

    def test_nonexistent_root_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resolve_project_slug(tmp_path / "does-not-exist")
