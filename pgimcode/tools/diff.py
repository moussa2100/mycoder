"""Diff generation and preview utilities."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class DiffResult:
    has_changes: bool
    unified_diff: str
    old_line_count: int
    new_line_count: int


def make_diff(old_text: str, new_text: str, label_a: str = "a", label_b: str = "b") -> str:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    # Ensure lines end with newline for clean diffs
    old_lines = [l if l.endswith("\n") else l + "\n" for l in old_lines]
    new_lines = [l if l.endswith("\n") else l + "\n" for l in new_lines]
    diff = list(difflib.unified_diff(old_lines, new_lines, fromfile=label_a, tofile=label_b))
    return "".join(diff)


def diff_preview(path: Path, edit_fn: Callable[[str], str]) -> DiffResult:
    """Run an edit function on a copy and return the diff without mutating the original."""
    if not path.exists():
        old_text = ""
    else:
        try:
            old_text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            old_text = ""
    new_text = edit_fn(old_text)
    unified = make_diff(old_text, new_text, label_a=str(path), label_b=str(path) + " (after)")
    return DiffResult(
        has_changes=old_text != new_text,
        unified_diff=unified,
        old_line_count=old_text.count("\n") + 1,
        new_line_count=new_text.count("\n") + 1,
    )