# Checklist

- [x] Prompts are loaded from `src/prompts/`.
- [x] `AgentState` tracks `task_status`.
- [x] `Navigation_Reflector` and `Context_Expander` tools work as expected.
- [x] Tool outputs are summarized (Denoising) before reaching Supervisor.
- [x] Workflow graph cycles Supervisor -> Tools -> Supervisor.
- [x] Supervisor correctly interprets observations and issues new commands.
- [x] "Final Answer" signal correctly routes to Worker.
- [x] Validator feedback is returned to Supervisor.
- [x] Message history is trimmed to the last 3 turns.
