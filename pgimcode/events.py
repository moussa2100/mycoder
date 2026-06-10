"""Event system: typed events, async bus, JSONL writer."""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from pgimcode.observability import MetricsCollector, TraceRecorder

from pydantic import BaseModel


class EventType(str, Enum):
    SESSION_STARTED = "session_started"
    REPO_SCANNING = "repo_scanning"
    FILE_READING = "file_reading"
    RESEARCH_STARTED = "research_started"
    EVIDENCE_CAPTURED = "evidence_captured"
    PLANNING_STARTED = "planning_started"
    PLAN_GENERATED = "plan_generated"
    PATCH_APPLYING = "patch_applying"
    TESTS_RUNNING = "tests_running"
    VERIFICATION_STARTED = "verification_started"
    TASK_UPDATED = "task_updated"
    DIFF_READY = "diff_ready"
    SELF_REVIEW_STARTED = "self_review_started"
    SELF_REVIEW_COMPLETED = "self_review_completed"
    MILESTONE_REACHED = "milestone_reached"
    BLOCKED_FOR_APPROVAL = "blocked_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CONTEXT_COMPACTED = "context_compacted"
    MODEL_SWITCHED = "model_switched"
    # Event streaming (v3 protocol)
    SUBAGENT_STARTED = "subagent_started"
    SUBAGENT_COMPLETED = "subagent_completed"
    SUBAGENT_FAILED = "subagent_failed"
    SUBAGENT_MESSAGE = "subagent_message"
    SUBAGENT_TOOL_CALL = "subagent_tool_call"
    SUBAGENT_TOOL_RESULT = "subagent_tool_result"
    COORDINATOR_MESSAGE = "coordinator_message"
    COORDINATOR_TOOL_CALL = "coordinator_tool_call"
    COORDINATOR_TOOL_RESULT = "coordinator_tool_result"


class Event(BaseModel):
    id: str | None = None
    session_id: str
    timestamp: datetime = datetime.now(timezone.utc)
    type: EventType
    step: int = 0
    status: str = "started"
    details: str | None = None
    data: dict | None = None

    def model_dump_json(self, **kwargs) -> str:
        kwargs.setdefault("exclude_none", True)
        return super().model_dump_json(**kwargs)


# Type alias for event handler
EventHandler = Callable[[Event], None]


class EventBus:
    """Simple async pub/sub event bus."""

    def __init__(
        self,
        metrics_collector: "MetricsCollector | None" = None,
        trace_recorder: "TraceRecorder | None" = None,
    ):
        self._handlers: list[EventHandler] = []
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._metrics_collector = metrics_collector
        self._trace_recorder = trace_recorder

    def subscribe(self, handler: EventHandler) -> None:
        """Register a handler."""
        self._handlers.append(handler)

    async def publish(self, event: Event) -> None:
        """Publish an event to all handlers."""
        start = time.perf_counter()
        await self._queue.put(event)
        # Dispatch immediately inline
        for handler in self._handlers:
            if inspect.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        end = time.perf_counter()
        duration_ms = (end - start) * 1000
        if self._metrics_collector:
            self._metrics_collector.record(event, duration_ms)
        if self._trace_recorder:
            self._trace_recorder.record(event, duration_ms)

    async def drain(self) -> None:
        """Wait until queue is empty."""
        await self._queue.join()


class EventLogWriter:
    """Appends events as JSONL to a file."""

    def __init__(self, path: Path):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def write(self, event: Event) -> None:
        async with self._lock:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")


class EventStreamAdapter:
    """Bridges a GraphRunStream (v3 protocol) to the EventBus.

    Consumes the stream's projections (messages, subagents, tool_calls)
    and publishes typed Event objects so the renderer and log writer
    see structured, real-time updates.

    When a renderer is provided, it also calls ``on_assistant_token``
    for token-level streaming of coordinator messages.
    """

    def __init__(self, bus: EventBus, session_id: str, renderer=None):
        self._bus = bus
        self._session_id = session_id
        self._renderer = renderer
        self._step = 0
        self._seen_subagents: set[str] = set()

    async def consume(self, stream) -> None:
        """Iterate the v3 stream and publish events for each projection."""
        import time

        from pgimcode.session import _new_ulid

        # Consume coordinator messages (token-level streaming to renderer)
        async for message in self._iter_channel(getattr(stream, "messages", None)):
            self._step += 1
            text = await self._message_text(message)
            if text:
                # Token-level streaming to renderer
                if self._renderer and hasattr(self._renderer, "on_assistant_token"):
                    self._renderer.on_assistant_token(text)

                await self._bus.publish(Event(
                    id=_new_ulid(),
                    session_id=self._session_id,
                    type=EventType.COORDINATOR_MESSAGE,
                    step=self._step,
                    status="in_progress",
                    details=text[:500],
                ))

        # Consume subagent lifecycle
        async for subagent in self._iter_channel(getattr(stream, "subagents", None)):
            name = getattr(subagent, "name", "unknown")
            if name not in self._seen_subagents:
                self._seen_subagents.add(name)
                self._step += 1
                await self._bus.publish(Event(
                    id=_new_ulid(),
                    session_id=self._session_id,
                    type=EventType.SUBAGENT_STARTED,
                    step=self._step,
                    status="in_progress",
                    details=f"Subagent started: {name}",
                    data={"subagent_name": name},
                ))

            # Subagent messages
            try:
                async for msg in self._iter_channel(getattr(subagent, "messages", None)):
                    self._step += 1
                    text = await self._message_text(msg)
                    if text:
                        # Show subagent text in renderer
                        if self._renderer and hasattr(self._renderer, "show_assistant_text"):
                            self._renderer.show_assistant_text(f"[{name}] {text}")

                        await self._bus.publish(Event(
                            id=_new_ulid(),
                            session_id=self._session_id,
                            type=EventType.SUBAGENT_MESSAGE,
                            step=self._step,
                            status="in_progress",
                            details=text[:500],
                            data={"subagent_name": name},
                        ))
            except Exception:
                pass

            # Subagent tool calls
            try:
                async for tc in self._iter_channel(getattr(subagent, "tool_calls", None)):
                    self._step += 1
                    tool_name = getattr(tc, "tool_name", "?")
                    tool_input = getattr(tc, "input", {})
                    await self._bus.publish(Event(
                        id=_new_ulid(),
                        session_id=self._session_id,
                        type=EventType.SUBAGENT_TOOL_CALL,
                        step=self._step,
                        status="in_progress",
                        details=f"{tool_name}({str(tool_input)[:200]})",
                        data={"subagent_name": name, "tool_name": tool_name},
                    ))

                    # Notify renderer
                    if self._renderer and hasattr(self._renderer, "on_tool_call"):
                        self._renderer.on_tool_call(tool_name, tool_input)

                    # Tool output
                    try:
                        output = getattr(tc, "output", None)
                        error = getattr(tc, "error", None)
                        if output is not None:
                            await self._bus.publish(Event(
                                id=_new_ulid(),
                                session_id=self._session_id,
                                type=EventType.SUBAGENT_TOOL_RESULT,
                                step=self._step,
                                status="done",
                                details=str(output)[:500],
                                data={"subagent_name": name, "tool_name": tool_name},
                            ))
                            if self._renderer and hasattr(self._renderer, "on_tool_result"):
                                self._renderer.on_tool_result(tool_name, str(output)[:500], success=True)
                        elif error is not None:
                            await self._bus.publish(Event(
                                id=_new_ulid(),
                                session_id=self._session_id,
                                type=EventType.SUBAGENT_TOOL_RESULT,
                                step=self._step,
                                status="failed",
                                details=str(error)[:500],
                                data={"subagent_name": name, "tool_name": tool_name},
                            ))
                            if self._renderer and hasattr(self._renderer, "on_tool_result"):
                                self._renderer.on_tool_result(tool_name, str(error)[:500], success=False)
                    except Exception:
                        pass
            except Exception:
                pass

            # Subagent completion/failure
            try:
                _ = subagent.output
                self._step += 1
                await self._bus.publish(Event(
                    id=_new_ulid(),
                    session_id=self._session_id,
                    type=EventType.SUBAGENT_COMPLETED,
                    step=self._step,
                    status="done",
                    details=f"Subagent completed: {name}",
                    data={"subagent_name": name},
                ))
            except Exception:
                self._step += 1
                await self._bus.publish(Event(
                    id=_new_ulid(),
                    session_id=self._session_id,
                    type=EventType.SUBAGENT_FAILED,
                    step=self._step,
                    status="failed",
                    details=f"Subagent failed: {name}",
                    data={"subagent_name": name},
                ))

        # Consume coordinator tool calls
        async for tc in self._iter_channel(getattr(stream, "tool_calls", None)):
            self._step += 1
            tool_name = getattr(tc, "tool_name", "?")
            tool_input = getattr(tc, "input", {})
            await self._bus.publish(Event(
                id=_new_ulid(),
                session_id=self._session_id,
                type=EventType.COORDINATOR_TOOL_CALL,
                step=self._step,
                status="in_progress",
                details=f"{tool_name}({str(tool_input)[:200]})",
            ))

            # Notify renderer
            if self._renderer and hasattr(self._renderer, "on_tool_call"):
                self._renderer.on_tool_call(tool_name, tool_input)

            try:
                output = getattr(tc, "output", None)
                error = getattr(tc, "error", None)
                if output is not None:
                    await self._bus.publish(Event(
                        id=_new_ulid(),
                        session_id=self._session_id,
                        type=EventType.COORDINATOR_TOOL_RESULT,
                        step=self._step,
                        status="done",
                        details=str(output)[:500],
                    ))
                    if self._renderer and hasattr(self._renderer, "on_tool_result"):
                        self._renderer.on_tool_result(tool_name, str(output)[:500], success=True)
                elif error is not None:
                    await self._bus.publish(Event(
                        id=_new_ulid(),
                        session_id=self._session_id,
                        type=EventType.COORDINATOR_TOOL_RESULT,
                        step=self._step,
                        status="failed",
                        details=str(error)[:500],
                    ))
                    if self._renderer and hasattr(self._renderer, "on_tool_result"):
                        self._renderer.on_tool_result(tool_name, str(error)[:500], success=False)
            except Exception:
                pass

    @staticmethod
    async def _iter_channel(channel):
        """Yield from an async stream channel, tolerating absent/sync channels."""
        if channel is None:
            return
        try:
            async for item in channel:
                yield item
        except RuntimeError as exc:
            if "bound to sync mode" not in str(exc):
                raise
            for item in channel:
                yield item

    @staticmethod
    async def _message_text(msg) -> str:
        """Extract text from a stream message projection."""
        try:
            text = await msg.text
            if isinstance(text, str) and text.strip():
                return text.strip()
        except Exception:
            pass
        try:
            output = msg.output
            content = getattr(output, "content", "") or ""
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                return "".join(parts).strip()
        except Exception:
            pass
        return ""