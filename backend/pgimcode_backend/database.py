"""SQLite database layer for persisting tasks and chat messages."""

from __future__ import annotations

import aiosqlite
import json
from pathlib import Path
from typing import AsyncIterator

from .models import Task, TaskStatus, ChatMessage

DB_PATH = Path(__file__).parent.parent / "data" / "pgimcode.db"


def _dict_to_task(row: dict) -> Task:
    """Convert a database row dict to a Task model."""
    return Task(
        id=row["id"],
        title=row["title"],
        description=row.get("description", ""),
        status=TaskStatus(row.get("status", "planning")),
        model=row.get("model", "gemini-3.5-flash"),
        plan=row.get("plan", ""),
        plan_conversation=row.get("plan_conversation", ""),
        stream_response=row.get("stream_response", ""),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
        position=row.get("position", 0),
    )


def _dict_to_chat_message(row: dict) -> ChatMessage:
    """Convert a database row dict to a ChatMessage model."""
    return ChatMessage(
        id=row["id"],
        role=row["role"],
        content=row["content"],
        model=row.get("model", ""),
        created_at=row.get("created_at", ""),
    )


async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Get an async SQLite connection (dependency injection helper)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await _init_schema(db)
    try:
        yield db
    finally:
        await db.close()


async def _init_schema(db: aiosqlite.Connection) -> None:
    """Create tables if they don't exist."""
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'planning',
            model TEXT NOT NULL DEFAULT 'gemini-3.5-flash',
            plan TEXT NOT NULL DEFAULT '',
            plan_conversation TEXT NOT NULL DEFAULT '',
            stream_response TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            position INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            model TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_position ON tasks(position);
        CREATE INDEX IF NOT EXISTS idx_chat_created ON chat_messages(created_at);
    """)


# ── Task CRUD ───────────────────────────────────────────────

async def get_all_tasks(db: aiosqlite.Connection) -> list[Task]:
    cursor = await db.execute(
        "SELECT * FROM tasks ORDER BY status, position ASC"
    )
    rows = await cursor.fetchall()
    return [_dict_to_task(dict(r)) for r in rows]


async def get_tasks_by_status(db: aiosqlite.Connection, status: TaskStatus) -> list[Task]:
    cursor = await db.execute(
        "SELECT * FROM tasks WHERE status = ? ORDER BY position ASC",
        (status.value,),
    )
    rows = await cursor.fetchall()
    return [_dict_to_task(dict(r)) for r in rows]


async def get_task(db: aiosqlite.Connection, task_id: str) -> Task | None:
    cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = await cursor.fetchone()
    return _dict_to_task(dict(row)) if row else None


async def create_task(db: aiosqlite.Connection, task: Task) -> Task:
    await db.execute(
        """INSERT INTO tasks (id, title, description, status, model, plan,
           plan_conversation, stream_response, created_at, updated_at, position)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            task.id, task.title, task.description, task.status.value,
            task.model, task.plan, task.plan_conversation,
            task.stream_response, task.created_at, task.updated_at,
            task.position,
        ),
    )
    await db.commit()
    return task


async def update_task(db: aiosqlite.Connection, task_id: str, updates: dict) -> Task | None:
    # Build SET clause
    allowed = {
        "title", "description", "status", "model", "plan",
        "plan_conversation", "stream_response", "position", "updated_at",
    }
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return await get_task(db, task_id)

    set_clause = ", ".join(f"{k} = ?" for k in filtered)
    values = list(filtered.values()) + [task_id]

    await db.execute(
        f"UPDATE tasks SET {set_clause} WHERE id = ?",
        values,
    )
    await db.commit()
    return await get_task(db, task_id)


async def delete_task(db: aiosqlite.Connection, task_id: str) -> bool:
    cursor = await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    await db.commit()
    return cursor.rowcount > 0


# ── Chat CRUD ───────────────────────────────────────────────

async def get_chat_messages(db: aiosqlite.Connection) -> list[ChatMessage]:
    cursor = await db.execute(
        "SELECT * FROM chat_messages ORDER BY created_at ASC"
    )
    rows = await cursor.fetchall()
    return [_dict_to_chat_message(dict(r)) for r in rows]


async def add_chat_message(db: aiosqlite.Connection, msg: ChatMessage) -> ChatMessage:
    await db.execute(
        "INSERT INTO chat_messages (id, role, content, model, created_at) VALUES (?, ?, ?, ?, ?)",
        (msg.id, msg.role, msg.content, msg.model, msg.created_at),
    )
    await db.commit()
    return msg


async def clear_chat(db: aiosqlite.Connection) -> None:
    await db.execute("DELETE FROM chat_messages")
    await db.commit()
