import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage
from src.core.schema import ExtractionResult
from src.core.workflow import create_graph

@pytest.fixture
def mock_llm():
    with patch("src.agents.nodes.get_llm") as mock_get:
        yield mock_get

def test_workflow_execution(mock_llm):
    """
    Test the full workflow with mocked LLMs.
    """
    # Setup Supervisor Mock
    supervisor_llm = MagicMock()
    supervisor_with_tools = MagicMock()
    
    # Setup Worker Mock
    worker_llm = MagicMock()
    worker_structured = MagicMock()
    
    # Configure get_llm to return appropriate mocks based on model_name
    def get_llm_side_effect(model_name, **kwargs):
        if "gpt-4o" in model_name:
            return supervisor_llm
        elif "qwen" in model_name:
            return worker_llm
        return MagicMock()
        
    mock_llm.side_effect = get_llm_side_effect
    
    # Supervisor chain mocking
    # It calls bind_tools then invoke
    supervisor_llm.bind_tools.return_value = supervisor_with_tools
    
    # We want supervisor to return a tool call for the first task "Total Amount"
    # And then maybe stop or continue.
    # Since the graph loops, we need to handle multiple calls if we want to test full loop.
    # Let's test one iteration.
    
    supervisor_response = AIMessage(
        content="",
        tool_calls=[{
            "name": "structural_lookup",
            "args": {"path": "Payment"},
            "id": "call_123"
        }]
    )
    supervisor_with_tools.invoke.return_value = supervisor_response
    supervisor_with_tools.return_value = supervisor_response
    
    # Worker chain mocking
    # It calls with_structured_output then invoke
    worker_llm.with_structured_output.return_value = worker_structured
    
    worker_result = ExtractionResult(
        field_name="Total Amount",
        value=1000.0,
        confidence=0.9,
        source_snippet="Total Amount: $1000",
        source_chunk_id=123
    )
    worker_structured.invoke.return_value = worker_result
    worker_structured.return_value = worker_result
    
    # Run the graph
    app = create_graph()
    
    # Initial state
    initial_state = {
        "messages": [],
        "extraction_results": {}
    }
    
    # Execute one step (or until interrupt)
    # Since we didn't mock the tool execution, the ToolNode will try to execute "structural_lookup".
    # We need to make sure "structural_lookup" works or is mocked.
    # It uses the real LookupToolSet which uses real Retriever (mocked backend).
    # So it should be fine, just returns "No content found" if empty.
    
    # We can inject some data into Retriever to make it return something.
    from src.agents.nodes import _retriever
    _retriever.index_chunks([{"text": "The Total Amount is $1000.", "path": "Payment/1.1"}])
    
    # Run
    # We use stream to see steps
    events = list(app.stream(initial_state, stream_mode="values"))
    
    # Check results
    final_state = events[-1]
    
    # Verify Supervisor was called
    assert supervisor_with_tools.invoke.called or supervisor_with_tools.called
    
    # Verify Worker was called
    assert worker_structured.invoke.called or worker_structured.called
    
    # Verify Extraction Results
    results = final_state.get("extraction_results", {})
    assert "Total Amount" in results
    assert results["Total Amount"]["value"] == 1000.0
    
    # Verify loop behavior
    # The supervisor should have been called again for the next task
    # But our mock supervisor returns the same thing every time?
    # If it returns "structural_lookup" again, it might loop indefinitely if we don't handle it.
    # However, `supervisor_node` logic:
    # 1. Identify next missing field.
    # If "Total Amount" is done, next is "Effective Date".
    # So supervisor is called with "Effective Date".
    # Our mock returns "structural_lookup" (path="Payment") again.
    # That's fine, tool executes, worker extracts (same mock result).
    # It will overwrite "Total Amount" if the task was "Total Amount".
    # But since task is "Effective Date", worker will extract "Effective Date" with value 1000.0 (mock).
    # So eventually all tasks will be filled.
    
    # To prevent infinite loop if something goes wrong, LangGraph has recursion limit.
    # But let's check if we have at least one success.
    
    assert len(results) >= 1

def test_validator_logic():
    """
    Test the validator node logic including Null Value, Date Order, and Amount Conservation.
    """
    from src.agents.nodes import validator_node
    
    # Mock retriever
    with patch("src.agents.nodes._retriever") as mock_retriever:
        mock_retriever.get_context.return_value = [{"text": "context"}]
        
        # Test 1: Null Value
        state = {
            "current_task": "Vendor Name",
            "extraction_results": {
                "Vendor Name": {
                    "field_name": "Vendor Name",
                    "value": "___",
                    "source_chunk_id": 1
                }
            }
        }
        result = validator_node(state)
        res_data = result["extraction_results"]["Vendor Name"]
        assert res_data["value"] is None
        assert "Original Empty" in res_data["validation_notes"]
        assert mock_retriever.get_context.called
        
        # Test 2: Date Order
        mock_retriever.reset_mock()
        state = {
            "current_task": "Effective Date",
            "extraction_results": {
                "Sign Date": {"value": "2023-01-01"},
                "Effective Date": {
                    "field_name": "Effective Date",
                    "value": "2022-01-01",
                    "source_chunk_id": 2
                }
            }
        }
        result = validator_node(state)
        res_data = result["extraction_results"]["Effective Date"]
        assert "before Sign Date" in res_data["validation_notes"]
        assert mock_retriever.get_context.called

        # Test 3: Amount Conservation
        mock_retriever.reset_mock()
        state = {
            "current_task": "Total Amount",
            "extraction_results": {
                "Installment Amounts": {"value": [100.0, 200.0]},
                "Total Amount": {
                    "field_name": "Total Amount",
                    "value": 500.0,
                    "source_chunk_id": 3
                }
            }
        }
        result = validator_node(state)
        res_data = result["extraction_results"]["Total Amount"]
        assert "Sum of installments" in res_data["validation_notes"]
        assert mock_retriever.get_context.called

if __name__ == "__main__":
    # Manually run if needed
    pytest.main([__file__])
