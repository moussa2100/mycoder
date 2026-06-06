"""Context management: active window, summarization, pinning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pgimcode.events import Event, EventType


@dataclass
class ContextSummary:
    events_count: int
    event_types: str
    key_outcomes: str
    last_step: int
    compacted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class PinnedItem:
    text: str
    reason: str
    step: int
    pinned_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ContextManager:
    """Manages context tiers: active events, summaries, pinned items."""

    DEFAULT_MAX_ACTIVE = 10
    DEFAULT_BUDGET = 3000

    def __init__(self, session_id: str, budget: int = DEFAULT_BUDGET, max_active: int = DEFAULT_MAX_ACTIVE):
        self.session_id = session_id
        self.budget = budget
        self.max_active = max_active
        self.active_events: list = []        # Tier 1
        self.summaries: list[ContextSummary] = []  # Tier 2
        self.pinned: list[PinnedItem] = []   # Items that survive compaction
        self.total_compactions = 0
        self._orig_event_count = 0           # Track total events received

    def add(self, event: 'Event') -> bool:
        """Add an event. Returns True if compaction was triggered."""
        self.active_events.append(event)
        self._orig_event_count += 1
        if len(self.active_events) > self.max_active:
            self.compact()
            return True
        return False

    def pin(self, text: str, reason: str, step: int = 0) -> None:
        """Manually pin an item so it survives compaction."""
        self.pinned.append(PinnedItem(text=text, reason=reason, step=step))

    def compact(self) -> None:
        """Move oldest active events into summaries, keeping last `max_active` in active."""
        keep = max(self.max_active // 2, 1)  # Keep at least 1
        if len(self.active_events) <= keep:
            return
        to_compact = self.active_events[:-keep]
        self._pin_critical(to_compact)
        summary = self._summarize(to_compact)
        self.summaries.append(summary)
        self.active_events = self.active_events[-keep:]
        self.total_compactions += 1

    def _pin_critical(self, events: list) -> None:
        """Auto-pin items that should never be compacted away."""
        from pgimcode.events import EventType
        for ev in events:
            if ev.type == EventType.BLOCKED_FOR_APPROVAL and ev.status == "blocked":
                self.pin(f"Approval blocked: {ev.details}", "critical", ev.step)
            elif ev.type == EventType.FAILED and ev.status not in ("denied",):
                self.pin(f"Failure: {ev.details}", "needs_followup", ev.step)
            elif ev.type == EventType.PATCH_APPLYING and ev.status != "cancelled":
                self.pin(f"Edited: {ev.details}", "active_file", ev.step)
            elif ev.type == EventType.PLAN_GENERATED:
                self.pin(f"Plan: {ev.details}", "plan", ev.step)

    def _summarize(self, events: list) -> ContextSummary:
        """Create a ContextSummary from a batch of events."""
        from collections import Counter
        counts = Counter(e.type.value for e in events)
        types_str = " | ".join(f"{k}({v})" for k, v in sorted(counts.items()))
        outcomes = [f"{e.type.value}={e.status}" for e in events if e.status in ("done", "failed", "denied", "approved")]
        last_step = events[-1].step if events else 0
        return ContextSummary(
            events_count=len(events),
            event_types=types_str,
            key_outcomes=" | ".join(outcomes[:5]),
            last_step=last_step,
        )

    def estimate_tokens(self) -> int:
        """Rough token count (words × 1.5)."""
        total = 0
        for ev in self.active_events:
            text = f"{ev.type.value} {ev.details or ''} {ev.status}"
            total += len(text.split()) * 2  # rough heuristic
        for s in self.summaries:
            total += len(s.key_outcomes.split()) * 2
        for p in self.pinned:
            total += len(p.text.split()) * 2
        return total

    def should_compact(self) -> bool:
        return len(self.active_events) > self.max_active or self.estimate_tokens() > self.budget

    def get_active_context(self) -> str:
        """Markdown summary for terminal display or prompt injection."""
        lines = [f"# Context (session: {self.session_id})"]
        lines.append(f"- Active events: {len(self.active_events)}")
        lines.append(f"- Summaries: {len(self.summaries)}")
        lines.append(f"- Pinned: {len(self.pinned)}")
        lines.append(f"- Compactions: {self.total_compactions}")
        lines.append(f"- Est. tokens: {self.estimate_tokens()}")
        lines.append("")

        if self.pinned:
            lines.append("## Pinned")
            for p in self.pinned[-5:]:
                lines.append(f"- {p.text}")
            lines.append("")

        if self.summaries:
            lines.append("## Summaries")
            for s in self.summaries[-5:]:
                lines.append(f"- Step {s.last_step}: {s.event_types} [{s.key_outcomes}]")
            lines.append("")

        if self.active_events:
            lines.append("## Recent Events")
            for ev in self.active_events[-5:]:
                lines.append(f"- [{ev.step}] {ev.type.value.upper()} ({ev.status})")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "budget": self.budget,
            "max_active": self.max_active,
            "total_compactions": self.total_compactions,
            "active_events_count": len(self.active_events),
            "summaries": [s.__dict__ for s in self.summaries],
            "pinned": [p.__dict__ for p in self.pinned],
        }