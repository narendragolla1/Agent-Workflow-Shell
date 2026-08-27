import json

import pytest

from agent_workflow_shell.rules_generator import (
    ProjectProfile,
    render_rules_doc,
    scan_project,
)


def write(path, content=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestScanProjectNodeEcosystem:
    def test_detects_javascript_from_package_json(self, tmp_path):
        write(
            tmp_path / "package.json",
            json.dumps(
                {
                    "name": "widget-app",
                    "scripts": {"test": "jest", "lint": "eslint .", "build": "webpack"},
                    "devDependencies": {"jest": "^29.0.0"},
                }
            ),
        )
        profile = scan_project(tmp_path)
        assert isinstance(profile, ProjectProfile)
        assert "JavaScript" in profile.languages
        assert profile.project_name == "widget-app"
        assert "jest" in profile.test_frameworks
        assert profile.test_command == "jest"
        assert profile.lint_command == "eslint ."
        assert profile.build_command == "webpack"

    def test_defaults_to_npm_when_no_lockfile(self, tmp_path):
        write(tmp_path / "package.json", json.dumps({"name": "app"}))
        profile = scan_project(tmp_path)
        assert "npm" in profile.package_managers

    def test_detects_yarn_from_lockfile(self, tmp_path):
        write(tmp_path / "package.json", json.dumps({"name": "app"}))
        write(tmp_path / "yarn.lock", "")
        profile = scan_project(tmp_path)
        assert "yarn" in profile.package_managers
        assert "npm" not in profile.package_managers

    def test_detects_pnpm_from_lockfile_over_yarn(self, tmp_path):
        write(tmp_path / "package.json", json.dumps({"name": "app"}))
        write(tmp_path / "yarn.lock", "")
        write(tmp_path / "pnpm-lock.yaml", "")
        profile = scan_project(tmp_path)
        assert "pnpm" in profile.package_managers
        assert "yarn" not in profile.package_managers

    def test_typescript_replaces_javascript_when_tsconfig_present(self, tmp_path):
        write(tmp_path / "package.json", json.dumps({"name": "app"}))
        write(tmp_path / "tsconfig.json", "{}")
        profile = scan_project(tmp_path)
        assert "TypeScript" in profile.languages
        assert "JavaScript" not in profile.languages

    def test_malformed_package_json_does_not_crash(self, tmp_path):
        write(tmp_path / "package.json", "{not valid json,,,")
        profile = scan_project(tmp_path)
        assert "JavaScript" in profile.languages
        assert profile.test_command is None
        assert profile.test_frameworks == ()

    def test_no_test_script_leaves_test_command_none(self, tmp_path):
        write(tmp_path / "package.json", json.dumps({"name": "app"}))
        profile = scan_project(tmp_path)
        assert profile.test_command is None


class TestScanProjectPythonEcosystem:
    def test_detects_python_and_pytest_from_requirements_txt(self, tmp_path):
        write(tmp_path / "requirements.txt", "flask==2.0\npytest==7.4.0\n")
        profile = scan_project(tmp_path)
        assert "Python" in profile.languages
        assert "pytest" in profile.test_frameworks
        assert profile.test_command == "pytest"
        assert "pip" in profile.package_managers

    def test_detects_poetry_from_pyproject_toml(self, tmp_path):
        write(
            tmp_path / "pyproject.toml",
            "[tool.poetry]\nname = \"svc\"\nversion = \"0.1.0\"\n",
        )
        profile = scan_project(tmp_path)
        assert "poetry" in profile.package_managers
        assert "pip" not in profile.package_managers

    def test_pyproject_without_poetry_table_defaults_to_pip(self, tmp_path):
        write(tmp_path / "pyproject.toml", "[project]\nname = \"svc\"\n")
        profile = scan_project(tmp_path)
        assert "pip" in profile.package_managers

    def test_requirements_without_pytest_leaves_test_frameworks_empty(self, tmp_path):
        write(tmp_path / "requirements.txt", "flask==2.0\n")
        profile = scan_project(tmp_path)
        assert profile.test_frameworks == ()
        assert profile.test_command is None


class TestScanProjectOtherEcosystems:
    def test_detects_rust_from_cargo_toml(self, tmp_path):
        write(tmp_path / "Cargo.toml", "[package]\nname = \"svc\"\n")
        profile = scan_project(tmp_path)
        assert "Rust" in profile.languages
        assert "cargo" in profile.package_managers
        assert profile.test_command == "cargo test"

    def test_detects_go_from_go_mod(self, tmp_path):
        write(tmp_path / "go.mod", "module example.com/svc\n")
        profile = scan_project(tmp_path)
        assert "Go" in profile.languages
        assert profile.test_command == "go test ./..."


class TestScanProjectGeneral:
    def test_empty_directory_yields_empty_profile(self, tmp_path):
        profile = scan_project(tmp_path)
        assert profile.languages == ()
        assert profile.package_managers == ()
        assert profile.test_frameworks == ()
        assert profile.test_command is None

    def test_project_name_falls_back_to_directory_name(self, tmp_path):
        project_dir = tmp_path / "my-cool-project"
        project_dir.mkdir()
        profile = scan_project(project_dir)
        assert profile.project_name == "my-cool-project"

    def test_polyglot_project_detects_both_languages(self, tmp_path):
        write(tmp_path / "package.json", json.dumps({"name": "app"}))
        write(tmp_path / "requirements.txt", "pytest\n")
        profile = scan_project(tmp_path)
        assert "JavaScript" in profile.languages
        assert "Python" in profile.languages

    def test_source_dirs_excludes_ignored_directories(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "node_modules").mkdir()
        (tmp_path / ".git").mkdir()
        (tmp_path / "__pycache__").mkdir()
        profile = scan_project(tmp_path)
        assert "src" in profile.source_dirs
        assert "node_modules" not in profile.source_dirs
        assert ".git" not in profile.source_dirs
        assert "__pycache__" not in profile.source_dirs

    def test_nonexistent_root_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            scan_project(tmp_path / "does-not-exist")


class TestRenderRulesDoc:
    def test_render_includes_project_name_and_commands(self):
        profile = ProjectProfile(
            project_name="widget-app",
            languages=("JavaScript",),
            package_managers=("npm",),
            test_frameworks=("jest",),
            test_command="jest",
            lint_command="eslint .",
            build_command="webpack",
            source_dirs=("src", "test"),
        )
        doc = render_rules_doc(profile)
        assert "widget-app" in doc
        assert "jest" in doc
        assert "eslint ." in doc
        assert "src" in doc

    def test_render_marks_missing_commands_as_not_detected(self):
        profile = ProjectProfile(
            project_name="bare-project",
            languages=(),
            package_managers=(),
            test_frameworks=(),
            test_command=None,
            lint_command=None,
            build_command=None,
            source_dirs=(),
        )
        doc = render_rules_doc(profile)
        assert "not detected" in doc.lower()
