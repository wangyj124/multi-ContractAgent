# Refine Context and Tasks Spec

## Why
Currently, the system uses hardcoded task lists (`XT_TASKS`) and the supervisor lacks a global view of the document structure, which can lead to inefficient retrieval and task planning. The goal is to make the system dynamic and context-aware.

## What Changes
- **Dynamic Task Loading**: Replace the hardcoded `XT_TASKS` in `nodes.py` with a dynamically loaded list from `XT.xlsx` (via `XTParser`), injected into the `AgentState`.
- **Central Context Management**: Implement a `generate_document_structure` method in `Archivist` to create a "Summary Tree" of the document. Inject this tree into `AgentState` so the `supervisor_node` can use it for better planning.
- **State Update**: Add `task_list` and ensure `document_structure` is populated in `AgentState`.

## Impact
- Affected files: `src/core/archivist.py`, `src/core/state.py`, `src/agents/nodes.py`, `main.py`, `src/core/task_init.py` (if needed).
- Improved flexibility: Changing `XT.xlsx` will automatically update the agent's tasks without code changes.
- Improved accuracy: Supervisor will have a map of the document (Chapter 1, 1.1, etc.) to guide `structural_lookup`.

## ADDED Requirements

### Requirement: Central Context Management (Summary Tree)
The `Archivist` SHALL generate a hierarchical summary of the document (e.g., a tree string of headers).
This summary SHALL be injected into `AgentState` under `document_structure`.
The `supervisor_node` SHALL include this structure in its system prompt to inform tool selection.

#### Scenario: Supervisor Planning
- **WHEN** the Supervisor starts planning for a task (e.g., "Payment Terms").
- **THEN** it sees the `document_structure` (e.g., "Chapter 2: Financials > 2.2 Payment").
- **AND** it chooses `structural_lookup("Chapter 2/2.2")` instead of a generic search.

### Requirement: Dynamic Task List Integration
The system SHALL load extraction tasks from `XT.xlsx` using `XTParser`.
The tasks SHALL be stored in `AgentState` as `task_list`.
The `supervisor_node` SHALL iterate through `state["task_list"]` to determine the next task, instead of using a hardcoded global list.

## MODIFIED Requirements

### Requirement: Agent State
`AgentState` will be updated to include:
- `task_list`: List[str] (The list of fields to extract)
- `document_structure`: str (The hierarchical summary)
