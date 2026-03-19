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
    YELLOW = '\033[93m'
    BLUE = '\033[94m'

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

    # Check if we just came from tools
    # If the last message is a ToolMessage, it means tools just executed.
    messages = state.get("field_messages", [])
    if messages and isinstance(messages[-1], ToolMessage):
        last_tool_output = messages[-1].content
        
        # Check if tool execution was successful (found something)
        # If tool returned "not found" or similar, we should let Supervisor THINK again to retry with another tool
        # instead of passing empty/error text to Worker.
        # Common failure patterns from src/tools/lookup.py:
        # "未找到路径..."
        # "未找到相关内容..."
        # "重排序后未找到..."
        
        failure_keywords = ["未找到", "No information found", "无法获取内容"]
        is_tool_failure = any(k in last_tool_output for k in failure_keywords) and len(last_tool_output) < 200
        
        # New check for Navigation_Reflector output (usually just a list of paths)
        # If the output looks like a path or list of paths, and NOT full content, we should continue thinking.
        # Heuristic: Check if the last tool called was Navigation_Reflector
        is_navigation_output = False
        if len(messages) >= 2:
             # Find the last AIMessage that initiated this tool call
             # messages list: [... AIMessage(tool_calls), ToolMessage(content)]
             prev_msg = messages[-2]
             if isinstance(prev_msg, AIMessage) and prev_msg.tool_calls:
                 # Check all tool calls in the last message
                 for tc in prev_msg.tool_calls:
                     if tc['name'] == "Navigation_Reflector":
                         is_navigation_output = True
                         break
        
        if not is_tool_failure and not is_navigation_output:
            print(f"{Colors.CYAN}[Field Supervisor] 决策: 工具执行完毕且有内容，转交 Worker 进行提取{Colors.RESET}")
            return {"field_next_step": "worker"}
        elif is_navigation_output:
             print(f"{Colors.CYAN}[Field Supervisor] 决策: 收到路径列表，继续思考以获取具体内容{Colors.RESET}")
        else:
            print(f"{Colors.CYAN}[Field Supervisor] 决策: 工具未找到有效内容，继续思考重试策略{Colors.RESET}")
            # Fall through to LLM logic below
        
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
        print(f"{Colors.CYAN}[Field Supervisor] 思考: {response.content}{Colors.RESET}")

    if response.tool_calls:
        next_step = "tools"
        for tool_call in response.tool_calls:
            decision_msg = f"工具调用: {tool_call['name']} ({tool_call['args']})"
            print(f"{Colors.CYAN}[Field Supervisor] 决策: {decision_msg}{Colors.RESET}")
            navigation_history.append(decision_msg)
    else:
        # If no tool calls, it means the supervisor thinks we have enough info or can't find anything.
        # In this case, we should pass to worker to attempt extraction or report "not found".
        next_step = "worker"
        print(f"{Colors.CYAN}[Field Supervisor] 决策: 无需更多工具，转交 Worker{Colors.RESET}")
    
    return {
        "field_next_step": next_step,
        "field_messages": [response],
        "navigation_history": navigation_history
    }

from langchain_core.output_parsers import JsonOutputParser

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
            print(f"{Colors.BLUE}[Worker] 收到工具输出: {tool_output[:200]}...{Colors.RESET}")
            break
            
    if not tool_output:
        # Fallback if no tool output found (should not happen in normal flow)
        tool_output = "No information found."
        print(f"{Colors.YELLOW}[Worker] 未检测到工具输出，使用默认值。{Colors.RESET}")

    # Use Qwen for extraction as requested
    llm = get_llm(os.environ.get("MODEL_WORKER", "qwen3-30B-A3B-Instruct"), temperature=0)
    
    # We want structured output
    # Since Qwen might have issues with with_structured_output in some environments,
    # we use JsonOutputParser which is more robust.
    parser = JsonOutputParser(pydantic_object=ExtractionResult)
    
    # Load prompt and append format instructions
    prompt_text = _load_prompt("worker")
    prompt_text += "\n请严格按照以下JSON格式输出结果，不要包含任何Markdown标记或其他文本：\n{format_instructions}\n"
    
    prompt = ChatPromptTemplate.from_template(prompt_text)
    
    chain = prompt | llm | parser
    
    try:
        result_dict = chain.invoke({
            "task": current_task, 
            "text": tool_output,
            "format_instructions": parser.get_format_instructions()
        })
        
        # FIX for "Present but Empty" vs "Not Found"
        # If the tool found the path but it's empty (e.g., "1.1 签署日期：__________")
        # the LLM might return None. We need to preserve the source_chunk_id so Validator knows it exists.
        # If result_dict["value"] is None but there's a valid source_snippet, it means it was found but empty.
        
        # We need to extract the chunk_id from tool_output if LLM failed to do so
        if result_dict.get("source_chunk_id") is None and "[Chunk ID:" in tool_output:
            import re
            match = re.search(r'\[Chunk ID:\s*(\d+)\]', tool_output)
            if match:
                result_dict["source_chunk_id"] = match.group(1)

        # Ensure default fields
        if "confidence" not in result_dict:
            result_dict["confidence"] = 1.0
            
        print(f"{Colors.BLUE}[Worker] 提取结果: {json.dumps(result_dict, ensure_ascii=False, indent=2)}{Colors.RESET}")
        
    except Exception as e:
        print(f"{Colors.RED}[Worker] 提取失败: {e}{Colors.RESET}")
        # Handle parsing errors or LLM errors
        result_dict = {
            "field_name": current_task,
            "value": None,
            "error": str(e),
            "confidence": 0.0,
            "validation_notes": None,
            "failure_reason": "Extraction Error"
        }
    
    # Add navigation history to result
    result_dict["navigation_history"] = navigation_history
        
    # Update extraction results
    current_results = state.get("extraction_results", {}).copy()
    current_results[current_task] = result_dict
    
    return {
        "extraction_results": current_results,
        "field_next_step": "validator", # Go to validator next
        "navigation_history": navigation_history
    }

def validator_node(state: FieldState) -> Dict[str, Any]:
    """
    Validator node that checks the extraction result using LLM.
    """
    current_task = state.get("field_current_task")
    extraction_results = state.get("extraction_results", {})
    
    result_data = extraction_results.get(current_task)
    
    if not result_data:
        # Should not happen
        return {"field_next_step": "field_supervisor"}
        
    value = result_data.get("value")
    chunk_id = result_data.get("source_chunk_id")
    
    # Context Expansion Logic
    context_text = "无上下文"
    if chunk_id:
        try:
            # Retrieve specific chunk
            chunk_data = _retriever.get_chunk(int(chunk_id))
            if chunk_data:
                # Get path
                # Metadata might be flattened or in metadata dict depending on how it was indexed
                path = chunk_data.get("path") or chunk_data.get("metadata", {}).get("path")
                
                if path:
                    # Expand to parent scope (e.g. "Chapter 2/2.2" -> "Chapter 2")
                    parts = path.split('/')
                    if len(parts) > 1:
                        parent_path = "/".join(parts[:-1])
                        # Retrieve all chunks in parent scope
                        # Note: search_by_path returns list of dicts (payloads)
                        related_chunks = _retriever.search_by_path(parent_path)
                        
                        # Sort by chunk_id to maintain document order
                        # Ensure chunk_id exists and is sortable
                        related_chunks.sort(key=lambda x: int(x.get('chunk_id', 0)))
                        
                        # Concatenate content
                        texts = []
                        for c in related_chunks:
                            c_text = c.get('content') or c.get('text')
                            if c_text:
                                texts.append(c_text)
                        
                        if texts:
                            context_text = "\n---\n".join(texts)
                            print(f"{Colors.CYAN}[验证器] 上下文扩展成功: {parent_path} (包含 {len(texts)} 个块){Colors.RESET}")
                        else:
                             context_text = chunk_data.get('content') or chunk_data.get('text') or "无法获取内容"
                    else:
                        # Top level, just use chunk content
                        context_text = chunk_data.get('content') or chunk_data.get('text') or "无法获取内容"
                else:
                     context_text = chunk_data.get('content') or chunk_data.get('text') or "无法获取内容"
        except Exception as e:
            print(f"{Colors.RED}[验证器] 获取上下文失败: {e}{Colors.RESET}")

    # Use LLM for validation
    llm = get_llm(os.environ.get("MODEL_VALIDATOR", "qwen3-30B-A3B-Instruct"), temperature=0)
    
    prompt_text = _load_prompt("validator")
    prompt = ChatPromptTemplate.from_template(prompt_text)
    
    chain = prompt | llm
    
    try:
        validation_response = chain.invoke({
            "task": current_task,
            "value": str(value),
            "chunk_id": str(chunk_id) if chunk_id else "Unknown",
            "context": context_text
        })
        content = validation_response.content
        print(f"{Colors.CYAN}[验证器] 模型分析: {content}{Colors.RESET}")
    except Exception as e:
        content = f"验证过程出错: {str(e)}"

    # Parse LLM response for issues (heuristic)
    notes = []
    
    # 2. Extract validity from LLM response
    # It must contain either "验证通过（Valid）" or "验证失败（Invalid）" based on prompt
    is_valid = "验证通过" in content or "Valid" in content
    is_invalid = "验证失败" in content or "Invalid" in content
    
    # Check specifically for "正确地未找到" or "留空" which should be Valid
    is_confirmed_missing_or_empty = "正确地未找到" in content or "留空" in content or "未填写" in content
    
    # Conflict resolution: Trust the explicit marker first
    if "**验证通过（Valid）**" in content or "**通过（Valid）**" in content:
        is_valid = True
        is_invalid = False
    elif "**验证失败（Invalid）**" in content or "**失败（Invalid）**" in content:
        is_invalid = True
        is_valid = False
        
    if is_valid and not is_invalid:
        pass # Success
    elif is_confirmed_missing_or_empty:
        pass # Success (Empty but valid)
    else:
        # Likely failed
        notes.append(content)
        print(f"{Colors.RED}[验证失败] {content[:200]}...{Colors.RESET}")
        
    # Update result with notes
    if notes:
        existing_notes = result_data.get("validation_notes")
        if existing_notes:
            notes.insert(0, existing_notes)
        notes_str = "; ".join(notes)
        result_data["validation_notes"] = notes_str
        
        # Determine failure type
        failure_type = "VALIDATION_ERROR"
        result_data["failure_reason"] = f"{failure_type}: {notes_str}"

    # Update state with modified result
    extraction_results[current_task] = result_data
    
    # If validation failed (notes added), create feedback message and force retry
    if notes:
        # Check max retries
        current_retries = state.get("validation_retries", 0)
        MAX_RETRIES = 3
        
        if current_retries >= MAX_RETRIES:
            print(f"{Colors.RED}[验证器] 超过最大重试次数 ({MAX_RETRIES})，放弃任务: {current_task}{Colors.RESET}")
            # Mark as failed but finished
            result_data["failure_reason"] = f"MAX_RETRIES_EXCEEDED: {notes_str}"
            extraction_results[current_task] = result_data
            return {
                "extraction_results": extraction_results,
                "field_next_step": "finish"
            }
            
        # Check if the failure is actually a valid "Not Found" case
        # Loose check for "Valid" or "通过" to handle LLM variations
        is_confirmed_missing = any("通过" in content or "Valid" in content or "确实未提及" in content for content in notes)
        
        if is_confirmed_missing:
             # It's actually a success
             result_data["validation_notes"] = None # Clear notes
             extraction_results[current_task] = result_data
             return {
                "extraction_results": extraction_results,
                "field_next_step": "finish"
             }
        
        # We remove the task from extraction_results so supervisor sees it as missing and retries
        if current_task in extraction_results:
            del extraction_results[current_task]
            
        feedback_msg = HumanMessage(
            content=f"任务验证失败 '{current_task}': {notes_str}。请尝试再次查找正确信息。",
            name="validator"
        )
        
        # When retrying, we go back to supervisor. 
        # Supervisor will see the feedback message and decide on new tool calls.
        return {
            "extraction_results": extraction_results,
            "field_next_step": "field_supervisor",
            "field_messages": [feedback_msg],
            "validation_retries": current_retries + 1
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
