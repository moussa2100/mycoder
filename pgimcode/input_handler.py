"""Interactive slash-command input handler for the terminal agent."""

from __future__ import annotations

import queue
import sys
import threading
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pgimcode.config import AGENT_MODEL_FIELDS
from pgimcode.models import (
    AVAILABLE_MODELS,
    ModelProvider,
    get_default_model_for_provider,
    resolve_model_info,
)

if TYPE_CHECKING:
    from pgimcode.config import Settings
    from pgimcode.events import EventBus


class SlashCommandListener:
    """Background thread that reads stdin for slash commands (/model, etc.)."""

    def __init__(
        self,
        settings: "Settings",
        bus: "EventBus",
        console: Console,
        session_id: str,
    ):
        self._settings = settings
        self._bus = bus
        self._console = console
        self._session_id = session_id
        self._command_queue: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        """Start the background input listener thread."""
        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background listener."""
        self._running = False

    def _listen(self) -> None:
        """Read stdin lines and detect slash commands."""
        while self._running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                stripped = line.strip().lower()
                if stripped == "/model":
                    self._command_queue.put("model_switch")
            except (EOFError, OSError):
                break

    def pending_command(self) -> str | None:
        """Return the next pending command without blocking, or None."""
        try:
            return self._command_queue.get_nowait()
        except queue.Empty:
            return None

    def has_command(self) -> bool:
        """Check if there's a pending command."""
        return not self._command_queue.empty()


class ModelSelector:
    """Static methods for rendering and handling model selection UI."""

    @staticmethod
    def render_selection(console: Console, current_model_id: str) -> None:
        """Display the model selection table and handle user input.

        Returns the new model_id if selected, or None if cancelled.
        """
        console.print()
        console.print()

        table = Table(
            title="[bold cyan]Available Models[/]",
            border_style="cyan",
            show_lines=False,
            pad_edge=True,
        )
        table.add_column("#", style="dim", justify="right", width=3)
        table.add_column("Provider", style="bold")
        table.add_column("Model", style="cyan")
        table.add_column("Context", justify="right")
        table.add_column("Pricing", style="dim")
        table.add_column("Description")

        models = list(AVAILABLE_MODELS.values())
        current_provider = None

        for i, model in enumerate(models, 1):
            provider_label = ""
            if model.provider != current_provider:
                provider_label = model.provider.value.upper()
                current_provider = model.provider

            ctx_str = f"{model.context_window // 1000}K"
            cursor = ">" if model.id == current_model_id else " "

            table.add_row(
                f"{cursor}{i}",
                provider_label,
                model.name,
                ctx_str,
                model.pricing_note,
                model.description,
            )

        console.print(table)

        current_info = AVAILABLE_MODELS.get(current_model_id)
        current_name = current_info.name if current_info else current_model_id

        console.print()
        console.print(
            f"[dim]Current model:[/] [bold cyan]{current_name}[/] "
            f"[dim]({current_model_id})[/]"
        )
        console.print(
            "[dim]Enter number to switch, or press Enter / Esc to cancel[/]"
        )
        console.print()

        try:
            choice = console.input("[bold]Model #:[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            return None

        if not choice:
            return None

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                model = models[idx]
                return model.id
        except ValueError:
            pass

        return None

    @staticmethod
    def apply_model_selection(
        settings: "Settings",
        model_id: str,
    ) -> None:
        """Apply a model selection to settings in-place and persist it."""
        info = resolve_model_info(model_id)
        settings.model_name = model_id
        settings.api_provider = info.provider.value
        settings.api_base_url = info.api_base_url or None
        settings.save_model_choice()

    @staticmethod
    def render_agent_models(console: Console, settings: "Settings") -> None:
        """Display the current per-agent model overrides."""
        table = Table(
            title="[bold cyan]Agent Model Overrides[/]",
            border_style="cyan",
            show_lines=False,
        )
        table.add_column("Agent", style="bold")
        table.add_column("Model", style="cyan")
        table.add_column("Effective")

        for agent_name, field_name in AGENT_MODEL_FIELDS.items():
            override = getattr(settings, field_name)
            effective = override or settings.model_name
            table.add_row(agent_name, override or "[dim]default[/]", effective)

        console.print(table)

    @staticmethod
    def render_agent_model_selection(
        console: Console,
        settings: "Settings",
    ) -> tuple[str, str | None] | None:
        """Interactively choose an agent and model override."""
        console.print()
        ModelSelector.render_agent_models(console, settings)
        agents = list(AGENT_MODEL_FIELDS.keys())

        console.print()
        console.print("[dim]Choose agent number, or press Enter to cancel[/]")
        for index, agent_name in enumerate(agents, 1):
            console.print(f"  [cyan]{index}[/]. {agent_name}")

        try:
            agent_choice = console.input("[bold]Agent #:[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if not agent_choice:
            return None

        try:
            agent_name = agents[int(agent_choice) - 1]
        except (ValueError, IndexError):
            return None

        console.print("[dim]Choose model number, or 0 to use session default[/]")
        models = list(AVAILABLE_MODELS.values())
        for index, model in enumerate(models, 1):
            console.print(f"  [cyan]{index}[/]. {model.id} ({model.provider.value})")

        try:
            model_choice = console.input("[bold]Model #:[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if not model_choice:
            return None
        if model_choice == "0":
            return agent_name, None

        try:
            model_id = models[int(model_choice) - 1].id
        except (ValueError, IndexError):
            return None

        return agent_name, model_id

    @staticmethod
    def apply_agent_model_selection(
        settings: "Settings",
        agent_name: str,
        model_id: str | None,
    ) -> None:
        """Apply a model override for one sub-agent and persist it."""
        normalized_agent = agent_name.lower().strip()
        if normalized_agent not in AGENT_MODEL_FIELDS:
            valid = ", ".join(AGENT_MODEL_FIELDS)
            raise ValueError(f"Unknown agent '{agent_name}'. Available: {valid}")

        if model_id:
            resolve_model_info(model_id)

        setattr(settings, AGENT_MODEL_FIELDS[normalized_agent], model_id)
        settings.save_model_choice()
