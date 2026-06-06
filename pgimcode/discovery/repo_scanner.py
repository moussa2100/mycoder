"""Scan repository tree with ignore rules."""

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess

@dataclass(frozen=True)
class ScannedFile:
    path: Path          # relative to root
    abs_path: Path
    size: int
    is_binary: bool
    language: str | None = None

class RepoScanner:
    DEFAULT_SKIP = {
        ".git", "__pycache__", "node_modules", ".idea", ".vscode",
        ".pytest_cache", ".mypy_cache", "dist", "build", ".tox",
        "venv", ".venv", "env", ".env", "*.egg-info", ".gitignore",
    }

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.skip_patterns = set(self.DEFAULT_SKIP)
        self._load_gitignore()

    def _load_gitignore(self) -> None:
        gitignore = self.root / ".gitignore"
        if gitignore.exists():
            for line in gitignore.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    self.skip_patterns.add(line.rstrip("/"))

    def _is_ignored(self, rel: Path) -> bool:
        parts = rel.parts
        for part in parts:
            if part in self.skip_patterns:
                return True
            # also check globs
            for pat in self.skip_patterns:
                if pat.startswith("*") and part.endswith(pat.lstrip("*")):
                    return True
                if pat.startswith(".") and part == pat:
                    return True
        return False

    def _is_binary(self, path: Path) -> bool:
        try:
            with open(path, "rb") as f:
                chunk = f.read(8192)
                return b"\x00" in chunk
        except Exception:
            return True

    def scan(self) -> list[ScannedFile]:
        """Return list of ScannedFile for all non-ignored files under root."""
        results = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            rel_dir = Path(dirpath).relative_to(self.root)
            # Filter out ignored dirs in-place so os.walk doesn't recurse into them
            dirnames[:] = [
                d for d in dirnames
                if not self._is_ignored(rel_dir / d)
            ]
            for filename in filenames:
                rel = rel_dir / filename
                if self._is_ignored(rel):
                    continue
                abs_p = self.root / rel
                size = abs_p.stat().st_size
                is_bin = self._is_binary(abs_p)
                results.append(ScannedFile(
                    path=rel,
                    abs_path=abs_p,
                    size=size,
                    is_binary=is_bin,
                ))
        return results