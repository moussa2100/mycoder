"""Query-intent heuristics for coding tasks."""

from __future__ import annotations

from dataclasses import dataclass

from pgimcode.tools.ranker import extract_keywords


@dataclass
class QueryIntent:
    kind: str
    keywords: list[str]
    wants_dependency_view: bool = False
    wants_implementation_view: bool = True

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "keywords": self.keywords,
            "wants_dependency_view": self.wants_dependency_view,
            "wants_implementation_view": self.wants_implementation_view,
        }


def classify_query_intent(task: str) -> QueryIntent:
    keywords = extract_keywords(task)
    lowered = task.lower()
    kind = "update"
    if any(word in lowered for word in ("fix", "bug", "broken", "error")):
        kind = "bugfix"
    elif any(word in lowered for word in ("add", "implement", "build", "create")):
        kind = "feature"
    elif any(word in lowered for word in ("refactor", "restructure", "cleanup")):
        kind = "refactor"
    return QueryIntent(
        kind=kind,
        keywords=keywords,
        wants_dependency_view=any(word in lowered for word in ("impact", "dependency", "blast radius", "depends")),
        wants_implementation_view=not any(word in lowered for word in ("explain", "why", "overview")),
    )
