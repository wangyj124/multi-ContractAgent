import pytest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage
from src.core.schema import ExtractionResult
from src.core.workflow import create_graph

@pytest.fixture
def mock_llm():
    # Patch get_llm in src.agents.nodes because that's where the nodes are defined
    with patch("src.agents.nodes.get_llm") as mock_get:
        yield mock_get

def test_parallel_workflow_execution(mock_llm):
    """
    Test the parallel workflow with mocked LLMs.
    """
    # Setup Supervisor Mock (Field Supervisor)
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
    supervisor_llm.bind_tools.return_value = supervisor_with_tools
    
    # Logic for Field Supervisor:
    # It receives inputs: {"task": ..., "messages": ...}
    # We want to simulate:
    # Task A: Tool Call -> Final Answer
    # Task B: Final Answer (Directly)
    
    def supervisor_invoke_side_effect(input_val, **kwargs):
        # input_val is likely a list of messages or ChatPromptValue
        messages = []
        if hasattr(input_val, "to_messages"):
            messages = input_val.to_messages()
        elif isinstance(input_val, list):
            messages = input_val
            
        # Extract task from System Message
        task = "Unknown"
        for m in messages:
            if m.type == "system":
                if "Task A" in m.content:
                    task = "Task A"
                elif "Task B" in m.content:
                    task = "Task B"
                break
        
        # Check history for tool output
        # History messages are appended
        has_tool_output = any(m.type == "tool" for m in messages)
        
        if task == "Task A":
            if not has_tool_output:
                # First call: Return Tool Call
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "structural_lookup",
                        "args": {"path": "Section A"},
                        "id": "call_A"
                    }]
                )
            else:
                # Second call: Return Final Answer
                return AIMessage(content="Final Answer")
                
        elif task == "Task B":
            return AIMessage(content="Final Answer")
            
        return AIMessage(content="Final Answer")

    supervisor_with_tools.invoke.side_effect = supervisor_invoke_side_effect
    supervisor_with_tools.side_effect = supervisor_invoke_side_effect
    
    # Worker chain mocking
    worker_llm.with_structured_output.return_value = worker_structured
    
    def worker_invoke_side_effect(input_val, **kwargs):
        # input_val is prompt string or messages
        content = ""
        if isinstance(input_val, str):
            content = input_val
        elif hasattr(input_val, "to_string"):
            content = input_val.to_string()
        elif isinstance(input_val, list):
            content = str([m.content for m in input_val])
            
        task = "Unknown"
        if "Task A" in content:
            task = "Task A"
        elif "Task B" in content:
            task = "Task B"
            
        return ExtractionResult(
            field_name=task,
            value=f"Value for {task}",
            confidence=0.9,
            source_snippet="mock",
            source_chunk_id=1
        )
        
    worker_structured.invoke.side_effect = worker_invoke_side_effect
    worker_structured.side_effect = worker_invoke_side_effect
    
    # Run the graph
    app = create_graph()
    
    # Initial state
    initial_state = {
        "messages": [],
        "extraction_results": {},
        "task_list": ["Task A", "Task B"],
        "document_structure": "Mock Structure"
    }
    
    # Run
    # Use invoke instead of stream for simplicity in parallel execution check
    final_state = app.invoke(initial_state, config={"recursion_limit": 20})
    
    # Verify Results
    results = final_state.get("extraction_results", {})
    
    assert "Task A" in results
    assert results["Task A"]["value"] == "Value for Task A"
    
    assert "Task B" in results
    assert results["Task B"]["value"] == "Value for Task B"
    
    # Verify Supervisor was called at least 3 times (2 for A, 1 for B)
    # Note: calls might happen in any order
    # Check call_count on the object itself, as RunnableSequence might call it directly
    assert supervisor_with_tools.call_count >= 3
    
    # Verify Worker was called 2 times
    assert worker_structured.call_count == 2

if __name__ == "__main__":
    pytest.main([__file__])
