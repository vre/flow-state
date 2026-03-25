"""Tests for check_existing.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "youtube-to-markdown"))
from lib.check_existing import detect_comments_state, find_existing_files


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


class TestFindExistingFiles:
    """Tests for find_existing_files function."""

    def test_finds_files_with_date_prefix(self, tmp_path):
        """Find files with new date prefix format."""
        (tmp_path / "2024-01-15 - Test Title (abc123).md").write_text("summary")
        (tmp_path / "2024-01-15 - Test Title - comments (abc123).md").write_text("comments")
        (tmp_path / "2024-01-15 - Test Title - transcript (abc123).md").write_text("transcript")

        result = find_existing_files("abc123", tmp_path)

        assert result["summary_file"] is not None
        assert result["comment_file"] is not None
        assert result["transcript_file"] is not None

    def test_finds_files_without_date_prefix(self, tmp_path):
        """Find files with current format without date prefix."""
        (tmp_path / "Test Title (abc123).md").write_text("summary")
        (tmp_path / "Test Title - comments (abc123).md").write_text("comments")

        result = find_existing_files("abc123", tmp_path)

        assert result["summary_file"] is not None
        assert result["comment_file"] is not None

    def test_finds_legacy_files_with_youtube_prefix(self, tmp_path):
        """Legacy youtube-prefixed filenames still resolve."""
        (tmp_path / "youtube - Test Title (abc123).md").write_text("summary")
        (tmp_path / "youtube - Test Title - comments (abc123).md").write_text("comments")

        result = find_existing_files("abc123", tmp_path)

        assert result["summary_file"] is not None
        assert result["comment_file"] is not None

    def test_finds_no_files(self, tmp_path):
        """No matching files returns None."""
        result = find_existing_files("abc123", tmp_path)

        assert result["summary_file"] is None
        assert result["comment_file"] is None
        assert result["transcript_file"] is None

    def test_excludes_backup_files(self, tmp_path):
        """Backup files are excluded from results."""
        (tmp_path / "2024-01-15 - Test Title (abc123).md").write_text("summary")
        (tmp_path / "2024-01-15 - Test Title_backup_20240201 (abc123).md").write_text("backup")

        result = find_existing_files("abc123", tmp_path)

        assert result["summary_file"] is not None
        assert "_backup_" not in Path(result["summary_file"]).name
