"""Inspect InMemoryStore to understand the BaseStore API."""
from langgraph.store.memory import InMemoryStore
import inspect

# List all public methods
print("InMemoryStore methods:")
for name in sorted(dir(InMemoryStore)):
    if name.startswith("_"):
        continue
    obj = getattr(InMemoryStore, name)
    if callable(obj):
        sig = inspect.signature(obj)
        print(f"  {name}{sig}")
