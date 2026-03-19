
import os
import sys
import logging
from typing import Dict, Any, List
import pandas as pd
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from src.core.archivist import Archivist
from src.core.retriever import Retriever
from src.core.workflow import create_graph
import src.agents.nodes
import src.core.subgraph
from src.tools.lookup import LookupToolSet, Colors
from src.core.llm import get_llm

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("ScenarioTest")

def run_scenario(scenario_name: str, docx_path: str, task: str, expected_behavior: str):
    print("\n" + "="*60)
    print(f">>> 测试场景: {scenario_name} <<<")
    print(f"任务: {task}")
    print(f"文档: {docx_path}")
    print(f"预期: {expected_behavior}")
    print("="*60)
    
    if not os.path.exists(docx_path):
        print(f"{Colors.RED}❌ 文档不存在: {docx_path}{Colors.RESET}")
        return None, None, "Doc Not Found"

    # Initialize per-scenario (clean state)
    archivist = Archivist()
    # Use unique collection name to avoid pollution
    collection_name = f"scenario_{scenario_name.split('.')[0].strip()}_{task}"
    # Sanitize collection name
    collection_name = "".join([c if c.isalnum() else "_" for c in collection_name]).lower()
    
    retriever = Retriever(location=":memory:", collection_name=collection_name)
    
    # Inject
    src.agents.nodes._retriever = retriever
    _lookup_tools = LookupToolSet(retriever)
    
    # Update tools list in-place to ensure all references (like in subgraph.py) see the change
    new_tools = _lookup_tools.get_tools()
    # We need to access the original list object in nodes.py
    # But since we imported src.agents.nodes, we can access it.
    if hasattr(src.agents.nodes, "tools") and isinstance(src.agents.nodes.tools, list):
        src.agents.nodes.tools.clear()
        src.agents.nodes.tools.extend(new_tools)
        # Also ensure subgraph sees the same list (it should if it imported the list object)
        # But for safety, we can clear and extend the list in subgraph too if it's a different object (unlikely)
        if hasattr(src.core.subgraph, "tools") and src.core.subgraph.tools is not src.agents.nodes.tools:
             print(f"{Colors.YELLOW}[WARN] Subgraph tools list is different object! Patching it too.{Colors.RESET}")
             if isinstance(src.core.subgraph.tools, list):
                 src.core.subgraph.tools.clear()
                 src.core.subgraph.tools.extend(new_tools)
    else:
        # Fallback
        src.agents.nodes.tools = new_tools
        src.core.subgraph.tools = new_tools

    # Process
    print(f"{Colors.CYAN}[1/3] 处理文档...{Colors.RESET}")
    chunks = archivist.extract_chunks(docx_path)
    
    # Debug: Print first few chunks paths
    print(f"{Colors.YELLOW}[DEBUG] Chunks Paths:{Colors.RESET}")
    for i, chunk in enumerate(chunks[:5]):
        print(f"  - Chunk {i}: {chunk.get('metadata', {}).get('path')} | Content: {chunk.get('content')[:30]}...")
        
    doc_structure = archivist.generate_document_structure(chunks)
    print(f"{Colors.YELLOW}[DEBUG] Document Structure:\n{doc_structure}{Colors.RESET}")
    
    retriever.index_chunks(chunks)
    
    # Workflow
    app = create_graph()
    
    initial_state = {
        "extraction_results": {},
        "messages": [],
        "next_step": "dispatcher",
        "task_status": "pending",
        "task_list": [task],
        "document_structure": doc_structure,
        "current_task": ""
    }
    
    print(f"{Colors.CYAN}[2/3] 执行提取...{Colors.RESET}")
    final_state = None
    try:
        # Increase timeout or just run
        # LangGraph stream doesn't have a direct timeout, but the underlying LLM calls do.
        # We rely on the fix in worker_node to prevent hangs.
        
        for state in app.stream(initial_state, stream_mode="values"):
            final_state = state
            
    except KeyboardInterrupt:
        print(f"{Colors.YELLOW}⚠️ 用户中断测试{Colors.RESET}")
        return None, None, "Interrupted"
    except Exception as e:
        print(f"{Colors.RED}❌ 执行出错: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return None, None, str(e)

    # Verify
    print(f"{Colors.CYAN}[3/3] 结果验证:{Colors.RESET}")
    res = final_state.get("extraction_results", {}).get(task, {})
    
    value = res.get("value")
    notes = res.get("validation_notes")
    fail_reason = res.get("failure_reason")
    
    print(f"提取值: {value}")
    print(f"校验备注: {notes}")
    print(f"失败原因: {fail_reason}")
    
    return value, notes, fail_reason

def main():
    load_dotenv()
    results = []

    # Scenario 1: Normal Success
    val, notes, fail = run_scenario(
        "1. 正常提取", 
        "data/input/scenarios/scenario_1_success.docx", 
        "合同总价",
        "找到正确金额(100万)，校验通过"
    )
    is_success = val and "100" in str(val) and not fail
    results.append({
        "Scenario": "1. 正常提取",
        "Result": "PASS" if is_success else "FAIL",
        "Details": f"Val: {val}, Fail: {fail}"
    })

    # Scenario 2: Present but Empty
    val, notes, fail = run_scenario(
        "2. 存在但为空", 
        "data/input/scenarios/scenario_2_empty.docx", 
        "签署日期",
        "找到并识别为None/空，校验通过"
    )
    # Check if value is essentially None
    is_none = val is None or str(val).lower() in ["none", "null", "nan", ""]
    results.append({
        "Scenario": "2. 存在但为空",
        "Result": "PASS" if is_none and not fail else "FAIL",
        "Details": f"Val: {val}, Fail: {fail}"
    })

    # Scenario 3: Not Found
    val, notes, fail = run_scenario(
        "3. 完全不存在", 
        "data/input/scenarios/scenario_3_missing.docx", 
        "违约金比例",
        "未找到(None)，校验通过"
    )
    is_none = val is None or str(val).lower() in ["none", "null", "nan", ""]
    results.append({
        "Scenario": "3. 完全不存在",
        "Result": "PASS" if is_none and not fail else "FAIL",
        "Details": f"Val: {val}, Fail: {fail}"
    })

    # Scenario 4: Distributed / Ambiguous (Retry)
    # This scenario is complex, might need retry logic or just check if it gets partial info.
    # We mainly check if it doesn't crash.
    val, notes, fail = run_scenario(
        "4. 分布式信息", 
        "data/input/scenarios/scenario_4_retry.docx", 
        "分期付款详情",
        "提取部分或全部信息，不卡死"
    )
    results.append({
        "Scenario": "4. 分布式信息",
        "Result": "OBSERVE", # Manual check
        "Details": f"Val: {val}, Fail: {fail}"
    })

    print("\n" + "="*60)
    print(">>> 测试总结 <<<")
    df = pd.DataFrame(results)
    print(df.to_markdown(index=False))

if __name__ == "__main__":
    main()
