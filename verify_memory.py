"""Full verification of the memory module."""
import sys
sys.path.insert(0, r"C:\Users\mouss\Documents\repo\mycoder")

import shutil
from pathlib import Path

# 1
from pgimcode.memory.store import PersistentFileStore
print("1. store module: OK")

# 2
from pgimcode.memory.seeds import seed_memory_store, SEED_AGENTS_MD, SEED_CHANGES_MD
print(f"2. seeds module: OK (AGENTS.md: {len(SEED_AGENTS_MD)} chars, CHANGES.md: {len(SEED_CHANGES_MD)} chars)")

# 3
store = PersistentFileStore(root_dir=r"C:\Users\mouss\Documents\repo\mycoder\.test_verify")
seed_memory_store(store, ("pgimcode", "default_user"))

a = store.get(("pgimcode", "default_user"), "/memories/AGENTS.md")
assert a is not None and "pgimcode" in a.value["content"]
c = store.get(("pgimcode", "default_user"), "/memories/CHANGES.md")
assert c is not None and "Change Log" in c.value["content"]
print("3. seed -> store round-trip: OK")

# 4
store2 = PersistentFileStore(root_dir=r"C:\Users\mouss\Documents\repo\mycoder\.test_verify")
a2 = store2.get(("pgimcode", "default_user"), "/memories/AGENTS.md")
assert a2 is not None
print(f"4. cross-instance persistence: OK ({len(a2.value['content'])} chars)")

# Cleanup
shutil.rmtree(r"C:\Users\mouss\Documents\repo\mycoder\.test_verify", ignore_errors=True)
print()
print("=== ALL VERIFICATION CHECKS PASSED ===")
