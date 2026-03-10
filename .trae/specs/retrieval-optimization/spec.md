# Retrieval Optimization Spec

## Why
Current retrieval mechanisms lack precision (no path filtering for semantic search), return excessive raw content (noise), and lack "business logic" understanding (ranking). The Supervisor also lacks explicit guidance on query refinement and link tracing.

## What Changes
- **Structured Filtering**: Update `semantic_fallback` to accept an optional `path_filter` argument.
- **Observation Denoising**: Implement a pre-processing step ("Summary Worker") in `Retriever` or `LookupToolSet` that summarizes top-K chunks into a concise report before returning to Supervisor.
- **Query Refinement**: Update Supervisor's system prompt to encourage query rewriting upon failure.
- **Reranking**: Implement a lightweight reranker (using LLM scoring) in `lookup.py` to filter search results based on relevance to the query.
- **Link Tracing**: Update Supervisor's system prompt to explicitly look for "See Attachment X" or "Refer to Clause Y" and use `structural_lookup`.

## Impact
- **Affected Code**: `src/tools/lookup.py`, `src/core/retriever.py`, `src/prompts/supervisor.txt`.
- **Breaking Changes**: `semantic_fallback` signature changes (adds optional arg). Tool output format changes (summarized report).

## ADDED Requirements

### Requirement: Path-Filtered Semantic Search
`semantic_fallback` SHALL accept `path_filter` (optional string).
If provided, the search SHALL be restricted to chunks where `path` starts with `path_filter`.
*Implementation Note*: Qdrant supports filtering. We need to update `Retriever.search` to accept a filter.

### Requirement: Observation Denoising (Summary Report)
When `semantic_fallback` returns multiple chunks, instead of concatenating raw text, the system SHALL:
1.  Use an LLM to generate a single "Search Report".
2.  Report format: "Found X relevant points: Chunk A mentions... Chunk B mentions...".
3.  Limit report length (e.g., 200 words).

### Requirement: Business Relevance Reranking
After vector search retrieves Top-K (e.g., 10), the system SHALL:
1.  Use an LLM (30B) to score each chunk (1-10) based on relevance to the `query`.
2.  Filter out chunks with score < 8 (or keep top 3).
3.  Only return high-relevance chunks (or their summary).

### Requirement: Supervisor Query Refinement
Supervisor System Prompt SHALL include instructions: "If initial search fails, try rewriting the query with synonyms (e.g., 'Retention Money' instead of 'Warranty Bond')."

### Requirement: Link Tracing
Supervisor System Prompt SHALL include instructions: "If you see references like 'See Attachment 4', use structural_lookup to retrieve that specific section."

## MODIFIED Requirements
- **Retriever.search**: Add `filter` parameter (dict or Qdrant Filter object).
- **LookupToolSet.semantic_fallback**: Update to use filter and reranking/summarization pipeline.
