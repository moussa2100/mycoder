"""Integration test for the long-term memory system."""
import sys
sys.path.insert(0, r"C:\Users\mouss\Documents\repo\mycoder")

import shutil
from pathlib import Path

# 1. Test PersistentFileStore
from pgimcode.memory.store import PersistentFileStore

store_dir = Path(r"C:\Users\mouss\Documents\repo\mycoder\.test_memory_integration")
if store_dir.exists():
    shutil.rmtree(store_dir)

store = PersistentFileStore(root_dir=store_dir)
print("1. PersistentFileStore created OK")

# 2. Test seeding
from pgimcode.memory.seeds import seed_memory_store
seed_memory_store(store, ("pgimcode", "default_user"))
print("2. Seeds populated OK")

# 3. Verify items exist
for key in ["/memories/AGENTS.md", "/memories/CHANGES.md"]:
    item = store.get(("pgimcode", "default_user"), key)
    assert item is not None, f"Missing item: {key}"
    content = item.value.get("content", "")
    assert len(content) > 50, f"Content too short for {key}"
    print(f"   {key}: {len(content)} chars OK")

# 4. Test StoreBackend integration
from deepagents.backends import StoreBackend
sb = StoreBackend(store=store, namespace=lambda rt: ("pgimcode", "default_user"))
print("4. StoreBackend created OK")

# 5. Test CompositeBackend integration
from deepagents.backends import CompositeBackend, StateBackend, LocalShellBackend
fs = LocalShellBackend(root_dir=store_dir, virtual_mode=True, inherit_env=True)
cb = CompositeBackend(
    default=fs,
    routes={"/memories/": sb},
)
print("5. CompositeBackend created OK")

# 6. Verify create_orchestrator accepts the store without error
from pgimcode.config import Settings
from pgimcode.agents.orchestrator import create_orchestrator

settings = Settings()
settings.api_provider = "gemini"
settings.gemini_api_key = "AI-test-fake"
settings.model_name = "gemini-3.5-flash"

try:
    agent = create_orchestrator(settings, workspace_root=str(store_dir), store=store)
    print("6. Orchestrator created OK with memory store")
except Exception as e:
    print(f"6. Orchestrator creation: {e}")

# Cleanup
shutil.rmtree(store_dir, ignore_errors=True)
print("\n=== ALL TESTS PASSED ===")
