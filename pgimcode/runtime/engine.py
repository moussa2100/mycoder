"""Graph-first runtime engine for the real agent path."""

from __future__ import annotations

from dataclasses import dataclass

from pgimcode.events import Event, EventBus, EventType
from pgimcode.session import _new_ulid


@dataclass
class EngineResult:
    status: str
    final_message: str
    final_state: dict


class GraphRuntimeEngine:
    """Run the LangGraph stack and translate updates into user-visible events."""

    def __init__(self, bus: EventBus, session_id: str, task: str, mode: str, settings, renderer=None, context_manager=None, recent_files=None, conversation_history=None):
        self._bus = bus
        self._session_id = session_id
        self._task = task
        self._mode = mode
        self._settings = settings
        self._renderer = renderer
        self._context_manager = context_manager
        self._recent_files = list(recent_files or [])
        self._conversation_history = list(conversation_history or [])
        self._step = 0
        self._state: dict = {}
        self._seen_tool_calls: set[str] = set()
        self._seen_tool_results: set[str] = set()

    async def run(self) -> EngineResult:
        from pgimcode.graph.graph import build_graph

        graph = build_graph(self._settings.llm_max_turns)
        config = {"configurable": {"thread_id": self._session_id}}
        carryover_context = self._build_carryover_context()
        initial_state = {
            "session_id": self._session_id,
            "task": self._task,
            "mode": self._mode,
            "max_turns": self._settings.llm_max_turns,
            "messages": [{"role": "user", "content": self._task}],
            "carryover_context": carryover_context,
            "recent_files": list(self._recent_files),
            "settings_dict": self._settings.model_dump(),
        }

        await self._emit(EventType.SESSION_STARTED, f"Starting task: {self._task}", data=self._snapshot_data(initial_state))
        async for chunk in graph.astream(initial_state, config):
            for node_name, state_update in (chunk or {}).items():
                if node_name in {"__start__", "__end__", "start"} or not isinstance(state_update, dict):
                    continue
                self._state.update(state_update)
                self._render_messages(state_update.get("messages", []))
                await self._emit_node_events(node_name, state_update)

        final_message = self._extract_final_message(self._state)
        if final_message and self._renderer and hasattr(self._renderer, "on_assistant_token"):
            self._renderer.on_assistant_token(final_message)
            self._renderer.on_assistant_end(render_panel=True)
        status = self._state.get("status", "completed")
        return EngineResult(status=status, final_message=final_message, final_state=dict(self._state))

    async def _emit(self, event_type: EventType, details: str, status: str = "done", data: dict | None = None) -> None:
        self._step += 1
        await self._bus.publish(Event(id=_new_ulid(), session_id=self._session_id, type=event_type, step=self._step, status=status, details=details, data=data))

    async def _emit_node_events(self, node_name: str, state_update: dict) -> None:
        data = self._snapshot_data(self._state)
        if node_name == "discovery":
            repo_map = state_update.get("repo_map", {})
            mode = state_update.get("discovery_mode", self._state.get("discovery_mode", "full"))
            if mode == "fast":
                details = f"Fast-scanned likely follow-up targets: {repo_map.get('total_files', 0)} files, languages={', '.join(repo_map.get('languages', {}).keys()) or 'unknown'}"
            else:
                details = f"Scanned repository: {repo_map.get('total_files', 0)} files, languages={', '.join(repo_map.get('languages', {}).keys()) or 'unknown'}"
            await self._emit(EventType.REPO_SCANNING, details, data=data)
        elif node_name == "planning":
            await self._emit(EventType.RESEARCH_STARTED, "Built research goals and candidate files", data=data)
            if state_update.get("task_board"):
                await self._emit(EventType.TASK_UPDATED, "Created task board for the current request", data=data)
            if state_update.get("evidence"):
                await self._emit(EventType.EVIDENCE_CAPTURED, f"Seeded {len(state_update.get('evidence', []))} evidence item(s)", data=data)
            if state_update.get("plan"):
                steps = len(state_update["plan"].get("steps", []))
                await self._emit(EventType.PLAN_GENERATED, f"Generated implementation plan with {steps} step(s)", data=data)
        elif node_name == "tool_exec":
            for result in state_update.get("last_tool_result", {}).get("result", []):
                event_type = self._tool_event_type(result.get("name", ""))
                await self._emit(event_type, result.get("message", result.get("name", "tool")), data=data)
            if state_update.get("task_board"):
                await self._emit(EventType.TASK_UPDATED, "Updated task board from tool activity", data=data)
        elif node_name == "finish":
            final_status = state_update.get("status", self._state.get("status", "completed"))
            event_type = EventType.FAILED if final_status == "failed" else EventType.COMPLETED
            detail = "Task failed" if event_type == EventType.FAILED else "Task completed"
            await self._emit(event_type, detail, data=data)

    def _tool_event_type(self, tool_name: str) -> EventType:
        if tool_name in {"search_text", "search_symbol"}:
            return EventType.EVIDENCE_CAPTURED
        if tool_name in {"read_file", "read_chunk", "list_files"}:
            return EventType.FILE_READING
        if tool_name in {"edit_replace_block", "edit_patch", "write_file", "create_directory"}:
            return EventType.PATCH_APPLYING
        if tool_name in {"verify_file", "run_command"}:
            return EventType.VERIFICATION_STARTED
        return EventType.MILESTONE_REACHED

    def _snapshot_data(self, state: dict) -> dict:
        return {
            "candidate_files": [item.get("path") for item in state.get("candidate_files", [])[:5]],
            "evidence_count": len(state.get("evidence", [])),
            "task_board": state.get("task_board", [])[:5],
            "recent_files": state.get("recent_files", [])[:8],
            "changed_files": state.get("changed_files", [])[:8],
        }

    def _build_carryover_context(self) -> str:
        lines: list[str] = []

        recent_successes = [task for task, success in self._conversation_history if success][-3:]
        if recent_successes:
            lines.append("Recent successful requests:")
            for item in recent_successes:
                lines.append(f"- {item}")

        if self._recent_files:
            if lines:
                lines.append("")
            lines.append("Recent changed files:")
            for path in self._recent_files[-8:]:
                lines.append(f"- {path}")

        context_manager = self._context_manager
        if context_manager is not None:
            pinned = getattr(context_manager, "pinned", [])[-5:]
            if pinned:
                if lines:
                    lines.append("")
                lines.append("Pinned session context:")
                for item in pinned:
                    text = getattr(item, "text", str(item))
                    lines.append(f"- {text}")

        return "\n".join(lines).strip()

    def _render_messages(self, messages: list[dict]) -> None:
        if not self._renderer:
            return
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tool_call in msg.get("tool_calls", []):
                    tc_id = tool_call.get("id") or f"{tool_call.get('name')}:{tool_call.get('args')}"
                    if tc_id in self._seen_tool_calls:
                        continue
                    self._seen_tool_calls.add(tc_id)
                    if hasattr(self._renderer, "on_tool_call"):
                        self._renderer.on_tool_call(tool_call.get("name", "tool"), tool_call.get("args", {}))
            elif msg.get("role") == "tool":
                tc_id = msg.get("tool_call_id") or f"tool:{msg.get('name')}:{msg.get('content')}"
                if tc_id in self._seen_tool_results:
                    continue
                self._seen_tool_results.add(tc_id)
                if hasattr(self._renderer, "on_tool_result"):
                    self._renderer.on_tool_result(msg.get("name", "tool"), msg.get("content", ""), success=not str(msg.get("content", "")).startswith("Error:"))

    def _extract_final_message(self, state: dict) -> str:
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("content"):
                return str(msg.get("content"))
        return ""
