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
        "inspect": EventType.FILE_READING,
        "edit": EventType.PATCH_APPLYING,
        "execute": EventType.TESTS_RUNNING,
        "verify": EventType.VERIFICATION_STARTED,
        "compact": EventType.CONTEXT_COMPACTED,
        "approval": EventType.BLOCKED_FOR_APPROVAL,
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
    ):
        self._bus = bus
        self._session_id = session_id
        self._task = task
        self._mode = mode
        self.cancelled = False
        self.approval_gate = approval_gate
        self.context_manager = context_manager
        self._settings = Settings()

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
            "repo_map": None,
            "plan": None,
            "current_node": "start",
            "last_tool_result": {},
            "tool_calls": [],
            "status": "running",
            "approval_required": False,
            "approval_reason": "",
            "pending_action": {},
            "token_usage": 0,
            "cost_usd": 0.0,
            "changed_files": [],
            "next_node": "",
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

            for node_name, state_update in chunk.items():
                if "__end__" in node_name:
                    continue

                step = state_update.get("turn", 0)
                event_type = _node_to_event_type(node_name)

                await self._bus.publish(Event(
                    id=_new_ulid(),
                    session_id=self._session_id,
                    type=event_type,
                    step=step,
                    status="in_progress",
                    details=f"Node: {node_name}",
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

    def cancel(self) -> None:
        """Set cancelled flag so the run loop exits early."""
        self.cancelled = True