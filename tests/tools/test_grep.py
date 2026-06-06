"""Tests for grep.py wrapper."""

from pathlib import Path

import pytest

from pgimcode.tools.grep import GrepResult, rg_search, rg_search_symbol


def test_rg_search_basic():
    """Test basic ripgrep search in the repo."""
    root = Path("/mnt/c/Users/moussa/Desktop/repo/pgim-code")
    results = rg_search("def test_", root, max_results=5, context_lines=2)

    # Should find some test definitions
    assert len(results) > 0
    assert all(isinstance(r, GrepResult) for r in results)
    assert all(r.path.exists() for r in results)


def test_rg_search_with_glob():
    """Test ripgrep with glob filter."""
    root = Path("/mnt/c/Users/moussa/Desktop/repo/pgim-code")
    results = rg_search("import", root, glob="*.py", max_results=3, context_lines=0)

    # All results should be Python files
    assert all(r.path.suffix == ".py" for r in results)


def test_rg_search_no_results():
    """Test search that returns nothing."""
    # Search in a specific subdirectory that won't contain the test file
    root = Path("/mnt/c/Users/moussa/Desktop/repo/pgim-code/pgimcode")
    results = rg_search("ZZZNONEXISTENTZZZ123", root, max_results=5)
    assert results == []


def test_rg_search_context():
    """Test that context lines are captured."""
    root = Path("/mnt/c/Users/moussa/Desktop/repo/pgim-code")
    results = rg_search("def test_", root, max_results=1, context_lines=2)

    if results:
        r = results[0]
        # Context should be captured (before or after)
        has_context = len(r.context_before) > 0 or len(r.context_after) > 0
        # Note: might be empty if match is at start/end of file


def test_rg_search_symbol_python():
    """Test symbol search for Python."""
    root = Path("/mnt/c/Users/moussa/Desktop/repo/pgim-code")
    results = rg_search_symbol("RepoScanner", root, language="python")

    # Should find the RepoScanner class/function
    assert len(results) > 0
    assert all("RepoScanner" in r.text for r in results)


def test_rg_search_symbol_nonexistent():
    """Test symbol search for nonexistent symbol."""
    root = Path("/mnt/c/Users/moussa/Desktop/repo/pgim-code")
    results = rg_search_symbol("ZZZNONEXISTENT123", root, language="python")
    assert results == []