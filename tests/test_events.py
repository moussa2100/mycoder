"""Tests for the event system."""

import asyncio

import pytest

from pgimcode.events import Event, EventBus, EventType


@pytest.mark.asyncio
async def test_publish_single_event():
    bus = EventBus()
    received = []

    def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(handler)
    event = Event(
        session_id="ses-1",
        type=EventType.SESSION_STARTED,
        step=1,
        status="started",
        details="hello",
    )
    await bus.publish(event)

    assert len(received) == 1
    assert received[0].type == EventType.SESSION_STARTED


@pytest.mark.asyncio
async def test_event_log_writer(tmp_path):
    from pgimcode.events import EventLogWriter

    log_file = tmp_path / "test.jsonl"
    writer = EventLogWriter(log_file)

    event = Event(
        session_id="ses-1",
        type=EventType.REPO_SCANNING,
        step=2,
        status="in_progress",
        details="scanning...",
    )
    await writer.write(event)

    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 1
    assert "repo_scanning" in lines[0]