"""Long-term memory module for pgimcode.

Provides a persistent file-based store and helpers to seed and retrieve
agent memory files (architecture knowledge, change logs, etc.).
"""

from pgimcode.memory.store import PersistentFileStore

__all__ = ["PersistentFileStore"]
