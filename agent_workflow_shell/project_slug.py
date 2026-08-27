"""Deterministic project-slug resolution shared by all workflow commands.

Every command file references `docs/memory/<project>.md`, but until now
`<project>` was a bare placeholder the agent had to fill in from scratch on
each run — two sessions on the same repo could pick different names and
silently fragment memory across files. `resolve_project_slug` fixes that:
it derives the slug from `rules_generator.scan_project` (the same
deterministic manifest scan `/setup-rules` already uses) and pins the
result in `docs/memory/.project-slug` on first use, so every later call —
same session or a fresh one — reads back the identical value instead of
re-deriving it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Union

from .rules_generator import scan_project

PathLike = Union[str, Path]

_PIN_FILENAME = ".project-slug"
_INVALID_CHARS_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Normalize a project/package name into a filesystem-safe slug.

    Lowercases, drops scope markers (`@org/pkg` -> `org-pkg`), and
    collapses any run of non-alphanumeric characters into a single hyphen.
    """
    normalized = name.strip().lower().replace("@", "").replace("/", "-")
    slug = _INVALID_CHARS_RE.sub("-", normalized).strip("-")
    return slug or "project"


def resolve_project_slug(root: PathLike, *, memory_dir: PathLike = "docs/memory") -> str:
    """Resolve the canonical project slug for `root`, pinning it on first use.

    The slug is cached at `<root>/<memory_dir>/.project-slug`. Once
    written, that pinned value is always returned — even if the
    underlying manifest name changes later — so `docs/memory/<slug>.md`
    stays the same file across every command and every session.
    """
    root_path = Path(root)
    pin_path = root_path / Path(memory_dir) / _PIN_FILENAME

    if pin_path.exists():
        cached = pin_path.read_text().strip()
        if cached:
            return cached

    profile = scan_project(root_path)
    slug = slugify(profile.project_name)

    pin_path.parent.mkdir(parents=True, exist_ok=True)
    pin_path.write_text(slug + "\n")
    return slug
