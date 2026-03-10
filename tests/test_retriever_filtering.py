import pytest
import sys
import os
from qdrant_client.http import models

# Add src to path if not already there
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from core.retriever import Retriever

def test_retriever_filtering():
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
    
    # Test search with filter for path
    # We want to search for "contract" but filter only for "contracts/contract_a.txt"
    
    # Construct filter
    # Assuming 'path' is stored as keyword/text. Qdrant auto-detects.
    # If it's a string, MatchValue does exact match.
    
    path_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="path",
                match=models.MatchValue(value="contracts/contract_a.txt")
            )
        ]
    )
    
    results = retriever.search("contract", k=10, filter=path_filter)
    
    # Verify results
    assert len(results) == 2
    for res in results:
        assert res["payload"]["path"] == "contracts/contract_a.txt"
        
    # Test search with filter for another path
    path_filter_b = models.Filter(
        must=[
            models.FieldCondition(
                key="path",
                match=models.MatchValue(value="contracts/contract_b.txt")
            )
        ]
    )
    
    results_b = retriever.search("contract", k=10, filter=path_filter_b)
    assert len(results_b) == 1
    assert results_b[0]["payload"]["path"] == "contracts/contract_b.txt"

    # Test filtering with MatchText (if we want to match words in path or other fields)
    # Let's filter by type="clause"
    type_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="type",
                match=models.MatchValue(value="clause")
            )
        ]
    )
    results_type = retriever.search("contract", k=10, filter=type_filter)
    assert len(results_type) == 3
