"""Tool Runtime layer for pgimcode.

Keep package imports lightweight so submodules do not eagerly pull in
optional symbol-analysis dependencies.
"""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "ReadResult": ("pgimcode.tools.read", "ReadResult"),
    "read_file": ("pgimcode.tools.read", "read_file"),
    "read_file_chunk": ("pgimcode.tools.read", "read_file_chunk"),
    "file_exists": ("pgimcode.tools.read", "file_exists"),
    "count_lines": ("pgimcode.tools.read", "count_lines"),
    "GrepResult": ("pgimcode.tools.grep", "GrepResult"),
    "rg_search": ("pgimcode.tools.grep", "rg_search"),
    "rg_search_symbol": ("pgimcode.tools.grep", "rg_search_symbol"),
    "find_symbol": ("pgimcode.tools.symbols", "find_symbol"),
    "find_references": ("pgimcode.tools.symbols", "find_references"),
    "create_code_tools": ("pgimcode.tools.code_reader", "create_code_tools"),
    "build_outline": ("pgimcode.tools.code_reader", "build_outline"),
    "is_code_file": ("pgimcode.tools.code_reader", "is_code_file"),
    "RankedFile": ("pgimcode.tools.ranker", "RankedFile"),
    "extract_keywords": ("pgimcode.tools.ranker", "extract_keywords"),
    "rank_files_by_relevance": ("pgimcode.tools.ranker", "rank_files_by_relevance"),
    "DiffResult": ("pgimcode.tools.diff", "DiffResult"),
    "make_diff": ("pgimcode.tools.diff", "make_diff"),
    "diff_preview": ("pgimcode.tools.diff", "diff_preview"),
    "Snapshot": ("pgimcode.tools.snapshot", "Snapshot"),
    "SnapshotManager": ("pgimcode.tools.snapshot", "SnapshotManager"),
}


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'pgimcode.tools' has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name)
    return getattr(module, attr_name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))

__all__ = [
    # read
    "ReadResult",
    "read_file",
    "read_file_chunk",
    "file_exists",
    "count_lines",
    # grep
    "GrepResult",
    "rg_search",
    "rg_search_symbol",
    # symbols
    "find_symbol",
    "find_references",
    # code_reader (tree-sitter)
    "create_code_tools",
    "build_outline",
    "is_code_file",
    # ranker
    "RankedFile",
    "extract_keywords",
    "rank_files_by_relevance",
    # diff
    "DiffResult",
    "make_diff",
    "diff_preview",
    # snapshot
    "Snapshot",
    "SnapshotManager",
]