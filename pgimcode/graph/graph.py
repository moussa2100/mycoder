"""LangGraph builder and compiler for the pgimcode agent."""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from pgimcode.graph.state import AgentState
from pgimcode.graph.nodes import (
    intake_node,
    discovery_node,
    planning_node,
    decision_node,
    execute_tool_node,
    finish_node,
    next_node,
)


def build_graph(max_turns: int = 50) -> StateGraph:
    """Build and compile the agent StateGraph with LLM-powered decision + tool execution."""
    builder = StateGraph(AgentState)

    builder.add_node("intake", intake_node)
    builder.add_node("discovery", discovery_node)
    builder.add_node("planning", planning_node)
    builder.add_node("decision", decision_node)
    builder.add_node("tool_exec", execute_tool_node)
    builder.add_node("finish", finish_node)

    # Linear: START → intake → discovery → planning → decision
    builder.add_edge(START, "intake")
    builder.add_edge("intake", "discovery")
    builder.add_edge("discovery", "planning")
    builder.add_edge("planning", "decision")

    # Decision: either call a tool or finish
    builder.add_conditional_edges(
        "decision",
        next_node,
        {
            "tool_exec": "tool_exec",
            "finish": "finish",
        },
    )

    # Tool execution loops back to decision
    builder.add_edge("tool_exec", "decision")

    # Finish ends the graph
    builder.add_edge("finish", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
