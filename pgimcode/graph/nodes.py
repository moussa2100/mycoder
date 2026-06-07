"""LangGraph node implementations — real LLM-powered agent."""

from __future__ import annotations
from pathlib import Path
from typing import Literal

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

from pgimcode.graph.state import AgentState
from pgimcode.graph.tools import TOOL_DEFINITIONS, call_tool
from pgimcode.discovery.repo_scanner import RepoScanner
from pgimcode.discovery.repo_map import build_repo_map
from pgimcode.discovery.language_detector import annotate_languages
from pgimcode.tools.ranker import rank_files_by_relevance
from pgimcode.planner import TaskPlanner
from pgimcode.events import EventType
from pgimcode.config import Settings


def _get_workspace_root() -> Path:
    """Find the project root, walking up from CWD."""
    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "pyproject.toml").exists() or (parent / ".env").exists():
            return parent
    return cwd


def _to_dict(state) -> dict:
    if hasattr(state, "model_dump"):
        return state.model_dump()
    return dict(state)


def _get_settings(state) -> Settings:
    s = _to_dict(state)
    raw = s.get("settings_dict", {})
    if isinstance(raw, Settings):
        return raw
    if isinstance(raw, dict):
        return Settings(**raw)
    return Settings()


_llm_cache: dict[str, ChatOpenAI] = {}


def _build_llm(state) -> ChatOpenAI:
    settings = _get_settings(state)
    provider = settings.resolve_provider()

    if provider == "deepseek":
        model = settings.model_name if settings.model_name.startswith("deepseek") else "deepseek-chat"
        api_key = settings.deepseek_api_key
        base_url = settings.api_base_url or "https://api.deepseek.com/v1"
    else:
        model = settings.model_name if settings.model_name.startswith("gpt") or settings.model_name.startswith("o") else "gpt-4o"
        api_key = settings.openai_api_key
        base_url = settings.api_base_url or None

    temperature = settings.llm_temperature

    # Build cache key from all parameters that affect the LLM instance
    cache_key = f"{provider}:{model}:{temperature}:{api_key}:{base_url}"
    cached = _llm_cache.get(cache_key)
    if cached is not None:
        return cached

    kwargs = dict(model=model, temperature=temperature)
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url

    llm = ChatOpenAI(**kwargs)
    _llm_cache[cache_key] = llm
    return llm


def _build_system_prompt(state: dict) -> str:
    task = state.get("task", "")
    mode = state.get("mode", "build")
    repo_map = state.get("repo_map", {})
    plan = state.get("plan", {})

    languages = repo_map.get("languages", {})
    lang_str = ", ".join(f"{k} ({v} files)" for k, v in languages.items()) if languages else "unknown"
    frameworks = repo_map.get("frameworks", [])
    fw_str = ", ".join(frameworks) if frameworks else "none detected"
    total_files = repo_map.get("total_files", 0)
    plan_steps = ""
    if plan:
        steps = plan.get("steps", [])
        plan_steps = "\n".join(f"  {i+1}. {s.get('description', '')}" for i, s in enumerate(steps[:10]))

    return f"""You are pgimcode, a terminal AI coding assistant. You help users with software engineering tasks by reading, editing, and creating code files in their workspace.

## Current Task
{task}

## Agent Mode
{mode}

## Repository Context
- Languages: {lang_str}
- Frameworks: {fw_str}
- Total files: {total_files}

## Plan
{plan_steps if plan_steps else 'No plan generated yet.'}

## Critical Instructions
1. **ALWAYS read a file before editing it.** Use read_file to understand the current contents.
2. **If a search returns no results, try reading the target file directly** or try a different search query. Don't give up after one empty search.
3. **Use write_file to create new files, read_file to read existing files, edit_replace_block to modify.**
4. **Make focused, minimal changes.** Don't rewrite entire files if a small edit will do.
5. **When asked to style/modify HTML:** read the file first, then apply changes using edit_replace_block.
6. **After completing the task, verify with a brief summary.**
7. **Work step by step.** Read first, then plan, then execute.
8. **Never say 'Done' without actually making the requested changes.** If you need more information, use tools to find it.

Be persistent. Complete the full task — don't stop halfway."""


# ─────────────────────────────────────────────────────────────
# Setup nodes (unchanged from original)
# ─────────────────────────────────────────────────────────────

def intake_node(state) -> dict:
    s = _to_dict(state)
    current = s.get("turn", 0)
    task = s.get("task", "")
    if task:
        task = task.strip()
    messages = list(s.get("messages", []))
    settings = s.get("settings_dict", {})
    return {
        "task": task,
        "turn": current + 1,
        "current_node": "discovery",
        "messages": messages,
        "settings_dict": settings,
    }


def discovery_node(state) -> dict:
    s = _to_dict(state)
    current = s.get("turn", 0)
    root = _get_workspace_root()
    scanner = RepoScanner(root=root)
    scanned = scanner.scan()
    scanned = annotate_languages(scanned)
    repo_map = build_repo_map(scanner)
    repo_map_dict = {
        "root": str(repo_map.root),
        "languages": repo_map.languages,
        "frameworks": repo_map.frameworks,
        "entry_points": repo_map.entry_points,
        "test_locations": repo_map.test_locations,
        "dependency_files": repo_map.dependency_files,
        "build_commands": repo_map.build_commands,
        "total_files": repo_map.total_files,
        "total_lines": repo_map.total_lines,
        "total_size": repo_map.total_size,
        "top_dirs": repo_map.top_dirs,
    }
    return {
        "turn": current + 1,
        "current_node": "planning",
        "repo_map": repo_map_dict,
    }


def planning_node(state) -> dict:
    s = _to_dict(state)
    current = s.get("turn", 0)
    task = s.get("task", "")
    repo_map_dict = s.get("repo_map")
    root = _get_workspace_root()
    scanner = RepoScanner(root=root)
    files = scanner.scan()
    files = annotate_languages(files)
    ranked = rank_files_by_relevance(task, files, root, max_results=20)
    from pgimcode.discovery.repo_map import RepoMap
    if repo_map_dict:
        repo_map_for_planner = RepoMap(
            root=Path(repo_map_dict["root"]),
            languages=repo_map_dict.get("languages", {}),
            frameworks=repo_map_dict.get("frameworks", []),
            entry_points=repo_map_dict.get("entry_points", []),
            test_locations=repo_map_dict.get("test_locations", []),
            dependency_files=repo_map_dict.get("dependency_files", []),
            build_commands=repo_map_dict.get("build_commands", []),
            total_files=repo_map_dict.get("total_files", 0),
            total_lines=repo_map_dict.get("total_lines", 0),
            total_size=repo_map_dict.get("total_size", 0),
            top_dirs=repo_map_dict.get("top_dirs", []),
        )
    else:
        repo_map_for_planner = build_repo_map(scanner)
    planner = TaskPlanner(repo_map=repo_map_for_planner, ranked_files=ranked)
    plan = planner.plan(task)
    plan_dict = {
        "task": plan.task,
        "interpretation": plan.interpretation,
        "objective": plan.objective,
        "constraints": plan.constraints,
        "acceptance_criteria": plan.acceptance_criteria,
        "assumptions": plan.assumptions,
        "steps": [
            {"description": step.description, "status": step.status,
             "tool": step.tool, "target": step.target, "reasoning": step.reasoning}
            for step in plan.steps
        ],
        "files_to_inspect": plan.files_to_inspect,
        "next_action": plan.next_action,
        "confidence": plan.confidence,
    }
    return {
        "turn": current + 1,
        "current_node": "decision",
        "plan": plan_dict,
    }


# ─────────────────────────────────────────────────────────────
# LLM-powered nodes
# ─────────────────────────────────────────────────────────────

def decision_node(state) -> dict:
    """Call the LLM with tools. Return next_node: tool_exec or finish."""
    s = _to_dict(state)
    current = s.get("turn", 0)
    max_turns = s.get("max_turns", 50)
    messages = list(s.get("messages", []))

    if current >= max_turns:
        return {"next_node": "finish", "turn": current + 1}

    system_prompt = _build_system_prompt(s)

    # Build message list: system + existing messages
    llm_messages = []
    has_system = any(
        isinstance(m, dict) and m.get("role") == "system"
        for m in messages
    )
    if not has_system:
        llm_messages.append(SystemMessage(content=system_prompt))

    for m in messages:
        if isinstance(m, dict):
            role = m.get("role", "")
            content = m.get("content", "")
            name = m.get("name", "")
            tool_call_id = m.get("tool_call_id", "")
            if role in ("user", "human"):
                llm_messages.append(HumanMessage(content=content))
            elif role in ("assistant", "ai"):
                msg = AIMessage(content=content)
                if m.get("tool_calls"):
                    from langchain_core.messages import ToolCall
                    msg.tool_calls = [
                        ToolCall(name=tc["name"], args=tc.get("args", {}), id=tc.get("id", ""))
                        for tc in m["tool_calls"]
                    ]
                llm_messages.append(msg)
            elif role == "tool":
                llm_messages.append(ToolMessage(content=content, tool_call_id=tool_call_id, name=name))
        elif hasattr(m, "content"):
            llm_messages.append(m)

    try:
        llm = _build_llm(state)
        llm_with_tools = llm.bind_tools(TOOL_DEFINITIONS)
        response = llm_with_tools.invoke(llm_messages)
    except Exception as exc:
        error_msg = f"LLM call failed: {exc}"
        return {
            "turn": current + 1,
            "next_node": "finish",
            "status": "failed",
            "last_tool_result": {"success": False, "result": error_msg},
            "messages": messages,
        }

    # Record the AI response in messages
    ai_msg = {
        "role": "assistant",
        "content": response.content or "",
    }
    if hasattr(response, "tool_calls") and response.tool_calls:
        ai_msg["tool_calls"] = [
            {"name": tc["name"], "args": tc.get("args", {}), "id": tc.get("id", "")}
            for tc in response.tool_calls
        ]

    token_usage = s.get("token_usage", 0)
    if hasattr(response, "response_metadata"):
        usage = response.response_metadata.get("token_usage", {})
        token_usage += usage.get("total_tokens", 0)

    messages.append(ai_msg)

    if hasattr(response, "tool_calls") and response.tool_calls:
        # Store all tool calls for batch execution
        all_calls = [
            {"name": tc["name"], "args": tc.get("args", {}), "id": tc.get("id", "")}
            for tc in response.tool_calls
        ]
        return {
            "turn": current + 1,
            "next_node": "tool_exec",
            "pending_action": all_calls,
            "messages": messages,
            "token_usage": token_usage,
        }

    return {
        "turn": current + 1,
        "next_node": "finish",
        "messages": messages,
        "token_usage": token_usage,
        "status": "completed",
    }


def execute_tool_node(state) -> dict:
    """Execute all pending tool calls and store results."""
    s = _to_dict(state)
    current = s.get("turn", 0)
    pending = s.get("pending_action", [])
    messages = list(s.get("messages", []))
    changed_files = list(s.get("changed_files", []))

    # Normalize: could be single dict or list of dicts
    if isinstance(pending, dict) and pending:
        tool_calls = [pending]
    elif isinstance(pending, list):
        tool_calls = pending
    else:
        tool_calls = []

    results = []
    for tc in tool_calls:
        tool_name = tc.get("name", "")
        tool_args = tc.get("args", {})
        tool_id = tc.get("id", "")

        result = call_tool(tool_name, tool_args)

        inner = result.get("result", "Done")
        if isinstance(inner, dict):
            result_content = inner.get("message", str(inner))
        else:
            result_content = str(inner)

        if not result.get("success"):
            result_content = f"Error: {result_content}"

        messages.append({
            "role": "tool",
            "content": result_content,
            "tool_call_id": tool_id,
            "name": tool_name,
        })
        results.append({"name": tool_name, "success": result.get("success", False), "message": result_content})

        if tool_name in ("write_file", "edit_replace_block", "edit_patch"):
            path = tool_args.get("path", "")
            if path and path not in changed_files:
                changed_files.append(path)

    return {
        "turn": current + 1,
        "next_node": "decision",
        "last_tool_result": {"success": all(r["success"] for r in results), "result": results},
        "messages": messages,
        "changed_files": changed_files,
        "pending_action": [],
    }


def finish_node(state) -> dict:
    s = _to_dict(state)
    return {
        "status": s.get("status", "completed"),
        "current_node": "finish",
    }


# ─────────────────────────────────────────────────────────────
# Router for conditional edges
# ─────────────────────────────────────────────────────────────

def next_node(state) -> Literal["tool_exec", "finish"]:
    s = _to_dict(state)
    nxt = s.get("next_node", "")
    if nxt == "tool_exec":
        return "tool_exec"
    return "finish"
