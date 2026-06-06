"""Tests for the mock agent."""

import asyncio
import pytest

from pgimcode.events import EventBus, EventType
from pgimcode.mock_agent import MockAgent


@pytest.mark.asyncio
async def test_mock_agent_runs_all_steps():
    """Test that the mock agent runs all 8 steps and emits correct events."""
    bus = EventBus()
    events = []

    def collector(event):
        events.append(event)

    bus.subscribe(collector)

    agent = MockAgent(bus, session_id="test-session", task="test task")
    await agent.run(delay=0.05)

    # Should have 9 events (7 steps with in_progress + step 8 with in_progress + done)
    assert len(events) == 9

    # Check event types in order
    expected_types = [
        EventType.SESSION_STARTED,
        EventType.REPO_SCANNING,
        EventType.FILE_READING,
        EventType.PLANNING_STARTED,
        EventType.PATCH_APPLYING,
        EventType.TESTS_RUNNING,
        EventType.VERIFICATION_STARTED,
        EventType.COMPLETED,
    ]

    for i, expected_type in enumerate(expected_types):
        assert events[i].type == expected_type, f"Step {i+1}: expected {expected_type}, got {events[i].type}"

    # Last event should be COMPLETED
    assert events[-1].type == EventType.COMPLETED
    assert events[-1].status == "done"


@pytest.mark.asyncio
async def test_mock_agent_cancellation():
    """Test that the mock agent can be cancelled."""
    bus = EventBus()
    events = []

    def collector(event):
        events.append(event)

    bus.subscribe(collector)

    agent = MockAgent(bus, session_id="test-session", task="test task")

    # Start the agent in a task
    async def run_with_cancel():
        # Start the agent in background
        task = asyncio.create_task(agent.run(delay=2.0))
        # Give it a moment to start
        await asyncio.sleep(0.1)
        # Cancel it
        agent.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await run_with_cancel()

    # Should have at least one event before cancellation
    assert len(events) >= 1
    # The agent should have been cancelled before completing all steps
    assert len(events) < 8