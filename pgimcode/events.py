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