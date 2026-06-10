"""Seed the persistent store with initial memory files."""
from __future__ import annotations

from pathlib import Path
from langgraph.store.base import Item
from deepagents.backends.utils import create_file_data


SEED_AGENTS_MD = """# pgimcode Architecture & Knowledge Base

## Project Overview
pgimcode is a terminal AI coding assistant (Claude Code-style) built with DeepAgents.
It orchestrates specialized sub-agents (reader, editor, executor, planner, verifier)
to perform software engineering tasks in a user's workspace.

## Directory Structure
```
/pgimcode/
  __main__.py          # Module entry point (python -m pgimcode)
  __init__.py          # Package metadata
  agent.py             # RealAgent — graph-based orchestrator
  approval.py          # Approval gates for human-in-the-loop
  chat.py              # ChatSession + ChatRenderer (interactive UI)
  cli.py               # Typer CLI with commands: run, analyze, plan, chat, models
  config.py            # Settings via pydantic-settings + persisted prefs
  context.py           # ContextManager (active events, summaries, pinned items)
  events.py            # Event, EventBus, EventLogWriter, EventType enum
  input_handler.py     # SlashCommandListener, ModelSelector
  mock_agent.py        # MockAgent for testing without LLM
  models.py            # AVAILABLE_MODELS dict (OpenAI + DeepSeek)
  observability.py     # MetricsCollector, TraceRecorder, FailureSnapshot
  planner.py           # TaskPlanner with scored steps
  session.py           # Session dataclass + SessionStore (JSON on disk)
  terminal.py          # RichTerminalRenderer (Live display)
  verification.py      # Verifier for post-edit checks
  agents/
    orchestrator.py    # create_orchestrator — wires sub-agents, backend, tools
    reader.py          # Reader sub-agent
    editor.py          # Editor sub-agent
    executor.py        # Executor sub-agent
    planner.py         # Planner sub-agent
    verifier.py        # Verifier sub-agent
  tools/
    code_reader.py     # Tree-sitter powered code reading tools
    web_fetch.py       # web_fetch(url, timeout) tool
    diff.py, ranker.py, read.py, snapshot.py, symbols.py, test_runner.py
  discovery/
    repo_scanner.py    # File scanning and language detection
    repo_map.py        # RepoMap generation
    language_detector.py, symbol_parser.py
  frontend/            # (Future) web frontend
  memory/              # Long-term memory infrastructure (this!)
    __init__.py
    store.py           # PersistentFileStore (file-based BaseStore)
```

## Key Libraries & Dependencies
- **deepagents** >= 0.6.8 — agent framework (create_deep_agent, sub-agents, backends)
- **langchain-openai** — LLM provider (ChatOpenAI for both OpenAI and DeepSeek)
- **langgraph** — graph engine, checkpointer, store (BaseStore, InMemoryStore)
- **tree-sitter** + **tree-sitter-language-pack** — code parsing
- **pydantic** + **pydantic-settings** — configuration
- **typer** — CLI framework
- **rich** — terminal UI (tables, panels, markdown, syntax highlighting)
- **prompt-toolkit** — interactive input with history
- **platformdirs** — XDG config directories
- **python-ulid** — unique IDs for sessions and events

## Design Patterns
1. **Event-driven orchestration** — EventBus + EventType enum; agents publish events, renderer subscribes
2. **Multi-agent architecture** — Orchestrator spawns specialized sub-agents via DeepAgents
3. **Context management** — Tiered context (active events → summaries → pinned items)
4. **Composite backends** — StoreBackend for persistent memory + StateBackend for session files
5. **In-memory + persistent store** — InMemoryStore for testing, PersistentFileStore for production
6. **File-based long-term memory** — The agent reads/writes markdown files in a StoreBackend

## Agent Memory System
The long-term memory uses DeepAgents' store-backed memory pattern:
- `memory=["/memories/AGENTS.md", "/memories/CHANGES.md"]` — files loaded at startup
- `StoreBackend(namespace=lambda rt: (rt.server_info.user.identity,))` for user-scoped memory
- OR `StoreBackend(namespace=lambda rt: (rt.server_info.assistant_id,))` for agent-scoped memory
- The agent can `edit_file` to update its own memory files
- A `PersistentFileStore` (Implements BaseStore) stores data as JSON files on disk

## Design Decisions
- **Single user** — Current mode: user-scoped memory per session
- **DeepSeek API** as primary LLM provider (default), with OpenAI as fallback
- **LocalShellBackend** with virtual mode for filesystem operations
- **InMemoryStore** for testing → PersistentFileStore for deployed use
"""

SEED_CHANGES_MD = """# pgimcode Change Log

## [Unreleased]

### Added
- `memory/` package with PersistentFileStore (file-based BaseStore implementation)
- Long-term memory integration: agent loads AGENTS.md and CHANGES.md at startup
- Agent can read and update its own memory files across sessions
- `.pgim_memory/` directory stored at project root for persistence
"""


def seed_memory_store(store, namespace: tuple[str, ...]) -> None:
    """Write seed memory files if they do not already exist."""
    # AGENTS.md — architecture knowledge
    existing = store.get(namespace, "/memories/AGENTS.md")
    if existing is None:
        store.put(
            namespace,
            "/memories/AGENTS.md",
            create_file_data(SEED_AGENTS_MD),
        )

    # CHANGES.md — change log
    existing = store.get(namespace, "/memories/CHANGES.md")
    if existing is None:
        store.put(
            namespace,
            "/memories/CHANGES.md",
            create_file_data(SEED_CHANGES_MD),
        )


def read_memory(store, namespace: tuple[str, ...], path: str) -> str | None:
    """Read the content of a memory file, or None."""
    item = store.get(namespace, path)
    if item is None:
        return None
    return item.value.get("content", "")
