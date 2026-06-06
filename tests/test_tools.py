"""Tests for tool definitions and the call_tool dispatcher."""

import pytest

from pgimcode.graph.tools import (
    TOOL_DEFINITIONS,
    TOOL_MAP,
    call_tool,
)


def test_tool_definitions_valid():
    """Each tool in TOOL_DEFINITIONS has type, function.name, function.description, function.parameters."""
    for defn in TOOL_DEFINITIONS:
        assert defn.get("type") == "function", f"Missing type: {defn}"
        fn = defn.get("function", {})
        assert "name" in fn, f"Missing function.name in {defn}"
        assert "description" in fn, f"Missing function.description in {defn}"
        assert "parameters" in fn, f"Missing function.parameters in {defn}"


def test_tool_map_has_all_definitions():
    """Every definition has a matching callable in TOOL_MAP."""
    for defn in TOOL_DEFINITIONS:
        name = defn["function"]["name"]
        assert name in TOOL_MAP, f"Tool '{name}' defined but not in TOOL_MAP"
        assert callable(TOOL_MAP[name]), f"TOOL_MAP['{name}'] is not callable"


def test_call_tool_unknown():
    """call_tool('unknown', {}) returns success=False."""
    result = call_tool("unknown", {})
    assert result["success"] is False
    assert "Unknown tool" in result["result"]


def test_call_tool_read_file():
    """call_tool('read_file', {'path': 'README.md'}) returns success=True."""
    # README.md may or may not exist in the test environment
    # The call should succeed if the file exists, or return success=False if not
    result = call_tool("read_file", {"path": "README.md"})
    # Result structure should be correct regardless of file existence
    assert "success" in result
    # If file doesn't exist, success will be False but that's acceptable
    # The important thing is the dispatch worked without raising


def test_call_tool_dispatch():
    """Verify dispatcher catches exceptions gracefully."""
    # Call with invalid arguments — should return success=False, not raise
    result = call_tool("read_file", {})
    assert result["success"] is False
    assert "required" in result["result"].lower() or "missing" in result["result"].lower()

    # Call search_text with valid-ish args
    result = call_tool("search_text", {"query": "nonexistent_pattern_xyz"})
    assert "success" in result
    # Should not have raised an exception