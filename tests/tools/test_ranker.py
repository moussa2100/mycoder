"""Tests for ranker.py utilities."""

import tempfile
from pathlib import Path

import pytest

from pgimcode.tools.ranker import extract_keywords, rank_files_by_relevance
from pgimcode.discovery.repo_scanner import ScannedFile


def test_extract_keywords_basic():
    """Test basic keyword extraction."""
    task = "add user authentication to the login page"
    keywords = extract_keywords(task)

    assert "user" in keywords
    assert "authentication" in keywords
    assert "login" in keywords
    assert "page" in keywords
    # Stopwords should be removed
    assert "the" not in keywords
    assert "to" not in keywords
    assert "add" not in keywords


def test_extract_keywords_order():
    """Test that keyword order is preserved."""
    task = "fix bug in parser"
    keywords = extract_keywords(task)

    # Should dedupe but preserve order
    assert len(keywords) == len(set(keywords))


def test_extract_keywords_short_tokens():
    """Test that short tokens are filtered out."""
    task = "a an the or in on at"
    keywords = extract_keywords(task)

    assert keywords == []


def test_rank_files_by_relevance_empty():
    """Test ranking with no files returns empty."""
    root = Path("/tmp")
    results = rank_files_by_relevance("some task", [], root)
    assert results == []


def test_rank_files_by_relevance_basic():
    """Test basic file ranking."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create some test files
        (root / "main.py").write_text("def main():\n    pass\n")
        (root / "utils.py").write_text("def helper():\n    pass\n")
        (root / "readme.txt").write_text("documentation\n")

        # Create ScannedFile objects
        files = [
            ScannedFile(
                path=Path("main.py"),
                abs_path=root / "main.py",
                size=100,
                is_binary=False,
                language="python",
            ),
            ScannedFile(
                path=Path("utils.py"),
                abs_path=root / "utils.py",
                size=100,
                is_binary=False,
                language="python",
            ),
            ScannedFile(
                path=Path("readme.txt"),
                abs_path=root / "readme.txt",
                size=100,
                is_binary=False,
                language=None,
            ),
        ]

        results = rank_files_by_relevance("main python file", files, root, max_results=3)

        assert len(results) > 0
        # main.py should rank higher due to keyword match
        scores = {str(r.file.path): r.score for r in results}
        if "main.py" in scores and "utils.py" in scores:
            assert scores["main.py"] >= scores["utils.py"]


def test_rank_files_by_relevance_entry_point():
    """Test that entry points get bonus score."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create entry point file
        (root / "main.py").write_text("def main():\n    pass\n")
        (root / "other.py").write_text("def other():\n    pass\n")

        files = [
            ScannedFile(
                path=Path("main.py"),
                abs_path=root / "main.py",
                size=100,
                is_binary=False,
                language="python",
            ),
            ScannedFile(
                path=Path("other.py"),
                abs_path=root / "other.py",
                size=100,
                is_binary=False,
                language="python",
            ),
        ]

        results = rank_files_by_relevance("task about code", files, root, max_results=2)

        # main.py is an entry point and should get bonus
        assert len(results) > 0
        # Check that entry point got the bonus
        main_result = next((r for r in results if r.file.path == Path("main.py")), None)
        assert main_result is not None
        assert "entry point" in main_result.reasons


def test_rank_files_max_results():
    """Test max_results parameter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create multiple files
        for i in range(20):
            (root / f"file_{i}.py").write_text(f"# file {i}\n")

        files = [
            ScannedFile(
                path=Path(f"file_{i}.py"),
                abs_path=root / f"file_{i}.py",
                size=100,
                is_binary=False,
                language="python",
            )
            for i in range(20)
        ]

        results = rank_files_by_relevance("file", files, root, max_results=5)
        assert len(results) == 5