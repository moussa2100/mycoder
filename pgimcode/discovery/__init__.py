"""Repository discovery engine for pgimcode."""

from pgimcode.discovery.repo_scanner import RepoScanner, ScannedFile
from pgimcode.discovery.file_index import FileIndex
from pgimcode.discovery.language_detector import (
    detect_language,
    annotate_languages,
    detect_frameworks,
    find_entry_points,
    find_test_locations,
    find_dependency_files,
    infer_build_commands,
)

__all__ = [
    "RepoScanner",
    "ScannedFile",
    "FileIndex",
    "detect_language",
    "annotate_languages",
    "detect_frameworks",
    "find_entry_points",
    "find_test_locations",
    "find_dependency_files",
    "infer_build_commands",
]