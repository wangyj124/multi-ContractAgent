
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.tools.lookup import LookupToolSet
from src.core.retriever import Retriever

@pytest.fixture
def mock_retriever():
    retriever = MagicMock(spec=Retriever)
    return retriever

@pytest.fixture
def lookup_tool(mock_retriever):
    return LookupToolSet(retriever=mock_retriever)

def test_rerank_results(lookup_tool):
    # Mock LLM
    with patch("src.tools.lookup.get_llm") as mock_get_llm:
        mock_llm_instance = MagicMock()
        mock_get_llm.return_value = mock_llm_instance
        
        # Setup mock responses for LLM
        # We need to return different scores for different calls
        # First call: Score 8 (keep), Second call: Score 4 (drop)
        mock_llm_instance.invoke.side_effect = [
            MagicMock(content="The relevance score is 8."),
            MagicMock(content="The relevance score is 4.")
        ]
        
        results = [
            {"id": 1, "payload": {"text": "High relevance content", "chunk_id": 1}},
            {"id": 2, "payload": {"text": "Low relevance content", "chunk_id": 2}}
        ]
        
        reranked = lookup_tool._rerank_results("query", results)
        
        assert len(reranked) == 1
        assert reranked[0]["id"] == 1
        assert reranked[0]["rerank_score"] == 8

def test_generate_search_report(lookup_tool):
    with patch("src.tools.lookup.get_llm") as mock_get_llm:
        mock_llm_instance = MagicMock()
        mock_get_llm.return_value = mock_llm_instance
        
        expected_report = "Found 1 relevant chunks: \n- [Chunk ID: 1] Summary..."
        mock_llm_instance.invoke.return_value = MagicMock(content=expected_report)
        
        results = [
            {"id": 1, "payload": {"text": "Content", "chunk_id": 1}, "rerank_score": 8}
        ]
        
        report = lookup_tool._generate_search_report(results)
        
        assert report == expected_report

def test_semantic_fallback_single_result(lookup_tool, mock_retriever):
    with patch("src.tools.lookup.get_llm") as mock_get_llm:
        mock_llm_instance = MagicMock()
        mock_get_llm.return_value = mock_llm_instance
        
        # Mock search results
        mock_retriever.search.return_value = [
            {"id": 1, "payload": {"text": "Content 1", "chunk_id": 1}}
        ]
        
        # Mock rerank score to keep it
        mock_llm_instance.invoke.return_value = MagicMock(content="Score: 9")
        
        result = lookup_tool.semantic_fallback("query")
        
        assert "[Chunk ID: 1]" in result
        assert "Content 1" in result
        # Should NOT be a report if only 1 result

def test_semantic_fallback_multiple_results(lookup_tool, mock_retriever):
    with patch("src.tools.lookup.get_llm") as mock_get_llm:
        mock_llm_instance = MagicMock()
        mock_get_llm.return_value = mock_llm_instance
        
        # Mock search results (2 results)
        mock_retriever.search.return_value = [
            {"id": 1, "payload": {"text": "Content 1", "chunk_id": 1}},
            {"id": 2, "payload": {"text": "Content 2", "chunk_id": 2}}
        ]
        
        # Mock LLM responses:
        # 1. Score for chunk 1 (8)
        # 2. Score for chunk 2 (9)
        # 3. Report generation
        mock_llm_instance.invoke.side_effect = [
            MagicMock(content="Score: 8"),
            MagicMock(content="Score: 9"),
            MagicMock(content="Found 2 relevant chunks...")
        ]
        
        result = lookup_tool.semantic_fallback("query")
        
        assert "Found 2 relevant chunks..." in result

def test_semantic_fallback_no_results_after_rerank(lookup_tool, mock_retriever):
    with patch("src.tools.lookup.get_llm") as mock_get_llm:
        mock_llm_instance = MagicMock()
        mock_get_llm.return_value = mock_llm_instance
        
        # Mock search results
        mock_retriever.search.return_value = [
            {"id": 1, "payload": {"text": "Content 1", "chunk_id": 1}}
        ]
        
        # Mock rerank score to drop it
        mock_llm_instance.invoke.return_value = MagicMock(content="Score: 2")
        
        result = lookup_tool.semantic_fallback("query")
        
        assert "No relevant content found after reranking." in result
