"""Check what store types are available."""
import sys

from langgraph.store.memory import InMemoryStore
print("InMemoryStore OK")

# Check langgraph.store package
import langgraph.store
print("langgraph.store:", dir(langgraph.store))

# Try to find persistent stores
try:
    from langgraph.store.sqlite import SqliteStore
    print("SqliteStore available")
except ImportError as e:
    print(f"No SqliteStore: {e}")

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    print("SqliteSaver available")
except ImportError as e:
    print(f"No SqliteSaver: {e}")

try:
    from langgraph.store.postgres import PostgresStore
    print("PostgresStore available")
except ImportError as e:
    print(f"No PostgresStore: {e}")

# Try file-based stores
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

class FileBasedStore:
    """A simple file-backed persistent store for memory files.
    
    Stores each (namespace, key) pair as a JSON file on disk.
    Compatible with langgraph.store.base.BaseStore interface.
    """
    def __init__(self, root_dir: str = ".pgim_memory"):
        self._root = Path(root_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
    
    def _path(self, namespace, key):
        """Convert namespace + key to a file path."""
        ns_path = self._root.joinpath(*namespace)
        safe_key = key.replace("/", "_").replace("\\", "_").lstrip("_")
        return ns_path / f"{safe_key}.json"
    
    def put(self, namespace, key, value):
        """Store a value."""
        p = self._path(namespace, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value, indent=2), encoding="utf-8")
    
    def get(self, namespace, key):
        """Retrieve a value."""
        p = self._path(namespace, key)
        if not p.exists():
            return None
        value = json.loads(p.read_text(encoding="utf-8"))
        from langgraph.store.base import Item
        now = datetime.now(timezone.utc)
        return Item(namespace=tuple(namespace), key=key, value=value, created_at=now, updated_at=now)
    
    def search(self, namespace_prefix):
        """List all items under a namespace prefix."""
        ns_path = self._root.joinpath(*namespace_prefix) if namespace_prefix else self._root
        if not ns_path.exists():
            return []
        from langgraph.store.base import Item
        results = []
        for json_file in ns_path.rglob("*.json"):
            key_parts = json_file.stem
            value = json.loads(json_file.read_text(encoding="utf-8"))
            now = datetime.now(timezone.utc)
            results.append(Item(
                namespace=tuple(namespace_prefix) if namespace_prefix else (),
                key=key_parts,
                value=value,
                created_at=now,
                updated_at=now,
            ))
        return results

fs_store = FileBasedStore(".pgim_memory_test")
fs_store.put(("pgimcode",), "test_key", {"content": "hello world"})
item = fs_store.get(("pgimcode",), "test_key")
print("FileBasedStore:", item.value if item else "None")

# Cleanup
import shutil
shutil.rmtree(".pgim_memory_test", ignore_errors=True)

print("Done")
