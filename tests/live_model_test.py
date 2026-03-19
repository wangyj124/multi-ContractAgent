import os
import sys
import logging
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv

# Add src to path if needed (relative path handling)
# This assumes the script is run from the project root or tests/ directory
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Load .env first
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING) 
logging.getLogger("openai").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Verify API Key is present
if not os.environ.get("OPENAI_API_KEY"):
    logger.error("未找到 OPENAI_API_KEY 环境变量。请检查您的 .env 文件。")
    # We don't exit here to allow import checks, but it will likely fail later
else:
    logger.info("已找到 OPENAI_API_KEY。")

try:
    from src.core.archivist import Archivist
    from src.core.retriever import Retriever
    from src.core.workflow import create_graph
    import src.agents.nodes
    from src.tools.lookup import LookupToolSet
    from src.core.task_init import XTParser
    from langchain_core.messages import AIMessage
except ImportError as e:
    logger.error(f"导入模块失败：{e}")
    sys.exit(1)

def main():
    # 1. Load XT tasks
    xt_path = os.path.join(project_root, "data/input/XT.xlsx")
    task_list = []
    
    if os.path.exists(xt_path):
        logger.info(f"正在使用 XTParser 从 {xt_path} 加载任务...")
        try:
            parser = XTParser(xt_path)
            xt_tasks = parser.load_tasks()
            # Extract 'focus' as the task name, defaulting to empty list if key missing
            task_list = [t.get('focus', 'Unknown') for t in xt_tasks if 'focus' in t]
            logger.info(f"已加载 {len(task_list)} 个任务。")
        except Exception as e:
            logger.error(f"通过 XTParser 加载任务失败：{e}")
            # Fallback for testing
            task_list = ["Total Contract Amount", "Payment Terms"]
    else:
        logger.warning(f"未找到 {xt_path}。使用默认测试任务。")
        task_list = ["Total Contract Amount", "Payment Terms"]

    if not task_list:
        logger.warning("未加载任务。退出。")
        return

    # 2. Initialize Archivist and Retriever (Real Embeddings)
    logger.info("正在使用 OpenAI 嵌入初始化 Archivist 和 Retriever...")
    
    # Initialize Archivist (it uses get_llm internally for summaries)
    archivist = Archivist() 
    
    # Initialize Retriever with OpenAI embeddings
    # Ensure OPENAI_API_KEY is available for this
    try:
        retriever = Retriever(location=":memory:", collection_name="contract_chunks", embedding_model="openai")
    except Exception as e:
        logger.error(f"初始化 Retriever 失败：{e}")
        return
    
    # Inject retriever into nodes
    # This overrides the global variables in src.agents.nodes
    logger.info("正在向 Agent 注入 Retriever...")
    src.agents.nodes._retriever = retriever
    
    # Re-initialize tools with the real retriever and inject
    _lookup_tools = LookupToolSet(retriever)
    new_tools = _lookup_tools.get_tools()
    src.agents.nodes.tools = new_tools
    
    # Also need to inject into subgraph module because it imported 'tools' directly
    import src.core.subgraph as subgraph_module
    subgraph_module.tools = new_tools
    # And we need to re-create the graph because create_field_extraction_subgraph uses the imported tools
    # Actually create_graph calls create_field_extraction_subgraph which uses the global 'tools' in subgraph module
    # So patching src.core.subgraph.tools should work IF create_graph is called AFTER patching.
    # create_graph is imported at top level.
    # We call create_graph() in main(), so it should use the patched tools.


    # 3. Load and chunk contract
    docx_path = os.path.join(project_root, "data/input/甘露机岛合同-20181211版最终-签字版（无价格版）.docx")
    logger.info(f"正在加载并分块 {docx_path}...")
    if not os.path.exists(docx_path):
        logger.error(f"未找到 {docx_path}！")
        return

    chunks = archivist.extract_chunks(docx_path)
    logger.info(f"已提取 {len(chunks)} 个块。")
    
    # Generate document structure
    logger.info("正在生成文档结构...")
    doc_structure_str = archivist.generate_document_structure(chunks)
    logger.info("文档结构生成完毕。")

    # 4. Index chunks
    logger.info("正在建立索引...")
    retriever.index_chunks(chunks)

    # 5. Build Graph
    logger.info("正在构建工作流图...")
    app = create_graph()

    # 6. Invoke Graph
    logger.info("正在调用图...")
    initial_state = {
        "extraction_results": {},
        "messages": [],
        "next_step": "supervisor", # Depending on graph entry point, might need adjustment
        "task_status": "Initial_Search",
        "task_list": task_list,
        "document_structure": doc_structure_str
    }
    
    logger.info("正在流式执行图...")
    final_state = initial_state
    
    # Use tqdm to track progress
    with tqdm(total=len(task_list), desc="正在处理字段", unit="field") as pbar:
        try:
            # stream_mode="values" returns the full state at each step
            for state in app.stream(initial_state, stream_mode="values"):
                final_state = state
                
                # Monitor Supervisor thought process
                # We look for the latest message in the state
                # Note: 'messages' in global state might be sparse if subgraphs handle messages
                # But 'extraction_results' should be updating
                
                # Check for field_messages if they propagate up, or just check global messages
                # In this architecture, it seems messages might be handled within subgraphs (field_supervisor)
                # and might not bubble up to global state 'messages' list unless explicitly returned.
                # However, we can monitor 'extraction_results' updates.
                
                current_results = state.get("extraction_results", {})
                completed_count = len(current_results)
                
                # Update progress bar
                if completed_count > pbar.n:
                    pbar.n = completed_count
                    pbar.refresh()
                
                if pbar.n < len(task_list):
                     pbar.set_description(f"正在处理字段 ({pbar.n}/{len(task_list)})")
                else:
                     pbar.set_description("正在完成...")
                     
        except Exception as e:
            logger.error(f"图执行期间出错：{e}")
            # Continue to export whatever we have

    # 7. Export results
    results = final_state.get("extraction_results", {})
    output_data = []
    
    logger.info(f"正在处理 {len(results)} 个结果...")
    
    for task, res in results.items():
        # Handle Pydantic object or dict
        if hasattr(res, "model_dump"):
            res_dict = res.model_dump()
        elif isinstance(res, dict):
            res_dict = res
        else:
            res_dict = {"value": str(res)}
            
        output_data.append({
            "Task": task,
            "Value": res_dict.get("value"),
            "Source Chunk": res_dict.get("source_chunk_id"),
            "Confidence": res_dict.get("confidence"),
            "Notes": res_dict.get("validation_notes"),
            "Failure Reason": res_dict.get("failure_reason"),
            # Optional: Add navigation history length or summary
            "History Steps": len(res_dict.get("navigation_history", [])) if res_dict.get("navigation_history") else 0
        })
    
    if output_data:
        output_df = pd.DataFrame(output_data)
        output_dir = os.path.join(project_root, "data/output")
        os.makedirs(output_dir, exist_ok=True)
        output_csv = os.path.join(output_dir, "result_live.csv")
        output_df.to_csv(output_csv, index=False)
        
        logger.info(f"成功！结果已导出至 {output_csv}")
        print(output_df)
    else:
        logger.warning("没有要导出的结果。")

if __name__ == "__main__":
    main()
