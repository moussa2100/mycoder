"""Chat-style renderer that prints events inline (no Live display).

Extracted from ``chat.py`` to keep the module focused — this class is
pure rendering with zero dependencies on ``ChatSession``.
"""

from __future__ import annotations

import json as _json
import time

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from pgimcode.config import Settings
from pgimcode.events import Event, EventType

_DIRECT_RENDERED_EVENT_TYPES = frozenset({
    EventType.COORDINATOR_MESSAGE,
    EventType.COORDINATOR_TOOL_CALL,
    EventType.COORDINATOR_TOOL_RESULT,
    EventType.SUBAGENT_MESSAGE,
    EventType.SUBAGENT_TOOL_CALL,
    EventType.SUBAGENT_TOOL_RESULT,
})

_STREAMING_SAFE_EVENT_TYPES = frozenset({EventType.COMPLETED, EventType.FAILED})


class ChatRenderer:
    """Simple chat-style renderer that prints events inline (no Live display)."""

    def __init__(
        self,
        console: Console,
        session_id: str,
        settings: Settings | None = None,
    ):
        self._console = console
        self._session_id = session_id
        self._settings = settings or Settings()
        self._current_model = self._settings.model_name
        self._turn_start: float | None = None
        self._stream_active = False
        self._stream_chars = 0
        self._assistant_buffer = ""
        self._suppress_live_stream = False
        self._printed_texts: set[str] = set()
        self._todo_timers: dict[str, float] = {}
        self._todo_prev: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_welcome(self) -> None:
        """Display welcome banner at chat start."""
        from rich.align import Align

        self._console.print()
        welcome = Panel(
            Align.center(
                f"[bold cyan]{self._settings.app_name}[/] [dim]v{self._settings.version}[/]\n"
                f"[dim]Terminal AI Coding Assistant[/]\n\n"
                f"[dim]Model:[/] [bold]{self._current_model}[/]\n"
                f"[dim]Type /help for commands, /quit to exit[/]",
                vertical="middle",
            ),
            border_style="cyan",
            padding=(1, 3),
            title="[bold]Welcome[/]",
        )
        self._console.print(welcome)
        self._console.print()

    def show_info(self) -> None:
        """Show a one-line info bar with session and model."""
        self._console.print(
            f"[dim]{self._settings.app_name} • {self._current_model} • {self._session_id}[/]"
        )

    def start_turn(self, task: str) -> None:
        """Mark the start of a turn (the prompt line already shows the user's text)."""
        self._turn_start = time.time()
        self._printed_texts.clear()
        self._console.print()

    def add_event(self, event: Event) -> None:
        """Print an event inline with label and color using Rich Text (ASCII-safe).

        Skips v3 streaming events already rendered via direct hooks, and
        avoids interrupting a live token stream except for terminal events.
        """
        if event.type in _DIRECT_RENDERED_EVENT_TYPES:
            return
        if self._stream_active and event.type not in _STREAMING_SAFE_EVENT_TYPES:
            return

        self.on_assistant_end()
        color = self._get_color(event)
        label = self._get_label(event)
        details = event.details or event.type.value
        text = Text()
        text.append("  ", style="")
        text.append(label, style=f"bold {color}")
        text.append(f"  {details}", style=color)
        self._console.print(text)

    # ------------------------------------------------------------------
    # Streaming-style rendering (Claude-Code-like)
    # ------------------------------------------------------------------

    def on_assistant_token(self, token: str) -> None:
        """Append a token from the LLM's current assistant message, no newline."""
        if not token:
            return
        if not self._assistant_buffer:
            self._assistant_buffer = ""
            self._suppress_live_stream = False
        self._assistant_buffer += token

        if self._should_suppress_live_stream(self._assistant_buffer):
            self._suppress_live_stream = True
            return

        if not self._stream_active and self._should_start_live_stream(
            self._assistant_buffer, token
        ):
            self._print_assistant_header()
            self._console.file.write(self._assistant_buffer)
            self._console.file.flush()
            self._stream_active = True
            self._stream_chars = len(self._assistant_buffer)
            return

        if self._stream_active:
            self._console.file.write(token)
            self._console.file.flush()
            self._stream_chars += len(token)

    def on_assistant_end(self, render_panel: bool = False) -> None:
        """Finalize the in-flight assistant text block."""
        content = self._assistant_buffer.strip()
        if self._stream_active:
            self._console.file.write("\n")
            self._console.file.flush()
            self._stream_active = False
            self._stream_chars = 0
        elif content and not render_panel:
            self._print_assistant_header()
            self._console.print(f"  {content}", markup=False)

        if render_panel and content:
            self._console.print(
                Panel(
                    Markdown(content),
                    title="[bold cyan]Final response[/]",
                    title_align="left",
                    border_style="cyan",
                    padding=(0, 1),
                )
            )

        if content:
            self._printed_texts.add(self._dedup_key(content))
        self._assistant_buffer = ""
        self._suppress_live_stream = False

    def show_assistant_text(self, text: str) -> None:
        """Print an assistant thinking/narration block between tool calls.

        Deduplicated against text already streamed token-by-token.
        """
        content = (text or "").strip()
        if not content:
            return
        key = self._dedup_key(content)
        if key in self._printed_texts:
            return
        self.on_assistant_end()
        self._printed_texts.add(key)
        self._print_assistant_header(inline=False)
        self._console.print(Markdown(content))

    def on_tool_call(self, name: str, args: dict | None = None) -> None:
        """Render a tool-call panel with name + JSON arguments.

        ``write_todos`` gets a special progress display with timer and icons.
        """
        self.on_assistant_end()

        if name == "write_todos" and args:
            self._render_write_todos(args)
            return

        try:
            args_str = _json.dumps(
                self._compact_tool_args(args or {}),
                indent=2,
                ensure_ascii=False,
            )
        except (TypeError, ValueError):
            args_str = str(args)
        body = Syntax(
            args_str,
            "json",
            theme="ansi_dark",
            line_numbers=False,
            word_wrap=True,
            background_color="default",
        )
        self._console.print(
            Panel(
                body,
                title=f"[bold yellow]⚙  {name}[/]",
                title_align="left",
                border_style="yellow",
                padding=(0, 1),
            )
        )

    def on_tool_result(
        self, name: str, content: str, success: bool = True, max_chars: int = 600
    ) -> None:
        """Render a tool-result panel; truncates long output with a hint.

        Skips ``write_todos`` — its progress panel already shows the state.
        """
        if name == "write_todos":
            return
        self.on_assistant_end()
        text = "" if content is None else str(content)
        truncated_n = 0
        if len(text) > max_chars:
            truncated_n = len(text) - max_chars
            text = text[:max_chars].rstrip() + f"\n… [{truncated_n} more chars hidden]"
        color = "green" if success else "red"
        title = f"[bold {color}]↳ {name}[/]"
        if truncated_n:
            title += "  [dim](truncated)[/]"
        self._console.print(
            Panel(
                text or "[dim](empty)[/]",
                title=title,
                title_align="left",
                border_style=color,
                padding=(0, 1),
            )
        )

    def end_turn(self, success: bool = True) -> None:
        """Print elapsed time at end of turn."""
        self.on_assistant_end(render_panel=success)
        if self._turn_start:
            elapsed = time.time() - self._turn_start
            label = "OK" if success else "FAIL"
            color = "green" if success else "red"
            text = Text()
            text.append("  ", style="")
            text.append(label, style=f"bold {color}")
            text.append(f"  Done in {elapsed:.1f}s", style=color)
            self._console.print(text)
            self._turn_start = None

    def show_help(self) -> None:
        """Display available slash commands."""
        self._console.print()
        self._console.print(
            Panel(
                "[bold cyan]/model[/]     Switch AI model\n"
                "[bold cyan]/agent-model[/] Set per-agent model overrides\n"
                "[bold cyan]/skills[/]    List, view, or activate skills\n"
                "[bold cyan]/quit[/]      Exit chat session\n"
                "[bold cyan]/help[/]      Show this help\n"
                "[bold cyan]/clear[/]     Clear the screen\n"
                "[bold cyan]/sessions[/]  List saved sessions\n"
                "[bold cyan]/history[/]   Show turn history for this chat session\n"
                "[bold cyan]/plan[/]      Toggle plan-only mode\n",
                border_style="cyan",
                padding=(1, 2),
                title="[bold]Commands[/]",
            )
        )
        self._console.print()

    def show_model_switched(self, new_model: str) -> None:
        """Show model switch confirmation."""
        self._current_model = new_model
        text = Text()
        text.append("  MODEL ", style="bold cyan")
        text.append(f"Switched to: {new_model}", style="dim")
        self._console.print(text)

    def set_model(self, model_name: str) -> None:
        """Update the current model name."""
        self._current_model = model_name

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dedup_key(text: str) -> str:
        """Normalize whitespace so streamed and complete messages compare equal."""
        return " ".join(text.split())

    def _get_label(self, event: Event) -> str:
        if event.type in (
            EventType.RESEARCH_STARTED,
            EventType.EVIDENCE_CAPTURED,
            EventType.TASK_UPDATED,
            EventType.SELF_REVIEW_STARTED,
            EventType.SELF_REVIEW_COMPLETED,
            EventType.MILESTONE_REACHED,
        ):
            return "INFO" if event.status == "done" else "-"
        if event.status == "done":
            return "FAIL" if event.type == EventType.FAILED else "OK"
        if event.status == "failed":
            return "FAIL"
        return "-"

    @staticmethod
    def _get_color(event: Event) -> str:
        if event.status == "done":
            return "green"
        if event.status == "failed":
            return "red"
        if event.status in ("in_progress", "started"):
            return "yellow"
        return "white"

    def _render_write_todos(self, args: dict) -> None:
        """Render ``write_todos`` as a rich progress panel.

        Shows each todo with a status icon (⏳/✓/○), an "In progress…" label
        for the active item, and an elapsed timer (m:ss) since the turn began.
        """
        todos = args.get("todos", [])
        now = time.time()
        elapsed = int(now - self._turn_start) if self._turn_start else 0
        mins, secs = divmod(elapsed, 60)
        timer_str = f"[{mins}m {secs}s]" if mins else f"[{secs}s]"

        lines: list[str] = []
        active_found = False
        for todo in todos:
            # content may be nested inside compacted form
            content = todo.get("content")
            if not isinstance(content, str) or not content:
                content = todo.get("content_summary", "?")
            status = todo.get("status", "pending")

            idx = content  # use content as identity key
            if status == "completed":
                icon = "✓"
                style = "green"
                # report elapsed time for freshly-completed items
                extra = ""
                if idx in self._todo_timers:
                    dt = int(now - self._todo_timers.pop(idx))
                    dm, ds = divmod(dt, 60)
                    extra = f"  [dim](in {dm}m {ds}s)[/]" if dm else f"  [dim](in {ds}s)[/]"
                lines.append(f"  [{style}]{icon}[/] [green]{content}[/]{extra}")
            elif status == "in_progress":
                icon = "◌"
                style = "bold yellow"
                active_found = True
                if idx not in self._todo_timers:
                    self._todo_timers[idx] = now
                lines.append(f"  [{style}]{icon}[/] [bold yellow]{content}[/]")
            else:  # pending
                icon = "○"
                style = "dim"
                lines.append(f"  [{style}]{icon}[/] [dim]{content}[/]")

        # Build header
        header = "[bold cyan]◷  Progress[/]"
        if active_found:
            header += "  [bold yellow]In progress…[/]"
        header += f"  [dim]{timer_str}[/]"

        body = "\n".join(lines) if lines else "[dim]No tasks[/]"
        self._console.print(
            Panel(
                body,
                title=header,
                title_align="left",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    def _compact_tool_args(self, value: object) -> object:
        """Hide large blobs like file contents from tool-call panels."""
        if isinstance(value, dict):
            compacted: dict[str, object] = {}
            for key, item in value.items():
                if isinstance(item, str) and key in {
                    "content", "old_text", "new_text", "patch_text",
                    "old_string", "new_string",
                }:
                    compacted[f"{key}_summary"] = self._string_summary(item)
                else:
                    compacted[key] = self._compact_tool_args(item)
            return compacted
        if isinstance(value, list):
            return [self._compact_tool_args(item) for item in value[:10]]
        if isinstance(value, str):
            return self._compact_string(value)
        return value

    @staticmethod
    def _compact_string(value: str, max_inline: int = 140) -> str:
        if len(value) <= max_inline and "\n" not in value:
            return value
        preview = value[:80].replace("\n", "\\n")
        suffix = "..." if len(value) > 80 else ""
        return f"<{len(value)} chars hidden: {preview}{suffix}>"

    @staticmethod
    def _string_summary(value: str) -> str:
        lines = value.count("\n") + 1
        return f"{len(value)} chars hidden across {lines} line(s)"

    def _print_assistant_header(self, inline: bool = True) -> None:
        self._console.print()
        header = Text()
        header.append("  ● ", style="bold cyan")
        header.append("Assistant", style="bold")
        self._console.print(header)
        if inline:
            self._console.file.write("  ")

    def _should_start_live_stream(self, buffer: str, latest_token: str) -> bool:
        stripped = buffer.strip()
        if not stripped or self._suppress_live_stream:
            return False
        return len(stripped) >= 36 or latest_token.endswith((".", "!", "?", ":"))

    @staticmethod
    def _should_suppress_live_stream(buffer: str) -> bool:
        stripped = buffer.strip()
        if not stripped:
            return False
        markdown_indicators = ("\n- ", "\n* ", "\n1. ", "```", "\n#", "|---")
        return any(marker in stripped for marker in markdown_indicators)
