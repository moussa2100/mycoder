"""Tests for the Rich terminal renderer."""

import pytest
from unittest.mock import MagicMock

from pgimcode.events import Event, EventType
from pgimcode.terminal import RichTerminalRenderer


def test_renderer_creates_without_crash():
    """Test that the renderer can be created without crashing."""
    renderer = RichTerminalRenderer(
        console=MagicMock(),
        session_id="test-session",
        task="test task",
        mode="build"
    )
    assert renderer is not None


def test_renderer_add_event_and_render():
    """Test that add_event and render don't raise exceptions."""
    renderer = RichTerminalRenderer(
        console=MagicMock(),
        session_id="test-session",
        task="test task",
        mode="build"
    )

    event = Event(
        session_id="test-session",
        type=EventType.SESSION_STARTED,
        step=1,
        status="started",
        details="Initialized build agent"
    )

    renderer.add_event(event)

    # render() should not raise
    layout = renderer.render()
    assert layout is not None


def test_summary_text_none_when_no_completed():
    """Test that _summary_text() returns None when no COMPLETED/FAILED event."""
    renderer = RichTerminalRenderer(
        console=MagicMock(),
        session_id="test-session",
        task="test task",
        mode="build"
    )

    # Add an event that's not COMPLETED or FAILED
    event = Event(
        session_id="test-session",
        type=EventType.SESSION_STARTED,
        step=1,
        status="done",
        details="Started session"
    )
    renderer.add_event(event)

    summary = renderer._summary_text()
    assert summary is None


def test_summary_text_has_content_when_completed():
    """Test that _summary_text() has content when COMPLETED is the last event."""
    renderer = RichTerminalRenderer(
        console=MagicMock(),
        session_id="test-session",
        task="test task",
        mode="build"
    )

    # Add COMPLETED event as the last one
    event = Event(
        session_id="test-session",
        type=EventType.COMPLETED,
        step=8,
        status="done",
        details="Task completed successfully"
    )
    renderer.add_event(event)

    summary = renderer._summary_text()
    assert summary is not None
    # Summary should contain task status and duration info
    summary_str = str(summary)
    assert "completed" in summary_str.lower() or "success" in summary_str.lower() or "test task" in summary_str