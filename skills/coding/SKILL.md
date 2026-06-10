---
name: Python Coding Standards
description: Python coding conventions, async patterns, and Poetry dependency management for the pgimcode project.
---

# Python Coding Standards

## Async Patterns
Follow this table for async/sync decisions:

| Situation | Correct approach |
|---|---|
| Calling async from async | `await func()` |
| Calling many async tasks | `await asyncio.gather(...)` |
| Calling async from app startup/script | `asyncio.run(main())` |
| Calling blocking sync from async | `await asyncio.to_thread(func)` |
| Inside FastAPI/Jupyter/event loop | never use `asyncio.run()` |
| Sync function needs async work | redesign to async, or call at top-level boundary only |

The best long-term design is: pick one execution model per layer. Keep infrastructure clients async if your app is async, and avoid mixing sync/async deep inside service methods.

## Poetry Dependency Management
- When adding a new Python library import, first check `pyproject.toml`
- If not listed, run `poetry add <package-name>` — never manually edit pyproject.toml
- If the library is a transitive dependency, no action needed

## Code Style
- Use type hints everywhere
- Prefer dataclasses for data containers
- Use `__future__` annotations at the top of every module
- Follow SOLID principles
- Keep functions small and focused
