from typing import TypedDict, List, Dict, Any, Annotated, Union
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    State for the multi-agent contract extraction workflow.
    """
    # Messages history
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Supervisor decision on what to do next
    next_step: str
    
    # Current extraction task (e.g. "Total Amount")
    current_task: str
    
    # Final extraction results
    # Key: field name, Value: extraction result
    extraction_results: Dict[str, Any]
    
    # Document structure context for the supervisor
    document_structure: str
