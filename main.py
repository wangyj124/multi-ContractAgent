import os
import sys
import logging
import pandas as pd
from typing import List, Dict, Any, Optional
import uuid
from unittest.mock import MagicMock

# Add src to path if needed
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from src.core.archivist import Archivist
from src.core.retriever import Retriever
from src.core.workflow import create_graph
from src.core.schema import ExtractionResult
import src.core.llm
import src.agents.nodes

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
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
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
        # Handle Supervisor
        if self.mode == "supervisor":
            # Input is list of messages
            # Last message is HumanMessage with "Find information for {task}"
            if isinstance(input, list) and len(input) > 0:
                last_msg = input[-1].content
                task = last_msg.replace("Find information for ", "")
            elif isinstance(input, dict):
                 task = input.get("task", "")
            else:
                task = str(input)

            logger.info(f"[Mock Supervisor] Processing task: {task}")
            
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
            # Last message: "Text:\n{text}\n\nExtract {task}."
            if isinstance(input, list) and len(input) > 0:
                content = input[-1].content
            elif isinstance(input, dict):
                content = input.get("text", "") + " " + input.get("task", "")
            else:
                content = str(input)

            # Extract task name from prompt if possible
            task = "Unknown"
            if "Extract " in content:
                # "Extract {task}." -> split by "Extract " take last, remove "."
                # But task might be at end.
                task = content.split("Extract ")[-1].strip().rstrip(".")
            
            logger.info(f"[Mock Worker] Extracting for task: {task}")

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
                validation_notes="Mock extraction"
            )

        return AIMessage(content="Mock response")

def mock_get_llm(model_name: str, temperature: float = 0):
    return MockLLM()

def main():
    # Monkeypatch if needed
    if USE_MOCK_LLM:
        logger.info("Monkeypatching get_llm...")
        src.core.llm.get_llm = mock_get_llm
        src.agents.nodes.get_llm = mock_get_llm

    # 1. Load XT tasks
    xt_path = "data/input/XT.xlsx"
    task_list = []
    if os.path.exists(xt_path):
        logger.info(f"Loading tasks from {xt_path} using XTParser...")
        try:
            from src.core.task_init import XTParser
            parser = XTParser(xt_path)
            xt_tasks = parser.load_tasks()
            # Extract 'focus' as the task name
            task_list = [t['focus'] for t in xt_tasks]
            logger.info(f"Loaded {len(task_list)} tasks: {task_list}")
        except Exception as e:
            logger.error(f"Failed to load tasks via XTParser: {e}")
    else:
        logger.warning(f"{xt_path} not found. Task list will be empty.")

    # 2. Initialize Archivist and Retriever
    logger.info("Initializing Archivist and Retriever...")
    archivist = Archivist() # Defaults to mock embedding internally
    # Use memory for Qdrant and mock embeddings
    retriever = Retriever(location=":memory:", collection_name="contract_chunks", embedding_model="mock")
    
    # Inject retriever into nodes (since nodes.py initializes its own global)
    # We need to update the global _retriever in src.agents.nodes
    # and also re-initialize the tools because tools bind the retriever.
    logger.info("Injecting Retriever into agents...")
    src.agents.nodes._retriever = retriever
    from src.tools.lookup import LookupToolSet
    _lookup_tools = LookupToolSet(retriever)
    src.agents.nodes.tools = _lookup_tools.get_tools()

    # 3. Load and chunk contract
    docx_path = "data/input/contract.docx"
    logger.info(f"Loading and chunking {docx_path}...")
    if not os.path.exists(docx_path):
        logger.error(f"{docx_path} not found!")
        return

    chunks = archivist.extract_chunks(docx_path)
    logger.info(f"Extracted {len(chunks)} chunks.")
    
    # Generate document structure
    logger.info("Generating document structure...")
    doc_structure_str = archivist.generate_document_structure(chunks)
    logger.info("Document structure generated.")

    # 4. Index chunks
    logger.info("Indexing chunks...")
    retriever.index_chunks(chunks)

    # 5. Build Graph
    logger.info("Building Workflow Graph...")
    app = create_graph()

    # 6. Invoke Graph
    logger.info("Invoking Graph...")
    # Initial state
    initial_state = {
        "extraction_results": {},
        "messages": [],
        "next_step": "supervisor", # Start with supervisor
        "task_list": task_list,
        "document_structure": doc_structure_str
    }
    
    # Run the graph
    final_state = app.invoke(initial_state)

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
            "Notes": res.get("validation_notes")
        })
    
    output_df = pd.DataFrame(output_data)
    output_dir = "data/output"
    os.makedirs(output_dir, exist_ok=True)
    output_csv = os.path.join(output_dir, "result.csv")
    output_df.to_csv(output_csv, index=False)
    
    logger.info(f"Success! Results exported to {output_csv}")
    print(output_df)

if __name__ == "__main__":
    main()
