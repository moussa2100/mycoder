"""Safe file reading utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ReadResult:
    path: Path
    content: str
    total_lines: int
    truncated: bool


def read_file(path: Path, max_chars: int = 50000, max_lines: int = 1000) -> ReadResult:
    """Read a text file, truncating if it exceeds limits."""
    if not path.exists():
        return ReadResult(path=path, content="", total_lines=0, truncated=False)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ReadResult(path=path, content="", total_lines=0, truncated=False)

    total_lines = text.count("\n") + 1
    truncated = False
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        text = "\n".join(lines) + "\n\n... [truncated at " + str(max_lines) + " lines]\n"
        truncated = True
    elif len(text) > max_chars:
        text = text[:max_chars] + "\n\n... [truncated at " + str(max_chars) + " chars]\n"
        truncated = True

    return ReadResult(path=path, content=text, total_lines=total_lines, truncated=truncated)


def read_file_chunk(path: Path, start_line: int, end_line: int) -> ReadResult:
    """Read a specific line range from a file (1-indexed)."""
    if not path.exists():
        return ReadResult(path=path, content="", total_lines=0, truncated=False)
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return ReadResult(path=path, content="", total_lines=0, truncated=False)

    total_lines = len(lines)
    start = max(0, start_line - 1)
    end = min(total_lines, end_line)
    chunk = "\n".join(lines[start:end])
    return ReadResult(path=path, content=chunk, total_lines=total_lines, truncated=False)


def file_exists(path: Path) -> bool:
    return path.exists() and path.is_file()


def count_lines(path: Path) -> int:
    try:
        return path.read_text(encoding="utf-8", errors="replace").count("\n") + 1
    except Exception:
        return 0