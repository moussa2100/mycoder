"""Services that wrap pgimcode's RealAgent for the API layer.

Each function creates a real pgimcode session (SessionStore + EventLogWriter)
so that sessions started via the API show up in the CLI `/sessions` listing.

The agent's coordinator messages are captured from the EventBus and exposed
either as a single string (generate_plan) or as an async chunk stream
(execute_task_stream, chat_stream).
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from pgimcode.agent import RealAgent
from pgimcode.config import Settings
from pgimcode.events import Event, EventBus, EventLogWriter, EventType
from pgimcode.session import SessionStore

_settings: Settings | None = None
_SENTINEL = object()


def _get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def _make_session(task: str, mode: str = "build"):
    """Create + persist a Session and return (store, session, log_writer, bus)."""
    store = SessionStore()
    session = store.create(task=task, mode=mode)
    store.save(session)
    bus = EventBus()
    log_writer = EventLogWriter(store.jsonl_path(session.id))

    async def _log(event: Event) -> None:
        await log_writer.write(event)

    bus.subscribe(_log)
    return store, session, bus


def _finalize(store: SessionStore, session, step_count: int, failed: bool = False) -> None:
    session.status = "failed" if failed else "completed"
    session.completed_at = datetime.now(timezone.utc)
    session.step_count = step_count
    try:
        store.update(session)
    except Exception:
        pass


def _build_agent(bus: EventBus, session_id: str, task: str, mode: str) -> RealAgent:
    return RealAgent(
        bus=bus,
        session_id=session_id,
        task=task,
        mode=mode,
        settings=_get_settings(),
        renderer=None,
        recent_files=[],
        conversation_history=[],
    )


def _chdir_guard(workspace_dir: str | None):
    """Context-manager-ish helper: chdir into workspace_dir, return prior cwd."""
    prior = os.getcwd()
    if workspace_dir and os.path.isdir(workspace_dir):
        os.chdir(workspace_dir)
    return prior


async def _run_collecting(agent: RealAgent, bus: EventBus) -> str:
    """Run the agent and concatenate every COORDINATOR_MESSAGE event into one string."""
    chunks: list[str] = []

    def _capture(event: Event) -> None:
        if event.type in (EventType.COORDINATOR_MESSAGE, EventType.SUBAGENT_MESSAGE):
            if event.details:
                chunks.append(event.details)

    bus.subscribe(_capture)
    await agent.run()
    return "\n".join(c for c in chunks if c).strip()


async def _run_streaming(
    agent: RealAgent, bus: EventBus
) -> AsyncIterator[str]:
    """Run the agent and yield COORDINATOR_MESSAGE chunks as they arrive."""
    queue: asyncio.Queue = asyncio.Queue()

    async def _capture(event: Event) -> None:
        if event.type in (EventType.COORDINATOR_MESSAGE, EventType.SUBAGENT_MESSAGE):
            if event.details:
                await queue.put(event.details)

    bus.subscribe(_capture)

    async def _drive() -> None:
        try:
            await agent.run()
        finally:
            await queue.put(_SENTINEL)

    task = asyncio.create_task(_drive())
    try:
        while True:
            item = await queue.get()
            if item is _SENTINEL:
                break
            yield item
    finally:
        if not task.done():
            task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


# ── generate_plan ─────────────────────────────────────────────

async def generate_plan(
    title: str,
    description: str,
    model: str,
    feedback: str | None = None,
    current_plan: str | None = None,
) -> str:
    if feedback and current_plan:
        prompt = (
            f"You are a task planning assistant. Revise the plan based on the user's feedback.\n\n"
            f"Task: {title}\nDescription: {description or 'None'}\n\n"
            f"Current plan:\n{current_plan}\n\nUser feedback: {feedback}\n\n"
            f"Return the revised plan in clear markdown."
        )
    else:
        prompt = (
            f"You are a task planning assistant. Produce a structured, actionable plan.\n\n"
            f"Task Title: {title}\nDescription: {description or 'None'}\n\n"
            f"Provide: 1) summary, 2) numbered steps, 3) risks, 4) complexity (Low/Med/High).\n"
            f"Return concise markdown only."
        )

    store, session, bus = _make_session(task=f"plan: {title}", mode="plan")
    failed = False
    try:
        agent = _build_agent(bus, session.id, prompt, mode="plan")
        result = await _run_collecting(agent, bus)
        return result or "Plan generated."
    except Exception as e:
        failed = True
        return f"## Plan Generation Error\n\n{e}"
    finally:
        _finalize(store, session, step_count=1, failed=failed)


# ── execute_task_stream ───────────────────────────────────────

async def execute_task_stream(
    task_id: str,
    task_title: str,
    task_plan: str,
    model: str,
    workspace_dir: str,
) -> AsyncIterator[str]:
    prompt = (
        f"Execute this task based on the plan.\n\n"
        f"Task: {task_title}\n\nPlan:\n{task_plan}\n\n"
        f"Report progress step by step."
    )
    store, session, bus = _make_session(task=f"execute: {task_title}", mode="build")
    prior_cwd = _chdir_guard(workspace_dir)
    failed = False
    step = 0
    try:
        agent = _build_agent(bus, session.id, prompt, mode="build")
        async for chunk in _run_streaming(agent, bus):
            step += 1
            yield chunk
    except Exception as e:
        failed = True
        yield f"\n## Execution Error\n\n{e}"
    finally:
        os.chdir(prior_cwd)
        _finalize(store, session, step_count=step, failed=failed)


# ── chat_stream ───────────────────────────────────────────────

async def chat_stream(
    message: str,
    model: str,
    workspace_dir: str,
) -> AsyncIterator[str]:
    store, session, bus = _make_session(task=message[:200], mode="build")
    prior_cwd = _chdir_guard(workspace_dir)
    failed = False
    step = 0
    try:
        agent = _build_agent(bus, session.id, message, mode="build")
        async for chunk in _run_streaming(agent, bus):
            step += 1
            yield chunk
    except Exception as e:
        failed = True
        yield f"Error: {e}"
    finally:
        os.chdir(prior_cwd)
        _finalize(store, session, step_count=step, failed=failed)
