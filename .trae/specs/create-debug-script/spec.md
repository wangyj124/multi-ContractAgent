# Document Structure Debug Script Spec

## Why
The user needs to verify the document structure extraction and summarization logic independently, without running the full agent workflow. The existing test script `tests/full_process_debug_test.py` is too heavy and includes unnecessary steps. A dedicated script will allow for faster iteration and verification of the document tree requirements (depth limit, summary format, etc.).

## What Changes
- Create a new Python script `tests/debug_doc_structure.py`.
- The script will:
  - Initialize `Archivist`.
  - Load the target document: `data/input/甘露机岛合同-20181211版最终-签字版（无价格版）.docx`.
  - Extract chunks.
  - Generate the document structure string.
  - Print the structure to stdout.
  - Verify specific requirements (e.g., presence of "Chapter 4", absence of "4.1.1", summary length).

## Impact
- **Affected specs**: None (new test tool).
- **Affected code**: New file `tests/debug_doc_structure.py`.

## ADDED Requirements
### Requirement: Debug Script
The script SHALL perform the following steps:
1. Load the specific contract file.
2. Call `archivist.extract_chunks()`.
3. Call `archivist.generate_document_structure()`.
4. Print the output.
5. (Optional) Perform programmatic assertions on the output string to check for compliance with depth and content rules.
