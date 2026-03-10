import os
import sys
import logging
import pandas as pd
from typing import List, Dict, Any, Optional
import uuid
from tqdm import tqdm
from unittest.mock import MagicMock

# Add src to path if needed
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from src.core.archivist import Archivist
from src.core.retriever import Retriever
from src.core.workflow import create_graph
from src.core.schema import ExtractionResult
import src.core.llm
import src.agents.nodes
import src.core.archivist
import src.tools.lookup

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global flag
USE_MOCK_LLM = False

# Check API Key
if not os.environ.get("OPENAI_API_KEY"):
    logger.warning("OPENAI_API_KEY not found. Using Mock LLM.")
    USE_MOCK_LLM = True

# Mock classes
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel

class MockLLM(Runnable):
    def __init__(self, mode="default"):
        self.mode = mode

    def bind_tools(self, tools, **kwargs):
        return MockLLM(mode="supervisor")

    def with_structured_output(self, schema, **kwargs):
        return MockLLM(mode="worker")

    def invoke(self, input, config: Optional[RunnableConfig] = None, **kwargs):
        # Normalize input to messages if possible
        messages = []
        if hasattr(input, "to_messages"):
            messages = input.to_messages()
        elif isinstance(input, list):
            messages = input
        
        # Handle Supervisor
        if self.mode == "supervisor":
            task = ""
            if messages:
                last_msg = messages[-1].content
                if isinstance(last_msg, str):
                    task = last_msg.replace("Find information for ", "")
            elif isinstance(input, dict):
                # Fallback for dict input if not converted to messages
                task = input.get("task", "")
                if not task and input.get("messages"):
                     msgs = input.get("messages")
                     if msgs:
                         last_msg = msgs[-1].content
                         if isinstance(last_msg, str):
                             task = last_msg.replace("Find information for ", "")
            else:
                task = str(input)

            logger.info(f"[模拟主管] 正在处理任务: {task}")
            
            # Check for previous failures to avoid loops
            if messages:
                for msg in reversed(messages):
                    if isinstance(msg, ToolMessage) and "未找到" in msg.content:
                        logger.info("[模拟主管] 上一次工具调用失败。返回最终答案。")
                        return AIMessage(content="最终答案：无法使用模拟工具找到信息。")
            
            tool_name = "structural_lookup"
            tool_args = {"path": "Chapter 1"} # Default
            
            # Simple keyword matching for tool selection
            if any(k in task for k in ["金额", "Amount", "Payment", "付款", "Financials"]):
                tool_name = "structural_lookup"
                tool_args = {"path": "Chapter 2"}
            elif any(k in task for k in ["日期", "Date", "Term", "期限"]):
                tool_name = "structural_lookup"
                tool_args = {"path": "Chapter 3"}
            
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": tool_name,
                    "args": tool_args,
                    "id": f"call_{uuid.uuid4()}"
                }]
            )

        # Handle Worker
        elif self.mode == "worker":
            # Input is list of messages
            content = ""
            if messages:
                content = messages[-1].content
            elif isinstance(input, dict):
                content = input.get("text", "") + " " + input.get("task", "")
            else:
                content = str(input)

            # Extract task name from prompt if possible
            task = "未知"
            # Debug logging
            # logger.info(f"DEBUG: content type: {type(content)}")
            # logger.info(f"DEBUG: content preview: {str(content)[-100:]}")
            
            if "提取 " in str(content):
                # "Extract {task}." -> split by "Extract " take last, remove "."
                # But task might be at end.
                task = str(content).split("提取 ")[-1].strip().rstrip(".")
            
            logger.info(f"[模拟工人] 正在提取任务: {task}")

            # Return mock result based on task keywords
            value = "Mock Value"
            if any(k in task for k in ["Total Amount", "合同金额"]):
                value = 1000000
            elif any(k in task for k in ["Installment", "Payment", "付款方式"]):
                value = [500000, 500000] # List for installments
            elif any(k in task for k in ["Sign Date", "签署日期"]):
                value = "2023-01-01"
            elif any(k in task for k in ["Effective Date", "生效日期"]):
                value = "2023-01-10"
            
            return ExtractionResult(
                field_name=task,
                value=value,
                source_chunk_id=1,
                confidence=0.95,
                validation_notes="模拟提取"
            )

        # Handle Default (Reranking, Summarization, etc.)
        content_str = str(input)
        if isinstance(input, list) and len(input) > 0:
             content_str = input[-1].content
        
        if "Score the following text" in content_str or "relevance score" in content_str or "评分" in content_str:
             return AIMessage(content="评分：9\n理由：高度相关的模拟内容。")
        
        if "Summarize" in content_str or "summarize" in content_str or "总结" in content_str:
             return AIMessage(content="摘要：这是内容的模拟摘要。")

        return AIMessage(content="模拟响应")

def mock_get_llm(model_name: str, temperature: float = 0):
    return MockLLM()

def main():
    # Monkeypatch if needed
    if USE_MOCK_LLM:
        logger.info("正在修补 get_llm...")
        # Patch the original source
        src.core.llm.get_llm = mock_get_llm
        
        # Patch all modules that imported it
        src.agents.nodes.get_llm = mock_get_llm
        
        src.core.archivist.get_llm = mock_get_llm
        
        src.tools.lookup.get_llm = mock_get_llm

    # 1. Load XT tasks
    xt_path = "data/input/XT.xlsx"
    task_list = []
    if os.path.exists(xt_path):
        logger.info(f"正在使用 XTParser 加载任务...")
        try:
            from src.core.task_init import XTParser
            parser = XTParser(xt_path)
            xt_tasks = parser.load_tasks()
            # Extract 'focus' as the task name
            task_list = [t['focus'] for t in xt_tasks]
            logger.info(f"已加载 {len(task_list)} 个任务: {task_list}")
        except Exception as e:
            logger.error(f"通过 XTParser 加载任务失败: {e}")
    else:
        logger.warning(f"{xt_path} 未找到。任务列表将为空。")

    # 2. Initialize Archivist and Retriever
    logger.info("正在初始化 Archivist 和 Retriever...")
    archivist = Archivist() # Defaults to mock embedding internally
    # Use memory for Qdrant and mock embeddings
    retriever = Retriever(location=":memory:", collection_name="contract_chunks", embedding_model="mock")
    
    # Inject retriever into nodes (since nodes.py initializes its own global)
    # We need to update the global _retriever in src.agents.nodes
    # and also re-initialize the tools because tools bind the retriever.
    logger.info("正在向 Agent 注入 Retriever...")
    src.agents.nodes._retriever = retriever
    from src.tools.lookup import LookupToolSet
    _lookup_tools = LookupToolSet(retriever)
    src.agents.nodes.tools = _lookup_tools.get_tools()

    # 3. Load and chunk contract
    docx_path = "data/input/contract.docx"
    logger.info(f"正在加载并分块 {docx_path}...")
    if not os.path.exists(docx_path):
        logger.error(f"{docx_path} not found!")
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
    # Initial state
    initial_state = {
        "extraction_results": {},
        "messages": [],
        "next_step": "supervisor", # Start with supervisor
        "task_status": "Initial_Search",
        "task_list": task_list,
        "document_structure": doc_structure_str
    }
    
    # Run the graph
    # final_state = app.invoke(initial_state)
    logger.info("正在流式执行图...")
    final_state = initial_state
    
    with tqdm(total=len(task_list), desc="正在处理字段", unit="field") as pbar:
        # Using stream_mode="values" to get the full state at each step
        for state in app.stream(initial_state, stream_mode="values"):
            final_state = state
            
            # Update progress based on completed tasks
            current_results = state.get("extraction_results", {})
            pbar.n = len(current_results)
            pbar.refresh()
            
            # Update description based on count
            if pbar.n < len(task_list):
                 pbar.set_description(f"正在处理字段 ({pbar.n}/{len(task_list)})")
            else:
                 pbar.set_description("正在完成...")

    # 7. Export results
    results = final_state.get("extraction_results", {})
    output_data = []
    for task, res in results.items():
        # res is a dict (model_dump of ExtractionResult)
        output_data.append({
            "Task": task,
            "Value": res.get("value"),
            "Source Chunk": res.get("source_chunk_id"),
            "Confidence": res.get("confidence"),
            "Notes": res.get("validation_notes"),
            "Navigation History": res.get("navigation_history"),
            "Failure Reason": res.get("failure_reason")
        })
    
    output_df = pd.DataFrame(output_data)
    output_dir = "data/output"
    os.makedirs(output_dir, exist_ok=True)
    output_csv = os.path.join(output_dir, "result.csv")
    output_df.to_csv(output_csv, index=False)
    
    logger.info(f"成功！结果已导出至 {output_csv}")
    print(output_df)

if __name__ == "__main__":
    main()
