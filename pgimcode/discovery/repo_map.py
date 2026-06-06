"""Aggregate repo map from scanned files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pgimcode.discovery.repo_scanner import RepoScanner
from pgimcode.discovery.file_index import FileIndex, ScannedFile
from pgimcode.discovery.language_detector import (
    annotate_languages,
    detect_frameworks,
    find_entry_points,
    find_test_locations,
    find_dependency_files,
    infer_build_commands,
)


@dataclass
class RepoMap:
    root: Path
    languages: dict[str, int] = field(default_factory=dict)
    frameworks: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    test_locations: list[str] = field(default_factory=list)
    dependency_files: list[str] = field(default_factory=list)
    build_commands: list[str] = field(default_factory=list)
    total_files: int = 0
    total_lines: int = 0
    total_size: int = 0
    top_dirs: list[tuple[str, int]] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [f"# Repo Map: {self.root}", ""]

        lines += ["## Languages", ""]
        for lang, count in sorted(self.languages.items(), key=lambda x: -x[1]):
            lines.append(f"- {lang} ({count} files)")
        lines.append("")

        if self.frameworks:
            lines += ["## Frameworks", ""]
            for fw in self.frameworks:
                lines.append(f"- {fw}")
            lines.append("")

        if self.entry_points:
            lines += ["## Entry Points", ""]
            for ep in self.entry_points:
                lines.append(f"- {ep}")
            lines.append("")

        if self.test_locations:
            lines += ["## Test Locations", ""]
            for loc in self.test_locations:
                lines.append(f"- {loc}")
            lines.append("")

        if self.dependency_files:
            lines += ["## Dependency Files", ""]
            for df in self.dependency_files:
                lines.append(f"- {df}")
            lines.append("")

        if self.build_commands:
            lines += ["## Inferred Build/Test Commands", ""]
            for cmd in self.build_commands:
                lines.append(f"- `{cmd}`")
            lines.append("")

        lines += ["## Summary", ""]
        lines.append(f"- **Total files:** {self.total_files}")
        lines.append(f"- **Total lines:** {self.total_lines}")
        lines.append(f"- **Total size:** {self.total_size:,} bytes")

        return "\n".join(lines)


def build_repo_map(scanner: RepoScanner) -> RepoMap:
    files = scanner.scan()
    files = annotate_languages(files)
    index = FileIndex(files=files, root=scanner.root)

    return RepoMap(
        root=scanner.root,
        languages=dict(index.language_counts()),
        frameworks=detect_frameworks(files),
        entry_points=find_entry_points(files),
        test_locations=find_test_locations(files),
        dependency_files=find_dependency_files(files),
        build_commands=infer_build_commands(files),
        total_files=len(files),
        total_lines=index.total_lines(),
        total_size=index.total_size(),
        top_dirs=index.top_directories(),
    )