# Checklist

- [x] Tree structure does not contain nodes deeper than Level 3 (e.g., no 2.1.1).
- [x] Headers longer than 10 chars are replaced by short titles (< 10 chars).
- [x] Short titles follow "序号 + 简短主题" format.
- [x] Summaries are not truncated with ellipsis by the system (only by LLM if instructed).
- [x] Content < 20 chars uses raw text as summary.
- [x] Content >= 20 chars uses LLM summary.
- [x] Level 3 summaries include content from "sub-clauses" (former Level 4+).
- [x] Logs show extraction depth, model calls, and aggregation stats.
- [x] "合同封面", "目录", "此页为合同签字页" are Level 1.
