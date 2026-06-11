"""Protocol definition for the terminal renderer interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RendererProtocol(Protocol):
    """Protocol defining the interface expected by RealAgent for rendering.

    Any renderer passed to RealAgent must implement these methods.
    The ``@runtime_checkable`` decorator allows ``isinstance`` checks.
    """

    def add_event(self, event: object) -> None: ...
    def refresh(self) -> None: ...

    def on_assistant_token(self, text: str) -> None: ...
    def show_assistant_text(self, text: str) -> None: ...

    def on_tool_call(self, name: str, args: object) -> None: ...
    def on_tool_result(self, name: str, text: str, success: bool) -> None: ...

    def pause_live(self) -> None: ...
    def resume_live(self) -> None: ...
    def set_model(self, model_name: str) -> None: ...

    @property
    def _console(self) -> object: ...  # noqa: ANN001
