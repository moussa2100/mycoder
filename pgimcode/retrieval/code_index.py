"""Lightweight code index for top-level symbols."""

from __future__ import annotations

import re
from pathlib import Path


_SYMBOL_PATTERN = re.compile(r"^\s*(?:async\s+def|def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)


def build_code_index(root: Path, max_files: int = 200) -> dict[str, dict]:
    """Index Python files with simple top-level symbol extraction."""
    index: dict[str, dict] = {}
    for idx, path in enumerate(root.rglob("*.py"), start=1):
        if idx > max_files:
            break
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        index[rel] = {
            "symbols": _SYMBOL_PATTERN.findall(text)[:20],
        }
    return index
