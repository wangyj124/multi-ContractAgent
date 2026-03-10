# ReAct Optimization Spec

## Why
The current workflow has a linear Supervisor -> Tool -> Worker flow, which prevents the Supervisor from reasoning based on tool outputs (Observations). Additionally, context management is inefficient, tool capabilities are limited, and validation feedback is not utilized for self-correction.

## What Changes
- **Workflow Reconfiguration**: Redirect `tools` output back to `supervisor` to enable a true ReAct loop.
- **Information Denoising**: Introduce a "Summary Worker" step within the tool execution or as a pre-processing step to summarize large text before returning to Supervisor.
- **Context Management**: Implement a sliding window for `messages` in `AgentState` to keep only the last 3 turns.
- **Tool Enhancement**:
    - Add `Navigation_Reflector` (returns logical coordinates).
    - Add `Context_Expander` (retrieves surrounding chunks).
- **Task State Machine**: Introduce `Task_Context` with states (Initial_Search, Following_Clue, Validating) and enforce atomic task execution.
- **Feedback Loop**: Enhance `validator_node` to return specific error observations to Supervisor instead of just logging notes.
- **Prompt Management**: Move prompts to a dedicated folder structure.

## Impact
- **Affected Code**: `src/core/workflow.py`, `src/agents/nodes.py`, `src/core/state.py`, `src/tools/lookup.py`.
- **Breaking Changes**: The graph structure changes (Tools -> Supervisor). `AgentState` structure might need updates for task status.

## ADDED Requirements

### Requirement: Observation-Driven Loop
The workflow SHALL be: Supervisor -> Tools -> Supervisor.
The Supervisor SHALL analyze the Tool Output (Observation) and decide to:
1. Call another tool (e.g., Navigation, Context Expansion).
2. Or, if sufficient information is found, output "Final Answer" to trigger the transition to Worker (for extraction).
**Termination Signal**: When Supervisor outputs "Final Answer", flow goes to Worker.

### Requirement: Information Denoising
Tool outputs SHALL be summarized if they exceed a token limit (e.g., > 500 words).
A lightweight LLM call (Summary Worker) SHALL be used to generate this summary.

### Requirement: Context Sliding Window
`AgentState` SHALL maintain a trimmed history of messages (last 3 turns of Thought-Action-Observation).

### Requirement: New Tools
- `Navigation_Reflector`: Input path/query, Output logical tree location.
- `Context_Expander`: Input chunk_id, Output surrounding text (+/- 1 chunk).

### Requirement: Task State Machine
`AgentState` SHALL track `task_status` for the `current_task`.
Supervisor SHALL only switch tasks after the current one is validated or deemed not found after retries.

### Requirement: Validator Feedback
`validator_node` SHALL return a `ToolMessage` (or equivalent Observation) if validation fails, containing the specific error details, and route back to Supervisor.

### Requirement: Prompt Management
Create `src/prompts/` directory.
Store system prompts in separate files (e.g., `supervisor.txt`, `worker.txt`).

## MODIFIED Requirements
- **Supervisor Node**: Must handle ToolMessages in input and decide next step based on them.
- **Workflow Graph**: Change edge `tools` -> `worker` to `tools` -> `supervisor`. Add conditional edge from `supervisor` to `worker` (when "Final Answer" detected).

## REMOVED Requirements
- **Linear Flow**: The direct `tools` -> `worker` edge is removed.
