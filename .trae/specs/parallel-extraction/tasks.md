# Tasks

- [x] Task 1: Define Field Extraction Subgraph
  - [x] SubTask 1.1: Refactor the existing ReAct loop (`supervisor`, `tools`, `worker`, `validator`) into a reusable `StateGraph` (Subgraph).
  - [x] SubTask 1.2: Define the `FieldState` (subset of `AgentState`) for the subgraph.

- [x] Task 2: Implement Main Dispatcher
  - [x] SubTask 2.1: Create `dispatcher_node` (replacing the old top-level supervisor logic) to select batch of tasks.
  - [x] SubTask 2.2: Implement logic to yield `Send` objects for each selected task, targeting the Subgraph.

- [x] Task 3: Implement Aggregator
  - [x] SubTask 3.1: Create `aggregator_node` to merge results from the subgraph branches.

- [x] Task 4: Update Workflow Construction
  - [x] SubTask 4.1: Modify `src/core/workflow.py` to use the new architecture (Dispatcher -> Map -> Subgraph -> Aggregator).
  - [x] SubTask 4.2: Set `CONCURRENCY_LIMIT` logic (can be handled by LangGraph's logic or simple slicing in Dispatcher).

- [x] Task 5: Verification
  - [x] SubTask 5.1: Verify parallel execution (logs should show interleaved or concurrent processing).
  - [x] SubTask 5.2: Verify all results are aggregated correctly.
