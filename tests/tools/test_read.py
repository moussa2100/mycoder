"""Tests for read.py utilities."""

import tempfile
from pathlib import Path

import pytest

from pgimcode.tools.read import (
    ReadResult,
    read_file,
    read_file_chunk,
    file_exists,
    count_lines,
)


def test_read_file_basic():
    """Test basic file reading."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\nline 3")  # no trailing newline
        path = Path(f.name)

    try:
        result = read_file(path)
        assert isinstance(result, ReadResult)
        assert result.path == path
        assert result.content == "line 1\nline 2\nline 3"
        assert result.total_lines == 3
        assert result.truncated is False
    finally:
        path.unlink()


def test_read_file_nonexistent():
    """Test reading nonexistent file returns empty result."""
    result = read_file(Path("/nonexistent/file.txt"))
    assert result.content == ""
    assert result.total_lines == 0
    assert result.truncated is False


def test_read_file_max_lines():
    """Test truncation by max_lines."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("\n".join(f"line {i}" for i in range(2000)))
        path = Path(f.name)

    try:
        result = read_file(path, max_lines=100)
        assert result.truncated is True
        assert "truncated at 100 lines" in result.content
        assert result.total_lines == 2000
    finally:
        path.unlink()


def test_read_file_max_chars():
    """Test truncation by max_chars."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a" * 100000)
        path = Path(f.name)

    try:
        result = read_file(path, max_chars=50000)
        assert result.truncated is True
        assert "truncated at 50000 chars" in result.content
    finally:
        path.unlink()


def test_read_file_chunk():
    """Test reading a specific line range."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\nline 3\nline 4\nline 5\n")
        path = Path(f.name)

    try:
        # 1-indexed lines
        result = read_file_chunk(path, 2, 4)
        assert result.content == "line 2\nline 3\nline 4"
        assert result.total_lines == 5
    finally:
        path.unlink()


def test_read_file_chunk_out_of_bounds():
    """Test reading line range that exceeds file bounds."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\n")
        path = Path(f.name)

    try:
        result = read_file_chunk(path, 1, 100)
        assert result.content == "line 1\nline 2"
        assert result.total_lines == 2
    finally:
        path.unlink()


def test_file_exists():
    """Test file_exists function."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        path = Path(f.name)

    try:
        assert file_exists(path) is True
        assert file_exists(Path("/nonexistent")) is False
    finally:
        path.unlink()


def test_count_lines():
    """Test count_lines function."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\nline 3")  # no trailing newline
        path = Path(f.name)

    try:
        assert count_lines(path) == 3
    finally:
        path.unlink()


def test_count_lines_nonexistent():
    """Test count_lines returns 0 for nonexistent file."""
    assert count_lines(Path("/nonexistent/file.txt")) == 0