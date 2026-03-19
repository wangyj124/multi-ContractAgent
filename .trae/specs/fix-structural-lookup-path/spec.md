# Fix Structural Lookup Path Spec

## Why
The `structural_lookup` tool currently fails to find content when the provided path contains extra levels (hallucinated by the LLM) or minor mismatches (e.g., missing spaces in headers) compared to the actual document structure. Specifically, a query like `第二卷/第三章/3.1` fails to match `第二卷/3.1` because of the extra "第三章" and exact matching requirements.

## What Changes
- Update `Retriever.search_by_path` to implement a robust, fuzzy subsequence matching algorithm.
- The matching logic will:
  - Tokenize paths into components.
  - Allow components to match if one is a prefix of the other (case-insensitive, whitespace-normalized).
  - Calculate a match score based on the number of query components found in the actual path (order matching).
  - Return chunks that have a high match score (e.g., matching all but one component, or a high percentage).

## Impact
- **Affected specs**: `structural_lookup` tool behavior.
- **Affected code**: `src/core/retriever.py`.

## MODIFIED Requirements
### Requirement: Fuzzy Path Matching
The `search_by_path` method SHALL return chunks where the chunk's path is a "fuzzy match" for the query path.
A "fuzzy match" is defined as:
1. The query components form a subsequence of the actual path components (allowing for skipped levels in actual path, or extra levels in query path within tolerance).
2. Component matching is case-insensitive and ignores whitespace differences.
3. Component matching allows the query component to be a prefix of the actual component (e.g. "3.1" matches "3.1 Title").
