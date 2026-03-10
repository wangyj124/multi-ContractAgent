from langgraph.graph import StateGraph, END
from langgraph.types import Send
from typing import Literal

from src.core.state import AgentState
from src.agents.nodes import dispatcher_node, aggregator_node
from src.core.subgraph import create_field_extraction_subgraph

def create_graph():
    """
    Creates the LangGraph workflow for parallel contract extraction.
    """
    workflow = StateGraph(AgentState)
    
    workflow.add_node("dispatcher", dispatcher_node)
    workflow.add_node("aggregator", aggregator_node)
    
    # Add the field extraction subgraph as a node
    field_subgraph = create_field_extraction_subgraph()
    workflow.add_node("field_extraction_subgraph", field_subgraph)
    
    workflow.set_entry_point("dispatcher")
    
    def dispatcher_router(state: AgentState):
        next_step = state.get("next_step")
        if next_step == "end":
            return END
        
        # Dispatch logic
        extraction_results = state.get("extraction_results", {})
        task_list = state.get("task_list", [])
        pending_tasks = [task for task in task_list if task not in extraction_results]
        
        # Concurrency Limit: 5
        batch = pending_tasks[:5]
        
        if not batch:
             return END
             
        # Send to subgraph
        # We need to pass the initial state for the subgraph (FieldState)
        return [
            Send("field_extraction_subgraph", {
                "field_current_task": task,
                "document_structure": state.get("document_structure", ""),
                "field_messages": [], # Start fresh history for each field
                "extraction_results": {} # Start empty, result will be merged
            }) for task in batch
        ]

    # The router returns Send objects targeting "field_extraction_subgraph"
    # Or returns END.
    workflow.add_conditional_edges("dispatcher", dispatcher_router, ["field_extraction_subgraph", END])
    
    # After subgraph finishes, go to aggregator
    workflow.add_edge("field_extraction_subgraph", "aggregator")
    
    # From aggregator loop back to dispatcher
    workflow.add_edge("aggregator", "dispatcher")
    
    return workflow.compile()
