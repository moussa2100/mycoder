"""Runtime context schema for per-invocation configuration.

Defines the shape of data passed via ``runtime.context`` to tools and
middleware. This is immutable per run and propagates to all sub-agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    """Per-invocation context that flows to the agent and all sub-agents.

    Tools access this via ``runtime.context`` (the ``ToolRuntime`` object).
    Middleware can read it via ``request.runtime.context``.

    Attributes:
        mode: Agent operating mode (build, plan, review).
        user_id: Optional user identifier for multi-user setups.
        preferences: User preferences dict (e.g., {"verbose": False}).
        workspace_root: Absolute path to the workspace root.
        session_id: Current session ULID.
        recent_files: Files changed in prior turns of a chat session.
        conversation_history: Prior task/success pairs for context carryover.
        extra: Catch-all for provider-specific or future fields.
    """
    mode: str = "build"
    user_id: str = "default"
    preferences: dict[str, Any] = field(default_factory=dict)
    workspace_root: str = ""
    session_id: str = ""
    recent_files: list[str] = field(default_factory=list)
    conversation_history: list[tuple[str, bool]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
