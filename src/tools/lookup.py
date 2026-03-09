from typing import List, Optional
from langchain_core.tools import StructuredTool
from src.core.retriever import Retriever

class LookupToolSet:
    def __init__(self, retriever: Retriever):
        self.retriever = retriever

    def structural_lookup(self, path: str) -> str:
        """
        Takes a path (e.g. "Chapter 1/1.1").
        Uses a global or passed-in Retriever instance to find chunks with that path prefix.
        Returns the content of matching chunks combined.
        """
        # Search by path prefix
        results = self.retriever.search_by_path(path)
        
        if not results:
            return f"No content found for path: {path}"
        
        # Combine content from chunks
        # Use "text" or "content" field
        contents = []
        for res in results:
            content = res.get("text") or res.get("content") or ""
            chunk_id = res.get("chunk_id")
            if content:
                if chunk_id is not None:
                    contents.append(f"[Chunk ID: {chunk_id}]\n{content}")
                else:
                    contents.append(content)
                
        return "\n\n".join(contents)

    def semantic_fallback(self, query: str) -> str:
        """
        Takes a query string.
        Uses Retriever to search for relevant chunks.
        Returns the content of top-k chunks combined.
        """
        # Search semantically
        results = self.retriever.search(query, k=5)
        
        if not results:
            return "No relevant content found."
            
        contents = []
        for res in results:
            payload = res.get("payload", {})
            content = payload.get("text") or payload.get("content") or ""
            chunk_id = res.get("id") # Search result has 'id' at top level
            
            # Also check payload for chunk_id if not in top level (it should be in top level for Qdrant points)
            if chunk_id is None:
                chunk_id = payload.get("chunk_id")

            if content:
                if chunk_id is not None:
                    contents.append(f"[Chunk ID: {chunk_id}]\n{content}")
                else:
                    contents.append(content)
                
        return "\n\n".join(contents)

    def get_tools(self) -> List[StructuredTool]:
        """
        Return a list of tools for use in LangChain agents.
        """
        return [
            StructuredTool.from_function(
                func=self.structural_lookup,
                name="structural_lookup",
                description="Find chunks with a specific path prefix (e.g. 'Chapter 1/1.1'). Returns combined content."
            ),
            StructuredTool.from_function(
                func=self.semantic_fallback,
                name="semantic_fallback",
                description="Search for relevant chunks using semantic search. Returns combined content."
            )
        ]
