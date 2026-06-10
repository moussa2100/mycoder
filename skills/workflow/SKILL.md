---
name: Workflow Patterns
description: Standard workflows for planning, editing, verifying, and reviewing code changes.
---

# Workflow Patterns

## Standard Edit Workflow
1. **Read** — Use tree-sitter tools (`code_outline`, `read_code`, `read_symbol`) to understand the file
2. **Plan** — Delegate to the planner subagent for complex changes
3. **Edit** — Use `edit_file` for small changes, `write_file` for new files
4. **Verify** — Delegate to the verifier subagent to check correctness
5. **Execute** — Run tests or build commands via the executor subagent

## Code Review Checklist
- SOLID violations (mixed responsibilities, oversized classes)
- DRY violations (duplicated logic)
- Missing error handling (empty inputs, edge cases, exceptions)
- Async correctness (no `asyncio.run()` inside async functions)
- Missing type hints
- Algorithmic complexity (accidental O(n²))
- Missing Poetry dependency entries for new imports
