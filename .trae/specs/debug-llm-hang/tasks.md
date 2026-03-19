# Tasks

- [ ] Task 1: Create Connectivity Test Script
  - [ ] Create `test_llm_connection.py` that uses `src.core.llm.get_llm` to send a simple "Hello" query.
  - [ ] Run this script immediately to confirm if the API endpoint is accessible.

- [ ] Task 2: Add Deep Debug Logging
  - [ ] Modify `src/core/archivist.py` to log prompt details (length, preview) and model configuration before invocation.
  - [ ] Ensure logs are flushed to stdout.

- [ ] Task 3: Verify with Real Document (Again)
  - [ ] Run `uv run python3 verify_refinement.py` with the new logging.
  - [ ] Analyze if the hang happens *before* sending bytes or *while waiting* for a response.
