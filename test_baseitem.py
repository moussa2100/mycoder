"""Check BaseStore API."""
from langgraph.store.base import BaseStore, Item
import inspect

sig = inspect.signature(Item.__init__)
print("Item.__init__:", sig)

# Minimal Item construction
try:
    i = Item(namespace=["test"], key="k", value={"content": "hello"}, created_at="now", updated_at="now")
    print("Item created:", i)
except Exception as e:
    print("Item creation error:", e)
