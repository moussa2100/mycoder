"""Tests for RealAgent (LangGraph-powered agent)."""

import asyncio
import pytest

from pgimcode.agent import RealAgent
from pgimcode.events import EventBus, EventType


@pytest.mark.asyncio
async def test_real_agent_runs():
    """Create EventBus, RealAgent, run it, verify events were published."""
    bus = EventBus()
    events = []

    def collector(event):
        events.append(event)

    bus.subscribe(collector)

    agent = RealAgent(bus, "test-session", "test task")
    await agent.run()

    assert len(events) > 0


@pytest.mark.asyncio
async def test_real_agent_publishes_events():
    """Run agent, verify at least 5 events on the bus, verify event types include SESSION_STARTED, REPO_SCANNING, etc."""
    bus = EventBus()
    events = []

    def collector(event):
        events.append(event)

    bus.subscribe(collector)

    agent = RealAgent(bus, "test-session-2", "another test task")
    await agent.run()

    assert len(events) >= 5

    event_types = {e.type for e in events}
    expected = {EventType.SESSION_STARTED, EventType.REPO_SCANNING}
    assert expected.issubset(event_types), (
        f"Expected events {expected} not all found in {event_types}"
    )


@pytest.mark.asyncio
async def test_real_agent_cancel():
    """Create agent, call cancel(), run it, verify FAILED event is published."""
    bus = EventBus()
    events = []

    def collector(event):
        events.append(event)

    bus.subscribe(collector)

    agent = RealAgent(bus, "test-session-3", "cancellable task")

    # Cancel before running
    agent.cancel()

    await agent.run()

    # Should have a FAILED event from cancellation
    failed_events = [e for e in events if e.type == EventType.FAILED]
    assert len(failed_events) >= 1
    assert "cancelled" in failed_events[0].details.lower()


def test_real_agent_interface_matches_mock():
    """Verify RealAgent has run() and cancel() methods."""
    bus = EventBus()
    agent = RealAgent(bus, "test-session", "test task")

    assert hasattr(agent, "run")
    assert callable(agent.run)
    assert hasattr(agent, "cancel")
    assert callable(agent.cancel)