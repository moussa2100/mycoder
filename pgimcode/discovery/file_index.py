"""Indexed file list with queries."""

from dataclasses import dataclass
from pathlib import Path
from collections import Counter

from pgimcode.discovery.repo_scanner import ScannedFile


@dataclass
class FileIndex:
    files: list[ScannedFile]
    root: Path | None = None

    def by_language(self, lang: str) -> list[ScannedFile]:
        return [f for f in self.files if f.language == lang]

    def by_extension(self, ext: str) -> list[ScannedFile]:
        ext = ext if ext.startswith(".") else f".{ext}"
        return [f for f in self.files if f.path.suffix == ext]

    def by_pattern(self, pattern: str) -> list[ScannedFile]:
        return [f for f in self.files if f.path.match(pattern)]

    def total_lines(self) -> int:
        count = 0
        for f in self.files:
            if f.is_binary:
                continue
            try:
                with open(f.abs_path, "r", encoding="utf-8", errors="ignore") as fh:
                    count += sum(1 for _ in fh)
            except Exception:
                pass
        return count

    def total_size(self) -> int:
        return sum(f.size for f in self.files)

    def language_counts(self) -> dict[str, int]:
        return Counter(f.language for f in self.files if f.language)

    def top_directories(self, n: int = 10) -> list[tuple[str, int]]:
        counts = Counter()
        for f in self.files:
            top = f.path.parts[0] if f.path.parts else "."
            counts[top] += 1
        return counts.most_common(n)

    def to_dict(self) -> dict:
        return {
            "total_files": len(self.files),
            "total_lines": self.total_lines(),
            "total_size": self.total_size(),
            "languages": dict(self.language_counts()),
            "top_directories": self.top_directories(),
        }