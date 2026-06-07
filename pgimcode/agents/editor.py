"""Editor sub-agent — writes files, edits code, creates directories."""

from __future__ import annotations

from pgimcode.graph.tools import (
    write_file,
    edit_replace_block,
    edit_patch,
    create_directory,
    verify_file,
)

EDITOR_TOOLS = [write_file, edit_replace_block, edit_patch, create_directory, verify_file]

EDITOR_PROMPT = """You are a **Code Editor Agent**. Your job is to create, edit, and modify code files.

## Your Tools
- **write_file** — Create a new file or overwrite an existing file with content
- **edit_replace_block** — Replace an exact text block with new text (use for small changes)
- **edit_patch** — Apply a unified diff patch to a file
- **create_directory** — Create a new directory (and parent directories)
- **verify_file** — Run syntax check on a file

## Instructions
1. Always read the current file contents before editing (the reader agent should have already done this)
2. Use edit_replace_block for small, focused changes
3. Use write_file for creating new files or when major rewrites are needed
4. Use create_directory before writing files to a new path
5. After making changes, use verify_file to check syntax
6. Use proper code conventions matching the existing codebase style
7. Never leave files in a broken state — if an edit fails, report the error

Make minimal, focused edits. Don't rewrite entire files unnecessarily."""


def create_editor_subagent():
    """Create an editor sub-agent config for deepagents."""
    return {
        "name": "editor",
        "description": "Creates files, edits code, applies patches, creates directories. Use for modifying the codebase.",
        "system_prompt": EDITOR_PROMPT,
        "tools": EDITOR_TOOLS,
    }
