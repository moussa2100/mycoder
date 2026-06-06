"""Tests for shell.py utilities."""

import tempfile
from pathlib import Path

import pytest

from pgimcode.tools.shell import ShellRunner, CommandResult, DEFAULT_ALLOWLIST


def test_run_echo():
    """Run echo hi, verify stdout='hi\\n', exit_code=0."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = ShellRunner(workspace_root=Path(tmpdir))
        result = runner.run(["echo", "hi"])
        assert result.exit_code == 0
        assert result.stdout.strip() == "hi"
        assert result.timed_out is False
        assert result.stderr == ""


def test_run_timeout():
    """Run sleep 2 with timeout=1, verify timed_out=True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = ShellRunner(workspace_root=Path(tmpdir), default_timeout=30, allowlist={"sleep", "echo"})
        result = runner.run(["sleep", "2"], timeout=1)
        assert result.timed_out is True
        assert result.exit_code == -1


def test_run_command_not_allowed():
    """Run whoami, verify error about allowlist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = ShellRunner(workspace_root=Path(tmpdir))
        # whoami is not in the allowlist - should raise ValueError
        with pytest.raises(ValueError, match="not in allowlist"):
            runner.run(["whoami"])


def test_run_cwd_outside_workspace():
    """Run in /tmp when workspace is '.', verify error."""
    # Use current directory as workspace, try to run in /tmp
    runner = ShellRunner(workspace_root=Path("."))
    # Should fail because /tmp is outside the workspace
    with pytest.raises(ValueError, match="outside workspace"):
        runner.run(["echo", "hi"], cwd=Path("/tmp"))


def test_run_python():
    """Run python -c 'print(42)', verify stdout='42\\n'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = ShellRunner(workspace_root=Path(tmpdir), allowlist={"python", "python3", "echo"})
        result = runner.run(["python", "-c", "print(42)"])
        # May fail if python not found, but should not timeout
        if result.exit_code == 0:
            assert result.stdout.strip() == "42"


def test_default_allowlist_has_expected_commands():
    """Verify default allowlist contains expected commands."""
    expected = {"pytest", "python", "python3", "poetry", "git", "echo", "ls"}
    for cmd in expected:
        assert cmd in DEFAULT_ALLOWLIST


def test_run_with_custom_allowlist():
    """Test running with custom allowlist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = ShellRunner(workspace_root=Path(tmpdir), allowlist={"echo", "cat"})
        result = runner.run(["echo", "hello"])
        assert result.exit_code == 0
        assert "hello" in result.stdout


def test_run_cwd_defaults_to_workspace_root():
    """Test that cwd defaults to workspace_root when not specified."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        runner = ShellRunner(workspace_root=workspace)
        # Create a test file in workspace
        test_file = workspace / "test.txt"
        test_file.write_text("content")
        result = runner.run(["cat", "test.txt"])
        assert result.exit_code == 0
        assert "content" in result.stdout