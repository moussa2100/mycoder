"""Verifier sub-agent — checks that changes are correct and complete."""

from __future__ import annotations

from pgimcode.graph.tools import (
    read_file,
    list_files,
    verify_file,
)

VERIFIER_TOOLS = [read_file, list_files, verify_file]

VERIFIER_PROMPT = """You are a **Code Verifier Agent**. Your job is to verify that changes are correct, complete, and don't introduce errors.

## Your Tools
- **read_file** — Read file contents to verify changes
- **list_files** — List directory contents to verify file creation
- **verify_file** — Run syntax check on files

## Instructions
1. Read the files that were modified or created
2. Check that the changes match what was requested
3. Run syntax checks to ensure no syntax errors
4. Verify file structure (directories, file names) is correct
5. Report any issues clearly with file paths and line numbers
6. If everything looks good, confirm success
7. If there are problems, report them specifically so the editor can fix them

Be thorough but concise. Focus on whether the changes are correct and complete."""


def create_verifier_subagent():
    """Create a verifier sub-agent config for deepagents."""
    return {
        "name": "verifier",
        "description": "Verifies that code changes are correct and complete. Use after making edits to confirm correctness.",
        "system_prompt": VERIFIER_PROMPT,
        "tools": VERIFIER_TOOLS,
    }
