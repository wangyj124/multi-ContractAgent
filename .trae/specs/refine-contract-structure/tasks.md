# Tasks

- [x] Task 1: Update Regex Patterns and Constants
  - [x] Update `HIERARCHY_PATTERNS` to support new levels (Cover, TOC, Volume, Signature) and formats (1., 10(A)).
  - [x] Define hierarchy levels constants.

- [x] Task 2: Enhance Document Extraction Logic
  - [x] Modify `extract_chunks` to handle the first page as "Contract Cover".
  - [x] Implement logic to detect "Table of Contents".
  - [x] Improve buffer management to aggregate Level 4+ content into Level 3 nodes.

- [x] Task 3: Implement Advanced Summarization Logic
  - [x] Update `_generate_smart_summary` to use `qwen3-30B-A3B-Instruct`.
  - [x] Implement length-based conditional summarization (<50 words vs >=50 words).
  - [x] Ensure summary generation respects the aggregated content from sub-clauses.

- [x] Task 4: Refine Tree Structure Generation
  - [x] Update `generate_document_structure` to match the required output format.
  - [x] Ensure Level 4+ nodes are not displayed as separate tree nodes but contribute to parent summaries.

- [x] Task 5: Verification
  - [x] Create a test script/document to verify the extraction and tree generation.
  - [x] Verify regex matches against examples (1., 2.1, 10(A)).
