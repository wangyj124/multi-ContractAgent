import pytest
import sys
import os

# Add src to path if not already there
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from core.retriever import Retriever

def test_retriever_indexing_and_search():
    # Initialize retriever with mock embeddings
    retriever = Retriever(location=":memory:", embedding_model="mock")
    
    # Mock chunks
    chunks = [
        {
            "text": "This is a contract about payment terms.",
            "path": "contracts/contract_a.txt",
            "type": "clause",
            "summary": "Payment terms",
            "clause_no": "1.1"
        },
        {
            "text": "The buyer shall pay the seller within 30 days.",
            "path": "contracts/contract_a.txt",
            "type": "clause",
            "summary": "Payment deadline",
            "clause_no": "1.2"
        },
        {
            "text": "This is a contract about confidentiality.",
            "path": "contracts/contract_b.txt",
            "type": "clause",
            "summary": "Confidentiality",
            "clause_no": "2.1"
        }
    ]
    
    # Index chunks
    retriever.index_chunks(chunks)
    
    # Test semantic search
    # Since we use mock embeddings, we just check if search returns results
    results = retriever.search("payment", k=2)
    assert len(results) > 0
    # Check structure of results
    assert "score" in results[0]
    assert "payload" in results[0]
    
    # Test search by path (exact match via prefix)
    path_results = retriever.search_by_path("contracts/contract_a.txt")
    # We expect 2 chunks for contract_a
    assert len(path_results) == 2
    paths = [r["path"] for r in path_results]
    assert all(p == "contracts/contract_a.txt" for p in paths)
    
    # Test search by path prefix
    prefix_results = retriever.search_by_path("contracts/")
    # We expect all 3 chunks
    assert len(prefix_results) == 3
    
    # Test search by non-existent path
    empty_results = retriever.search_by_path("non_existent/")
    assert len(empty_results) == 0

def test_retriever_empty_index():
    retriever = Retriever(location=":memory:", embedding_model="mock")
    results = retriever.search("anything")
    assert len(results) == 0
