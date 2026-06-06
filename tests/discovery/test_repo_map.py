"""Tests for repo map aggregation."""

from pathlib import Path

from pgimcode.discovery.repo_scanner import RepoScanner
from pgimcode.discovery.repo_map import build_repo_map, RepoMap


def test_build_repo_map(tmp_path):
    # Create a mini project
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main():\n    pass\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_main():\n    pass\n")
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'x'\n")
    (tmp_path / "requirements.txt").write_text("pytest\n")

    scanner = RepoScanner(tmp_path)
    repo_map = build_repo_map(scanner)

    assert repo_map.total_files == 4
    assert "python" in repo_map.languages
    assert "poetry" in repo_map.frameworks
    assert any("main.py" in ep for ep in repo_map.entry_points)
    assert "tests" in repo_map.test_locations
    assert "pyproject.toml" in repo_map.dependency_files
    assert "pytest" in repo_map.build_commands


def test_repo_map_markdown():
    rm = RepoMap(
        root=Path("/tmp/proj"),
        languages={"python": 5},
        frameworks=["poetry"],
        total_files=5,
        total_lines=42,
    )
    md = rm.to_markdown()
    assert "Repo Map: /tmp/proj" in md
    assert "python" in md
    assert "poetry" in md
    assert "**Total files:** 5" in md