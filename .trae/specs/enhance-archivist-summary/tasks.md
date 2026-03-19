# Tasks
- [ ] Task 1: Update `HIERARCHY_PATTERNS` in `src/core/archivist.py` with expanded regex support.
  - [ ] Add support for "1.", "10(A)", "10(A).1", "Contract Agreement", "Table of Contents".
- [ ] Task 2: Implement `_generate_smart_summary` method in `src/core/archivist.py`.
  - [ ] Implement logic to check text length and call LLM if needed.
  - [ ] Implement LLM call using `qwen3-30b-instruct` with temp 0.
  - [ ] Handle parallel processing/batching for summaries.
- [ ] Task 3: Refactor `extract_chunks` and `_add_text_chunks` to use `_generate_smart_summary`.
  - [ ] Integrate the summary generation into the chunking process.
  - [ ] Ensure special handling for "Contract Agreement" and "Signature Page".
- [ ] Task 4: Update `generate_document_structure` to include summaries.
  - [ ] Modify the output format to display summaries alongside hierarchy nodes.

# Task Dependencies
- Task 3 depends on Task 2.
- Task 4 depends on Task 3.
