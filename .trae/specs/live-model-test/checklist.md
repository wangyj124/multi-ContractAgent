# Checklist

- [x] `.env` file is created with correct Qwen3 settings.
- [x] `Retriever` successfully generates embeddings using `qwen3-embedding-8B` via API.
- [x] `tests/live_model_test.py` runs without errors.
- [x] Supervisor logs show "Thought" process using `structural_lookup` prioritized.
- [x] Token usage is logged and stays within 8192 limit (trimming active).
- [x] `result_live.csv` contains all expected columns and valid data.
