
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.state import FieldState
from src.core.subgraph import create_field_subgraph
from src.agents.nodes import _retriever

def test_field_subgraph_integration():
    print("Setting up test data...")
    # 1. Setup Data
    # Re-initialize to ensure clean state
    # We are modifying the global singleton _retriever from src.agents.nodes
    # This will recreate the collection in memory
    _retriever.__init__(location=":memory:", collection_name="test_contract")
    
    mock_text = "The Total Contract Value shall be $50,000.00, payable in installments."
    # We need to ensure embedding dimension is correct for the mock model
    # The default mock uses 1536 dim
    _retriever.index_chunks([{"text": mock_text, "path": "section/1", "content": mock_text}])
    
    print("Data indexed.")
    
    # 2. Build Graph
    print("Building subgraph...")
    app = create_field_subgraph()
    
    # 3. Invoke
    print("Invoking subgraph...")
    initial_state = {
        "messages": [],
        "current_task": "Total Amount",
        "document_structure": "Section 1: Payment",
        "extraction_results": {},
        "next_step": "start",
        "task_status": "pending"
    }
    
    # Recursion limit might need to be set if the loop is long, but default is usually enough
    result = app.invoke(initial_state)
    
    # 4. Verify
    print("Result Extraction:", result.get("extraction_results"))
    
    extraction_results = result.get("extraction_results", {})
    if "Total Amount" in extraction_results:
        res = extraction_results["Total Amount"]
        value = res.get("value")
        print(f"Extracted Value: {value}")
        
        # Simple assertions
        assert value is not None, "Value should not be None"
        # Check for 50000 or 50,000
        assert "50,000" in str(value) or "50000" in str(value), f"Expected 50,000 in {value}"
        print("TEST PASSED")
    else:
        print("TEST FAILED: 'Total Amount' not found in results.")
        print(result)

if __name__ == "__main__":
    test_field_subgraph_integration()
