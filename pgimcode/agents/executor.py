"""Executor sub-agent — runs shell commands and tests."""

from __future__ import annotations

from pgimcode.graph.tools import (
    run_command,
    run_tests,
)

EXECUTOR_TOOLS = [run_command, run_tests]

EXECUTOR_PROMPT = """You are a **Code Executor Agent**. Your job is to run shell commands and test suites.

## Your Tools
- **run_command** — Run a shell command in the workspace root (allowlist-restricted)
- **run_tests** — Run the project's test suite (auto-detects framework)

## Instructions
1. Run commands exactly as specified by the orchestrator
2. When running tests, use run_tests to auto-detect the framework
3. Report command outputs clearly — both stdout and stderr
4. If a command fails, report the exit code and error message
5. Never run destructive commands (rm -rf, format, etc.)
6. Always respect the working directory

Report results clearly with exit codes, output summaries, and any errors."""


def create_executor_subagent():
    """Create an executor sub-agent config for deepagents."""
    return {
        "name": "executor",
        "description": "Runs shell commands and tests. Use for executing build commands, running test suites, and verifying changes.",
        "system_prompt": EXECUTOR_PROMPT,
        "tools": EXECUTOR_TOOLS,
    }
