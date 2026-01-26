"""Tests for apply_paragraph_breaks module."""

import pytest
from pathlib import Path
from lib.paragraph_breaker import ParagraphBreaker, ParsedLine, extract_video_id_from_path
from lib.shared_types import FileOperationError


class TestParagraphBreaker:
    """Tests for ParagraphBreaker class."""

    def test_parse_break_points_success(self):
        """Test parsing valid break points string."""
        breaker = ParagraphBreaker()
        result = breaker.parse_break_points("15,42,78,103")
        assert result == {15, 42, 78, 103}

    def test_parse_break_points_with_spaces(self):
        """Test parsing break points with spaces."""
        breaker = ParagraphBreaker()
        result = breaker.parse_break_points("15, 42, 78, 103")
        assert result == {15, 42, 78, 103}

    def test_parse_break_points_invalid_format(self):
        """Test error on invalid break points format."""
        breaker = ParagraphBreaker()
        with pytest.raises(ValueError, match="Invalid break points format"):
            breaker.parse_break_points("15,abc,78")

    def test_parse_transcript_line_with_timestamp(self):
        """Test parsing line with timestamp."""
        breaker = ParagraphBreaker()
        line = "[00:00:01.080] Hello world"
        result = breaker.parse_transcript_line(line)

        assert result.timestamp == "[00:00:01.080]"
        assert result.text == "Hello world"

    def test_parse_transcript_line_without_timestamp(self):
        """Test parsing line without timestamp."""
        breaker = ParagraphBreaker()
        line = "Plain text"
        result = breaker.parse_transcript_line(line)

        assert result.timestamp is None
        assert result.text == "Plain text"

    def test_apply_breaks_success(self, mock_fs, sample_deduped_transcript):
        """Test successful paragraph break application."""
        breaker = ParagraphBreaker(fs=mock_fs)

        input_path = Path("/input.md")
        output_path = Path("/output.md")
        mock_fs.write_text(input_path, sample_deduped_transcript)

        # Break after lines 2 and 4
        break_points = {2, 4}
        paragraph_count = breaker.apply_breaks(input_path, output_path, break_points)

        assert paragraph_count == 3
        content = mock_fs.read_text(output_path)
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        assert len(paragraphs) == 3

        # First paragraph should have lines 1-2
        assert "First line of text Second line of text" in paragraphs[0]
        assert "[00:00:01.000]" in paragraphs[0]

    def test_apply_breaks_file_not_found(self, mock_fs):
        """Test error when input file doesn't exist."""
        breaker = ParagraphBreaker(fs=mock_fs)

        with pytest.raises(FileOperationError, match="not found"):
            breaker.apply_breaks(
                Path("/nonexistent.md"),
                Path("/output.md"),
                {2, 4}
            )

    def test_apply_breaks_no_paragraphs_created(self, mock_fs):
        """Test error when no paragraphs are created."""
        breaker = ParagraphBreaker(fs=mock_fs)

        input_path = Path("/input.md")
        output_path = Path("/output.md")
        mock_fs.write_text(input_path, "")  # Empty input

        with pytest.raises(FileOperationError, match="No paragraphs created"):
            breaker.apply_breaks(input_path, output_path, {1})

    def test_apply_breaks_single_paragraph(self, mock_fs):
        """Test with no break points (single paragraph)."""
        breaker = ParagraphBreaker(fs=mock_fs)

        input_content = "[00:00:01.000] Line one\n[00:00:02.000] Line two"
        input_path = Path("/input.md")
        output_path = Path("/output.md")
        mock_fs.write_text(input_path, input_content)

        # Break at end only
        paragraph_count = breaker.apply_breaks(input_path, output_path, {2})

        assert paragraph_count == 1
        content = mock_fs.read_text(output_path)
        assert "Line one Line two" in content
        assert "[00:00:01.000]" in content  # Should have first timestamp

    def test_apply_breaks_preserves_first_timestamp(self, mock_fs):
        """Test that first timestamp of paragraph is preserved."""
        breaker = ParagraphBreaker(fs=mock_fs)

        input_content = """[00:00:01.000] First
[00:00:02.000] Second
[00:00:03.000] Third"""
        input_path = Path("/input.md")
        output_path = Path("/output.md")
        mock_fs.write_text(input_path, input_content)

        paragraph_count = breaker.apply_breaks(input_path, output_path, {3})

        content = mock_fs.read_text(output_path)
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

        # Should have timestamp from first line of paragraph
        assert "[00:00:01.000]" in paragraphs[0]
        assert "[00:00:02.000]" not in paragraphs[0]  # Later timestamps removed

    def test_convert_timestamp_to_link_hms_format(self):
        """Test converting HH:MM:SS timestamp to YouTube link."""
        breaker = ParagraphBreaker(video_id="dQw4w9WgXcQ")
        timestamp = "[00:01:08.400]"
        result = breaker.convert_timestamp_to_link(timestamp)

        assert result == "[[00:01:08]](https://youtube.com/watch?v=dQw4w9WgXcQ&t=68s)"

    def test_convert_timestamp_to_link_ms_format(self):
        """Test converting MM:SS timestamp to YouTube link."""
        breaker = ParagraphBreaker(video_id="dQw4w9WgXcQ")
        timestamp = "[01:30.500]"
        result = breaker.convert_timestamp_to_link(timestamp)

        assert result == "[[01:30]](https://youtube.com/watch?v=dQw4w9WgXcQ&t=90s)"

    def test_convert_timestamp_to_link_no_video_id(self):
        """Test timestamp conversion without video_id returns original."""
        breaker = ParagraphBreaker(video_id=None)
        timestamp = "[00:01:08.400]"
        result = breaker.convert_timestamp_to_link(timestamp)

        assert result == "[00:01:08.400]"

    def test_convert_timestamp_to_link_rounds_down_subseconds(self):
        """Test that subseconds are rounded down."""
        breaker = ParagraphBreaker(video_id="test123")
        timestamp = "[00:01:08.999]"
        result = breaker.convert_timestamp_to_link(timestamp)

        # Should round down to 68 seconds, not 69
        assert "t=68s" in result
        assert "[[00:01:08]]" in result

    def test_apply_breaks_with_video_id_creates_links(self, mock_fs):
        """Test that applying breaks with video_id creates clickable links."""
        breaker = ParagraphBreaker(fs=mock_fs, video_id="test_video_id")

        input_content = "[00:00:01.000] First line\n[00:00:02.000] Second line"
        input_path = Path("/input.md")
        output_path = Path("/output.md")
        mock_fs.write_text(input_path, input_content)

        breaker.apply_breaks(input_path, output_path, {2})

        content = mock_fs.read_text(output_path)

        # Should contain markdown link instead of plain timestamp
        assert "[[00:00:01]](https://youtube.com/watch?v=test_video_id&t=1s)" in content
        assert "[00:00:01.000]" not in content  # Original timestamp should be replaced


class TestExtractVideoIdFromPath:
    """Tests for extract_video_id_from_path function."""

    def test_extract_video_id_standard_format(self):
        """Test extracting video ID from standard file path."""
        path = Path("youtube_dQw4w9WgXcQ_transcript.md")
        result = extract_video_id_from_path(path)
        assert result == "dQw4w9WgXcQ"

    def test_extract_video_id_with_hyphens(self):
        """Test extracting video ID with hyphens."""
        path = Path("youtube_test-video-123_deduped.md")
        result = extract_video_id_from_path(path)
        assert result == "test-video-123"

    def test_extract_video_id_with_underscores(self):
        """Test extracting video ID with underscores."""
        path = Path("youtube_test_video_123_output.md")
        result = extract_video_id_from_path(path)
        assert result == "test_video_123"

    def test_extract_video_id_no_match(self):
        """Test returns None when pattern doesn't match."""
        path = Path("some_other_file.md")
        result = extract_video_id_from_path(path)
        assert result is None

    def test_extract_video_id_from_full_path(self):
        """Test extraction works with full path, not just filename."""
        path = Path("/some/directory/youtube_abc123_transcript.md")
        result = extract_video_id_from_path(path)
        assert result == "abc123"
