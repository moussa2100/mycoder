"""Skill discovery, loading, and management for the pgimcode terminal CLI.

Skills are progressive-disclosure knowledge files stored under ``/skills/``
in the virtual filesystem (or ``<project_root>/skills/`` on disk).
This module provides a ``SkillManager`` that discovers available skills,
reads their metadata, and loads their full content for injection into
the agent's system prompt.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


SKILLS_ROOT = Path("/skills")


def _find_project_root() -> Path:
    """Find the project root by looking for pyproject.toml upward from cwd."""
    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return cwd


class SkillInfo:
    """Metadata about a discovered skill."""

    def __init__(self, name: str, description: str, path: Path, category: str):
        self.name = name
        self.description = description
        self.path = path
        self.category = category  # e.g. "coding", "workflow"

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
            "path": str(self.path),
            "category": self.category,
        }


def _parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse YAML-like frontmatter between ``---`` delimiters.

    Only supports simple ``key: value`` pairs (no nested structures).
    Returns an empty dict if no frontmatter is found.
    """
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}
    meta: dict[str, Any] = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip().strip('"').strip("'")
    return meta


class SkillManager:
    """Discovers, loads, and manages skills for the agent.

    Searches for skills in the virtual filesystem path ``/skills/`` first,
    then falls back to ``<project_root>/skills/`` on the real filesystem.

    Usage:
        manager = SkillManager()
        all_skills = manager.list_skills()
        content = manager.load_skill("Python Coding Standards")
    """

    def __init__(self, skills_root: str | Path | None = None) -> None:
        self._root = Path(skills_root or SKILLS_ROOT)
        self._cache: dict[str, SkillInfo] = {}
        self._fallback_root = _find_project_root() / "skills"

    def _discover_from(self, root: Path) -> list[SkillInfo]:
        """Scan a single directory for SKILL.md files and return SkillInfo list."""
        results: list[SkillInfo] = []
        if not root.exists():
            return results
        for skill_file in sorted(root.rglob("SKILL.md")):
            category = skill_file.parent.name if skill_file.parent != root else ""
            try:
                text = skill_file.read_text(encoding="utf-8")
            except OSError:
                continue
            meta = _parse_frontmatter(text)
            name = meta.get("name", skill_file.parent.name)
            description = meta.get("description", "")
            info = SkillInfo(
                name=name,
                description=description,
                path=skill_file,
                category=category,
            )
            results.append(info)
        return results

    def list_skills(self) -> list[SkillInfo]:
        """Discover all available skills by scanning the skills directory.

        Returns a list of ``SkillInfo`` objects sorted by category then name.
        """
        if self._cache:
            return list(self._cache.values())

        # Try virtual filesystem path first, then fallback to project root
        all_skills = self._discover_from(self._root)
        if not all_skills:
            all_skills = self._discover_from(self._fallback_root)

        for info in all_skills:
            self._cache[info.name] = info

        return list(self._cache.values())

    def get_skill(self, name: str) -> SkillInfo | None:
        """Look up a skill by name (case-insensitive partial match)."""
        self.list_skills()  # ensure cache is populated
        # Exact match first
        if name in self._cache:
            return self._cache[name]
        # Case-insensitive
        lower = name.lower()
        for info in self._cache.values():
            if info.name.lower() == lower:
                return info
        # Partial match
        for info in self._cache.values():
            if lower in info.name.lower():
                return info
        return None

    def load_skill(self, name: str) -> str | None:
        """Load the full content of a skill by name.

        Returns the raw markdown content, or ``None`` if not found.
        """
        info = self.get_skill(name)
        if info is None:
            return None
        try:
            return info.path.read_text(encoding="utf-8")
        except OSError:
            return None

    def load_skill_content(self, skill_path: str | Path) -> str | None:
        """Load skill content directly from a path (used by middleware)."""
        try:
            return Path(skill_path).read_text(encoding="utf-8")
        except OSError:
            return None

    def get_skills_by_category(self, category: str) -> list[SkillInfo]:
        """Filter skills by category (e.g. 'coding', 'workflow')."""
        return [s for s in self.list_skills() if s.category == category]

    def invalidate_cache(self) -> None:
        """Clear the cached skill list (e.g. after adding a new skill)."""
        self._cache.clear()
