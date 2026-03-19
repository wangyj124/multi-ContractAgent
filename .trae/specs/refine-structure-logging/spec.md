# Refine Structure and Logging Spec

## Why
Current document processing creates an overly granular tree structure, fails to handle long titles effectively, truncates summaries arbitrarily, and lacks sufficient debugging information.

## What Changes
- **Hierarchy Limiting**: Remove Level 4+ regex patterns. Treat Level 4+ content as part of Level 3 nodes.
- **Title Refinement**: Use LLM to extract short titles (< 10 chars) for headers > 10 chars.
- **Enhanced Summarization**:
    - Remove hard truncation in summaries.
    - Summarize Level 3 nodes including all their sub-content (Level 4+).
    - Conditional summary: < 20 chars uses raw text; > 20 chars uses LLM (max 50 chars).
- **Special Pages**: Ensure Cover, TOC, and Signature pages are Level 1 and properly summarized.
- **Logging**: Add detailed console logs for extraction, model calls, and statistics.

## Impact
- **Affected specs**: Document ingestion.
- **Affected code**: `src/core/archivist.py`

## ADDED Requirements
### Requirement: Level 3 Limit
The system SHALL NOT create tree nodes deeper than Level 3 (e.g., 2.1).
- Patterns like `2.1.1` SHALL be treated as body text belonging to `2.1`.
- `HIERARCHY_PATTERNS` SHALL be updated to remove Level 4 patterns.

### Requirement: Short Title Extraction
- **WHEN** a Level 3 header is longer than 10 characters
- **THEN** the system SHALL call `qwen3-30B-A3B-Instruct` to generate a short title (< 10 chars).
- **Format**: `序号 + 简短主题` (e.g., "5.1 交货期要求").

### Requirement: Enhanced Logging
The system SHALL log:
- `[提取层级] 检测到标题: {text} -> 映射深度: {depth}`
- `[模型调用] 正在为 "{title}" 生成摘要/精简标题...`
- `[数据聚合] 条款 {level_3_node} 包含子条款字数: {total_chars}`
- Final stats: Total nodes, total chunks, time taken (optional).

## MODIFIED Requirements
### Requirement: Summarization Logic
- **Threshold**:
    - If content length < 20 chars: Use raw text.
    - If content length >= 20 chars: Use LLM to generate summary (max 50 chars).
- **Scope**: Summary for Level 3 nodes MUST include content from all subsequent text until the next Level 1-3 header.
- **Completeness**: The summary string returned by LLM SHALL be used in full without post-processing truncation (ellipsis).

### Requirement: Tree Structure Output
The output format SHALL be: `Title (Summary)`, where Summary is the full string from the summarization step.
