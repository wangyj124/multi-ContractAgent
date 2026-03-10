# Tasks

- [x] Task 1: Prompt Management and State Update
  - [x] SubTask 1.1: Create `src/prompts/` and move existing prompts there.
  - [x] SubTask 1.2: Update `AgentState` in `src/core/state.py` to include `task_status` and ensure `messages` support sliding window logic (or implement trimming in nodes).

- [x] Task 2: Tool Enhancements and Denoising
  - [x] SubTask 2.1: Implement `Navigation_Reflector` and `Context_Expander` in `src/tools/lookup.py`.
  - [x] SubTask 2.2: Implement "Summary Worker" logic inside `LookupToolSet` to summarize large outputs.

- [x] Task 3: Workflow and Supervisor Refactoring
  - [x] SubTask 3.1: Modify `create_graph` in `src/core/workflow.py` to redirect `tools` -> `supervisor`.
  - [x] SubTask 3.2: Update `supervisor_node` in `src/agents/nodes.py` to handle observations, maintain the loop, and output "Final Answer" to break the loop.
  - [x] SubTask 3.3: Implement sliding window logic for message history in `supervisor_node`.

- [x] Task 4: Validator Feedback Loop
  - [x] SubTask 4.1: Update `validator_node` to return feedback as a message to Supervisor upon failure.
  - [x] SubTask 4.2: Update `create_graph` to route `validator` (failure) -> `supervisor`.

- [x] Task 5: Integration Verification
  - [x] SubTask 5.1: Verify the ReAct loop with a test case where Supervisor searches, reflects, and then extracts.
  - [x] SubTask 5.2: Verify validator feedback triggers a retry.
