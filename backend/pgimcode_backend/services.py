"""Services that wrap pgimcode's RealAgent for the API layer.

Each service function handles a specific agent interaction:
- generate_plan: analyze a task request and produce a structured plan
- execute_task: run a task from its plan and stream results
- chat: conversational interaction with the agent
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from pgimcode.agent import RealAgent
from pgimcode.config import Settings
from pgimcode.events import EventBus
from pgimcode.session import _new_ulid

# Reusable settings instance (reads from .env in project root)
_settings: Settings | None = None


def _get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def _build_agent(
    task: str,
    workspace_root: str,
    mode: str = "build",
) -> RealAgent:
    """Create a RealAgent instance ready to run."""
    settings = _get_settings()
    session_id = _new_ulid()
    bus = EventBus(session_id=session_id)

    return RealAgent(
        bus=bus,
        session_id=session_id,
        task=task,
        mode=mode,
        settings=settings,
        renderer=None,  # No terminal renderer in API mode
        recent_files=[],
        conversation_history=[],
    )


async def generate_plan(
    title: str,
    description: str,
    model: str,
    feedback: str | None = None,
    current_plan: str | None = None,
) -> str:
    """Generate a plan for a task using the LLM agent.

    Returns the plan content as a markdown string.
    """
    if feedback and current_plan:
        prompt = f"""You are a task planning assistant. The user has provided feedback on a plan and wants it modified.

Original task: {title}
Description: {description or 'No description'}

Current plan:
{current_plan}

User feedback: {feedback}

Please revise the plan based on the feedback. Keep the same structure but incorporate the changes requested."""
    else:
        prompt = f"""You are a task planning assistant. Analyze this task request and create a structured, actionable plan.

Task Title: {title}
Description: {description or 'No description provided'}

Provide:
1. A summary of what needs to be done
2. Key steps in order (numbered)
3. Potential challenges and considerations
4. Estimated complexity (Low/Medium/High)

Format the response in clear markdown. Keep it concise and actionable."""

    try:
        agent = _build_agent(task=prompt, workspace_root="/", mode="plan")
        # Run agent synchronously in a thread to avoid blocking
        result = await asyncio.to_thread(agent.run)
        return result or "Plan generated successfully."
    except Exception as e:
        return f"## Plan Generation Error\n\nAn error occurred: {str(e)}\n\nPlease check your API keys and try again."


async def execute_task_stream(
    task_id: str,
    task_title: str,
    task_plan: str,
    model: str,
    workspace_dir: str,
) -> AsyncIterator[str]:
    """Execute a task and yield streaming output chunks.

    This is a generator that yields SSE-formatted text chunks
    as the agent executes the task.
    """
    prompt = f"""Execute the following task based on the plan.

Task: {task_title}

Plan:
{task_plan}

Work in the workspace directory and complete the implementation.
Report your progress step by step."""

    try:
        agent = _build_agent(
            task=prompt,
            workspace_root=workspace_dir or ".",
            mode="build",
        )
        # In a real implementation, we'd stream from the agent's event bus
        # For now, we run the agent and yield results
        result = await asyncio.to_thread(agent.run)
        yield result or "Task execution completed."
    except Exception as e:
        yield f"\n## Execution Error\n\n{str(e)}"


async def chat_stream(
    message: str,
    model: str,
    workspace_dir: str,
) -> AsyncIterator[str]:
    """Chat with the agent and yield streaming response chunks."""
    prompt = f"""You are pgimcode, a terminal AI coding assistant. 

The user says: {message}

Respond helpfully and concisely. If they're asking about code, reference 
the workspace directory context as needed."""
    try:
        agent = _build_agent(
            task=prompt,
            workspace_root=workspace_dir or ".",
            mode="build",
        )
        result = await asyncio.to_thread(agent.run)
        yield result or "I processed your message."
    except Exception as e:
        yield f"Error: {str(e)}"
