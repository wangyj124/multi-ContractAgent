import pytest
from unittest.mock import MagicMock
import sys
import os

# Add src to path if not already there
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.tools.lookup import LookupToolSet

def test_structural_lookup():
    mock_retriever = MagicMock()
    # Mock search_by_path return
    mock_retriever.search_by_path.return_value = [
        {"text": "Chunk 1 content", "path": "Chapter 1/1.1"},
        {"text": "Chunk 2 content", "path": "Chapter 1/1.1/1.1.1"}
    ]
    
    toolset = LookupToolSet(mock_retriever)
    result = toolset.structural_lookup("Chapter 1/1.1")
    
    mock_retriever.search_by_path.assert_called_once_with("Chapter 1/1.1")
    assert "Chunk 1 content" in result
    assert "Chunk 2 content" in result
    assert "\n\n" in result

def test_semantic_fallback():
    mock_retriever = MagicMock()
    # Mock search return
    mock_retriever.search.return_value = [
        {"score": 0.9, "payload": {"text": "Relevant chunk 1"}},
        {"score": 0.8, "payload": {"text": "Relevant chunk 2"}}
    ]
    
    toolset = LookupToolSet(mock_retriever)
    result = toolset.semantic_fallback("payment terms")
    
    mock_retriever.search.assert_called_once_with("payment terms", k=5)
    assert "Relevant chunk 1" in result
    assert "Relevant chunk 2" in result

def test_get_tools():
    mock_retriever = MagicMock()
    toolset = LookupToolSet(mock_retriever)
    tools = toolset.get_tools()
    
    assert len(tools) == 2
    names = [t.name for t in tools]
    assert "structural_lookup" in names
    assert "semantic_fallback" in names

if __name__ == "__main__":
    pytest.main([__file__])
