# pgimcode

Terminal coding agent with visible micro-steps. LangGraph-powered reasoning engine with real-time observability, approval gates, and tool integration.

---

## Prerequisites

- **Python** 3.11+
- **Poetry** (dependency manager)
- **ripgrep (rg)** — for code search (optional but recommended)
- **OpenAI API key** — for `--real` LLM mode (optional)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd pgimcode

# Install dependencies (includes LangGraph, OpenAI, Rich, Typer)
poetry install

# Verify installation
poetry run pgimcode --version
```

---

## Quick Start

### 1. Run with the mock agent (no API key needed)

```bash
poetry run pgimcode "Add a caching layer to the API"
```

This uses the built-in mock agent that demonstrates the event pipeline without calling external LLMs.

### 2. Run with the real LLM agent

```bash
export OPENAI_API_KEY="sk-..."
poetry run pgimcode "Add a caching layer to the API" --real
```

---

## Configuration

The CLI reads settings from environment variables (prefix: `PGIMCODE_`) or an optional `.env` file.

| Variable | Default | Description |
|----------|---------|-------------|
| `PGIMCODE_OPENAI_API_KEY` | `None` | OpenAI API key for `--real` mode |
| `PGIMCODE_MODEL_NAME` | `gpt-4o` | LLM model name |
| `PGIMCODE_LLM_MAX_TURNS` | `50` | Max graph turns before auto-finish |
| `PGIMCODE_LLM_TEMPERATURE` | `0.2` | LLM sampling temperature |
| `PGIMCODE_SESSION_DIR` | `~/.config/pgimcode/sessions` | Session persistence directory |
| `PGIMCODE_MOCK_DELAY_SECONDS` | `1.5` | Delay between mock agent steps |
| `PGIMCODE_DEFAULT_MODE` | `build` | Default agent mode |

**Example `.env`:**

```
PGIMCODE_OPENAI_API_KEY=sk-...
PGIMCODE_MODEL_NAME=gpt-4o
PGIMCODE_LLM_MAX_TURNS=30
```

---

## CLI Commands

### `run` — Execute a coding task

```bash
pgimcode run <TASK> [OPTIONS]
```

**Positional argument:**
- `TASK` — Natural language description of what to build/fix/test

**Options:**

| Flag | Description |
|------|-------------|
| `--mode` / `-m` | Agent mode: `build`, `plan`, or `review` (default: `build`) |
| `--real` | Use the real LangGraph + LLM agent instead of the mock agent |
| `--resume` / `-r` | Resume from an existing session ID |
| `--plan-only` | Generate and display the plan without running the agent |
| `--dry-run` | Preview what the agent would do without modifying files |
| `--execute-tests` | Run actual tests instead of mocking test execution |
| `--verify` / `-v` | Run post-edit verification checks (syntax, lint, tests) |
| `--auto-approve` | Auto-approve caution-level actions (skip interactive prompts) |
| `--metrics` | Print session metrics (latency, tokens, cost) at completion |
| `--trace-export` | Export trace to a JSONL file, e.g. `--trace-export trace.jsonl` |
| `--failure-snapshot` | Write a `.failure.json` snapshot on FAILED events |
| `--no-color` | Disable colored terminal output |

**Examples:**

```bash
# Basic mock run
poetry run pgimcode run "Fix the login bug"

# Real LLM run with metrics
poetry run pgimcode run "Refactor the auth module" --real --metrics

# Plan only, no execution
poetry run pgimcode run "Add rate limiting" --plan-only

# Resume an interrupted session
poetry run pgimcode run "Fix the login bug" --resume pgim-01HABC...

# Dry run with trace export
poetry run pgimcode run "Update dependencies" --dry-run --trace-export trace.jsonl

# Full pipeline: real agent + tests + verification + metrics
poetry run pgimcode run "Implement OAuth2" \
  --real \
  --execute-tests \
  --verify \
  --metrics \
  --trace-export oauth2-trace.jsonl \
  --failure-snapshot
```

### `analyze` — Analyze a repository

```bash
pgimcode analyze [PATH] [OPTIONS]
```

Scans a repository, detects languages/frameworks, and prints a structured map.

| Flag | Description |
|------|-------------|
| `--output` / `-o` | Output format: `markdown` or `json` (default: `markdown`) |
| `--include-symbols` | Extract symbols from top files |
| `--max-symbol-files` | Max files to parse symbols for (default: `10`) |

**Examples:**

```bash
# Analyze current directory
poetry run pgimcode analyze

# Analyze a specific path with symbols
poetry run pgimcode analyze ./my-project --include-symbols

# JSON output for scripting
poetry run pgimcode analyze ./my-project --output json
```

### `plan` — Generate a plan without executing

```bash
pgimcode plan <TASK> [OPTIONS]
```

Scans the repo, ranks files by relevance, reads top matches, and produces a plan.

| Flag | Description |
|------|-------------|
| `--path` / `-p` | Repository root path (default: `.`) |
| `--max-files` / `-n` | Max files to read (default: `5`) |
| `--include-symbols` / `--no-symbols` | Toggle symbol extraction (default: `on`) |
| `--no-color` | Disable colors |

**Example:**

```bash
poetry run pgimcode plan "Add Redis caching" --max-files 10
```

### `list-sessions` — View past sessions

```bash
poetry run pgimcode list-sessions
```

Displays a table of all stored sessions with ID, task, mode, status, and creation time.

Sessions are persisted as `.meta.json` and `.jsonl` files in the session directory.

### `version` — Show version

```bash
poetry run pgimcode version
```

---

## What Happens During a Run

When you run `pgimcode`, the following pipeline executes:

1. **Session creation** — A unique session ID is generated and metadata is saved to disk.
2. **Event bus setup** — All components (renderer, log writer, metrics collector, trace recorder) subscribe to the event bus.
3. **Discovery** — The repository is scanned: languages, frameworks, entry points, tests, and dependencies are detected.
4. **Planning** — Files are ranked by relevance to the task, and a structured plan with steps is generated.
5. **Execution** — The agent executes steps (inspect, edit, test, verify) while publishing visible events.
6. **Approval gates** — Dangerous actions (file edits, test runs) pause for user approval unless `--auto-approve` is set.
7. **Context compaction** — Old events are summarized automatically to stay within context window limits.
8. **Completion** — The session status is updated and a summary is printed.

### Terminal Display

The terminal shows a live-updating layout with:
- **Header** — App version, session ID, task, mode
- **Current Step** — What the agent is doing right now
- **Event Feed** — Rolling log of the last 12 events with icons and status colors

Event icons:
- 🚀 Session started
- 🔍 Repository scanning
- 📄 File reading
- 📝 Planning
- 🔧 Patch applying
- 🧪 Tests running
- 🔒 Verification
- 🛑 Approval blocked
- ✅ Completed
- ❌ Failed

---

## Observability & Debugging

### Session Metrics (`--metrics`)

At the end of a run, prints a markdown table with:
- Per-step latency (ms)
- Token estimates and cost (USD)
- Tool call counts
- Retry, approval, and compaction counts

### Trace Export (`--trace-export`)

Exports every event as a JSONL line for external analysis:

```bash
poetry run pgimcode run "Fix bug" --trace-export trace.jsonl
cat trace.jsonl | jq '{step, type, duration_ms, status}'
```

### Failure Snapshot (`--failure-snapshot`)

On a FAILED event, writes `<session_id>.failure.json` containing:
- Session metadata
- Last event
- Full context dump (active events, summaries, pinned items)

### Session Logs

Every session produces two files in `~/.config/pgimcode/sessions/`:
- `<session_id>.meta.json` — Session metadata (task, mode, status, timestamps)
- `<session_id>.jsonl` — All events in JSONL format

### Resuming Sessions

Use `--resume <session_id>` to continue a previous session. The LangGraph checkpoint system preserves state between runs.

```bash
# Find your session ID
poetry run pgimcode list-sessions

# Resume
poetry run pgimcode run "Continue fixing the bug" --resume pgim-01HABC...
```

---

## Tool Reference

The agent can invoke the following tools (shown in `--real` mode):

| Tool | Description |
|------|-------------|
| `read_file` | Read full file contents |
| `read_chunk` | Read a specific line range |
| `search_text` | Ripgrep search with context |
| `search_symbol` | Language-aware symbol search |
| `edit_replace_block` | Exact text replacement |
| `edit_patch` | Unified diff application |
| `run_command` | Execute a shell command (allowlist-restricted) |
| `run_tests` | Auto-detect and run test suite |
| `verify_file` | Syntax check (Python via `py_compile`) |

---

## Development

### Running Tests

```bash
poetry run pytest tests/ -q
```

### Adding a New Tool

1. Implement the tool function in `pgimcode/tools/<module>.py`
2. Add the wrapper and OpenAI schema in `pgimcode/graph/tools.py`
3. Register the node logic in `pgimcode/graph/nodes.py`
4. Export from `pgimcode/graph/__init__.py`
5. Add tests in `tests/test_tools.py`

---

## License

MIT
