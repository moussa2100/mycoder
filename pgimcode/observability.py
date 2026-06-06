"""Observability: metrics collection, trace recording, and failure snapshots."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pgimcode.events import Event, EventType


# ------------------------------------------------------------------
# Dataclasses
# ------------------------------------------------------------------

@dataclass
class StepMetric:
    step: int
    event_type: str
    started_at: float  # perf_counter value at event start
    ended_at: float   # perf_counter value at event end
    duration_ms: float
    token_estimate: int
    status: str


@dataclass
class SessionMetrics:
    session_id: str
    task: str
    started_at: str          # ISO-format datetime string
    ended_at: str | None     # ISO-format datetime string
    total_duration_ms: float
    total_steps: int
    step_metrics: list[StepMetric]
    token_estimate: int
    cost_estimate_usd: float
    tool_counts: dict[str, int]
    retry_count: int
    approval_count: int
    compaction_count: int
    failure_reason: str | None

    # Cost per token (GPT-4o rough rate)
    COST_PER_TOKEN = 0.00001

    def to_markdown(self) -> str:
        """Render metrics as a markdown summary with tables."""
        lines = [
            f"# Session Metrics: {self.task}",
            "",
            f"**Session ID**: `{self.session_id}`",
            f"**Started**: {self.started_at}",
            f"**Ended**: {self.ended_at or '(incomplete)'}",
            f"**Total Duration**: {self.total_duration_ms:.1f} ms",
            f"**Total Steps**: {self.total_steps}",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Steps | {self.total_steps} |",
            f"| Total Duration | {self.total_duration_ms:.1f} ms |",
            f"| Token Estimate | {self.token_estimate:,} |",
            f"| Cost Estimate | ${self.cost_estimate_usd:.6f} |",
            f"| Retry Count | {self.retry_count} |",
            f"| Approval Count | {self.approval_count} |",
            f"| Compaction Count | {self.compaction_count} |",
            f"| Failure Reason | {self.failure_reason or 'none'} |",
            "",
            "## Tool Counts",
            "",
        ]

        if self.tool_counts:
            lines.append("| Tool | Count |")
            lines.append("|------|-------|")
            for tool, count in sorted(self.tool_counts.items()):
                lines.append(f"| {tool} | {count} |")
            lines.append("")
        else:
            lines.append("_No tool events recorded._\n")

        lines.append("## Step Metrics")
        lines.append("")
        lines.append("| Step | Event | Status | Duration (ms) | Tokens |")
        lines.append("|------|-------|--------|---------------|--------|")
        for sm in self.step_metrics:
            lines.append(
                f"| {sm.step} | {sm.event_type} | {sm.status} | "
                f"{sm.duration_ms:.1f} | {sm.token_estimate:,} |"
            )
        lines.append("")

        return "\n".join(lines)


# ------------------------------------------------------------------
# MetricsCollector
# ------------------------------------------------------------------

class MetricsCollector:
    """Collects per-event and aggregate session metrics."""

    def __init__(self, session_id: str, task: str) -> None:
        self.session_id = session_id
        self.task = task
        self._started_at: float | None = None
        self._started_at_dt: datetime | None = None
        self._ended_at_dt: datetime | None = None
        self._step_metrics: list[StepMetric] = []
        self._total_token_estimate = 0
        self._tool_counts: dict[str, int] = {}
        self._retry_count = 0
        self._approval_count = 0
        self._compaction_count = 0
        self._failure_reason: str | None = None
        self._session_end: float | None = None

    def start(self) -> None:
        """Record the session start time."""
        self._started_at = time.perf_counter()
        self._started_at_dt = datetime.now(timezone.utc)

    def record(self, event: Event, duration_ms: float) -> None:
        """Record a single event's metrics."""
        now = time.perf_counter()

        token_estimate = self._estimate_tokens(event)
        self._total_token_estimate += token_estimate

        # Tool counts — track by EventType.value string
        event_type_value = event.type.value
        self._tool_counts[event_type_value] = self._tool_counts.get(event_type_value, 0) + 1

        # Approval count
        if event.type == EventType.BLOCKED_FOR_APPROVAL:
            self._approval_count += 1

        # Compaction count
        if event.type == EventType.CONTEXT_COMPACTED:
            self._compaction_count += 1

        # Retry count: details contains "retry" (case-insensitive) or data has a retry key
        if self._is_retry_event(event):
            self._retry_count += 1

        step_metric = StepMetric(
            step=event.step,
            event_type=event_type_value,
            started_at=now - (duration_ms / 1000.0),
            ended_at=now,
            duration_ms=duration_ms,
            token_estimate=token_estimate,
            status=event.status,
        )
        self._step_metrics.append(step_metric)

    def finish(self, failure_reason: str | None = None) -> SessionMetrics:
        """Finalize metrics and return a SessionMetrics instance."""
        self._session_end = time.perf_counter()
        self._ended_at_dt = datetime.now(timezone.utc)
        self._failure_reason = failure_reason

        total_duration_ms = 0.0
        if self._started_at is not None and self._session_end is not None:
            total_duration_ms = (self._session_end - self._started_at) * 1000

        return SessionMetrics(
            session_id=self.session_id,
            task=self.task,
            started_at=self._started_at_dt.isoformat() if self._started_at_dt else "",
            ended_at=self._ended_at_dt.isoformat() if self._ended_at_dt else None,
            total_duration_ms=total_duration_ms,
            total_steps=len(self._step_metrics),
            step_metrics=self._step_metrics,
            token_estimate=self._total_token_estimate,
            cost_estimate_usd=self._total_token_estimate * SessionMetrics.COST_PER_TOKEN,
            tool_counts=dict(self._tool_counts),
            retry_count=self._retry_count,
            approval_count=self._approval_count,
            compaction_count=self._compaction_count,
            failure_reason=failure_reason,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_tokens(event: Event) -> int:
        """Estimate token count from event details using char/4 ratio."""
        text = event.details or ""
        return len(text) // 4

    @staticmethod
    def _is_retry_event(event: Event) -> bool:
        """Return True if the event looks like a retry event."""
        details = event.details or ""
        if "retry" in details.lower():
            return True
        if event.data:
            for key in event.data:
                if "retry" in key.lower():
                    return True
        return False


# ------------------------------------------------------------------
# TraceRecorder
# ------------------------------------------------------------------

class TraceRecorder:
    """Records structured trace segments for replay and analysis."""

    def __init__(self, session_id: str, output_path: Path | None = None) -> None:
        self.session_id = session_id
        self.output_path = output_path
        self._segments: list[dict[str, Any]] = []
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: Event, duration_ms: float) -> None:
        """Append a trace segment. Writes JSONL immediately if output_path is set."""
        segment: dict[str, Any] = {
            "session_id": self.session_id,
            "step": event.step,
            "type": event.type.value,
            "status": event.status,
            "timestamp": event.timestamp.isoformat(),
            "duration_ms": duration_ms,
            "details": event.details,
        }
        self._segments.append(segment)

        if self.output_path:
            with self.output_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(segment) + "\n")


# ------------------------------------------------------------------
# FailureSnapshot
# ------------------------------------------------------------------

class FailureSnapshot:
    """Captures a point-in-time snapshot of failure state for post-mortem analysis."""

    @staticmethod
    def capture(
        session: Any,
        context_manager: Any,
        last_event: Event,
    ) -> dict[str, Any]:
        """
        Return a JSON-serializable dict containing:
        - session_id, task, status
        - last_event (as dict)
        - context (from context_manager.to_dict())
        - timestamp (ISO-format utcnow)
        """
        return {
            "session_id": session.id,
            "task": session.task,
            "status": session.status,
            "last_event": last_event.model_dump(mode="json"),
            "context": context_manager.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }