# Tasks

- [x] Task 1: Implement Depth-Weighted Hierarchy Detection
  - [x] SubTask 1.1: Define regex patterns with associated depths in `Archivist`.
  - [x] SubTask 1.2: Update `_detect_hierarchy` to use these patterns and implement path truncation logic.
  - [x] SubTask 1.3: Handle special pages (Signature Page) as Depth 1.

- [x] Task 2: Enhance Chunking and Metadata
  - [x] SubTask 2.1: Update `extract_chunks` to include the header text at the beginning of the new chunk buffer.
  - [x] SubTask 2.2: Update metadata `path` to be a string joined by `/`.
  - [x] SubTask 2.3: Update `generate_document_structure` to handle the new path format (or ensure compatibility).

- [x] Task 3: Implement Semantic Summary Generation
  - [x] SubTask 3.1: Add `_generate_summary(text)` method to `Archivist` using `get_llm`.
  - [x] SubTask 3.2: Call this method for each chunk and populate `metadata['summary']`.

- [x] Task 4: Verification
  - [x] SubTask 4.1: Update/Create tests to verify hierarchy detection with complex examples (Volume, Signature Page).
  - [x] SubTask 4.2: Verify summary generation (mock LLM).
