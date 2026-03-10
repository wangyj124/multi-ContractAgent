# Debugging & Progress Design Spec

## Why
The system currently operates as a "black box," making it difficult to understand internal decision-making, track progress, or debug failures. Real-time feedback and structured debugging information are essential for industrial-grade applications.

## What Changes
- **Progress Monitoring**: Integrate `tqdm` in `main.py` to visualize task completion progress.
- **Thought Visualization**: Add colored console output in `field_supervisor_node` to display the agent's current goal and plan.
- **Navigation History**: Enhance `FieldState` to track the search path (e.g., "Chapter 2/Section 4") for each field.
- **Tracing Integration**: Add optional LangSmith support in `src/core/llm.py` via `LANGCHAIN_TRACING_V2`.
- **Failure Classification**: Update `validator_node` to categorize and log failure reasons (e.g., "Missing", "Logic Error").

## Impact
- **Affected Code**: `main.py`, `src/agents/nodes.py`, `src/core/state.py`, `src/core/llm.py`.
- **Dependencies**: New dependency `tqdm` and potentially `colorama` or `termcolor` for colored output (or just ANSI codes).

## ADDED Requirements

### Requirement: Real-time Progress Bar
`main.py` SHALL use `tqdm` to wrap the execution loop (or update manually) to show "Processed X/Y tasks".
The progress bar description SHALL update to show the current batch of tasks.

### Requirement: Thought Visualization
`field_supervisor_node` SHALL print a highlighted message (e.g., Cyan color) to the console: `[THINKING] Goal: {task}, Plan: {plan}`.

### Requirement: Navigation History Tracking
`FieldState` SHALL include a `navigation_history` list.
Every time a tool is called (or `structural_lookup` specifically), the target path SHALL be appended to this history.
The final output (CSV) SHALL include a "Search Path" column summarizing this history.

### Requirement: LangSmith Integration
`src/core/llm.py` SHALL check for `LANGCHAIN_TRACING_V2` environment variable. If set, it ensures LangChain tracing is enabled (usually automatic if env var is present, but we can add explicit logging).

### Requirement: Failure Reason Classification
`validator_node` SHALL classify errors into categories:
- `MISSING_CONTENT`: Value is null/empty.
- `LOGIC_ERROR`: Date mismatch, sum mismatch.
- `FORMAT_ERROR`: Parsing failed.
These categories SHALL be logged and potentially added to the result output.

## MODIFIED Requirements
- **AgentState/FieldState**: Add `navigation_history`.
- **ExtractionResult**: Might need a field for `failure_reason` if not just using `validation_notes`.
