"""Tests for symbol parser."""

from pathlib import Path

from pgimcode.discovery.symbol_parser import SymbolParser, _guess_language


def test_guess_language():
    assert _guess_language(Path("foo.py")) == "python"
    assert _guess_language(Path("bar.js")) == "javascript"
    assert _guess_language(Path("README")) is None


def test_parse_python_file(tmp_path):
    code = '''
import os
from typing import List

def hello(name: str) -> str:
    return f"Hello {name}"

class Greeter:
    def greet(self, name):
        return hello(name)
'''
    f = tmp_path / "test.py"
    f.write_text(code)

    parser = SymbolParser()
    result = parser.parse_file(f)

    assert result.language == "python"
    assert len(result.functions) >= 1
    assert any(s.name == "hello" for s in result.functions)
    assert len(result.classes) >= 1
    assert any(s.name == "Greeter" for s in result.classes)
    assert len(result.imports) >= 2


def test_parse_empty_file(tmp_path):
    f = tmp_path / "empty.py"
    f.write_text("")
    parser = SymbolParser()
    result = parser.parse_file(f)
    assert result.language == "python"
    assert result.functions == []
    assert result.classes == []


def test_unsupported_extension():
    # Should return gracefully without crashing
    parser = SymbolParser()
    result = parser.parse_file(Path("/does/not/exist.xyz"))
    assert result.language == "unknown"