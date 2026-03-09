# Tasks

- [x] Task 1: Enhance Archivist with Document Structure Generation
  - [x] SubTask 1.1: Implement `generate_document_structure(chunks)` in `Archivist` to build a tree string from chunk metadata.
  - [x] SubTask 1.2: Verify the tree structure with a test case.

- [x] Task 2: Dynamic Task List Integration
  - [x] SubTask 2.1: Update `AgentState` in `src/core/state.py` to include `task_list`.
  - [x] SubTask 2.2: Update `supervisor_node` in `src/agents/nodes.py` to use `state["task_list"]` instead of global `XT_TASKS`.
  - [x] SubTask 2.3: Remove hardcoded `XT_TASKS` from `src/agents/nodes.py`.

- [x] Task 3: Integration in Main Workflow
  - [x] SubTask 3.1: Update `main.py` to use `XTParser` to load tasks.
  - [x] SubTask 3.2: Update `main.py` to generate document structure after chunking.
  - [x] SubTask 3.3: Initialize `AgentState` with `task_list` and `document_structure`.
  - [x] SubTask 3.4: Verify the full flow with `main.py`.
