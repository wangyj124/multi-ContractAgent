# Tasks

- [x] Task 1: Environment & Core Configuration
  - [x] SubTask 1.1: Create `.env` file with provided configuration.
  - [x] SubTask 1.2: Update `src/core/llm.py` to strictly respect `MODEL_SUPERVISOR` and `MODEL_WORKER` env vars.
  - [x] SubTask 1.3: Update `src/core/retriever.py` to support `OpenAIEmbeddings` using `MODEL_EMBEDDING` and `OPENAI_BASE_URL`.

- [x] Task 2: Live Test Script Implementation
  - [x] SubTask 2.1: Create `tests/live_model_test.py` based on `main.py` but with enhanced monitoring (token usage logging).
  - [x] SubTask 2.2: Ensure the script loads real data (`contract.docx`, `XT.xlsx`).

- [x] Task 3: Execution & Verification
  - [x] SubTask 3.1: Run `tests/live_model_test.py`.
  - [x] SubTask 3.2: Monitor and record:
      - Supervisor Thought process (screenshots or logs).
      - Token usage warnings.
      - Concurrency/Rate limit handling.
  - [x] SubTask 3.3: Verify final CSV output against requirements (all columns, correct extraction).
