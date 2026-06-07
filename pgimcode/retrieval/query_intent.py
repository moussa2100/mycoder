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


def should_use_fast_followup_scan(task: str, recent_files: list[str] | None = None) -> bool:
    """Heuristic for obvious follow-up edits that should avoid a full repo scan first."""
    if not recent_files:
        return False

    lowered = task.lower().strip()
    if not lowered:
        return False

    explicit_search_terms = (
        "find ", "search", "where is", "scan repo", "scan repository",
        "analyze repo", "analyze repository", "explore repo", "inspect repo",
    )
    if any(term in lowered for term in explicit_search_terms):
        return False

    explicit_paths = ("/", "\\", ".py", ".js", ".ts", ".html", ".css", ".json", ".md")
    references_current_artifact = any(
        phrase in lowered
        for phrase in (
            "the page", "this page", "that page", "the file", "this file", "that file",
            "same file", "same page", "it ", "style the", "update the", "modify the",
            "change the", "edit the", "add to the",
        )
    )
    likely_edit = any(
        word in lowered
        for word in ("use ", "add ", "update ", "change ", "modify ", "edit ", "style ", "insert ", "remove ", "delete ", "replace ")
    )
    short_followup = len(lowered.split()) <= 20
    no_explicit_path = not any(token in lowered for token in explicit_paths)

    return likely_edit and references_current_artifact and (no_explicit_path or short_followup)


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
