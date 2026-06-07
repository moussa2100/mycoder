"""Scan repository tree with ignore rules."""

from dataclasses import dataclass
from pathlib import Path
import os

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

    def _scan_file(self, rel: Path) -> ScannedFile | None:
        if not rel or self._is_ignored(rel):
            return None
        abs_p = (self.root / rel).resolve()
        if not abs_p.exists() or not abs_p.is_file():
            return None
        try:
            rel = abs_p.relative_to(self.root)
        except ValueError:
            return None
        return ScannedFile(
            path=rel,
            abs_path=abs_p,
            size=abs_p.stat().st_size,
            is_binary=self._is_binary(abs_p),
        )

    def _resolve_targets(self, target_paths: list[str]) -> list[Path]:
        resolved: dict[str, Path] = {}
        for raw_path in target_paths:
            normalized = str(raw_path or "").replace("\\", "/").lstrip("./")
            if not normalized:
                continue

            direct = (self.root / normalized).resolve()
            if direct.exists() and direct.is_file():
                try:
                    rel = direct.relative_to(self.root)
                except ValueError:
                    continue
                resolved[rel.as_posix()] = rel
                continue

            file_name = Path(normalized).name
            suffix_matches: list[Path] = []
            for candidate in self.root.rglob(file_name):
                if not candidate.is_file():
                    continue
                try:
                    rel = candidate.resolve().relative_to(self.root)
                except ValueError:
                    continue
                rel_text = rel.as_posix()
                if self._is_ignored(rel) or not rel_text.endswith(normalized):
                    continue
                suffix_matches.append(rel)
            if len(suffix_matches) == 1:
                rel = suffix_matches[0]
                resolved[rel.as_posix()] = rel

        return list(resolved.values())

    def scan_targets(self, target_paths: list[str], sibling_limit: int = 12) -> list[ScannedFile]:
        """Scan a small, targeted slice of the repo around known candidate files."""
        ordered: dict[str, ScannedFile] = {}
        targets = self._resolve_targets(target_paths)

        for rel in targets:
            scanned = self._scan_file(rel)
            if scanned is not None:
                ordered[rel.as_posix()] = scanned

        for rel in targets:
            parent = (self.root / rel).parent
            if not parent.exists() or not parent.is_dir():
                continue
            added = 0
            for child in sorted(parent.iterdir()):
                if added >= sibling_limit:
                    break
                if not child.is_file():
                    continue
                try:
                    child_rel = child.resolve().relative_to(self.root)
                except ValueError:
                    continue
                if child_rel.as_posix() in ordered:
                    continue
                scanned = self._scan_file(child_rel)
                if scanned is None:
                    continue
                ordered[child_rel.as_posix()] = scanned
                added += 1

        return list(ordered.values())

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