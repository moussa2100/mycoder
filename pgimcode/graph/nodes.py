"""LangGraph node implementations for the pgimcode agent."""

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pgimcode.graph.state import AgentState
from pgimcode.discovery.repo_scanner import RepoScanner
from pgimcode.discovery.repo_map import build_repo_map
from pgimcode.discovery.language_detector import annotate_languages
from pgimcode.tools.ranker import rank_files_by_relevance
from pgimcode.planner import TaskPlanner
from pgimcode.events import EventType


def _to_dict(state) -> dict:
    """Convert AgentState Pydantic model or dict to a plain dict."""
    if hasattr(state, "model_dump"):
        return state.model_dump()
    return dict(state)


def _make_event(event_type: EventType, step: int, details: str = "", data: dict | None = None) -> dict:
    return {
        "session_id": "",
        "type": event_type.value,
        "step": step,
        "status": "in_progress",
        "details": details,
        "data": data or {},
    }


def intake_node(state) -> dict:
    """Normalize task, initialize session."""
    s = _to_dict(state)
    current = s.get("turn", 0)
    task = s.get("task", "")
    if task:
        task = task.strip()
    events = list(s.get("events", []))
    events.append(_make_event(EventType.SESSION_STARTED, current + 1, f"Task: {task[:80] if task else ''}"))
    return {
        "task": task,
        "turn": current + 1,
        "current_node": "discovery",
        "events": events,
    }


def discovery_node(state) -> dict:
    """Scan repo, annotate languages, build repo map."""
    s = _to_dict(state)
    current = s.get("turn", 0)
    events = list(s.get("events", []))
    events.append(_make_event(EventType.REPO_SCANNING, current + 1, "Scanning repository"))
    events.append(_make_event(EventType.FILE_READING, current + 1, "Reading file metadata"))

    root = Path(".")
    scanner = RepoScanner(root=root)
    scanned = scanner.scan()
    scanned = annotate_languages(scanned)
    repo_map = build_repo_map(scanner)

    repo_map_dict = {
        "root": str(repo_map.root),
        "languages": repo_map.languages,
        "frameworks": repo_map.frameworks,
        "entry_points": repo_map.entry_points,
        "test_locations": repo_map.test_locations,
        "dependency_files": repo_map.dependency_files,
        "build_commands": repo_map.build_commands,
        "total_files": repo_map.total_files,
        "total_lines": repo_map.total_lines,
        "total_size": repo_map.total_size,
        "top_dirs": repo_map.top_dirs,
    }

    return {
        "turn": current + 1,
        "current_node": "planning",
        "repo_map": repo_map_dict,
        "events": events,
    }


def planning_node(state) -> dict:
    """Rank files and generate a plan."""
    s = _to_dict(state)
    current = s.get("turn", 0)
    task = s.get("task", "")
    repo_map_dict = s.get("repo_map")
    events = list(s.get("events", []))
    events.append(_make_event(EventType.PLANNING_STARTED, current + 1, "Planning started"))
    events.append(_make_event(EventType.PLAN_GENERATED, current + 1, "Plan generated"))

    root = Path(".")
    scanner = RepoScanner(root=root)
    files = scanner.scan()
    files = annotate_languages(files)

    ranked = rank_files_by_relevance(task, files, root, max_results=20)

    from pgimcode.discovery.repo_map import RepoMap
    if repo_map_dict:
        repo_map_for_planner = RepoMap(
            root=Path(repo_map_dict["root"]),
            languages=repo_map_dict.get("languages", {}),
            frameworks=repo_map_dict.get("frameworks", []),
            entry_points=repo_map_dict.get("entry_points", []),
            test_locations=repo_map_dict.get("test_locations", []),
            dependency_files=repo_map_dict.get("dependency_files", []),
            build_commands=repo_map_dict.get("build_commands", []),
            total_files=repo_map_dict.get("total_files", 0),
            total_lines=repo_map_dict.get("total_lines", 0),
            total_size=repo_map_dict.get("total_size", 0),
            top_dirs=repo_map_dict.get("top_dirs", []),
        )
    else:
        repo_map_for_planner = build_repo_map(scanner)

    planner = TaskPlanner(repo_map=repo_map_for_planner, ranked_files=ranked)
    plan = planner.plan(task)

    plan_dict = {
        "task": plan.task,
        "interpretation": plan.interpretation,
        "objective": plan.objective,
        "constraints": plan.constraints,
        "acceptance_criteria": plan.acceptance_criteria,
        "assumptions": plan.assumptions,
        "steps": [
            {
                "description": step.description,
                "status": step.status,
                "tool": step.tool,
                "target": step.target,
                "reasoning": step.reasoning,
            }
            for step in plan.steps
        ],
        "files_to_inspect": plan.files_to_inspect,
        "next_action": plan.next_action,
        "confidence": plan.confidence,
    }

    return {
        "turn": current + 1,
        "current_node": "decision",
        "plan": plan_dict,
        "events": events,
    }


# Routing function passed to add_conditional_edges.
# In mock mode, cycles: inspect → edit → execute → verify → finish.
def next_node(state) -> Literal["inspect", "edit", "execute", "verify", "compact", "approval", "finish"]:
    """Routing function: return the name of the next node to execute."""
    s = _to_dict(state)
    turn = s.get("turn", 0)
    max_turns = s.get("max_turns", 50)
    next_node_val = s.get("next_node", "")

    if turn >= max_turns:
        return "finish"

    if next_node_val == "inspect":
        return "inspect"
    if next_node_val == "edit":
        return "edit"
    if next_node_val == "execute":
        return "execute"
    if next_node_val == "verify":
        return "verify"
    if next_node_val == "compact":
        return "compact"
    if next_node_val == "approval":
        return "approval"
    if next_node_val == "finish":
        return "finish"

    # Default: start cycling at inspect
    if not next_node_val and turn < max_turns:
        return "inspect"

    return "finish"


# Stub action nodes — each sets last_tool_result, advances turn, sets next_node

def inspect_node(state) -> dict:
    """Inspect files based on plan."""
    s = _to_dict(state)
    current = s.get("turn", 0)
    return {
        "turn": current + 1,
        "last_tool_result": {"mock": True, "node": "inspect"},
        "next_node": "edit",
        "current_node": "decision",
    }


def edit_node(state) -> dict:
    """Apply edits."""
    s = _to_dict(state)
    current = s.get("turn", 0)
    changed = list(s.get("changed_files", []))
    changed.append(f"mock_edit_{current}")
    return {
        "turn": current + 1,
        "last_tool_result": {"mock": True, "node": "edit"},
        "changed_files": changed,
        "next_node": "execute",
        "current_node": "decision",
    }


def execute_node(state) -> dict:
    """Execute commands or tests."""
    s = _to_dict(state)
    current = s.get("turn", 0)
    return {
        "turn": current + 1,
        "last_tool_result": {"mock": True, "node": "execute"},
        "next_node": "verify",
        "current_node": "decision",
    }


def verify_node(state) -> dict:
    """Verify changes."""
    s = _to_dict(state)
    current = s.get("turn", 0)
    return {
        "turn": current + 1,
        "last_tool_result": {"mock": True, "node": "verify"},
        "next_node": "finish",
        "current_node": "decision",
    }


def compact_node(state) -> dict:
    """Compact context if needed (every 5 turns)."""
    s = _to_dict(state)
    current = s.get("turn", 0)
    active_events = list(s.get("active_events", []))
    events = s.get("events", [])

    if current % 5 == 0 and events:
        recent = events[-5:]
        active_events = recent

    return {
        "turn": current + 1,
        "active_events": active_events,
        "current_node": "decision",
        "next_node": "inspect",
    }


def approval_node(state) -> dict:
    """Check if approval is required."""
    s = _to_dict(state)
    current = s.get("turn", 0)
    changed_files = s.get("changed_files", [])
    approval_required = len(changed_files) > 0
    return {
        "turn": current + 1,
        "approval_required": approval_required,
        "approval_reason": "Edit requires approval" if approval_required else "",
        "current_node": "decision",
        "next_node": "inspect",
    }


def finish_node(state) -> dict:
    """Finalize session."""
    return {
        "status": "completed",
        "current_node": "finish",
    }