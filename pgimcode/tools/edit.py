"""Safe file editing primitives."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import difflib


@dataclass
class EditResult:
    success: bool
    path: Path
    operation: str  # replace_block | patch_file | create_file | delete_file
    message: str
    before: str = ""
    after: str = ""
    start_line: int = 0
    end_line: int = 0


def replace_block(path: Path, old_text: str, new_text: str) -> EditResult:
    """Replace the first exact occurrence of old_text with new_text."""
    if not path.exists():
        return EditResult(success=False, path=path, operation="replace_block", message="File does not exist")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return EditResult(success=False, path=path, operation="replace_block", message=str(e))

    count = text.count(old_text)
    if count == 0:
        return EditResult(success=False, path=path, operation="replace_block", message="old_text not found")
    if count > 1:
        return EditResult(success=False, path=path, operation="replace_block", message="old_text found multiple times; be more specific")

    start = text.index(old_text)
    before = text[:start + len(old_text)]
    after_text = text.replace(old_text, new_text, 1)

    # Compute line numbers
    start_line = text[:start].count("\n") + 1
    end_line = start_line + old_text.count("\n")

    try:
        path.write_text(after_text, encoding="utf-8")
    except Exception as e:
        return EditResult(success=False, path=path, operation="replace_block", message=str(e))

    return EditResult(
        success=True, path=path, operation="replace_block",
        message="Replaced block successfully",
        before=before, after=after_text,
        start_line=start_line, end_line=end_line,
    )


def patch_file(path: Path, patch_text: str) -> EditResult:
    """Apply a unified diff to a file."""
    if not path.exists():
        return EditResult(success=False, path=path, operation="patch_file", message="File does not exist")
    try:
        original = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return EditResult(success=False, path=path, operation="patch_file", message=str(e))

    # Parse unified diff and apply
    lines = patch_text.splitlines(keepends=True)
    # Collect all non-metadata lines
    old_lines = original.splitlines(keepends=True)
    new_lines = list(old_lines)

    # Simple unified diff parser: look for @@ -l,s +l,s @@ and apply hunks
    i = 0
    hunks = []
    current_hunk = []
    in_hunk = False
    target_line = None

    for line in lines:
        if line.startswith("@@"):
            if current_hunk:
                hunks.append((target_line, current_hunk))
                current_hunk = []
            in_hunk = True
            # Parse @@ -start,count +start,count @@
            # Simple: find -N,M and take N as target start (1-indexed)
            parts = line.split()
            for p in parts:
                if p.startswith("-"):
                    try:
                        target_line = int(p[1:].split(",")[0])
                    except ValueError:
                        pass
                    break
            continue
        if in_hunk:
            if line.startswith("+"):
                current_hunk.append(("add", line[1:]))
            elif line.startswith("-"):
                current_hunk.append(("remove", line[1:]))
            elif line.startswith(" "):
                current_hunk.append(("context", line[1:]))
            else:
                # End of hunk
                if current_hunk:
                    hunks.append((target_line, current_hunk))
                    current_hunk = []
                in_hunk = False

    if current_hunk:
        hunks.append((target_line, current_hunk))

    # Apply hunks in reverse order to preserve line numbers
    try:
        for target_line, hunk in reversed(hunks):
            if target_line is None:
                continue
            idx = target_line - 1  # 0-indexed
            offset = 0
            for op, content in hunk:
                if op == "context":
                    if idx + offset >= len(new_lines):
                        raise ValueError("Diff context out of range")
                    # Verify context matches
                    if new_lines[idx + offset].rstrip("\n") != content.rstrip("\n"):
                        raise ValueError(f"Diff context mismatch at line {idx + offset + 1}")
                    offset += 1
                elif op == "remove":
                    if idx + offset >= len(new_lines):
                        raise ValueError("Diff remove out of range")
                    if new_lines[idx + offset].rstrip("\n") != content.rstrip("\n"):
                        raise ValueError(f"Diff remove mismatch at line {idx + offset + 1}")
                    del new_lines[idx + offset]
                elif op == "add":
                    new_lines.insert(idx + offset, content if content.endswith("\n") else content + "\n")
                    offset += 1
    except ValueError as e:
        return EditResult(success=False, path=path, operation="patch_file", message=str(e))

    new_text = "".join(new_lines)
    try:
        path.write_text(new_text, encoding="utf-8")
    except Exception as e:
        return EditResult(success=False, path=path, operation="patch_file", message=str(e))

    start_line = hunks[0][0] if hunks else 0
    end_line = start_line + sum(1 for _, h in hunks for op, _ in h if op in ("add", "remove"))

    return EditResult(
        success=True, path=path, operation="patch_file",
        message="Patch applied successfully",
        before=original, after=new_text,
        start_line=start_line, end_line=end_line,
    )


def create_file(path: Path, content: str, overwrite: bool = False) -> EditResult:
    """Create a new file with given content."""
    if path.exists() and not overwrite:
        return EditResult(success=False, path=path, operation="create_file", message="File already exists (use overwrite=True)")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except Exception as e:
        return EditResult(success=False, path=path, operation="create_file", message=str(e))
    return EditResult(success=True, path=path, operation="create_file", message="File created successfully")


def delete_file(path: Path) -> EditResult:
    """Delete a file."""
    if not path.exists():
        return EditResult(success=False, path=path, operation="delete_file", message="File does not exist")
    try:
        path.unlink()
    except Exception as e:
        return EditResult(success=False, path=path, operation="delete_file", message=str(e))
    return EditResult(success=True, path=path, operation="delete_file", message="File deleted successfully")