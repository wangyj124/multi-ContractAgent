# Retrieval Strategy Update Spec

## Why
The current Supervisor strategy is relatively unstructured, providing only general guidance. To improve efficiency and accuracy, a strict three-tiered retrieval strategy ("Navigate -> Local Search -> Global Search") is required. This ensures the model prioritizes high-precision structural lookups before falling back to broader, more expensive semantic searches.

## What Changes
- **Supervisor Prompt Update**: Rewrite the `src/prompts/supervisor.txt` to explicitly define and enforce the three-tier retrieval logic.
- **Strategy Definition**:
    1.  **Tier 1: Structural Navigation (Path-based)**: Use `structural_lookup` when the target section is clear from the document map (e.g., "Delivery" -> "Delivery Section").
    2.  **Tier 2: Local Semantic Search (Path-filtered)**: Use `semantic_fallback` with `path_filter` when the section is known but the specific clause is not.
    3.  **Tier 3: Global Semantic Search**: Use `semantic_fallback` (no filter) only when structural cues fail or for cross-cutting information.

## Impact
- **Affected Code**: `src/prompts/supervisor.txt`.
- **Breaking Changes**: None. This is a prompt optimization.

## ADDED Requirements

### Requirement: Three-Tier Retrieval Strategy
The Supervisor SHALL follow a strict priority order for information retrieval:
1.  **CHECK MAP FIRST**: Look at the `{document_structure}`. If a section title matches the task (e.g., Task "Payment" matches Chapter "4. Payment"), use `structural_lookup(path="Chapter 4")`.
2.  **NARROW SEARCH SECOND**: If a section seems relevant but specific details are missing, use `semantic_fallback(query="...", path_filter="Chapter 4")`.
3.  **GLOBAL SEARCH LAST**: Only if the above fail or the information could be anywhere (e.g., "Total Amount"), use `semantic_fallback(query="...")` without a filter.

## MODIFIED Requirements
- **Supervisor Prompt**: Update the system prompt to include these specific instructions and examples.
