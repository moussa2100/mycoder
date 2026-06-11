"""Shared CLI session infrastructure — eliminates duplicated setup across commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from pgimcode.config import Settings
from pgimcode.events import Event, EventBus, EventLogWriter, EventType
from pgimcode.session import SessionStore
from pgimcode.terminal import RichTerminalRenderer

if TYPE_CHECKING:
    from pgimcode.approval import ApprovalConfig, ApprovalGate


@dataclass
class CLISession:
    """Encapsulates the shared setup for all CLI commands: bus, store, session,
    log writer, renderer, and event subscriptions.

    Usage::

        sess = CLISession.create(task="My task", mode="build")
        with sess.renderer:
            await sess.bus.publish(...)
            # ... do work ...
        sess.complete()

    Or use the async context manager::

        async with CLISession.create(task="...", mode="plan") as sess:
            await sess.bus.publish(...)
    """

    bus: EventBus
    store: SessionStore
    session: object  # Session dataclass
    log_writer: EventLogWriter
    console: Console
    renderer: RichTerminalRenderer

    # Optional
    metrics_collector: object | None = None
    trace_recorder: object | None = None

    @classmethod
    def create(
        cls,
        task: str,
        mode: str = "build",
        *,
        resume: str | None = None,
        no_color: bool = False,
        metrics: bool = False,
        trace_export: str | None = None,
        settings: Settings | None = None,
    ) -> "CLISession":
        """Create a fully-wired CLI session with bus, store, renderer, and log writer."""
        console = Console(no_color=no_color)
        store = SessionStore()
        trace_recorder = None
        metrics_collector = None

        # Create or resume session
        if resume:
            session = store.get(resume)
            if not session:
                raise ValueError(f"Session '{resume}' not found.")
        else:
            session = store.create(task=task, mode=mode)
            store.save(session)

        # Trace recorder
        if trace_export:
            from pgimcode.observability import TraceRecorder
            trace_recorder = TraceRecorder(
                session_id=session.id, output_path=Path(trace_export)
            )

        # Metrics collector
        if metrics:
            from pgimcode.observability import MetricsCollector
            metrics_collector = MetricsCollector(session_id=session.id, task=task)
            metrics_collector.start()

        bus = EventBus(
            metrics_collector=metrics_collector,
            trace_recorder=trace_recorder,
        )

        # Log writer
        jsonl_path = store.jsonl_path(session.id)
        log_writer = EventLogWriter(jsonl_path)

        # Terminal renderer
        renderer = RichTerminalRenderer(
            console=console,
            session_id=session.id,
            task=task,
            mode=mode,
        )

        # Wire events to renderer + log writer
        def _on_event(event: Event) -> None:
            renderer.add_event(event)
            renderer.refresh()

        async def _log_event(event: Event) -> None:
            await log_writer.write(event)

        bus.subscribe(_on_event)
        bus.subscribe(_log_event)

        return cls(
            bus=bus,
            store=store,
            session=session,
            log_writer=log_writer,
            console=console,
            renderer=renderer,
            metrics_collector=metrics_collector,
            trace_recorder=trace_recorder,
        )

    @property
    def session_id(self) -> str:
        return self.session.id  # type: ignore[union-attr]

    def complete(self, step_count: int = 0) -> None:
        """Mark the session as completed and persist."""
        self.session.status = "completed"  # type: ignore[union-attr]
        self.session.completed_at = datetime.now(timezone.utc)  # type: ignore[union-attr]
        if step_count:
            self.session.step_count = step_count  # type: ignore[union-attr]
        self.store.save(self.session)  # type: ignore[arg-type]

    def fail(self, step_count: int = 0) -> None:
        """Mark the session as failed and persist."""
        self.session.status = "failed"  # type: ignore[union-attr]
        self.session.completed_at = datetime.now(timezone.utc)  # type: ignore[union-attr]
        if step_count:
            self.session.step_count = step_count  # type: ignore[union-attr]
        self.store.update(self.session)  # type: ignore[arg-type]

    async def __aenter__(self) -> "CLISession":
        self.renderer.__enter__()
        return self

    async def __aexit__(self, *args: object) -> None:
        self.renderer.__exit__(*args)


def create_approval_gate(
    *,
    auto_approve: bool = False,
    session_id: str = "",
    bus: EventBus | None = None,
    console: Console | None = None,
    no_color: bool = False,
) -> "ApprovalGate":
    """Create an ApprovalGate with optional interactive prompt.

    This is duplicated across default_callback, run, and chat_command —
    extracted here as a single factory.
    """
    from pgimcode.approval import ApprovalConfig, ApprovalGate

    config = ApprovalConfig(auto_approve_caution=auto_approve)
    gate = ApprovalGate(
        config=config, session_id=session_id, bus=bus, console=console
    )

    if not auto_approve:
        c = console or Console(no_color=no_color)

        def _prompt_user(action: str, details: str) -> bool:
            c.print(f"\n[yellow]🛑 Approval required:[/] {action}")
            c.print(f"[dim]{details}[/dim]")
            answer = c.input("Approve? [y/N]: ").strip().lower()
            return answer in ("y", "yes")

        gate.prompt_fn = _prompt_user

    return gate
