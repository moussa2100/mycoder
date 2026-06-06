"""Tests for symbols.py utilities."""

import tempfile
from pathlib import Path

import pytest

from pgimcode.tools.symbols import find_symbol, find_references


def test_find_symbol():
    """Test finding symbols in a Python file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("""\
def hello():
    pass

class MyClass:
    def method(self):
        pass

def hello_world():
    pass
""")
        path = Path(f.name)

    try:
        # Find "hello" function
        results = find_symbol("hello", path)
        assert len(results) > 0
        # Should match both "hello" and "hello_world"
        names = [s.name for s in results]
        assert "hello" in names or "hello_world" in names

        # Find exact match
        results = find_symbol("MyClass", path)
        assert len(results) > 0
        assert any(s.name == "MyClass" for s in results)
    finally:
        path.unlink()


def test_find_symbol_nonexistent():
    """Test finding nonexistent symbol returns empty."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def foo():\n    pass\n")
        path = Path(f.name)

    try:
        results = find_symbol("nonexistent", path)
        assert results == []
    finally:
        path.unlink()


def test_find_symbol_nonexistent_file():
    """Test finding symbol in nonexistent file returns empty."""
    results = find_symbol("foo", Path("/nonexistent/file.py"))
    assert results == []


def test_find_references():
    """Test finding references to a name in a file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("""\
def hello():
    return "hello"

result = hello()
print(hello())
""")
        path = Path(f.name)

    try:
        refs = find_references("hello", path)
        # Should find references (2 calls + 1 assignment, minus 1 def)
        assert len(refs) >= 2
    finally:
        path.unlink()


def test_find_references_excludes_def():
    """Test that find_references excludes the definition line."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("""\
def foo():
    return foo()
""")
        path = Path(f.name)

    try:
        refs = find_references("foo", path)
        # Should only find the call inside, not the definition
        for ref in refs:
            assert not ref.name.startswith("def foo")
    finally:
        path.unlink()


def test_find_references_nonexistent():
    """Test finding references in nonexistent file."""
    refs = find_references("foo", Path("/nonexistent/file.py"))
    assert refs == []