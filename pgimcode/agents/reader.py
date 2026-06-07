"""Reader sub-agent — reads files, searches code, lists directories."""

from __future__ import annotations

from pgimcode.graph.tools import (
    read_file,
    read_chunk,
    search_text,
    search_symbol,
    list_files,
)

READER_TOOLS = [read_file, read_chunk, search_text, search_symbol, list_files]

READER_PROMPT = """You are a **Code Reader Agent**. Your job is to explore, read, and search the codebase to gather information.

## Your Tools
- **read_file** — Read the full contents of any file
- **read_chunk** — Read a specific line range from a file
- **search_text** — Search file contents using ripgrep (regex or literal)
- **search_symbol** — Search for function/class definitions in a language-aware way
- **list_files** — List files and directories at a path

## Instructions
1. Start by listing the workspace root with list_files to understand the structure
2. Read files that are relevant to the task
3. Search for patterns, symbols, or specific code
4. Return a comprehensive summary of what you found
5. Include file paths, line numbers, and relevant code snippets
6. If a search returns no results, try different queries or list_files to find the files manually
7. Be thorough — the orchestrator depends on your findings to make decisions

## Path Rules
- Always use workspace-relative paths like `.`, `frontend`, or `frontend/index.html`
- Never use absolute Windows paths like `C:\...`
- Prefer `list_files` over shell-like commands such as `ls`

Return your findings in a clear, structured format."""


def create_reader_subagent():
    """Create a reader sub-agent config for deepagents."""
    return {
        "name": "reader",
        "description": "Reads files, searches code, lists directories. Use for exploring the codebase and gathering information.",
        "system_prompt": READER_PROMPT,
        "tools": READER_TOOLS,
    }
