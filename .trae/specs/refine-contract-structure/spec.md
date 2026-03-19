# Refine Contract Structure Spec

## Why
Current document parsing lacks granularity for complex contracts, missing special pages like covers and signature pages, and struggling with nested clause numbering. Summarization is also uniform, wasting resources on short sections and missing context from nested clauses.

## What Changes
- **Regex Patterns**: comprehensive update to `HIERARCHY_PATTERNS` to support 4 levels of hierarchy and special pages.
- **Extraction Logic**: explicitly handle cover pages, TOC, and content aggregation for lower-level clauses.
- **Summarization**: switch to `qwen3-30B-A3B-Instruct`, implement conditional summarization based on length, and include aggregated content.
- **Tree Generation**: output a specific format where summaries follow titles.

## Impact
- **Affected specs**: Document ingestion and processing.
- **Affected code**: `src/core/archivist.py`

## ADDED Requirements
### Requirement: Hierarchy Recognition
The system SHALL recognize the following hierarchy levels:
- **Level 1**: Contract Cover (First Page), Table of Contents, Volume (第一卷/第二卷), Signature Page.
- **Level 2**: Chapter (第一章).
- **Level 3**: Main Clause (1., 2.1, 10(A)).
- **Level 4+**: Sub-clauses (1.1.1) should be merged into Level 3 content for summarization and not appear as independent nodes in the high-level tree.

### Requirement: Conditional Summarization
The system SHALL generate summaries based on content length:
- **< 50 words**: Use original text.
- **>= 50 words**: Use `qwen3-30B-A3B-Instruct` to generate a 50-150 word summary.
- **Context**: Summaries for Level 3 clauses must include content from their Level 4+ sub-clauses.

## MODIFIED Requirements
### Requirement: Document Extraction
- **Cover Page**: The first page of the document is automatically treated as "Contract Cover" unless otherwise identified.
- **Table of Contents**: Explicitly identify "目录" as a Level 1 node.
- **Buffer Management**: Ensure all sub-content (Level 4+) is accumulated before generating the summary for the parent Level 3 node.

### Requirement: Tree Output
The `generate_document_structure` output format SHALL be:
`Title (Summary)` or `Title \n (Summary)`
Example: `第一卷 (摘要...) -> 第一章 -> 1. (摘要...)`
