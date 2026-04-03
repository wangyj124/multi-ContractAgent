import os
import sys
import logging
import pandas as pd
import argparse
from typing import List, Dict, Any, Optional
import uuid
from tqdm import tqdm
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from src.core.archivist import Archivist
from src.core.retriever import Retriever
from src.core.workflow import create_graph
from src.core.schema import ExtractionResult
from src.utils.dummy_gen import generate_dummy_contract
import src.agents.nodes
from src.tools.lookup import LookupToolSet

# Configure Logging
class TqdmLoggingHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except Exception:
            self.handleError(record)

def setup_logging(debug_mode: bool):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO if not debug_mode else logging.DEBUG)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    # Add Tqdm handler
    handler = TqdmLoggingHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Set third-party loggers to WARNING to avoid noise
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("qdrant_client").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)

logger = logging.getLogger("Main")

def main():
    parser = argparse.ArgumentParser(description="Contract Agent Main Flow")
    parser.add_argument("--debug", action="store_true", help="Enable detailed debug logging")
    parser.add_argument("--dummy", action="store_true", help="Use dummy contract data")
    parser.add_argument("--doc", type=str, help="Path to the document to process")
    parser.add_argument("--tasks", type=str, help="Path to the Excel tasks file")
    args = parser.parse_args()
    
    setup_logging(args.debug)
    
    logger.info(">>> 启动 Contract Agent 工作流 <<<")
    
    # 1. Prepare Document
    docx_path = "data/input/contract.docx"
    if args.doc:
        docx_path = args.doc
    elif args.dummy:
        logger.info("[初始化] 生成测试文档...")
        docx_path = "data/input/dummy_contract.docx"
        generate_dummy_contract(docx_path)
    
    if not os.path.exists(docx_path):
        logger.error(f"文档未找到: {docx_path}")
        return

    # 2. Define Tasks
    if args.tasks:
        from src.core.task_init import XTParser
        try:
            parser = XTParser(args.tasks)
            tasks = parser.load_tasks()
            task_list = [t["focus"] for t in tasks if t.get("focus")]
            logger.info(f"成功从 {args.tasks} 加载 {len(task_list)} 个任务")
        except Exception as e:
            logger.error(f"加载任务文件失败: {e}")
            return
    else:
        # For testing, we use a fixed list. In production, load from Excel/User input.
        task_list = [
            "合同编号", 
            "买方名称", 
            "卖方名称", 
            "合同总价", 
            "预付款比例",
            "质保金比例",
            "交货期", # Might be missing in dummy
            "签署日期"
        ]
    logger.info(f"[任务列表] 待提取字段 ({len(task_list)}): {task_list}")

    # 3. Initialize Core Components
    logger.info("[初始化] 启动 Archivist & Retriever...")
    embedding_model = os.environ.get("MODEL_EMBEDDING", "qwen3-embedding-8B")
    archivist = Archivist(embedding_model_name=embedding_model)
    # Use memory for speed
    retriever = Retriever(location=":memory:", collection_name="contract_chunks", embedding_model=embedding_model)
    
    # Inject dependencies
    src.agents.nodes._retriever = retriever
    _lookup_tools = LookupToolSet(retriever)
    src.agents.nodes.tools = _lookup_tools.get_tools()
    
    # 4. Process Document
    logger.info("[处理文档] 开始文档切片与结构化...")
    chunks = archivist.extract_chunks(docx_path)
    logger.info(f"[处理文档] 提取完成，共 {len(chunks)} 个文本块")
    
    doc_structure = archivist.generate_document_structure(chunks)
    if args.debug:
        logger.debug(f"[文档结构]预览:\n{doc_structure}")
        
    # 5. Indexing
    logger.info("[索引] 建立向量索引...")
    retriever.index_chunks(chunks)
    
    # 6. Build Workflow
    logger.info("[工作流] 构建多智能体图...")
    app = create_graph()
    
    initial_state = {
        "extraction_results": {},
        "messages": [],
        "next_step": "dispatcher",
        "task_status": "pending",
        "task_list": task_list,
        "document_structure": doc_structure,
        "current_task": "" # Not used in parallel dispatcher but schema requires it? No, TypedDict is flexible if not required
    }
    
    # 7. Execute Workflow
    logger.info("[执行] 开始提取任务...")
    final_state = initial_state
    
    # Use tqdm for overall progress
    with tqdm(total=len(task_list), desc="字段提取进度", unit="field") as pbar:
        # Stream workflow updates
        # "values" mode yields the state after each step
        last_completed_count = 0
        
        for state in app.stream(initial_state, stream_mode="values"):
            final_state = state
            
            # Check completion
            results = state.get("extraction_results", {})
            completed_count = len(results)
            
            if completed_count > last_completed_count:
                delta = completed_count - last_completed_count
                pbar.update(delta)
                last_completed_count = completed_count
                
                # Log newly completed items
                if args.debug:
                    # Find diff
                    pass # TODO: detailed logs of what finished
            
            if completed_count == len(task_list):
                # All done
                break
                
    # 8. Export Results
    logger.info("[输出] 导出结果...")
    results = final_state.get("extraction_results", {})
    
    output_data = []
    for task in task_list:
        res = results.get(task, {})
        # If result is just a dict, use it. If it's None (failed/missing), handle it.
        if not res:
            res = {"value": "N/A", "confidence": 0.0, "validation_notes": "未提取"}
            
        output_data.append({
            "Field": task,
            "Value": res.get("value"),
            "Source Chunk ID": res.get("source_chunk_id"),
            "Confidence": res.get("confidence"),
            "Notes": res.get("validation_notes"),
            "Failure Reason": res.get("failure_reason", "")
        })
        
    df = pd.DataFrame(output_data)
    print("\n" + "="*50)
    print(df.to_markdown(index=False))
    print("="*50 + "\n")
    
    output_path = "data/output/extraction_results.csv"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info(f"结果已保存至 {output_path}")

if __name__ == "__main__":
    main()
