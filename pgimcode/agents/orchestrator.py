"""Main orchestrator agent powered by DeepAgents with specialized sub-agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend

from pgimcode.agents.reader import create_reader_subagent
from pgimcode.agents.editor import create_editor_subagent
from pgimcode.agents.executor import create_executor_subagent
from pgimcode.agents.planner import create_planner_subagent
from pgimcode.agents.verifier import create_verifier_subagent

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

## Rules
1. **Always read before editing** — Never edit a file without understanding its current contents
2. **Delegate for context isolation** — Use sub-agents for focused tasks
3. **Verify after editing** — Always check your work
4. **Be persistent** — If something fails, try a different approach
5. **Complete the full task** — Don't stop halfway through
6. **Report clearly** — Summarize what was done when the task is complete

You have direct access to DeepAgents native tools as well. Use them when a quick read or write is faster than delegating to a sub-agent.

## Native Tool Rules
- Use DeepAgents native tools: `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, and `execute`
- Always use virtual absolute repo paths like `/frontend/index.html`
- Treat `/` as the repository root
- Never use Windows paths like `C:\\...`
- Never invent custom tool names like `edit_replace_block`, `list_files`, `search_text`, or `run_command`"""


def create_orchestrator(settings: "Settings", workspace_root=None):
    """Create the main orchestrator agent with all sub-agents and tools."""
    from pathlib import Path
    root = Path(workspace_root or ".").resolve()

    # Resolve provider and build the LLM
    provider = settings.resolve_provider()

    if provider == "deepseek":
        model_name = settings.model_name if settings.model_name.startswith("deepseek") else "deepseek-chat"
        api_key = settings.deepseek_api_key
        base_url = settings.api_base_url or "https://api.deepseek.com/v1"
    else:
        model_name = settings.model_name if (settings.model_name.startswith("gpt") or settings.model_name.startswith("o")) else "gpt-4o"
        api_key = settings.openai_api_key
        base_url = settings.api_base_url or None

    llm_kwargs = dict(model=model_name, temperature=settings.llm_temperature)
    if api_key:
        llm_kwargs["api_key"] = api_key
    if base_url:
        llm_kwargs["base_url"] = base_url

    model = ChatOpenAI(**llm_kwargs)

    # Build sub-agent configs
    subagents = [
        create_reader_subagent(),
        create_editor_subagent(),
        create_executor_subagent(),
        create_planner_subagent(),
        create_verifier_subagent(),
    ]

    backend = LocalShellBackend(
        root_dir=root,
        virtual_mode=True,
        inherit_env=True,
    )

    agent = create_deep_agent(
        model=model,
        system_prompt=ORCHESTRATOR_PROMPT,
        subagents=subagents,
        backend=backend,
    )

    return agent
