"""Tests for the plan CLI command."""

from typer.testing import CliRunner
from pgimcode.cli import app

runner = CliRunner()


def test_plan_nonexistent_path():
    result = runner.invoke(app, ["plan", "find auth", "--path", "/does/not/exist"])
    assert result.exit_code == 1


def test_plan_current_repo():
    result = runner.invoke(app, ["plan", "find cli entry point", "--path", "."])
    assert result.exit_code == 0
    # Should contain analysis output
    assert "Plan for:" in result.output
    assert "Top Relevant Files" in result.output