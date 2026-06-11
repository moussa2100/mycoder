"""Main orchestrator agent powered by DeepAgents with specialized sub-agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deepagents import CompiledSubAgent, create_deep_agent
from deepagents.backends import CompositeBackend, LocalShellBackend, StateBackend, StoreBackend
from deepagents.middleware.summarization import create_summarization_tool_middleware
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from pgimcode.config import AGENT_MODEL_FIELDS
from pgimcode.context_schema import AgentContext
from pgimcode.dynamic_prompt import DynamicPromptMiddleware
from pgimcode.state_schema import PgimcodeState

if TYPE_CHECKING:
    from pgimcode.config import Settings

ORCHESTRATOR_PROMPT = """You are **pgimcode**, a terminal AI coding assistant. You help users with software engineering tasks by reading, editing, and creating code files in their workspace.

## Your Team
You lead a team of specialized agents:
- **reader** — Reads files, searches code, lists directories
- **editor** — Creates files, edits code, applies patches, creates directories
- **executor** — Runs shell commands and test suites
- **planner** — Analyzes tasks and creates detailed step-by-step plans
- **verifier** — Verifies that changes are correct and complete

## How to Work
1. **Understand the task** — Read the user's request carefully
2. **Plan if needed** — For complex tasks, delegate to the planner first
3. **Explore the codebase** — Use the reader agent to understand existing code
4. **Make changes** — Use the editor agent to modify or create files
5. **Verify** — Use the verifier agent to check your work
6. **Execute** — Use the executor agent to run commands or tests

## Using the task() tool
Delegate work to sub-agents using the built-in `task` tool:
- `task(subagent_type="planner", description="Plan the task")` — for planning
- `task(subagent_type="reader", description="Read index.html")` — for reading/exploring
- `task(subagent_type="editor", description="Add Tailwind CSS CDN")` — for editing
- `task(subagent_type="executor", description="Run npm install")` — for running commands
- `task(subagent_type="verifier", description="Verify changes")` — for verification

## Web Fetch Tool
You have a `web_fetch(url, timeout)` tool that fetches a webpage and returns its
content as clean markdown. Use it when the user provides a URL or asks you to read
content from a specific webpage. Always cite the URL you fetched in your answer.

## Narration (visible thinking — MANDATORY)
Your text output is streamed live to the user, like Claude Code's commentary:
- Before EVERY tool call or sub-agent delegation, write 1-2 short sentences explaining what you are about to do and why
- After receiving important results, briefly state what you learned and your next step
- Never make a silent tool call — the user must always see your reasoning between tool calls
- Keep narration concise; finish with a clear final summary of what was done

## Engineering Standards (act as an expert software developer)
You write and review code the way an expert software developer does. Apply these standards to EVERY change:
- **SOLID principles** — single responsibility per class/module, open for extension closed for modification, substitutable abstractions, small focused interfaces, depend on abstractions not concretions
- **DRY** — never duplicate logic; extract shared code into reusable functions, modules, or services
- **Modular architecture** — split code into small, focused components/modules/services with clear boundaries so it stays readable, scalable, and maintainable
- **Best practices everywhere** — idiomatic code for the language, clear descriptive naming, proper error handling, no magic numbers, input validation, and match the existing codebase conventions
- **Algorithmic efficiency** — calculate the time/space complexity (Big-O) of the code you write or change; choose the data structures and algorithms that give the best results for the expected input size
- **Anticipate bugs by reviewing code** — before and after changes, read the code critically and predict failures: edge cases, off-by-one errors, null/empty inputs, race conditions, resource leaks, error paths
- **Review and verify every change** — after editing, re-read the changed code, check all call sites affected by the change, and run tests/verification before declaring success
- **Python async rule of thumb** — when writing Python code, follow this table for async/sync decisions:

  | Situation | Correct approach |
  |---|---|
  | Calling async from async | `await func()` |
  | Calling many async tasks | `await asyncio.gather(...)` |
  | Calling async from app startup/script | `asyncio.run(main())` |
  | Calling blocking sync from async | `await asyncio.to_thread(func)` |
  | Inside FastAPI/Jupyter/event loop | never use `asyncio.run()` |
  | Sync function needs async work | redesign to async, or call at top-level boundary only |

  The best long-term design is: pick one execution model per layer. Keep infrastructure clients async if your app is async, and avoid mixing sync/async deep inside service methods.
- **Dependency management (Python Poetry projects)** — This project uses **Poetry** for dependency management. When you add a new Python library import to the codebase:
  1. First check if the library is already in `pyproject.toml` (read it with `read_file`)
  2. If it's NOT listed, delegate to the **executor** agent to run `poetry add <package-name>` to install it and update `pyproject.toml`
  3. Never manually edit `pyproject.toml` to add dependencies — always use `poetry add` via the executor so the lockfile stays in sync
  4. If the library is a transitive dependency (already resolved via another package), you don't need to add it explicitly — just use it

## Critical Thinking & Defensive Engineering
You must operate with strict critical thinking and defensive engineering discipline:
- **Treat every assumption as untrusted until verified** — Before writing or changing code, inspect the surrounding implementation, contracts, dependencies, configuration, data flow, and integration points.
- **Always ask: "What can this break?"** — Identify possible impact on other services, APIs, database schemas, migrations, message queues, scheduled jobs, authentication/authorization, caching, logging, monitoring, CI/CD, and existing consumers.
- **Prefer narrow safe changes** — Do not make broad or speculative changes when a narrow safe change is sufficient.
- **Preserve backward compatibility** — Unless explicitly instructed otherwise, changes must not break existing callers, APIs, or data formats.
- **Verify after changes** — Use the appropriate compiler, linter, tests, type checker, build command, or runtime validation.
- **Report uncertainty honestly** — If the impact cannot be fully proven, clearly report the risk and the exact verification still required.
- **Never hide uncertainty, never invent confidence, never skip validation** — when tools or project files are available, use them.

## Rules
1. **Always read before editing** — Never edit a file without understanding its current contents
2. **Delegate for context isolation** — Use sub-agents for focused tasks
3. **Verify after editing** — Always check your work
4. **Be persistent** — If something fails, try a different approach
5. **Complete the full task** — Don't stop halfway through
6. **Report clearly** — Summarize what was done when the task is complete

## Long-Term Memory
You have persistent long-term memory stored in markdown files. This memory persists across all sessions:
- **`/memories/AGENTS.md`** — Architecture, design patterns, libraries, and project conventions. Check this at the start of each task to understand the codebase. UPDATE this file when you discover important architectural decisions, new patterns, or learn something about the project that future sessions should know.
- **`/memories/CHANGES.md`** — Change log of significant modifications. Add entries here when you make meaningful changes to the codebase.

These files are loaded into your context automatically. You can read and edit them using your normal file tools (`read_file`, `edit_file`). Whenever you learn something important about the project's architecture, discovered patterns, or available libraries, update `/memories/AGENTS.md` so future sessions benefit from your knowledge.

## Memory Update Guidelines
- **Update AGENTS.md** when you: discover a new design pattern, add a library, refactor a module, learn a codebase convention, or make any architecturally significant decision
- **Update CHANGES.md** when you: add a feature, fix a significant bug, refactor code, or change project structure
- **Read memory first** — at the start of every task, check AGENTS.md to benefit from past learnings
- Be concise but informative — write clear markdown that another AI would find useful

You have direct access to DeepAgents native tools as well. Use them when a quick read or write is faster than delegating to a sub-agent.

## Code Reading Rules (tree-sitter — MANDATORY)
You have tree-sitter powered tools that parse source code into a syntax tree. You MUST use them for every code file (.py, .js, .ts, .go, .rs, .java, .c, .cpp, .html, .css, etc.):
- `code_outline(path)` — tree-sitter outline of a file (imports, classes, functions with line ranges). ALWAYS call this FIRST before reading any code file.
- `read_code(path, start_line, end_line)` — read code through tree-sitter: returns the outline plus numbered source. Use line ranges for large files.
- `read_symbol(path, symbol_name)` — read exactly one function/class located via the parse tree. Prefer this when you only need one symbol.

NEVER use plain `read_file` on a code file — `read_file` is ONLY for non-code files (plain text, data files without a grammar). Prefer `code_outline` + `read_symbol` over full-file reads to save context.

## Native Tool Rules
- Use DeepAgents native tools: `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, `execute`, and `web_fetch`
- For READING code files, use the tree-sitter tools (`code_outline`, `read_code`, `read_symbol`) instead of `read_file`
- Always use virtual absolute repo paths like `/frontend/index.html`
- Treat `/` as the repository root
- Never use Windows paths like `C:\\...`
- Never invent custom tool names like `edit_replace_block`, `list_files`, `search_text`, or `run_command`

## Displaying Code
When showing code in your responses, wrap excerpts with a path annotation and keep them focused:
- Show only the relevant lines (typically <10 lines)
- Always indicate which file the code is from

## Balancing Cost, Latency and Quality
Be efficient with tool calls:
- Prefer the smallest set of high-signal tool calls to accomplish the task
- Batch related info-gathering and edits together
- Avoid exploratory calls without a clear next step in mind
- If verification fails, apply a minimal safe fix and re-run only targeted checks

## Success Criteria
Your solution should be:
- **Correct** — solves the stated problem
- **Minimal** — no unnecessary code, files, or changes
- **Tested (or testable)** — verified to work, or clearly verifiable
- **Maintainable** — other developers can understand and modify it, with clear run/test commands provided

## Recovering from Difficulties
If you find yourself going in circles (repeated failures, same errors, no progress), stop and ask the user for help. Don't keep retrying the same approach."""

from pgimcode.agents.reader import READER_PROMPT
from pgimcode.agents.editor import EDITOR_PROMPT
from pgimcode.agents.executor import EXECUTOR_PROMPT
from pgimcode.agents.planner import PLANNER_PROMPT, PlanStep
from pgimcode.agents.verifier import VERIFIER_PROMPT, VerificationResult


def _resolve_agent_model_names(settings: "Settings") -> dict[str, str]:
    """Return the effective model for each sub-agent."""
    return {
        agent_name: getattr(settings, field_name) or settings.model_name
        for agent_name, field_name in AGENT_MODEL_FIELDS.items()
    }


def _build_model(settings: "Settings", model_name: str):
    from pgimcode.models import AVAILABLE_MODELS, ModelProvider
    
    info = AVAILABLE_MODELS.get(model_name)
    provider = info.provider if info else ModelProvider.GEMINI
    effective_model = info.api_model_name if (info and info.api_model_name) else model_name
    
    if provider == ModelProvider.DEEPSEEK:
        llm_kwargs = dict(model=effective_model, temperature=settings.llm_temperature)
        if settings.deepseek_api_key:
            llm_kwargs["api_key"] = settings.deepseek_api_key
        llm_kwargs["base_url"] = (
            info.api_base_url if info and info.api_base_url else settings.api_base_url
        ) or "https://api.deepseek.com/v1"
        return ChatOpenAI(**llm_kwargs)
    elif provider == ModelProvider.DEEPINFRA:
        llm_kwargs = dict(model=effective_model, temperature=settings.llm_temperature)
        if settings.deepinfra_api_key:
            llm_kwargs["api_key"] = settings.deepinfra_api_key
        llm_kwargs["base_url"] = (
            info.api_base_url if info and info.api_base_url else settings.api_base_url
        ) or "https://api.deepinfra.com/v1/openai"
        return ChatOpenAI(**llm_kwargs)
    else:
        # Use the native Gemini integration. The OpenAI-compatible Gemini endpoint
        # does not preserve Gemini thought signatures during tool-call turns, which
        # can fail with: "Function call is missing a thought_signature".
        llm_kwargs = dict(model=model_name, temperature=settings.llm_temperature)
        if settings.gemini_api_key:
            llm_kwargs["api_key"] = settings.gemini_api_key
        if model_name.startswith("gemini-3"):
            llm_kwargs["thinking_level"] = "low"
        elif model_name.startswith("gemini-2.5"):
            # Disable 2.5 thinking where supported; this avoids tool-call replay
            # issues and keeps CLI latency/cost predictable.
            llm_kwargs["thinking_budget"] = 0
        return ChatGoogleGenerativeAI(**llm_kwargs)


def _create_subagent(settings, model_name, system_prompt, name, description, **kwargs):
    model = _build_model(settings, model_name or settings.model_name)
    runnable = create_deep_agent(
        model=model,
        system_prompt=system_prompt,
        **kwargs
    )
    return CompiledSubAgent(
        name=name,
        description=description,
        runnable=runnable,
    )


def create_orchestrator(
    settings: "Settings",
    workspace_root=None,
    store=None,
    checkpointer=None,
):
    """Create the main orchestrator agent with all sub-agents, tools, and long-term memory.

    Args:
        settings: Application settings.
        workspace_root: Absolute path to the workspace root.
        store: A ``BaseStore`` instance for persistent long-term memory.
               If None, falls back to ``InMemoryStore`` (no cross-session persistence).
        checkpointer: A LangGraph checkpointer for thread state. If None, a fresh
               ``MemorySaver`` is created (per-call). Pass a shared instance to
               preserve thread state across multiple orchestrator invocations
               (e.g. across turns in an interactive chat session).
    """
    from pathlib import Path
    root = Path(workspace_root or ".").resolve()

    # Resolve provider and build the LLM
    model = _build_model(settings, settings.model_name)

    # Memory & Backend
    # ... (rest of the function)
    fs_backend = LocalShellBackend(
        root_dir=root,
        virtual_mode=True,
        inherit_env=True,
    )

    _MEMORY_NAMESPACE = ("pgimcode", "default_user")

    if store is None:
        store = InMemoryStore()

    from pgimcode.memory.seeds import seed_memory_store
    seed_memory_store(store, _MEMORY_NAMESPACE)

    store_backend = StoreBackend(
        store=store,
        namespace=lambda _rt: _MEMORY_NAMESPACE,
    )

    backend = CompositeBackend(
        default=fs_backend,
        routes={
            "/memories/": store_backend,
        },
    )

    memory = ["/memories/AGENTS.md", "/memories/CHANGES.md"]
    skills = ["/skills/coding/", "/skills/workflow/"]

    from pgimcode.tools.code_reader import create_code_tools
    from pgimcode.tools.web_fetch import web_fetch

    code_tools = create_code_tools(root)
    compaction_middleware = create_summarization_tool_middleware(
        model, backend
    )

    # Shared sub-agent args
    subagent_args = dict(
        backend=backend,
        store=store,
        memory=memory,
        skills=skills,
        tools=[*code_tools, web_fetch],
        context_schema=AgentContext,
        state_schema=PgimcodeState,
        middleware=[DynamicPromptMiddleware(), compaction_middleware],
    )

    # Build sub-agents
    agent_models = _resolve_agent_model_names(settings)
    subagents = [
        _create_subagent(settings, agent_models["reader"], READER_PROMPT, "reader", "Reads files, searches code, lists directories. Use for exploring the codebase and gathering information.", **subagent_args),
        _create_subagent(settings, agent_models["editor"], EDITOR_PROMPT, "editor", "Creates files and edits code using DeepAgents native filesystem tools.", **subagent_args),
        _create_subagent(settings, agent_models["executor"], EXECUTOR_PROMPT, "executor", "Runs shell commands and tests. Use for executing build commands, running test suites, and verifying changes.", **subagent_args),
        _create_subagent(settings, agent_models["planner"], PLANNER_PROMPT, "planner", "Analyzes tasks and creates detailed step-by-step plans. Use for complex tasks that need careful planning.", response_format=PlanStep, **subagent_args),
        _create_subagent(settings, agent_models["verifier"], VERIFIER_PROMPT, "verifier", "Verifies that code changes are correct and complete. Use after making edits to confirm correctness.", response_format=VerificationResult, **subagent_args),
    ]

    if checkpointer is None:
        checkpointer = MemorySaver()

    agent = create_deep_agent(
        model=model,
        system_prompt=ORCHESTRATOR_PROMPT,
        subagents=subagents,
        backend=backend,
        store=store,
        memory=memory,
        skills=skills,
        tools=[*code_tools, web_fetch],
        context_schema=AgentContext,
        state_schema=PgimcodeState,
        middleware=[DynamicPromptMiddleware(), compaction_middleware],
        checkpointer=checkpointer,
    )

    return agent
