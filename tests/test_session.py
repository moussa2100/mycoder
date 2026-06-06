"""Tests for session persistence."""

import json

import pytest

from pgimcode.session import Session, SessionStore


def test_create_session():
    store = SessionStore(tmp_root=None)
    session = store.create(task="add caching", mode="build")

    assert session.id.startswith("pgim-")
    assert session.task == "add caching"
    assert session.mode == "build"
    assert session.status == "running"
    assert session.step_count == 0


def test_save_and_load_session(tmp_path):
    store = SessionStore(tmp_root=tmp_path)
    session = store.create(task="fix bug", mode="plan")
    store.save(session)

    loaded = store.get(session.id)
    assert loaded.id == session.id
    assert loaded.task == "fix bug"


def test_list_sessions(tmp_path):
    store = SessionStore(tmp_root=tmp_path)
    s1 = store.create(task="a", mode="build")
    s2 = store.create(task="b", mode="plan")
    store.save(s1)
    store.save(s2)

    sessions = store.list_sessions()
    assert len(sessions) == 2
    assert {s.task for s in sessions} == {"a", "b"}


def test_jsonl_append(tmp_path):
    store = SessionStore(tmp_root=tmp_path)
    session = store.create(task="t", mode="build")
    store.save(session)

    from pgimcode.events import Event, EventType

    event = Event(session_id=session.id, type=EventType.FILE_READING, step=1)
    store.append_event(session.id, event)

    lines = (tmp_path / "sessions" / f"{session.id}.jsonl").read_text().strip().split("\n")
    assert len(lines) == 1
    assert "file_reading" in lines[0]