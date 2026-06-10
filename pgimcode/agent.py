"""RealAgent: DeepAgents-powered multi-agent orchestrator with sub-agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pgimcode.config import Settings
from pgimcode.events import Event, EventBus, EventType
from pgimcode.session import _new_ulid

if TYPE_CHECKING:
    from pgimcode.approval import ApprovalGate


class RealAgent:
    """Graph-first real agent with evented runtime orchestration."""

    def __init__(
        self,
        bus: EventBus,
        session_id: str,
        task: str,
        approval_gate: "ApprovalGate | None" = None,
        context_manager=None,
        mode: str = "build",
        settings: Settings | None = None,
        slash_listener=None,
        renderer=None,
        recent_files: list[str] | None = None,
        conversation_history: list[tuple[str, bool]] | None = None,
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
        self._workspace_root = self._resolve_root()

    async def run(self) -> None:
        """Run the deepagents orchestrator and surface failures as events."""
        from pgimcode.agents.orchestrator import create_orchestrator
        from pgimcode.memory.store import PersistentFileStore
        from pathlib import Path

        try:
            await self._bus.publish(Event(
                id=_new_ulid(),
                session_id=self._session_id,
                type=EventType.SESSION_STARTED,
                step=0,
                status="in_progress",
                details=f"Starting task: {self._task}",
            ))

            # Create persistent long-term memory store
            memory_dir = self._workspace_root / ".pgim_memory"
            memory_store = PersistentFileStore(root_dir=memory_dir)

            agent = create_orchestrator(
                self._settings,
                workspace_root=self._workspace_root,
                store=memory_store,
            )
            initial = {"messages": [{"role": "user", "content": self._build_task_input()}]}
            config = {"configurable": {"thread_id": self._session_id}}

            if self.renderer and hasattr(self.renderer, "on_assistant_token"):
                await self._run_streaming(agent, initial, config)
            else:
                await self._run_updates_only(agent, initial, config)

            await self._bus.publish(Event(
                id=_new_ulid(),
                session_id=self._session_id,
                type=EventType.COMPLETED,
                step=0,
                status="done",
                details="Task completed",
            ))

        except Exception as e:
            await self._bus.publish(Event(
                id=_new_ulid(),
                session_id=self._session_id,
                type=EventType.FAILED,
                step=0,
                status="done",
                details=f"Error: {e}",
            ))
            raise

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

    async def _run_streaming(self, agent, initial, config) -> None:
        """Stream tokens + tool calls + tool results (including sub-agent activity) to the renderer."""
        seen_tool_call_ids: set[str] = set()
        seen_tool_result_ids: set[str] = set()

        # subgraphs=True surfaces sub-agent (task tool) messages, so the user
        # sees the thinking and tool calls happening inside delegated agents.
        async for item in agent.astream(
            initial, config, stream_mode=["updates", "messages"], subgraphs=True
        ):
            if self.cancelled:
                break

            if self.slash_listener and self.slash_listener.has_command():
                cmd = self.slash_listener.pending_command()
                if cmd == "model_switch":
                    await self._handle_model_switch()

            # With subgraphs=True items are (namespace, mode, data); without, (mode, data)
            if isinstance(item, tuple) and len(item) == 3:
                _namespace, mode, data = item
            else:
                mode, data = item

            if mode == "messages":
                msg_chunk, meta = data
                content = self._extract_stream_text(msg_chunk, meta)
                if content:
                    self.renderer.on_assistant_token(content)
                continue

            if mode == "updates":
                for node_name, state_update in (data or {}).items():
                    if node_name in ("__end__", "__start__", "start"):
                        continue
                    if not isinstance(state_update, dict):
                        continue
                    for msg in state_update.get("messages", []) or []:
                        self._render_message(msg, seen_tool_call_ids, seen_tool_result_ids)

    def _message_text(self, msg) -> str:
        """Extract plain text from a message's content (str or content-block list)."""
        content = getattr(msg, "content", "") or ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            return "".join(parts)
        return ""

    def _render_message(
        self, msg, seen_tool_call_ids: set[str], seen_tool_result_ids: set[str]
    ) -> None:
        """Render a single agent message (assistant narration, tool-calls, or tool result)."""
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            # Show the assistant's thinking/narration that precedes the tool calls
            narration = self._message_text(msg).strip()
            if narration and hasattr(self.renderer, "show_assistant_text"):
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
                if tc_id and tc_id in seen_tool_call_ids:
                    continue
                if tc_id:
                    seen_tool_call_ids.add(tc_id)
                self.renderer.on_tool_call(name, args)
            return

        role = getattr(msg, "role", "") or getattr(msg, "type", "")
        if role == "tool":
            tc_id = getattr(msg, "tool_call_id", "") or ""
            if tc_id and tc_id in seen_tool_result_ids:
                return
            if tc_id:
                seen_tool_result_ids.add(tc_id)
            name = getattr(msg, "name", "") or "tool"
            content = getattr(msg, "content", "") or ""
            success = True
            text = content if isinstance(content, str) else str(content)
            try:
                import json as _json
                parsed = _json.loads(text)
                if isinstance(parsed, dict):
                    if parsed.get("success") is False:
                        success = False
                    msg_text = parsed.get("message")
                    if isinstance(msg_text, str) and msg_text:
                        text = msg_text
            except (ValueError, TypeError):
                pass
            self.renderer.on_tool_result(name, text, success=success)
            return

        # Plain assistant message (no tool calls) — intermediate thinking/answer.
        # Deduplicated by the renderer against text already streamed token-by-token.
        if role in ("ai", "assistant"):
            text = self._message_text(msg).strip()
            if text and hasattr(self.renderer, "show_assistant_text"):
                self.renderer.show_assistant_text(text)

    def _extract_stream_text(self, msg_chunk, meta: dict | None) -> str | None:
        """Return only user-meaningful assistant narration, not tool payloads."""
        node_name = str((meta or {}).get("langgraph_node", ""))
        chunk_type = msg_chunk.__class__.__name__.lower()

        if "tool" in node_name.lower() or "tool" in chunk_type:
            return None
        if getattr(msg_chunk, "tool_call_id", None) or getattr(msg_chunk, "name", None):
            return None

        content = getattr(msg_chunk, "content", "") or ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            text = "".join(parts)
        else:
            return None

        stripped = text.strip()
        if not stripped:
            return None
        if stripped.startswith("{") and '"message"' in stripped:
            return None
        if stripped.lower().startswith("<!doctype html") or stripped.lower().startswith("<html"):
            return None
        return text

    async def _run_updates_only(self, agent, initial, config) -> None:
        """Legacy path: emit one event per node update via the bus (no renderer streaming)."""
        step = 0
        async for chunk in agent.astream(initial, config):
            if self.cancelled:
                break

            if self.slash_listener and self.slash_listener.has_command():
                cmd = self.slash_listener.pending_command()
                if cmd == "model_switch":
                    await self._handle_model_switch()

            for node_name, state_update in chunk.items():
                if node_name in ("__end__", "__start__", "start"):
                    continue
                if state_update is None:
                    continue
                detail = self._parse_deepagents_event(node_name, state_update)
                if detail:
                    step += 1
                    event_type = self._event_type_for_node(node_name)
                    await self._emit_event(event_type, step, detail)

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
                import json
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
        from pathlib import Path
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
        from pgimcode.input_handler import ModelSelector

        console = None
        if self.renderer and hasattr(self.renderer, '_console'):
            console = self.renderer._console

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


# pathlib import needed at module level for _resolve_root
from pathlib import Path
