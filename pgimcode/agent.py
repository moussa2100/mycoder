"""RealAgent: DeepAgents-powered multi-agent orchestrator with sub-agents."""

from __future__ import annotations

import asyncio
import json
import warnings
from pathlib import Path
from typing import Any

from langchain_core._api import LangChainBetaWarning

from pgimcode.agents.orchestrator import create_orchestrator
from pgimcode.config import Settings
from pgimcode.context_schema import AgentContext
from pgimcode.events import Event, EventBus, EventStreamAdapter, EventType
from pgimcode.input_handler import ModelSelector
from pgimcode.memory.store import PersistentFileStore
from pgimcode.session import _new_ulid

from pgimcode.approval import ApprovalGate
from pgimcode.renderer_protocol import RendererProtocol


def _extract_content_text(content: Any) -> str:
    """Extract plain text from message content (str or content-block list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return ""


class RealAgent:
    """Graph-first real agent with evented runtime orchestration."""

    def __init__(
        self,
        bus: EventBus,
        session_id: str,
        task: str,
        approval_gate: ApprovalGate | None = None,
        context_manager: object | None = None,
        mode: str = "build",
        settings: Settings | None = None,
        slash_listener: object | None = None,
        renderer: RendererProtocol | None = None,
        recent_files: list[str] | None = None,
        conversation_history: list[tuple[str, bool]] | None = None,
        active_skills: list[str] | None = None,
        checkpointer: object | None = None,
    ):
        self._bus = bus
        self._session_id = session_id
        self._task = task
        self._mode = mode
        self.cancelled = False
        self.approval_gate = approval_gate
        self.context_manager = context_manager
        self._settings = settings if settings is not None else Settings()
        self.slash_listener = slash_listener
        self.renderer = renderer
        self._recent_files = recent_files or []
        self._conversation_history = conversation_history or []
        self._active_skills = active_skills or []
        self._workspace_root = self._resolve_root()
        self._model_changed = False
        self._checkpointer = checkpointer

    def _on_model_switched(self, event: Event) -> None:
        if event.type == EventType.MODEL_SWITCHED:
            self._model_changed = True

    async def run(self) -> None:
        """Run the deepagents orchestrator and surface failures as events."""
        self._bus.subscribe(self._on_model_switched)

        try:
            await self._emit_lifecycle(EventType.SESSION_STARTED, f"Starting task: {self._task}")

            memory_store = PersistentFileStore(
                root_dir=self._workspace_root / ".pgim_memory"
            )

            await self._run_with_model_switch_loop(memory_store)

            await self._emit_lifecycle(EventType.COMPLETED, "Task completed")

        except Exception as e:
            await self._emit_lifecycle(EventType.FAILED, f"Error: {e}")
            raise

    async def _emit_lifecycle(self, event_type: EventType, detail: str) -> None:
        """Publish a lifecycle event (SESSION_STARTED, COMPLETED, FAILED)."""
        await self._bus.publish(Event(
            id=_new_ulid(),
            session_id=self._session_id,
            type=event_type,
            step=0,
            status="in_progress" if event_type == EventType.SESSION_STARTED else "done",
            details=detail,
        ))

    async def _run_with_model_switch_loop(self, memory_store: PersistentFileStore) -> None:
        """Run the agent, re-creating it on model switch, until no more switches."""
        while True:
            agent = create_orchestrator(
                self._settings,
                workspace_root=self._workspace_root,
                store=memory_store,
                checkpointer=self._checkpointer,
            )

            ctx = self._build_agent_context()
            initial = self._build_initial_state()
            config = {"configurable": {"thread_id": self._session_id}}

            if self.renderer:
                await self._run_streaming(agent, initial, config, context=ctx)
            else:
                await self._run_updates_only(agent, initial, config, context=ctx)

            # Update conversation history from checkpointed state.
            # This is best-effort — without a checkpointer, get_state fails gracefully.
            try:
                state = agent.get_state(config)
                self._conversation_history = state.values.get(
                    "conversation_history", self._conversation_history
                )
            except Exception:
                pass

            if not self._model_changed:
                break
            self._model_changed = False

    def _build_agent_context(self) -> AgentContext:
        """Build the runtime context for this invocation."""
        return AgentContext(
            mode=self._mode,
            workspace_root=str(self._workspace_root),
            session_id=self._session_id,
            recent_files=list(self._recent_files),
            conversation_history=list(self._conversation_history),
            active_skills=list(self._active_skills),
            preferences={"verbose": True},
        )

    def _build_initial_state(self) -> dict[str, Any]:
        """Build the initial graph state for this invocation."""
        return {
            "messages": [{"role": "user", "content": self._build_task_input()}],
            "recent_files": list(self._recent_files),
            "conversation_history": list(self._conversation_history),
            "session_mode": self._mode,
            "current_task": self._task,
        }

    def _build_task_input(self) -> str:
        """Prepend session carryover (recent files, prior successes) to the task."""
        lines: list[str] = []
        successes = [t for t, ok in self._conversation_history if ok][-3:]
        if successes:
            lines.append("Recent successful requests:")
            for item in successes:
                lines.append(f"- {item}")
        if self._recent_files:
            if lines:
                lines.append("")
            lines.append("Recent changed files:")
            for path in self._recent_files[-8:]:
                lines.append(f"- {path}")
        if self.context_manager is not None:
            pinned = getattr(self.context_manager, "pinned", [])[-5:]
            if pinned:
                if lines:
                    lines.append("")
                lines.append("Pinned session context:")
                for item in pinned:
                    lines.append(f"- {getattr(item, 'text', str(item))}")
        if not lines:
            return self._task
        return self._task + "\n\nRelevant session context:\n" + "\n".join(lines)

    async def _run_streaming(self, agent, initial, config, context=None) -> None:
        """Stream tokens + tool calls + subagent activity via v3 event-streaming."""
        adapter = EventStreamAdapter(
            bus=self._bus,
            session_id=self._session_id,
            renderer=self.renderer,
        )
        await self._consume_event_stream(agent, initial, config, adapter, context=context)

    async def _open_v3_event_stream(self, agent, initial, config, context=None):
        """Open LangGraph's v3 async stream, suppressing beta warnings."""
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="The v3 streaming protocol on Pregel is experimental.*",
                category=LangChainBetaWarning,
            )
            kwargs: dict[str, Any] = {"version": "v3"}
            if context is not None:
                kwargs["context"] = context
            return await agent.astream_events(initial, config=config, **kwargs)

    @staticmethod
    def _message_text(msg) -> str:
        """Extract plain text from a message's content (str or content-block list)."""
        return _extract_content_text(getattr(msg, "content", "") or "")

    def _render_message(
        self, msg, seen_tool_call_ids: set[str], seen_tool_result_ids: set[str]
    ) -> None:
        """Render a single agent message (assistant narration, tool-calls, or tool result)."""
        if self._render_tool_calls(msg, seen_tool_call_ids):
            return
        if self._render_tool_result(msg, seen_tool_result_ids):
            return
        self._render_assistant_text(msg)

    def _render_tool_calls(self, msg, seen_ids: set[str]) -> bool:
        """Render tool-call messages. Returns True if msg was a tool-call."""
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            return False

        narration = self._message_text(msg).strip()
        if narration and self.renderer:
            self.renderer.show_assistant_text(narration)

        for tc in (tool_calls if isinstance(tool_calls, list) else [tool_calls]):
            if isinstance(tc, dict):
                tc_id = tc.get("id") or ""
                name = tc.get("name", "?")
                args = tc.get("args", {}) or {}
            else:
                tc_id = getattr(tc, "id", "") or ""
                name = getattr(tc, "name", "?")
                args = getattr(tc, "args", {}) or {}
            if tc_id and tc_id in seen_ids:
                continue
            if tc_id:
                seen_ids.add(tc_id)
            self.renderer.on_tool_call(name, args)
        return True

    def _render_tool_result(self, msg, seen_ids: set[str]) -> bool:
        """Render tool-result messages. Returns True if msg was a tool result."""
        role = getattr(msg, "role", "") or getattr(msg, "type", "")
        if role != "tool":
            return False

        tc_id = getattr(msg, "tool_call_id", "") or ""
        if tc_id and tc_id in seen_ids:
            return True
        if tc_id:
            seen_ids.add(tc_id)

        name = getattr(msg, "name", "") or "tool"
        content = getattr(msg, "content", "") or ""
        text = content if isinstance(content, str) else str(content)
        success = True
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                if parsed.get("success") is False:
                    success = False
                msg_text = parsed.get("message")
                if isinstance(msg_text, str) and msg_text:
                    text = msg_text
        except (ValueError, TypeError):
            pass
        self.renderer.on_tool_result(name, text, success=success)
        return True

    def _render_assistant_text(self, msg) -> None:
        """Render plain assistant narration (no tool calls/results)."""
        role = getattr(msg, "role", "") or getattr(msg, "type", "")
        if role not in ("ai", "assistant"):
            return
        text = self._message_text(msg).strip()
        if text and self.renderer:
            self.renderer.show_assistant_text(text)

    def _extract_stream_text(self, msg_chunk, meta: dict | None) -> str | None:
        """Return only user-meaningful assistant narration, not tool payloads."""
        node_name = str((meta or {}).get("langgraph_node", ""))
        chunk_type = msg_chunk.__class__.__name__.lower()

        if "tool" in node_name.lower() or "tool" in chunk_type:
            return None
        if getattr(msg_chunk, "tool_call_id", None) or getattr(msg_chunk, "name", None):
            return None

        text = _extract_content_text(getattr(msg_chunk, "content", "") or "")
        stripped = text.strip()
        if not stripped:
            return None
        if stripped.startswith("{") and '"message"' in stripped:
            return None
        if stripped.lower().startswith("<!doctype html") or stripped.lower().startswith("<html"):
            return None
        return text

    async def _run_updates_only(self, agent, initial, config, context=None) -> None:
        """Legacy path: emit events via bus without token-level renderer."""
        adapter = EventStreamAdapter(bus=self._bus, session_id=self._session_id)
        await self._consume_event_stream(agent, initial, config, adapter, context=context)

    async def _consume_event_stream(
        self, agent, initial, config, adapter: EventStreamAdapter, context=None,
    ) -> None:
        """Open the v3 stream and consume it via the adapter, respecting model switch."""
        stream = await self._open_v3_event_stream(agent, initial, config, context=context)
        consume_task = asyncio.create_task(adapter.consume(stream))
        while not consume_task.done():
            if self._model_changed:
                consume_task.cancel()
                break
            await asyncio.sleep(0.1)
        try:
            await consume_task
        except asyncio.CancelledError:
            pass

    def _parse_deepagents_event(self, node_name: str, update: dict) -> str | None:
        """Parse a deepagents streaming event into a human-readable string."""
        msgs = update.get("messages", [])
        if not msgs:
            return None

        last = msgs[-1]

        # Tool calls from the LLM
        tool_calls = getattr(last, "tool_calls", None)
        if tool_calls:
            for tc in (tool_calls if isinstance(tool_calls, list) else [tool_calls]):
                name = tc.get("name", "?") if isinstance(tc, dict) else getattr(tc, "name", "?")
                args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                path = args.get("path", "")
                content = getattr(last, "content", "") or ""
                if content:
                    return content[:300]
                if path:
                    return f"{name}: {path}"
                return f"Calling {name}..."
            return None

        # Tool results
        role = getattr(last, "role", "") or getattr(last, "type", "")
        name = getattr(last, "name", "")
        content = getattr(last, "content", "")

        if role == "tool" or name:
            # Try to parse JSON result
            try:
                data = json.loads(content) if isinstance(content, str) else content
                if isinstance(data, dict):
                    msg = data.get("message", "")
                    if msg:
                        return msg
                    if data.get("success") is False:
                        return f"Failed: {data.get('message', content)}"
            except (json.JSONDecodeError, TypeError):
                pass
            return content[:200] if content else None

        # Assistant text response
        if role == "assistant" or role == "ai" or not role:
            if content and not tool_calls:
                return content[:300]

        # Skip middleware nodes
        if "middleware" in node_name.lower() or "after_model" in node_name or "before_agent" in node_name:
            return None

        return None

    def _event_type_for_node(self, node_name: str) -> EventType:
        if "model" in node_name or "agent" in node_name:
            return EventType.PLANNING_STARTED
        if "tools" in node_name:
            return EventType.PATCH_APPLYING
        return EventType.SESSION_STARTED

    def _resolve_root(self) -> Path:
        cwd = Path.cwd().resolve()
        for parent in [cwd] + list(cwd.parents):
            if (parent / "pyproject.toml").exists() or (parent / ".env").exists():
                return parent
        return cwd

    async def _emit(self, node: str, detail: str) -> None:
        await self._bus.publish(Event(
            id=_new_ulid(),
            session_id=self._session_id,
            type=self._event_type_for_node(node),
            step=0,
            status="in_progress",
            details=detail,
        ))

    async def _emit_event(self, event_type: EventType, step: int, detail: str) -> None:
        await self._bus.publish(Event(
            id=_new_ulid(),
            session_id=self._session_id,
            type=event_type,
            step=step,
            status="in_progress",
            details=detail,
        ))

    async def _handle_model_switch(self) -> None:
        console = self.renderer._console if self.renderer else None

        if self.renderer:
            self.renderer.pause_live()

        if console:
            new_model_id = ModelSelector.render_selection(
                console, self._settings.model_name
            )
            if new_model_id and new_model_id != self._settings.model_name:
                ModelSelector.apply_model_selection(self._settings, new_model_id)
                if self.renderer:
                    self.renderer.set_model(new_model_id)
                await self._bus.publish(Event(
                    id=_new_ulid(),
                    session_id=self._session_id,
                    type=EventType.MODEL_SWITCHED,
                    step=0,
                    status="done",
                    details=f"Switched to: {new_model_id}",
                ))

        if self.renderer:
            self.renderer.resume_live()

    def cancel(self) -> None:
        self.cancelled = True
