"""Tool Runtime layer for pgimcode."""

from pgimcode.tools.read import (
    ReadResult,
    read_file,
    read_file_chunk,
    file_exists,
    count_lines,
)
from pgimcode.tools.grep import (
    GrepResult,
    rg_search,
    rg_search_symbol,
)
from pgimcode.tools.symbols import (
    find_symbol,
    find_references,
)
from pgimcode.tools.ranker import (
    RankedFile,
    extract_keywords,
    rank_files_by_relevance,
)
from pgimcode.tools.edit import (
    EditResult,
    replace_block,
    patch_file,
    create_file,
    delete_file,
)
from pgimcode.tools.diff import (
    DiffResult,
    make_diff,
    diff_preview,
)
from pgimcode.tools.snapshot import (
    Snapshot,
    SnapshotManager,
)

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
    # ranker
    "RankedFile",
    "extract_keywords",
    "rank_files_by_relevance",
    # edit
    "EditResult",
    "replace_block",
    "patch_file",
    "create_file",
    "delete_file",
    # diff
    "DiffResult",
    "make_diff",
    "diff_preview",
    # snapshot
    "Snapshot",
    "SnapshotManager",
]