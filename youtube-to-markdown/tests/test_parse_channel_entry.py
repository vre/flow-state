"""Tests for parse_channel_entry fields."""

from lib.channel_listing import parse_channel_entry


class TestParseChannelEntry:
    """Tests for parse_channel_entry()."""

    def test_view_count_included(self) -> None:
        """view_count raw int is in output."""
        entry = {
            "id": "vid1",
            "title": "Test",
            "view_count": 1_500_000,
            "description": "Video description",
            "duration_string": "10:00",
            "url": "https://youtube.com/watch?v=vid1",
        }
        result = parse_channel_entry(entry)
        assert result["view_count"] == 1_500_000
        assert result["views"] == "1.5M"  # formatted string also present
        assert result["description"] == "Video description"

    def test_view_count_none(self) -> None:
        """view_count is None when not in entry."""
        entry = {"id": "vid1", "title": "Test"}
        result = parse_channel_entry(entry)
        assert result["view_count"] is None
        assert result["views"] == "N/A"
        assert result["description"] == ""

    def test_view_count_zero(self) -> None:
        """view_count 0 is preserved, not treated as None."""
        entry = {
            "id": "vid1",
            "title": "Test",
            "view_count": 0,
            "duration_string": "0:30",
            "url": "https://youtube.com/watch?v=vid1",
        }
        result = parse_channel_entry(entry)
        assert result["view_count"] == 0

    def test_description_truncated_to_500_chars(self) -> None:
        """Description is capped at 500 chars for context budget."""
        long_description = "A" * 700
        entry = {
            "id": "vid1",
            "title": "Test",
            "view_count": 100,
            "description": long_description,
        }
        result = parse_channel_entry(entry)
        assert len(result["description"]) == 500
        assert result["description"] == long_description[:500]
