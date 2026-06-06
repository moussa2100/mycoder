"""Mock Agent for deterministic testing and demos."""

from __future__ import annotations

import asyncio

from pgimcode.approval import ApprovalGate
from pgimcode.config import Settings
from pgimcode.events import Event, EventBus, EventType
from pgimcode.session import _new_ulid


_STEPS = [
    (EventType.SESSION_STARTED, "Initialized build agent", None),
    (EventType.REPO_SCANNING, "Scanning workspace structure", {"files": ["src/api.py", "src/config.py", "tests/"]}),
    (EventType.FILE_READING, "Reading source files", {"files": ["src/api.py", "tests/test_api.py", "requirements.txt"]}),
    (EventType.PLANNING_STARTED, "Plan: add Redis cache layer to API", None),
    (EventType.PATCH_APPLYING, "Edit: src/api.py (+12, -3 lines)", None),
    (EventType.TESTS_RUNNING, "pytest tests/test_api.py", {"result": "3 passed, 0 failed"}),
    (EventType.VERIFICATION_STARTED, "All tests pass, no regressions", None),
    (EventType.COMPLETED, "Caching layer added successfully", None),
]


class MockAgent:
    """Deterministic mock agent for testing and demos."""

    def __init__(self, bus: EventBus, session_id: str, task: str, approval_gate: ApprovalGate | None = None, context_manager=None):
        self._bus = bus
        self._session_id = session_id
        self._task = task
        self.cancelled = False
        self._settings = Settings()
        self.approval_gate = approval_gate
        self.context_manager = context_manager

    async def run(self, delay: float | None = None) -> None:
        """Run through all steps, publishing events."""
        if delay is None:
            delay = self._settings.mock_delay_seconds

        for step_idx, (event_type, details, data) in enumerate(_STEPS):
            if self.cancelled:
                break

            # Check approval before emitting events for CAUTION+ actions
            if self.approval_gate and event_type in (EventType.PATCH_APPLYING, EventType.TESTS_RUNNING):
                approved = await self.approval_gate.check(event_type, details or "")
                if not approved:
                    # Emit failure and stop
                    await self._bus.publish(Event(
                        id=_new_ulid(),
                        session_id=self._session_id,
                        type=EventType.FAILED,
                        step=step_idx + 1,
                        status="done",
                        details=f"Approval denied for {event_type.value}",
                    ))
                    return

            step_num = step_idx + 1

            # For step 8 (COMPLETED), emit TWO events: one in_progress then one done
            if step_num == 8:
                # First event: in_progress
                event_in_progress = Event(
                    id=_new_ulid(),
                    session_id=self._session_id,
                    type=event_type,
                    step=step_num,
                    status="in_progress",
                    details=details,
                    data=data,
                )
                await self._bus.publish(event_in_progress)
                await asyncio.sleep(delay)

                if self.cancelled:
                    break

                # Second event: done (final state)
                event_done = Event(
                    id=_new_ulid(),
                    session_id=self._session_id,
                    type=event_type,
                    step=step_num,
                    status="done",
                    details=details,
                    data=data,
                )
                await self._bus.publish(event_done)
            else:
                # Regular step: emit with status="in_progress" only
                event = Event(
                    id=_new_ulid(),
                    session_id=self._session_id,
                    type=event_type,
                    step=step_num,
                    status="in_progress",
                    details=details,
                    data=data,
                )
                await self._bus.publish(event)

            # Add event to context manager and check for compaction
            if self.context_manager:
                did_compact = self.context_manager.add(event)
                if did_compact:
                    await self._bus.publish(Event(
                        session_id=self._session_id,
                        type=EventType.CONTEXT_COMPACTED,
                        step=step_num,
                        status="done",
                        details=f"Compacted to {len(self.context_manager.summaries)} summary blocks",
                    ))

            await asyncio.sleep(delay)

            if self.cancelled:
                break

    def cancel(self) -> None:
        """Set cancelled flag so loop exits early."""
        self.cancelled = True