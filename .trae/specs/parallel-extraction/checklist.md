# Checklist

- [x] Existing ReAct loop is encapsulated in a Subgraph.
- [x] Main graph uses `Send` to dispatch tasks to the Subgraph.
- [x] Dispatcher selects up to 5 tasks at a time.
- [x] Each branch operates independently (own `current_task`, own message history).
- [x] Aggregator correctly merges results into the main state.
- [x] System handles Rate Limits (via concurrency limit).
