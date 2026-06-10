"""Check BaseStore abstract methods and TTL support."""
from langgraph.store.base import BaseStore
import inspect

print("BaseStore methods that are abstract:")
for name in sorted(dir(BaseStore)):
    if name.startswith("_"):
        continue
    attr = getattr(BaseStore, name)
    if getattr(attr, "__isabstractmethod__", False):
        sig = inspect.signature(attr)
        print(f"  {name}{sig}")

print()
print(f"has supports_ttl: {hasattr(BaseStore, 'supports_ttl')}")
print(f"has ttl_config: {hasattr(BaseStore, 'ttl_config')}")

# Try to instantiate our PersistentFileStore to check for missing abstract methods
import sys
sys.path.insert(0, r"C:\Users\mouss\Documents\repo\mycoder")
from pgimcode.memory.store import PersistentFileStore
from langgraph.store.base import Item

# Check that it has no abstract methods
try:
    pfs = PersistentFileStore(root_dir=r"C:\Users\mouss\Documents\repo\mycoder\.test_memory")
    print(f"\nPersistentFileStore instantiated OK at {pfs._root}")
    
    # Test a basic round-trip
    ns = ("test",)
    key = "/memories/test.md"
    value = {"content": "Hello memory!", "encoding": "utf-8"}
    pfs.put(ns, key, value)
    
    item = pfs.get(ns, key)
    print(f"Read back: {item.value['content'] if item else 'None'}")
    
    # Clean up
    pfs.delete(ns, key)
    import shutil
    shutil.rmtree(pfs._root, ignore_errors=True)
    print("Cleanup done")
except TypeError as e:
    print(f"Instantiation failed: {e}")
    # Find which methods are still abstract
    missing = []
    for name in sorted(dir(BaseStore)):
        if name.startswith("_"):
            continue
        attr = getattr(BaseStore, name)
        if getattr(attr, "__isabstractmethod__", False):
            impl = getattr(PersistentFileStore, name, None)
            if impl is attr or impl is None:
                missing.append(name)
    if missing:
        print(f"Missing implementations: {missing}")
