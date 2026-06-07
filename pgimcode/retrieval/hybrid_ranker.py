"""Hybrid ranking that blends lexical relevance with lightweight relationships."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pgimcode.discovery.repo_scanner import ScannedFile
from pgimcode.retrieval.code_index import build_code_index
from pgimcode.retrieval.query_intent import classify_query_intent
from pgimcode.retrieval.relationship_index import build_relationship_index
from pgimcode.tools.ranker import extract_keywords, rank_files_by_relevance


@dataclass
class HybridHit:
    path: str
    score: float
    reason: str
    related_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "score": round(self.score, 2),
            "reason": self.reason,
            "related_files": self.related_files,
        }


def _resolve_preferred_paths(preferred_paths: list[str] | None, files: list[ScannedFile]) -> set[str]:
    file_lookup = {f.path.as_posix() for f in files}
    resolved: set[str] = set()

    for raw_path in preferred_paths or []:
        normalized = str(raw_path).replace("\\", "/").lstrip("./")
        if not normalized:
            continue
        if normalized in file_lookup:
            resolved.add(normalized)
            continue

        suffix_matches = [path for path in file_lookup if path.endswith(normalized)]
        if len(suffix_matches) == 1:
            resolved.add(suffix_matches[0])
            continue

        file_name = Path(normalized).name
        name_matches = [path for path in file_lookup if Path(path).name == file_name]
        if len(name_matches) == 1:
            resolved.add(name_matches[0])

    return resolved


def hybrid_rank_files(task: str, files: list[ScannedFile], root: Path, max_results: int = 12, preferred_paths: list[str] | None = None) -> list[HybridHit]:
    """Rank candidate files using lexical signals plus relationship/symbol hints."""
    intent = classify_query_intent(task)
    base_ranked = rank_files_by_relevance(task, files, root, max_results=max_results)
    keywords = set(extract_keywords(task))
    code_index = build_code_index(root)
    relationships = build_relationship_index(root)
    preferred = _resolve_preferred_paths(preferred_paths, files)
    file_lookup = {f.path.as_posix(): f for f in files}
    hits: dict[str, HybridHit] = {}

    for ranked in base_ranked:
        path = ranked.file.path.as_posix()
        related = relationships.get(path, [])
        symbols = set(code_index.get(path, {}).get("symbols", []))
        score = ranked.score
        reason_bits = list(dict.fromkeys(ranked.reasons))
        if keywords & {symbol.lower() for symbol in symbols}:
            score += 1.0
            reason_bits.append("keyword matched symbol")
        if related:
            score += 0.4 + (0.3 if intent.wants_dependency_view else 0.0)
            reason_bits.append("has related dependency files")
        if path in preferred:
            score += 4.0
            reason_bits.append("recently changed in this session")
        hits[path] = HybridHit(path=path, score=score, reason="; ".join(reason_bits[:4]), related_files=related[:5])

    for path in preferred:
        if path in hits or path not in file_lookup:
            continue
        hits[path] = HybridHit(
            path=path,
            score=4.5,
            reason="recently changed in this session",
            related_files=relationships.get(path, [])[:5],
        )

    for hit in list(hits.values())[:3]:
        for related in hit.related_files[:3]:
            if related in hits:
                continue
            hits[related] = HybridHit(path=related, score=max(0.5, hit.score * 0.65), reason=f"related to {hit.path}", related_files=[])

    ordered = sorted(hits.values(), key=lambda item: item.score, reverse=True)
    return ordered[:max_results]
