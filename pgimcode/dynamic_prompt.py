"""Dynamic prompt middleware for context-aware system prompt injection.

Reads from ``runtime.context`` and ``runtime.store`` to build context-aware
instructions that are appended to the system prompt at runtime.

Usage:
    ```python
    from pgimcode.dynamic_prompt import DynamicPromptMiddleware

    agent = create_deep_agent(
        model=model,
        middleware=[DynamicPromptMiddleware()],
        context_schema=AgentContext,
    )
    ```
"""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.base import AgentRequest, AgentResponse


class DynamicPromptMiddleware(AgentMiddleware):
    """Middleware that injects context-aware instructions into the system prompt.

    Reads ``request.runtime.context`` (the ``AgentContext`` dataclass) and
    appends a dynamic prompt section that reflects the current mode, user
    preferences, and session state.

    This is the pgimcode equivalent of the ``@dynamic_prompt`` decorator
    described in the DeepAgents context engineering docs.
    """

    def __init__(self) -> None:
        """Initialize the dynamic prompt middleware."""
        super().__init__()

    async def before_model(self, request: AgentRequest) -> AgentRequest:
        """Inject context-aware instructions before the model is called.

        Reads the runtime context and appends a dynamic prompt section
        to the system prompt.
        """
        ctx = getattr(request.runtime, "context", None)
        if ctx is None:
            return request

        # Build dynamic prompt sections from context
        sections: list[str] = []

        # ── Mode-specific instructions ──
        mode = getattr(ctx, "mode", "build")
        if mode == "plan":
            sections.append(
                "## Mode: Plan-Only\n"
                "You are in **plan-only** mode. Read files, explore the codebase, "
                "and produce a detailed plan. Do NOT edit any files or run destructive commands."
            )
        elif mode == "review":
            sections.append(
                "## Mode: Review\n"
                "You are in **review** mode. Read code and provide a thorough code review. "
                "Do NOT make any edits."
            )
        else:
            sections.append(
                "## Mode: Build\n"
                "You are in **build** mode. You may read, edit, and create files as needed."
            )

        # ── User preferences from context ──
        preferences = getattr(ctx, "preferences", {}) or {}
        if preferences.get("verbose") is False:
            sections.append(
                "## User Preference: Concise\n"
                "The user prefers concise responses. Keep explanations brief "
                "and focus on actionable output."
            )
        if preferences.get("auto_approve"):
            sections.append(
                "## User Preference: Auto-approve\n"
                "The user has enabled auto-approve. You may proceed with "
                "caution-level actions without waiting for approval."
            )

        # ── Session context ──
        session_id = getattr(ctx, "session_id", "")
        if session_id:
            sections.append(
                f"## Session Context\n"
                f"Session ID: {session_id}"
            )

        # ── Recent files ──
        recent_files = getattr(ctx, "recent_files", [])
        if recent_files:
            files_str = "\n".join(f"  - {f}" for f in recent_files[-8:])
            sections.append(
                "## Recent Changed Files\n"
                "The following files were modified in prior turns:\n"
                f"{files_str}"
            )

        # ── Conversation history ──
        history = getattr(ctx, "conversation_history", [])
        successes = [t for t, ok in history if ok][-3:]
        if successes:
            successes_str = "\n".join(f"  - {s}" for s in successes)
            sections.append(
                "## Recent Successful Requests\n"
                "Prior successful tasks in this session:\n"
                f"{successes_str}"
            )

        if not sections:
            return request

        dynamic_prompt = "\n\n".join(sections)

        # Append to the system prompt
        existing_prompt = getattr(request, "system_prompt", "") or ""
        if existing_prompt:
            request.system_prompt = f"{existing_prompt}\n\n{dynamic_prompt}"
        else:
            request.system_prompt = dynamic_prompt

        return request

    async def after_model(self, request: AgentRequest, response: AgentResponse) -> AgentResponse:
        """Pass through — no post-model processing needed."""
        return response
