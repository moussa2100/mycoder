"""Tests for the observability module."""

from datetime import datetime, timezone

import pytest

from pgimcode.context import ContextManager
from pgimcode.events import Event, EventType
from pgimcode.observability import (
    FailureSnapshot,
    MetricsCollector,
    SessionMetrics,
    StepMetric,
    TraceRecorder,
)
from pgimcode.session import Session


# ------------------------------------------------------------------
# MetricsCollector
# ------------------------------------------------------------------

def test_metrics_collector_records_event():
    """MetricsCollector.record() populates step metric fields correctly."""
    collector = MetricsCollector(session_id="ses-test", task="test task")
    collector.start()

    event = Event(
        session_id="ses-test",
        type=EventType.FILE_READING,
        step=1,
        status="done",
        details="read main.py (500 chars)",
    )
    collector.record(event, duration_ms=42.5)

    assert len(collector._step_metrics) == 1
    sm = collector._step_metrics[0]
    assert sm.step == 1
    assert sm.event_type == "file_reading"
    assert sm.duration_ms == 42.5
    assert sm.status == "done"
    assert sm.token_estimate == len("read main.py (500 chars)") // 4


def test_metrics_collector_finish():
    """start/record/finish produces a SessionMetrics with correct totals."""
    collector = MetricsCollector(session_id="ses-finish", task="finish test")
    collector.start()

    for i in range(3):
        event = Event(
            session_id="ses-finish",
            type=EventType.PLAN_GENERATED,
            step=i + 1,
            status="done",
            details="x" * 400,  # 100 tokens
        )
        collector.record(event, duration_ms=10.0 * (i + 1))

    metrics = collector.finish()

    assert metrics.session_id == "ses-finish"
    assert metrics.task == "finish test"
    assert metrics.total_steps == 3
    assert metrics.total_duration_ms >= 0.0
    assert metrics.token_estimate == 300  # 3 × 100
    assert metrics.cost_estimate_usd == pytest.approx(300 * SessionMetrics.COST_PER_TOKEN)
    assert metrics.started_at != ""
    assert metrics.ended_at is not None
    assert len(metrics.step_metrics) == 3


def test_metrics_collector_counts():
    """MetricsCollector tracks approval, compaction, and retry counts."""
    collector = MetricsCollector(session_id="ses-counts", task="counts test")
    collector.start()

    # Approval event
    collector.record(
        Event(
            session_id="ses-counts",
            type=EventType.BLOCKED_FOR_APPROVAL,
            step=1,
            status="blocked",
            details="waiting for user",
        ),
        duration_ms=5.0,
    )

    # Compaction event
    collector.record(
        Event(
            session_id="ses-counts",
            type=EventType.CONTEXT_COMPACTED,
            step=2,
            status="done",
            details="compacted 10 events",
        ),
        duration_ms=3.0,
    )

    # Retry events (details contains "retry")
    collector.record(
        Event(
            session_id="ses-counts",
            type=EventType.PATCH_APPLYING,
            step=3,
            status="retry",
            details="patch retry attempt 1",
        ),
        duration_ms=20.0,
    )
    collector.record(
        Event(
            session_id="ses-counts",
            type=EventType.PATCH_APPLYING,
            step=4,
            status="retry",
            details="retry: applying patch",
        ),
        duration_ms=25.0,
    )

    metrics = collector.finish()

    assert metrics.approval_count == 1
    assert metrics.compaction_count == 1
    assert metrics.retry_count == 2


# ------------------------------------------------------------------
# TraceRecorder
# ------------------------------------------------------------------

def test_trace_recorder_appends():
    """TraceRecorder stores segments in memory when no output_path is given."""
    recorder = TraceRecorder(session_id="ses-trace")

    event1 = Event(
        session_id="ses-trace",
        type=EventType.SESSION_STARTED,
        step=1,
        status="started",
        details="begin",
    )
    event2 = Event(
        session_id="ses-trace",
        type=EventType.PLAN_GENERATED,
        step=2,
        status="done",
        details="plan ready",
    )

    recorder.record(event1, duration_ms=1.5)
    recorder.record(event2, duration_ms=8.0)

    assert len(recorder._segments) == 2
    assert recorder._segments[0]["type"] == "session_started"
    assert recorder._segments[0]["duration_ms"] == 1.5
    assert recorder._segments[1]["type"] == "plan_generated"
    assert recorder._segments[1]["duration_ms"] == 8.0


def test_trace_recorder_writes_jsonl(tmp_path):
    """TraceRecorder appends valid JSONL lines when output_path is set."""
    jsonl_path = tmp_path / "trace.jsonl"
    recorder = TraceRecorder(session_id="ses-jsonl", output_path=jsonl_path)

    event = Event(
        session_id="ses-jsonl",
        type=EventType.PATCH_APPLYING,
        step=1,
        status="done",
        details="applied diff",
    )
    recorder.record(event, duration_ms=12.3)

    lines = jsonl_path.read_text().strip().split("\n")
    assert len(lines) == 1

    import json
    parsed = json.loads(lines[0])
    assert parsed["session_id"] == "ses-jsonl"
    assert parsed["step"] == 1
    assert parsed["type"] == "patch_applying"
    assert parsed["duration_ms"] == 12.3
    assert "timestamp" in parsed


# ------------------------------------------------------------------
# FailureSnapshot
# ------------------------------------------------------------------

def test_failure_snapshot_capture():
    """FailureSnapshot.capture() returns a dict with expected structure."""
    session = Session(id="ses-fail", task="fix bug", mode="build", status="failed")
    ctx_mgr = ContextManager(session_id="ses-fail")
    ctx_mgr.pin("keep this", "important", step=1)

    last_event = Event(
        session_id="ses-fail",
        type=EventType.FAILED,
        step=3,
        status="failed",
        details="assertion error in test",
    )

    snapshot = FailureSnapshot.capture(session, ctx_mgr, last_event)

    assert snapshot["session_id"] == "ses-fail"
    assert snapshot["task"] == "fix bug"
    assert snapshot["status"] == "failed"
    assert snapshot["last_event"]["type"] == "failed"
    assert snapshot["last_event"]["step"] == 3
    assert snapshot["context"]["session_id"] == "ses-fail"
    assert "pinned" in snapshot["context"]
    assert "timestamp" in snapshot


# ------------------------------------------------------------------
# EventBus integration
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_bus_with_metrics_collector():
    """EventBus publishes events to MetricsCollector via publish()."""
    collector = MetricsCollector(session_id="ses-bus", task="bus test")
    collector.start()

    from pgimcode.events import EventBus
    bus = EventBus(metrics_collector=collector)

    event = Event(
        session_id="ses-bus",
        type=EventType.TESTS_RUNNING,
        step=1,
        status="done",
        details="all tests passed",
    )
    await bus.publish(event)

    metrics = collector.finish()
    assert metrics.total_steps == 1
    assert metrics.tool_counts.get("tests_running") == 1
    assert metrics.step_metrics[0].event_type == "tests_running"


# ------------------------------------------------------------------
# SessionMetrics
# ------------------------------------------------------------------

def test_session_metrics_to_markdown():
    """SessionMetrics.to_markdown() renders markdown tables with correct values."""
    metrics = SessionMetrics(
        session_id="ses-md",
        task="build feature X",
        started_at="2024-01-01T10:00:00+00:00",
        ended_at="2024-01-01T10:05:00+00:00",
        total_duration_ms=300000.0,
        total_steps=2,
        step_metrics=[
            StepMetric(
                step=1,
                event_type="planning_started",
                started_at=0.0,
                ended_at=1.0,
                duration_ms=1000.0,
                token_estimate=500,
                status="done",
            ),
            StepMetric(
                step=2,
                event_type="completed",
                started_at=1.0,
                ended_at=2.0,
                duration_ms=1000.0,
                token_estimate=300,
                status="done",
            ),
        ],
        token_estimate=800,
        cost_estimate_usd=0.008,
        tool_counts={"planning_started": 1, "completed": 1},
        retry_count=0,
        approval_count=1,
        compaction_count=2,
        failure_reason=None,
    )

    md = metrics.to_markdown()

    assert "# Session Metrics: build feature X" in md
    assert "`ses-md`" in md
    assert "| Total Steps | 2 |" in md
    assert "| Total Duration | 300000.0 ms |" in md
    assert "| Token Estimate | 800 |" in md
    assert "| Cost Estimate | $0.008000 |" in md
    assert "| Retry Count | 0 |" in md
    assert "| Approval Count | 1 |" in md
    assert "| Compaction Count | 2 |" in md
    assert "| planning_started | 1 |" in md
    assert "| completed | 1 |" in md
    assert "| 1 | planning_started | done | 1000.0 | 500 |" in md
    assert "| 2 | completed | done | 1000.0 | 300 |" in md