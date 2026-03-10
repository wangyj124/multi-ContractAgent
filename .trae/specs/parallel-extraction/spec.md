# Parallel Extraction Spec

## Why
The current workflow processes fields sequentially (one by one), which is inefficient for long contracts with many independent fields. Processing 40-page contracts with multiple fields takes too long. Parallelizing the extraction of independent fields will significantly reduce total processing time.

## What Changes
- **Parallel Strategy**: Modify `supervisor_node` to identify and dispatch *multiple* tasks (3-5) at once instead of a single `current_task`.
- **Dynamic Dispatch (Send)**: Use LangGraph's `Send` API to map these tasks to parallel `worker` instances.
- **State Isolation**: Each parallel worker needs its own state context (at least `current_task`) to avoid interference. We likely need a subgraph or a specific state structure for the mapped nodes.
- **Aggregation**: Introduce an `aggregator` node to collect results from parallel workers and update the main state.
- **Concurrency Control**: Limit the number of parallel tasks (e.g., 5) to avoid rate limits.

## Impact
- **Affected Specs**: Workflow logic changes from linear loop to map-reduce style.
- **Affected Code**: `src/core/workflow.py`, `src/agents/nodes.py`, `src/core/state.py`.
- **Breaking Changes**: `AgentState` might need adjustment to support parallel branches or the workflow graph structure will change significantly. `supervisor_node` return type changes.

## ADDED Requirements

### Requirement: Batch Task Identification
The Supervisor SHALL identify a batch of up to `CONCURRENCY_LIMIT` (e.g., 5) missing fields from `task_list` that are ready for extraction.
The Supervisor SHALL return this list of tasks.

### Requirement: Parallel Worker Execution
The system SHALL use LangGraph's `Send` (Map-Reduce pattern) to spawn a `worker_subgraph` (or just `worker` node if possible) for each task in the batch.
Each parallel execution MUST have its own `current_task` context.

### Requirement: Result Aggregation
An `aggregator` node SHALL run after the parallel workers complete.
It SHALL collect `ExtractionResult`s from all branches and merge them into the global `extraction_results`.

### Requirement: Concurrency Limit
The number of parallel branches SHALL NOT exceed 5.

## MODIFIED Requirements
- **Workflow Graph**: 
    - Old: Supervisor -> Tools -> Supervisor -> Worker -> Validator -> Supervisor
    - New: Supervisor -> (Map/Send) -> [Branch: Tools -> Supervisor -> Worker -> Validator] -> Aggregator -> Supervisor
    - *Wait, the ReAct loop (Tools <-> Supervisor) is complex to parallelize if they share state.*
    - *Alternative Approach*: If we parallelize *extraction*, does each branch have its own ReAct loop?
    - Yes, each field extraction is an independent ReAct process.
    - So we need a **Subgraph** for the extraction process of a single field.
    - The Main Supervisor just dispatches tasks to the Subgraph.
    - The Subgraph contains: `FieldSupervisor` -> `Tools` -> `FieldSupervisor` -> `Worker` -> `Validator`.
    - This is a significant architectural shift.

### Revised Architecture:
1.  **Main Graph**: `TaskDispatcher` (Supervisor) -> `Map(Send)` -> `FieldExtractionSubgraph` -> `Aggregator` -> `End`.
2.  **FieldExtractionSubgraph**: The existing ReAct loop (`Supervisor` -> `Tools` -> `Worker` -> `Validator`).
    - Input: `current_task`, `document_structure`, `retriever` access.
    - Output: `ExtractionResult`.

Let's refine this. The user request says "Modify supervisor_node... to return 3-5 tasks... use LangGraph Send...".
If we simply parallelize `worker`, we assume `tools` are already done? No, the ReAct loop needs tools.
So we MUST parallelize the entire ReAct loop for each field.

## REMOVED Requirements
- **Sequential Processing**: The strict single-task loop in the main graph is replaced by parallel subgraphs.
