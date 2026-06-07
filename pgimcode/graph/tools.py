"""OpenAI tool definitions and wrappers for the agent graph."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pgimcode.tools.edit import patch_file as _edit_patch_file, replace_block as _replace_block
from pgimcode.tools.grep import rg_search as _rg_search, rg_search_symbol as _rg_search_symbol
from pgimcode.tools.read import read_file as _read_file, read_file_chunk as _read_file_chunk
from pgimcode.tools.shell import ShellRunner
from pgimcode.tools.test_runner import run_tests as _run_tests
from pgimcode.verification import Verifier


# ---------------------------------------------------------------------------
# Tool definitions in OpenAI function-calling format
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full contents of a text file, truncating very large files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to read."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_chunk",
            "description": "Read a specific line range from a file (1-indexed lines, inclusive).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to read."},
                    "start_line": {"type": "integer", "description": "First line number (1-indexed, inclusive)."},
                    "end_line": {"type": "integer", "description": "Last line number (1-indexed, inclusive)."},
                },
                "required": ["path", "start_line", "end_line"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_text",
            "description": "Search file contents using ripgrep. Returns matching lines with context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Regex or literal string to search for."},
                    "glob": {"type": "string", "description": "Optional glob pattern to limit search to matching files."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_symbol",
            "description": "Search for a symbol definition (function, class, etc.) in a language-aware way.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol_name": {"type": "string", "description": "Name of the symbol to search for."},
                    "language": {"type": "string", "description": "Programming language ('python', 'typescript', 'rust', 'go', 'java'). Default: 'python'."},
                },
                "required": ["symbol_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_replace_block",
            "description": "Replace the first exact occurrence of old_text with new_text in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to edit."},
                    "old_text": {"type": "string", "description": "Exact text block to replace (must be unique in the file)."},
                    "new_text": {"type": "string", "description": "Replacement text."},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_patch",
            "description": "Apply a unified diff patch to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to patch."},
                    "patch_text": {"type": "string", "description": "Unified diff string to apply."},
                },
                "required": ["path", "patch_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command in the workspace root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "array", "items": {"type": "string"}, "description": "Command as a list of arguments, e.g. ['pytest', '-v']."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run the project's test suite (auto-detects framework).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_file",
            "description": "Run syntax check on one or more Python files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to verify."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create a new file or overwrite an existing file with the given content. Creates parent directories if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to write."},
                    "content": {"type": "string", "description": "Full text content to write to the file."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a new directory (and any necessary parent directories).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the directory to create."},
                },
                "required": ["path"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Wrapper functions
# ---------------------------------------------------------------------------

_workspace_root = Path(".")


def _make_result(success: bool, result: Any) -> dict:
    return {"success": success, "result": result}


def _wrap_read_file(path: str) -> dict:
    from pgimcode.tools.read import ReadResult
    r = _read_file(Path(path))
    return {"content": r.content, "total_lines": r.total_lines, "truncated": r.truncated}


def _wrap_read_chunk(path: str, start_line: int, end_line: int) -> dict:
    r = _read_file_chunk(Path(path), start_line, end_line)
    return {"content": r.content, "total_lines": r.total_lines, "truncated": r.truncated}


def _wrap_search_text(query: str, glob: str | None = None) -> dict:
    results = _rg_search(query, root=_workspace_root, glob=glob, max_results=50, context_lines=2)
    return {
        "count": len(results),
        "matches": [
            {
                "path": str(m.path),
                "line_number": m.line_number,
                "text": m.text,
                "context_before": m.context_before,
                "context_after": m.context_after,
            }
            for m in results
        ],
    }


def _wrap_search_symbol(symbol_name: str, language: str = "python") -> dict:
    results = _rg_search_symbol(symbol_name, root=_workspace_root, language=language)
    return {
        "count": len(results),
        "matches": [
            {
                "path": str(m.path),
                "line_number": m.line_number,
                "text": m.text,
                "context_before": m.context_before,
                "context_after": m.context_after,
            }
            for m in results
        ],
    }


def _wrap_edit_replace_block(path: str, old_text: str, new_text: str) -> dict:
    result = _replace_block(Path(path), old_text, new_text)
    return {
        "success": result.success,
        "operation": result.operation,
        "message": result.message,
        "start_line": result.start_line,
        "end_line": result.end_line,
    }


def _wrap_edit_patch(path: str, patch_text: str) -> dict:
    result = _edit_patch_file(Path(path), patch_text)
    return {
        "success": result.success,
        "operation": result.operation,
        "message": result.message,
        "start_line": result.start_line,
        "end_line": result.end_line,
    }


def _wrap_run_command(command: list[str]) -> dict:
    runner = ShellRunner(workspace_root=_workspace_root)
    result = runner.run(command)
    return {
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_ms": result.duration_ms,
        "timed_out": result.timed_out,
    }


def _wrap_run_tests() -> dict:
    result = _run_tests(_workspace_root, timeout=60)
    return {
        "success": result.success,
        "framework": result.framework,
        "pass_count": result.pass_count,
        "fail_count": result.fail_count,
        "skip_count": result.skip_count,
        "total": result.total,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_ms": result.duration_ms,
        "timed_out": result.timed_out,
    }


def _wrap_verify_file(path: str) -> dict:
    verifier = Verifier(workspace_root=_workspace_root)
    check = verifier.check_syntax([Path(path)])
    return {
        "status": check.status,
        "message": check.message,
        "details": check.details,
    }


def _wrap_write_file(path: str, content: str) -> dict:
    filepath = Path(path)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    return {
        "success": True,
        "path": str(filepath),
        "size": len(content),
        "lines": content.count("\n") + 1,
        "message": f"Created file: {path} ({len(content)} bytes, {content.count(chr(10)) + 1} lines)",
    }


def _wrap_create_directory(path: str) -> dict:
    dirpath = Path(path)
    dirpath.mkdir(parents=True, exist_ok=True)
    return {
        "success": True,
        "path": str(dirpath),
        "message": f"Created directory: {path}",
    }


# ---------------------------------------------------------------------------
# Name → wrapper map
# ---------------------------------------------------------------------------

TOOL_MAP: dict[str, Callable[..., dict]] = {
    "read_file": _wrap_read_file,
    "read_chunk": _wrap_read_chunk,
    "search_text": _wrap_search_text,
    "search_symbol": _wrap_search_symbol,
    "edit_replace_block": _wrap_edit_replace_block,
    "edit_patch": _wrap_edit_patch,
    "run_command": _wrap_run_command,
    "run_tests": _wrap_run_tests,
    "verify_file": _wrap_verify_file,
    "write_file": _wrap_write_file,
    "create_directory": _wrap_create_directory,
}


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def call_tool(name: str, arguments: dict) -> dict:
    """Call a tool by name with the given arguments.

    Returns ``{"success": bool, "result": ...}`` on success,
    ``{"success": False, "result": error_string}`` on failure.
    """
    wrapper = TOOL_MAP.get(name)
    if wrapper is None:
        return _make_result(False, f"Unknown tool: {name}")

    try:
        result = wrapper(**arguments)
        return _make_result(True, result)
    except Exception as exc:  # noqa: BLE001
        return _make_result(False, str(exc))