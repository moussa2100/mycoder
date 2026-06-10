"""Verify all imports work."""
import sys
sys.path.insert(0, r"C:\Users\mouss\Documents\repo\mycoder")

print("Checking imports...")

from pgimcode.memory.store import PersistentFileStore
print("  store: OK")

from pgimcode.memory.seeds import seed_memory_store
print("  seeds: OK")

from pgimcode.memory import PersistentFileStore as PFS2
print("  __init__: OK")

from pgimcode.agents.orchestrator import create_orchestrator, ORCHESTRATOR_PROMPT
assert "/memories/AGENTS.md" in ORCHESTRATOR_PROMPT
assert "/memories/CHANGES.md" in ORCHESTRATOR_PROMPT
print("  orchestrator: OK (prompt includes memory instructions)")

from pgimcode.agent import RealAgent
print("  agent: OK")

from pgimcode.chat import ChatSession
print("  chat: OK")

print()
print("=== ALL IMPORTS VERIFIED ===")
