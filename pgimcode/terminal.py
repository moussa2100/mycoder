"""Rich Live Terminal Renderer for pgimcode."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.live import Live

from pgimcode.config import Settings
from pgimcode.events import Event, EventType


# Event type to icon mapping
_EVENT_ICONS: dict[EventType, str] = {
    EventType.SESSION_STARTED: "🚀",
    EventType.REPO_SCANNING: "🔍",
    EventType.FILE_READING: "📄",
    EventType.RESEARCH_STARTED: "🧭",
    EventType.EVIDENCE_CAPTURED: "🧠",
    EventType.PLANNING_STARTED: "📝",
    EventType.PATCH_APPLYING: "🔧",
    EventType.TESTS_RUNNING: "🧪",
    EventType.VERIFICATION_STARTED: "🔒",
    EventType.TASK_UPDATED: "📋",
    EventType.DIFF_READY: "🧩",
    EventType.SELF_REVIEW_STARTED: "🔎",
    EventType.SELF_REVIEW_COMPLETED: "🛡️",
    EventType.MILESTONE_REACHED: "🏁",
    EventType.BLOCKED_FOR_APPROVAL: "🛑",
    EventType.COMPLETED: "✅",
    EventType.FAILED: "❌",
    EventType.MODEL_SWITCHED: "🔄",
    # Event streaming (v3 protocol)
    EventType.SUBAGENT_STARTED: "🧑‍💻",
    EventType.SUBAGENT_COMPLETED: "✅",
    EventType.SUBAGENT_FAILED: "❌",
    EventType.SUBAGENT_MESSAGE: "💬",
    EventType.SUBAGENT_TOOL_CALL: "🔧",
    EventType.SUBAGENT_TOOL_RESULT: "📦",
    EventType.COORDINATOR_MESSAGE: "🤖",
    EventType.COORDINATOR_TOOL_CALL: "🔧",
    EventType.COORDINATOR_TOOL_RESULT: "📦",
}

# Status to icon mapping
_STATUS_ICONS: dict[str, str] = {
    "done": "✓",
    "failed": "✗",
    "in_progress": "◐",
    "started": "◐",
}


class RichTerminalRenderer:
    """Renders events in a rich Live terminal display."""

    def __init__(
        self,
        console: Console | None = None,
        session_id: str = "",
        task: str = "",
        mode: str = "build"
    ):
        self._console = console or Console()
        self._session_id = session_id
        self._task = task
        self._mode = mode
        self._events: list[Event] = []
        self._start_time = time.time()
        self._live: Live | None = None
        self._settings = Settings()
        self._current_model = self._settings.model_name

    def add_event(self, event: Event) -> None:
        """Append an event to the internal list."""
        self._events.append(event)

    def set_model(self, model_name: str) -> None:
        """Update the current model name shown in the header."""
        self._current_model = model_name

    def pause_live(self) -> None:
        """Pause the Live display for interactive prompts."""
        if self._live and self._live.is_started:
            self._live.stop()

    def resume_live(self) -> None:
        """Resume the Live display after interactive prompts."""
        if self._live:
            self._live.start()

    def _get_icon(self, event: Event) -> str:
        """Get the icon for an event based on type and status."""
        # Check status first for done/failed
        if event.status == "done":
            if event.type == EventType.COMPLETED:
                return "✅"
            elif event.type == EventType.FAILED:
                return "❌"
            return _STATUS_ICONS.get("done", "✓")
        elif event.status == "failed":
            return _STATUS_ICONS.get("failed", "✗")
        elif event.status in ("in_progress", "started"):
            return _STATUS_ICONS.get("in_progress", "◐")

        # Fallback to event type icon
        return _EVENT_ICONS.get(event.type, "•")

    def _get_color(self, event: Event) -> str:
        """Get color based on status."""
        if event.status == "done":
            return "green"
        elif event.status == "failed":
            return "red"
        elif event.status in ("in_progress", "started"):
            return "yellow"
        return "white"

    def _format_event_line(self, event: Event) -> Text:
        """Format a single event as a rich Text line."""
        icon = self._get_icon(event)
        color = self._get_color(event)

        step_str = f" [{event.step}]" if event.step > 0 else ""
        details = event.details or ""

        text = Text(f"{icon}{step_str} {event.type.value}: {details}", style=color)
        return text

    def render(self) -> Layout:
        """Return a rich Layout with header, current step, and event feed."""
        settings = Settings()
        layout = Layout(name="root")

        # Header (1 line)
        header_text = Text()
        header_text.append(f"{settings.app_name} ", style="bold cyan")
        header_text.append(f"v{settings.version} ", style="dim")
        header_text.append(f"| {self._session_id} ", style="dim")
        header_text.append(f"| ", style="dim")
        header_text.append(f"{self._task} ", style="bold")
        header_text.append(f"| {self._mode}", style="dim")
        header_text.append(f" | model: {self._current_model}", style="dim cyan")

        header_panel = Panel(header_text, border_style="cyan", padding=(0, 1))
        layout.split_column(
            Layout(header_panel, size=1),
            Layout(name="current_step", size=8),
            Layout(name="event_feed"),
        )

        # Current Step Panel (8 lines)
        current_event = self._events[-1] if self._events else None
        if current_event:
            elapsed = int(time.time() - self._start_time)
            snapshot = current_event.data or {}
            step_text = Text()
            step_text.append(f"{self._get_icon(current_event)} ", style=self._get_color(current_event))
            step_text.append(f"{current_event.type.value}\n", style="bold")
            step_text.append(f"{current_event.details or 'No details'}\n", style="white")
            candidate_files = snapshot.get("candidate_files", [])
            evidence_count = snapshot.get("evidence_count", 0)
            if candidate_files or evidence_count:
                step_text.append(
                    f"Candidates {len(candidate_files)} | Evidence {evidence_count} | ",
                    style="dim cyan",
                )
            step_text.append(f"Step {current_event.step} | ", style="dim")
            step_text.append(f"Elapsed {elapsed}s", style="dim")

            current_step_panel = Panel(
                step_text,
                border_style=self._get_color(current_event),
                padding=(1, 2),
                title="Current Step",
            )
        else:
            current_step_panel = Panel(
                Text("Waiting for events...", style="dim"),
                border_style="blue",
                padding=(1, 2),
                title="Current Step",
            )

        layout["current_step"].update(current_step_panel)

        # Event Feed Panel (remaining): last 12 events
        feed_text = Text()
        recent_events = self._events[-12:] if len(self._events) > 12 else self._events

        for event in recent_events:
            feed_text.append(self._format_event_line(event))
            feed_text.append("\n")

        if not recent_events:
            feed_text.append("No events yet", style="dim")

        event_feed_panel = Panel(
            feed_text,
            border_style="blue",
            padding=(0, 1),
            title="Event Feed",
        )
        layout["event_feed"].update(event_feed_panel)

        return layout

    def _summary_text(self) -> Text | None:
        """Return Rich Text summary if COMPLETED or FAILED, else None."""
        if not self._events:
            return None

        last_event = self._events[-1]

        # Only show summary for COMPLETED or FAILED
        if last_event.type not in (EventType.COMPLETED, EventType.FAILED):
            return None

        duration = int(time.time() - self._start_time)
        step_count = len(self._events)

        summary = Text()
        if last_event.type == EventType.COMPLETED:
            summary.append("✅ COMPLETED", style="bold green")
        else:
            summary.append("❌ FAILED", style="bold red")

        summary.append(f"\nTask: {self._task}\n")
        summary.append(f"Duration: {duration}s\n")
        summary.append(f"Steps: {step_count}\n")

        # Include log file path if session_id is available
        if self._session_id:
            from pgimcode.session import SessionStore
            store = SessionStore()
            log_path = store.jsonl_path(self._session_id)
            summary.append(f"Log: {log_path}", style="dim")

        return summary

    def __enter__(self) -> "RichTerminalRenderer":
        """Start the rich Live display at 4 FPS."""
        self._start_time = time.time()
        layout = self.render()
        self._live = Live(
            layout,
            console=self._console,
            refresh_per_second=4,
            transient=False
        )
        self._live.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop Live display and print static summary if completed/failed."""
        if self._live:
            self._live.stop()

            # Print static summary if completed or failed
            summary = self._summary_text()
            if summary:
                self._console.print("\n")
                self._console.print(Panel(
                    summary,
                    border_style="green" if exc_type is None or exc_type == type(None) else "red",
                    padding=(1, 2),
                ))

    def refresh(self) -> None:
        """Update the Live display if running."""
        if self._live and self._live.is_started:
            self._live.update(self.render())