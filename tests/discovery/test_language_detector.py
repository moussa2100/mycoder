"""Tests for language and framework detection."""

from pathlib import Path

from pgimcode.discovery.repo_scanner import ScannedFile
from pgimcode.discovery.language_detector import (
    detect_language, detect_frameworks, find_entry_points,
    find_test_locations, find_dependency_files, infer_build_commands,
    annotate_languages,
)


def test_detect_language_python():
    assert detect_language(Path("foo.py")) == "python"
    assert detect_language(Path("bar.js")) == "javascript"
    assert detect_language(Path("baz.rs")) == "rust"


def test_detect_language_none():
    assert detect_language(Path("README")) is None


def test_annotate_languages():
    files = [
        ScannedFile(Path("a.py"), Path("/a.py"), 10, False),
        ScannedFile(Path("b.js"), Path("/b.js"), 20, False),
    ]
    annotated = annotate_languages(files)
    assert annotated[0].language == "python"
    assert annotated[1].language == "javascript"


def test_detect_frameworks_poetry(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'x'\n")
    files = [ScannedFile(Path("pyproject.toml"), tmp_path / "pyproject.toml", 50, False)]
    fw = detect_frameworks(files)
    assert "python" in fw
    assert "poetry" in fw


def test_find_entry_points():
    files = [
        ScannedFile(Path("src/main.py"), Path("/src/main.py"), 10, False, "python"),
        ScannedFile(Path("app.js"), Path("/app.js"), 20, False, "javascript"),
    ]
    eps = find_entry_points(files)
    assert "src/main.py" in eps


def test_find_test_locations():
    files = [
        ScannedFile(Path("tests/test_x.py"), Path("/tests/test_x.py"), 10, False, "python"),
        ScannedFile(Path("src/main.py"), Path("/src/main.py"), 10, False, "python"),
    ]
    locs = find_test_locations(files)
    assert "tests" in locs


def test_infer_build_commands():
    files = [ScannedFile(Path("pyproject.toml"), Path("/pyproject.toml"), 10, False)]
    cmds = infer_build_commands(files)
    assert "pytest" in cmds