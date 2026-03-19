# Debug Verification Hang Spec

## Why
The verification script `verify_refinement.py` hangs indefinitely during LLM calls, preventing validation of the document processing logic. The user requires more debug information and a restart of the verification process.

## What Changes
- **Recreate Verification Script**: Restore `verify_refinement.py` which was deleted.
- **Enhanced Debug Logging**: Add detailed start/end logs around LLM invocations in `src/core/archivist.py` to identify exactly where it hangs.
- **Timeout Mechanism**: Add a timeout to the LLM invocation (if possible via `invoke` params or wrapper) to prevent indefinite hanging.
- **Output Flushing**: Ensure print statements are flushed immediately to the console.

## Impact
- **Affected specs**: `refine-structure-logging` (verification step).
- **Affected code**: `src/core/archivist.py`, `verify_refinement.py` (new).

## ADDED Requirements
### Requirement: Debug Logging
The system SHALL log the following events with timestamps:
- Before LLM call: `[模型调用] 开始调用 LLM... (Model: {model_name})`
- After LLM call: `[模型调用] LLM 调用完成，耗时: {duration}s`
- Error during LLM call: `[错误] LLM 调用异常: {error}`

### Requirement: Timeout Protection
The system SHOULD attempt to set a timeout for LLM calls (e.g., 60 seconds) to fail fast if the model server is unresponsive.

### Requirement: Verification Script
A script `verify_refinement.py` SHALL be created to:
- Load the specified real document.
- Run `extract_chunks` and `generate_document_structure`.
- Print the resulting tree.
- Flush stdout after every print.

## MODIFIED Requirements
### Requirement: LLM Invocation
- Update `_generate_smart_summary` and `_generate_short_title` to include the new logging and timeout logic.
