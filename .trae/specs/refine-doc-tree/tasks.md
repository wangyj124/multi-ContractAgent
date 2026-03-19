# Tasks
- [ ] Task 1: Create prompt files.
  - [ ] Create `src/prompts/summary.txt` with strict instructions for concise (<100 words) summaries.
  - [ ] Create `src/prompts/validator.txt` for the validator node.
- [ ] Task 2: Refine `src/core/archivist.py`.
  - [ ] Update `HIERARCHY_PATTERNS` to robustly capture "Chapter" headers.
  - [ ] Modify `_generate_smart_summary` to load `summary.txt` and ensure output is PURE summary (no titles).
  - [ ] Enforce the < 50 chars threshold strictly.
  - [ ] Modify `generate_document_structure` to limit display depth to Level 3 (e.g., "4.1") and prune deeper nodes from the *visual* tree.
- [ ] Task 3: Update `src/agents/nodes.py`.
  - [ ] Update `validator_node` to load and use `src/prompts/validator.txt`.

# Task Dependencies
- Task 2 and Task 3 can be done in parallel.
