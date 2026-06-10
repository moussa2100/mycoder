"""Quick test: verify StoreBackend + InMemoryStore wiring."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from deepagents.backends.utils import create_file_data
print('imports OK')

from langgraph.store.memory import InMemoryStore
store = InMemoryStore()
print('store created')

store.put(
    ('pgimcode-agent',),
    '/memories/AGENTS.md',
    create_file_data('# Test memory\nArchitecture knowledge goes here.')
)
print('data put')

item = store.get(('pgimcode-agent',), '/memories/AGENTS.md')
print('Item:', item)
if item:
    print('Item.value type:', type(item.value))
    print('Item.value:', item.value)

d = create_file_data('# Test')
print('create_file_data type:', type(d))
print('create_file_data value:', d)
