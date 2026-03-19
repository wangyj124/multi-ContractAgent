# Refine Document Tree and Summarization Spec

## Why
The current document tree generation still has significant flaws:
1. **Missing Chapter Headers**: Headers like "Chapter 4" are missing from the tree, even though they exist in the source.
2. **Excessive Depth**: The tree includes levels deeper than "4.1" (e.g., "4.2.1"), which is not desired.
3. **Poor Summarization**: Summaries are verbose, include the title, and don't seem to strictly follow the length limit or use the LLM effectively as requested.
4. **Missing Validation Prompt**: The validator node lacks a dedicated prompt file.
5. **Logic Gaps**: The threshold logic for using original text vs. LLM summary (< 50 chars) needs verification and stricter enforcement.

## What Changes
- **Refine Hierarchy Patterns**: Ensure "Chapter X" headers are correctly captured and prioritized.
- **Limit Tree Depth**: Modify `generate_document_structure` to strictly prune or aggregate nodes deeper than level 3 (e.g., stop at "4.1").
- **Optimize Summarization Prompt**: Create a dedicated prompt file for summarization to enforce brevity (< 100 words) and exclude titles from the summary output.
- **Fix Summary Logic**: Ensure the summary ONLY contains the generated content, not the original title + content.
- **Add Validator Prompt**: Create `src/prompts/validator.txt` for the validation node.
- **Strict Length Check**: Enforce the < 50 chars check before calling LLM.

## Impact
- **Affected specs**: Document tree generation, Summarization logic.
- **Affected code**: `src/core/archivist.py`, `src/agents/nodes.py`.
- **New files**: `src/prompts/summary.txt`, `src/prompts/validator.txt`.

## MODIFIED Requirements
### Requirement: Strict Hierarchy Control
- The document tree SHALL explicitly include "Chapter" level nodes.
- The document tree SHALL NOT display nodes deeper than the "Section" level (e.g., "4.1"). Content from deeper levels (e.g., "4.1.1") must be aggregated or ignored in the tree visualization (but kept in chunks).

### Requirement: Concise LLM Summarization
- **Prompt**: Use a dedicated `summary.txt` prompt template.
- **Input**: Only send text to LLM if length > 50 chars.
- **Output**: Summary must be < 100 words, strictly content-focused, NO title repetition.
- **Format**: `(摘要: <summary_content>)` in the tree.

### Requirement: Validator Configuration
- Implement a dedicated prompt for the validator node (`validator.txt`) to standardize validation logic.
