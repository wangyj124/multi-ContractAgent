from typing import List, Optional, Set, Union, Dict
from langchain_core.tools import StructuredTool
from src.core.retriever import Retriever
from src.core.llm import get_llm
try:
    from qdrant_client.http import models
except ImportError:
    models = None # Handle gracefully if needed, but Retriever ensures it's there

class LookupToolSet:
    def __init__(self, retriever: Retriever):
        self.retriever = retriever

    def _summarize_if_needed(self, text: str) -> str:
        """
        Check if text length > 2000. If so, summarize it using LLM.
        """
        if len(text) <= 2000:
            return text
            
        llm = get_llm("qwen3-30B-A3B-Instruct")
        try:
            summary_response = llm.invoke(f"Summarize the following text into 150 words:\n\n{text}")
            summary = summary_response.content
            return f"{summary}\n\n[Note: This is a summary of the retrieved text due to length limit]"
        except Exception as e:
            # Fallback to original text or truncated version if LLM fails
            return text[:2000] + "\n\n[Note: Text truncated due to length and summarization failure]"

    def _rerank_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """
        Rerank and filter search results using LLM.
        """
        llm = get_llm("qwen3-30B-A3B-Instruct")
        reranked_results = []
        
        for res in results:
            payload = res.get("payload", {})
            content = payload.get("text") or payload.get("content") or ""
            chunk_id = res.get("id") or payload.get("chunk_id")
            
            if not content:
                continue
                
            prompt = f"""
            Query: {query}
            
            Document Chunk:
            {content[:1000]}
            
            Task: Rate the relevance of the document chunk to the query on a scale of 0 to 10.
            0 means completely irrelevant, 10 means perfect match.
            Return ONLY the number.
            """
            
            try:
                response = llm.invoke(prompt)
                score_str = response.content.strip()
                # Extract number from string in case LLM is chatty
                import re
                match = re.search(r'\d+', score_str)
                if match:
                    score = int(match.group())
                else:
                    score = 0
            except Exception:
                score = 0
                
            if score >= 7:
                res['rerank_score'] = score # Store score for later use
                reranked_results.append(res)
                
        # Sort by score descending
        reranked_results.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
        return reranked_results

    def _generate_search_report(self, results: List[Dict]) -> str:
        """
        Generate a concise report of the search results using LLM.
        """
        if not results:
            return "No relevant results found after reranking."
            
        llm = get_llm("qwen3-30B-A3B-Instruct")
        
        candidates_text = ""
        for res in results:
            payload = res.get("payload", {})
            content = payload.get("text") or payload.get("content") or ""
            chunk_id = res.get("id") or payload.get("chunk_id")
            score = res.get('rerank_score', 0)
            candidates_text += f"[Chunk ID: {chunk_id}] (Score: {score})\n{content[:500]}...\n\n"
            
        prompt = f"""
        Here are some search results found for a user query.
        Summarize these results into a concise report.
        Format: "Found X relevant chunks: \\n- [Chunk ID] Summary..."
        
        Search Results:
        {candidates_text}
        """
        
        try:
            response = llm.invoke(prompt)
            return response.content
        except Exception as e:
            return "Error generating report."

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
                
        combined_text = "\n\n".join(contents)
        return self._summarize_if_needed(combined_text)

    def semantic_fallback(self, query: str, path_filter: Optional[str] = None) -> str:
        """
        Takes a query string and optional path filter.
        Uses Retriever to search for relevant chunks.
        If path_filter is provided, only chunks matching the path (prefix or keyword) are returned.
        Returns the content of top-k chunks combined.
        """
        # Search semantically
        qdrant_filter = None
        if path_filter and models:
            # We use MatchText for path filtering as a loose "contains" or "keyword" match
            # Ideally, path should be indexed for prefix search, but MatchText is reasonable default
            qdrant_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="path",
                        match=models.MatchText(text=path_filter)
                    )
                ]
            )
        
        results = self.retriever.search(query, k=10, filter=qdrant_filter)
        
        if not results:
            return "No relevant content found."
            
        reranked = self._rerank_results(query, results)
        
        if not reranked:
            return "No relevant content found after reranking."
            
        if len(reranked) == 1:
            res = reranked[0]
            payload = res.get("payload", {})
            content = payload.get("text") or payload.get("content") or ""
            chunk_id = res.get("id") or payload.get("chunk_id")
            result_text = f"[Chunk ID: {chunk_id}]\n{content}"
            return self._summarize_if_needed(result_text)
            
        return self._generate_search_report(reranked)

    def Navigation_Reflector(self, path_or_query: str) -> str:
        """
        Takes a path or query string.
        Returns a unique list of 'path' metadata for matched chunks.
        Helps to find where content is located.
        """
        # Strategy: try search as query first, then if no results or if it looks like a path, try path?
        # User prompt says: "Use retriever.search(query, k=3) or search_by_path"
        
        paths: Set[str] = set()
        
        # Try semantic search first
        semantic_results = self.retriever.search(path_or_query, k=3)
        for res in semantic_results:
            payload = res.get("payload", {})
            p = payload.get("path")
            if p:
                paths.add(p)
                
        # Also try as path prefix if it looks like a path (optional optimization, but let's just do it if semantic yields nothing or few)
        # Or just do both to be safe as per "path_or_query" name
        path_results = self.retriever.search_by_path(path_or_query)
        # Limit path results to avoid overwhelming if prefix is too broad (though search_by_path might return many)
        # For reflector, maybe we just want to see if it exists.
        for res in path_results[:10]: # Limit to top 10 path matches
            p = res.get("path")
            if p:
                paths.add(p)
                
        if not paths:
            return "No paths found."
            
        return "\n".join(sorted(list(paths)))

    def Context_Expander(self, chunk_id: int) -> str:
        """
        Takes a chunk_id.
        Returns combined text of the chunk and its neighbors (window=1).
        """
        results = self.retriever.get_context(chunk_id, window=1)
        
        if not results:
            return f"No context found for chunk_id: {chunk_id}"
            
        contents = []
        for res in results:
            content = res.get("text") or res.get("content") or ""
            cid = res.get("chunk_id")
            path = res.get("path")
            
            header = f"[Chunk ID: {cid}]"
            if path:
                header += f" [Path: {path}]"
            
            if content:
                contents.append(f"{header}\n{content}")
                
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
                description="Search for relevant chunks using semantic search. Optionally filter by path. Returns combined content."
            ),
            StructuredTool.from_function(
                func=self.Navigation_Reflector,
                name="Navigation_Reflector",
                description="Find paths/locations of content based on a query or path string. Returns list of paths."
            ),
            StructuredTool.from_function(
                func=self.Context_Expander,
                name="Context_Expander",
                description="Expand context around a specific chunk ID. Returns combined text of chunk and neighbors."
            )
        ]
