# Regex Refinement Spec

## Why
The current hierarchy detection patterns are too generic and do not support the specific multi-level structure required by the user (Volumes, Special Pages, Attachments, and specific Clause formats).

## What Changes
- **Refine `HIERARCHY_PATTERNS`**: Update the list of regex patterns and associated depths in `src/core/archivist.py` to strictly follow the user's requirements.
- **Specific Patterns**:
    - Volume/Book/Part: Depth 1
    - Special Page (Signature): Depth 1
    - Chapter: Depth 2
    - Attachment: Depth 3
    - Section (X.X): Depth 3
    - Clause (X.X.X): Depth 4
    - Special Clause (10(A)): Depth 3
- **Order Matters**: Ensure more specific patterns (like X.X.X) come before general ones (X.X) to avoid partial matches being misinterpreted.

## Impact
- Affected Code: `src/core/archivist.py`.
- Affected Tests: `tests/test_enhanced_archivist.py` (may need updates if existing tests rely on old depths). New tests will be added.

## ADDED Requirements

### Requirement: Specific Hierarchy Patterns
The system SHALL use the following regex patterns for hierarchy detection:
1.  **Volume/Book/Part**: `r'^(第[一二三四五六七八九十\d]+[卷册篇])'`, Depth 1.
2.  **Special Page**: `r'^(此页为合同签字页)$'`, Depth 1.
3.  **Chapter**: `r'^(第[一二三四五六七八九十\d]+章)'`, Depth 2.
4.  **Attachment**: `r'^([商务技术]*附件\s*\d+)'`, Depth 3.
5.  **Clause (X.X.X)**: `r'^(\d+\.\d+\.\d+)'`, Depth 4.
6.  **Section (X.X)**: `r'^(\d+\.\d+)'`, Depth 3.
7.  **Special Clause**: `r'^(第\d+[（(][A-Z][）)]条)'`, Depth 3.

### Requirement: Pattern Priority
Patterns SHALL be ordered such that longer/more specific matches are checked first (e.g., X.X.X before X.X).

## MODIFIED Requirements
- **Hierarchy Detection Logic**: The `_detect_hierarchy` method logic remains largely the same but will use the new pattern list. The dynamic depth calculation for dots might be removed or kept as a fallback if no specific pattern matches, but given the user's strict requirements, we should prioritize the explicit patterns.

## REMOVED Requirements
- **Dynamic Dot-Based Depth**: The generic `^(\d+(\.\d+)+)` pattern with dynamic depth calculation might be deprioritized or removed in favor of explicit X.X and X.X.X patterns if the user only wants those levels. However, keeping it as a fallback at the end is safer.
