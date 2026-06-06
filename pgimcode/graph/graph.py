"""LangGraph builder and compiler for the pgimcode agent."""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from pgimcode.graph.state import AgentState
from pgimcode.graph.nodes import (
    intake_node,
    discovery_node,
    planning_node,
    next_node,
    inspect_node,
    edit_node,
    execute_node,
    verify_node,
    compact_node,
    approval_node,
    finish_node,
)


def build_graph(max_turns: int = 50) -> StateGraph:
    """Build and compile the agent StateGraph."""
    builder = StateGraph(AgentState)

    # Add all nodes
    builder.add_node("intake", intake_node)
    builder.add_node("discovery", discovery_node)
    builder.add_node("planning", planning_node)
    builder.add_node("decision", lambda s: {"current_node": "decision"})
    builder.add_node("inspect", inspect_node)
    builder.add_node("edit", edit_node)
    builder.add_node("execute", execute_node)
    builder.add_node("verify", verify_node)
    builder.add_node("compact", compact_node)
    builder.add_node("approval", approval_node)
    builder.add_node("finish", finish_node)

    # Linear edges: START → intake → discovery → planning → decision
    builder.add_edge(START, "intake")
    builder.add_edge("intake", "discovery")
    builder.add_edge("discovery", "planning")
    builder.add_edge("planning", "decision")

    # Conditional edges from decision based on router output
    builder.add_conditional_edges(
        "decision",
        next_node,
        {
            "inspect": "inspect",
            "edit": "edit",
            "execute": "execute",
            "verify": "verify",
            "compact": "compact",
            "approval": "approval",
            "finish": "finish",
        },
    )

    # Action nodes loop back to decision
    for node in ["inspect", "edit", "execute", "verify", "compact", "approval"]:
        builder.add_edge(node, "decision")

    # Finish ends the graph
    builder.add_edge("finish", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)