# Tasks
- [ ] Task 1: Update `search_by_path` in `src/core/retriever.py` to support fuzzy matching.
  - [ ] Implement `_match_path_fuzzy` helper that calculates a match score.
  - [ ] Update `search_by_path` to use the scoring logic and return results with high scores (e.g. `matches >= len(query_parts) - 1` or similar logic).
  - [ ] Ensure strict component prefix matching is still supported (e.g. "3.1" matches "3.1 Title").

# Task Dependencies
- Task 1 is independent.
