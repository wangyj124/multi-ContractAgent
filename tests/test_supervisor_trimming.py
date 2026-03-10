
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.nodes import supervisor_node
from langchain_core.messages import HumanMessage, AIMessage

@pytest.fixture
def mock_get_llm():
    with patch("src.agents.nodes.get_llm") as mock:
        yield mock

@pytest.fixture
def mock_tools():
    with patch("src.agents.nodes.tools", new=[]) as mock:
        yield mock

def test_supervisor_node_message_trimming(mock_get_llm, mock_tools):
    # Setup mock LLM and chain
    mock_llm_instance = MagicMock()
    mock_get_llm.return_value = mock_llm_instance
    
    mock_chain = MagicMock()
    # Mock the chain structure: prompt | llm_with_tools
    # supervisor_node calls:
    # llm = get_llm(...)
    # llm_with_tools = llm.bind_tools(...)
    # chain = prompt | llm_with_tools
    # response = chain.invoke(...)
    
    # We need to intercept the invoke call on the chain.
    # The chain is created inside the function, so we can't easily mock it directly 
    # unless we mock the components that create it.
    
    # However, chain.invoke takes the input dict.
    # Let's see how `supervisor_node` constructs the chain.
    # It uses `ChatPromptTemplate.from_messages` and `|` operator.
    
    # A better way might be to mock `ChatPromptTemplate` or just check the call to `llm.bind_tools`.
    # But the trimming happens *before* invoke, and the trimmed messages are passed to invoke.
    # So we need to inspect the arguments passed to chain.invoke.
    
    # Since chain is a local variable, we can mock `ChatPromptTemplate` to return a mock object
    # that when piped with something returns our mock chain.
    
    with patch("src.agents.nodes.ChatPromptTemplate") as MockPromptTemplate:
        mock_prompt = MagicMock()
        MockPromptTemplate.from_messages.return_value = mock_prompt
        
        # mock_prompt | llm_with_tools -> chain
        mock_chain = MagicMock()
        mock_prompt.__or__.return_value = mock_chain
        
        # Setup state with 5 messages
        state = {
            "task_list": ["Task 1"],
            "extraction_results": {},
            "document_structure": "Doc Structure",
            "messages": [
                HumanMessage(content="1"),
                AIMessage(content="2"),
                HumanMessage(content="3"),
                AIMessage(content="4"),
                HumanMessage(content="5")
            ]
        }
        
        # Call supervisor_node
        supervisor_node(state)
        
        # Verify chain.invoke was called
        assert mock_chain.invoke.called
        
        # Get arguments passed to invoke
        call_args = mock_chain.invoke.call_args
        inputs = call_args[0][0]
        
        # Check messages in inputs
        messages = inputs["messages"]
        assert len(messages) == 3
        assert messages[0].content == "3"
        assert messages[1].content == "4"
        assert messages[2].content == "5"

