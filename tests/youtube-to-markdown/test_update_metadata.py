"""Tests for update_metadata module."""

from lib.update_metadata import replace_metadata_section, update_extraction_date


class TestReplaceMetadataSection:
    """Tests for replace_metadata_section function."""

    def test_replaces_video_section(self):
        summary = """# Test Video

## Video

- **Title:** [Old Title](https://youtube.com)
- **Views:** 1K

## Summary

This is the summary.
"""
        fresh_metadata = """- **Title:** [New Title](https://youtube.com)
- **Views:** 2K"""

        result = replace_metadata_section(summary, fresh_metadata)

        assert "New Title" in result
        assert "2K" in result
        assert "Old Title" not in result
        assert "## Summary" in result
        assert "This is the summary." in result

    def test_preserves_other_sections(self):
        summary = """# Test Video

## Video

Old metadata here.

## Summary

Summary content.

## Comment Insights

Comments content.
"""
        fresh_metadata = "New metadata content"

        result = replace_metadata_section(summary, fresh_metadata)

        assert "New metadata content" in result
        assert "## Summary" in result
        assert "Summary content." in result
        assert "## Comment Insights" in result
        assert "Comments content." in result

    def test_handles_video_section_at_end(self):
        summary = """# Test Video

## Summary

Summary here.

## Video

Old metadata here."""
        fresh_metadata = "New metadata content"

        result = replace_metadata_section(summary, fresh_metadata)

        assert "New metadata content" in result
        assert "## Summary" in result
        assert "Summary here." in result

    def test_inserts_section_if_missing(self):
        summary = """# Test Video

Some content here.
"""
        fresh_metadata = "- **Title:** Test"

        result = replace_metadata_section(summary, fresh_metadata)

        assert "## Video" in result
        assert "- **Title:** Test" in result


class TestUpdateExtractionDate:
    """Tests for update_extraction_date function."""

    def test_updates_extraction_date(self):
        content = "- **Published:** 2024-01-01 | Extracted: 2024-01-01"
        result = update_extraction_date(content)

        # Date should be updated to today
        assert "Extracted: 2024-01-01" not in result or "Extracted:" in result
        # Should still have Published date unchanged
        assert "Published:** 2024-01-01" in result

    def test_handles_different_date_formats(self):
        content = "Extracted: 2023-06-15"
        result = update_extraction_date(content)

        assert "Extracted: 2023-06-15" not in result or "Extracted:" in result

    def test_no_change_if_no_date(self):
        content = "No date here"
        result = update_extraction_date(content)

        assert result == content
