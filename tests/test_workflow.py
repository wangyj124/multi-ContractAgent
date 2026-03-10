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
    # And then return "Final Answer" to trigger worker.
    
    supervisor_response_tool = AIMessage(
        content="",
        tool_calls=[{
            "name": "structural_lookup",
            "args": {"path": "Payment"},
            "id": "call_123"
        }]
    )
    
    supervisor_response_final = AIMessage(
        content="Final Answer",
        tool_calls=[]
    )
    
    # Sequence:
    # 1. Task 1: Call Tool
    # 2. Task 1: Final Answer (Router -> Worker)
    # 3. Task 2: Call Tool
    # 4. Task 2: Final Answer (Router -> Worker)
    # 5. Finish (Task list empty) -> handled by supervisor_node returning next_step="finish" before invoking LLM?
    # Wait, supervisor_node checks task_list first. If empty, returns finish. LLM not invoked.
    # So we need 4 responses for the 2 tasks.
    
    supervisor_with_tools.side_effect = [
        supervisor_response_tool,
        supervisor_response_final,
        supervisor_response_tool,
        supervisor_response_final
    ]
    
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
    # Worker is called twice (once per task)
    # Since it's treated as callable in the chain
    worker_structured.return_value = worker_result
    
    # Run the graph
    app = create_graph()
    
    # Initial state
    initial_state = {
        "messages": [],
        "extraction_results": {},
        "task_list": ["Total Amount", "Effective Date"]
    }
    
    # Inject data
    from src.agents.nodes import _retriever
    _retriever.index_chunks([{"text": "The Total Amount is $1000.", "path": "Payment/1.1"}])
    
    # Run
    # Increase recursion limit just in case
    events = list(app.stream(initial_state, config={"recursion_limit": 20}, stream_mode="values"))
    
    # Check results
    final_state = events[-1]
    
    # Verify Supervisor was called multiple times
    assert supervisor_with_tools.call_count >= 2
    
    # Verify Worker was called multiple times
    assert worker_structured.call_count >= 1
    
    # Verify Extraction Results
    results = final_state.get("extraction_results", {})
    assert "Total Amount" in results
    assert results["Total Amount"]["value"] == 1000.0
    
    # Since we mocked worker to return same result for both tasks, 
    # "Effective Date" will also have value 1000.0 (and field_name "Total Amount" inside the object, technically mismatch but works for test)
    # Actually worker_node uses current_task to prompt, but our mock returns fixed object.
    # The node puts it into extraction_results[current_task].
    assert "Effective Date" in results


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
        # With new logic, if notes are present, the task is removed from results to trigger retry
        # and a message is added.
        assert "Vendor Name" not in result["extraction_results"]
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert "Original Empty" in result["messages"][0].content
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
        assert "Effective Date" not in result["extraction_results"]
        assert "messages" in result
        assert "before Sign Date" in result["messages"][0].content
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
        assert "Total Amount" not in result["extraction_results"]
        assert "messages" in result
        assert "Sum of installments" in result["messages"][0].content
        assert mock_retriever.get_context.called

if __name__ == "__main__":
    # Manually run if needed
    pytest.main([__file__])
