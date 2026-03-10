# Tasks

- [x] Task 1: Update Retriever with Filtering
  - [x] SubTask 1.1: Modify `src/core/retriever.py` `search` method to accept `filter` (e.g., path prefix).
  - [x] SubTask 1.2: Implement Qdrant filtering logic for `path` metadata.

- [x] Task 2: Implement Reranking and Denoising in Lookup
  - [x] SubTask 2.1: Implement `_rerank_results(query, results)` in `LookupToolSet` using LLM scoring.
  - [x] SubTask 2.2: Implement `_generate_search_report(results)` in `LookupToolSet` to summarize findings.
  - [x] SubTask 2.3: Update `semantic_fallback` to use Reranking -> Denoising pipeline.
  - [x] SubTask 2.4: Update `semantic_fallback` signature to accept `path_filter`.

- [x] Task 3: Update Supervisor Prompts
  - [x] SubTask 3.1: Update `src/prompts/supervisor.txt` with Query Refinement and Link Tracing instructions.

- [x] Task 4: Verification
  - [x] SubTask 4.1: Test `semantic_fallback` with path filter (ensure only target chapter chunks returned).
  - [x] SubTask 4.2: Test Reranking logic (ensure irrelevant chunks are dropped).
  - [x] SubTask 4.3: Test Summary Report format.
