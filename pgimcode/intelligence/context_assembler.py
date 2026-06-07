"""Prompt context assembly for richer graph decisions."""

from __future__ import annotations

from pgimcode.intelligence.evidence import compress_evidence


def assemble_prompt_context(state: dict) -> str:
    """Build a compact markdown block from research/task/evidence state."""
    lines: list[str] = []

    recent_files = state.get("recent_files", [])
    if recent_files:
        lines += ["## Recent Files"]
        for path in recent_files[:6]:
            lines.append(f"- {path}")
        lines.append("")

    carryover_context = state.get("carryover_context", "").strip()
    if carryover_context:
        lines += ["## Session Carryover", carryover_context, ""]

    candidate_files = state.get("candidate_files", [])
    if candidate_files:
        lines += ["## Candidate Files"]
        for item in candidate_files[:6]:
            related = ", ".join(item.get("related_files", [])[:3]) or "none"
            lines.append(f"- {item.get('path')} (score {item.get('score', 0):.2f}) — {item.get('reason', '')}; related: {related}")
        lines.append("")

    task_board = state.get("task_board", [])
    if task_board:
        lines += ["## Task Board"]
        for item in task_board[:5]:
            lines.append(f"- {item.get('label')}: {item.get('status')} {item.get('note', '')}".rstrip())
        lines.append("")

    evidence = compress_evidence(state.get("evidence", []), max_items=6)
    if evidence:
        lines += ["## Evidence"]
        for item in evidence:
            lines.append(f"- {item.get('claim')} [{item.get('source')}, confidence {item.get('confidence', 0):.2f}]")
        lines.append("")

    questions = state.get("open_questions", [])
    if questions:
        lines += ["## Open Questions"]
        for question in questions[:4]:
            lines.append(f"- {question}")
        lines.append("")

    verification_plan = state.get("verification_plan", [])
    if verification_plan:
        lines += ["## Verification Plan"]
        for item in verification_plan[:4]:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines).strip()
