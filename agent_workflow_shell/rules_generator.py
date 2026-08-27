"""Deterministic project scanner backing /setup-rules.

Scans package manifests and lockfiles (not a full-tree dump — bounded,
targeted reads only, per the token-cost controls in the build spec) to
produce a ProjectProfile, then renders it into a `docs/rules/<project>-
project.md` style document.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union

PathLike = Union[str, Path]

_IGNORED_DIR_NAMES = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    "target",
    "vendor",
}

_JS_TEST_FRAMEWORKS = ("jest", "mocha", "vitest", "jasmine", "ava")


@dataclass(frozen=True)
class ProjectProfile:
    project_name: str
    languages: Tuple[str, ...]
    package_managers: Tuple[str, ...]
    test_frameworks: Tuple[str, ...]
    test_command: Optional[str]
    lint_command: Optional[str]
    build_command: Optional[str]
    source_dirs: Tuple[str, ...]


def _scan_node(root: Path):
    package_json_path = root / "package.json"
    if not package_json_path.exists():
        return None

    name = None
    scripts = {}
    deps = {}

    try:
        data = json.loads(package_json_path.read_text())
        if isinstance(data, dict):
            name = data.get("name")
            scripts = data.get("scripts") or {}
            deps = {
                **(data.get("dependencies") or {}),
                **(data.get("devDependencies") or {}),
            }
    except json.JSONDecodeError:
        pass

    language = "TypeScript" if (root / "tsconfig.json").exists() else "JavaScript"

    if (root / "pnpm-lock.yaml").exists():
        manager = "pnpm"
    elif (root / "yarn.lock").exists():
        manager = "yarn"
    else:
        manager = "npm"

    test_frameworks = tuple(
        fw for fw in _JS_TEST_FRAMEWORKS if fw in deps
    )

    return {
        "name": name,
        "language": language,
        "manager": manager,
        "test_frameworks": test_frameworks,
        "test_command": scripts.get("test"),
        "lint_command": scripts.get("lint"),
        "build_command": scripts.get("build"),
    }


def _scan_python(root: Path):
    pyproject_path = root / "pyproject.toml"
    requirements_path = root / "requirements.txt"
    setup_py_path = root / "setup.py"

    if not (pyproject_path.exists() or requirements_path.exists() or setup_py_path.exists()):
        return None

    manager = "pip"
    if pyproject_path.exists():
        pyproject_text = pyproject_path.read_text()
        if re.search(r"^\[tool\.poetry\]", pyproject_text, re.MULTILINE):
            manager = "poetry"

    has_pytest = False
    if requirements_path.exists():
        for line in requirements_path.read_text().splitlines():
            candidate = line.split("#", 1)[0].strip()
            if re.match(r"^pytest([=<>!~\[]|$)", candidate):
                has_pytest = True
                break
    if not has_pytest and pyproject_path.exists():
        if re.search(r"\bpytest\b", pyproject_path.read_text()):
            has_pytest = True

    return {
        "manager": manager,
        "test_frameworks": ("pytest",) if has_pytest else (),
        "test_command": "pytest" if has_pytest else None,
    }


def scan_project(root: PathLike) -> ProjectProfile:
    """Scan a project directory for its tech stack, structure, and
    commands to run tests/lint/build.
    """
    root_path = Path(root)
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(f"project root does not exist: {root_path}")

    languages = []
    package_managers = []
    test_frameworks: Tuple[str, ...] = ()
    test_command = None
    lint_command = None
    build_command = None
    project_name = None

    node = _scan_node(root_path)
    if node is not None:
        languages.append(node["language"])
        package_managers.append(node["manager"])
        test_frameworks += node["test_frameworks"]
        test_command = test_command or node["test_command"]
        lint_command = lint_command or node["lint_command"]
        build_command = build_command or node["build_command"]
        project_name = project_name or node["name"]

    python = _scan_python(root_path)
    if python is not None:
        languages.append("Python")
        package_managers.append(python["manager"])
        test_frameworks += python["test_frameworks"]
        test_command = test_command or python["test_command"]

    if (root_path / "Cargo.toml").exists():
        languages.append("Rust")
        package_managers.append("cargo")
        test_command = test_command or "cargo test"

    if (root_path / "go.mod").exists():
        languages.append("Go")
        package_managers.append("go modules")
        test_command = test_command or "go test ./..."

    if project_name is None:
        project_name = root_path.name

    source_dirs = sorted(
        entry.name
        for entry in root_path.iterdir()
        if entry.is_dir() and entry.name not in _IGNORED_DIR_NAMES
    )

    return ProjectProfile(
        project_name=project_name,
        languages=tuple(languages),
        package_managers=tuple(package_managers),
        test_frameworks=tuple(test_frameworks),
        test_command=test_command,
        lint_command=lint_command,
        build_command=build_command,
        source_dirs=tuple(source_dirs),
    )


def render_rules_doc(profile: ProjectProfile) -> str:
    """Render a ProjectProfile into a docs/rules/<project>-project.md body."""

    def _list_or_none(values: Tuple[str, ...]) -> str:
        return ", ".join(values) if values else "not detected"

    def _cmd_or_none(value: Optional[str]) -> str:
        return value if value else "not detected"

    lines = [
        f"# {profile.project_name} — Project Rules",
        "",
        "## Tech Stack",
        f"- Languages: {_list_or_none(profile.languages)}",
        f"- Package managers: {_list_or_none(profile.package_managers)}",
        f"- Test frameworks: {_list_or_none(profile.test_frameworks)}",
        "",
        "## Commands",
        f"- Test: `{_cmd_or_none(profile.test_command)}`",
        f"- Lint: `{_cmd_or_none(profile.lint_command)}`",
        f"- Build: `{_cmd_or_none(profile.build_command)}`",
        "",
        "## Structure",
        f"- Source directories: {_list_or_none(profile.source_dirs)}",
        "",
    ]
    return "\n".join(lines)
