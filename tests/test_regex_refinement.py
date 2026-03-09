import pytest
import re
from src.core.archivist import Archivist, HIERARCHY_PATTERNS

class TestRegexRefinement:
    @pytest.fixture
    def archivist(self):
        return Archivist()

    def test_volume_pattern(self, archivist):
        # Volume: Depth 1
        text = "第一卷 总则"
        hierarchy = archivist._detect_hierarchy(text, [])
        assert len(hierarchy) == 1
        assert hierarchy[0] == text

    def test_special_page_pattern(self, archivist):
        # Special Page: Depth 1
        text = "此页为合同签字页"
        hierarchy = archivist._detect_hierarchy(text, [])
        assert len(hierarchy) == 1
        assert hierarchy[0] == text

    def test_chapter_pattern(self, archivist):
        # Chapter: Depth 2
        text = "第一章 定义"
        # Simulate existing hierarchy of depth 1
        current = ["第一卷"]
        hierarchy = archivist._detect_hierarchy(text, current)
        assert len(hierarchy) == 2
        assert hierarchy[0] == "第一卷"
        assert hierarchy[1] == text

    def test_attachment_pattern(self, archivist):
        # Attachment: Depth 3
        text = "附件1 技术规格书"
        current = ["第一卷", "第一章"]
        hierarchy = archivist._detect_hierarchy(text, current)
        assert len(hierarchy) == 3
        assert hierarchy[-1] == text

    def test_clause_pattern(self, archivist):
        # Clause (X.X.X): Depth 4
        text = "4.2.1 详细条款"
        current = ["Vol", "Chap", "Sec"]
        hierarchy = archivist._detect_hierarchy(text, current)
        assert len(hierarchy) == 4
        assert hierarchy[-1] == text

    def test_section_pattern(self, archivist):
        # Section (X.X): Depth 3
        text = "4.2 一般条款"
        current = ["Vol", "Chap"]
        hierarchy = archivist._detect_hierarchy(text, current)
        assert len(hierarchy) == 3
        assert hierarchy[-1] == text

    def test_special_clause_pattern(self, archivist):
        # Special Clause: Depth 3
        text = "第10（A）条 特别约定"
        current = ["Vol", "Chap"]
        hierarchy = archivist._detect_hierarchy(text, current)
        assert len(hierarchy) == 3
        assert hierarchy[-1] == text

    def test_clause_vs_section_priority(self, archivist):
        # Test "4.2.1 Title" matches Depth 4 (not 3 via Section pattern)
        text = "4.2.1 Title"
        # Start with enough context
        current = ["L1", "L2", "L3"]
        hierarchy = archivist._detect_hierarchy(text, current)
        
        # If matched Section (Depth 3), it would truncate to 2 and append -> length 3
        # If matched Clause (Depth 4), it would truncate to 3 and append -> length 4
        # Since Clause is checked before Section, it should match Clause.
        assert len(hierarchy) == 4, "Should match Clause pattern (Depth 4) before Section pattern (Depth 3)"
        assert hierarchy[-1] == text

    def test_clause_vs_section_priority_explicit_check(self):
        # Explicitly check patterns order and matching
        text = "4.2.1 Title"
        
        matched_patterns = []
        for pattern, depth in HIERARCHY_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                matched_patterns.append((pattern, depth))
        
        # We expect multiple matches potentially, but the first one in the list is what matters for _detect_hierarchy
        first_match = matched_patterns[0]
        assert first_match[1] == 4, f"First match should be Depth 4, got {first_match[1]} from pattern {first_match[0]}"

    def test_dynamic_fallback(self, archivist):
        # Test dynamic fallback for deeper levels if not covered?
        # The dynamic fallback is `r"^(\d+(\.\d+)+)"` with depth -1.
        # It handles X.X.X.X etc.
        text = "1.2.3.4.5 Deep"
        # 1.2.3.4.5 has 4 dots -> depth 5.
        current = ["L1", "L2", "L3", "L4"]
        hierarchy = archivist._detect_hierarchy(text, current)
        assert len(hierarchy) == 5
        assert hierarchy[-1] == text
