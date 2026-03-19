
import os
import sys
import logging
from tqdm import tqdm
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from src.core.archivist import Archivist
from src.core.retriever import Retriever
from src.core.workflow import create_graph
from src.utils.dummy_gen import generate_dummy_contract
import src.agents.nodes
from src.tools.lookup import LookupToolSet

# Setup simple logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("TestSingleFlow")

def test_single_flow():
    load_dotenv()
    
    print("\n" + "="*50)
    print(">>> 快速验证流程：单问题 + 最大重试测试 <<<")
    print("="*50 + "\n")
    
    # 1. Generate Dummy Contract
    docx_path = "data/input/test_single_contract.docx"
    generate_dummy_contract(docx_path)
    
    # 2. Initialize Components
    archivist = Archivist()
    retriever = Retriever(location=":memory:", collection_name="test_single")
    
    # Inject dependencies
    src.agents.nodes._retriever = retriever
    _lookup_tools = LookupToolSet(retriever)
    src.agents.nodes.tools = _lookup_tools.get_tools()
    
    # 3. Process Document
    print("[1/4] 处理文档...")
    chunks = archivist.extract_chunks(docx_path)
    doc_structure = archivist.generate_document_structure(chunks)
    retriever.index_chunks(chunks)
    
    # 4. Build Graph
    app = create_graph()
    
    # 5. Define ONE Task
    # Using a task that exists: "合同总价" -> Should succeed
    # Using a task that is tricky/ambiguous to test retry: "不可抗力通知期限" (Not in dummy gen) -> Should fail retry loop
    
    target_task = "不可抗力通知期限" 
    print(f"[2/4] 开始提取任务: {target_task}")
    print("      (预期行为：Worker找不到 -> Validator报错 -> 重试3次 -> 最终失败并输出原因)")
    
    initial_state = {
        "extraction_results": {},
        "messages": [],
        "next_step": "dispatcher",
        "task_status": "pending",
        "task_list": [target_task],
        "document_structure": doc_structure,
        "current_task": ""
    }
    
    # 6. Run Workflow
    print("[3/4] 执行工作流...")
    final_state = None
    
    try:
        for state in app.stream(initial_state, stream_mode="values"):
            final_state = state
            
            # Print extraction progress
            res = state.get("extraction_results", {}).get(target_task)
            if res:
                retry_count = state.get("validation_retries", 0) # This might be in FieldState, not AgentState
                # Actually AgentState merges results, but doesn't keep track of individual field retries in the top level state easily
                # Retries are local to the subgraph.
                # However, when subgraph updates extraction_results, we can see the notes.
                pass
                
    except Exception as e:
        print(f"Workflow Error: {e}")

    # 7. Verify Result
    print("\n[4/4] 验证结果:")
    result = final_state.get("extraction_results", {}).get(target_task)
    
    if result:
        print(f"Value: {result.get('value')}")
        print(f"Notes: {result.get('validation_notes')}")
        print(f"Failure Reason: {result.get('failure_reason')}")
        
        if "MAX_RETRIES_EXCEEDED" in str(result.get("failure_reason")):
            print("✅ 成功验证：系统正确触发了最大重试机制并终止了循环。")
        else:
            print("⚠️ 警告：未触发最大重试错误 (可能是找到了信息或者逻辑不同)")
    else:
        print("❌ 错误：未生成提取结果。")

if __name__ == "__main__":
    test_single_flow()
