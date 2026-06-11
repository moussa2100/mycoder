"""Interactive chat session — Claude Code-style terminal UI.

This module provides the interactive chat loop that powers the ``pgimcode chat``
command.  It reads user input via prompt_toolkit (with fuzzy slash-command
completion), dispatches slash commands, and routes coding tasks to the real
LLM agent (``RealAgent``) or the mock agent (``MockAgent``).

Rendering is delegated to :class:`ChatRenderer` (``chat_renderer.py``) so this
module stays focused on the chat *session* lifecycle.
"""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import FuzzyWordCompleter
from prompt_toolkit.shortcuts import CompleteStyle
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pgimcode.chat_renderer import ChatRenderer
from pgimcode.config import Settings
from pgimcode.events import Event, EventBus, EventType
from pgimcode.skills import SkillManager

if TYPE_CHECKING:
    from pgimcode.approval import ApprovalGate


# ---------------------------------------------------------------------------
# Pending-input drain helpers
#
# Terminals *without* bracketed-paste deliver a multiline paste as individual
# keystrokes — the first newline submits the prompt and the remaining lines
# stay buffered.  These helpers drain that buffer so the whole paste becomes
# ONE message instead of just the first line.
# ---------------------------------------------------------------------------

def _drain_pending_input(grace_seconds: float = 0.08) -> str:
    """Collect terminal input already buffered (the rest of a multiline paste).

    On Windows this delegates to ``msvcrt``; on POSIX it uses ``select``.
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

    return (
        b"".join(chunks)
        .decode("utf-8", errors="replace")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )


# ---------------------------------------------------------------------------
# ChatSession
# ---------------------------------------------------------------------------

class ChatSession:
    """Interactive chat session with multi-turn conversation, history,
    slash-command dispatch, and agent routing.
    """

    # Slash commands exposed in the prompt_toolkit completer.
    _COMMANDS: tuple[str, ...] = (
        "/help", "/h",
        "/model",
        "/agent-model",
        "/agent-model list",
        "/agent-model clear",
        "/quit", "/q",
        "/clear",
        "/sessions",
        "/plan",
        "/skills",
        "/skills list",
        "/skills view",
        "/skills use",
        "/skills deactivate",
    )

    def __init__(
        self,
        console: Console | None = None,
        settings: Settings | None = None,
        approval_gate: ApprovalGate | None = None,
        use_real: bool = False,
    ):
        self._console = console or Console()
        self._settings = settings or Settings()
        self._approval_gate = approval_gate
        self._use_real = use_real

        # Mutable session state — populated in start().
        self._session_id: str = ""
        self._running: bool = False
        self._context_manager = None
        self._renderer: ChatRenderer | None = None

        # Per-session accumulators.
        self._history: list[tuple[str, bool]] = []           # (task, success)
        self._recent_changed_files: list[str] = []
        self._active_skills: list[str] = []
        self._plan_only: bool = False

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    # ------------------------------------------------------------------
    # start() — main entry point
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the interactive chat loop.  Blocks until the user quits."""
        from pgimcode.context import ContextManager
        from pgimcode.session import SessionStore

        store = SessionStore()
        session = store.create(task="Chat session", mode="build")
        self._session_id = session.id

        self._context_manager = ContextManager(session_id=self._session_id)
        self._renderer = ChatRenderer(
            console=self._console,
            session_id=self._session_id,
            settings=self._settings,
        )
        self._renderer.show_welcome()

        bus = EventBus()
        self._wire_event_bus(bus)

        self._running = True

        prompt_session = self._build_prompt_session()
        is_tty = sys.stdin.isatty()

        while self._running:
            try:
                raw = await self._read_input(prompt_session, is_tty)
            except (EOFError, KeyboardInterrupt):
                break

            # Drain any extra lines (pastes on terminals without bracketed paste).
            extra = _drain_pending_input() if is_tty else ""
            if extra:
                for cont in extra.splitlines():
                    self._console.print(f"  [bold bright_white]>[/] {cont}")
                raw = f"{raw}\n{extra}"

            line = raw.strip()
            if not line:
                continue

            # Slash commands: single-line only.
            if line.startswith("/") and "\n" not in line:
                await self._handle_slash_command(line, store, bus)
                continue

            # Process as a coding / general task.
            self._renderer.start_turn(line)
            success = False
            try:
                success = await self._process_task(line, bus)
                self._history.append((line, success))
            except Exception as exc:
                self._console.print(f"  FAIL [red]Error: {exc}[/red]")

            self._renderer.end_turn(success)

        self._console.print()
        self._console.print("[dim]Goodbye![/]")

    # ------------------------------------------------------------------
    # Task processing
    # ------------------------------------------------------------------

    async def _process_task(self, task: str, bus: EventBus) -> bool:
        """Run *task* through the appropriate agent and return success."""
        from pgimcode.context import ContextManager
        from pgimcode.session import _new_ulid

        ctx = self._context_manager or ContextManager(session_id=self._session_id)
        ctx.pin(f"Task: {task}", "goal", 0)

        if self._use_real or self._has_valid_api_key():
            from pgimcode.agent import RealAgent

            agent = RealAgent(
                bus=bus,
                session_id=self._session_id,
                task=task,
                context_manager=ctx,
                mode="build",
                settings=self._settings,
                renderer=self._renderer,
                recent_files=list(self._recent_changed_files),
                conversation_history=list(self._history),
                active_skills=list(self._active_skills),
            )
            try:
                await agent.run()
                return True
            except Exception as exc:
                await bus.publish(Event(
                    id=_new_ulid(),
                    session_id=self._session_id,
                    type=EventType.FAILED,
                    step=0,
                    status="done",
                    details=f"Task failed: {exc}",
                ))
                return False

        # Fallback to MockAgent.
        from pgimcode.mock_agent import MockAgent

        if not self._is_coding_task(task):
            return await self._respond_conversational(task, bus)

        mock = MockAgent(
            bus=bus,
            session_id=self._session_id,
            task=task,
            approval_gate=self._approval_gate,
            context_manager=ctx,
            settings=self._settings,
        )
        try:
            await mock.run(delay=self._settings.mock_delay_seconds)
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

    async def _respond_conversational(self, task: str, bus: EventBus) -> bool:
        """Handle non-coding chat messages with a mock response."""
        import asyncio
        from pgimcode.session import _new_ulid

        task_lower = task.lower()

        if any(g in task_lower for g in ("hi", "hello", "hey", "yo")):
            msg = (
                "Hello! I'm pgimcode, your AI coding assistant. "
                "Try asking me to add a feature, fix a bug, or refactor code. "
                "Type /help for commands."
            )
        elif "what can you do" in task_lower or "help" in task_lower:
            msg = (
                "I can scan your repo, read files, edit code, run tests, and verify changes. "
                "Try: 'add error handling to auth.py' or 'fix the login bug'."
            )
        elif any(q in task_lower for q in ("who are you", "what are you")):
            msg = (
                f"I'm pgimcode v{self._settings.version}, a terminal AI coding agent. "
                "I use LLMs to help you code. Currently running in mock/demo mode."
            )
        elif "model" in task_lower:
            msg = f"Current model: {self._settings.model_name}. Use /model to switch."
        else:
            msg = (
                "I'm in mock mode — I don't have a real LLM connected yet. "
                "Try a coding task like 'add a caching layer' or 'fix the login bug' "
                "to see the demo pipeline. Use /model to switch models."
            )

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

    # ------------------------------------------------------------------
    # Slash-command dispatch
    # ------------------------------------------------------------------

    async def _handle_slash_command(
        self, line: str, store, bus: EventBus,
    ) -> None:
        """Dispatch a single-line slash command."""
        cmd = line.strip().lower()

        # -- simple commands --
        if cmd in ("/quit", "/q"):
            self._running = False
            return

        if cmd in ("/help", "/h"):
            self._renderer.show_help()
            return

        if cmd == "/clear":
            self._console.clear()
            return

        if cmd == "/model":
            from pgimcode.input_handler import ModelSelector

            new_model_id = ModelSelector.render_selection(
                self._console, self._settings.model_name,
            )
            if new_model_id and new_model_id != self._settings.model_name:
                ModelSelector.apply_model_selection(self._settings, new_model_id)
                self._renderer.show_model_switched(new_model_id)
                await bus.publish(Event(
                    session_id=self._session_id,
                    type=EventType.MODEL_SWITCHED,
                    step=0,
                    status="done",
                    details=f"Switched to: {new_model_id}",
                ))
            return

        if cmd == "/agent-model":
            from pgimcode.input_handler import ModelSelector

            selection = ModelSelector.render_agent_model_selection(
                self._console, self._settings,
            )
            if selection:
                agent_name, model_id = selection
                ModelSelector.apply_agent_model_selection(
                    self._settings, agent_name, model_id,
                )
                effective = model_id or self._settings.model_name
                self._console.print(
                    f"  [bold cyan]MODEL[/] {agent_name} agent -> {effective}",
                )
            return

        if cmd.startswith("/agent-model "):
            await self._handle_agent_model_command(line)
            return

        if cmd == "/sessions":
            table = Table(title="Sessions")
            table.add_column("ID", style="cyan")
            table.add_column("Task", style="white")
            table.add_column("Status", style="green")
            table.add_column("Created", style="dim")
            for s in store.list_sessions():
                created = s.created_at.strftime("%Y-%m-%d %H:%M")
                table.add_row(s.id, s.task, s.status, created)
            self._console.print(table)
            return

        if cmd == "/plan":
            self._plan_only = not self._plan_only
            state = "[green]ON[/]" if self._plan_only else "[dim]OFF[/]"
            self._console.print(f"  PLAN Plan-only mode: {state}")
            return

        if cmd.startswith("/skills"):
            await self._handle_skills_command(cmd)
            return

        # -- unknown --
        self._console.print(
            f"  [dim]Unknown command: {line}. Type /help for commands.[/]",
        )

    async def _handle_agent_model_command(self, line: str) -> None:
        """Handle ``/agent-model list|clear <agent>|<agent> <model>``."""
        from pgimcode.input_handler import ModelSelector

        parts = line.strip().split()
        action = parts[1].lower() if len(parts) > 1 else "list"

        if action in ("list", "show"):
            ModelSelector.render_agent_models(self._console, self._settings)
            return

        try:
            if action == "clear" and len(parts) == 3:
                agent_name = parts[2].lower()
                ModelSelector.apply_agent_model_selection(
                    self._settings, agent_name, None,
                )
                effective = self._settings.model_name
                self._console.print(
                    f"  [bold cyan]MODEL[/] {agent_name} agent -> {effective} (default)",
                )
                return

            if len(parts) == 3:
                agent_name = parts[1].lower()
                model_id = parts[2].lower()
                ModelSelector.apply_agent_model_selection(
                    self._settings, agent_name, model_id,
                )
                self._console.print(
                    f"  [bold cyan]MODEL[/] {agent_name} agent -> {model_id}",
                )
                return
        except ValueError as exc:
            self._console.print(f"  [red]{exc}[/red]")
            return

        self._console.print(
            "  [dim]Usage: /agent-model list | /agent-model <agent> <model> | "
            "/agent-model clear <agent>[/]",
        )

    async def _handle_skills_command(self, cmd: str) -> None:
        """Handle ``/skills list|view <name>|use <name>|deactivate [<name>]``."""
        manager = SkillManager()
        parts = cmd.split(maxsplit=2)
        subcmd = parts[1] if len(parts) > 1 else "list"

        if subcmd == "list":
            skills = manager.list_skills()
            if not skills:
                self._console.print("  [dim]No skills found in /skills/ directory.[/]")
                return

            table = Table(title="[bold cyan]Available Skills[/]", border_style="cyan")
            table.add_column("#", style="dim", justify="right", width=3)
            table.add_column("Name", style="bold")
            table.add_column("Category", style="dim")
            table.add_column("Description")
            table.add_column("Active", justify="center")

            for i, skill in enumerate(skills, 1):
                active_mark = "[green]YES[/]" if skill.name in self._active_skills else ""
                table.add_row(
                    str(i), skill.name, skill.category,
                    skill.description, active_mark,
                )
            self._console.print()
            self._console.print(table)
            self._console.print()
            self._console.print(
                "[dim]Use [bold]/skills use <name>[/] to activate a skill, "
                "[bold]/skills view <name>[/] to see its content, "
                "[bold]/skills deactivate <name>[/] to turn it off.[/]",
            )
            return

        if subcmd == "view" and len(parts) >= 3:
            from rich.markdown import Markdown

            skill_name = parts[2]
            content = manager.load_skill(skill_name)
            if content is None:
                self._console.print(f"  [red]Skill not found:[/] {skill_name}")
                return
            self._console.print()
            self._console.print(Panel(
                Markdown(content),
                title=f"[bold cyan]Skill: {skill_name}[/]",
                title_align="left",
                border_style="cyan",
                padding=(0, 1),
            ))
            return

        if subcmd == "use" and len(parts) >= 3:
            skill_name = parts[2]
            info = manager.get_skill(skill_name)
            if info is None:
                self._console.print(f"  [red]Skill not found:[/] {skill_name}")
                return
            if info.name not in self._active_skills:
                self._active_skills.append(info.name)
            self._console.print(f"  [green]Activated skill:[/] {info.name}")
            return

        if subcmd == "deactivate":
            if len(parts) >= 3:
                skill_name = parts[2]
                info = manager.get_skill(skill_name)
                if info is None:
                    self._console.print(f"  [red]Skill not found:[/] {skill_name}")
                    return
                if info.name in self._active_skills:
                    self._active_skills.remove(info.name)
                    self._console.print(f"  [yellow]Deactivated skill:[/] {info.name}")
                else:
                    self._console.print(f"  [dim]Skill '{info.name}' is not active.[/]")
            else:
                if self._active_skills:
                    self._active_skills.clear()
                    self._console.print("  [yellow]All skills deactivated.[/]")
                else:
                    self._console.print("  [dim]No skills are currently active.[/]")
            return

        self._console.print(
            "  [dim]Usage: /skills list | view <name> | use <name> | deactivate [<name>][/]",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _has_valid_api_key(self) -> bool:
        """Return True when at least one API key is configured (not a placeholder)."""
        for candidate in (
            self._settings.deepseek_api_key,
            self._settings.gemini_api_key,
        ):
            if candidate and not candidate.endswith("-here") and len(candidate) > 20:
                return True
        return False

    def _wire_event_bus(self, bus: EventBus) -> None:
        """Subscribe the renderer + context-manager to the event bus."""

        def _on_event(event: Event) -> None:
            self._renderer.add_event(event)
            if self._context_manager is not None:
                self._context_manager.add(event)

            snapshot = event.data or {}
            for path in snapshot.get("changed_files", [])[:8]:
                if path and path not in self._recent_changed_files:
                    self._recent_changed_files.append(path)
                    self._recent_changed_files = self._recent_changed_files[-12:]
                    if self._context_manager is not None:
                        self._context_manager.pin(
                            f"Recent changed file: {path}", "active_file", event.step,
                        )

        bus.subscribe(_on_event)

    @staticmethod
    def _is_coding_task(task: str) -> bool:
        """Heuristic: does *task* read like a code-change request?"""
        coding_keywords = {
            "add", "fix", "create", "implement", "change", "update",
            "remove", "delete", "refactor", "rewrite", "build", "write",
            "modify", "optimize", "debug", "patch", "edit", "rename",
            "extract", "move", "convert", "migrate", "upgrade", "setup",
            "configure", "install", "deploy", "test",
        }
        task_lower = task.lower()
        return any(kw in task_lower for kw in coding_keywords)

    @classmethod
    def _build_completer(cls) -> FuzzyWordCompleter:
        """Fuzzy completer for slash commands.

        Activates when the user types ``/`` — e.g. ``/mod`` → ``/model``.
        """
        return FuzzyWordCompleter(
            words=list(cls._COMMANDS),
            WORD=True,  # treat the whole input as one token
        )

    @staticmethod
    def _build_prompt_session() -> PromptSession | None:
        """Return a PromptSession if stdin is a TTY, else None."""
        if not sys.stdin.isatty():
            return None
        return PromptSession(
            completer=ChatSession._build_completer(),
            complete_style=CompleteStyle.MULTI_COLUMN,
        )

    @staticmethod
    async def _read_input(
        prompt_session: PromptSession | None, is_tty: bool,
    ) -> str:
        """Read one line of user input, falling back to plain ``input`` on pipes."""
        if prompt_session is not None:
            return await prompt_session.prompt_async([("bold", "  > ")])
        # Fallback for non-TTY (piped input, etc.).
        console = Console()
        return console.input("  [bold bright_white]>[/] ")
