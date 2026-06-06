"""Rank files by relevance to a task."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pgimcode.discovery.repo_scanner import ScannedFile
from pgimcode.discovery.language_detector import find_entry_points, find_test_locations
from pgimcode.tools.grep import rg_search


STOPWORDS = {
    "a", "an", "the", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "as", "and", "or", "is", "are", "was", "were", "be", "been",
    "being", "this", "that", "these", "those", "it", "its", "will", "can",
    "should", "would", "could", "may", "might", "must", "do", "does", "did",
    "have", "has", "had", "get", "got", "make", "made", "take", "took",
    "using", "use", "add", "adds", "added", "fix", "fixes", "fixed",
    "update", "updates", "updated", "change", "changes", "changed",
    "remove", "removes", "removed", "delete", "deletes", "deleted",
    "implement", "implements", "implemented", "create", "creates", "created",
}


@dataclass
class RankedFile:
    file: ScannedFile
    score: float
    reasons: list[str]


def extract_keywords(task: str) -> list[str]:
    """Extract meaningful keywords from a task description."""
    # Simple extraction: alphanumeric tokens, skip stopwords
    import re
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9]*", task.lower())
    keywords = [t for t in tokens if t not in STOPWORDS and len(t) > 2]
    return list(dict.fromkeys(keywords))  # dedupe preserve order


def rank_files_by_relevance(
    task: str,
    files: list[ScannedFile],
    root: Path,
    max_results: int = 10,
) -> list[RankedFile]:
    """Rank files by relevance to task. Returns top max_results."""
    keywords = extract_keywords(task)
    eps = set(find_entry_points(files))
    test_locs = set(find_test_locations(files))

    scored = []
    for f in files:
        if f.is_binary:
            continue
        score = 0.0
        reasons = []

        # Keyword match in filename
        for kw in keywords:
            if kw in f.path.name.lower():
                score += 3.0
                reasons.append(f"keyword '{kw}' in filename")
            if kw in str(f.path.parent).lower():
                score += 1.0
                reasons.append(f"keyword '{kw}' in path")

        # Entry point bonus
        if str(f.path) in eps:
            score += 2.0
            reasons.append("entry point")

        # Test penalty (tests are less likely the implementation target)
        if any(str(f.path).startswith(tl) for tl in test_locs):
            score -= 1.0
            reasons.append("is test file")

        # Language relevance (Python tasks → Python files preferred)
        if f.language == "python" and any(kw in ("python", "py") for kw in keywords):
            score += 1.0

        # Grep search for keywords inside file (expensive but useful)
        if keywords and score > 0:  # only grep files that already scored
            for kw in keywords:
                try:
                    results = rg_search(kw, root, glob=str(f.path), max_results=1, context_lines=0)
                    if results:
                        score += 2.0
                        reasons.append(f"keyword '{kw}' found in content")
                        break  # only count once
                except Exception:
                    pass

        # Penalize huge files slightly
        try:
            lines = f.abs_path.read_text(encoding="utf-8", errors="replace").count("\n")
            if lines > 500:
                score -= 0.5
        except Exception:
            pass

        if score > 0:
            scored.append(RankedFile(file=f, score=score, reasons=reasons))

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:max_results]