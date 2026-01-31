"""Tests for check_existing.py comment detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "youtube-to-markdown"))
from lib.check_existing import detect_comments_state


class TestDetectCommentsState:
    """Tests for detect_comments_state function."""

    def test_curated_only_no_insights(self):
        """File with only Curated Comments, no insights section."""
        content = """## Curated Comments

### 1. @user (5 likes)
Great video!

### 2. @another (2 likes)
Thanks for sharing.
"""
        assert detect_comments_state(content) == "curated_only"

    def test_v1_insights_no_type_sections(self):
        """File with Comment Insights but no type-specific sections (v1)."""
        content = """## Comment Insights

The comments discuss various approaches to the problem.
Users share their experiences with the technique.

## Curated Comments

### 1. @user (5 likes)
Great video!
"""
        assert detect_comments_state(content) == "v1"

    def test_v2_with_common_failures(self):
        """File with v2 type-specific section: Common Failures."""
        content = """## Comment Insights

**Common Failures**
- Users report issues with X
- Y doesn't work as expected

## Curated Comments

### 1. @user (5 likes)
Great video!
"""
        assert detect_comments_state(content) == "v2"

    def test_v2_with_success_patterns(self):
        """File with v2 type-specific section: Success Patterns."""
        content = """## Comment Insights

**Success Patterns**
- Approach A works well
- Best results with B

## Curated Comments

### 1. @user (5 likes)
Great video!
"""
        assert detect_comments_state(content) == "v2"

    def test_v2_with_points_of_debate(self):
        """File with v2 type-specific section: Points of Debate."""
        content = """## Comment Insights

**Points of Debate**
- Some prefer X over Y
- Discussion about best approach

## Curated Comments

### 1. @user (5 likes)
Great video!
"""
        assert detect_comments_state(content) == "v2"

    def test_v2_with_multiple_type_sections(self):
        """File with multiple v2 type-specific sections."""
        content = """## Comment Insights

**Common Failures**
- Issue X

**Success Patterns**
- Approach Y

## Curated Comments

### 1. @user (5 likes)
Great video!
"""
        assert detect_comments_state(content) == "v2"

    def test_empty_content(self):
        """Empty file content."""
        content = ""
        assert detect_comments_state(content) == "curated_only"

    def test_no_relevant_sections(self):
        """File with neither Curated Comments nor Comment Insights."""
        content = """## Some Other Section

Random content here.
"""
        assert detect_comments_state(content) == "curated_only"
