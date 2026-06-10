"""Interactive chat session — Claude Code-style terminal UI."""

from __future__ import annotations

import asyncio
import sys
import time
from typing import TYPE_CHECKING

from prompt_toolkit import PromptSession
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.markdown import Markdown
from rich.syntax import Syntax

from pgimcode.config import Settings
from pgimcode.events import Event, EventBus, EventType
from pgimcode.memory.store import PersistentFileStore

if TYPE_CHECKING:
    from pgimcode.approval import ApprovalGate


_DIRECT_RENDERED_EVENT_TYPES = {
    EventType.COORDINATOR_MESSAGE,
    EventType.COORDINATOR_TOOL_CALL,
    EventType.COORDINATOR_TOOL_RESULT,
    EventType.SUBAGENT_MESSAGE,
    EventType.SUBAGENT_TOOL_CALL,
    EventType.SUBAGENT_TOOL_RESULT,
}


def _drain_pending_input(grace_seconds: float = 0.08) -> str:
    """Collect terminal input that is already buffered (the rest of a multiline paste).

    Terminals without bracketed-paste support deliver a paste as plain
    keystrokes: the first newline submits the prompt and the remaining lines
    stay in the console buffer. This drains them so the whole paste becomes
    ONE message instead of the first line only.
    """
    try:
        import msvcrt
    except ImportError:
        return _drain_pending_input_posix(grace_seconds)
    chars: list[str] = []
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        while msvcrt.kbhit():
            chars.append(msvcrt.getwch())
            deadline = time.monotonic() + grace_seconds
        time.sleep(0.005)
    return "".join(chars).replace("\r\n", "\n").replace("\r", "\n").strip()


def _drain_pending_input_posix(grace_seconds: float) -> str:
    import os
    import select

    chunks: list[bytes] = []
    fd = sys.stdin.fileno()
    while True:
        ready, _, _ = select.select([fd], [], [], grace_seconds)
        if not ready:
            break
        data = os.read(fd, 65536)
        if not data:
            break
        chunks.append(data)
    return b"".join(chunks).decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n").strip()


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

    def show_welcome(self) -> None:
        """Display welcome banner at chat start."""
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
        """Print an event inline with label and color using Rich Text (ASCII-safe)."""
        # v3 streaming events are already rendered through direct renderer hooks
        # (assistant text blocks and tool panels). Printing them here duplicates
        # the same content as raw yellow status lines.
        if event.type in _DIRECT_RENDERED_EVENT_TYPES:
            return
        # Don't interrupt a token stream with status lines.
        if self._stream_active and event.type not in (
            EventType.COMPLETED, EventType.FAILED
        ):
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

        if not self._stream_active and self._should_start_live_stream(self._assistant_buffer, token):
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
            self._console.print(f"  {content}")

        if render_panel and content:
            self._console.print(Panel(
                Markdown(content),
                title="[bold cyan]Final response[/]",
                title_align="left",
                border_style="cyan",
                padding=(0, 1),
            ))

        if content:
            self._printed_texts.add(self._dedup_key(content))
        self._assistant_buffer = ""
        self._suppress_live_stream = False

    def show_assistant_text(self, text: str) -> None:
        """Print an assistant thinking/narration block between tool calls.

        Deduplicated against text already streamed token-by-token, so the same
        message is never shown twice.
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

    @staticmethod
    def _dedup_key(text: str) -> str:
        """Normalize whitespace so streamed and complete messages compare equal."""
        return " ".join(text.split())

    def on_tool_call(self, name: str, args: dict | None = None) -> None:
        """Render a tool-call panel with name + JSON arguments."""
        self.on_assistant_end()
        import json
        try:
            args_str = json.dumps(self._compact_tool_args(args or {}), indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            args_str = str(args)
        body = Syntax(
            args_str, "json", theme="ansi_dark",
            line_numbers=False, word_wrap=True, background_color="default",
        )
        self._console.print(Panel(
            body,
            title=f"[bold yellow]⚙  {name}[/]",
            title_align="left",
            border_style="yellow",
            padding=(0, 1),
        ))

    def on_tool_result(
        self, name: str, content: str, success: bool = True, max_chars: int = 600
    ) -> None:
        """Render a tool-result panel; truncates long output with a hint."""
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
        self._console.print(Panel(
            text or "[dim](empty)[/]",
            title=title,
            title_align="left",
            border_style=color,
            padding=(0, 1),
        ))

    def _compact_tool_args(self, value):
        """Hide large blobs like file contents from tool-call panels."""
        if isinstance(value, dict):
            compacted = {}
            for key, item in value.items():
                if isinstance(item, str) and key in {"content", "old_text", "new_text", "patch_text", "old_string", "new_string"}:
                    compacted[f"{key}_summary"] = self._string_summary(item)
                else:
                    compacted[key] = self._compact_tool_args(item)
            return compacted
        if isinstance(value, list):
            return [self._compact_tool_args(item) for item in value[:10]]
        if isinstance(value, str):
            return self._compact_string(value)
        return value

    def _compact_string(self, value: str, max_inline: int = 140) -> str:
        if len(value) <= max_inline and "\n" not in value:
            return value
        preview = value[:80].replace("\n", "\\n")
        suffix = "..." if len(value) > 80 else ""
        return f"<{len(value)} chars hidden: {preview}{suffix}>"

    def _string_summary(self, value: str) -> str:
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

    def _should_suppress_live_stream(self, buffer: str) -> bool:
        stripped = buffer.strip()
        if not stripped:
            return False
        markdown_indicators = ("\n- ", "\n* ", "\n1. ", "```", "\n#", "|---")
        return any(marker in stripped for marker in markdown_indicators)

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
        help_panel = Panel(
            "[bold cyan]/model[/]     Switch AI model\n"
            "[bold cyan]/quit[/]      Exit chat session\n"
            "[bold cyan]/help[/]      Show this help\n"
            "[bold cyan]/clear[/]     Clear the screen\n"
            "[bold cyan]/sessions[/]  List saved sessions\n"
            "[bold cyan]/plan[/]      Toggle plan-only mode\n",
            border_style="cyan",
            padding=(1, 2),
            title="[bold]Commands[/]",
        )
        self._console.print(help_panel)
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

    def _get_label(self, event: Event) -> str:
        """Return a short label for the event type/status."""
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
            if event.type == EventType.COMPLETED:
                return "OK"
            elif event.type == EventType.FAILED:
                return "FAIL"
            return "OK"
        elif event.status == "failed":
            return "FAIL"
        elif event.status in ("in_progress", "started"):
            return "-"
        return "-"

    def _get_color(self, event: Event) -> str:
        if event.status == "done":
            return "green"
        elif event.status == "failed":
            return "red"
        elif event.status in ("in_progress", "started"):
            return "yellow"
        return "white"


class ChatSession:
    """Interactive chat session with multi-turn conversation."""

    def __init__(
        self,
        console: Console | None = None,
        settings: Settings | None = None,
        approval_gate: "ApprovalGate | None" = None,
        use_real: bool = False,
    ):
        self._console = console or Console()
        self._settings = settings or Settings()
        self._approval_gate = approval_gate
        self._session_id: str = ""
        self._history: list[tuple[str, bool]] = []  # (task, success)
        self._recent_changed_files: list[str] = []
        self._context_manager = None
        self._running = False
        self._plan_only = False
        self._use_real = use_real

    @property
    def session_id(self) -> str:
        return self._session_id

    async def start(self) -> None:
        """Start the interactive chat loop."""
        from pgimcode.session import SessionStore

        store = SessionStore()
        session = store.create(task="Chat session", mode="build")
        self._session_id = session.id
        from pgimcode.context import ContextManager

        self._context_manager = ContextManager(session_id=self._session_id)

        renderer = ChatRenderer(
            console=self._console,
            session_id=self._session_id,
            settings=self._settings,
        )

        renderer.show_welcome()

        bus = EventBus()

        def _on_event(event: Event) -> None:
            renderer.add_event(event)
            if self._context_manager is not None:
                self._context_manager.add(event)
            snapshot = event.data or {}
            for path in snapshot.get("changed_files", [])[:8]:
                if path and path not in self._recent_changed_files:
                    self._recent_changed_files.append(path)
                    self._recent_changed_files = self._recent_changed_files[-12:]
                    if self._context_manager is not None:
                        self._context_manager.pin(f"Recent changed file: {path}", "active_file", event.step)

        bus.subscribe(_on_event)

        self._running = True

        # prompt_toolkit session: bracketed paste keeps a multiline paste in
        # ONE buffer (only a real Enter submits), plus up-arrow input history.
        # Falls back to a plain prompt when stdin is not a terminal (pipes).
        is_tty = sys.stdin.isatty()
        prompt_session: PromptSession | None = PromptSession() if is_tty else None

        while self._running:
            try:
                if prompt_session is not None:
                    raw = await prompt_session.prompt_async([("bold", "  > ")])
                else:
                    raw = self._console.input("  [bold bright_white]>[/] ")
            except (EOFError, KeyboardInterrupt):
                break

            # Fallback for terminals without bracketed paste: a paste's first
            # newline submits the prompt and the rest stays buffered — drain
            # it and echo the extra lines so the full message is visible.
            extra = _drain_pending_input() if is_tty else ""
            if extra:
                for cont in extra.splitlines():
                    self._console.print(f"  [bold bright_white]>[/] {cont}")
                raw = f"{raw}\n{extra}"

            line = raw.strip()
            if not line:
                continue

            # Handle slash commands (single-line input only)
            if line.startswith("/") and "\n" not in line:
                await self._handle_slash_command(line.lower(), renderer, store, bus)
                continue

            # Process the task
            renderer.start_turn(line)

            success = False
            try:
                success = await self._process_task(line, bus, renderer)
                self._history.append((line, success))
            except Exception as e:
                self._console.print(f"  FAIL [red]Error: {e}[/red]")

            renderer.end_turn(success)

        # Clean exit
        self._console.print()
        self._console.print("[dim]Goodbye![/]")

    async def _handle_slash_command(
        self,
        line: str,
        renderer: ChatRenderer,
        store,
        bus: EventBus,
    ) -> None:
        """Handle /model, /quit, /help, /clear, /sessions, /plan commands."""
        cmd = line.strip().lower()

        if cmd == "/quit" or cmd == "/q":
            self._running = False

        elif cmd == "/help" or cmd == "/h":
            renderer.show_help()

        elif cmd == "/clear":
            self._console.clear()

        elif cmd == "/model":
            from pgimcode.input_handler import ModelSelector
            new_model_id = ModelSelector.render_selection(
                self._console, self._settings.model_name
            )
            if new_model_id and new_model_id != self._settings.model_name:
                ModelSelector.apply_model_selection(self._settings, new_model_id)
                renderer.show_model_switched(new_model_id)
                await bus.publish(Event(
                    session_id=self._session_id,
                    type=EventType.MODEL_SWITCHED,
                    step=0,
                    status="done",
                    details=f"Switched to: {new_model_id}",
                ))

        elif cmd == "/sessions":
            from rich.table import Table
            table = Table(title="Sessions")
            table.add_column("ID", style="cyan")
            table.add_column("Task", style="white")
            table.add_column("Status", style="green")
            table.add_column("Created", style="dim")
            for s in store.list_sessions():
                created = s.created_at.strftime("%Y-%m-%d %H:%M")
                table.add_row(s.id, s.task, s.status, created)
            self._console.print(table)

        elif cmd == "/plan":
            self._plan_only = not self._plan_only
            state = "[green]ON[/]" if self._plan_only else "[dim]OFF[/]"
            self._console.print(f"  PLAN Plan-only mode: {state}")

        else:
            self._console.print(f"  [dim]Unknown command: {line}. Type /help for commands.[/]")

    def _is_coding_task(self, task: str) -> bool:
        """Check if the task looks like a coding request."""
        coding_keywords = [
            "add", "fix", "create", "implement", "change", "update",
            "remove", "delete", "refactor", "rewrite", "build", "write",
            "modify", "optimize", "debug", "patch", "edit", "rename",
            "extract", "move", "convert", "migrate", "upgrade", "setup",
            "configure", "install", "deploy", "test",
        ]
        task_lower = task.lower()
        return any(kw in task_lower for kw in coding_keywords)

    async def _respond_conversational(self, task: str, bus: EventBus) -> bool:
        """Handle non-coding chat messages with a mock response."""
        from pgimcode.session import _new_ulid
        import asyncio

        task_lower = task.lower()

        if any(g in task_lower for g in ("hi", "hello", "hey", "yo")):
            msg = f"Hello! I'm pgimcode, your AI coding assistant. Try asking me to add a feature, fix a bug, or refactor code. Type /help for commands."
        elif "what can you do" in task_lower or "help" in task_lower:
            msg = "I can scan your repo, read files, edit code, run tests, and verify changes. Try: 'add error handling to auth.py' or 'fix the login bug'."
        elif any(q in task_lower for q in ("who are you", "what are you")):
            msg = f"I'm pgimcode v{self._settings.version}, a terminal AI coding agent. I use LLMs to help you code. Currently running in mock/demo mode."
        elif "model" in task_lower:
            msg = f"Current model: {self._settings.model_name}. Use /model to switch."
        else:
            msg = f"I'm in mock mode — I don't have a real LLM connected yet. Try a coding task like 'add a caching layer' or 'fix the login bug' to see the demo pipeline. Use /model to switch models."

        await bus.publish(Event(
            id=_new_ulid(),
            session_id=self._session_id,
            type=EventType.SESSION_STARTED,
            step=1,
            status="in_progress",
            details=msg,
        ))
        await asyncio.sleep(0.3)
        await bus.publish(Event(
            id=_new_ulid(),
            session_id=self._session_id,
            type=EventType.COMPLETED,
            step=2,
            status="done",
            details=msg,
        ))
        return True

    async def _process_task(
        self,
        task: str,
        bus: EventBus,
        renderer: ChatRenderer,
    ) -> bool:
        """Run the task through the agent and stream events."""
        from pgimcode.session import _new_ulid
        from pgimcode.context import ContextManager

        # Determine if we should use the real LLM agent
        can_use_real = self._use_real or (
            bool(self._settings.deepseek_api_key and not self._settings.deepseek_api_key.endswith("-here"))
            or bool(self._settings.openai_api_key and not self._settings.openai_api_key.endswith("-here"))
        )

        if can_use_real:
            from pgimcode.agent import RealAgent

            context_manager = self._context_manager or ContextManager(session_id=self._session_id)
            context_manager.pin(f"Task: {task}", "goal", 0)

            agent = RealAgent(
                bus=bus,
                session_id=self._session_id,
                task=task,
                context_manager=context_manager,
                mode="build",
                settings=self._settings,
                renderer=renderer,
                recent_files=list(self._recent_changed_files),
                conversation_history=list(self._history),
            )
            try:
                await agent.run()
                return True
            except Exception as e:
                await bus.publish(Event(
                    id=_new_ulid(),
                    session_id=self._session_id,
                    type=EventType.FAILED,
                    step=0,
                    status="done",
                    details=f"Task failed: {e}",
                ))
                return False

        # Fallback to MockAgent
        from pgimcode.mock_agent import MockAgent

        if not self._is_coding_task(task):
            return await self._respond_conversational(task, bus)

        context_manager = ContextManager(session_id=self._session_id)
        context_manager.pin(f"Task: {task}", "goal", 0)

        agent = MockAgent(
            bus=bus,
            session_id=self._session_id,
            task=task,
            approval_gate=self._approval_gate,
            context_manager=context_manager,
            settings=self._settings,
        )

        try:
            await agent.run(delay=self._settings.mock_delay_seconds)
            return True
        except Exception:
            await bus.publish(Event(
                id=_new_ulid(),
                session_id=self._session_id,
                type=EventType.FAILED,
                step=0,
                status="done",
                details="Task failed",
            ))
            return False
