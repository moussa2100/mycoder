"""Tests for RealAgent (LangGraph-powered agent)."""

import asyncio
from types import SimpleNamespace

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


@pytest.mark.asyncio
async def test_real_agent_run_streaming_routes_tokens_and_tools():
    """Streaming path should route tokens, tool calls, and tool results to renderer."""

    class FakeRenderer:
        def __init__(self):
            self.tokens = []
            self.tool_calls = []
            self.tool_results = []

        def on_assistant_token(self, token):
            self.tokens.append(token)

        def on_tool_call(self, name, args):
            self.tool_calls.append((name, args))

        def on_tool_result(self, name, content, success=True, max_chars=600):
            self.tool_results.append((name, content, success))

    class FakeAgent:
        def __init__(self):
            self.stream_mode = None

        async def astream(self, initial, config, stream_mode=None):
            self.stream_mode = stream_mode
            yield ("messages", (SimpleNamespace(content="Hello"), {}))
            yield ("updates", {"tools": {"messages": [
                SimpleNamespace(tool_calls=[{"id": "1", "name": "write_file", "args": {"path": "a.txt"}}]),
                SimpleNamespace(role="tool", tool_call_id="1", name="write_file", content='{"message":"Created a.txt","success":true}'),
            ]}})

    renderer = FakeRenderer()
    agent = RealAgent(EventBus(), "test-session", "test task", renderer=renderer)
    fake = FakeAgent()

    await agent._run_streaming(fake, {}, {})

    assert fake.stream_mode == ["updates", "messages"]
    assert renderer.tokens == ["Hello"]
    assert renderer.tool_calls == [("write_file", {"path": "a.txt"})]
    assert renderer.tool_results == [("write_file", "Created a.txt", True)]


def test_real_agent_render_message_marks_failed_tool_results():
    """Tool result JSON with success=false should be rendered as failed."""

    class FakeRenderer:
        def __init__(self):
            self.tool_results = []

        def on_tool_result(self, name, content, success=True, max_chars=600):
            self.tool_results.append((name, content, success))

    renderer = FakeRenderer()
    agent = RealAgent(EventBus(), "test-session", "test task", renderer=renderer)
    message = SimpleNamespace(
        role="tool",
        tool_call_id="2",
        name="run_tests",
        content='{"message":"Tests failed","success":false}',
    )

    agent._render_message(message, set(), set())

    assert renderer.tool_results == [("run_tests", "Tests failed", False)]