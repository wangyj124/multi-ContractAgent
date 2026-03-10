# Live Model Test Spec

## Why
The system has been developed using Mock LLMs and a simplified environment. To ensure production readiness, we need to verify the full workflow using real Qwen3 models, focusing on connectivity, ReAct logic integrity, context management, and concurrency stability.

## What Changes
- **Environment Configuration**: Update `.env` and `src/core/llm.py` to support Qwen3 models via a local API (vLLM/OpenAI compatible).
- **Retriever Update**: Configure `Retriever` to use `qwen3-embedding-8B` (via OpenAI compatible endpoint or local embedding integration).
- **Test Script**: Create `tests/live_model_test.py` to run the full pipeline with real data and models.
- **Monitoring**: Implement detailed logging for ReAct thought process, token usage, and rate limits.

## Impact
- **Affected Code**: `src/core/llm.py`, `src/core/retriever.py`, `tests/live_model_test.py`.
- **Dependencies**: Requires a running model server (e.g., vLLM) at `http://127.0.0.1:10081/v1`.

## ADDED Requirements

### Requirement: Model Configuration
The system SHALL read `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `MODEL_SUPERVISOR`, `MODEL_WORKER`, and `MODEL_EMBEDDING` from environment variables.
`get_llm` SHALL use these variables to initialize `ChatOpenAI`.

### Requirement: Qwen3 Embedding Support
`Retriever` SHALL support an "openai" embedding mode (or similar) to use the `qwen3-embedding-8B` model via the API, OR use a compatible local library if the API supports embeddings.
*Note*: The user specified `MODEL_EMBEDDING=qwen3-embedding-8B` and `OPENAI_BASE_URL`. This implies using the OpenAI Embedding API interface.

### Requirement: Live Test Script
`tests/live_model_test.py` SHALL:
1.  Load `data/input/contract.docx` and `data/input/XT.xlsx`.
2.  Initialize Archivist and Retriever (with real embeddings).
3.  Run the LangGraph workflow.
4.  Print real-time logs:
    - Supervisor Thoughts (cyan).
    - Token usage per node (if available via callback or response metadata).
    - Rate limit warnings (429).
5.  Export results to `data/output/result_live.csv`.

### Requirement: Verification Points
The test execution must verify:
- **ReAct Logic**: Supervisor uses `structural_lookup` first.
- **Extraction**: Worker extracts correct values with evidence.
- **Context**: Context window stays within limits (trimming works).
- **Concurrency**: Parallel requests work without crashing (handling 429 if needed).

## MODIFIED Requirements
- **Retriever**: Add logic to use `OpenAIEmbeddings` (LangChain) or direct HTTP call for `qwen3-embedding-8B` when `embedding_model` is set to "openai" or similar, utilizing the base URL.
