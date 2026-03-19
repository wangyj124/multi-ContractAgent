# Debug LLM Hang Spec

## Why
The document processing pipeline hangs indefinitely when calling the LLM for summarization. The previous attempt to add logging showed where it hung (during the "Contract Cover" summary) but didn't explain *why*. We need to verify basic connectivity to the model server and inspect the exact payload being sent to rule out malformed prompts or connection issues.

## What Changes
- **Standalone Connectivity Test**: Create a script to test the LLM API directly with a minimal prompt.
- **Deep Logging**: Modify `src/core/archivist.py` to log:
    - The exact text content (preview) being sent to the LLM.
    - The prompt template after formatting.
    - The model parameters (URL, key masked, model name).
- **Environment Verification**: Ensure the `get_llm` function is correctly picking up the environment variables.

## Impact
- **Affected specs**: Debugging only.
- **Affected code**: `src/core/archivist.py`, `test_llm_connection.py` (new).

## ADDED Requirements
### Requirement: LLM Connectivity Test
A script `test_llm_connection.py` SHALL be created to:
- Import `get_llm` from `src.core.llm`.
- Invoke the model with a simple "Hello" message.
- Print the response and the time taken.
- Handle and print any connection errors/timeouts explicitly.

### Requirement: Request Inspection Logging
In `src/core/archivist.py` (`_generate_smart_summary` and `_generate_short_title`), the system SHALL log BEFORE the `llm.invoke` call:
- `[DEBUG] Requesting Model: {model_name}`
- `[DEBUG] Prompt Length: {len(prompt)} chars`
- `[DEBUG] Prompt Preview: {prompt[:100]}...`
- `[DEBUG] Text Content Preview: {text[:100]}...`

## MODIFIED Requirements
### Requirement: Error Handling
- Catch `httpx.ConnectError`, `httpx.ReadTimeout`, and generic `Exception` specifically to differentiate between connection failure and model hanging.
