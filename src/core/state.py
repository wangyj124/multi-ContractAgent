from typing import TypedDict, List, Dict, Any, Annotated, Union
import operator
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

def merge_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two dictionaries.
    """
    return {**a, **b}

def overwrite(a: Any, b: Any) -> Any:
    """
    Overwrite reducer.
    """
    return b

class AgentState(TypedDict):
    """
    State for the multi-agent contract extraction workflow.
    """
    # Messages history
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Supervisor decision on what to do next
    next_step: str
    
    # Current extraction task (e.g. "Total Amount")
    # In parallel mode, this might be unused or just for the dispatcher
    current_task: str

    # Status of the current task (e.g., "pending", "in_progress", "completed", "failed")
    task_status: str
    
    # Final extraction results
    # Key: field name, Value: extraction result
    # We use a reducer to allow parallel updates to merge results
    extraction_results: Annotated[Dict[str, Any], merge_dicts]
    
    # Document structure context for the supervisor
    # Use overwrite reducer to handle parallel returns (they should be identical)
    document_structure: Annotated[str, overwrite]

    # Dynamic list of tasks to extract
    task_list: List[str]

class FieldState(TypedDict):
    """
    State for the single field extraction subgraph.
    """
    field_messages: Annotated[List[BaseMessage], add_messages]
    field_current_task: str
    document_structure: str
    # extraction_results here is just what this field produced
    extraction_results: Dict[str, Any] 
    field_next_step: str
    field_task_status: str
    navigation_history: List[str]
