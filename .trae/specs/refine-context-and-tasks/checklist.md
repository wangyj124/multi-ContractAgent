# Checklist

- [x] `Archivist.generate_document_structure` produces a correct hierarchical string from chunks.
- [x] `AgentState` includes `task_list` and `document_structure`.
- [x] `supervisor_node` correctly reads tasks from `state["task_list"]`.
- [x] `supervisor_node` system prompt includes the document structure.
- [x] `main.py` successfully loads tasks from `XT.xlsx` and passes them to the graph.
- [x] The entire workflow runs without errors and produces the expected CSV output using dynamic tasks.
