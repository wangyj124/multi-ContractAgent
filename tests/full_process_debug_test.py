import os
import sys
import logging
from dotenv import load_dotenv

# Add src to path if needed
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

logger = logging.getLogger("FullProcessDebug")

try:
    from src.core.archivist import Archivist
    from src.core.retriever import Retriever
    from src.core.subgraph import create_field_extraction_subgraph
    from src.tools.lookup import LookupToolSet
    from langchain_core.messages import ToolMessage, AIMessage, HumanMessage
    import src.agents.nodes
    import src.core.subgraph as subgraph_module
except ImportError as e:
    logger.error(f"Import failed: {e}")
    sys.exit(1)

def print_separator(char="-", length=80):
    print(char * length)

def run_debug_test(task_name="Total Contract Amount"):
    logger.info(f"Starting full process debug test for task: {task_name}")

    # 1. Initialize Components (Archivist, Retriever)
    logger.info("Initializing Archivist and Retriever (Real Embeddings)...")
    
    archivist = Archivist() 
    
    try:
        # Using :memory: for test
        retriever = Retriever(location=":memory:", collection_name="contract_chunks_debug", embedding_model="openai")
    except Exception as e:
        logger.error(f"Failed to initialize Retriever: {e}")
        return
    
    # Inject retriever into nodes
    logger.info("Injecting Retriever into Agents...")
    src.agents.nodes._retriever = retriever
    
    # Re-initialize tools with the real retriever and inject
    _lookup_tools = LookupToolSet(retriever)
    new_tools = _lookup_tools.get_tools()
    src.agents.nodes.tools = new_tools
    subgraph_module.tools = new_tools # Patch the imported tools in subgraph

    # 2. Load and Chunk Document
    docx_path = os.path.join(project_root, "data/input/甘露机岛合同-20181211版最终-签字版（无价格版）.docx")
    logger.info(f"Loading document: {docx_path}")
    
    if not os.path.exists(docx_path):
        logger.error(f"Document not found: {docx_path}")
        return

    chunks = archivist.extract_chunks(docx_path)
    logger.info(f"Extracted {len(chunks)} chunks.")
    
    logger.info("Generating document structure...")
    doc_structure_str = archivist.generate_document_structure(chunks)
    print(f"\n--- DOCUMENT STRUCTURE ---\n{doc_structure_str}\n--------------------------\n")
    logger.info("Document structure generated.")

    logger.info("Indexing chunks...")
    retriever.index_chunks(chunks)
    logger.info("Indexing complete.")

    # 3. Create Subgraph (Field Extraction)
    logger.info("Creating Field Extraction Subgraph...")
    subgraph = create_field_extraction_subgraph()

    # 4. Prepare Initial State
    initial_state = {
        "field_current_task": task_name,
        "document_structure": doc_structure_str,
        "field_messages": [],
        "extraction_results": {},
        "navigation_history": [],
        "field_next_step": "field_supervisor" # Start point
    }

    logger.info("Starting execution stream...")
    print_separator("=")

    # 5. Stream Execution
    try:
        # stream_mode="updates" gives us the updates from each node
        # Set a recursion limit or step limit to prevent infinite loops during debug
        config = {"recursion_limit": 15}
        for event in subgraph.stream(initial_state, stream_mode="updates", config=config):
            for node_name, update in event.items():
                print(f"\nNode: [{node_name}]")
                
                # Check for messages (Tool calls, Tool outputs)
                if "field_messages" in update:
                    messages = update["field_messages"]
                    for msg in messages:
                        if isinstance(msg, AIMessage):
                            if msg.tool_calls:
                                for tc in msg.tool_calls:
                                    print(f"  -> [Supervisor] Decision: Call Tool '{tc['name']}'")
                                    print(f"     Args: {tc['args']}")
                            elif msg.content:
                                print(f"  -> [Supervisor] Thought: {msg.content}")
                        elif isinstance(msg, ToolMessage):
                            print(f"  <- [Tool] Output (ID: {msg.tool_call_id}):")
                            content_preview = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
                            print(f"     {content_preview}")
                        elif isinstance(msg, HumanMessage):
                             print(f"  -> [Validator] Feedback: {msg.content}")

                # Check for extraction results (Worker output)
                if "extraction_results" in update:
                    results = update["extraction_results"]
                    # Usually only the current task is updated
                    if task_name in results:
                        res = results[task_name]
                        # Handle if it's a dict (from model_dump)
                        val = res.get("value")
                        notes = res.get("validation_notes")
                        print(f"  => [Worker/Validator] Extraction Result:")
                        print(f"     Value: {val}")
                        if notes:
                            print(f"     Validation Notes: {notes}")
                        if res.get("failure_reason"):
                            print(f"     Failure Reason: {res.get('failure_reason')}")
                            
                # Check for next step
                if "field_next_step" in update:
                    print(f"  -> Next Step: {update['field_next_step']}")

                print_separator()
        
        logger.info("Debug Test Complete.")
                
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    task = "Total Contract Amount"
    # Allow command line arg for task
    if len(sys.argv) > 1:
        task = sys.argv[1]
    
    run_debug_test(task)