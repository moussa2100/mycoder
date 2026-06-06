"""Tests for CLI analyze command."""

from typer.testing import CliRunner

from pgimcode.cli import app

runner = CliRunner()


def test_analyze_nonexistent_path():
    result = runner.invoke(app, ["analyze", "/does/not/exist"])
    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_analyze_current_repo():
    # Analyze the current project itself
    result = runner.invoke(app, ["analyze", ".", "--output", "json"])
    assert result.exit_code == 0
    # Should detect Python, Poetry, pytest
    assert "python" in result.output.lower()
    assert "poetry" in result.output.lower()


def test_analyze_with_symbols():
    result = runner.invoke(app, ["analyze", ".", "--include-symbols"])
    assert result.exit_code == 0