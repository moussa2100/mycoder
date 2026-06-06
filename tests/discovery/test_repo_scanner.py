"""Tests for repo scanner."""

from pathlib import Path

from pgimcode.discovery.repo_scanner import RepoScanner, ScannedFile


def test_scan_skips_git_dir(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n")

    scanner = RepoScanner(tmp_path)
    files = scanner.scan()
    paths = [f.path for f in files]
    assert Path("src/main.py") in paths
    assert not any(".git" in str(p) for p in paths)


def test_scan_skips_pycache(tmp_path):
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "foo.cpython-312.pyc").write_bytes(b"\x00")
    (tmp_path / "foo.py").write_text("x = 1\n")

    scanner = RepoScanner(tmp_path)
    files = scanner.scan()
    assert len(files) == 1
    assert files[0].path.name == "foo.py"


def test_binary_detection(tmp_path):
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")
    (tmp_path / "text.txt").write_text("hello world\n")

    scanner = RepoScanner(tmp_path)
    files = scanner.scan()
    by_name = {f.path.name: f for f in files}
    assert by_name["image.png"].is_binary is True
    assert by_name["text.txt"].is_binary is False