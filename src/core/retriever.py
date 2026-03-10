import uuid
import hashlib
import random
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

        for i, chunk in enumerate(chunks):
            # Handle Archivist structure (content vs text)
            text = chunk.get("text") or chunk.get("content")
            if not text:
                continue
                
            vector = self._get_embedding(text)
            
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
        Semantic search.
        
        Args:
            query: Search query
            k: Number of results to return
            filter: Optional Qdrant filter (dict or Filter object)
        """
        query_vector = self._get_embedding(query)
        
        # If filter is a dict, we assume it's a Qdrant Filter structure or custom dict
        # Ideally, caller should pass models.Filter
        query_filter = filter
        
        search_result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=k
        ).points
        
        return [
            {
                "score": hit.score,
                "payload": hit.payload,
                "id": hit.id
            }
            for hit in search_result
        ]

    def search_by_path(self, path_prefix: str) -> List[Dict[str, Any]]:
        """
        Structural lookup by path prefix.
        Returns a list of payloads (chunks) that match the path prefix.
        """
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
                if path.startswith(path_prefix):
                    results.append(payload)
            
            offset = next_offset
            if offset is None:
                break
                
        return results
