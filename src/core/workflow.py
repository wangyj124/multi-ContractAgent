from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from src.core.state import AgentState
from src.agents.nodes import supervisor_node, worker_node, validator_node, tools

def create_graph():
    """
    Creates the LangGraph workflow for contract extraction.
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("worker", worker_node)
    workflow.add_node("validator", validator_node)

    # Set entry point
    workflow.set_entry_point("supervisor")

    # Define conditional edges from supervisor
    def supervisor_router(state: AgentState) -> Literal["tools", "end"]:
        # Check next_step
        next_step = state.get("next_step")
        if next_step == "finish":
            return "end"
        
        # If tool calls are present in the last message, go to tools
        messages = state.get("messages", [])
        if messages and hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
            return "tools"
            
        # Fallback (should not happen in this design if supervisor always calls tools)
        return "end"

    workflow.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "tools": "tools",
            "end": END
        }
    )

    # Define edges
    # From tools to worker (as per requirement)
    workflow.add_edge("tools", "worker")
    
    # From worker to validator
    workflow.add_edge("worker", "validator")
    
    # From validator back to supervisor
    workflow.add_edge("validator", "supervisor")

    return workflow.compile()
