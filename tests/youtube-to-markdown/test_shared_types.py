"""Tests for shared types and utilities."""

import pytest
from shared_types import (
    extract_video_id, format_upload_date, format_subscribers,
    format_duration, clean_title_for_filename,
    VideoIdExtractionError
)


class TestExtractVideoId:
    """Tests for extract_video_id function."""

    def test_extract_from_youtu_be_url(self):
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_from_youtube_com_url(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_with_query_params(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_invalid_url_raises_error(self):
        url = "https://example.com/video"
        with pytest.raises(VideoIdExtractionError):
            extract_video_id(url)


class TestFormatUploadDate:
    """Tests for format_upload_date function."""

    def test_format_valid_date(self):
        assert format_upload_date("20240115") == "2024-01-15"

    def test_format_unknown_date(self):
        assert format_upload_date("Unknown") == "Unknown"

    def test_format_invalid_date(self):
        assert format_upload_date("2024") == "2024"


class TestFormatSubscribers:
    """Tests for format_subscribers function."""

    def test_format_integer_subscribers(self):
        assert format_subscribers(1000000) == "1,000,000 subscribers"

    def test_format_none_subscribers(self):
        assert format_subscribers(None) == "N/A subscribers"

    def test_format_string_subscribers(self):
        assert format_subscribers("N/A") == "N/A subscribers"


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_format_hours_minutes_seconds(self):
        assert format_duration(3661) == "01:01:01"

    def test_format_minutes_seconds(self):
        assert format_duration(125) == "02:05"

    def test_format_zero_duration(self):
        assert format_duration(0) == "Unknown"


class TestCleanTitleForFilename:
    """Tests for clean_title_for_filename function."""

    def test_remove_invalid_characters(self):
        title = 'Test: Video | "Title" <2024>'
        result = clean_title_for_filename(title)
        assert result == "Test Video Title 2024"

    def test_normalize_whitespace(self):
        title = "Test   Video    Title"
        result = clean_title_for_filename(title)
        assert result == "Test Video Title"

    def test_truncate_long_title(self):
        title = "A" * 100
        result = clean_title_for_filename(title, max_length=60)
        assert len(result) <= 60

    def test_truncate_at_word_boundary(self):
        title = "This is a very long title that needs to be truncated properly"
        result = clean_title_for_filename(title, max_length=30)
        # Should cut at word boundary and be within max_length
        assert len(result) <= 30
        # Result should end with a complete word
        assert not result.endswith(" ")  # No trailing space
