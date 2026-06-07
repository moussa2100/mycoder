"""Relationship-aware file linking using lightweight Python import parsing."""

from __future__ import annotations

import re
from pathlib import Path


IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z0-9_\.]+)|^\s*from\s+([A-Za-z0-9_\.]+)\s+import", re.MULTILINE)


def _module_name(path: Path) -> str:
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def build_relationship_index(root: Path, max_files: int = 200) -> dict[str, list[str]]:
    """Map files to nearby related files based on import relationships."""
    py_files = [path.relative_to(root) for path in root.rglob("*.py")][:max_files]
    module_map = {_module_name(path): path.as_posix() for path in py_files}
    relationships: dict[str, set[str]] = {path.as_posix(): set() for path in py_files}
    for rel_path in py_files:
        abs_path = root / rel_path
        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in IMPORT_RE.finditer(text):
            module = match.group(1) or match.group(2) or ""
            candidates = [module]
            if "." in module:
                candidates.append(module.rsplit(".", 1)[0])
            for candidate in candidates:
                related = module_map.get(candidate)
                if related and related != rel_path.as_posix():
                    relationships[rel_path.as_posix()].add(related)
    return {path: sorted(values)[:8] for path, values in relationships.items() if values}
