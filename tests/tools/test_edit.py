"""Tests for edit.py utilities."""

import tempfile
from pathlib import Path

import pytest

from pgimcode.tools.edit import (
    EditResult,
    replace_block,
    patch_file,
    create_file,
    delete_file,
)


def test_replace_block_success():
    """Test replacing a block of text in a file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\nline 3\n")
        path = Path(f.name)

    try:
        result = replace_block(path, "line 2", "REPLACED")
        assert result.success is True
        assert result.operation == "replace_block"
        content = path.read_text()
        assert content == "line 1\nREPLACED\nline 3\n"
    finally:
        path.unlink()


def test_replace_block_not_found():
    """Test error when old_text not present."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\n")
        path = Path(f.name)

    try:
        result = replace_block(path, "nonexistent", "replacement")
        assert result.success is False
        assert "not found" in result.message
    finally:
        path.unlink()


def test_replace_block_ambiguous():
    """Test error when old_text appears twice."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line A\nline B\nline A\n")
        path = Path(f.name)

    try:
        result = replace_block(path, "line A", "REPLACED")
        assert result.success is False
        assert "multiple times" in result.message
    finally:
        path.unlink()


def test_patch_file_success():
    """Test applying a unified diff patch."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\nline 3\n")
        path = Path(f.name)

    try:
        # Unified diff to replace "line 2" with "REPLACED"
        patch = """--- a
+++ b
@@ -1,3 +1,3 @@
 line 1
-line 2
+REPLACED
 line 3
"""
        result = patch_file(path, patch)
        assert result.success is True
        content = path.read_text()
        assert content == "line 1\nREPLACED\nline 3\n"
    finally:
        path.unlink()


def test_create_file():
    """Test creating a new file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "newfile.txt"
        result = create_file(path, "hello world")
        assert result.success is True
        assert path.exists()
        assert path.read_text() == "hello world"


def test_create_file_no_overwrite():
    """Test that create_file fails when file exists and overwrite=False."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("existing content")
        path = Path(f.name)

    try:
        result = create_file(path, "new content", overwrite=False)
        assert result.success is False
        assert "already exists" in result.message
    finally:
        path.unlink()


def test_delete_file():
    """Test deleting a file."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        path = Path(f.name)

    assert path.exists()
    result = delete_file(path)
    assert result.success is True
    assert not path.exists()


def test_delete_file_nonexistent():
    """Test deleting a nonexistent file returns error."""
    result = delete_file(Path("/nonexistent/file.txt"))
    assert result.success is False
    assert "does not exist" in result.message