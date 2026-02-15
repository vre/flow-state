"""Tests for parse_channel_entry view_count addition."""

from lib.channel_listing import parse_channel_entry


class TestParseChannelEntryViewCount:
    """Tests for view_count raw int in parse_channel_entry()."""

    def test_view_count_included(self) -> None:
        """view_count raw int is in output."""
        entry = {
            "id": "vid1",
            "title": "Test",
            "view_count": 1_500_000,
            "duration_string": "10:00",
            "url": "https://youtube.com/watch?v=vid1",
        }
        result = parse_channel_entry(entry)
        assert result["view_count"] == 1_500_000
        assert result["views"] == "1.5M"  # formatted string also present

    def test_view_count_none(self) -> None:
        """view_count is None when not in entry."""
        entry = {"id": "vid1", "title": "Test"}
        result = parse_channel_entry(entry)
        assert result["view_count"] is None
        assert result["views"] == "N/A"

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
