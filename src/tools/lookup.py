import os
from typing import List, Optional, Set, Union, Dict
from pathlib import Path
from langchain_core.tools import StructuredTool
from src.core.retriever import Retriever
from src.core.llm import get_llm
try:
    from qdrant_client.http import models
except ImportError:
    models = None # Handle gracefully if needed, but Retriever ensures it's there

def _load_prompt(prompt_name: str) -> str:
    base_path = Path(__file__).parent.parent / "prompts"
    prompt_path = base_path / f"{prompt_name}.txt"
    if not prompt_path.exists():
         raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

class Colors:
    CYAN = '\033[96m'
    RED = '\033[91m'
    RESET = '\033[0m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'

class LookupToolSet:
    def __init__(self, retriever: Retriever):
        self.retriever = retriever

    def _summarize_if_needed(self, text: str) -> str:
        """
        Check if text length > 2000. If so, summarize it using LLM.
        """
        # Configurable summary via env var
        enable_summary = os.environ.get("ENABLE_LOOKUP_SUMMARY", "false").lower() == "true"
        
        if not enable_summary:
            return text
            
        if len(text) <= 2000:
            return text
            
        llm = get_llm("qwen3-30B-A3B-Instruct")
        try:
            prompt_template = _load_prompt("lookup_summary")
            prompt = prompt_template.format(text=text)
            summary_response = llm.invoke(prompt)
            summary = summary_response.content
            return f"{summary}\n\n[注意：由于长度限制，这是检索文本的摘要]"
        except Exception as e:
            # Fallback to original text or truncated version if LLM fails
            return text[:2000] + "\n\n[注意：由于长度和总结失败，文本已被截断]"

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
                
            prompt_template = _load_prompt("lookup_rerank")
            prompt = prompt_template.format(query=query, content=content[:1000])
            
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
            return "重排序后未找到相关结果。"
            
        llm = get_llm("qwen3-30B-A3B-Instruct")
        
        candidates_text = ""
        for res in results:
            payload = res.get("payload", {})
            content = payload.get("text") or payload.get("content") or ""
            chunk_id = res.get("id") or payload.get("chunk_id")
            score = res.get('rerank_score', 0)
            candidates_text += f"[Chunk ID: {chunk_id}] (Score: {score})\n{content[:500]}...\n\n"
            
        prompt_template = _load_prompt("lookup_report")
        prompt = prompt_template.format(candidates_text=candidates_text)
        
        try:
            response = llm.invoke(prompt)
            return response.content
        except Exception as e:
            return "生成报告时出错。"

    def structural_lookup(self, path: str) -> str:
        """
        Takes a path (e.g. "Chapter 1/1.1").
        Uses a global or passed-in Retriever instance to find chunks with that path prefix.
        Returns the content of matching chunks combined.
        """
        print(f"{Colors.YELLOW}[工具] 执行 structural_lookup(path='{path}'){Colors.RESET}")
        # Search by path prefix
        results = self.retriever.search_by_path(path)
        
        if not results:
            # Try to find a suggestion using the last part of the path
            parts = path.split('/')
            if len(parts) > 1:
                target = parts[-1]
                # Search for the target keyword in paths
                # We use a simple semantic search for the target term, expecting it to appear in the path
                suggestion_results = self.retriever.search(target, k=3)
                suggestions = []
                for res in suggestion_results:
                    p = res.get("payload", {}).get("path", "")
                    if target in p and p != path:
                        suggestions.append(p)
                
                if suggestions:
                    # Deduplicate and limit
                    suggestions = list(set(suggestions))[:3]
                    return f"未找到路径 '{path}' 的内容。你是不是指：{', '.join(suggestions)}？"

            return f"未找到路径的内容：{path}"
        
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
        result = self._summarize_if_needed(combined_text)
        print(f"{Colors.YELLOW}[工具] 返回内容长度: {len(result)} 字符{Colors.RESET}")
        return result

    def semantic_fallback(self, query: str, path_filter: Optional[str] = None) -> str:
        """
        Takes a query string and optional path filter.
        Uses Retriever to search for relevant chunks.
        If path_filter is provided, only chunks matching the path (prefix or keyword) are returned.
        Returns the content of top-k chunks combined.
        """
        print(f"{Colors.YELLOW}[工具] 执行 semantic_fallback(query='{query}', path_filter='{path_filter}'){Colors.RESET}")
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
            return "未找到相关内容。"
            
        reranked = self._rerank_results(query, results)
        
        if not reranked:
            return "重排序后未找到相关内容。"
            
        if len(reranked) == 1:
            res = reranked[0]
            payload = res.get("payload", {})
            content = payload.get("text") or payload.get("content") or ""
            chunk_id = res.get("id") or payload.get("chunk_id")
            result_text = f"[Chunk ID: {chunk_id}]\n{content}"
            final_res = self._summarize_if_needed(result_text)
            print(f"{Colors.YELLOW}[工具] 返回单条结果长度: {len(final_res)} 字符{Colors.RESET}")
            return final_res
            
        report = self._generate_search_report(reranked)
        print(f"{Colors.YELLOW}[工具] 返回搜索报告长度: {len(report)} 字符{Colors.RESET}")
        return report

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
            return "未找到路径。"
            
        return "\n".join(sorted(list(paths)))

    def Context_Expander(self, chunk_id: int) -> str:
        """
        Takes a chunk_id.
        Returns combined text of the chunk and its neighbors (window=1).
        """
        results = self.retriever.get_context(chunk_id, window=1)
        
        if not results:
            return f"未找到块ID的上下文：{chunk_id}"
            
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
