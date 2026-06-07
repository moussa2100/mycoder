"""RealAgent: DeepAgents-powered multi-agent orchestrator with sub-agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pgimcode.config import Settings
from pgimcode.events import Event, EventBus, EventType
from pgimcode.session import _new_ulid

if TYPE_CHECKING:
    from pgimcode.approval import ApprovalGate


class RealAgent:
    """DeepAgents-powered multi-agent orchestrator."""

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
        self._workspace_root = self._resolve_root()

    async def run(self) -> None:
        """Run the agent orchestrator, publishing events as sub-agents execute."""
        from pgimcode.agents.orchestrator import create_orchestrator

        # Phase 1: Scan repo
        await self._emit("scanning", "Scanning repository...")
        from pgimcode.discovery.repo_scanner import RepoScanner
        from pgimcode.discovery.language_detector import annotate_languages
        from pgimcode.discovery.repo_map import build_repo_map
        scanner = RepoScanner(root=self._workspace_root)
        scanned = annotate_languages(scanner.scan())
        repo_map = build_repo_map(scanner)

        # Phase 2: Find relevant files
        from pgimcode.tools.ranker import rank_files_by_relevance
        ranked = rank_files_by_relevance(self._task, scanned, self._workspace_root, max_results=20)

        repo_summary = f"{repo_map.total_files} files, {repo_map.languages}"
        top_files = "\n".join(f"  {rf.file.path} (score: {rf.score:.1f})" for rf in ranked[:8])

        context_prompt = f"""## Task
{self._task}

## Repository
{repo_summary}
Workspace: {self._workspace_root}

## Top Files
{top_files if top_files else 'No files found'}

Complete the task using the available tools. Be thorough."""

        # Phase 3: Run orchestrator
        try:
            agent = create_orchestrator(self._settings, self._workspace_root)
            config = {"configurable": {"thread_id": self._session_id}}
            initial = {"messages": [{"role": "user", "content": context_prompt}]}

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

            await self._emit("complete", "Task completed")

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
