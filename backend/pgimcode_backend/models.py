"""Pydantic models shared across the backend API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PLANNING = "planning"
    QUEUE = "queue"
    IN_PROGRESS = "in-progress"
    IN_REVIEW = "in-review"
    DONE = "done"
    ARCHIVE = "archive"


class Task(BaseModel):
    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PLANNING
    model: str = "gemini-3.5-flash"
    plan: str = ""
    plan_conversation: str = ""
    stream_response: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    position: int = 0


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    model: str = "gemini-3.5-flash"


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    model: str | None = None
    plan: str | None = None
    plan_conversation: str | None = None
    stream_response: str | None = None
    position: int | None = None


class PlanRequest(BaseModel):
    title: str
    description: str = ""
    model: str = "gemini-3.5-flash"
    feedback: str | None = None
    current_plan: str | None = None


class PlanResponse(BaseModel):
    plan: str
    conversation: str


class ExecuteRequest(BaseModel):
    task_id: str
    model: str = "gemini-3.5-flash"
    workspace_dir: str = ""


class ChatMessage(BaseModel):
    id: str
    role: str  # "user" | "assistant"
    content: str
    model: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ChatRequest(BaseModel):
    message: str
    model: str = "gemini-3.5-flash"
    workspace_dir: str = ""


class WorkspaceRequest(BaseModel):
    path: str


class WorkspaceInfo(BaseModel):
    path: str
    exists: bool
    is_directory: bool
