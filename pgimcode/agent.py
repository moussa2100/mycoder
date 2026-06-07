"""RealAgent: LangGraph-powered agent with LLM integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pgimcode.approval import ApprovalGate
from pgimcode.config import Settings
from pgimcode.events import Event, EventBus, EventType
from pgimcode.graph.graph import build_graph
from pgimcode.session import _new_ulid


def _node_to_event_type(node_name: str) -> EventType:
    """Map graph node names to EventType."""
    mapping = {
        "intake": EventType.SESSION_STARTED,
        "discovery": EventType.REPO_SCANNING,
        "planning": EventType.PLAN_GENERATED,
        "decision": EventType.PLANNING_STARTED,
        "tool_exec": EventType.PATCH_APPLYING,
        "finish": EventType.COMPLETED,
    }
    return mapping.get(node_name, EventType.SESSION_STARTED)


class RealAgent:
    """Real LangGraph-powered agent."""

    def __init__(
        self,
        bus: EventBus,
        session_id: str,
        task: str,
        approval_gate: ApprovalGate | None = None,
        context_manager=None,
        mode: str = "build",
        settings=None,
        slash_listener=None,
        renderer=None,
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

    async def run(self) -> None:
        """Run the agent graph end-to-end, publishing events as nodes execute."""
        graph = build_graph(max_turns=self._settings.llm_max_turns)
        config = {"configurable": {"thread_id": self._session_id}}

        initial_state = {
            "session_id": self._session_id,
            "task": self._task,
            "mode": self._mode,
            "turn": 0,
            "max_turns": self._settings.llm_max_turns,
            "events": [],
            "active_events": [],
            "summaries": [],
            "pinned": [],
            "messages": [],
            "repo_map": None,
            "plan": None,
            "current_node": "start",
            "last_tool_result": {},
            "tool_calls": [],
            "status": "running",
            "approval_required": False,
            "approval_reason": "",
            "pending_action": [],
            "token_usage": 0,
            "cost_usd": 0.0,
            "changed_files": [],
            "next_node": "",
            "settings_dict": self._settings.model_dump(),
        }

        async for chunk in graph.astream(initial_state, config):
            if self.cancelled:
                await self._bus.publish(Event(
                    id=_new_ulid(),
                    session_id=self._session_id,
                    type=EventType.FAILED,
                    step=0,
                    status="done",
                    details="Agent cancelled",
                ))
                break

            if self.slash_listener and self.slash_listener.has_command():
                cmd = self.slash_listener.pending_command()
                if cmd == "model_switch":
                    await self._handle_model_switch()

            for node_name, state_update in chunk.items():
                if "__end__" in node_name:
                    continue

                step = state_update.get("turn", 0)
                event_type = _node_to_event_type(node_name)

                # Build a descriptive detail string — natural language, not node names
                detail = ""
                if node_name == "tool_exec":
                    last = state_update.get("last_tool_result", {})
                    if isinstance(last, dict) and last.get("result"):
                        results = last["result"]
                        if isinstance(results, list):
                            for r in reversed(results):
                                if isinstance(r, dict) and r.get("message"):
                                    detail = r["message"]
                                    break
                        elif isinstance(results, dict):
                            detail = results.get("message", "")
                    if not detail:
                        detail = "Tool executed"

                elif node_name == "decision":
                    msgs = state_update.get("messages", [])
                    content = ""
                    if msgs and isinstance(msgs[-1], dict):
                        content = msgs[-1].get("content", "")
                    nxt = state_update.get("next_node", "")
                    status = state_update.get("status", "")

                    if status == "failed":
                        ltr = state_update.get("last_tool_result", {})
                        if isinstance(ltr, dict):
                            detail = f"Error: {ltr.get('result', 'Unknown')}"
                        else:
                            detail = "LLM call failed"
                    elif nxt == "tool_exec":
                        if content:
                            detail = content[:300]
                        else:
                            pending = state_update.get("pending_action", [])
                            if isinstance(pending, list) and pending:
                                names = [c.get("name", "?") for c in pending]
                                paths = []
                                for c in pending:
                                    args = c.get("args", {})
                                    p = args.get("path", "")
                                    if p:
                                        paths.append(p)
                                if paths and len(paths) == 1:
                                    detail = f"{names[0]}: {paths[0]}"
                                elif paths:
                                    detail = f"{', '.join(names)}: {', '.join(paths)}"
                                else:
                                    detail = f"{', '.join(names)}"
                            else:
                                detail = "Thinking..."
                    elif nxt == "finish":
                        detail = content[:300] if content else "Done"
                    else:
                        detail = "Thinking..."

                elif node_name == "intake":
                    detail = "Initializing..."
                elif node_name == "discovery":
                    detail = "Scanning repository"
                elif node_name == "planning":
                    detail = "Planning approach"
                elif node_name == "finish":
                    detail = "Task completed"
                else:
                    detail = state_update.get("status", "Processing...")

                await self._bus.publish(Event(
                    id=_new_ulid(),
                    session_id=self._session_id,
                    type=event_type,
                    step=step,
                    status="in_progress",
                    details=detail,
                ))

                # Also add to context manager if set
                if self.context_manager:
                    event = Event(
                        id=_new_ulid(),
                        session_id=self._session_id,
                        type=event_type,
                        step=step,
                        status="in_progress",
                        details=f"Node: {node_name}",
                    )
                    self.context_manager.add(event)

    async def _handle_model_switch(self) -> None:
        """Pause agent, show model selector, apply selection, resume."""
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
        """Set cancelled flag so the run loop exits early."""
        self.cancelled = True