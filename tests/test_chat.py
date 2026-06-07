"""Tests for chat-style rendering."""

from io import StringIO

from rich.console import Console

from pgimcode.chat import ChatRenderer


def test_chat_renderer_streams_and_renders_final_response_panel():
    """The renderer should stream tokens and then show a styled final response block."""
    output = StringIO()
    console = Console(file=output, force_terminal=False, color_system=None, width=100)
    renderer = ChatRenderer(console=console, session_id="session-1")

    renderer.start_turn("create index.html")
    renderer.on_assistant_token("Hello")
    renderer.on_assistant_token(" world")
    renderer.end_turn(success=True)

    text = output.getvalue()

    assert "Assistant" in text
    assert "Hello world" in text
    assert "Final response" in text
    assert "Done in" in text


def test_chat_renderer_shows_tool_call_and_truncated_tool_result():
    """Tool calls and long tool results should be visible in panels."""
    output = StringIO()
    console = Console(file=output, force_terminal=False, color_system=None, width=100)
    renderer = ChatRenderer(console=console, session_id="session-1")

    renderer.on_tool_call("write_file", {"path": "frontend/index.html"})
    renderer.on_tool_result("write_file", "x" * 700)

    text = output.getvalue()

    assert "write_file" in text
    assert "frontend/index.html" in text
    assert "more chars hidden" in text