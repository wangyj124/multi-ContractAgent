# Refactor Archivist for Enhanced Document Structure and Summarization Spec

## Why
The current `Archivist` class uses simple regular expressions for hierarchy detection, leading to missed sections (e.g., "1.", "10(A).1") and an incomplete document tree. Furthermore, it lacks intelligent summarization for long content, resulting in a tree structure that is hard to navigate and lacks semantic information.

## What Changes
- Update `HIERARCHY_PATTERNS` in `src/core/archivist.py` to support more diverse contract header formats.
- Implement `_generate_smart_summary` method to intelligently summarize content based on length.
- Refactor `extract_chunks` and `_add_text_chunks` to integrate the new summarization logic.
- Update `generate_document_structure` to include summaries in the tree output.
- Add special handling for "Contract Agreement" (合同协议书) and "Signature Page" (签字页) to ensure they are summarized and included in the tree.

## Impact
- **Affected specs**: Document structure generation, Chunk extraction.
- **Affected code**: `src/core/archivist.py`.

## MODIFIED Requirements
### Requirement: Enhanced Hierarchy Detection
The system SHALL support the following hierarchy patterns:
- Level 1: "Volume X", "Contract Agreement", "Signature Page", "Table of Contents".
- Level 2: "Chapter X", "X." (e.g., "1.").
- Level 3: "X.X", "Article X(Y)" (e.g., "10(A)").
- Level 4: "X.X.X", "Article X(Y).Z".

### Requirement: Intelligent Summarization
- If text length < 50 chars: Use original text as summary.
- If text length >= 50 chars: Call LLM (`qwen3-30b-instruct`, temp 0) to generate a summary (< 100 chars).
- Summarization SHALL happen in parallel batches where possible to improve performance, respecting context limits.
- Summaries SHALL focus on core obligations, amounts, dates, or responsibilities.

### Requirement: Document Tree with Summaries
The `generate_document_structure` output SHALL include the generated summaries for each node, improving navigability.
