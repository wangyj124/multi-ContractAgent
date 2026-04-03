import uuid
import hashlib
import random
import os
from tqdm import tqdm
from typing import List, Dict, Any, Optional, Union
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.models import Filter, FieldCondition, MatchValue, MatchText
except ImportError:
    raise ImportError("Please install qdrant-client first.")

try:
    from fastembed import TextEmbedding
    FASTEMBED_AVAILABLE = True
except ImportError:
    FASTEMBED_AVAILABLE = False

try:
    from langchain_openai import OpenAIEmbeddings
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from src.core.llm import get_llm
from pathlib import Path

def _load_prompt(prompt_name: str) -> str:
    base_path = Path(__file__).parent.parent.parent / "src/prompts"
    prompt_path = base_path / f"{prompt_name}.txt"
    if not prompt_path.exists():
         # Fallback try relative path
         base_path = Path(__file__).parent.parent / "prompts"
         prompt_path = base_path / f"{prompt_name}.txt"
         
    if not prompt_path.exists():
         raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

class Retriever:
    def __init__(self, location: str = ":memory:", collection_name: str = "contract_chunks", embedding_model: str = "mock"):
        """
        Initialize Retriever with QdrantClient and embedding model.
        
        Args:
            location: Qdrant location (default: ":memory:")
            collection_name: Name of the collection
            embedding_model: "mock" or "fastembed" (default: "mock")
        """
        self.client = QdrantClient(location=location)
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        
        # Determine embedding dimension
        self.embedding_dim = 1536 # Default for mock (compatible with many models)
        
        if self.embedding_model == "fastembed":
            if FASTEMBED_AVAILABLE:
                self.embedder = TextEmbedding()
                # FastEmbed default model (BAAI/bge-small-en-v1.5) is 384 dim
                # We can check the model name, but for now assuming default
                self.embedding_dim = 384 
            else:
                print("FastEmbed not available, falling back to mock embeddings.")
                self.embedding_model = "mock"
        
        elif self.embedding_model == "openai" or self.embedding_model == "qwen3-embedding-8B":
            if OPENAI_AVAILABLE:
                base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
                api_key = os.environ.get("OPENAI_API_KEY", "sk-proj-...")
                # If model name is just "openai", default to text-embedding-3-small
                model_name = os.environ.get("MODEL_EMBEDDING") or \
                     (self.embedding_model if self.embedding_model != "openai" else "qwen3-embedding-8B")
                
                self.embedder = OpenAIEmbeddings(
                    model=model_name,
                    openai_api_base=base_url,
                    openai_api_key=api_key,
                    check_embedding_ctx_length=False
                )
                
                # Determine dimension by embedding a sample
                try:
                    # We do a quick check to ensure connectivity and get dimension
                    sample = self.embedder.embed_query("test")
                    self.embedding_dim = len(sample)
                except Exception as e:
                    print(f"Error initializing OpenAI embeddings ({model_name}): {e}. Falling back to mock.")
                    self.embedding_model = "mock"
            else:
                print("langchain-openai not available, falling back to mock embeddings.")
                self.embedding_model = "mock"

        # Initialize collection
        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
            
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.embedding_dim,
                distance=models.Distance.COSINE
            )
        )

    def _get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.
        """
        if self.embedding_model == "fastembed" and FASTEMBED_AVAILABLE:
            # fastembed returns a generator of embeddings
            return list(self.embedder.embed([text]))[0]
        elif (self.embedding_model == "openai" or self.embedding_model == "qwen3-embedding") and OPENAI_AVAILABLE:
             return self.embedder.embed_query(text)
        else:
            # Mock embedding: deterministic random vector based on text hash
            # Use md5 hash of text to seed random to ensure same text gets same vector
            seed = int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16)
            rng = random.Random(seed)
            return [rng.uniform(-1.0, 1.0) for _ in range(self.embedding_dim)]

    def index_chunks(self, chunks: List[Dict[str, Any]]):
        """
        Index chunks from Archivist.
        chunks: List of dicts, expected to have 'text' and other metadata.
        """
        points = []
        # Get current count to continue indexing sequentially
        try:
            count_result = self.client.count(collection_name=self.collection_name)
            start_id = count_result.count
        except Exception:
            start_id = 0

        pbar = tqdm(chunks, desc="正在建立向量索引", unit="chunk")

        for i, chunk in enumerate(pbar):
            # Handle Archivist structure (content vs text)
            text = chunk.get("text") or chunk.get("content")
            if not text:
                continue

            try:
                # 获取向量 (Dense Vector)
                vector = self._get_embedding(text)
                
                # 第一次成功时报一次成功提示
                if i == 0:
                    tqdm.write("Successfully connected to Embedding service. Processing remaining chunks...")
                
            except Exception as e:
                # 中途失败时，使用 tqdm.write 避免破坏进度条结构
                tqdm.write(f"Error at chunk {i}: {str(e)}")
                continue            
            
            # Create payload
            # Ensure we keep all metadata
            payload = chunk.copy()
            
            # Flatten metadata if present (Archivist style)
            if "metadata" in payload and isinstance(payload["metadata"], dict):
                for k, v in payload["metadata"].items():
                    payload[k] = v
            
            # If path is a list (from Archivist), convert to string
            if isinstance(payload.get("path"), list):
                payload["path"] = "/".join(payload["path"])
            
            # Ensure text/content is available
            if "content" in payload and "text" not in payload:
                payload["text"] = payload["content"]
            
            # Use sequential integer ID
            point_id = start_id + i
            
            # Store ID in payload as well for easy access
            payload["chunk_id"] = point_id
            
            points.append(models.PointStruct(
                id=point_id,
                vector=vector,
                payload=payload
            ))
            
        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
        tqdm.write(f"Indexing complete. Total {len(points)} chunks added.")

    def get_chunk(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific chunk by ID.
        """
        try:
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[chunk_id],
                with_payload=True,
                with_vectors=False
            )
            if points:
                return points[0].payload
            return None
        except Exception as e:
            print(f"Error retrieving chunk {chunk_id}: {e}")
            return None

    def get_context(self, chunk_id: int, window: int = 1) -> List[Dict[str, Any]]:
        """
        Retrieve previous and next chunks based on ID.
        """
        start_id = max(0, chunk_id - window)
        # We don't know the max ID easily without querying count, but retrieve handles missing IDs gracefully usually.
        # But let's just query a range.
        end_id = chunk_id + window
        
        ids_to_fetch = list(range(start_id, end_id + 1))
        
        try:
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=ids_to_fetch,
                with_payload=True,
                with_vectors=False
            )
            
            # Sort by ID to ensure order
            points.sort(key=lambda p: p.id)
            
            return [p.payload for p in points]
        except Exception as e:
            print(f"Error retrieving context for chunk {chunk_id}: {e}")
            return []

    def search(self, query: str, k: int = 5, filter: Optional[Union[Dict[str, Any], models.Filter]] = None) -> List[Dict[str, Any]]:
        """
        Hybrid Search (Semantic + Keyword Boost).
        
        Uses Dense Vector Search as the primary retrieval method (Top 2*k),
        then re-ranks results by boosting scores based on keyword presence.
        
        Args:
            query: Search query
            k: Number of results to return
            filter: Optional Qdrant filter
        """
        query_vector = self._get_embedding(query)
        
        # 1. Semantic Search
        # Note: client.search returns list of ScoredPoint
        # Use query_points for synchronous client if search is not available
        search_result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=filter,
            limit=k * 2 # Fetch more candidates for re-ranking
        ).points
        
        # 2. Client-side Keyword Boost
        query_terms = set(query.lower().split())
        
        candidates = []
        for hit in search_result:
            payload = hit.payload
            text = (payload.get("text") or payload.get("content") or "").lower()
            
            # Calculate term overlap
            # Simple exact match of terms
            term_matches = sum(1 for term in query_terms if term in text)
            
            # Apply Boost
            boost = 1.0 + (0.1 * term_matches) 
            final_score = hit.score * boost
            
            candidates.append({
                "score": final_score,
                "payload": payload,
                "id": hit.id,
                "original_score": hit.score
            })
            
        # Sort by boosted score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        # 3. LLM Reranking (Optional, Top 5)
        # Rerank the top candidates using LLM score
        top_candidates = candidates[:5]
        
        # Check if LLM reranking is enabled via env or if we have enough candidates
        enable_llm_rerank = os.environ.get("ENABLE_LLM_RERANK", "true").lower() == "true"
        
        if enable_llm_rerank and top_candidates:
            llm = get_llm("qwen3-30B-A3B-Instruct", temperature=0)
            rerank_prompt_template = _load_prompt("lookup_rerank")
            
            for cand in top_candidates:
                content = cand["payload"].get("content", "")[:1000] # Limit content length
                prompt = rerank_prompt_template.format(query=query, content=content)
                
                try:
                    response = llm.invoke(prompt)
                    score_str = response.content.strip()
                    # Extract number from response
                    import re
                    match = re.search(r"\d+", score_str)
                    if match:
                        llm_score = int(match.group())
                        # Normalize to 0-1 range and blend with vector score
                        # Vector score is usually 0.7-0.9. LLM score is 0-10.
                        # New Score = 0.7 * VectorScore + 0.3 * (LLMScore / 10)
                        cand["llm_score"] = llm_score
                        cand["final_score"] = 0.7 * cand["score"] + 0.3 * (llm_score / 10.0)
                    else:
                        cand["final_score"] = cand["score"]
                except Exception as e:
                    # print(f"Rerank failed: {e}")
                    cand["final_score"] = cand["score"]
            
            # Re-sort based on blended score
            top_candidates.sort(key=lambda x: x.get("final_score", 0), reverse=True)
            return top_candidates
            
        return candidates[:k]

    def search_by_path(self, path_prefix: str) -> List[Dict[str, Any]]:
        """
        Structural lookup by path prefix.
        Supports fuzzy matching where path_prefix components match the start of actual path components.
        e.g. "Chapter 1/1.1" matches "Chapter 1 Introduction/1.1 Definition"
        Also supports missing or extra levels in the query path.
        """
        # Normalize query path parts
        query_parts = [p.strip() for p in path_prefix.split('/') if p.strip()]
        
        results = []
        offset = None
        while True:
            # Scroll through all points
            points_result, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=None, 
                limit=100,
                with_payload=True,
                with_vectors=False,
                offset=offset
            )
            
            for point in points_result:
                payload = point.payload or {}
                path = payload.get("path", "")
                
                # Calculate match score
                score, last_matched = self._calculate_path_match_score(query_parts, path)
                
                # Threshold logic:
                # 1. If query has multiple parts, we generally require the LAST part to match.
                #    (e.g. "Vol 2/3.1" should match "3.1" or "Vol 2/3.1", but NOT just "Vol 2")
                # 2. Score threshold: Allow 1 miss if length > 1.
                
                threshold = 1.0
                if len(query_parts) > 1:
                    threshold = (len(query_parts) - 1.0) / len(query_parts)
                    threshold -= 0.01 # Float tolerance
                
                # Condition: High score AND (last part matched OR strict perfect match on prefix)
                # Actually, if last part matches, it's usually what we want.
                # If last part doesn't match, it might be a parent matching a child query? No, parent matching child query means query has MORE parts.
                # If query "A/B" matches "A", last part "B" missed.
                # If query "A" matches "A/B", last part "A" matched.
                
                if score >= threshold and (last_matched or len(query_parts) == 1):
                    results.append(payload)
            
            offset = next_offset
            if offset is None:
                break
                
        return results

    def _calculate_path_match_score(self, query_parts: List[str], actual_path: str) -> tuple[float, bool]:
        """
        Helper to calculate a match score (0.0 to 1.0) between query and actual path.
        Returns (score, last_part_matched_bool).
        """
        if not actual_path or not query_parts:
            return 0.0, False
            
        actual_parts = [p.strip() for p in actual_path.split('/') if p.strip()]
        
        matches = 0
        match_idx = 0
        last_part_matched = False
        
        for idx, q in enumerate(query_parts):
            q_norm = " ".join(q.split()).lower()
            
            # Find fuzzy match in remaining actual parts
            # We want to support skipping levels if needed, but order matters.
            # Also support substring match: "2.2" should match "2.2 本合同..."
            
            # 为了防止过长的路径（带有空格、特殊符号、换行等）在经过模型和系统的传递中变形导致不匹配
            # 我们截取前 20 个非空字符作为关键特征（因为 20 个字在同一层级下通常已经足够唯一）
            # 注意这里对中英文混合处理做了一个相对安全的近似截取
            q_safe = q_norm.replace(" ", "")[:20] if len(q_norm.replace(" ", "")) > 20 else q_norm.replace(" ", "")

            for i in range(match_idx, len(actual_parts)):
                a = actual_parts[i]
                a_norm = " ".join(a.split()).lower()
                a_safe = a_norm.replace(" ", "")
                
                # Check for startsWith or contains (if query is specific like 2.2)
                # 如果查询词去除了所有空格后，是目标词去除所有空格后的子串（即核心内容一致），即视为匹配
                # 这样可以完全无视原句中 `万元` 前后的那几个空格到底是全角、半角还是换行
                
                if q_safe in a_safe:
                    match_idx = i + 1
                    matches += 1
                    if idx == len(query_parts) - 1:
                        last_part_matched = True
                    break
        
        return matches / len(query_parts), last_part_matched

    def _match_path_fuzzy(self, query_parts: List[str], actual_path: str) -> bool:
        """
        Deprecated. Use _calculate_path_match_score instead.
        """
        score, _ = self._calculate_path_match_score(query_parts, actual_path)
        return score == 1.0
