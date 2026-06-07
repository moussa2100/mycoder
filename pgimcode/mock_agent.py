"""Mock Agent for deterministic testing and demos — with real tool execution."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from pgimcode.approval import ApprovalGate
from pgimcode.config import Settings
from pgimcode.events import Event, EventBus, EventType
from pgimcode.session import _new_ulid


def _parse_task(task: str) -> list[dict]:
    """Parse a natural language task into executable actions.

    Returns a list of action dicts with keys: type, params, description.
    """
    actions: list[dict] = []
    task_lower = task.lower()

    # ── Detect folder creation ──
    folder_patterns = [
        r"create\s+(?:a\s+)?(?:new\s+)?(?:folder|directory)\s+(?:named\s+|called\s+|name\s+it\s+)?['\"]?(\S+?)['\"]?(?:\s|$|,|\.)",
        r"name\s+it\s+['\"]?(\S+?)['\"]?(?:\s|$|,|\.)",
        r"mkdir\s+['\"]?(\S+?)['\"]?",
    ]
    _skip_words = {"name", "it", "a", "the", "an", "and", "that", "which", "with", "contains"}
    folders = []
    for pat in folder_patterns:
        for m in re.finditer(pat, task_lower):
            name = m.group(1).rstrip(".,;")
            if name and name not in folders and name.lower() not in _skip_words:
                folders.append(name)

    for folder in folders:
        actions.append({
            "type": "mkdir",
            "params": {"path": folder},
            "description": f"Create folder: {folder}/",
        })

    # ── Detect file creation with content ──
    file_pattern = r"(?:create|make|write)\s+(?:a\s+)?(?:new\s+)?(?:file\s+)?(?:named\s+|called\s+)?['\"]?(\S+?\.[a-zA-Z]+)['\"]?"
    content_patterns = [
        r"(?:that|which|with)\s+(?:contains?|has|says?|shows?|displays?)\s+['\"]?(.+?)(?:['\"]?\s*(?:in\s+(?:a\s+)?(?:<[^>]+>|p\s*(?:tag)?|div\s*(?:tag)?|h\d\s*(?:tag)?|span\s*(?:tag)?)|$|\.$|,))?",
        r"contain(?:s|ing)\s+['\"]?(.+?)(?:['\"]?\s*(?:in\s+(?:a\s+)?(?:<[^>]+>|p\s*(?:tag)?|div|h\d|span)|$|\.$|,))?",
        r"with\s+(?:the\s+)?(?:content|text|message)\s+['\"]?(.+?)['\"]?(?:\s*(?:in|inside|within)\s+(?:a\s+)?(?:<[^>]+>|p\s*(?:tag)?|div|h\d|span))?",
        r"write\s+['\"]?(.+?)['\"]?\s+(?:to|into|in)\s+['\"]?(\S+?\.[a-zA-Z]+)['\"]?",
        r"write\s+(?:a\s+)?(?:file\s+)?(?:named\s+)?['\"]?(\S+?\.[a-zA-Z]+)['\"]?\s+(?:that|which|with)\s+['\"]?(.+?)['\"]?",
    ]

    content = ""
    html_tag = None

    # Detect HTML tag wrapping
    tag_match = re.search(r"in\s+(?:a\s+)?(?:<([^>]+)>|(p|div|h[1-6]|span|pre|code)\s*(?:tag)?)", task_lower)
    if tag_match:
        html_tag = tag_match.group(1) or tag_match.group(2)

    # Extract content
    for pat in content_patterns:
        m = re.search(pat, task_lower, re.DOTALL)
        if m:
            if len(m.groups()) == 2 and m.group(2):
                content = m.group(1).strip().strip("'\"")
            else:
                content = m.group(1).strip().strip("'\"")
            break

    if not content:
        # Fallback: grab text after "contains" or "with"
        for kw in ["contains", "containing", "says", "displays", "shows"]:
            idx = task_lower.find(kw)
            if idx >= 0:
                rest = task[idx + len(kw):].strip(" :\"'")
                content = rest.rstrip(".,;").strip("'\"")
                break

    # Detect file names
    file_names = []
    for m in re.finditer(file_pattern, task_lower):
        name = m.group(1).rstrip(".,;")
        if name and name not in file_names:
            file_names.append(name)

    # Build full path
    full_path = file_names[0] if file_names else "index.html"
    if folders and "/" not in full_path and "\\" not in full_path:
        if not full_path.startswith(folders[0]):
            full_path = f"{folders[0]}/{full_path}"

    if content or file_names:
        # Determine file type from extension and generate appropriate content
        ext = Path(full_path).suffix.lower()
        if html_tag:
            body = f"<{html_tag}>{content}</{html_tag}>"
        else:
            body = content or "hello world"

        if ext in (".html", ".htm"):
            file_content = f"<!DOCTYPE html>\n<html>\n<head><title>{content[:30] if content else 'Page'}</title></head>\n<body>\n  {body}\n</body>\n</html>\n"
        elif ext == ".md":
            file_content = f"# {content[:50] if content else 'Title'}\n\n{body}\n"
        elif ext == ".py":
            file_content = f"# {content[:50] if content else 'Module'}\n\n{body}\n"
        elif ext == ".json":
            import json as _json
            file_content = _json.dumps({"content": body}, indent=2) + "\n"
        elif ext == ".txt":
            file_content = f"{body}\n"
        elif ext == ".css":
            file_content = f"/* {content[:50] if content else 'Styles'} */\n\n{body}\n"
        elif ext == ".js":
            file_content = f"// {content[:50] if content else 'Script'}\n\n{body}\n"
        else:
            file_content = f"{body}\n"

        actions.append({
            "type": "write_file",
            "params": {"path": full_path, "content": file_content},
            "description": f"Create file: {full_path} ({len(file_content)} bytes)",
        })

    # If nothing detected, return a default set of actions
    if not actions:
        if re.search(r"create|make|write|build|add|fix", task_lower):
            actions.append({
                "type": "write_file",
                "params": {"path": "output.txt", "content": task},
                "description": f"Write task to output.txt",
            })
        else:
            actions.append({
                "type": "noop",
                "params": {},
                "description": "No actionable steps detected — try a coding task",
            })

    return actions


def _execute_action(action: dict) -> dict:
    """Execute a single action and return a result dict."""
    atype = action["type"]

    if atype == "mkdir":
        path = Path(action["params"]["path"])
        try:
            path.mkdir(parents=True, exist_ok=True)
            return {"success": True, "message": f"Created folder: {path}/"}
        except OSError as e:
            return {"success": False, "message": f"Failed to create folder: {e}"}

    elif atype == "write_file":
        path = Path(action["params"]["path"])
        content = action["params"]["content"]
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {"success": True, "message": f"Created file: {path} ({len(content)} bytes)"}
        except OSError as e:
            return {"success": False, "message": f"Failed to write file: {e}"}

    elif atype == "run_command":
        import subprocess
        cmd = action["params"]["command"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=".")
            if result.returncode == 0:
                return {"success": True, "message": result.stdout.strip() or "Command succeeded"}
            else:
                return {"success": False, "message": result.stderr.strip() or f"Exit code {result.returncode}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    elif atype == "noop":
        return {"success": True, "message": action["description"]}

    return {"success": False, "message": f"Unknown action type: {atype}"}


class MockAgent:
    """Mock agent that parses tasks and executes real tool calls."""

    def __init__(self, bus: EventBus, session_id: str, task: str,
                 approval_gate: ApprovalGate | None = None,
                 context_manager=None, settings=None,
                 slash_listener=None, renderer=None):
        self._bus = bus
        self._session_id = session_id
        self._task = task
        self.cancelled = False
        self._settings = settings if settings is not None else Settings()
        self.approval_gate = approval_gate
        self.context_manager = context_manager
        self.slash_listener = slash_listener
        self.renderer = renderer

    async def run(self, delay: float | None = None) -> None:
        """Parse task, execute actions, publish real events."""
        if delay is None:
            delay = self._settings.mock_delay_seconds

        # ── Step 1: Parse the task ──
        actions = _parse_task(self._task)

        await self._emit(EventType.SESSION_STARTED, 1, "in_progress",
                         f"Parsing: {self._task[:80]}")
        await asyncio.sleep(delay * 0.3)

        # ── Step 2: Scan workspace ──
        repo_files = list(Path(".").glob("**/*"))
        file_count = len([f for f in repo_files if f.is_file() and not f.name.startswith(".")])
        await self._emit(EventType.REPO_SCANNING, 2, "in_progress",
                         f"Scanning workspace ({file_count} files)")
        await asyncio.sleep(delay * 0.3)

        # ── Step 3: Plan ──
        plan_lines = "\n".join(f"  - {a['description']}" for a in actions)
        await self._emit(EventType.PLANNING_STARTED, 3, "in_progress",
                         f"Plan ({len(actions)} step(s)):\n{plan_lines}" if actions else "No actions needed")
        await asyncio.sleep(delay * 0.3)

        # ── Step 4: Execute each action ──
        step = 4
        results = []
        for action in actions:
            if self.cancelled:
                break

            if self.slash_listener and self.slash_listener.has_command():
                cmd = self.slash_listener.pending_command()
                if cmd == "model_switch":
                    await self._handle_model_switch()

            # Approval check for file writes
            if self.approval_gate and action["type"] in ("write_file", "run_command"):
                approved = await self.approval_gate.check(
                    EventType.PATCH_APPLYING, action["description"]
                )
                if not approved:
                    await self._emit(EventType.FAILED, step, "done",
                                     f"Approval denied for: {action['description']}")
                    return

            await self._emit(EventType.PATCH_APPLYING, step, "in_progress",
                             action["description"])
            await asyncio.sleep(delay * 0.3)

            result = _execute_action(action)
            results.append(result)

            if result["success"]:
                await self._emit(EventType.PATCH_APPLYING, step, "done",
                                 result["message"])
            else:
                await self._emit(EventType.FAILED, step, "done",
                                 result["message"])
                return

            step += 1

        # ── Step 5: Verify ──
        await asyncio.sleep(delay * 0.3)
        await self._emit(EventType.VERIFICATION_STARTED, step, "in_progress",
                         "Verifying changes...")

        all_ok = all(r["success"] for r in results)
        if all_ok and results:
            # Verify files exist
            for action in actions:
                if action["type"] in ("write_file", "mkdir"):
                    p = Path(action["params"].get("path", ""))
                    if p.exists():
                        size = p.stat().st_size if p.is_file() else 0
                        label = f"{size} bytes" if p.is_file() else "directory"
                        await self._emit(EventType.VERIFICATION_STARTED, step, "done",
                                         f"Verified: {p} ({label}) exists")
                    else:
                        await self._emit(EventType.FAILED, step, "done",
                                         f"Missing: {p} was not created")
                        return

        await asyncio.sleep(delay * 0.3)

        # ── Step 6: Complete ──
        final_step = step + 1
        if all_ok:
            await self._emit(EventType.COMPLETED, final_step, "in_progress",
                             f"Task done: {self._task[:80]}")
            await asyncio.sleep(delay * 0.2)
            await self._emit(EventType.COMPLETED, final_step, "done",
                             f"Completed: {self._task[:80]}")
        else:
            await self._emit(EventType.FAILED, final_step, "done",
                             "Task could not be completed")

    async def _emit(self, event_type: EventType, step: int, status: str,
                    details: str) -> None:
        """Emit an event through the bus."""
        from pgimcode.events import Event
        event = Event(
            id=_new_ulid(),
            session_id=self._session_id,
            type=event_type,
            step=step,
            status=status,
            details=details,
        )
        await self._bus.publish(event)

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
        """Set cancelled flag so loop exits early."""
        self.cancelled = True
