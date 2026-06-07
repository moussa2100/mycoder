"""Task-board helpers for long-running agent workflows."""

from __future__ import annotations

from pgimcode.intelligence.models import TaskBoardItem


def build_default_task_board(task: str, candidate_files: list[dict] | None = None) -> list[dict]:
    """Create a simple default task board for a coding task."""
    top_target = ""
    if candidate_files:
        top_target = candidate_files[0].get("path", "")
    items = [
        TaskBoardItem("research", "Research task and collect evidence", status="in_progress"),
        TaskBoardItem("plan", "Build an implementation plan", status="pending"),
        TaskBoardItem("edit", "Apply the smallest safe code change", status="pending", note=top_target),
        TaskBoardItem("verify", "Verify changes and self-review", status="pending"),
        TaskBoardItem("complete", "Summarize outcome and residual risk", status="pending"),
    ]
    return [item.to_dict() for item in items]


def mark_stage(task_board: list[dict], key: str, status: str, note: str = "") -> list[dict]:
    """Update a task-board stage in-place-like fashion and return a new list."""
    updated: list[dict] = []
    for item in task_board:
        clone = dict(item)
        if clone.get("key") == key:
            clone["status"] = status
            if note:
                clone["note"] = note
        updated.append(clone)
    return updated


def summarize_task_board(task_board: list[dict]) -> str:
    """Return a short human-readable summary for UI/event rendering."""
    if not task_board:
        return "No task board"
    parts = []
    for item in task_board[:4]:
        parts.append(f"{item.get('label')}: {item.get('status')}")
    return " | ".join(parts)
