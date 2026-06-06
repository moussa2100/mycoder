"""Approval gate: permission levels, interactive prompts, audit trail."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from rich.console import Console

from pgimcode.events import Event, EventBus, EventType


class PermissionLevel(Enum):
    SAFE = "safe"
    CAUTION = "caution"
    DANGEROUS = "dangerous"


# Event type → permission level
ACTION_PERMISSIONS: dict[EventType, PermissionLevel] = {
    EventType.SESSION_STARTED: PermissionLevel.SAFE,
    EventType.REPO_SCANNING: PermissionLevel.SAFE,
    EventType.FILE_READING: PermissionLevel.SAFE,
    EventType.PLANNING_STARTED: PermissionLevel.SAFE,
    EventType.PLAN_GENERATED: PermissionLevel.SAFE,
    EventType.PATCH_APPLYING: PermissionLevel.CAUTION,
    EventType.TESTS_RUNNING: PermissionLevel.CAUTION,
    EventType.VERIFICATION_STARTED: PermissionLevel.SAFE,
    EventType.BLOCKED_FOR_APPROVAL: PermissionLevel.SAFE,
    EventType.COMPLETED: PermissionLevel.SAFE,
    EventType.FAILED: PermissionLevel.SAFE,
}


@dataclass
class ApprovalConfig:
    auto_approve_safe: bool = True
    auto_approve_caution: bool = False
    auto_approve_dangerous: bool = False
    default_answer: bool = False  # deny if non-interactive


@dataclass
class ApprovalRecord:
    action: str
    details: str
    level: str
    approved: bool
    timestamp: str


class ApprovalGate:
    """Manages approval for actions."""

    def __init__(
        self,
        config: ApprovalConfig,
        session_id: str,
        bus: EventBus,
        console: Console | None = None,
    ):
        self.config = config
        self.session_id = session_id
        self.bus = bus
        self.console = console or Console()
        self.records: list[ApprovalRecord] = []
        self.prompt_fn: Callable[[str, str], bool] | None = None

    def _needs_approval(self, event_type: EventType) -> bool:
        level = ACTION_PERMISSIONS.get(event_type, PermissionLevel.CAUTION)
        if level == PermissionLevel.SAFE:
            return False
        if level == PermissionLevel.CAUTION and self.config.auto_approve_caution:
            return False
        if level == PermissionLevel.DANGEROUS and self.config.auto_approve_dangerous:
            return False
        return True

    async def check(self, event_type: EventType, details: str) -> bool:
        if not self._needs_approval(event_type):
            return True

        level = ACTION_PERMISSIONS.get(event_type, PermissionLevel.CAUTION)

        # Emit blocked event
        await self.bus.publish(Event(
            session_id=self.session_id,
            type=EventType.BLOCKED_FOR_APPROVAL,
            status="blocked",
            details=f"Approval required: {event_type.value} — {details} [{level.value}]",
        ))

        # Prompt
        if self.prompt_fn:
            approved = self.prompt_fn(event_type.value, details)
        else:
            approved = self.config.default_answer

        self.records.append(ApprovalRecord(
            action=event_type.value,
            details=details,
            level=level.value,
            approved=approved,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

        if approved:
            await self.bus.publish(Event(
                session_id=self.session_id,
                type=EventType.BLOCKED_FOR_APPROVAL,
                status="approved",
                details=f"Approved: {event_type.value}",
            ))
        else:
            await self.bus.publish(Event(
                session_id=self.session_id,
                type=EventType.BLOCKED_FOR_APPROVAL,
                status="denied",
                details=f"Denied: {event_type.value}",
            ))

        return approved

    def to_dict(self) -> dict:
        return {
            "config": self.config.__dict__,
            "records": [r.__dict__ for r in self.records],
        }