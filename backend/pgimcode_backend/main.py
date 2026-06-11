"""pgimcode Backend - FastAPI application server.

Provides REST + SSE endpoints for the Electron frontend:
- Task CRUD
- LLM plan generation (with streaming)
- LLM task execution (with streaming)
- Chat (with streaming)
- Workspace management
"""

from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from .database import (
    get_db,
    get_all_tasks,
    get_tasks_by_status,
    get_task,
    create_task as db_create_task,
    update_task as db_update_task,
    delete_task as db_delete_task,
    get_chat_messages,
    add_chat_message,
    clear_chat,
)
from .models import (
    Task,
    TaskCreate,
    TaskUpdate,
    TaskStatus,
    PlanRequest,
    PlanResponse,
    ExecuteRequest,
    ChatMessage,
    ChatRequest,
    WorkspaceRequest,
    WorkspaceInfo,
)
from .services import generate_plan, execute_task_stream, chat_stream


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: ensure DB is initialized on startup."""
    async for db in get_db():
        pass  # Schema is created on first connection
    yield


app = FastAPI(
    title="pgimcode API",
    description="Backend API for the pgimcode Electron frontend",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - allow Electron renderer
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helper ──────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Health ──────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ── Task CRUD ───────────────────────────────────────────────

@app.get("/api/tasks", response_model=list[Task])
async def list_tasks(status: TaskStatus | None = Query(None)):
    """Get all tasks, optionally filtered by status."""
    async for db in get_db():
        if status:
            return await get_tasks_by_status(db, status)
        return await get_all_tasks(db)
    return []


@app.get("/api/tasks/{task_id}", response_model=Task)
async def get_task_endpoint(task_id: str):
    """Get a single task by ID."""
    async for db in get_db():
        task = await get_task(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    raise HTTPException(status_code=500)


@app.post("/api/tasks", response_model=Task, status_code=201)
async def create_task_endpoint(body: TaskCreate):
    """Create a new task (always starts in Planning)."""
    async for db in get_db():
        # Count tasks in planning for position
        planning_tasks = await get_tasks_by_status(db, TaskStatus.PLANNING)
        task = Task(
            id=str(uuid.uuid4()),
            title=body.title,
            description=body.description,
            status=TaskStatus.PLANNING,
            model=body.model,
            position=len(planning_tasks),
        )
        return await db_create_task(db, task)
    raise HTTPException(status_code=500)


@app.patch("/api/tasks/{task_id}", response_model=Task)
async def update_task_endpoint(task_id: str, body: TaskUpdate):
    """Update a task (title, description, status, plan, etc.)."""
    async for db in get_db():
        existing = await get_task(db, task_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Task not found")

        updates = body.model_dump(exclude_unset=True)
        updates["updated_at"] = _now()

        if "status" in updates and isinstance(updates["status"], TaskStatus):
            updates["status"] = updates["status"].value

        updated = await db_update_task(db, task_id, updates)
        if not updated:
            raise HTTPException(status_code=500)
        return updated
    raise HTTPException(status_code=500)


@app.delete("/api/tasks/{task_id}")
async def delete_task_endpoint(task_id: str):
    """Delete a task."""
    async for db in get_db():
        existing = await get_task(db, task_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Task not found")
        await db_delete_task(db, task_id)
        return {"success": True, "id": task_id}
    raise HTTPException(status_code=500)


# ── LLM Plan Generation (temp, no task ID) ──────────────────

@app.post("/api/tasks/plan-temp", response_model=PlanResponse)
async def generate_plan_temp(body: PlanRequest):
    """Generate a plan without a task ID (for the create modal)."""
    plan_text = await generate_plan(
        title=body.title or "",
        description=body.description or "",
        model=body.model or "gemini-3.5-flash",
        feedback=body.feedback,
        current_plan=body.current_plan,
    )
    return PlanResponse(plan=plan_text, conversation="")


# ── LLM Plan Generation ────────────────────────────────────

@app.post("/api/tasks/{task_id}/plan")
async def generate_plan_endpoint(task_id: str, body: PlanRequest):
    """Generate or revise a plan for a task using the LLM.

    Returns the plan as a streaming SSE response.
    """
    async for db in get_db():
        task = await get_task(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Run plan generation
        plan_text = await generate_plan(
            title=body.title or task.title,
            description=body.description or task.description,
            model=body.model or task.model,
            feedback=body.feedback,
            current_plan=body.current_plan or task.plan,
        )

        # Save plan to task
        conversation = task.plan_conversation or ""
        if body.feedback:
            conversation += f"\n\n---\n**You:** {body.feedback}\n\n---\n**Assistant:**\n{plan_text}"
        else:
            conversation = f"**You:** Generate a plan for: \"{body.title or task.title}\"\n\n---\n**Assistant:**\n{plan_text}"

        await db_update_task(db, task_id, {
            "plan": plan_text,
            "plan_conversation": conversation,
            "updated_at": _now(),
        })

        return PlanResponse(plan=plan_text, conversation=conversation)

    raise HTTPException(status_code=500)


@app.post("/api/tasks/{task_id}/plan/stream")
async def generate_plan_stream(task_id: str, body: PlanRequest):
    """Generate a plan with SSE streaming (real-time updates)."""
    async for db in get_db():
        task = await get_task(db, task_id)
        if not task:
            raise HTTPException(status_code=404)

    async def event_generator():
        plan_text = await generate_plan(
            title=body.title,
            description=body.description,
            model=body.model,
            feedback=body.feedback,
            current_plan=body.current_plan,
        )
        # Simulate streaming chunks
        chunks = plan_text.split(" ")
        for i, chunk in enumerate(chunks):
            yield {"event": "chunk", "data": chunk + (" " if i < len(chunks) - 1 else "")}
            await asyncio.sleep(0.03)
        yield {"event": "done", "data": plan_text}

    return EventSourceResponse(event_generator())


# ── Task Execution (Streaming) ──────────────────────────────

@app.post("/api/tasks/{task_id}/execute")
async def execute_task_endpoint(task_id: str, body: ExecuteRequest):
    """Execute a task with SSE streaming of progress."""
    async for db in get_db():
        task = await get_task(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        accumulated = ""
        async for chunk in execute_task_stream(
            task_id=task_id,
            task_title=task.title,
            task_plan=task.plan,
            model=body.model,
            workspace_dir=body.workspace_dir,
        ):
            accumulated += chunk
            yield {"event": "chunk", "data": chunk}

        # Save stream response to DB
        async for db in get_db():
            await db_update_task(db, task_id, {
                "stream_response": accumulated,
                "status": "in-review",
                "updated_at": _now(),
            })

        yield {"event": "done", "data": accumulated}

    return EventSourceResponse(event_generator())


# ── Chat ────────────────────────────────────────────────────

@app.get("/api/chat", response_model=list[ChatMessage])
async def list_chat():
    """Get all chat messages."""
    async for db in get_db():
        return await get_chat_messages(db)
    return []


@app.post("/api/chat", response_model=ChatMessage)
async def send_chat_message(body: ChatRequest):
    """Send a chat message and get an AI response."""
    async for db in get_db():
        # Save user message
        user_msg = ChatMessage(
            id=str(uuid.uuid4()),
            role="user",
            content=body.message,
            model=body.model,
        )
        await add_chat_message(db, user_msg)

        # Get AI response
        response_content = ""
        async for chunk in chat_stream(
            message=body.message,
            model=body.model,
            workspace_dir=body.workspace_dir,
        ):
            response_content += chunk

        # Save assistant message
        assistant_msg = ChatMessage(
            id=str(uuid.uuid4()),
            role="assistant",
            content=response_content,
            model=body.model,
        )
        await add_chat_message(db, assistant_msg)
        return assistant_msg

    raise HTTPException(status_code=500)


@app.post("/api/chat/stream")
async def chat_stream_endpoint(body: ChatRequest):
    """Send a chat message and get a streaming SSE response."""
    async for db in get_db():
        user_msg = ChatMessage(
            id=str(uuid.uuid4()),
            role="user",
            content=body.message,
            model=body.model,
        )
        await add_chat_message(db, user_msg)

    async def event_generator():
        full_response = ""
        async for chunk in chat_stream(
            message=body.message,
            model=body.model,
            workspace_dir=body.workspace_dir,
        ):
            full_response += chunk
            yield {"event": "chunk", "data": chunk}

        # Save assistant message
        async for db in get_db():
            assistant_msg = ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=full_response,
                model=body.model,
            )
            await add_chat_message(db, assistant_msg)

        yield {"event": "done", "data": full_response}

    return EventSourceResponse(event_generator())


@app.delete("/api/chat")
async def clear_chat_endpoint():
    """Clear all chat messages."""
    async for db in get_db():
        await clear_chat(db)
        return {"success": True}


# ── Workspace ───────────────────────────────────────────────

@app.post("/api/workspace/validate")
async def validate_workspace(body: WorkspaceRequest):
    """Validate a workspace directory path."""
    p = Path(body.path).expanduser().resolve()
    return WorkspaceInfo(
        path=str(p),
        exists=p.exists(),
        is_directory=p.is_dir() if p.exists() else False,
    )


@app.get("/api/models")
async def list_models():
    """List available LLM models."""
    from pgimcode.models import AVAILABLE_MODELS

    return [
        {
            "id": m.id,
            "name": m.name,
            "provider": m.provider.value,
            "context_window": m.context_window,
        }
        for m in AVAILABLE_MODELS
    ]


# ── Entry Point ─────────────────────────────────────────────

def main():
    """Entry point for running the server."""
    import uvicorn

    uvicorn.run(
        "pgimcode_backend.main:app",
        host="127.0.0.1",
        port=8765,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
