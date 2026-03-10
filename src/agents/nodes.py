import json
import os
from typing import List, Dict, Any, Literal, Optional

from langchain_core.messages import AIMessage, ToolMessage, SystemMessage, HumanMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pathlib import Path

from src.core.state import AgentState, FieldState
from src.core.llm import get_llm
from src.core.schema import ExtractionResult
from src.tools.lookup import LookupToolSet
from src.core.retriever import Retriever

class Colors:
    CYAN = '\033[96m'
    RED = '\033[91m'
    RESET = '\033[0m'

def _load_prompt(prompt_name: str) -> str:
    base_path = Path(__file__).parent.parent / "prompts"
    prompt_path = base_path / f"{prompt_name}.txt"
    if not prompt_path.exists():
         raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

# Initialize Retriever and Tools (Globals for now, ideally injected)
# We use a singleton pattern or just module level for simplicity
# In a real app, this might be initialized in main and passed around
_retriever = Retriever(location=":memory:", collection_name="contract_chunks")
_lookup_tools = LookupToolSet(_retriever)
tools = _lookup_tools.get_tools()

def field_supervisor_node(state: FieldState) -> Dict[str, Any]:
    """
    Field Supervisor node that manages the extraction for a SINGLE field.
    It decides which tool to use to retrieve information for the current_task.
    """
    current_task = state.get("field_current_task")
    document_structure = state.get("document_structure", "")
    
    if not current_task:
        # Should not happen in subgraph context if initialized correctly
        return {"field_next_step": "finish"}
        
    # Decide on tool usage
    # We use an LLM to decide which tool to call based on the task
    llm = get_llm(os.environ.get("MODEL_SUPERVISOR", "gpt-4o"), temperature=0) # Use a smart model for supervision
    llm_with_tools = llm.bind_tools(tools)
    
    prompt_text = _load_prompt("supervisor")
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_text),
        MessagesPlaceholder(variable_name="messages")
    ])
    
    chain = prompt | llm_with_tools
    
    # Sliding window for messages
    messages = state.get("field_messages", [])
    if len(messages) > 3:
        messages = messages[-3:]
    
    response = chain.invoke({
        "task": current_task, 
        "document_structure": document_structure,
        "messages": messages
    })
    
    navigation_history = state.get("navigation_history", []) or []

    if response.content:
        # If there is content, print it as thinking process
        print(f"{Colors.CYAN}[思考中] {response.content}{Colors.RESET}")

    if response.tool_calls:
        next_step = "tools"
        for tool_call in response.tool_calls:
            decision_msg = f"调用工具: {tool_call['name']} 参数 {tool_call['args']}"
            print(f"{Colors.CYAN}[决策] {decision_msg}{Colors.RESET}")
            navigation_history.append(decision_msg)
    else:
        next_step = "worker"
    
    return {
        "field_next_step": next_step,
        "field_messages": [response],
        "navigation_history": navigation_history
    }

def worker_node(state: FieldState) -> Dict[str, Any]:
    """
    Worker node that extracts information from the retrieved text.
    """
    current_task = state.get("field_current_task")
    messages = state.get("field_messages", [])
    
    # Find the last ToolMessage which contains the retrieved text
    # Or just the last message if it's from the tool
    # In LangGraph with ToolNode, the last message should be a ToolMessage
    
    # Build navigation history
    navigation_history = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tool_call in msg.tool_calls:
                 navigation_history.append(f"工具调用: {tool_call['name']} ({tool_call['args']})")
        elif isinstance(msg, ToolMessage):
             # Truncate output to avoid huge history
             content_preview = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
             navigation_history.append(f"工具输出: {content_preview}")

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
    llm = get_llm(os.environ.get("MODEL_WORKER", "qwen3-30B-A3B-Instruct"), temperature=0)
    
    # We want structured output
    structured_llm = llm.with_structured_output(ExtractionResult)
    
    prompt_text = _load_prompt("worker")
    prompt = ChatPromptTemplate.from_template(prompt_text)
    
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
    
    # Add navigation history to result
    result.navigation_history = navigation_history
        
    # Update extraction results
    current_results = state.get("extraction_results", {}).copy()
    current_results[current_task] = result.model_dump()
    
    return {
        "extraction_results": current_results,
        "field_next_step": "validator", # Go to validator next
        "navigation_history": navigation_history
    }

def validator_node(state: FieldState) -> Dict[str, Any]:
    """
    Validator node that checks the extraction result.
    """
    current_task = state.get("field_current_task")
    extraction_results = state.get("extraction_results", {})
    
    result_data = extraction_results.get(current_task)
    
    if not result_data:
        # Should not happen
        return {"field_next_step": "field_supervisor"}
        
    value = result_data.get("value")
    chunk_id = result_data.get("source_chunk_id")
    notes = []
    
    # 1. Null Value Logic
    # Check for "___" or empty string or similar placeholders
    if isinstance(value, str):
        cleaned_value = value.strip()
        if cleaned_value == "___" or cleaned_value == "" or all(c == '_' for c in cleaned_value):
            result_data["value"] = None
            notes.append("因占位符标记为原空。")
            
            # Fetch context to see if we can find real value?
            if chunk_id is not None:
                # Just trigger context retrieval as requested
                _retriever.get_context(chunk_id, window=1)
                notes.append(f"为填充空值检索上下文，来自块 {chunk_id}。")

    # 2. Date Order Logic
    # Check if "Sign Date" and "Effective Date" exist
    # NOTE: In parallel execution, we might not have access to other fields yet if they are being processed concurrently!
    # Validation relying on other fields (like Sign Date vs Effective Date) might fail or need to be done in Aggregator?
    # Or we just validate what we have. If Sign Date is missing in local state, we skip this check.
    # In FieldState, extraction_results only has the current task result usually, unless we pass in global results?
    # If we pass in global results in the Send payload, we can check.
    # But other fields might be in progress.
    # So cross-field validation is better done in Aggregator or a final Validator node in the main graph.
    # For now, we'll keep the logic but it might not trigger if data is missing.
    
    if current_task == "Effective Date" and "Sign Date" in extraction_results:
        sign_date_res = extraction_results["Sign Date"]
        sign_date = sign_date_res.get("value")
        effective_date = result_data.get("value")
        
        # Only compare if both are strings (simple comparison)
        if isinstance(sign_date, str) and isinstance(effective_date, str):
            if effective_date < sign_date:
                notes.append(f"警告：生效日期 ({effective_date}) 早于签署日期 ({sign_date})。")
                if chunk_id is not None:
                    _retriever.get_context(chunk_id)
                    notes.append(f"因日期不匹配检索上下文，来自块 {chunk_id}。")

    # 3. Amount Conservation Logic
    if current_task == "Total Amount" and "Installment Amounts" in extraction_results:
        installments_res = extraction_results["Installment Amounts"]
        installments = installments_res.get("value")
        total_amount = result_data.get("value")
        
        if isinstance(installments, list) and (isinstance(total_amount, int) or isinstance(total_amount, float)):
            try:
                # Sum installments (handling strings or numbers)
                inst_sum = sum(float(x) for x in installments if x is not None)
                if abs(inst_sum - float(total_amount)) > 0.01: # float epsilon
                    notes.append(f"警告：分期总和 ({inst_sum}) 与总金额 ({total_amount}) 不匹配。")
                    if chunk_id is not None:
                        _retriever.get_context(chunk_id)
                        notes.append(f"因金额不匹配检索上下文，来自块 {chunk_id}。")
            except ValueError:
                pass # Could not parse numbers

    # Update result with notes
    if notes:
        existing_notes = result_data.get("validation_notes")
        if existing_notes:
            notes.insert(0, existing_notes)
        notes_str = "; ".join(notes)
        result_data["validation_notes"] = notes_str
        
        # Determine failure type and print log
        failure_type = "GENERAL_ERROR"
        if result_data.get("value") is None:
             failure_type = "MISSING_CONTENT"
        elif "日期不匹配" in notes_str or "金额不匹配" in notes_str or "分期总和" in notes_str:
             failure_type = "LOGIC_ERROR"
        
        print(f"{Colors.RED}[验证失败] 类型: {failure_type}, 原因: {notes_str}{Colors.RESET}")
        result_data["failure_reason"] = f"{failure_type}: {notes_str}"

    # Update state with modified result
    extraction_results[current_task] = result_data
    
    # If validation failed (notes added), create feedback message and force retry
    if notes:
        # We remove the task from extraction_results so supervisor sees it as missing and retries
        if current_task in extraction_results:
            del extraction_results[current_task]
            
        feedback_msg = HumanMessage(
            content=f"任务验证失败 '{current_task}': {notes_str}。请尝试再次查找正确信息。",
            name="validator"
        )
        return {
            "extraction_results": extraction_results,
            "field_next_step": "field_supervisor",
            "field_messages": [feedback_msg]
        }
        
    return {
        "extraction_results": extraction_results,
        "field_next_step": "finish" # Success
    }

def dispatcher_node(state: AgentState) -> Dict[str, Any]:
    """
    Dispatcher node that selects a batch of tasks to process in parallel.
    """
    extraction_results = state.get("extraction_results", {})
    task_list = state.get("task_list", [])
    
    # Identify pending tasks
    pending_tasks = [task for task in task_list if task not in extraction_results]
    
    if not pending_tasks:
        return {"next_step": "end"}
        
    # We return dispatch to signal the router to send tasks
    return {"next_step": "dispatch"}

def aggregator_node(state: AgentState) -> Dict[str, Any]:
    """
    Aggregator node that synchronizes parallel branches.
    Since AgentState uses a reducer for extraction_results, the data is already merged.
    This node serves as a check point and loops back to dispatcher.
    """
    return {"next_step": "dispatcher"}
