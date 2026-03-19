# Tasks

- [x] Task 1: Update Regex Patterns
  - [x] Remove Level 4 patterns (e.g., `\d+\.\d+\.\d+`) from `HIERARCHY_PATTERNS`.
  - [x] Ensure Level 3 patterns are robust.

- [x] Task 2: Implement Logging and Statistics
  - [x] Add logging statements in `extract_chunks` and `_detect_hierarchy`.
  - [x] Track statistics (nodes, chunks).

- [x] Task 3: Implement Short Title Extraction
  - [x] Add logic to check header length (> 10 chars).
  - [x] Implement `_generate_short_title` method using `qwen3-30B-A3B-Instruct`.

- [x] Task 4: Refine Summarization Logic
  - [x] Update `_generate_smart_summary` thresholds (20 chars).
  - [x] Remove hard truncation of summaries.
  - [x] Ensure aggregation of Level 4+ content into Level 3 summary context.

- [x] Task 5: Verify with Real Document
  - [x] Create a verification script using `data/input/甘露机岛合同-20181211版最终-签字版（无价格版）.docx`.
  - [x] Verify tree depth (max Level 3).
  - [x] Verify short titles.
  - [x] Verify summary completeness.
