"""Build research goals, hypotheses, and task-board state from retrieval results."""

from __future__ import annotations

from pgimcode.intelligence.evidence import make_evidence_item, seed_evidence_from_candidates
from pgimcode.intelligence.task_board import build_default_task_board
from pgimcode.retrieval.query_intent import classify_query_intent


def build_investigation_packet(task: str, repo_map: object | None, candidate_files: list[dict]) -> dict:
    """Create the research scaffolding carried through the graph."""
    intent = classify_query_intent(task)
    research_goals = [
        "Confirm the primary implementation target before editing",
        "Understand nearby dependencies and blast radius",
        "Prepare a verification and self-review path before completion",
    ]
    if intent.wants_dependency_view:
        research_goals.append("Map dependencies and impact before changing code")

    hypotheses = [
        {
            "claim": "The primary implementation likely lives in the top-ranked candidate files.",
            "confidence": 0.65 if candidate_files else 0.25,
        },
        {
            "claim": "Dependency neighbors may need coordinated updates.",
            "confidence": 0.55 if any(item.get("related_files") for item in candidate_files[:3]) else 0.3,
        },
    ]
    if repo_map and getattr(repo_map, "entry_points", None):
        hypotheses.append({"claim": "Entry points can anchor the implementation path.", "confidence": 0.6})

    evidence = seed_evidence_from_candidates(candidate_files)
    if repo_map:
        evidence.append(
            make_evidence_item(
                "repo-shape",
                f"Repository shape: {getattr(repo_map, 'total_files', 0)} files across {len(getattr(repo_map, 'languages', {}))} language(s)",
                "repo_map",
                confidence=0.7,
            )
        )

    open_questions = []
    if not candidate_files:
        open_questions.append("No strong candidate files found yet; the agent should broaden repository search.")

    verification_plan = [
        "Verify changed files compile or parse cleanly",
        "Inspect command output for errors and warnings",
        "Run one self-review pass on blast radius and residual risk",
    ]

    return {
        "research_goals": research_goals,
        "hypotheses": hypotheses,
        "evidence": evidence,
        "candidate_files": candidate_files,
        "open_questions": open_questions,
        "blast_radius": [item.get("path") for item in candidate_files[:5]],
        "verification_plan": verification_plan,
        "task_board": build_default_task_board(task, candidate_files),
        "query_intent": intent.to_dict(),
    }
