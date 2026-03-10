import pytest
from unittest.mock import MagicMock, patch
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

@patch('src.tools.lookup.get_llm')
def test_semantic_fallback(mock_get_llm):
    mock_llm_instance = MagicMock()
    mock_get_llm.return_value = mock_llm_instance
    
    # 1. Rerank score for chunk 1
    # 2. Rerank score for chunk 2
    # 3. Report generation
    mock_llm_instance.invoke.side_effect = [
        MagicMock(content="Score: 9"), # Chunk 1
        MagicMock(content="Score: 8"), # Chunk 2
        MagicMock(content="Found relevant chunks:\n- [Chunk ID: 1] Relevant chunk 1\n- [Chunk ID: 2] Relevant chunk 2") # Report
    ]

    mock_retriever = MagicMock()
    # Mock search return
    mock_retriever.search.return_value = [
        {"score": 0.9, "payload": {"text": "Relevant chunk 1", "chunk_id": 1}, "id": 1},
        {"score": 0.8, "payload": {"text": "Relevant chunk 2", "chunk_id": 2}, "id": 2}
    ]
    
    toolset = LookupToolSet(mock_retriever)
    result = toolset.semantic_fallback("payment terms")
    
    # Verify search called without filter (or filter=None)
    mock_retriever.search.assert_called_once()
    args, kwargs = mock_retriever.search.call_args
    assert args[0] == "payment terms"
    assert kwargs.get("filter") is None
    
    assert "Relevant chunk 1" in result
    assert "Relevant chunk 2" in result

@patch('src.tools.lookup.get_llm')
def test_semantic_fallback_with_filter(mock_get_llm):
    mock_llm_instance = MagicMock()
    mock_get_llm.return_value = mock_llm_instance
    # Mock rerank scores - keep all
    # Only 1 result, so no report generation, just return content directly
    mock_llm_instance.invoke.return_value = MagicMock(content="Score: 9")

    mock_retriever = MagicMock()
    mock_retriever.search.return_value = [
        {"score": 0.9, "payload": {"text": "Filtered chunk 1", "path": "Chapter 1", "chunk_id": 1}, "id": 1}
    ]
    
    toolset = LookupToolSet(mock_retriever)
    result = toolset.semantic_fallback("payment", path_filter="Chapter 1")
    
    # Verify search was called with a filter
    mock_retriever.search.assert_called_once()
    args, kwargs = mock_retriever.search.call_args
    assert args[0] == "payment"
    assert kwargs["k"] == 10 # Default k is 10
    assert kwargs["filter"] is not None
    
    # Check if filter has correct structure (optional, depends on implementation details)
    # Since we can't easily check internal object properties without importing models, just checking not None is good start.
    assert "Filtered chunk 1" in result

def test_get_tools():
    mock_retriever = MagicMock()
    toolset = LookupToolSet(mock_retriever)
    tools = toolset.get_tools()
    
    assert len(tools) == 4
    names = [t.name for t in tools]
    assert "structural_lookup" in names
    assert "semantic_fallback" in names
    assert "Navigation_Reflector" in names
    assert "Context_Expander" in names

if __name__ == "__main__":
    pytest.main([__file__])
