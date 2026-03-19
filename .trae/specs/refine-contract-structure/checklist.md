# Checklist

- [x] Regex `HIERARCHY_PATTERNS` correctly identifies "第一卷", "第一章", "1.", "10(A)".
- [x] First page is correctly identified as "合同封面".
- [x] "目录" is correctly identified as Level 1.
- [x] Level 4+ content (e.g., "1.1.1") is aggregated into Level 3 (e.g., "1.1" or "1.") summary.
- [x] Summarization uses `qwen3-30B-A3B-Instruct`.
- [x] Short content (< 50 words) uses raw text as summary.
- [x] Long content (>= 50 words) uses LLM summary (50-150 words).
- [x] `generate_document_structure` output format follows `Title (Summary)`.
- [x] Tree structure does not show Level 4+ nodes explicitly.
