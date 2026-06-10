"""Debug create_file_data signature."""
from deepagents.backends.utils import create_file_data
import inspect

sig = inspect.signature(create_file_data)
print("signature:", sig)

src = inspect.getsource(create_file_data)
print("source:")
print(src[:800])
