# Checklist

- [x] `Retriever.search` supports path filtering.
- [x] `semantic_fallback` correctly filters by path when provided.
- [x] Reranking logic filters out low-relevance chunks.
- [x] Search results are returned as a concise "Search Report" instead of raw text concatenation.
- [x] Supervisor prompt includes Query Refinement instructions.
- [x] Supervisor prompt includes Link Tracing instructions.
- [x] Existing tests pass with new tool signatures.
