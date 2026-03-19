
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from src.core.retriever import Retriever

def debug_retriever():
    retriever = Retriever(location=":memory:", collection_name="debug_retriever")
    
    path = "合同封面/第一章 合同总价/1.1 合同总价"
    chunk = {
        "content": "1.1 本合同总价为人民币100万元整。",
        "path": path,
        "chunk_id": 0
    }
    
    retriever.index_chunks([chunk])
    
    print(f"Indexed chunk with path: '{path}'")
    
    # Test exact match
    query_path = "合同封面/第一章 合同总价/1.1 合同总价"
    print(f"Searching for: '{query_path}'")
    results = retriever.search_by_path(query_path)
    print(f"Results count: {len(results)}")
    if results:
        print(f"Found: {results[0].get('path')}")
    else:
        print("Not found.")

    # Test partial match (what user might have tried first)
    query_path_2 = "第一章/1.1"
    print(f"Searching for: '{query_path_2}'")
    results_2 = retriever.search_by_path(query_path_2)
    print(f"Results count: {len(results_2)}")

if __name__ == "__main__":
    debug_retriever()
