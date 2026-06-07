"""Evidence creation and compression helpers."""

from __future__ import annotations

from pgimcode.intelligence.models import EvidenceItem


def make_evidence_item(
    identifier: str,
    claim: str,
    source: str,
    file_path: str | None = None,
    confidence: float = 0.5,
    metadata: dict | None = None,
) -> dict:
    return EvidenceItem(
        id=identifier,
        claim=claim,
        source=source,
        file_path=file_path,
        confidence=confidence,
        metadata=metadata or {},
    ).to_dict()


def seed_evidence_from_candidates(candidate_files: list[dict]) -> list[dict]:
    evidence = []
    for idx, candidate in enumerate(candidate_files[:5], start=1):
        evidence.append(
            make_evidence_item(
                identifier=f"candidate-{idx}",
                claim=f"Candidate implementation file: {candidate.get('path', '?')}",
                source="hybrid_ranker",
                file_path=candidate.get("path"),
                confidence=min(0.95, 0.5 + float(candidate.get("score", 0)) / 20),
                metadata={"reason": candidate.get("reason", "")},
            )
        )
    return evidence


def record_tool_evidence(tool_name: str, tool_args: dict, result: dict) -> list[dict]:
    """Translate tool activity into evidence items."""
    file_path = tool_args.get("path")
    message = result.get("message") if isinstance(result, dict) else str(result)
    if tool_name in {"search_text", "search_symbol"}:
        count = int(result.get("count", 0)) if isinstance(result, dict) else 0
        return [make_evidence_item(f"{tool_name}:{count}:{file_path or ''}", f"{tool_name} captured {count} match(es)", tool_name, file_path, 0.7)]
    if tool_name in {"read_file", "read_chunk", "list_files"}:
        return [make_evidence_item(f"{tool_name}:{file_path or ''}", message or f"Inspected {file_path}", tool_name, file_path, 0.65)]
    if tool_name in {"edit_replace_block", "edit_patch", "write_file"}:
        return [make_evidence_item(f"edit:{file_path or ''}", message or f"Changed {file_path}", tool_name, file_path, 0.85)]
    if tool_name in {"verify_file", "run_command"}:
        return [make_evidence_item(f"verify:{file_path or ''}", message or f"Verification via {tool_name}", tool_name, file_path, 0.75)]
    return []


def compress_evidence(evidence: list[dict], max_items: int = 8) -> list[dict]:
    """Dedupe evidence by claim and keep the highest-confidence items."""
    deduped: dict[str, dict] = {}
    for item in evidence:
        claim = item.get("claim", "")
        prev = deduped.get(claim)
        if prev is None or item.get("confidence", 0) > prev.get("confidence", 0):
            deduped[claim] = item
    ordered = sorted(deduped.values(), key=lambda item: item.get("confidence", 0), reverse=True)
    return ordered[:max_items]
