"""Planner sub-agent — analyzes tasks and creates step-by-step plans."""

from __future__ import annotations

from pgimcode.graph.tools import (
    read_file, read_chunk, search_text, search_symbol, list_files,
    write_file, edit_replace_block, edit_patch, create_directory,
    verify_file, run_command, run_tests,
)

PLANNER_TOOLS = [
    read_file, read_chunk, search_text, search_symbol, list_files,
    write_file, edit_replace_block, edit_patch, create_directory,
    verify_file, run_command, run_tests,
]

PLANNER_PROMPT = """You are a **Task Planner Agent**. Your job is to analyze the user's request and create a detailed, step-by-step plan.

## Your Tools (read-only for planning)
- **list_files** — Explore the repository structure
- **read_file** — Read file contents to understand existing code
- **search_text** — Search for patterns in the codebase
- **search_symbol** — Find function/class definitions

## Instructions
1. Use list_files and read_file to understand the current state of the relevant files
2. Break down the task into clear, actionable steps
3. For each step, specify:
   - What needs to be done
   - Which file(s) are affected
   - What tool to use (reader, editor, or executor)
4. Consider edge cases and error handling
5. If the task is unclear, ask for clarification
6. Don't make any changes — just read and plan

Output a structured plan with numbered steps. Each step should be specific enough that another agent can execute it."""


def create_planner_subagent():
    """Create a planner sub-agent config for deepagents."""
    return {
        "name": "planner",
        "description": "Analyzes tasks and creates detailed step-by-step plans. Use for complex tasks that need careful planning.",
        "system_prompt": PLANNER_PROMPT,
        "tools": PLANNER_TOOLS,
    }
