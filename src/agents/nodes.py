import json
from typing import List, Dict, Any, Literal, Optional

from langchain_core.messages import AIMessage, ToolMessage, SystemMessage, HumanMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate

from src.core.state import AgentState
from src.core.llm import get_llm
from src.core.schema import ExtractionResult
from src.tools.lookup import LookupToolSet
from src.core.retriever import Retriever

# Define the extraction tasks (XT list)
XT_TASKS = [
    "Total Amount",
    "Effective Date",
    "Vendor Name",
    "Contract Term",
    "Sign Date",
    "Installment Amounts"
]

# Initialize Retriever and Tools (Globals for now, ideally injected)
# We use a singleton pattern or just module level for simplicity
# In a real app, this might be initialized in main and passed around
_retriever = Retriever(location=":memory:", collection_name="contract_chunks")
_lookup_tools = LookupToolSet(_retriever)
tools = _lookup_tools.get_tools()

def supervisor_node(state: AgentState) -> Dict[str, Any]:
    """
    Supervisor node that manages the extraction workflow.
    It identifies the next task and decides which tool to use to retrieve information.
    """
    extraction_results = state.get("extraction_results", {}) or {}
    
    # 1. Identify next missing field
    next_task = None
    for task in XT_TASKS:
        if task not in extraction_results:
            next_task = task
            break
            
    if not next_task:
        return {"next_step": "finish"}
        
    # 2. Update state with current task
    # Note: We return the update, LangGraph merges it
    
    # 3. Decide on tool usage
    # We use an LLM to decide which tool to call based on the task
    llm = get_llm("gpt-4o", temperature=0) # Use a smart model for supervision
    llm_with_tools = llm.bind_tools(tools)
    
    system_prompt = """You are a supervisor agent responsible for extracting contract information.
    Your goal is to find information for the current task: "{task}".
    You have access to tools to search the document.
    - structural_lookup: Use if you know the likely section (e.g. "Payment Terms").
    - semantic_fallback: Use to search by meaning (e.g. "How much is the contract worth?").
    
    Decide which tool to use to find the information for "{task}".
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Find information for {task}")
    ])
    
    chain = prompt | llm_with_tools
    
    response = chain.invoke({"task": next_task})
    
    return {
        "next_step": "tools",
        "current_task": next_task,
        "messages": [response]
    }

def worker_node(state: AgentState) -> Dict[str, Any]:
    """
    Worker node that extracts information from the retrieved text.
    """
    current_task = state.get("current_task")
    messages = state.get("messages", [])
    
    # Find the last ToolMessage which contains the retrieved text
    # Or just the last message if it's from the tool
    # In LangGraph with ToolNode, the last message should be a ToolMessage
    
    # We look for the most recent ToolMessage
    tool_output = ""
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            tool_output = msg.content
            break
            
    if not tool_output:
        # Fallback if no tool output found (should not happen in normal flow)
        tool_output = "No information found."

    # Use Qwen for extraction as requested
    llm = get_llm("qwen3-30B-A3B-Instruct", temperature=0)
    
    # We want structured output
    structured_llm = llm.with_structured_output(ExtractionResult)
    
    system_prompt = """You are an expert contract analyst.
    Extract the field "{task}" from the provided text.
    If the information is not present, set value to None and error to "Not found".
    The text contains chunks with IDs like [Chunk ID: 123].
    Please include the Source Chunk ID in your response.
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Text:\n{text}\n\nExtract {task}.")
    ])
    
    chain = prompt | structured_llm
    
    try:
        result: ExtractionResult = chain.invoke({"task": current_task, "text": tool_output})
    except Exception as e:
        # Handle parsing errors or LLM errors
        result = ExtractionResult(
            field_name=current_task,
            value=None,
            error=str(e),
            confidence=0.0
        )
        
    # Update extraction results
    # We need to handle the dict update carefully
    # LangGraph merges top-level keys. For dictionaries, it usually replaces them unless a reducer is defined.
    # In AgentState, extraction_results is just a Dict. We should fetch existing, update, and return.
    # Actually, AgentState definition in state.py uses `Dict[str, Any]`.
    # To merge, we usually define a reducer in Annotated, but here we can just read and update.
    # However, if we return `{"extraction_results": new_dict}`, it might overwrite.
    # But since we are inside the node, we have the full state.
    
    current_results = state.get("extraction_results", {}).copy()
    current_results[current_task] = result.model_dump()
    
    return {
        "extraction_results": current_results,
        "next_step": "validator" # Go to validator next
    }

def validator_node(state: AgentState) -> Dict[str, Any]:
    """
    Validator node that checks the extraction result.
    """
    current_task = state.get("current_task")
    extraction_results = state.get("extraction_results", {})
    
    result_data = extraction_results.get(current_task)
    
    if not result_data:
        # Should not happen
        return {"next_step": "supervisor"}
        
    value = result_data.get("value")
    chunk_id = result_data.get("source_chunk_id")
    notes = []
    
    # 1. Null Value Logic
    # Check for "___" or empty string or similar placeholders
    if isinstance(value, str):
        cleaned_value = value.strip()
        if cleaned_value == "___" or cleaned_value == "" or all(c == '_' for c in cleaned_value):
            result_data["value"] = None
            notes.append("Marked as Original Empty due to placeholder.")
            
            # Fetch context to see if we can find real value?
            if chunk_id is not None:
                # Just trigger context retrieval as requested
                _retriever.get_context(chunk_id, window=1)
                notes.append(f"Context retrieved for empty value from chunk {chunk_id}.")

    # 2. Date Order Logic
    # Check if "Sign Date" and "Effective Date" exist
    if current_task == "Effective Date" and "Sign Date" in extraction_results:
        sign_date_res = extraction_results["Sign Date"]
        sign_date = sign_date_res.get("value")
        effective_date = result_data.get("value")
        
        # Only compare if both are strings (simple comparison)
        if isinstance(sign_date, str) and isinstance(effective_date, str):
            if effective_date < sign_date:
                notes.append(f"Warning: Effective Date ({effective_date}) is before Sign Date ({sign_date}).")
                if chunk_id is not None:
                    _retriever.get_context(chunk_id)
                    notes.append(f"Context retrieved due to date mismatch from chunk {chunk_id}.")

    # 3. Amount Conservation Logic
    # Check "Total Amount" vs "Installment Amounts"
    # Assuming "Installment Amounts" is a list of numbers or strings
    if current_task == "Total Amount" and "Installment Amounts" in extraction_results:
        installments_res = extraction_results["Installment Amounts"]
        installments = installments_res.get("value")
        total_amount = result_data.get("value")
        
        if isinstance(installments, list) and (isinstance(total_amount, int) or isinstance(total_amount, float)):
            try:
                # Sum installments (handling strings or numbers)
                inst_sum = sum(float(x) for x in installments if x is not None)
                if abs(inst_sum - float(total_amount)) > 0.01: # float epsilon
                    notes.append(f"Warning: Sum of installments ({inst_sum}) does not match Total Amount ({total_amount}).")
                    if chunk_id is not None:
                        _retriever.get_context(chunk_id)
                        notes.append(f"Context retrieved due to amount mismatch from chunk {chunk_id}.")
            except ValueError:
                pass # Could not parse numbers

    # Update result with notes
    if notes:
        existing_notes = result_data.get("validation_notes")
        if existing_notes:
            notes.insert(0, existing_notes)
        result_data["validation_notes"] = "; ".join(notes)
        
    # Update state with modified result
    extraction_results[current_task] = result_data
        
    return {
        "extraction_results": extraction_results,
        "next_step": "supervisor"
    }
