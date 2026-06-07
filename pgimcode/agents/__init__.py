"""pgimcode.agents — Multi-agent architecture powered by DeepAgents."""

from pgimcode.agents.reader import create_reader_subagent
from pgimcode.agents.editor import create_editor_subagent
from pgimcode.agents.executor import create_executor_subagent
from pgimcode.agents.planner import create_planner_subagent
from pgimcode.agents.verifier import create_verifier_subagent
from pgimcode.agents.orchestrator import create_orchestrator

__all__ = [
    "create_reader_subagent",
    "create_editor_subagent",
    "create_executor_subagent",
    "create_planner_subagent",
    "create_verifier_subagent",
    "create_orchestrator",
]
