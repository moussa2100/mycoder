"""Tests for context manager."""

import pytest

from pgimcode.events import Event, EventType
from pgimcode.context import ContextManager, ContextSummary, PinnedItem


def test_add_event():
    cm = ContextManager("ses-1")
    ev = Event(session_id="ses-1", type=EventType.SESSION_STARTED, step=1, status="started")
    triggered = cm.add(ev)
    assert len(cm.active_events) == 1
    assert triggered is False


def test_compact_triggered():
    cm = ContextManager("ses-1", max_active=3)
    for i in range(5):
        ev = Event(session_id="ses-1", type=EventType.SESSION_STARTED, step=i, status="started")
        cm.add(ev)
    assert len(cm.active_events) <= 3
    assert len(cm.summaries) == 1
    assert cm.total_compactions == 1


def test_pin_critical_items():
    cm = ContextManager("ses-1", max_active=2)
    cm.add(Event(session_id="ses-1", type=EventType.PLAN_GENERATED, step=1, status="done", details="plan"))
    cm.add(Event(session_id="ses-1", type=EventType.PATCH_APPLYING, step=2, status="done", details="edit"))
    cm.add(Event(session_id="ses-1", type=EventType.TESTS_RUNNING, step=3, status="done", details="test"))
    assert any("Plan" in p.text for p in cm.pinned)
    assert any("Edited" in p.text for p in cm.pinned)


def test_estimate_tokens():
    cm = ContextManager("ses-1")
    ev = Event(session_id="ses-1", type=EventType.SESSION_STARTED, step=1, status="started", details="hello world example")
    cm.add(ev)
    assert cm.estimate_tokens() > 0


def test_get_active_context():
    cm = ContextManager("ses-1")
    cm.add(Event(session_id="ses-1", type=EventType.SESSION_STARTED, step=1, status="started"))
    ctx = cm.get_active_context()
    assert "session: ses-1" in ctx
    assert "SESSION_STARTED" in ctx


def test_should_compact():
    cm = ContextManager("ses-1", max_active=5, budget=10)  # High max_active, low budget
    cm.add(Event(session_id="ses-1", type=EventType.SESSION_STARTED, step=1, status="started", details="x " * 10))  # Many words to exceed budget
    # Should not compact based on count (1 <= 5) but may exceed budget
    cm.add(Event(session_id="ses-1", type=EventType.REPO_SCANNING, step=2, status="started", details="y " * 10))
    # After adding more events that exceed budget, should_compact returns True
    assert cm.should_compact() or cm.total_compactions > 0