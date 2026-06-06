"""Tests for diff.py utilities."""

import tempfile
from pathlib import Path

import pytest

from pgimcode.tools.diff import (
    DiffResult,
    make_diff,
    diff_preview,
)


def test_make_diff():
    """Test make_diff produces unified diff format."""
    old = "line 1\nline 2\nline 3\n"
    new = "line 1\nREPLACED\nline 3\n"
    diff = make_diff(old, new, label_a="a.txt", label_b="b.txt")
    assert "--- a.txt" in diff
    assert "+++ b.txt" in diff
    assert "@@" in diff
    assert "-line 2" in diff
    assert "+REPLACED" in diff


def test_diff_preview():
    """Test diff_preview runs edit_fn without mutating original."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\nline 3\n")
        path = Path(f.name)

    try:
        # Define edit function
        def replace_line2(text: str) -> str:
            return text.replace("line 2", "REPLACED")

        result = diff_preview(path, replace_line2)
        assert isinstance(result, DiffResult)
        assert result.has_changes is True
        assert "REPLACED" in result.unified_diff

        # Verify original file unchanged
        original_content = path.read_text()
        assert original_content == "line 1\nline 2\nline 3\n"
    finally:
        path.unlink()


def test_diff_preview_no_changes():
    """Test diff_preview returns has_changes=False when no changes."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\n")
        path = Path(f.name)

    try:
        # Define edit function that does nothing
        def noop(text: str) -> str:
            return text

        result = diff_preview(path, noop)
        assert result.has_changes is False
        assert result.unified_diff == ""
    finally:
        path.unlink()


def test_diff_preview_nonexistent_file():
    """Test diff_preview handles nonexistent file."""
    path = Path("/nonexistent/file.txt")

    def noop(text: str) -> str:
        return text

    result = diff_preview(path, noop)
    assert result.has_changes is False
    assert result.old_line_count == 1  # empty text has 1 line
    assert result.new_line_count == 1