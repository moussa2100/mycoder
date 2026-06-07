"""Tests for the LangGraph graph build and execution."""

import asyncio

import pytest

from pgimcode.graph.graph import build_graph


def test_graph_compiles():
    """build_graph() returns a compiled graph object."""
    graph = build_graph()
    assert graph is not None
    # Compiled graph is a StateGraph with a astream method
    assert hasattr(graph, "astream")
    assert hasattr(graph, "ainvoke")


def test_graph_runs_stub():
    """Invoke graph with initial state + config, verify status == completed and turn >= 4."""
    graph = build_graph(max_turns=50)
    config = {"configurable": {"thread_id": "test-1"}}

    initial_state = {
        "session_id": "test-session",
        "task": "test task",
        "mode": "build",
        "turn": 0,
        "max_turns": 50,
        "events": [],
        "active_events": [],
        "summaries": [],
        "pinned": [],
        "repo_map": None,
        "plan": None,
        "current_node": "start",
        "last_tool_result": {},
        "tool_calls": [],
        "status": "running",
        "approval_required": False,
        "approval_reason": "",
        "pending_action": [],
        "token_usage": 0,
        "cost_usd": 0.0,
        "changed_files": [],
        "next_node": "",
    }

    async def run():
        max_turn = 0
        async for chunk in graph.astream(initial_state, config):
            for state_update in chunk.values():
                if state_update.get("turn") is not None:
                    max_turn = max(max_turn, state_update["turn"])
                if state_update.get("status") == "completed":
                    return {"turn": max_turn, "status": "completed"}
        return {"turn": max_turn, "status": "unknown"}

    final_state = asyncio.run(run())

    assert final_state.get("status") == "completed"
    assert final_state.get("turn", 0) >= 4


def test_graph_nodes_exist():
    """Verify all expected nodes are in the compiled graph."""
    graph = build_graph()
    graph_repr = graph.get_graph()
    nodes = set(graph_repr.nodes.keys())

    expected_nodes = {
        "intake",
        "discovery",
        "planning",
        "decision",
        "tool_exec",
        "finish",
    }
    for node in expected_nodes:
        assert node in nodes, f"Missing node: {node}"


def test_graph_conditional_edges():
    """Verify decision node has conditional edges to action nodes."""
    graph = build_graph()
    graph_repr = graph.get_graph()

    # Get all edges with decision as source
    decision_targets = {e.target for e in graph_repr.edges if e.source == "decision"}
    expected_targets = {"tool_exec", "finish"}
    assert decision_targets == expected_targets, (
        f"Decision node should have edges to {expected_targets}, got {decision_targets}"
    )