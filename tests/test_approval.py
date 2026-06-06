"""Tests for approval gate."""

import pytest

from pgimcode.approval import (
    ApprovalConfig, ApprovalGate, PermissionLevel, ACTION_PERMISSIONS, ApprovalRecord,
)
from pgimcode.events import EventBus, EventType


@pytest.mark.asyncio
async def test_safe_action_auto_approved():
    bus = EventBus()
    gate = ApprovalGate(ApprovalConfig(), "ses-1", bus)
    approved = await gate.check(EventType.REPO_SCANNING, "scanning...")
    assert approved is True
    assert len(gate.records) == 0


@pytest.mark.asyncio
async def test_caution_action_blocked():
    bus = EventBus()
    gate = ApprovalGate(ApprovalConfig(), "ses-1", bus)
    approved = await gate.check(EventType.PATCH_APPLYING, "edit src/api.py")
    assert approved is False  # default_answer = False
    assert len(gate.records) == 1
    assert gate.records[0].approved is False


@pytest.mark.asyncio
async def test_caution_auto_approve():
    bus = EventBus()
    gate = ApprovalGate(ApprovalConfig(auto_approve_caution=True), "ses-1", bus)
    approved = await gate.check(EventType.PATCH_APPLYING, "edit src/api.py")
    assert approved is True
    assert len(gate.records) == 0


@pytest.mark.asyncio
async def test_custom_prompt_fn():
    bus = EventBus()
    gate = ApprovalGate(ApprovalConfig(), "ses-1", bus)
    gate.prompt_fn = lambda action, details: True
    approved = await gate.check(EventType.PATCH_APPLYING, "edit")
    assert approved is True
    assert gate.records[0].approved is True


def test_approval_record():
    rec = ApprovalRecord(action="edit", details="src/foo.py", level="caution", approved=True, timestamp="2026-01-01T00:00:00")
    assert rec.approved is True


def test_action_permissions():
    assert ACTION_PERMISSIONS[EventType.REPO_SCANNING] == PermissionLevel.SAFE
    assert ACTION_PERMISSIONS[EventType.PATCH_APPLYING] == PermissionLevel.CAUTION