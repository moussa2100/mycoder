"""Tests for test_runner.py utilities."""

import tempfile
from pathlib import Path

import pytest

from pgimcode.tools.test_runner import (
    detect_framework,
    run_tests,
    TestResult,
)


def test_detect_framework_pytest():
    """Detect pytest in current repo."""
    framework = detect_framework(Path("."))
    assert framework == "pytest"


def test_run_tests_pytest():
    """Run pytest on a tiny temp project, verify detection + pass count."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # Create a minimal pytest project
        (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\nasyncio_mode = 'auto'\n")
        test_file = root / "tests" / "test_demo.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def test_demo():\n    assert True\n")

        result = run_tests(root, framework="pytest", timeout=30)
        assert result.framework == "pytest"
        assert result.total > 0
        assert result.pass_count > 0


def test_detect_framework_none():
    """Tmp dir with no test framework -> None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        framework = detect_framework(Path(tmpdir))
        assert framework is None


def test_detect_framework_pyproject_toml():
    """Detect pytest from pyproject.toml."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "pyproject.toml").write_text("[tool.pytest.ini_options]")
        framework = detect_framework(Path(tmpdir))
        assert framework == "pytest"


def test_detect_framework_package_json():
    """Detect npm from package.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "package.json").write_text("{}")
        framework = detect_framework(Path(tmpdir))
        assert framework == "npm"


def test_detect_framework_cargo_toml():
    """Detect cargo from Cargo.toml."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "Cargo.toml").write_text("[package]")
        framework = detect_framework(Path(tmpdir))
        assert framework == "cargo"


def test_detect_framework_go_mod():
    """Detect go from go.mod."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "go.mod").write_text("module example.com")
        framework = detect_framework(Path(tmpdir))
        assert framework == "go"


def test_detect_framework_tests_directory():
    """Detect pytest from tests directory with .py files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tests_dir = Path(tmpdir) / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_foo.py").write_text("def test_foo(): pass")
        framework = detect_framework(Path(tmpdir))
        assert framework == "pytest"


def test_run_tests_unknown_framework():
    """Test run_tests with unknown framework."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_tests(Path(tmpdir), framework="unknown")
        assert result.success is False
        assert result.framework == "unknown"
        assert "Unknown framework" in result.stderr


def test_run_tests_no_framework():
    """Test run_tests with no framework detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_tests(Path(tmpdir), framework=None)
        assert result.success is False
        assert result.framework == "unknown"
        assert "No test framework detected" in result.stderr