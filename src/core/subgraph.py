from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from typing import Literal

from src.core.state import FieldState
from src.agents.nodes import field_supervisor_node, worker_node, validator_node
import src.agents.nodes as nodes

def create_field_extraction_subgraph():
    """
    Creates the subgraph for extracting a single field.
    """
    workflow = StateGraph(FieldState)
    
    workflow.add_node("field_supervisor", field_supervisor_node)
    workflow.add_node("tools", ToolNode(nodes.tools, messages_key="field_messages"))
    workflow.add_node("worker", worker_node)
    workflow.add_node("validator", validator_node)
    
    workflow.set_entry_point("field_supervisor")
    
    def router(state) -> Literal["tools", "worker"]:
        next_step = state.get("field_next_step")
        if next_step == "tools":
            return "tools"
        return "worker"

    workflow.add_conditional_edges("field_supervisor", router)
    
    workflow.add_edge("tools", "field_supervisor")
    workflow.add_edge("worker", "validator")
    
    def validator_router(state) -> Literal["field_supervisor", "finish"]:
        next_step = state.get("field_next_step")
        if next_step == "field_supervisor":
            return "field_supervisor"
        return "finish" # Maps to END

    workflow.add_conditional_edges("validator", validator_router, {"field_supervisor": "field_supervisor", "finish": END})
    
    return workflow.compile()
