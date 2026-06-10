"""Custom state schema for the pgimcode agent graph.

Extends ``DeepAgentState`` with fields that track mutable state across
agent turns — recent files, conversation history, and session metadata.
These fields are checkpointed with the thread and available through
``runtime.state`` in tools and middleware.
"""

from __future__ import annotations

from deepagents import DeepAgentState
from typing import Annotated


def _accumulate_list(current: list[str], new: list[str]) -> list[str]:
    """Reducer that appends new items, keeping the last N unique entries."""
    seen = set(current)
    result = list(current)
    for item in new:
        if item not in seen:
            result.append(item)
            seen.add(item)
    # Keep last 50
    return result[-50:]


def _accumulate_history(
    current: list[tuple[str, bool]], new: list[tuple[str, bool]]
) -> list[tuple[str, bool]]:
    """Reducer that appends new history entries, keeping the last 20."""
    result = list(current) + list(new)
    return result[-20:]


class PgimcodeState(DeepAgentState):
    """Custom state for pgimcode agent sessions.

    Attributes:
        recent_files: Files modified in the current session.
        conversation_history: Prior task/success pairs for context carryover.
        session_mode: The agent's operating mode (build, plan, review).
        current_task: The current task description.
    """
    recent_files: Annotated[list[str], _accumulate_list] = []
    conversation_history: Annotated[list[tuple[str, bool]], _accumulate_history] = []
    session_mode: str = "build"
    current_task: str = ""
